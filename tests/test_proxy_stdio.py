from mcp_chaos.faults import DropToolFault, FaultPlan, LatencyFault
from mcp_chaos.proxy.common import ProxyEngine


def test_engine_intercepts_tools_call_response():
    plan = FaultPlan(faults=[LatencyFault(added_ms=100)], seed=0)
    engine = ProxyEngine(plan)

    # Simulate a tools/call request then its response, by JSON-RPC id.
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": "get_metrics", "arguments": {}}}
    engine.on_request_message(req)

    resp = {"jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": "{\"cpu\":0.5}"}]}}
    out = engine.on_response_message(resp)

    # A latency fault does not alter the JSON-RPC body, but the call is recorded.
    s = engine.metrics.summary()
    assert s.calls == 1
    assert s.tcaf >= 0  # one call, recorded

    # An error fault would surface as a JSON-RPC error; verify recording path.
    assert out["id"] == 1


def test_engine_drop_tool_turns_response_into_error():
    engine = ProxyEngine(FaultPlan(faults=[DropToolFault(tools=["get_metrics"])], seed=0))
    engine.on_request_message({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                               "params": {"name": "get_metrics", "arguments": {}}})
    out = engine.on_response_message({"jsonrpc": "2.0", "id": 7,
                                      "result": {"content": [{"type": "text", "text": "ok"}]}})
    assert "error" in out
    assert engine.metrics.summary().availability == 0.0


def test_two_calls_blast_radius_reflects_partial_failure():
    """Two tools/call round-trips with one tool dropped → blast_radius == 0.5."""
    # Drop only "bad_tool"; "good_tool" succeeds.
    engine = ProxyEngine(FaultPlan(faults=[DropToolFault(tools=["bad_tool"])], seed=0))

    # First call: bad_tool (will be dropped → task fails)
    engine.on_request_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "bad_tool", "arguments": {}}})
    engine.on_response_message({"jsonrpc": "2.0", "id": 1,
                                "result": {"content": [{"type": "text", "text": "ok"}]}})

    # Second call: good_tool (succeeds → task succeeds)
    engine.on_request_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                               "params": {"name": "good_tool", "arguments": {}}})
    engine.on_response_message({"jsonrpc": "2.0", "id": 2,
                                "result": {"content": [{"type": "text", "text": "ok"}]}})

    s = engine.metrics.summary()
    assert s.blast_radius == 0.5
