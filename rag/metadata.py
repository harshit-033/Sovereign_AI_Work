from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from .models import CollectionRecord, IndexedDocument, RagStatus

COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,59}$")


class RagMetadataError(RuntimeError):
    pass


def normalize_collection_name(name: str) -> str:
    clean = " ".join(name.strip().split())
    if not COLLECTION_PATTERN.fullmatch(clean):
        raise ValueError("Collection name must be 1-60 characters and use letters, numbers, spaces, dot, dash, or underscore.")
    return clean


class MetadataStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._collections: dict[str, CollectionRecord] = {}
        self._documents: dict[str, IndexedDocument] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._collections = {
                item["collection_id"]: CollectionRecord(**item)
                for item in data.get("collections", [])
            }
            self._documents = {
                item["document_id"]: IndexedDocument.from_dict(item)
                for item in data.get("documents", [])
            }
        except Exception as exc:
            raise RagMetadataError(f"RAG metadata store is invalid: {self.path}") from exc

    def _save(self) -> None:
        temp = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        payload = {
            "version": 1,
            "collections": [item.to_dict() for item in self._collections.values()],
            "documents": [item.to_dict() | {"source_path": item.source_path} for item in self._documents.values()],
        }
        try:
            with temp.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                temp.chmod(0o600)
            except OSError:
                pass
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def create_collection(self, owner_user_id: str, name: str) -> CollectionRecord:
        with self._lock:
            clean = normalize_collection_name(name)
            if any(
                item.owner_user_id == owner_user_id and item.name.casefold() == clean.casefold()
                for item in self._collections.values()
            ):
                raise ValueError("Collection already exists.")
            collection = CollectionRecord(
                collection_id=f"col_{uuid.uuid4().hex[:16]}",
                owner_user_id=owner_user_id,
                name=clean,
            )
            self._collections[collection.collection_id] = collection
            self._save()
            return collection

    def get_collection(self, owner_user_id: str, collection_id: str) -> Optional[CollectionRecord]:
        with self._lock:
            collection = self._collections.get(collection_id)
            return collection if collection and collection.owner_user_id == owner_user_id else None

    def list_collections(self, owner_user_id: str) -> list[CollectionRecord]:
        with self._lock:
            return sorted(
                (item for item in self._collections.values() if item.owner_user_id == owner_user_id),
                key=lambda item: (item.name.casefold(), item.created_at),
            )

    def find_duplicate(self, owner_user_id: str, collection_id: str, file_hash: str) -> Optional[IndexedDocument]:
        with self._lock:
            return next(
                (
                    item
                    for item in self._documents.values()
                    if item.owner_user_id == owner_user_id
                    and item.collection_id == collection_id
                    and item.file_hash == file_hash
                ),
                None,
            )

    def get_document(self, owner_user_id: str, document_id: str) -> Optional[IndexedDocument]:
        with self._lock:
            document = self._documents.get(document_id)
            return document if document and document.owner_user_id == owner_user_id else None

    def list_documents(self, owner_user_id: str, collection_id: Optional[str] = None) -> list[IndexedDocument]:
        with self._lock:
            return sorted(
                (
                    item
                    for item in self._documents.values()
                    if item.owner_user_id == owner_user_id
                    and (collection_id is None or item.collection_id == collection_id)
                ),
                key=lambda item: item.updated_at,
                reverse=True,
            )

    def upsert_document(self, document: IndexedDocument) -> None:
        with self._lock:
            self._documents[document.document_id] = document
            self._save()

    def update_document(self, document_id: str, **changes: object) -> IndexedDocument:
        with self._lock:
            document = self._documents[document_id]
            for key, value in changes.items():
                setattr(document, key, value)
            document.updated_at = time.time()
            self._save()
            return document

    def delete_document(self, owner_user_id: str, document_id: str) -> Optional[IndexedDocument]:
        with self._lock:
            document = self.get_document(owner_user_id, document_id)
            if not document:
                return None
            removed = self._documents.pop(document_id)
            self._save()
            return removed
