import asyncio
import hashlib
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from server_test_support import USER1_PASSWORD, USER2_PASSWORD, app, session_manager
from core.auth import AuthService
from core.models import AppMode, UserCredentials, UserRole
from core.user_store import UserStore
from server.main import MAX_UPLOAD_BYTES, _model_stream


def login(client: TestClient, username: str, password: str) -> tuple[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"], response.json()["session_id"]


def test_auth_transport_and_headers():
    client = TestClient(app)
    token, session_id = login(client, "user1", USER1_PASSWORD)
    cookie = client.cookies.get("local_ai_session")
    assert cookie == token
    set_cookie = client.post(
        "/api/auth/login",
        json={"username": "user2", "password": USER2_PASSWORD},
    ).headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()

    anonymous = TestClient(app)
    assert anonymous.get(f"/api/session?token={token}").status_code == 401
    assert anonymous.get("/api/session", headers={"X-Session-ID": session_id}).status_code == 401
    assert anonymous.get("/api/metrics").status_code == 401

    root = anonymous.get("/", headers={"Origin": "https://attacker.invalid"})
    assert root.headers.get("access-control-allow-origin") is None
    assert root.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in root.headers["content-security-policy"]

    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})


def test_login_rate_limit():
    client = TestClient(app)
    username = f"missing_{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "Wrong-Password-2026!"},
        )
        assert response.status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"username": username, "password": "Wrong-Password-2026!"},
    ).status_code == 429


def test_tokens_are_not_persisted_and_legacy_hashes_upgrade():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "users.json"
        store = UserStore(path)
        password = "Legacy-Password-2026!"
        salt = b"0123456789abcdef"
        legacy_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        legacy_hash = f"{salt.hex()}:{legacy_key.hex()}"
        store.bootstrap_admin("legacyadmin", legacy_hash)

        auth = AuthService(store)
        token = auth.authenticate(UserCredentials("legacyadmin", password))
        assert hasattr(token, "token")
        saved_text = path.read_text(encoding="utf-8")
        assert token.token not in saved_text
        assert "active_session_token" not in saved_text
        assert store.get_user_by_username("legacyadmin").password_hash.startswith("scrypt$")


def test_upload_limits_magic_and_failure_cleanup():
    client = TestClient(app)
    token, session_id = login(client, "user2", USER2_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    too_large = b"%PDF-" + b"x" * MAX_UPLOAD_BYTES
    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("large.pdf", too_large, "application/pdf")},
    )
    assert response.status_code == 413

    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("broken.pdf", b"%PDF-invalid", "application/pdf")},
    )
    assert response.status_code == 400

    from server_test_support import file_handler

    session_dir = file_handler.get_session_dir(session_id, create=False)
    assert not session_dir.exists() or not any(session_dir.iterdir())
    client.post("/api/auth/logout", headers=headers)


def test_stream_is_incremental():
    session = session_manager.create_session("stream_user", "stream_user", UserRole.USER)

    def slow_stream(_messages):
        for piece in ("first", " second", " third"):
            time.sleep(0.2)
            yield piece

    async def exercise():
        generator = _model_stream(
            session.session_id,
            AppMode.GENERAL_CHAT,
            "hello",
            "hello",
            "stream_regression",
        )
        status_event = await anext(generator)
        assert '"status": "processing"' in status_event
        started = time.perf_counter()
        first_chunk = await anext(generator)
        elapsed = time.perf_counter() - started
        assert '"content": "first"' in first_chunk
        assert elapsed < 0.4, f"First token was buffered for {elapsed:.2f}s"
        remaining = [event async for event in generator]
        assert any('"type": "done"' in event for event in remaining)

    with patch("server.main.ai_service.generate_chat_stream", side_effect=slow_stream):
        asyncio.run(exercise())
    session_manager.delete_session(session.session_id)


if __name__ == "__main__":
    test_auth_transport_and_headers()
    test_login_rate_limit()
    test_tokens_are_not_persisted_and_legacy_hashes_upgrade()
    test_upload_limits_magic_and_failure_cleanup()
    test_stream_is_incremental()
    print("Security regression checks PASSED")
