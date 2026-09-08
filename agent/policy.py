from __future__ import annotations

import re

from .models import AgentContext, PolicyDecision, ToolCall
from .registry import ToolDefinition, ToolRegistry


class PolicyEngine:
    """Application policy boundary for all agent tool execution."""

    def __init__(self, registry: ToolRegistry, session_manager, rag_service):
        self.registry = registry
        self.session_manager = session_manager
        self.rag_service = rag_service

    def check(self, context: AgentContext, call: ToolCall, tool: ToolDefinition | None = None) -> PolicyDecision:
        try:
            tool = tool or self.registry.validate(call)
            if not context.task.user_id or not context.task.session_id:
                return PolicyDecision.DENY
            if tool.tool_id in {"get_document_metadata", "retrieve_document_information"}:
                document_id = call.arguments.get("document_id", "")
                if not self.session_manager.verify_document_ownership(context.task.session_id, document_id):
                    return PolicyDecision.DENY
            if tool.tool_id == "search_knowledge":
                collection_id = call.arguments.get("collection_id")
                if collection_id:
                    self.rag_service.require_collection(context.task.user_id, collection_id)
            if tool.requires_approval:
                return PolicyDecision.REQUIRE_APPROVAL
            return PolicyDecision.ALLOW
        except Exception:
            return PolicyDecision.DENY

    @staticmethod
    def safe_arguments(call: ToolCall) -> dict:
        safe = {}
        for key, value in call.arguments.items():
            if key == "content" and isinstance(value, str):
                safe[key] = f"<content:{len(value)} chars>"
            elif isinstance(value, str) and len(value) > 120:
                safe[key] = value[:117] + "..."
            else:
                safe[key] = value
        return safe
