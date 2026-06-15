"""The single, transport-agnostic place faults are applied to a call/result."""

from __future__ import annotations

from .faults import FaultPlan
from .types import ToolCall, ToolResult


class Interceptor:
    def __init__(self, plan: FaultPlan | None):
        self.plan = plan

    def on_request(self, call: ToolCall) -> ToolCall:
        if self.plan is None:
            return call
        return self.plan.apply_request(call)

    def on_response(self, call: ToolCall, result: ToolResult) -> ToolResult:
        if self.plan is None:
            return result
        return self.plan.apply_response(call, result)
