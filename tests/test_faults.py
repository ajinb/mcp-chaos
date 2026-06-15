import random

from mcp_chaos.faults import (
    DropToolFault,
    ErrorInjectionFault,
    FaultPlan,
    LatencyFault,
    PartialResultFault,
    RegistryInconsistencyFault,
    SchemaDriftFault,
)
from mcp_chaos.types import FaultTag, ToolCall, ToolResult


def _call(tool="get_metrics"):
    return ToolCall(tool=tool, deadline_ms=100)


def _result():
    return ToolResult(content={"cpu": 0.5, "mem": 0.6}, latency_ms=10)


def test_latency_fault_inflates_latency_and_tags():
    f = LatencyFault(added_ms=500)
    r = f.apply_response(_call(), _result(), random.Random(0))
    assert r.latency_ms == 510
    assert r.injected == FaultTag.LATENCY


def test_drop_tool_fault_makes_targeted_tool_unavailable():
    f = DropToolFault(tools=["get_metrics"])
    r = f.apply_response(_call("get_metrics"), _result(), random.Random(0))
    assert r.error is not None
    assert r.injected == FaultTag.DROP_TOOL
    # untargeted tool passes through
    r2 = f.apply_response(_call("get_logs"), _result(), random.Random(0))
    assert r2.error is None


def test_schema_drift_sets_schema_not_ok():
    f = SchemaDriftFault()
    r = f.apply_response(_call(), _result(), random.Random(0))
    assert r.schema_ok is False
    assert r.injected == FaultTag.SCHEMA_DRIFT


def test_partial_result_sets_unusable():
    f = PartialResultFault()
    r = f.apply_response(_call(), _result(), random.Random(0))
    assert r.usable is False
    assert r.injected == FaultTag.PARTIAL_RESULT


def test_registry_inconsistency_errors_on_call():
    f = RegistryInconsistencyFault(tools=["ghost_tool"])
    r = f.apply_response(_call("ghost_tool"), _result(), random.Random(0))
    assert r.error is not None
    assert r.injected == FaultTag.REGISTRY_INCONSISTENCY


def test_error_injection_is_probabilistic_and_seeded():
    f = ErrorInjectionFault(rate=0.5)
    rng = random.Random(1234)
    tags = [f.apply_response(_call(), _result(), rng).injected for _ in range(200)]
    errors = [t for t in tags if t == FaultTag.ERROR_INJECTION]
    # ~50% with this seed; assert it is clearly probabilistic, not all-or-nothing
    assert 60 < len(errors) < 140


def test_fault_plan_applies_all_active_faults():
    plan = FaultPlan(faults=[LatencyFault(added_ms=100), SchemaDriftFault()], seed=7)
    r = plan.apply_response(_call(), _result())
    assert r.latency_ms == 110
    assert r.schema_ok is False
