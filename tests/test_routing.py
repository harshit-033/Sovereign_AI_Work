from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from create_synthetic_pdfs import create_inspection_report
from core.models import UserRole
from routing import (
    CapabilityId,
    CapabilityNotAllowedError,
    CapabilityRouter,
    CapabilityUnavailableError,
    RoutingConfig,
    RoutingContext,
    RouterDisabledError,
    UnknownCapabilityError,
    build_default_registry,
)
from server_test_support import INSPECTOR_PASSWORD, USER1_PASSWORD, USER2_PASSWORD, app, rag_service


def context(message: str, mode: str = "Auto", document: str | None = None, collection: str | None = None, **kwargs):
    return RoutingContext("user-a", UserRole.USER.value, mode, document, collection, message, **kwargs)


def router(config: RoutingConfig | None = None) -> CapabilityRouter:
    config = config or RoutingConfig()
    return CapabilityRouter(config, build_default_registry(config))


def test_routing_matrix_is_deterministic():
    route = router()
    cases = (
        ("Hello, what can you do?", "GENERAL_CHAT", None),
        ("Explain recursion.", "GENERAL_CHAT", None),
        ("What is the equipment ID in this report?", "DOCUMENT_ANALYSIS", "doc-1"),
        ("What does page 4 of this document say?", "DOCUMENT_ANALYSIS", "doc-1"),
        ("Search my maintenance reports for Pump A17.", "KNOWLEDGE_RAG", None),
        ("What do our inspection reports say about bearing temperature?", "KNOWLEDGE_RAG", None),
    )
    for message, expected, document in cases:
        first = route.route(context(message, document=document)).to_dict()
        second = route.route(context(message, document=document)).to_dict()
        assert first["capability"] == expected
        assert first["capability"] == second["capability"]
        assert first["reason_code"] == second["reason_code"]


def test_explicit_modes_and_safe_ambiguity():
    route = router()
    assert route.route(context("anything", "General Chat" )).capability == CapabilityId.GENERAL_CHAT
    assert route.route(context("anything", "Document Analysis", document="doc-1")).capability == CapabilityId.DOCUMENT_ANALYSIS
    assert route.route(context("anything", "Knowledge Chat")).capability == CapabilityId.KNOWLEDGE_RAG
    assert route.route(context("Tell me about Pump A17", document="doc-1")).capability == CapabilityId.DOCUMENT_ANALYSIS
    assert route.route(context("Tell me about Pump A17")).capability == CapabilityId.GENERAL_CHAT


def test_router_rejects_disabled_unknown_and_missing_requirements():
    with_disabled = CapabilityRouter(
        RoutingConfig(enabled=False), build_default_registry(RoutingConfig(enabled=False))
    )
    try:
        with_disabled.route(context("hello"))
        assert False, "disabled router should fail"
    except RouterDisabledError:
        pass
    with pytest_raises(UnknownCapabilityError):
        router().route(context("hello", "Not A Mode"))
    with pytest_raises(CapabilityUnavailableError):
        router().route(context("summarize this document", "Document Analysis"))
    with pytest_raises(CapabilityUnavailableError):
        router().route(context("search indexed reports", "Auto", knowledge_base_available=False))
    restricted = context("search indexed reports", "Knowledge Chat")
    restricted = restricted.__class__(
        **{**restricted.__dict__, "available_capabilities": (CapabilityId.GENERAL_CHAT,)}
    )
    with pytest_raises(CapabilityNotAllowedError):
        router().route(restricted)


def test_model_mapping_is_separate_from_capability():
    with patch.dict(
        os.environ,
        {
            "SIH_MODEL_NAME": "fallback-model",
            "SIH_GENERAL_MODEL": "general-model",
            "SIH_DOCUMENT_MODEL": "document-model",
            "SIH_RAG_MODEL": "rag-model",
        },
        clear=False,
    ):
        config = RoutingConfig.from_env()
    route = CapabilityRouter(config, build_default_registry(config))
    assert route.route(context("hello")).model_name == "general-model"
    assert route.route(context("this document", document="doc-1")).model_name == "document-model"
    assert route.route(context("search my reports")).model_name == "rag-model"


class pytest_raises:
    def __init__(self, expected):
        self.expected = expected

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _traceback):
        assert exc_type is self.expected, (exc_type, exc)
        return True


