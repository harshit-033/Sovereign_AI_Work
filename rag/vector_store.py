from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings

from .models import RagChunk, RetrievalResult


class VectorStoreError(RuntimeError):
    pass


class PersistentVectorStore:
    COLLECTION_NAME = "sih_rag_chunks"

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.path),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine", "indexing_version": "phase5-v1"},
            )
        except Exception as exc:
            raise VectorStoreError("The local vector store could not be opened.") from exc

    def upsert(self, chunks: list[RagChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("Chunk and embedding counts do not match.")
        if not chunks:
            raise VectorStoreError("Cannot index an empty chunk set.")
        try:
            with self._lock:
                self.collection.upsert(
                    ids=[chunk.chunk_id for chunk in chunks],
                    embeddings=embeddings,
                    documents=[chunk.text for chunk in chunks],
                    metadatas=[chunk.metadata() for chunk in chunks],
                )
        except Exception as exc:
            raise VectorStoreError("The local vector store rejected the chunks.") from exc

    def delete_document(self, document_id: str) -> None:
        try:
            with self._lock:
                self.collection.delete(where={"document_id": document_id})
        except Exception as exc:
            raise VectorStoreError("The document vectors could not be deleted.") from exc

    def query(
        self,
        embedding: list[float],
        owner_user_id: str,
        collection_id: Optional[str],
        top_k: int,
    ) -> list[RetrievalResult]:
        filters: list[dict[str, str]] = [{"owner_user_id": owner_user_id}]
        if collection_id:
            filters.append({"collection_id": collection_id})
        where: dict[str, Any] = filters[0] if len(filters) == 1 else {"$and": filters}
        try:
            with self._lock:
                result = self.collection.query(
                    query_embeddings=[embedding],
                    n_results=top_k,
                    where=where,
                    include=["documents", "metadatas", "distances"],
                )
        except Exception as exc:
            raise VectorStoreError("The local vector search failed.") from exc

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        results: list[RetrievalResult] = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index]
            if metadata.get("owner_user_id") != owner_user_id:
                continue
            results.append(
                RetrievalResult(
                    chunk_id=str(chunk_id),
                    document_id=str(metadata["document_id"]),
                    owner_user_id=str(metadata["owner_user_id"]),
                    collection_id=str(metadata["collection_id"]),
                    filename=str(metadata["filename"]),
                    page_number=int(metadata["page_number"]),
                    extraction_method=str(metadata["extraction_method"]),
                    chunk_index=int(metadata["chunk_index"]),
                    text=str(documents[index]),
                    distance=float(distances[index]),
                )
            )
        return results

    def count(self) -> int:
        with self._lock:
            return int(self.collection.count())

    def close(self) -> None:
        with self._lock:
            close = getattr(self.client, "close", None)
            if close:
                close()
