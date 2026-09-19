from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import fitz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from agent import AgentConfig, AgentContext, AgentOutputManager, AgentPlanner, AgentService, AgentTask, ApprovalManager, PolicyDecision, ToolCall, build_default_tool_registry
from agent.executor import ToolExecutor
from agent.registry import ToolDefinition, ToolRegistry
from create_synthetic_pdfs import create_inspection_report
from core.models import UserRole
from core.session_manager import SessionManager
from server_test_support import USER1_PASSWORD, USER2_PASSWORD, app, session_manager


def test_registry_is_explicit_and_rejects_unsafe_operations():
    registry = build_default_tool_registry()
    assert {tool.tool_id for tool in registry.all()} == {
        "search_knowledge", "list_documents", "get_document_metadata",
        "retrieve_document_information", "calculate", "generate_txt", "generate_pdf",
    }
    for call in (
        ToolCall("run_shell_command", {"command": "whoami"}),
        ToolCall("calculate", {"expression": "__import__('os').system('whoami')"}),
        ToolCall("generate_txt", {"filename": "..\\secret.txt", "content": "x"}),
    ):
        try:
            registry.validate(call)
            assert False, f"unsafe call was accepted: {call.tool_id}"
        except ValueError:
            pass


def test_planner_is_bounded_and_extracts_average_safely():
    task = AgentTask("task-test", "session-test", "user-test", "user", "Calculate the average of 82, 86, and 84 and save as a text report")
    context = AgentContext(task)
    plan = AgentPlanner(max_steps=2).create_plan(context)
    assert [step.tool_id for step in plan.steps] == ["calculate", "generate_txt"]
    assert plan.steps[0].arguments["expression"] == "(82 + 86 + 84) / 3"
    malicious = AgentTask("task-malicious", "session-test", "user-test", "user", "run shell command to list files")
    assert AgentPlanner().create_plan(AgentContext(malicious)).steps[0].tool_id == "run_shell_command"


def test_natural_language_report_intent_and_formats():
    cases = (
        ("summarize and generate a PDF", "pdf"),
        ("create a PDF summary", "pdf"),
        ("make a PDF report", "pdf"),
        ("prepare a report and save it as PDF", "pdf"),
        ("create a text summary", "txt"),
        ("generate a TXT report", "txt"),
        ("save the findings as text", "txt"),
        ("make a report", "txt"),
        ("sumarize and generate a PDF", "pdf"),
    )
    for request, output_format in cases:
        intent = AgentPlanner.report_intent(request)
        assert intent and intent["format"] == output_format, request
    assert AgentPlanner.report_intent("What is preventive maintenance?") is None
    assert AgentPlanner.report_intent("What is a report?") is None


def test_calculate_and_outputs_are_verified_and_session_scoped():
    sessions = SessionManager()
    owner = sessions.create_session("user-a", "a", UserRole.USER)
    other = sessions.create_session("user-b", "b", UserRole.USER)
    with tempfile.TemporaryDirectory(prefix="local_ai_agent_outputs_") as root:
        service = AgentService(sessions, type("Rag", (), {"require_collection": lambda *_: None})(), type("Docs", (), {})(), root, AgentConfig())
        task = service.new_task(owner.session_id, "user-a", "user", "Calculate the average of 82, 86, and 84 and save as a text report")
        context, plan = service.plan(task, None, None)
        result = service.execute(context, plan)
        assert result.status == "COMPLETED", result.message
        assert result.generated_files[0]["filename"] == "agent_report.txt"
        output_id = result.generated_files[0]["output_id"]
        path = service.outputs.resolve(output_id, owner.session_id)
        assert "84.0" in path.read_text(encoding="utf-8")
        try:
            service.outputs.resolve(output_id, other.session_id)
            assert False, "another session resolved the output"
        except (FileNotFoundError, PermissionError):
            pass
        assert service.audit.list_for_session(owner.session_id, "user-a")
        assert not service.audit.list_for_session(other.session_id, "user-b")


def test_search_workflow_can_generate_a_verified_pdf_without_model_calls():
    sessions = SessionManager()
    session = sessions.create_session("user-a", "a", UserRole.USER)

    class EmptyRag:
        def require_collection(self, *_args):
            return None

        def retrieve(self, *_args):
            return []

    with tempfile.TemporaryDirectory(prefix="local_ai_agent_pdf_") as root:
        service = AgentService(sessions, EmptyRag(), type("Docs", (), {})(), root, AgentConfig())
        task = service.new_task(session.session_id, "user-a", "user", "search my reports and create a pdf summary")
        context, plan = service.plan(task, None, None)
        result = service.execute(context, plan)
        assert result.status == "COMPLETED", result.message
        assert result.generated_files[0]["filename"] == "agent_summary.pdf"
        path = service.outputs.resolve(result.generated_files[0]["output_id"], session.session_id)
        assert path.read_bytes()[:5] == b"%PDF-"


