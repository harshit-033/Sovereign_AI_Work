from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from .audit import AuditLogger
from .config import AgentConfig
from .composer import ReportComposer
from .executor import ToolExecutor
from .models import AgentContext, AgentExecutionResult, AgentPlan, AgentTask, AuditRecord, ToolCall, ToolExecutionResult, VerificationResult
from .outputs import AgentOutputManager
from .planner import AgentPlanner
from .verifier import VerificationService

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, session_manager, rag_service, doc_service, output_root: str | Path, config: Optional[AgentConfig] = None, registry=None, audit=None, approvals=None):
        from .approval import ApprovalManager
        from .policy import PolicyEngine
        from .registry import build_default_tool_registry

        self.config = config or AgentConfig.from_env()
        self.session_manager = session_manager
        self.rag_service = rag_service
        self.doc_service = doc_service
        self.registry = registry or build_default_tool_registry()
        self.audit = audit or AuditLogger()
        self.approvals = approvals or ApprovalManager()
        self.outputs = AgentOutputManager(output_root, self.config.max_file_bytes)
        self.composer = ReportComposer()
        self.planner = AgentPlanner(self.config.max_steps)
        self.verifier = VerificationService()
        self.policy = PolicyEngine(self.registry, session_manager, rag_service)
        self.executor = ToolExecutor(self.registry, self.policy, self.approvals, {
            "search_knowledge": self._search_knowledge,
            "list_documents": self._list_documents,
            "get_document_metadata": self._get_document_metadata,
            "retrieve_document_information": self._retrieve_document_information,
            "calculate": self._calculate,
            "generate_txt": self._generate_txt,
            "generate_pdf": self._generate_pdf,
        })

    def new_task(self, session_id: str, user_id: str, role: str, request: str) -> AgentTask:
        return AgentTask(f"task_{uuid.uuid4().hex}", session_id, user_id, role, request)

    def plan(self, task: AgentTask, current_document_id: str | None, collection_id: str | None) -> tuple[AgentContext, AgentPlan]:
        context = AgentContext(task, current_document_id, collection_id)
        plan = self.planner.create_plan(context)
        self.audit.record(AuditRecord(task.task_id, task.session_id, task.user_id, time.time(), "AGENT_TASK", tuple(step.tool_id for step in plan.steps)))
        logger.info("Agent plan created task_id=%s session_id=%s tools=%s", task.task_id, task.session_id, [step.tool_id for step in plan.steps])
        return context, plan

    def execute(self, context: AgentContext, plan: AgentPlan, progress: Optional[Callable[[str, dict[str, Any]], None]] = None, approval_id: str | None = None) -> AgentExecutionResult:
        started = time.perf_counter()
        tool_results: list[ToolExecutionResult] = []
        verifications: list[VerificationResult] = []
        files: list[dict[str, Any]] = []
        previous: dict[str, Any] = {}
        policies: list[str] = []
        approvals = "NOT_REQUIRED"
        if len(plan.steps) > self.config.max_steps:
            return AgentExecutionResult(context.task.task_id, "FAILED", "Maximum agent steps exceeded.", plan, total_latency_ms=(time.perf_counter() - started) * 1000)
        for index, original_call in enumerate(plan.steps):
            if time.perf_counter() - started > self.config.max_execution_seconds:
                return self._finish(context, plan, "FAILED", "Agent execution time limit exceeded.", tool_results, verifications, files, policies, approvals, started)
            if index >= self.config.max_tool_calls:
                return self._finish(context, plan, "FAILED", "Maximum agent tool calls exceeded.", tool_results, verifications, files, policies, approvals, started)
            call = self._resolve_call(original_call, previous, context)
            if progress:
                progress("tool_started", {"tool_id": call.tool_id, "step": index + 1})
            result = self.executor.execute(context, call, approval_id)
            tool_results.append(result)
            policies.append("REQUIRE_APPROVAL" if result.status == "APPROVAL_REQUIRED" else result.status if result.status == "DENIED" else "ALLOW")
            if result.status == "APPROVAL_REQUIRED":
                approvals = "PENDING"
                if progress:
                    progress("approval_required", {"approval_id": result.approval.approval_id})
                return self._finish(context, plan, "APPROVAL_REQUIRED", "Human approval is required before this tool can run.", tool_results, verifications, files, policies, approvals, started, result.approval)
            if progress:
                progress("tool_completed", {"tool_id": call.tool_id, "status": result.status})
            verification = self.verifier.verify(result)
            verifications.append(verification)
            if progress:
                progress("verification_completed", {"tool_id": call.tool_id, "passed": verification.passed})
            if not verification.passed:
                return self._finish(context, plan, "FAILED", verification.message, tool_results, verifications, files, policies, approvals, started)
            if result.status != "COMPLETED":
                return self._finish(context, plan, "DENIED", result.error, tool_results, verifications, files, policies, approvals, started)
            previous[call.tool_id] = result.data
            if call.tool_id in {"generate_txt", "generate_pdf"}:
                metadata = {key: value for key, value in result.data.items() if not key.startswith("_")}
                files.append(metadata)
        message = self._final_message(previous, files)
        return self._finish(context, plan, "COMPLETED", message, tool_results, verifications, files, policies, approvals, started)

    def _finish(self, context, plan, status, message, results, verifications, files, policies, approvals, started, approval=None):
        record = self.audit.update(context.task.task_id, policy_decisions=tuple(policies), approval_decision=approvals, tool_execution_status=tuple(item.status for item in results), verification_result=tuple("PASSED" if item.passed else "FAILED" for item in verifications), final_status=status, generated_files=tuple(files))
        return AgentExecutionResult(context.task.task_id, status, message, plan, tuple(results), tuple(verifications), tuple(files), approval, (time.perf_counter() - started) * 1000)

    @staticmethod
    def _resolve_call(call: ToolCall, previous: dict[str, Any], context: AgentContext) -> ToolCall:
        if call.tool_id not in {"generate_txt", "generate_pdf"}:
            return call
        content = call.arguments.get("content")
        if content == "__CALCULATION_REPORT__":
            result = previous.get("calculate")
            content = ReportComposer().compose(context.task, {"calculation": result}, call.arguments.get("format", "txt"))
        elif content == "__DOCUMENT_REPORT__":
            content = ReportComposer().compose(context.task, previous.get("retrieve_document_information"), call.arguments.get("format", "txt"))
        elif content == "__EVIDENCE_REPORT__":
            evidence = previous.get("search_knowledge") or []
            content = ReportComposer().compose(context.task, evidence, call.arguments.get("format", "txt"))
        return ToolCall(call.tool_id, {**call.arguments, "content": content or "No verified content available."})

    @staticmethod
    def _final_message(previous, files):
        if files:
            return "Agent task completed. Generated: " + ", ".join(item["filename"] for item in files)
        if "list_documents" in previous:
            documents = previous["list_documents"]
            return f"Found {len(documents)} document(s) in this session."
        if "calculate" in previous:
            return f"The calculated result is {previous['calculate']}."
        if "search_knowledge" in previous:
            return f"Retrieved {len(previous['search_knowledge'])} authorized evidence item(s)."
        return "Agent task completed."

    def _list_documents(self, context, _args):
        session = self.session_manager.get_session(context.task.session_id)
        if not session:
            raise PermissionError("Session not found.")
        return [item.to_dict() for item in session.uploaded_documents.values()]

    def _get_document_metadata(self, context, args):
        session = self.session_manager.get_session(context.task.session_id)
        if not session or not self.session_manager.verify_document_ownership(context.task.session_id, args["document_id"]):
            raise PermissionError("Document not found or access denied.")
        return session.uploaded_documents[args["document_id"]].to_dict()

    def _retrieve_document_information(self, context, args):
        session = self.session_manager.get_session(context.task.session_id)
        if not session or not self.session_manager.verify_document_ownership(context.task.session_id, args["document_id"]):
            raise PermissionError("Document not found or access denied.")
        metadata = session.uploaded_documents[args["document_id"]]
        extraction = self.doc_service.process_pdf(metadata.stored_path)
        text = "\n\n".join(page.as_prompt_text() for page in extraction.pages)[:14_000]
        if not text:
            raise ValueError("The authorized document has no readable information.")
        return {"document_id": args["document_id"], "filename": metadata.filename, "text": text}

    def _search_knowledge(self, context, args):
        results = self.rag_service.retrieve(context.task.user_id, args["question"], args.get("collection_id"))
        return [{"source": result.source_dict(), "text": result.text[:2_000]} for result in results]

    @staticmethod
    def _calculate(_context, args):
        import ast
        import operator
        tree = ast.parse(args["expression"], mode="eval")
        operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
        def visit(node):
            if isinstance(node, ast.Expression): return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool): return node.value
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = visit(node.operand); return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp) and type(node.op) in operations:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 12: raise ValueError("Power exponent is too large.")
                return operations[type(node.op)](left, right)
            raise ValueError("Only numeric arithmetic is allowed.")
        result = visit(tree)
        if abs(result) > 10**12: raise ValueError("Calculation result is outside the safe limit.")
        return result

    def _generate_txt(self, context, args):
        metadata = self.outputs.generate_txt(context.task.session_id, args["filename"], args["content"])
        return {**metadata, "_path": str(self.outputs.resolve(metadata["output_id"], context.task.session_id)), "_expected_markers": self.composer.expected_markers(args["content"])}

    def _generate_pdf(self, context, args):
        metadata = self.outputs.generate_pdf(context.task.session_id, args["filename"], args["content"])
        return {**metadata, "_path": str(self.outputs.resolve(metadata["output_id"], context.task.session_id)), "_expected_markers": self.composer.expected_markers(args["content"])}
