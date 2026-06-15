"""The Paper A §4 operational fault taxonomy as small, pure, seeded transformers.

Each fault implements apply_request and/or apply_response. Faults never raise on
normal input; they express failure by mutating the ToolResult and stamping
result.injected so metrics can separate injected faults from real upstream errors.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from .types import FaultTag, ToolCall, ToolResult


class Fault:
    """Base fault. Subclasses override apply_request/apply_response."""

    def apply_request(self, call: ToolCall, rng: random.Random) -> ToolCall:
        return call

    def apply_response(self, call: ToolCall, result: ToolResult, rng: random.Random) -> ToolResult:
        return result


@dataclass
class LatencyFault(Fault):
    added_ms: float = 250.0
    jitter_ms: float = 0.0
    probability: float = 1.0

    def apply_response(self, call, result, rng):
        if rng.random() > self.probability:
            return result
        extra = self.added_ms + (rng.uniform(0, self.jitter_ms) if self.jitter_ms else 0)
        return replace(result, latency_ms=result.latency_ms + extra, injected=FaultTag.LATENCY)


@dataclass
class DropToolFault(Fault):
    tools: list[str] = field(default_factory=list)

    def apply_response(self, call, result, rng):
        if call.tool in self.tools:
            return replace(result, error=f"tool '{call.tool}' unavailable", injected=FaultTag.DROP_TOOL)
        return result


@dataclass
class SchemaDriftFault(Fault):
    tools: list[str] = field(default_factory=list)  # empty => all tools
    probability: float = 1.0

    def _targeted(self, call):
        return not self.tools or call.tool in self.tools

    def apply_response(self, call, result, rng):
        if self._targeted(call) and rng.random() <= self.probability:
            return replace(result, schema_ok=False, injected=FaultTag.SCHEMA_DRIFT)
        return result


@dataclass
class PartialResultFault(Fault):
    tools: list[str] = field(default_factory=list)
    probability: float = 1.0

    def _targeted(self, call):
        return not self.tools or call.tool in self.tools

    def apply_response(self, call, result, rng):
        if self._targeted(call) and rng.random() <= self.probability:
            return replace(result, usable=False, injected=FaultTag.PARTIAL_RESULT)
        return result


@dataclass
class RegistryInconsistencyFault(Fault):
    """Synthetic context-dangling tool: advertised but errors on call (Paper A §4.1)."""

    tools: list[str] = field(default_factory=list)

    def apply_response(self, call, result, rng):
        if call.tool in self.tools:
            return replace(
                result,
                error=f"tool '{call.tool}' not found (registry inconsistency)",
                injected=FaultTag.REGISTRY_INCONSISTENCY,
            )
        return result


@dataclass
class ErrorInjectionFault(Fault):
    rate: float = 0.02
    tools: list[str] = field(default_factory=list)  # empty => all tools

    def _targeted(self, call):
        return not self.tools or call.tool in self.tools

    def apply_response(self, call, result, rng):
        if self._targeted(call) and rng.random() < self.rate:
            return replace(result, error="injected error", injected=FaultTag.ERROR_INJECTION)
        return result


@dataclass
class FaultPlan:
    """An ordered set of active faults plus a seed for reproducibility."""

    faults: list[Fault] = field(default_factory=list)
    seed: int = 0

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    def apply_request(self, call: ToolCall) -> ToolCall:
        for f in self.faults:
            call = f.apply_request(call, self._rng)
        return call

    def apply_response(self, call: ToolCall, result: ToolResult) -> ToolResult:
        for f in self.faults:
            result = f.apply_response(call, result, self._rng)
        return result
