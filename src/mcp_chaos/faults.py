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

    def reset(self) -> None:
        """Clear any cross-call state; called when the fault joins a new plan."""


@dataclass
class LatencyFault(Fault):
    # NOTE(v0.1): in live-proxy mode latency is recorded in metrics but not
    # actually slept; real delay injection is a v0.2 follow-up.
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
class BurstErrorFault(Fault):
    """Correlated error injection: failures arrive in bursts, not independently.

    A two-state Markov chain advanced once per call: bursts last `burst_len`
    calls on average, and the entry probability is chosen so the stationary
    marginal per-call error rate is exactly `rate` — the knob that makes
    correlated runs comparable with iid runs at the same marginal rate.
    burst_len=1 degenerates to (approximately) independent injection.
    """

    rate: float = 0.02
    burst_len: float = 8.0
    tools: list[str] = field(default_factory=list)  # empty => all tools
    _in_burst: bool | None = field(default=None, init=False, repr=False)

    def reset(self):
        self._in_burst = None

    def _targeted(self, call):
        return not self.tools or call.tool in self.tools

    def apply_response(self, call, result, rng):
        length = max(1.0, self.burst_len)
        if self._in_burst is None:
            self._in_burst = rng.random() < self.rate  # start in the stationary distribution
        elif self._in_burst:
            self._in_burst = rng.random() >= 1.0 / length
        else:
            p_enter = self.rate / (length * (1.0 - self.rate)) if self.rate < 1.0 else 1.0
            self._in_burst = rng.random() < p_enter
        if self._in_burst and self._targeted(call):
            return replace(result, error="injected burst error", injected=FaultTag.BURST_ERROR)
        return result


@dataclass
class ServerDegradationFault(Fault):
    """Server-scoped correlated fault: all listed tools fail together.

    Degradation episodes advance on task boundaries and last `episode_len`
    tasks on average; the entry probability is chosen so the stationary
    fraction of degraded tasks is `episode_rate`. Within a task the server
    state is frozen, so retries observe the same outage.
    """

    tools: list[str] = field(default_factory=list)
    episode_rate: float = 0.08
    episode_len: float = 20.0
    _active: bool | None = field(default=None, init=False, repr=False)
    _task: str | None = field(default=None, init=False, repr=False)

    def reset(self):
        self._active = None
        self._task = None

    def apply_response(self, call, result, rng):
        if call.task_id != self._task:
            self._task = call.task_id
            length = max(1.0, self.episode_len)
            if self._active is None:
                self._active = rng.random() < self.episode_rate
            elif self._active:
                self._active = rng.random() >= 1.0 / length
            else:
                p_enter = (
                    self.episode_rate / (length * (1.0 - self.episode_rate))
                    if self.episode_rate < 1.0
                    else 1.0
                )
                self._active = rng.random() < p_enter
        if self._active and call.tool in self.tools:
            return replace(
                result,
                error=f"server hosting '{call.tool}' degraded",
                injected=FaultTag.SERVER_DEGRADATION,
            )
        return result


@dataclass
class FaultPlan:
    """An ordered set of active faults plus a seed for reproducibility."""

    faults: list[Fault] = field(default_factory=list)
    seed: int = 0

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        for f in self.faults:
            f.reset()

    def apply_request(self, call: ToolCall) -> ToolCall:
        for f in self.faults:
            call = f.apply_request(call, self._rng)
        return call

    def apply_response(self, call: ToolCall, result: ToolResult) -> ToolResult:
        for f in self.faults:
            result = f.apply_response(call, result, self._rng)
        return result
