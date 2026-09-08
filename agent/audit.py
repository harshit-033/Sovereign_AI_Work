from __future__ import annotations

import threading
from dataclasses import replace

from .models import AuditRecord


class AuditLogger:
    def __init__(self):
        self._records: dict[str, AuditRecord] = {}
        self._lock = threading.RLock()

    def record(self, record: AuditRecord) -> AuditRecord:
        with self._lock:
            self._records[record.task_id] = record
        return record

    def get(self, task_id: str, session_id: str, user_id: str) -> AuditRecord | None:
        with self._lock:
            record = self._records.get(task_id)
        if record and record.session_id == session_id and record.user_id == user_id:
            return record
        return None

    def list_for_session(self, session_id: str, user_id: str) -> list[AuditRecord]:
        with self._lock:
            return [record for record in self._records.values() if record.session_id == session_id and record.user_id == user_id]

    def update(self, task_id: str, **changes) -> AuditRecord | None:
        with self._lock:
            current = self._records.get(task_id)
            if not current:
                return None
            updated = replace(current, **changes)
            self._records[task_id] = updated
            return updated

    def delete_session(self, session_id: str, user_id: str) -> None:
        with self._lock:
            for task_id in [key for key, item in self._records.items() if item.session_id == session_id and item.user_id == user_id]:
                del self._records[task_id]
