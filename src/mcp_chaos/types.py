"""Common vocabulary spoken by the core and every driver (sim, stdio, http)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FaultTag(str, Enum):
    NONE = "none"
    LATENCY = "latency"
    DROP_TOOL = "drop_tool"
    SCHEMA_DRIFT = "schema_drift"
    PARTIAL_RESULT = "partial_result"
    REGISTRY_INCONSISTENCY = "registry_inconsistency"
    ERROR_INJECTION = "error_injection"


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    task_id: str = ""
    deadline_ms: float = 1000.0


@dataclass
class ToolResult:
    content: Any = None
    schema_ok: bool = True          # False under SCHEMA_DRIFT
    usable: bool = True             # False under PARTIAL_RESULT
    latency_ms: float = 0.0
    error: str | None = None        # set => availability failure (no usable answer)
    injected: FaultTag = FaultTag.NONE


@dataclass
class CallRecord:
    call: ToolCall
    result: ToolResult
    retries: int = 0

    @property
    def responded(self) -> bool:
        # Availability factor A: the tool returned an answer at all.
        return self.result.error is None

    @property
    def within_deadline(self) -> bool:
        return self.result.latency_ms <= self.call.deadline_ms

    @property
    def correct(self) -> bool:
        # Correctness factor C: responded AND schema-conformant AND semantically usable.
        return self.responded and self.result.schema_ok and self.result.usable

    @property
    def success(self) -> bool:
        # TCSR numerator: usable result delivered within the step deadline.
        return self.correct and self.within_deadline
