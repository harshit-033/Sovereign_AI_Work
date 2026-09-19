from __future__ import annotations

import os
from dataclasses import dataclass


class RoutingConfigurationError(ValueError):
    pass


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RoutingConfigurationError(f"{name} must be one of 0, 1, true, or false.")


def _model(name: str, fallback: str) -> str:
    value = os.getenv(name, fallback).strip()
    if not value or len(value) > 120 or any(char in value for char in "\r\n"):
        raise RoutingConfigurationError(f"{name} must be 1-120 characters without newlines.")
    return value


@dataclass(frozen=True)
class RoutingConfig:
    enabled: bool = True
    auto_enabled: bool = True
    general_model: str = "llama3.2:latest"
    document_model: str = "llama3.2:latest"
    rag_model: str = "llama3.2:latest"
    agent_model: str = "llama3.2:latest"
    agent_enabled: bool = True

    @classmethod
    def from_env(cls) -> "RoutingConfig":
        fallback = os.getenv("LOCAL_AI_MODEL_NAME", cls.general_model).strip() or cls.general_model
        return cls(
            enabled=_flag("LOCAL_AI_ROUTING_ENABLED", True),
            auto_enabled=_flag("LOCAL_AI_AUTO_ROUTING_ENABLED", True),
            general_model=_model("LOCAL_AI_GENERAL_MODEL", fallback),
            document_model=_model("LOCAL_AI_DOCUMENT_MODEL", fallback),
            rag_model=_model("LOCAL_AI_RAG_MODEL", fallback),
            agent_model=_model("LOCAL_AI_AGENT_MODEL", fallback),
            agent_enabled=_flag("LOCAL_AI_AGENT_ENABLED", True),
        )