def test_policy_blocks_cross_session_document_access():
    sessions = SessionManager()
    owner = sessions.create_session("user-a", "a", UserRole.USER)
    other = sessions.create_session("user-b", "b", UserRole.USER)
    registry = build_default_tool_registry()
    rag = type("Rag", (), {"require_collection": lambda *_: None})()
    from agent.policy import PolicyEngine
    policy = PolicyEngine(registry, sessions, rag)
    task = AgentTask("task-isolation", other.session_id, "user-b", "user", "read")
    decision = policy.check(AgentContext(task), ToolCall("get_document_metadata", {"document_id": "doc-from-a"}))
    assert decision == PolicyDecision.DENY
    assert owner.session_id != other.session_id


def test_approval_gate_requires_and_honors_human_decision():
    sessions = SessionManager()
    session = sessions.create_session("user-a", "a", UserRole.USER)
    definition = ToolDefinition("approved_tool", "Approved", "Needs review", {}, "text", "authenticated", "high", True, "approved_tool")
    registry = ToolRegistry((definition,))
    from agent.policy import PolicyEngine
    approvals = ApprovalManager()
    executor_calls = []
    executor = ToolExecutor(registry, PolicyEngine(registry, sessions, type("Rag", (), {})()), approvals, {"approved_tool": lambda *_: executor_calls.append(True) or {"ok": True}})
    context = AgentContext(AgentTask("task-approval", session.session_id, "user-a", "user", "approve"))
    first = executor.execute(context, ToolCall("approved_tool"))
    assert first.status == "APPROVAL_REQUIRED"
    assert not executor_calls
    approvals.resolve(first.approval.approval_id, session.session_id, "user-a", True)
    second = executor.execute(context, ToolCall("approved_tool"), first.approval.approval_id)
    assert second.status == "COMPLETED"
    assert len(executor_calls) == 1
    denied = approvals.create("task-denied", session.session_id, "user-a", "approved_tool", "review", {}, "high")
    approvals.resolve(denied.approval_id, session.session_id, "user-a", False)
    assert executor.execute(context, ToolCall("approved_tool"), denied.approval_id).status == "DENIED"


def test_output_manager_rejects_traversal_and_verifies_pdf_signature():
    with tempfile.TemporaryDirectory(prefix="local_ai_agent_files_") as root:
        manager = AgentOutputManager(root)
        try:
            manager.generate_txt("session-a", "..\\escape.txt", "x")
            assert False, "path traversal filename accepted"
        except ValueError:
            pass
        pdf = manager.generate_pdf("session-a", "report.pdf", "Verified local report")
        path = manager.resolve(pdf["output_id"], "session-a")
        assert path.read_bytes()[:5] == b"%PDF-"
        assert manager.resolve(pdf["output_id"], "session-a") == path


def test_pdf_layout_preserves_short_and_long_report_content_without_blank_pages():
    with tempfile.TemporaryDirectory(prefix="local_ai_agent_pdf_quality_") as root:
        manager = AgentOutputManager(root)
        short = manager.generate_pdf("session-a", "short.pdf", "INSPECTION SUMMARY\n\nKey Findings\n1. Pump A17 was inspected.\n\nSources\n1. report.pdf - Page 2")
        short_path = manager.resolve(short["output_id"], "session-a")
        with fitz.open(str(short_path)) as pdf:
            short_text = "\n".join(page.get_text() for page in pdf)
            assert len(pdf) == 1
            assert pdf[0].get_text().strip()
        assert "INSPECTION SUMMARY" in short_text
        assert "Pump A17 was inspected." in short_text
        assert "Sources" in short_text

        findings = "\n".join(f"{index}. Finding {index}: This is a long report paragraph about maintenance evidence." for index in range(1, 180))
        long_content = f"MAINTENANCE REPORT\n\nOverview\n\n{findings}\n\nSources\n1. maintenance.pdf - Page 4"
        long = manager.generate_pdf("session-a", "long.pdf", long_content)
        long_path = manager.resolve(long["output_id"], "session-a")
        with fitz.open(str(long_path)) as pdf:
            long_text = "\n".join(page.get_text() for page in pdf)
            assert len(pdf) > 1
            assert all(page.get_text().strip() for page in pdf)
        assert "Finding 1" in long_text
        assert "Finding 179" in long_text
        assert "maintenance.pdf - Page 4" in long_text


