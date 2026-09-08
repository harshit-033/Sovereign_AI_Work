from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .models import UserModel, UserRole

logger = logging.getLogger(__name__)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,49}$")


def normalize_username(username: str) -> str:
    clean = username.strip()
    if not USERNAME_PATTERN.fullmatch(clean):
        raise ValueError(
            "Username must be 3-50 characters and use only letters, numbers, dot, dash, or underscore."
        )
    return clean


class UserStore:
    def __init__(self, storage_path: str | Path = "data/users.json"):
        self.storage_path = Path(storage_path).resolve()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._users: Dict[str, UserModel] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                return

            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                users_map: Dict[str, UserModel] = {}
                usernames: set[str] = set()
                for item in data.get("users", []):
                    user_id = str(item["id"])
                    username = normalize_username(str(item["username"]))
                    username_key = username.casefold()
                    if user_id in users_map or username_key in usernames:
                        raise ValueError("Duplicate user identity in account store.")
                    role = UserRole(str(item.get("role", UserRole.USER.value)))
                    users_map[user_id] = UserModel(
                        id=user_id,
                        username=username,
                        password_hash=str(item["password_hash"]),
                        role=role,
                        is_active=bool(item.get("is_active", True)),
                        created_at=float(item.get("created_at", time.time())),
                        last_login=item.get("last_login"),
                    )
                    usernames.add(username_key)
                self._users = users_map
                logger.info("Loaded %d users from %s", len(self._users), self.storage_path)
            except Exception as exc:
                raise RuntimeError(f"Account store is invalid: {self.storage_path}") from exc

    def _save(self) -> None:
        with self._lock:
            temp_path = self.storage_path.with_name(
                f".{self.storage_path.name}.{uuid.uuid4().hex}.tmp"
            )
            data = {
                "users": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "password_hash": user.password_hash,
                        "role": user.role.value,
                        "is_active": user.is_active,
                        "created_at": user.created_at,
                        "last_login": user.last_login,
                    }
                    for user in self._users.values()
                ]
            }
            try:
                with temp_path.open("x", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    temp_path.chmod(0o600)
                except OSError:
                    pass
                os.replace(temp_path, self.storage_path)
            finally:
                temp_path.unlink(missing_ok=True)

    def bootstrap_admin(self, username: str, password_hash: str) -> tuple[bool, Optional[UserModel], str]:
        with self._lock:
            if any(u.role == UserRole.ADMIN and u.is_active for u in self._users.values()):
                return False, None, "An active admin account already exists. Bootstrap refused."

            clean_username = normalize_username(username)
            existing = self.get_user_by_username(clean_username)
            if existing:
                existing.role = UserRole.ADMIN
                existing.password_hash = password_hash
                existing.is_active = True
                self._save()
                return True, existing, "Existing user promoted to admin."

            admin_user = UserModel(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                username=clean_username,
                password_hash=password_hash,
                role=UserRole.ADMIN,
                is_active=True,
                created_at=time.time(),
            )
            self._users[admin_user.id] = admin_user
            self._save()
            logger.info("Created first bootstrap admin '%s'", clean_username)
            return True, admin_user, "First admin created successfully."

    def get_user_by_username(self, username: str) -> Optional[UserModel]:
        with self._lock:
            clean = username.strip().casefold()
            return next(
                (user for user in self._users.values() if user.username.casefold() == clean),
                None,
            )

    def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        with self._lock:
            return self._users.get(user_id)

    def list_users(self) -> List[UserModel]:
        with self._lock:
            return sorted(self._users.values(), key=lambda user: (user.created_at, user.username.casefold()))

    def create_user(self, username: str, password_hash: str, role: UserRole = UserRole.USER) -> UserModel:
        with self._lock:
            clean_username = normalize_username(username)
            if self.get_user_by_username(clean_username):
                raise ValueError(f"Username '{clean_username}' already exists.")

            user = UserModel(
                id=f"usr_{uuid.uuid4().hex[:12]}",
                username=clean_username,
                password_hash=password_hash,
                role=role,
                is_active=True,
                created_at=time.time(),
            )
            self._users[user.id] = user
            self._save()
            logger.info("Created user '%s' with role '%s'", clean_username, role.value)
            return user

    def update_username(self, user_id: str, new_username: str) -> UserModel:
        with self._lock:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found.")
            clean = normalize_username(new_username)
            existing = self.get_user_by_username(clean)
            if existing and existing.id != user_id:
                raise ValueError(f"Username '{clean}' is already taken.")
            user.username = clean
            self._save()
            return user

    def update_password_hash(self, user_id: str, new_password_hash: str) -> UserModel:
        with self._lock:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found.")
            user.password_hash = new_password_hash
            self._save()
            return user

    def remove_user(self, user_id: str) -> bool:
        with self._lock:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            if user.role == UserRole.ADMIN and self.count_active_admins() <= 1:
                raise ValueError("Cannot remove the last remaining active admin.")
            del self._users[user_id]
            self._save()
            return True

    def deactivate_user(self, user_id: str) -> bool:
        with self._lock:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            if user.role == UserRole.ADMIN and self.count_active_admins() <= 1:
                raise ValueError("Cannot deactivate the last remaining active admin.")
            user.is_active = False
            self._save()
            return True

    def count_active_admins(self) -> int:
        with self._lock:
            return sum(
                1 for user in self._users.values()
                if user.role == UserRole.ADMIN and user.is_active
            )

    def update_last_login(self, user_id: str) -> None:
        with self._lock:
            user = self.get_user_by_id(user_id)
            if user:
                user.last_login = time.time()
                self._save()
