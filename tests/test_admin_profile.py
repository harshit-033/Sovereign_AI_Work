import concurrent.futures
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.auth import AuthService
from core.models import UserCredentials
from core.user_store import UserStore
from server_test_support import (
    ADMIN_PASSWORD,
    USER1_PASSWORD,
    USER2_PASSWORD,
    app,
)

NEW_ADMIN_PASSWORD = "New-Admin-Pass-456!"


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def logout(client: TestClient, token: str) -> None:
    response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text


def test_admin_profile_updates():
    client = TestClient(app)
    token = login(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch("/api/admin/me", headers=headers, json={"username": "superadmin"})
    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["username"] == "superadmin"

    duplicate = client.patch("/api/admin/me", headers=headers, json={"username": "user1"})
    assert duplicate.status_code == 409
    invalid = client.patch("/api/admin/me", headers=headers, json={"username": "   "})
    assert invalid.status_code in (400, 422)

    reset = client.patch("/api/admin/me", headers=headers, json={"username": "admin"})
    assert reset.status_code == 200
    logout(client, token)

    user_token = login(client, "user1", USER1_PASSWORD)
    forbidden = client.patch(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"username": "new_user_name"},
    )
    assert forbidden.status_code == 403
    logout(client, user_token)


def test_admin_password_lifecycle():
    client = TestClient(app)
    token = login(client, "admin", ADMIN_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    wrong = client.post(
        "/api/admin/me/change-password",
        headers=headers,
        json={
            "current_password": "Wrong-Password-2026!",
            "new_password": NEW_ADMIN_PASSWORD,
            "confirm_password": NEW_ADMIN_PASSWORD,
        },
    )
    assert wrong.status_code == 400

    mismatch = client.post(
        "/api/admin/me/change-password",
        headers=headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": NEW_ADMIN_PASSWORD,
            "confirm_password": "Different-Password-2026!",
        },
    )
    assert mismatch.status_code == 400

    weak = client.post(
        "/api/admin/me/change-password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": "short", "confirm_password": "short"},
    )
    assert weak.status_code in (400, 422)

    changed = client.post(
        "/api/admin/me/change-password",
        headers=headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": NEW_ADMIN_PASSWORD,
            "confirm_password": NEW_ADMIN_PASSWORD,
        },
    )
    assert changed.status_code == 200
    logout(client, token)
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    ).status_code == 401

    new_token = login(client, "admin", NEW_ADMIN_PASSWORD)
    restore = client.post(
        "/api/admin/me/change-password",
        headers={"Authorization": f"Bearer {new_token}"},
        json={
            "current_password": NEW_ADMIN_PASSWORD,
            "new_password": ADMIN_PASSWORD,
            "confirm_password": ADMIN_PASSWORD,
        },
    )
    assert restore.status_code == 200
    logout(client, new_token)


def test_single_active_admin_session_and_expiration():
    client_a = TestClient(app)
    client_b = TestClient(app)
    token_a = login(client_a, "admin", ADMIN_PASSWORD)
    conflict = client_b.post(
        "/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD}
    )
    assert conflict.status_code == 409
    logout(client_a, token_a)
    token_b = login(client_b, "admin", ADMIN_PASSWORD)
    logout(client_b, token_b)

    with tempfile.TemporaryDirectory() as tmpdir:
        store = UserStore(Path(tmpdir) / "users.json")
        auth = AuthService(store, token_ttl_seconds=1)
        first = auth.authenticate(UserCredentials("admin", ADMIN_PASSWORD))
        assert hasattr(first, "token")
        assert auth.authenticate(UserCredentials("admin", ADMIN_PASSWORD)) == "ADMIN_ALREADY_ACTIVE"
        time.sleep(1.1)
        assert hasattr(auth.authenticate(UserCredentials("admin", ADMIN_PASSWORD)), "token")


def test_normal_users_allow_multiple_sessions():
    first_client = TestClient(app)
    second_client = TestClient(app)
    first = login(first_client, "user1", USER1_PASSWORD)
    second = login(second_client, "user1", USER1_PASSWORD)
    logout(first_client, first)
    logout(second_client, second)


def test_admin_ai_dashboard_and_user_management():
    client = TestClient(app)
    admin_token = login(client, "admin", ADMIN_PASSWORD)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("core.ai_service.AIService.generate_chat") as mocked_chat:
        mocked_chat.return_value = {
            "content": "Hello admin!",
            "latency_seconds": 0.01,
            "model": "test-model",
        }
        response = client.post(
            "/api/chat", headers=admin_headers, json={"message": "Hi", "stream": False}
        )
        assert response.status_code == 200

    assert client.get("/api/admin/users", headers=admin_headers).status_code == 200
    created = client.post(
        "/api/admin/users",
        headers=admin_headers,
        json={"username": "temp_test_user", "password": "Temporary-User-2026!"},
    )
    assert created.status_code == 200
    created_id = created.json()["user"]["id"]
    assert client.delete(f"/api/admin/users/{created_id}", headers=admin_headers).status_code == 200
    logout(client, admin_token)

    user_token = login(client, "user2", USER2_PASSWORD)
    forbidden = client.post(
        "/api/admin/me/change-password",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "current_password": USER2_PASSWORD,
            "new_password": "Another-Password-2026!",
            "confirm_password": "Another-Password-2026!",
        },
    )
    assert forbidden.status_code == 403
    logout(client, user_token)


def test_concurrent_admin_login_race_condition():
    with tempfile.TemporaryDirectory() as tmpdir:
        auth = AuthService(UserStore(Path(tmpdir) / "users.json"))

        def attempt_login():
            return auth.authenticate(UserCredentials("admin", ADMIN_PASSWORD))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: attempt_login(), range(5)))
        assert len([result for result in results if hasattr(result, "token")]) == 1
        assert len([result for result in results if result == "ADMIN_ALREADY_ACTIVE"]) == 4


if __name__ == "__main__":
    test_admin_profile_updates()
    test_admin_password_lifecycle()
    test_single_active_admin_session_and_expiration()
    test_normal_users_allow_multiple_sessions()
    test_admin_ai_dashboard_and_user_management()
    test_concurrent_admin_login_race_condition()
    print("Admin profile and session security checks PASSED")
