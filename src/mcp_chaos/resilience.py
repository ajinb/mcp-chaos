"""Minimal Paper A §7 resilience toggles used by the sim to show recovery.

This is a config object plus thin helpers; the agent loop reads it to decide
whether to retry a failed call, degrade gracefully, or treat a tool as broken.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResilienceConfig:
    retry_budget: int = 0                 # max retries per call (0 = none)
    graceful_degradation: bool = False    # continue task if a non-critical tool fails
    eta_breaker_threshold: float = 1.0    # trip a tool's breaker when its ETA drops below this
    breaker_probe_interval: int = 0       # skipped calls between half-open probes (0 = never)

    @classmethod
    def disabled(cls) -> ResilienceConfig:
        # threshold=0.0: ETA is always >= 0, so the breaker never trips (fully disabled).
        return cls(retry_budget=0, graceful_degradation=False, eta_breaker_threshold=0.0)

    @classmethod
    def enabled(cls, probe_interval: int = 0) -> ResilienceConfig:
        return cls(retry_budget=2, graceful_degradation=True, eta_breaker_threshold=0.5,
                   breaker_probe_interval=probe_interval)


class CircuitBreaker:
    """Trips a tool open when its observed ETA falls below the threshold.

    With probe_interval=0 an open breaker never closes: under iid faults it
    simply never trips, but a correlated burst can trip it and lock the tool
    out for the rest of the run. probe_interval>0 enables half-open probes:
    every probe_interval-th skipped call is let through, and a correct result
    closes the breaker and restarts its observation window.
    """

    def __init__(self, threshold: float, probe_interval: int = 0):
        self.threshold = threshold
        self.probe_interval = probe_interval
        self._total: dict[str, int] = {}
        self._correct: dict[str, int] = {}
        self._open: set[str] = set()
        self._skips: dict[str, int] = {}

    def observe(self, tool: str, responded: bool, correct: bool) -> None:
        if tool in self._open:
            # Half-open probe outcome: close on success, restarting the window.
            if correct:
                self._open.discard(tool)
                self._total[tool] = 0
                self._correct[tool] = 0
            return
        self._total[tool] = self._total.get(tool, 0) + 1
        self._correct[tool] = self._correct.get(tool, 0) + (1 if correct else 0)
        seen = self._total[tool]
        eta = self._correct[tool] / seen
        if eta < self.threshold and seen >= 4:
            self._open.add(tool)

    def is_open(self, tool: str) -> bool:
        return tool in self._open

    def should_probe(self, tool: str) -> bool:
        """Call once per skipped invocation of an open tool."""
        if not self.probe_interval:
            return False
        n = self._skips.get(tool, 0) + 1
        if n >= self.probe_interval:
            self._skips[tool] = 0
            return True
        self._skips[tool] = n
        return False
