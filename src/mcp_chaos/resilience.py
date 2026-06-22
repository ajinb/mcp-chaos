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

    @classmethod
    def disabled(cls) -> "ResilienceConfig":
        # threshold=0.0: ETA is always >= 0, so the breaker never trips (fully disabled).
        return cls(retry_budget=0, graceful_degradation=False, eta_breaker_threshold=0.0)

    @classmethod
    def enabled(cls) -> "ResilienceConfig":
        return cls(retry_budget=2, graceful_degradation=True, eta_breaker_threshold=0.5)


class CircuitBreaker:
    """Trips a tool open when its observed ETA falls below the threshold."""

    def __init__(self, threshold: float):
        self.threshold = threshold
        self._total: dict[str, int] = {}
        self._correct: dict[str, int] = {}
        self._open: set[str] = set()

    def observe(self, tool: str, responded: bool, correct: bool) -> None:
        self._total[tool] = self._total.get(tool, 0) + 1
        self._correct[tool] = self._correct.get(tool, 0) + (1 if correct else 0)
        seen = self._total[tool]
        eta = self._correct[tool] / seen
        if eta < self.threshold and seen >= 4:
            self._open.add(tool)

    def is_open(self, tool: str) -> bool:
        return tool in self._open
