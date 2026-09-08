from __future__ import annotations

import re
import time

from .models import AgentContext, AgentPlan, ToolCall


class AgentPlanner:
    """Deterministic planner. It only emits IDs from the registered allowlist."""

    def __init__(self, max_steps: int = 8):
        self.max_steps = max_steps

    def create_plan(self, context: AgentContext) -> AgentPlan:
        started = time.perf_counter()
        request = " ".join(context.task.request.casefold().split())
        steps: list[ToolCall] = []
        report = self.report_intent(request)
        if any(term in request for term in ("powershell", "cmd.exe", "shell command", "run command", "execute command", "arbitrary python", "subprocess", "internet request")):
            steps.append(ToolCall("run_shell_command", {"command": context.task.request}))
        elif report and any(term in request for term in ("average", "calculate", "sum of", "percentage")):
            expression = self._extract_expression(request)
            steps.append(ToolCall("calculate", {"expression": expression}))
            steps.append(ToolCall(self._generator(report["format"]), {"filename": self._filename(request, report["format"], "agent_report"), "content": "__CALCULATION_REPORT__"}))
        elif report and context.current_document_id:
            steps.append(ToolCall("retrieve_document_information", {"document_id": context.current_document_id}))
            steps.append(ToolCall(self._generator(report["format"]), {"filename": self._filename(request, report["format"], "agent_summary"), "content": "__DOCUMENT_REPORT__"}))
        elif report:
            steps.append(ToolCall("search_knowledge", {"question": context.task.request, "collection_id": context.collection_id}))
            steps.append(ToolCall(self._generator(report["format"]), {"filename": self._filename(request, report["format"], "agent_summary"), "content": "__EVIDENCE_REPORT__"}))
        elif "list" in request and "document" in request:
            steps.append(ToolCall("list_documents"))
        elif any(term in request for term in ("average", "calculate", "sum of", "percentage")):
            expression = self._extract_expression(request)
            steps.append(ToolCall("calculate", {"expression": expression}))
            if "txt" in request or "text report" in request:
                steps.append(ToolCall("generate_txt", {"filename": "agent_report.txt", "content": "__CALCULATION_REPORT__"}))
        elif any(term in request for term in ("search", "find", "reports", "knowledge base", "maintenance")):
            steps.append(ToolCall("search_knowledge", {"question": context.task.request, "collection_id": context.collection_id}))
            if "pdf" in request:
                steps.append(ToolCall("generate_pdf", {"filename": "agent_summary.pdf", "content": "__EVIDENCE_REPORT__"}))
            elif "txt" in request or "text report" in request:
                steps.append(ToolCall("generate_txt", {"filename": "agent_summary.txt", "content": "__EVIDENCE_REPORT__"}))
        elif context.current_document_id and any(term in request for term in ("read", "document", "file", "report", "extract", "information")):
            steps.append(ToolCall("retrieve_document_information", {"document_id": context.current_document_id}))
        else:
            steps.append(ToolCall("list_documents"))
        if len(steps) > self.max_steps:
            raise ValueError("Agent plan exceeds the configured step limit.")
        return AgentPlan(context.task.task_id, tuple(steps), (time.perf_counter() - started) * 1000, "Deterministic bounded workflow plan.")

    @staticmethod
    def report_intent(request: str) -> dict[str, str] | None:
        normalized = " ".join(request.casefold().split())
        report_words = (
            "summarize", "sumarize", "save as", "export", "make a pdf", "create pdf", "generate pdf",
            "pdf summary", "pdf report", "make a text file", "create txt", "generate txt",
            "save as text", "text report",
        )
        has_save_format = bool(re.search(r"\bsave\b.{0,32}\b(as|to)\b.{0,16}\b(pdf|txt|text)\b", normalized))
        has_report_action = bool(re.search(r"\b(make|create|prepare|generate)\b.{0,32}\b(report|summary|findings)\b", normalized))
        if not any(word in normalized for word in report_words) and not has_save_format and not has_report_action:
            return None
        output_format = "pdf" if re.search(r"\bpdf\b", normalized) else "txt"
        return {"format": output_format}

    @staticmethod
    def _generator(output_format: str) -> str:
        return "generate_pdf" if output_format == "pdf" else "generate_txt"

    @staticmethod
    def _filename(request: str, output_format: str, fallback: str) -> str:
        normalized = request.casefold()
        stem = ""
        if "pump a17" in normalized:
            stem = "pump_a17_summary"
        elif "maintenance" in normalized:
            stem = "maintenance_report"
        elif "inspection" in normalized:
            stem = "inspection_summary"
        return f"{stem or fallback}.{output_format}"

    @staticmethod
    def _extract_expression(request: str) -> str:
        # Keep extraction conservative; the arithmetic validator remains authoritative.
        marker = request.find("average of")
        if marker >= 0:
            expression = request[marker + len("average of"):]
            values = re.findall(r"-?\d+(?:\.\d+)?", expression)
            if values:
                return f"({' + '.join(values)}) / {len(values)}"
        else:
            expression = request.split("calculate", 1)[-1]
        for suffix in (" and save", " save", " as a text", " as txt", "."):
            if suffix in expression:
                expression = expression.split(suffix, 1)[0]
        expression = expression.replace(" and ", " + ")
        expression = re.sub(r"[^0-9+\-*/().% ]", "", expression)
        return expression.strip() or "0"
