from mcp_chaos.faults import FaultPlan, LatencyFault
from mcp_chaos.interceptor import Interceptor
from mcp_chaos.types import ToolCall, ToolResult


def test_interceptor_applies_plan_to_response():
    plan = FaultPlan(faults=[LatencyFault(added_ms=200)], seed=0)
    ix = Interceptor(plan)
    call = ToolCall(tool="get_metrics", deadline_ms=100)
    result = ix.on_response(call, ToolResult(content={"x": 1}, latency_ms=10))
    assert result.latency_ms == 210


def test_interceptor_no_plan_is_passthrough():
    ix = Interceptor(None)
    call = ToolCall(tool="get_metrics")
    result = ToolResult(content={"x": 1}, latency_ms=10)
    assert ix.on_response(call, result) is result
    assert ix.on_request(call) is call
