from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class RagConfigurationError(ValueError):
    pass


def _positive_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RagConfigurationError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise RagConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _enabled(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise RagConfigurationError(f"{name} must be one of 0, 1, true, or false.")


@dataclass(frozen=True)
class RagConfig:
    enabled: bool = True
    embedding_model: str = "nomic-embed-text:latest"
    chunk_size: int = 1200
    chunk_overlap: int = 180
    top_k: int = 8
    context_limit: int = 12_000
    storage_path: Path = Path("data/rag")

    @classmethod
    def from_env(cls) -> "RagConfig":
        project_root = Path(__file__).resolve().parents[1]
        configured_path = os.getenv("SIH_RAG_STORAGE_PATH")
        storage_path = (
            Path(configured_path).expanduser().resolve()
            if configured_path
            else (project_root / "data" / "rag").resolve()
        )
        embedding_model = os.getenv("SIH_EMBED_MODEL", cls.embedding_model).strip()
        if not embedding_model or len(embedding_model) > 120:
            raise RagConfigurationError("SIH_EMBED_MODEL must be 1-120 characters.")
        chunk_size = _positive_int("SIH_RAG_CHUNK_SIZE", cls.chunk_size, 256, 8_000)
        chunk_overlap = _positive_int("SIH_RAG_CHUNK_OVERLAP", cls.chunk_overlap, 0, 2_000)
        if chunk_overlap >= chunk_size:
            raise RagConfigurationError("SIH_RAG_CHUNK_OVERLAP must be smaller than chunk size.")
        return cls(
            enabled=_enabled("SIH_RAG_ENABLED"),
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=_positive_int("SIH_RAG_TOP_K", cls.top_k, 1, 20),
            context_limit=_positive_int("SIH_RAG_CONTEXT_LIMIT", cls.context_limit, 1_000, 48_000),
            storage_path=storage_path,
        )
