from __future__ import annotations

from .models import CapabilityId, RoutingContext


class CapabilityClassifier:
    """Deterministic, conservative classifier that never reads document text."""

    _RAG_TERMS = (
        "knowledge base", "indexed", "search", "across", "reports", "documents",
        "maintenance report", "inspection reports", "what do our", "what do my",
        "in my files", "in our files", "from my files", "from our files",
    )
    _DOCUMENT_TERMS = (
        "this document", "this pdf", "this file", "selected document", "uploaded",
        "page ", "summarize the report", "in the report", "in this report",
        "equipment id", "document analysis",
    )
    _GENERAL_TERMS = (
        "hello", "hi", "hey", "what can you do", "explain", "how does", "define",
        "meaning of", "write ", "help me", "who are you",
    )
    _AGENT_TERMS = (
        "create a pdf", "create pdf", "generate a pdf", "generate pdf",
        "save the result", "save as a text", "text report", "txt report",
        "calculate the average", "list my available documents", "find and create",
        "search and create", "analyze and create", "report from", "then save",
        "summarize", "sumarize", "make a report", "prepare a report", "create a summary",
        "create a report", "generate a report", "create txt", "generate txt",
        "save as", "export", "make a text file",
    )

    def classify(self, context: RoutingContext) -> tuple[CapabilityId, float, str, str]:
        message = " ".join(context.message.casefold().split())
        rag_allowed = CapabilityId.KNOWLEDGE_RAG in context.available_capabilities
        document_allowed = CapabilityId.DOCUMENT_ANALYSIS in context.available_capabilities

        rag_signal = any(term in message for term in self._RAG_TERMS)
        document_signal = any(term in message for term in self._DOCUMENT_TERMS)
        agent_signal = any(term in message for term in self._AGENT_TERMS)
        if agent_signal and CapabilityId.AGENT_TASK in context.available_capabilities:
            return (
                CapabilityId.AGENT_TASK,
                0.95,
                "bounded_workflow_request",
                "The request requires a sequence of registered local operations.",
            )
        if rag_signal and rag_allowed:
            return (
                CapabilityId.KNOWLEDGE_RAG,
                0.94,
                "cross_document_query",
                "The request asks for information across the local knowledge base.",
            )
        if document_allowed and context.selected_document_id and document_signal:
            return (
                CapabilityId.DOCUMENT_ANALYSIS,
                0.93,
                "selected_document_reference",
                "The request refers to the selected session document.",
            )
        if document_allowed and context.selected_document_id and not any(
            term in message for term in self._GENERAL_TERMS
        ) and not rag_signal:
            return (
                CapabilityId.DOCUMENT_ANALYSIS,
                0.62,
                "selected_document_ambiguous",
                "A session document is selected, so the ambiguous request stays within that document.",
            )
        return (
            CapabilityId.GENERAL_CHAT,
            0.88 if any(term in message for term in self._GENERAL_TERMS) else 0.55,
            "general_fallback",
            "No safe document or knowledge-base intent was established; using General Chat.",
        )
