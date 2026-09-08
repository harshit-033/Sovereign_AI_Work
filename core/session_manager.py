from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional

from document.models import DocumentContext, DocumentExtraction

from .models import AppMode, DocumentMetadata, SessionData, UserRole

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a helpful offline AI assistant running locally. "
        "Answer clearly and do not claim to use online services."
    ),
}
MAX_HISTORY_MESSAGES = 40
MAX_STORED_MESSAGE_CHARS = 16_000
MAX_HISTORY_CONTEXT_CHARS = 48_000


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.RLock()

    def create_session(
        self, user_id: str, username: str, role: UserRole = UserRole.USER
    ) -> SessionData:
        with self._lock:
            session_id = str(uuid.uuid4())
            session = SessionData(
                session_id=session_id,
                user_id=user_id,
                username=username,
                role=role,
                mode=AppMode.GENERAL_CHAT,
                general_messages=[DEFAULT_SYSTEM_MESSAGE.copy()],
                document_messages=[DEFAULT_SYSTEM_MESSAGE.copy()],
                knowledge_messages=[DEFAULT_SYSTEM_MESSAGE.copy()],
            )
            self._sessions[session_id] = session
            logger.info("Created session %s for user %s", session_id, username)
            return session

    def get_session(self, session_id: str) -> Optional[SessionData]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_active = time.time()
            return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info("Deleted session %s", session_id)
                return True
            return False

    def list_sessions(self) -> List[SessionData]:
        with self._lock:
            return list(self._sessions.values())

    def delete_user_sessions(self, user_id: str) -> List[str]:
        with self._lock:
            session_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.user_id == user_id
            ]
            for session_id in session_ids:
                del self._sessions[session_id]
            return session_ids

    def add_document(
        self,
        session_id: str,
        doc_meta: DocumentMetadata,
        extraction: DocumentExtraction,
        context: DocumentContext,
    ) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return False
            session.uploaded_documents[doc_meta.document_id] = doc_meta
            session.current_document_id = doc_meta.document_id
            session.current_document_extraction = extraction
            session.current_document_context = context
            session.mode = (
                AppMode.DOCUMENT_ANALYSIS if extraction.pages else AppMode.GENERAL_CHAT
            )
            session.document_messages = [DEFAULT_SYSTEM_MESSAGE.copy()]
            return True

    def select_document(
        self, session_id: str, doc_id: str, extraction: DocumentExtraction, context: DocumentContext
    ) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session or doc_id not in session.uploaded_documents:
                return False
            session.current_document_id = doc_id
            session.current_document_extraction = extraction
            session.current_document_context = context
            session.mode = (
                AppMode.DOCUMENT_ANALYSIS if extraction.pages else AppMode.GENERAL_CHAT
            )
            session.document_messages = [DEFAULT_SYSTEM_MESSAGE.copy()]
            return True

    def clear_session_chat(self, session_id: str) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return False
            session.general_messages = [DEFAULT_SYSTEM_MESSAGE.copy()]
            session.document_messages = [DEFAULT_SYSTEM_MESSAGE.copy()]
            session.knowledge_messages = [DEFAULT_SYSTEM_MESSAGE.copy()]
            session.current_document_id = None
            session.current_document_extraction = None
            session.current_document_context = None
            session.mode = AppMode.GENERAL_CHAT
            session.uploaded_documents.clear()
            return True

    def add_message(
        self, session_id: str, mode: AppMode, role: str, content: str
    ) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return False
            target = (
                session.document_messages
                if mode == AppMode.DOCUMENT_ANALYSIS
                else session.knowledge_messages
                if mode == AppMode.KNOWLEDGE_CHAT
                else session.general_messages
            )
            target.append({"role": role, "content": content[:MAX_STORED_MESSAGE_CHARS]})
            if len(target) > MAX_HISTORY_MESSAGES + 1:
                target[1:] = target[-MAX_HISTORY_MESSAGES:]
            return True

    def get_messages(self, session_id: str, mode: AppMode) -> List[Dict[str, str]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return []
            target = (
                session.document_messages
                if mode == AppMode.DOCUMENT_ANALYSIS
                else session.knowledge_messages
                if mode == AppMode.KNOWLEDGE_CHAT
                else session.general_messages
            )
            if not target:
                return []
            selected: List[Dict[str, str]] = []
            used_chars = 0
            for message in reversed(target[1:]):
                content = message.get("content", "")
                if selected and used_chars + len(content) > MAX_HISTORY_CONTEXT_CHARS:
                    break
                selected.append(message.copy())
                used_chars += len(content)
            selected.reverse()
            return [target[0].copy(), *selected]

    def verify_document_ownership(self, session_id: str, doc_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            return doc_id in session.uploaded_documents
