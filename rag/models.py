from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RagStatus(str, Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


@dataclass
class CollectionRecord:
    collection_id: str
    owner_user_id: str
    name: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_id": self.collection_id,
            "owner_user_id": self.owner_user_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class IndexedDocument:
    document_id: str
    owner_user_id: str
    collection_id: str
    filename: str
    file_hash: str
    page_count: int
    status: RagStatus
    created_at: float
    updated_at: float
    extracted_chars: int = 0
    file_size_mb: float = 0.0
    extraction_seconds: float = 0.0
    native_pages: int = 0
    ocr_pages: int = 0
    method_summary: str = ""
    embedding_model: str = ""
    chunk_count: int = 0
    indexing_version: str = "phase5-v1"
    failure_reason: Optional[str] = None
    source_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "owner_user_id": self.owner_user_id,
            "collection_id": self.collection_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "page_count": self.page_count,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "extracted_chars": self.extracted_chars,
            "file_size_mb": round(self.file_size_mb, 2),
            "extraction_seconds": round(self.extraction_seconds, 2),
            "native_pages": self.native_pages,
            "ocr_pages": self.ocr_pages,
            "method_summary": self.method_summary,
            "embedding_model": self.embedding_model,
            "chunk_count": self.chunk_count,
            "indexing_version": self.indexing_version,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexedDocument":
        return cls(
            document_id=str(data["document_id"]),
            owner_user_id=str(data["owner_user_id"]),
            collection_id=str(data["collection_id"]),
            filename=str(data["filename"]),
            file_hash=str(data["file_hash"]),
            page_count=int(data.get("page_count", 0)),
            status=RagStatus(str(data.get("status", RagStatus.FAILED.value))),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            extracted_chars=int(data.get("extracted_chars", 0)),
            file_size_mb=float(data.get("file_size_mb", 0.0)),
            extraction_seconds=float(data.get("extraction_seconds", 0.0)),
            native_pages=int(data.get("native_pages", 0)),
            ocr_pages=int(data.get("ocr_pages", 0)),
            method_summary=str(data.get("method_summary", "")),
            embedding_model=str(data.get("embedding_model", "")),
            chunk_count=int(data.get("chunk_count", 0)),
            indexing_version=str(data.get("indexing_version", "phase5-v1")),
            failure_reason=data.get("failure_reason"),
            source_path=str(data.get("source_path", "")),
        )


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    document_id: str
    owner_user_id: str
    collection_id: str
    filename: str
    page_number: int
    extraction_method: str
    chunk_index: int
    text: str
    indexing_version: str = "phase5-v1"
    indexed_at: float = field(default_factory=time.time)

    def metadata(self) -> dict[str, str | int]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "owner_user_id": self.owner_user_id,
            "collection_id": self.collection_id,
            "filename": self.filename,
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "chunk_index": self.chunk_index,
            "indexing_version": self.indexing_version,
            "indexed_at": self.indexed_at,
        }


@dataclass(frozen=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    owner_user_id: str
    collection_id: str
    filename: str
    page_number: int
    extraction_method: str
    chunk_index: int
    text: str
    distance: float

    def source_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "filename": self.filename,
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "distance": round(self.distance, 6),
        }
