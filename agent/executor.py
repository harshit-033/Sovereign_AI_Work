from __future__ import annotations

import time
from typing import Callable, Optional

from .approval import ApprovalManager
from .models import AgentContext, ApprovalRequest, PolicyDecision, ToolCall, ToolExecutionResult
from .policy import PolicyEngine
from .registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, policy: PolicyEngine, approvals: ApprovalManager, handlers: dict[str, Callable]):
        self.registry = registry
        self.policy = policy
        self.approvals = approvals
        self.handlers = dict(handlers)

    def execute(self, context: AgentContext, call: ToolCall, approval_id: Optional[str] = None) -> ToolExecutionResult:
        started = time.perf_counter()
        try:
            definition = self.registry.validate(call)
        except (KeyError, ValueError) as exc:
            return ToolExecutionResult(
                call.tool_id,
                "DENIED",
                error="Tool operation rejected by the local allowlist.",
                execution_latency_ms=(time.perf_counter() - started) * 1000,
            )
        try:
            decision = self.policy.check(context, call, definition)
            if decision == PolicyDecision.DENY:
                return ToolExecutionResult(call.tool_id, "DENIED", error="Policy denied this tool operation.", execution_latency_ms=(time.perf_counter() - started) * 1000)
            if decision == PolicyDecision.REQUIRE_APPROVAL:
                existing = self.approvals.get(approval_id) if approval_id else None
                if existing and existing.session_id == context.task.session_id and existing.user_id == context.task.user_id and existing.status == "DENIED":
                    return ToolExecutionResult(call.tool_id, "DENIED", error="Human approval was denied for this tool operation.", execution_latency_ms=(time.perf_counter() - started) * 1000)
                if not existing or existing.session_id != context.task.session_id or existing.user_id != context.task.user_id or existing.status != "APPROVED":
                    approval = self.approvals.create(
                        context.task.task_id, context.task.session_id, context.task.user_id,
                        call.tool_id, definition.description, self.policy.safe_arguments(call), definition.risk_level,
                    )
                    return ToolExecutionResult(call.tool_id, "APPROVAL_REQUIRED", error="Human approval is required before execution.", approval=approval, execution_latency_ms=(time.perf_counter() - started) * 1000)
            handler = self.handlers.get(definition.handler)
            if not handler:
                return ToolExecutionResult(call.tool_id, "FAILED", error="Registered tool handler is unavailable.", execution_latency_ms=(time.perf_counter() - started) * 1000)
            data = handler(context, call.arguments)
            return ToolExecutionResult(call.tool_id, "COMPLETED", data=data, execution_latency_ms=(time.perf_counter() - started) * 1000)
        except Exception as exc:
            return ToolExecutionResult(call.tool_id, "FAILED", error=str(exc)[:500], execution_latency_ms=(time.perf_counter() - started) * 1000)
