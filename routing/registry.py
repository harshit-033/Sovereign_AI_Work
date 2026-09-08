from __future__ import annotations

from typing import Iterable

from .config import RoutingConfig
from .models import CapabilityDefinition, CapabilityId


class CapabilityRegistry:
    """Extensible metadata registry; execution remains in existing handlers."""

    def __init__(self, definitions: Iterable[CapabilityDefinition] = ()):
        self._definitions: dict[CapabilityId, CapabilityDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: CapabilityDefinition) -> None:
        if definition.capability_id in self._definitions:
            raise ValueError(f"Capability already registered: {definition.capability_id.value}")
        self._definitions[definition.capability_id] = definition

    def get(self, capability: CapabilityId) -> CapabilityDefinition:
        return self._definitions[capability]

    def all(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions.values())

    def contains(self, capability: CapabilityId) -> bool:
        return capability in self._definitions


def build_default_registry(config: RoutingConfig) -> CapabilityRegistry:
    return CapabilityRegistry(
        (
            CapabilityDefinition(
                CapabilityId.GENERAL_CHAT,
                "General Chat",
                "Local conversational assistance without private document context.",
                "general_chat_handler",
                config.general_model,
                priority=10,
            ),
            CapabilityDefinition(
                CapabilityId.DOCUMENT_ANALYSIS,
                "Document Analysis",
                "Question answering against the selected session-owned PDF.",
                "document_analysis_handler",
                config.document_model,
                requires_document=True,
                priority=20,
            ),
            CapabilityDefinition(
                CapabilityId.KNOWLEDGE_RAG,
                "Knowledge RAG",
                "Owner-scoped semantic retrieval from indexed local documents.",
                "knowledge_rag_handler",
                config.rag_model,
                requires_knowledge_base=True,
                priority=30,
            ),
            CapabilityDefinition(
                CapabilityId.AGENT_TASK,
                "Agent Task",
                "Bounded execution of an allowlisted local workflow.",
                "agent_task_handler",
                config.agent_model,
                enabled=config.agent_enabled,
                priority=40,
            ),
        )
    )
