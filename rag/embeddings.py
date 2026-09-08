from __future__ import annotations

import logging
from typing import Any, Sequence

import ollama

logger = logging.getLogger(__name__)


class RagEmbeddingError(RuntimeError):
    pass


def _model_names() -> list[str]:
    response = ollama.list()
    models = getattr(response, "models", None)
    if models is None and isinstance(response, dict):
        models = response.get("models", [])
    names: list[str] = []
    for model in models or []:
        name = getattr(model, "model", None) or getattr(model, "name", None)
        if not name and isinstance(model, dict):
            name = model.get("model") or model.get("name")
        if name:
            names.append(str(name))
    return names


class EmbeddingService:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.dimension: int | None = None

    def check_available(self) -> dict[str, Any]:
        try:
            names = _model_names()
            available = any(
                self.model_name == name or name.startswith(self.model_name.split(":")[0])
                for name in names
            )
            result = {
                "connected": True,
                "model_configured": self.model_name,
                "model_available": available,
                "available_models": names,
            }
            if not available:
                result["error"] = (
                    f"Embedding model is not installed. Run `ollama pull {self.model_name}`."
                )
            return result
        except Exception as exc:
            logger.warning("Embedding model health check failed: %s", exc)
            return {
                "connected": False,
                "model_configured": self.model_name,
                "model_available": False,
                "available_models": [],
                "error": "Local embedding service is unavailable.",
            }

    @staticmethod
    def _extract_embeddings(response: Any) -> list[list[float]]:
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings")
        if not embeddings:
            raise RagEmbeddingError("The local embedding model returned no vectors.")
        return [list(map(float, vector)) for vector in embeddings]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = ollama.embed(model=self.model_name, input=list(texts))
            vectors = self._extract_embeddings(response)
        except RagEmbeddingError:
            raise
        except Exception as exc:
            raise RagEmbeddingError(
                f"Embedding model '{self.model_name}' is unavailable. Run `ollama pull {self.model_name}` and try again."
            ) from exc
        if len(vectors) != len(texts):
            raise RagEmbeddingError("The local embedding model returned an unexpected vector count.")
        dimension = len(vectors[0])
        if dimension == 0 or any(len(vector) != dimension for vector in vectors):
            raise RagEmbeddingError("The local embedding model returned inconsistent vector dimensions.")
        if self.dimension is not None and self.dimension != dimension:
            raise RagEmbeddingError("The embedding dimension changed; re-index the knowledge base.")
        self.dimension = dimension
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0]