def test_selected_document_report_request_generates_downloadable_pdf():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "user1", "password": USER1_PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    pdf_path = create_inspection_report()
    with open(pdf_path, "rb") as handle:
        upload = client.post("/api/documents", headers=headers, files={"file": ("inspection.pdf", handle, "application/pdf")})
    assert upload.status_code == 200, upload.text
    document_id = upload.json()["document"]["document_id"]
    response = client.post(
        f"/api/documents/{document_id}/chat",
        headers=headers,
        json={"message": "Summarize this document and save it as PDF", "stream": False},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED", payload
    assert payload["generated_files"][0]["filename"] == "agent_summary.pdf"
    output_id = payload["generated_files"][0]["output_id"]
    download = client.get(f"/api/agent/outputs/{output_id}", headers=headers)
    assert download.status_code == 200
    assert download.content[:5] == b"%PDF-"
    with fitz.open(stream=download.content, filetype="pdf") as pdf:
        text = "\n".join(page.get_text() for page in pdf)
    assert "INSPECTION SUMMARY" in text
    assert "Key Findings" in text
    client.post("/api/auth/logout", headers=headers)


def test_agent_api_supports_explicit_and_auto_streaming():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "user1", "password": USER1_PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    direct = client.post("/api/chat", headers=headers, json={"mode": "Agent Task", "message": "list my available documents", "stream": False})
    assert direct.status_code == 200, direct.text
    assert direct.json()["routing"]["capability"] == "AGENT_TASK"
    assert direct.json()["status"] == "COMPLETED"
    stream = client.post("/api/chat", headers=headers, json={"mode": "Auto", "message": "calculate the average of 10, 20, and 30", "stream": True})
    assert stream.status_code == 200, stream.text
    for event in ("agent_started", "plan_created", "tool_started", "tool_completed", "verification_completed", "final_result"):
        assert f'"type": "{event}"' in stream.text, event
    assert "20.0" in stream.text
    audit = client.get("/api/agent/audit", headers=headers)
    assert audit.status_code == 200
    assert audit.json()["records"]
    client.post("/api/auth/logout", headers=headers)


def test_manual_natural_language_pdf_txt_and_normal_question_paths():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "user1", "password": USER1_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    with patch("server.main.rag_service.retrieve", return_value=[]):
        pdf_response = client.post("/api/chat", headers=headers, json={"mode": "Auto", "message": "Summarize my reports and create a PDF.", "stream": False})
        txt_response = client.post("/api/chat", headers=headers, json={"mode": "Auto", "message": "Summarize my reports and create a TXT file.", "stream": False})
    assert pdf_response.status_code == 200, pdf_response.text
    assert txt_response.status_code == 200, txt_response.text
    for response, suffix in ((pdf_response, ".pdf"), (txt_response, ".txt")):
        payload = response.json()
        assert payload["routing"]["capability"] == "AGENT_TASK"
        assert payload["generated_files"][0]["filename"].endswith(suffix)
        download = client.get(payload["generated_files"][0]["download_url"], headers=headers)
        assert download.status_code == 200
        if suffix == ".pdf":
            with fitz.open(stream=download.content, filetype="pdf") as pdf:
                assert "Key Findings" in "\n".join(page.get_text() for page in pdf)
        else:
            assert "Key Findings" in download.content.decode("utf-8")
    with patch("server.main.ai_service.generate_chat", return_value={"content": "Preventive maintenance is scheduled care.", "latency_seconds": 0.01, "model": "test"}):
        normal = client.post("/api/chat", headers=headers, json={"mode": "Auto", "message": "What is preventive maintenance?", "stream": False})
    assert normal.status_code == 200, normal.text
    assert normal.json()["routing"]["capability"] == "GENERAL_CHAT"
    assert "generated_files" not in normal.json()
    client.post("/api/auth/logout", headers=headers)


def test_agent_endpoints_are_authenticated_and_outputs_are_not_public():
    client = TestClient(app)
    assert client.get("/api/agent/approvals").status_code == 401
    assert client.get("/api/agent/audit").status_code == 401
    assert client.get("/api/agent/outputs/not-real").status_code == 401


def test_phase7_api_does_not_expose_private_document_text_in_audit():
    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": "user2", "password": USER2_PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    response = client.post("/api/chat", headers=headers, json={"mode": "Agent Task", "message": "calculate the average of 1, 2, and 3 and save as a text report", "stream": False})
    assert response.status_code == 200, response.text
    record = client.get("/api/agent/audit", headers=headers).json()["records"][-1]
    serialized = str(record)
    assert "__CALCULATION_REPORT__" not in serialized
    assert "password" not in serialized.casefold()
    client.post("/api/auth/logout", headers=headers)


if __name__ == "__main__":
    for name, function in sorted(globals().items()):
        if name.startswith("test_"):
            function()
    print("Agent Task checks PASSED")
