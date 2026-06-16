from mcp_chaos.metrics import MetricsCollector
from mcp_chaos.types import CallRecord, ToolCall, ToolResult


def _ok(task):
    return CallRecord(ToolCall(tool="t", task_id=task, deadline_ms=100),
                      ToolResult(content={"x": 1}, latency_ms=10))


def _err(task):
    return CallRecord(ToolCall(tool="t", task_id=task, deadline_ms=100),
                      ToolResult(error="boom", latency_ms=10))


def test_tcsr_and_eta_and_tcaf():
    m = MetricsCollector()
    # task A: 2 ok; task B: 1 ok 1 err
    for r in (_ok("A"), _ok("A"), _ok("B"), _err("B")):
        m.record_call(r)
    m.record_task("A", success=True)
    m.record_task("B", success=False)
    s = m.summary()
    assert s.tcaf == 2.0                 # 4 calls / 2 tasks
    assert s.tcsr == 0.75                # 3 of 4 calls succeeded
    assert round(s.availability, 3) == 0.75   # A: 3 of 4 responded
    assert round(s.correctness, 3) == 1.0     # of the 3 responded, all correct
    assert round(s.eta, 3) == 0.75       # A * C
    assert s.blast_radius == 0.5         # 1 of 2 tasks failed


def test_deadline_adherence():
    m = MetricsCollector()
    slow = CallRecord(ToolCall(tool="t", task_id="A", deadline_ms=100),
                      ToolResult(content={"x": 1}, latency_ms=250))
    m.record_call(_ok("A"))
    m.record_call(slow)
    m.record_task("A", success=False)
    assert m.summary().deadline_adherence == 0.5
