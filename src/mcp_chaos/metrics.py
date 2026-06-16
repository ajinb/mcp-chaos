"""Service-level indicators for the tool-call plane (Paper A §5)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .types import CallRecord


@dataclass
class Summary:
    calls: int
    tasks: int
    tcsr: float              # tool-call success rate
    availability: float      # A: responded / calls
    correctness: float       # C: correct / responded
    eta: float               # Effective Tool Availability = A * C
    scr: float               # schema-conformance rate
    tcaf: float              # tool-call amplification factor = calls / tasks
    deadline_adherence: float
    blast_radius: float      # fraction of tasks that failed


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


class MetricsCollector:
    def __init__(self):
        self._records: list[CallRecord] = []
        self._task_success: dict[str, bool] = {}

    def record_call(self, rec: CallRecord) -> None:
        self._records.append(rec)

    def record_task(self, task_id: str, success: bool) -> None:
        self._task_success[task_id] = success

    def events(self) -> list[str]:
        """One structured JSON line per call (sre-harness observability style)."""
        out = []
        for r in self._records:
            out.append(json.dumps({
                "tool": r.call.tool,
                "task_id": r.call.task_id,
                "latency_ms": r.result.latency_ms,
                "deadline_ms": r.call.deadline_ms,
                "responded": r.responded,
                "correct": r.correct,
                "success": r.success,
                "retries": r.retries,
                "injected": r.result.injected.value,
            }))
        return out

    def summary(self) -> Summary:
        recs = self._records
        n = len(recs)
        responded = sum(1 for r in recs if r.responded)
        correct = sum(1 for r in recs if r.correct)
        tasks = len(self._task_success)
        failed_tasks = sum(1 for ok in self._task_success.values() if not ok)
        availability = _safe_div(responded, n)
        correctness = _safe_div(correct, responded)
        return Summary(
            calls=n,
            tasks=tasks,
            tcsr=_safe_div(sum(1 for r in recs if r.success), n),
            availability=availability,
            correctness=correctness,
            eta=availability * correctness,
            scr=_safe_div(sum(1 for r in recs if r.result.schema_ok), n),
            tcaf=_safe_div(n, tasks),
            deadline_adherence=_safe_div(sum(1 for r in recs if r.within_deadline), n),
            blast_radius=_safe_div(failed_tasks, tasks),
        )

    def summary_dict(self) -> dict:
        return asdict(self.summary())
