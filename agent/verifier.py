from __future__ import annotations

import time
from pathlib import Path

import fitz

from .models import ToolExecutionResult, VerificationResult


class VerificationService:
    def verify(self, result: ToolExecutionResult) -> VerificationResult:
        started = time.perf_counter()
        if result.status != "COMPLETED":
            return VerificationResult(result.tool_id, False, result.error or "Tool did not complete.", (time.perf_counter() - started) * 1000)
        data = result.data
        try:
            if result.tool_id == "search_knowledge":
                passed = isinstance(data, list) and all(isinstance(item, dict) and "source" in item for item in data)
                message = "Search result structure verified." if passed else "Search result structure is invalid."
            elif result.tool_id == "retrieve_document_information":
                passed = isinstance(data, dict) and bool(data.get("text")) and bool(data.get("document_id"))
                message = "Authorized document evidence verified." if passed else "Document evidence is empty or malformed."
            elif result.tool_id == "calculate":
                passed = isinstance(data, (int, float)) and not isinstance(data, bool)
                message = "Numeric calculation verified." if passed else "Calculation result is invalid."
            elif result.tool_id in {"generate_txt", "generate_pdf"}:
                path = Path(str(data.get("_path", ""))) if isinstance(data, dict) else Path()
                passed = isinstance(data, dict) and data.get("output_id") and int(data.get("size_bytes", 0)) > 100 and path.is_file()
                markers = tuple(data.get("_expected_markers", ())) if isinstance(data, dict) else ()
                if result.tool_id == "generate_txt" and passed:
                    text = path.read_text(encoding="utf-8")
                    passed = bool(text.strip()) and all(marker in text for marker in markers)
                if result.tool_id == "generate_pdf" and passed:
                    passed = path.read_bytes()[:5] == b"%PDF-"
                    if passed:
                        with fitz.open(str(path)) as pdf:
                            text = "\n".join(page.get_text() for page in pdf)
                            passed = len(pdf) >= 1 and bool(pdf[0].get_text().strip()) and all(marker in text for marker in markers)
                message = "Generated file verified." if passed else "Generated file verification failed."
            else:
                passed = data is not None
                message = "Tool result verified." if passed else "Tool returned no result."
            return VerificationResult(result.tool_id, passed, message, (time.perf_counter() - started) * 1000)
        except Exception as exc:
            return VerificationResult(result.tool_id, False, f"Verification failed: {exc}", (time.perf_counter() - started) * 1000)
