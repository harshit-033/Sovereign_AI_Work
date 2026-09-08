from __future__ import annotations

from dataclasses import dataclass

from .models import CapabilityId


@dataclass(frozen=True)
class CapabilityHandler:
    """Binding metadata for an existing subsystem handler.

    The server owns the async transport and binds these names to the existing
    General, document, and RagService execution paths; this layer does not
    duplicate inference, OCR, or retrieval.
    """

    capability: CapabilityId
    name: str
    subsystem: str


DEFAULT_HANDLERS = (
    CapabilityHandler(CapabilityId.GENERAL_CHAT, "general_chat_handler", "AIService"),
    CapabilityHandler(CapabilityId.DOCUMENT_ANALYSIS, "document_analysis_handler", "DocumentService + AIService"),
    CapabilityHandler(CapabilityId.KNOWLEDGE_RAG, "knowledge_rag_handler", "RagService + AIService"),
    CapabilityHandler(CapabilityId.AGENT_TASK, "agent_task_handler", "AgentService"),
)
