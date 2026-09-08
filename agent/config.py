from __future__ import annotations

import os
from dataclasses import dataclass


class AgentConfigurationError(ValueError):
    pass


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise AgentConfigurationError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise AgentConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


@dataclass(frozen=True)
class AgentConfig:
    enabled: bool = True
    max_steps: int = 8
    max_tool_calls: int = 12
    max_execution_seconds: int = 120
    max_output_chars: int = 32_000
    max_file_bytes: int = 2_000_000

    @classmethod
    def from_env(cls) -> "AgentConfig":
        raw = os.getenv("SIH_AGENT_ENABLED", "1").strip().lower()
        if raw not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
            raise AgentConfigurationError("SIH_AGENT_ENABLED must be a boolean flag.")
        return cls(
            enabled=raw in {"1", "true", "yes", "on"},
            max_steps=_bounded_int("SIH_AGENT_MAX_STEPS", 8, 1, 32),
            max_tool_calls=_bounded_int("SIH_AGENT_MAX_TOOL_CALLS", 12, 1, 64),
            max_execution_seconds=_bounded_int("SIH_AGENT_MAX_EXECUTION_SECONDS", 120, 1, 600),
            max_output_chars=_bounded_int("SIH_AGENT_MAX_OUTPUT_CHARS", 32_000, 1_000, 128_000),
            max_file_bytes=_bounded_int("SIH_AGENT_MAX_FILE_BYTES", 2_000_000, 1_024, 10_000_000),
        )
