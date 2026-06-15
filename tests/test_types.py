from mcp_chaos.types import CallRecord, FaultTag, ToolCall, ToolResult


def test_successful_record_is_success():
    rec = CallRecord(
        call=ToolCall(tool="get_metrics", task_id="t1", deadline_ms=1000),
        result=ToolResult(content={"cpu": 0.5}, latency_ms=50),
    )
    assert rec.responded is True
    assert rec.within_deadline is True
    assert rec.correct is True
    assert rec.success is True


def test_schema_drift_breaks_correctness_not_availability():
    rec = CallRecord(
        call=ToolCall(tool="get_metrics", deadline_ms=1000),
        result=ToolResult(content={}, schema_ok=False, latency_ms=50, injected=FaultTag.SCHEMA_DRIFT),
    )
    assert rec.responded is True
    assert rec.correct is False
    assert rec.success is False


def test_hard_error_is_unavailable():
    rec = CallRecord(
        call=ToolCall(tool="get_metrics", deadline_ms=1000),
        result=ToolResult(error="tool unavailable", injected=FaultTag.DROP_TOOL),
    )
    assert rec.responded is False
    assert rec.correct is False


def test_latency_past_deadline_fails_adherence():
    rec = CallRecord(
        call=ToolCall(tool="get_metrics", deadline_ms=100),
        result=ToolResult(content={"ok": 1}, latency_ms=250, injected=FaultTag.LATENCY),
    )
    assert rec.within_deadline is False
    assert rec.success is False
