from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from .models import AuthToken, UserCredentials, UserRole
from .user_store import UserStore

logger = logging.getLogger(__name__)

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.")
    if password.isspace():
        raise ValueError("Password cannot contain only whitespace.")


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    validate_password(password)
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith("scrypt$"):
            _, n_text, r_text, p_text, salt_hex, key_hex = stored_hash.split("$", 5)
            expected_key = bytes.fromhex(key_hex)
            key = hashlib.scrypt(
                password.encode("utf-8"),
                salt=bytes.fromhex(salt_hex),
                n=int(n_text),
                r=int(r_text),
                p=int(p_text),
                dklen=len(expected_key),
            )
        else:
            # Legacy PBKDF2 hashes are accepted once and upgraded after login.
            salt_hex, key_hex = stored_hash.split(":", 1)
            expected_key = bytes.fromhex(key_hex)
            key = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 100_000
            )
        return hmac.compare_digest(key, expected_key)
    except (TypeError, ValueError):
        return False


def password_hash_needs_upgrade(stored_hash: str) -> bool:
    return not stored_hash.startswith(f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}$")


class LoginAttemptLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] > self.window_seconds:
                attempts.popleft()
            return len(attempts) < self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._attempts[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


class AuthService:
    def __init__(
        self,
        user_store: Optional[UserStore] = None,
        token_ttl_seconds: int = 28_800,
    ):
        self.token_ttl_seconds = token_ttl_seconds
        self.user_store = user_store if user_store is not None else UserStore()
        self._tokens: Dict[str, AuthToken] = {}
        self._admin_tokens: Dict[str, str] = {}
        self._lock = threading.RLock()
        self.bootstrap_password: Optional[str] = None
        self._ensure_initial_admin()

    def _ensure_initial_admin(self) -> None:
        if any(u.role == UserRole.ADMIN and u.is_active for u in self.user_store.list_users()):
            return

        username = os.getenv("SIH_BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"
        configured_password = os.getenv("SIH_BOOTSTRAP_ADMIN_PASSWORD")
        password = configured_password or secrets.token_urlsafe(18)
        self.user_store.bootstrap_admin(username, hash_password(password))
        if not configured_password:
            self.bootstrap_password = password
            logger.warning(
                "First-run admin created for username '%s'. Temporary password: %s",
                username,
                password,
            )
            logger.warning("Change this password immediately after the first login.")

    def authenticate(self, credentials: UserCredentials) -> Optional[AuthToken | str]:
        with self._lock:
            user = self.user_store.get_user_by_username(credentials.username)
            if not user or not user.is_active:
                logger.warning("Authentication failed for username '%s'", credentials.username)
                return None

            if not verify_password(credentials.password, user.password_hash):
                logger.warning("Authentication failed for username '%s'", credentials.username)
                return None

            if user.role == UserRole.ADMIN:
                active_token = self._admin_tokens.get(user.id)
                if active_token:
                    existing = self._tokens.get(active_token)
                    if existing and time.time() <= existing.expires_at:
                        return "ADMIN_ALREADY_ACTIVE"
                    self._admin_tokens.pop(user.id, None)
                    self._tokens.pop(active_token, None)

            if password_hash_needs_upgrade(user.password_hash):
                self.user_store.update_password_hash(user.id, hash_password(credentials.password))

            self.user_store.update_last_login(user.id)
            token_str = secrets.token_urlsafe(32)
            token = AuthToken(
                token=token_str,
                user_id=user.id,
                username=user.username,
                role=user.role,
                expires_at=time.time() + self.token_ttl_seconds,
            )
            self._tokens[token_str] = token
            if user.role == UserRole.ADMIN:
                self._admin_tokens[user.id] = token_str

            logger.info("Authentication successful for user '%s'", user.username)
            return token

    def validate_token(self, token_str: str) -> Optional[AuthToken]:
        with self._lock:
            token = self._tokens.get(token_str)
            if not token:
                return None

            if time.time() > token.expires_at:
                self._remove_token(token_str, token)
                return None

            user = self.user_store.get_user_by_id(token.user_id)
            if not user or not user.is_active:
                self._remove_token(token_str, token)
                return None

            token.username = user.username
            token.role = user.role
            return token

    def _remove_token(self, token_str: str, token: AuthToken) -> None:
        self._tokens.pop(token_str, None)
        if self._admin_tokens.get(token.user_id) == token_str:
            self._admin_tokens.pop(token.user_id, None)

    def revoke_token(self, token_str: str) -> bool:
        with self._lock:
            token = self._tokens.get(token_str)
            if not token:
                return False
            self._remove_token(token_str, token)
            return True

    def revoke_user_tokens(self, user_id: str, except_token: Optional[str] = None) -> int:
        with self._lock:
            targets = [
                token_str
                for token_str, token in self._tokens.items()
                if token.user_id == user_id and token_str != except_token
            ]
            for token_str in targets:
                self._remove_token(token_str, self._tokens[token_str])
            return len(targets)
