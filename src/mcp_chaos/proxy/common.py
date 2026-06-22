"""Transport-independent proxy engine: maps JSON-RPC tools/call traffic onto the
core ToolCall/ToolResult vocabulary, applies the interceptor, records metrics,
and rewrites the JSON-RPC response to reflect injected faults.
"""

from __future__ import annotations

from typing import Any

from ..interceptor import Interceptor
from ..metrics import MetricsCollector
from ..types import CallRecord, FaultTag, ToolCall, ToolResult


class ProxyEngine:
    def __init__(self, plan, strict: bool = False):
        self.ix = Interceptor(plan)
        self.metrics = MetricsCollector()
        self.strict = strict
        self._pending: dict[Any, ToolCall] = {}  # JSON-RPC id -> ToolCall

    def on_request_message(self, msg: dict) -> dict:
        try:
            if msg.get("method") == "tools/call":
                params = msg.get("params", {})
                call = ToolCall(
                    tool=params.get("name", ""),
                    arguments=params.get("arguments", {}) or {},
                    call_id=str(msg.get("id")),
                    task_id="live",
                    deadline_ms=1000.0,
                )
                self._pending[msg.get("id")] = self.ix.on_request(call)
        except Exception:
            if self.strict:
                raise
        return msg

    def on_response_message(self, msg: dict) -> dict:
        rid = msg.get("id")
        call = self._pending.pop(rid, None)
        if call is None:
            return msg  # not a tools/call response we are tracking
        try:
            base = ToolResult(content=msg.get("result"), latency_ms=0.0)
            faulted = self.ix.on_response(call, base)
            self.metrics.record_call(CallRecord(call=call, result=faulted))
            self.metrics.record_task(call.task_id, success=faulted.injected == FaultTag.NONE)
            return self._rewrite(msg, faulted)
        except Exception:
            if self.strict:
                raise
            return msg  # fail safe: forward original

    @staticmethod
    def _rewrite(msg: dict, result: ToolResult) -> dict:
        if result.error is not None:
            return {"jsonrpc": "2.0", "id": msg.get("id"),
                    "error": {"code": -32000, "message": result.error}}
        if not result.schema_ok or not result.usable:
            # Mark degraded results so downstream sees reduced fidelity.
            out = dict(msg)
            out.setdefault("_mcp_chaos", {})
            out["_mcp_chaos"] = {"injected": result.injected.value}
            return out
        return msg
