from __future__ import annotations

import os
import atexit
import tempfile
from pathlib import Path

TEST_STATE = tempfile.TemporaryDirectory(prefix="sih_server_tests_")
TEST_ROOT = Path(TEST_STATE.name)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "AdminTest-2026!"
USER1_PASSWORD = "UserOne-Test-2026!"
USER2_PASSWORD = "UserTwo-Test-2026!"
INSPECTOR_PASSWORD = "Inspector-Test-2026!"

os.environ["SIH_USER_STORE_PATH"] = str(TEST_ROOT / "users.json")
os.environ["SIH_UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["SIH_RAG_STORAGE_PATH"] = str(TEST_ROOT / "rag")
os.environ["SIH_AGENT_OUTPUT_DIR"] = str(TEST_ROOT / "agent_outputs")
os.environ["SIH_RAG_ENABLED"] = "1"
os.environ["SIH_EMBED_MODEL"] = "test-embed-model"
os.environ["SIH_BOOTSTRAP_ADMIN_USERNAME"] = ADMIN_USERNAME
os.environ["SIH_BOOTSTRAP_ADMIN_PASSWORD"] = ADMIN_PASSWORD

from core.auth import hash_password
from core.models import UserRole
from server.main import app, auth_service, file_handler, rag_service, session_manager, user_store

atexit.register(rag_service.close)

for username, password in (
    ("user1", USER1_PASSWORD),
    ("user2", USER2_PASSWORD),
    ("inspector", INSPECTOR_PASSWORD),
):
    if not user_store.get_user_by_username(username):
        user_store.create_user(username, hash_password(password), UserRole.USER)
