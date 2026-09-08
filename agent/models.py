from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    session_id: str
    user_id: str
    role: str
    request: str
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ToolCall:
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentPlan:
    task_id: str
    steps: tuple[ToolCall, ...]
    planning_latency_ms: float
    reason: str


@dataclass(frozen=True)
class AgentContext:
    task: AgentTask
    current_document_id: Optional[str] = None
    collection_id: Optional[str] = None


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    task_id: str
    session_id: str
    user_id: str
    tool_id: str
    purpose: str
    safe_arguments: dict[str, Any]
    risk_level: str
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_id: str
    status: str
    data: Any = None
    error: str = ""
    execution_latency_ms: float = 0.0
    approval: Optional[ApprovalRequest] = None


@dataclass(frozen=True)
class VerificationResult:
    tool_id: str
    passed: bool
    message: str
    verification_latency_ms: float = 0.0


@dataclass(frozen=True)
class AgentExecutionResult:
    task_id: str
    status: str
    message: str
    plan: AgentPlan
    tool_results: tuple[ToolExecutionResult, ...] = ()
    verifications: tuple[VerificationResult, ...] = ()
    generated_files: tuple[dict[str, Any], ...] = ()
    approval: Optional[ApprovalRequest] = None
    total_latency_ms: float = 0.0


@dataclass(frozen=True)
class AuditRecord:
    task_id: str
    session_id: str
    user_id: str
    timestamp: float
    requested_capability: str
    selected_tools: tuple[str, ...] = ()
    policy_decisions: tuple[str, ...] = ()
    approval_decision: str = "NOT_REQUIRED"
    tool_execution_status: tuple[str, ...] = ()
    verification_result: tuple[str, ...] = ()
    final_status: str = "STARTED"
    generated_files: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "requested_capability": self.requested_capability,
            "selected_tools": list(self.selected_tools),
            "policy_decisions": list(self.policy_decisions),
            "approval_decision": self.approval_decision,
            "tool_execution_status": list(self.tool_execution_status),
            "verification_result": list(self.verification_result),
            "final_status": self.final_status,
            "generated_files": list(self.generated_files),
        }
