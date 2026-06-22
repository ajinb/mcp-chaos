from mcp_chaos.config import load_fault_plan
from mcp_chaos.types import FaultTag, ToolCall, ToolResult


def test_load_fault_plan_from_yaml(tmp_path):
    p = tmp_path / "plan.yaml"
    p.write_text(
        "seed: 5\n"
        "faults:\n"
        "  - type: latency\n"
        "    added_ms: 300\n"
        "  - type: error_injection\n"
        "    rate: 1.0\n"
    )
    plan = load_fault_plan(str(p))
    r = plan.apply_response(ToolCall(tool="t"), ToolResult(content={"x": 1}, latency_ms=10))
    assert r.latency_ms == 310
    assert r.injected in (FaultTag.LATENCY, FaultTag.ERROR_INJECTION)
