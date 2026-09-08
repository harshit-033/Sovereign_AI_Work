from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CapabilityId(str, Enum):
    GENERAL_CHAT = "GENERAL_CHAT"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    KNOWLEDGE_RAG = "KNOWLEDGE_RAG"
    AGENT_TASK = "AGENT_TASK"


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: CapabilityId
    display_name: str
    description: str
    handler: str
    model_name: str
    requires_document: bool = False
    requires_knowledge_base: bool = False
    enabled: bool = True
    priority: int = 0


@dataclass(frozen=True)
class RoutingContext:
    """Non-sensitive request/session facts used by the classifier."""

    user_id: str
    role: str
    selected_mode: Optional[str]
    selected_document_id: Optional[str]
    knowledge_collection_id: Optional[str]
    message: str
    knowledge_base_available: bool = True
    available_capabilities: tuple[CapabilityId, ...] = field(
        default_factory=lambda: tuple(CapabilityId)
    )


@dataclass(frozen=True)
class RoutingDecision:
    capability: CapabilityId
    display_name: str
    confidence: float
    reason_code: str
    reason: str
    model_name: str
    handler: str
    requires_document: bool
    requires_knowledge_base: bool
    explicit: bool
    routing_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.value,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "model": self.model_name,
            "handler": self.handler,
            "requires_document": self.requires_document,
            "requires_knowledge_base": self.requires_knowledge_base,
            "explicit": self.explicit,
            "routing_latency_ms": self.routing_latency_ms,
        }


@dataclass(frozen=True)
class CapabilityHealth:
    capability: CapabilityId
    available: bool
    model_name: str
    handler: str
    reason: str = ""
    display_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability.value,
            "display_name": self.display_name or self.capability.value.replace("_", " ").title(),
            "available": self.available,
            "model": self.model_name,
            "handler": self.handler,
            "reason": self.reason,
        }
