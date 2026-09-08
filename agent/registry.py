from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from .models import ToolCall


ArgumentValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    display_name: str
    description: str
    input_schema: dict[str, str]
    output_schema: str
    required_permission: str
    risk_level: str
    requires_approval: bool
    handler: str
    validator: Optional[ArgumentValidator] = None


class ToolRegistry:
    """Explicit allowlist. An agent can only call a registered tool ID."""

    def __init__(self, tools: Iterable[ToolDefinition] = ()):
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", tool.tool_id):
            raise ValueError("Tool IDs must be lowercase allowlist identifiers.")
        if tool.tool_id in self._tools:
            raise ValueError(f"Tool already registered: {tool.tool_id}")
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools[tool_id]
        except KeyError as exc:
            raise ValueError(f"Unknown agent tool: {tool_id}") from exc

    def validate(self, call: ToolCall) -> ToolDefinition:
        definition = self.get(call.tool_id)
        if not isinstance(call.arguments, dict):
            raise ValueError(f"Arguments for {call.tool_id} must be an object.")
        if set(call.arguments) - set(definition.input_schema):
            raise ValueError(f"Unexpected arguments for {call.tool_id}.")
        if definition.validator:
            definition.validator(call.arguments)
        return definition

    def all(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())


def _required_string(name: str, maximum: int):
    def validate(args: dict[str, Any]) -> None:
        value = args.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{name} must be a non-empty string of at most {maximum} characters.")
    return validate


def _merge(*validators: ArgumentValidator) -> ArgumentValidator:
    def validate(args: dict[str, Any]) -> None:
        for validator in validators:
            validator(args)
    return validate


def _validate_search(args: dict[str, Any]) -> None:
    _required_string("question", 8_000)(args)
    collection = args.get("collection_id")
    if collection is not None and (not isinstance(collection, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", collection)):
        raise ValueError("collection_id is invalid.")


def _validate_doc_id(args: dict[str, Any]) -> None:
    value = args.get("document_id")
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value):
        raise ValueError("document_id is invalid.")


def _validate_calculate(args: dict[str, Any]) -> None:
    expression = args.get("expression")
    _required_string("expression", 500)(args)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Expression is not valid arithmetic.") from exc
    allowed = (ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub, ast.BinOp,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("Only numeric arithmetic is allowed.")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and (not isinstance(node.value, (int, float)) or isinstance(node.value, bool)):
            raise ValueError("Only numeric constants are allowed.")
        if isinstance(node, ast.Pow) and isinstance(node, ast.BinOp) and False:
            raise ValueError("Power operation is not allowed.")


def _validate_output(args: dict[str, Any]) -> None:
    _required_string("filename", 120)(args)
    _required_string("content", 32_000)(args)
    filename = args["filename"]
    if "\\" in filename or "/" in filename or ".." in filename or ":" in filename:
        raise ValueError("filename must be a simple name without path components.")


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        (
            ToolDefinition("search_knowledge", "Search Knowledge", "Search authorized local RAG documents.", {"question": "string", "collection_id": "optional string"}, "source records", "authenticated", "low", False, "search_knowledge" , _validate_search),
            ToolDefinition("list_documents", "List Documents", "List documents in the authenticated session.", {}, "document metadata list", "authenticated", "low", False, "list_documents"),
            ToolDefinition("get_document_metadata", "Get Document Metadata", "Read metadata for an authorized document.", {"document_id": "string"}, "document metadata", "authenticated", "low", False, "get_document_metadata", _validate_doc_id),
            ToolDefinition("retrieve_document_information", "Read Document Information", "Extract bounded text from an authorized document.", {"document_id": "string"}, "bounded document evidence", "authenticated", "medium", False, "retrieve_document_information", _validate_doc_id),
            ToolDefinition("calculate", "Calculate", "Evaluate restricted numeric arithmetic.", {"expression": "string"}, "numeric result", "authenticated", "low", False, "calculate", _validate_calculate),
            ToolDefinition("generate_txt", "Generate TXT", "Write a verified UTF-8 report under the session output directory.", {"filename": "string", "content": "string"}, "safe output metadata", "authenticated", "low", False, "generate_txt", _validate_output),
            ToolDefinition("generate_pdf", "Generate PDF", "Write a verified PDF report under the session output directory.", {"filename": "string", "content": "string"}, "safe output metadata", "authenticated", "low", False, "generate_pdf", _validate_output),
        )
    )
