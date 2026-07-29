"""A deterministic non-LLM agent: each task fans out to `fanout` tool calls.

This makes TCAF an input (not an emergent property) so blast radius is
measurable offline without a model. A task succeeds iff every required call
ultimately succeeds; resilience (retry budget, graceful degradation, ETA
breaker) modifies how the agent reacts to failed calls.
"""

from __future__ import annotations

from ..faults import ErrorInjectionFault, Fault, FaultPlan
from ..interceptor import Interceptor
from ..metrics import MetricsCollector, Summary
from ..resilience import CircuitBreaker, ResilienceConfig
from ..types import CallRecord, ToolCall
from .fake_server import FakeMCPServer

# Of the tools a task touches, treat the last two as "non-critical": under
# graceful degradation a task can still succeed if only those fail.
_NONCRITICAL_TAIL = 2


def run_workload(
    tasks: int,
    fanout: int,
    error_rate: float,
    seed: int,
    resilience: ResilienceConfig,
    faults: list[Fault] | None = None,
) -> Summary:
    """Drive the workload. By default injects iid per-call errors at `error_rate`;
    pass `faults` to substitute any fault list (e.g. correlated burst or
    server-degradation faults) while keeping the same workload and metrics."""
    server = FakeMCPServer()
    plan = FaultPlan(
        faults=list(faults) if faults is not None else [ErrorInjectionFault(rate=error_rate)],
        seed=seed,
    )
    ix = Interceptor(plan)
    metrics = MetricsCollector()
    breaker = CircuitBreaker(resilience.eta_breaker_threshold, resilience.breaker_probe_interval)
    tools = server.tools()

    for i in range(tasks):
        task_id = f"task-{i}"
        task_ok = True
        for j in range(fanout):
            tool = tools[j % len(tools)]
            critical = j < fanout - _NONCRITICAL_TAIL

            if breaker.is_open(tool) and not breaker.should_probe(tool):
                # Tool known-bad: degrade if allowed, else fail the task.
                # (When probing is enabled, every Nth skip falls through and the
                # call becomes a half-open probe; its outcome closes the breaker
                # via observe() on success.)
                if not (resilience.graceful_degradation and not critical):
                    task_ok = False
                continue

            call = ToolCall(tool=tool, task_id=task_id, deadline_ms=1000)
            rec = _attempt(call, server, ix, resilience.retry_budget)
            metrics.record_call(rec)
            breaker.observe(tool, rec.responded, rec.correct)

            if not rec.success:
                if resilience.graceful_degradation and not critical:
                    continue  # tolerate non-critical failure
                task_ok = False
        metrics.record_task(task_id, success=task_ok)

    return metrics.summary()


def _attempt(call: ToolCall, server: FakeMCPServer, ix: Interceptor, retry_budget: int) -> CallRecord:
    original = call
    attempts = 0
    last = None
    while attempts <= retry_budget:
        faulted_call = ix.on_request(original)
        result = ix.on_response(faulted_call, server.call(faulted_call))
        rec = CallRecord(call=faulted_call, result=result, retries=attempts)
        if rec.success:
            return rec
        last = rec
        attempts += 1
    return last
