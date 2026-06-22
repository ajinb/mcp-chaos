"""A deterministic FakeMCPServer: fixed tool catalog, baseline latency/results."""

from __future__ import annotations

from ..types import ToolCall, ToolResult

# Baseline (fault-free) latency per tool, milliseconds.
_CATALOG = {
    "get_metrics": 20.0,
    "get_logs": 35.0,
    "get_traces": 30.0,
    "describe_service": 15.0,
    "check_dependency": 25.0,
}


class FakeMCPServer:
    def __init__(self, catalog: dict[str, float] | None = None):
        self.catalog = catalog or dict(_CATALOG)

    def tools(self) -> list[str]:
        return list(self.catalog)

    def call(self, call: ToolCall) -> ToolResult:
        latency = self.catalog.get(call.tool)
        if latency is None:
            return ToolResult(error=f"unknown tool '{call.tool}'")
        return ToolResult(content={"tool": call.tool, "ok": True}, latency_ms=latency)
