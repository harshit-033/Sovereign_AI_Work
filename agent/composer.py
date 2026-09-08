from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


class ReportComposer:
    """Turn authorized evidence into bounded, human-readable report content."""

    _INTERNAL_MARKERS = ("__CALCULATION_REPORT__", "__EVIDENCE_REPORT__", "ToolExecutionResult", "traceback")

    @staticmethod
    def _clean(value: Any, maximum: int = 2_000) -> str:
        text = " ".join(str(value or "").replace("\x00", " ").split())
        return text[:maximum].strip()

    @staticmethod
    def _title(request: str, evidence: Any) -> str:
        request_text = request.casefold()
        if "pump a17" in request_text:
            return "Pump A17 Summary"
        if "maintenance" in request_text:
            return "Maintenance Report Summary"
        if "inspection" in request_text:
            return "Inspection Summary"
        if isinstance(evidence, dict) and evidence.get("filename"):
            stem = re.sub(r"[_-]+", " ", str(evidence["filename"]).rsplit(".", 1)[0]).strip()
            if stem:
                return f"{stem.title()} Summary"
        return "Local Evidence Summary"

    def compose(self, task, evidence: Any, requested_format: str = "txt") -> str:
        title = self._title(task.request, evidence)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        findings: list[str] = []
        sources: list[str] = []

        if isinstance(evidence, dict) and evidence.get("calculation") is not None:
            findings.append(f"The bounded local calculation produced {evidence['calculation']}.")
            overview = "This report records the result of the requested numeric calculation."
        elif isinstance(evidence, dict) and evidence.get("text"):
            overview = "This report summarizes information extracted from the authorized selected document."
            source_name = evidence.get("filename", "Selected document")
            sources.append(str(source_name))
            paragraphs = re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z0-9])", str(evidence["text"]))
            findings = [self._clean(item) for item in paragraphs if self._clean(item)]
        elif isinstance(evidence, list):
            overview = "This report summarizes information found in authorized local knowledge-base evidence."
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                text = self._clean(item.get("text"))
                source = item.get("source") if isinstance(item.get("source"), dict) else {}
                filename = source.get("filename", "Unknown source")
                page = source.get("page_number", "?")
                if text:
                    findings.append(text)
                sources.append(f"{filename} - Page {page}")
            if not findings:
                overview = "Insufficient evidence to provide a reliable conclusion."
        else:
            overview = "Insufficient evidence to provide a reliable conclusion."

        findings = findings[:32]
        lines = [title.upper(), "", f"Generated: {generated_at}", "", "Overview", "--------", overview, "", "Key Findings", "------------"]
        if findings:
            lines.extend(f"{index}. {finding}" for index, finding in enumerate(findings, 1))
        else:
            lines.append("1. Insufficient evidence to provide a reliable conclusion.")
        lines.extend(["", "Sources", "-------"])
        if sources:
            lines.extend(f"{index}. {source}" for index, source in enumerate(dict.fromkeys(sources), 1))
        else:
            lines.append("1. No authorized source was available.")
        content = "\n".join(lines).strip() + "\n"
        self.validate(content)
        return content

    @classmethod
    def validate(cls, content: str) -> None:
        if not isinstance(content, str) or len(content.strip()) < 40:
            raise ValueError("Report content is empty or too short.")
        lowered = content.casefold()
        if any(marker.casefold() in lowered for marker in cls._INTERNAL_MARKERS):
            raise ValueError("Internal tool output cannot be used as report content.")
        if "error:" in lowered or "exception" in lowered:
            raise ValueError("Error output cannot be used as report content.")
        if "key findings" not in lowered:
            raise ValueError("Report content must contain a Key Findings section.")

    @staticmethod
    def expected_markers(content: str) -> tuple[str, ...]:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return tuple(marker for marker in (lines[0] if lines else "", "Key Findings", "Sources") if marker)
