from __future__ import annotations

import threading
import uuid

from .models import ApprovalRequest


class ApprovalManager:
    def __init__(self):
        self._pending: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def create(self, task_id: str, session_id: str, user_id: str, tool_id: str, purpose: str, safe_arguments: dict, risk_level: str) -> ApprovalRequest:
        request = ApprovalRequest(
            approval_id=f"approval_{uuid.uuid4().hex}",
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            tool_id=tool_id,
            purpose=purpose,
            safe_arguments=safe_arguments,
            risk_level=risk_level,
        )
        with self._lock:
            self._pending[request.approval_id] = request
        return request

    def list_for_session(self, session_id: str, user_id: str) -> list[ApprovalRequest]:
        with self._lock:
            return [item for item in self._pending.values() if item.session_id == session_id and item.user_id == user_id and item.status == "PENDING"]

    def resolve(self, approval_id: str, session_id: str, user_id: str, approved: bool) -> ApprovalRequest:
        with self._lock:
            current = self._pending.get(approval_id)
            if not current or current.session_id != session_id or current.user_id != user_id:
                raise PermissionError("Approval request not found or access denied.")
            updated = ApprovalRequest(**{**current.__dict__, "status": "APPROVED" if approved else "DENIED"})
            self._pending[approval_id] = updated
            return updated

    def get(self, approval_id: str) -> ApprovalRequest | None:
        with self._lock:
            return self._pending.get(approval_id)
