from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from document.models import DocumentExtraction

from .chunker import chunk_document
from .config import RagConfig
from .embeddings import EmbeddingService, RagEmbeddingError
from .file_store import RagFileStore, RagFileStoreError
from .metadata import MetadataStore, RagMetadataError
from .models import CollectionRecord, IndexedDocument, RagStatus, RetrievalResult
from .prompts import build_rag_prompt
from .vector_store import PersistentVectorStore, VectorStoreError

logger = logging.getLogger(__name__)


class RagError(RuntimeError):
    pass


class RagDisabledError(RagError):
    pass


class RagNotFoundError(RagError):
    pass


class RagConflictError(RagError):
    pass


class RagService:
    def __init__(
        self,
        config: Optional[RagConfig] = None,
        metadata_store: Optional[MetadataStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[PersistentVectorStore] = None,
        file_store: Optional[RagFileStore] = None,
    ):
        self.config = config or RagConfig.from_env()
        self._lock = threading.RLock()
        self.metadata = metadata_store or MetadataStore(self.config.storage_path / "metadata" / "rag.json")
        self.files = file_store or RagFileStore(self.config.storage_path / "documents")
        self.embeddings = embedding_service or EmbeddingService(self.config.embedding_model)
        self.vectors = vector_store or PersistentVectorStore(self.config.storage_path / "chroma")

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise RagDisabledError("Knowledge Chat is disabled. Set SIH_RAG_ENABLED=1 to enable it.")

    def create_collection(self, owner_user_id: str, name: str) -> CollectionRecord:
        self._require_enabled()
        return self.metadata.create_collection(owner_user_id, name)

    def list_collections(self, owner_user_id: str) -> list[CollectionRecord]:
        self._require_enabled()
        return self.metadata.list_collections(owner_user_id)

    def ensure_default_collection(self, owner_user_id: str) -> CollectionRecord:
        self._require_enabled()
        collections = self.metadata.list_collections(owner_user_id)
        return collections[0] if collections else self.metadata.create_collection(owner_user_id, "General")

    def require_collection(self, owner_user_id: str, collection_id: str) -> CollectionRecord:
        self._require_enabled()
        collection = self.metadata.get_collection(owner_user_id, collection_id)
        if not collection:
            raise RagNotFoundError("Collection not found or access denied.")
        return collection

    def list_documents(self, owner_user_id: str, collection_id: Optional[str] = None) -> list[IndexedDocument]:
        self._require_enabled()
        if collection_id:
            self.require_collection(owner_user_id, collection_id)
        return self.metadata.list_documents(owner_user_id, collection_id)

    def get_document(self, owner_user_id: str, document_id: str) -> IndexedDocument:
        self._require_enabled()
        document = self.metadata.get_document(owner_user_id, document_id)
        if not document:
            raise RagNotFoundError("Document not found or access denied.")
        return document

    def _new_document(
        self,
        owner_user_id: str,
        collection_id: str,
        filename: str,
        file_hash: str,
    ) -> IndexedDocument:
        now = time.time()
        return IndexedDocument(
            document_id=f"doc_{uuid.uuid4().hex}",
            owner_user_id=owner_user_id,
            collection_id=collection_id,
            filename=filename,
            file_hash=file_hash,
            page_count=0,
            status=RagStatus.PENDING,
            created_at=now,
            updated_at=now,
            embedding_model=self.config.embedding_model,
        )

    def index_pdf(
        self,
        owner_user_id: str,
        collection_id: str,
        filename: str,
        content: bytes,
        process_pdf: Callable[[str], DocumentExtraction],
    ) -> IndexedDocument:
        self._require_enabled()
        collection = self.require_collection(owner_user_id, collection_id)
        file_hash = self.files.fingerprint(content)
        with self._lock:
            existing = self.metadata.find_duplicate(owner_user_id, collection.collection_id, file_hash)
            if existing and existing.status == RagStatus.INDEXING:
                raise RagConflictError("This document is already being indexed.")
            document = existing or self._new_document(owner_user_id, collection.collection_id, filename, file_hash)
            document.filename = filename
            document.embedding_model = self.config.embedding_model
            if not existing:
                source_path = self.files.save(document.document_id, content)
                document.source_path = str(source_path)
            else:
                try:
                    self.files.get(document.document_id)
                except RagFileStoreError:
                    source_path = self.files.save(document.document_id, content)
                    document.source_path = str(source_path)
            self.metadata.upsert_document(document)
            return self._index_existing_locked(document, process_pdf)

    def _index_existing_locked(
        self,
        document: IndexedDocument,
        process_pdf: Callable[[str], DocumentExtraction],
    ) -> IndexedDocument:
        self.metadata.update_document(
            document.document_id,
            status=RagStatus.INDEXING,
            failure_reason=None,
            chunk_count=0,
        )
        logger.info(
            "RAG indexing started document_id=%s collection_id=%s owner_user_id=%s",
            document.document_id,
            document.collection_id,
            document.owner_user_id,
        )
        try:
            extraction = process_pdf(document.source_path)
            if not extraction.pages:
                raise RagError("The PDF has no readable text to index.")
            chunks = chunk_document(
                document.document_id,
                document.owner_user_id,
                document.collection_id,
                document.filename,
                extraction,
                self.config,
            )
            if not chunks:
                raise RagError("The PDF produced no indexable text chunks.")
            embeddings = self.embeddings.embed_documents([chunk.text for chunk in chunks])
            self.vectors.delete_document(document.document_id)
            self.vectors.upsert(chunks, embeddings)
            indexed = self.metadata.update_document(
                document.document_id,
                status=RagStatus.INDEXED,
                page_count=extraction.page_count,
                extracted_chars=extraction.extracted_chars,
                file_size_mb=extraction.file_size_mb,
                extraction_seconds=extraction.extraction_seconds,
                native_pages=extraction.native_pages,
                ocr_pages=extraction.ocr_pages,
                method_summary=extraction.method_summary,
                embedding_model=self.config.embedding_model,
                chunk_count=len(chunks),
                failure_reason=None,
            )
            logger.info(
                "RAG indexing completed document_id=%s chunks=%d extraction_seconds=%.2f",
                document.document_id,
                len(chunks),
                extraction.extraction_seconds,
            )
            return indexed
        except Exception as exc:
            try:
                self.vectors.delete_document(document.document_id)
            except Exception:
                logger.exception("Failed to roll back vectors for document_id=%s", document.document_id)
            reason = str(exc) if isinstance(exc, RagError) else "Document indexing failed."
            failed = self.metadata.update_document(
                document.document_id,
                status=RagStatus.FAILED,
                failure_reason=reason[:500],
                chunk_count=0,
            )
            logger.exception("RAG indexing failed document_id=%s", document.document_id)
            raise RagError(reason) from exc

    def reindex_document(
        self,
        owner_user_id: str,
        document_id: str,
        process_pdf: Callable[[str], DocumentExtraction],
    ) -> IndexedDocument:
        self._require_enabled()
        with self._lock:
            document = self.get_document(owner_user_id, document_id)
            if document.status == RagStatus.INDEXING:
                raise RagConflictError("This document is already being indexed.")
            self.files.get(document.document_id)
            return self._index_existing_locked(document, process_pdf)

    def delete_document(self, owner_user_id: str, document_id: str) -> None:
        self._require_enabled()
        with self._lock:
            document = self.get_document(owner_user_id, document_id)
            if not document:
                raise RagNotFoundError("Document not found or access denied.")
            self.vectors.delete_document(document.document_id)
            removed = self.metadata.delete_document(owner_user_id, document_id)
            if not removed:
                raise RagNotFoundError("Document not found or access denied.")
            try:
                self.files.delete(document.document_id)
            except OSError:
                logger.warning("RAG source file cleanup failed document_id=%s", document.document_id)
            logger.info("RAG document deleted document_id=%s owner_user_id=%s", document_id, owner_user_id)

    def delete_user_documents(self, owner_user_id: str) -> None:
        for document in self.metadata.list_documents(owner_user_id):
            try:
                self.delete_document(owner_user_id, document.document_id)
            except RagError:
                logger.exception("RAG user cleanup failed document_id=%s", document.document_id)

    def retrieve(
        self,
        owner_user_id: str,
        question: str,
        collection_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> list[RetrievalResult]:
        self._require_enabled()
        if collection_id:
            self.require_collection(owner_user_id, collection_id)
        limit = top_k or self.config.top_k
        if not 1 <= limit <= 20:
            raise ValueError("top_k must be between 1 and 20.")
        embedding = self.embeddings.embed_query(question)
        results = self.vectors.query(embedding, owner_user_id, collection_id, limit)
        authorized: list[RetrievalResult] = []
        for result in results:
            document = self.metadata.get_document(owner_user_id, result.document_id)
            if (
                document
                and document.status == RagStatus.INDEXED
                and document.collection_id == result.collection_id
            ):
                authorized.append(result)
        logger.info(
            "RAG retrieval owner_user_id=%s collection_id=%s results=%d",
            owner_user_id,
            collection_id or "all-owned",
            len(authorized),
        )
        return authorized

    def build_prompt(self, question: str, results: list[RetrievalResult]) -> str:
        return build_rag_prompt(question, results, self.config.context_limit)

    def embedding_health(self) -> dict:
        self._require_enabled()
        return self.embeddings.check_available()

    def close(self) -> None:
        close = getattr(self.vectors, "close", None)
        if close:
            close()