def login(client: TestClient, username: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_route_explanation_and_auto_general_stream():
    client = TestClient(app)
    auth = login(client, "user1", USER1_PASSWORD)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    explanation = client.post(
        "/api/route", headers=headers, json={"mode": "Auto", "message": "Hello"}
    )
    assert explanation.status_code == 200, explanation.text
    assert explanation.json()["routing"]["capability"] == "GENERAL_CHAT"
    assert "retrieved" not in explanation.json()["routing"]["reason"].lower()
    with patch("server.main.ai_service.generate_chat_stream", return_value=iter(["Hello", " locally."])):
        response = client.post(
            "/api/chat", headers=headers, json={"mode": "Auto", "message": "Hello", "stream": True}
        )
    assert response.status_code == 200, response.text
    assert '"type": "routing"' in response.text
    assert '"capability": "GENERAL_CHAT"' in response.text
    assert '"content": "Hello"' in response.text
    client.post("/api/auth/logout", headers=headers)


def test_auto_document_and_rag_dispatch():
    client = TestClient(app)
    auth = login(client, "user1", USER1_PASSWORD)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    pdf_path = create_inspection_report()
    with open(pdf_path, "rb") as handle:
        upload = client.post(
            "/api/documents", headers=headers, files={"file": ("inspection.pdf", handle, "application/pdf")}
        )
    assert upload.status_code == 200, upload.text

    with patch("server.main.ai_service.generate_chat_stream", return_value=iter(["equipment is EQ-17"])):
        document_response = client.post(
            "/api/chat", headers=headers,
            json={"mode": "Auto", "message": "What is the equipment ID in this report?", "stream": True},
        )
    assert document_response.status_code == 200, document_response.text
    assert '"capability": "DOCUMENT_ANALYSIS"' in document_response.text

    with patch.object(rag_service, "retrieve", return_value=[]):
        rag_response = client.post(
            "/api/chat", headers=headers,
            json={"mode": "Auto", "message": "Search my maintenance reports for Pump A17", "stream": True},
        )
    assert rag_response.status_code == 200, rag_response.text
    assert '"capability": "KNOWLEDGE_RAG"' in rag_response.text
    client.post("/api/auth/logout", headers=headers)


def test_routing_isolation_between_authenticated_clients():
    client_a = TestClient(app)
    client_b = TestClient(app)
    client_c = TestClient(app)
    auth_a = login(client_a, "user1", USER1_PASSWORD)
    auth_b = login(client_b, "user2", USER2_PASSWORD)
    auth_c = login(client_c, "inspector", INSPECTOR_PASSWORD)
    headers_a = {"Authorization": f"Bearer {auth_a['token']}"}
    headers_b = {"Authorization": f"Bearer {auth_b['token']}"}
    headers_c = {"Authorization": f"Bearer {auth_c['token']}"}
    with patch("server.main.ai_service.generate_chat_stream", return_value=iter(["ok"])):
        general = client_b.post(
            "/api/chat", headers=headers_b, json={"mode": "Auto", "message": "Hello", "stream": True}
        )
    with patch.object(rag_service, "retrieve", return_value=[]):
        knowledge = client_a.post(
            "/api/chat", headers=headers_a,
            json={"mode": "Auto", "message": "Search my private maintenance reports", "stream": True},
        )
    pdf_path = create_inspection_report()
    with open(pdf_path, "rb") as handle:
        upload = client_c.post(
            "/api/documents", headers=headers_c,
            files={"file": ("client_c.pdf", handle, "application/pdf")},
        )
    assert upload.status_code == 200, upload.text
    with patch("server.main.ai_service.generate_chat_stream", return_value=iter(["document ok"])):
        document = client_c.post(
            "/api/chat", headers=headers_c,
            json={"mode": "Auto", "message": "What is the equipment ID in this report?", "stream": True},
        )
    assert '"capability": "GENERAL_CHAT"' in general.text
    assert '"capability": "KNOWLEDGE_RAG"' in knowledge.text
    assert '"capability": "DOCUMENT_ANALYSIS"' in document.text
    client_a.post("/api/auth/logout", headers=headers_a)
    client_b.post("/api/auth/logout", headers=headers_b)
    client_c.post("/api/auth/logout", headers=headers_c)


if __name__ == "__main__":
    test_routing_matrix_is_deterministic()
    test_explicit_modes_and_safe_ambiguity()
    test_router_rejects_disabled_unknown_and_missing_requirements()
    test_model_mapping_is_separate_from_capability()
    test_route_explanation_and_auto_general_stream()
    test_auto_document_and_rag_dispatch()
    test_routing_isolation_between_authenticated_clients()
    print("Routing checks PASSED")
