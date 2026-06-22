import httpx
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from mcp_chaos.faults import DropToolFault, FaultPlan
from mcp_chaos.proxy.http import build_app


@pytest.mark.asyncio
async def test_http_proxy_injects_drop_tool():
    # Fake upstream: always returns a successful tools/call result.
    # We inject a fake HTTP client factory so the outer ASGI test transport
    # is not affected (patching httpx.AsyncClient.post at class level would
    # intercept the outer client's ASGI-dispatched call before FastAPI runs).
    async def fake_post(url, json=None, **kw):
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": json["id"],
                                         "result": {"content": [{"type": "text", "text": "ok"}]}})

    @asynccontextmanager
    async def fake_client_factory():
        client = AsyncMock()
        client.post = fake_post
        yield client

    plan = FaultPlan(faults=[DropToolFault(tools=["get_metrics"])], seed=0)
    app = build_app(upstream="http://upstream.invalid/mcp", plan=plan,
                    _http_client_factory=fake_client_factory)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                            "params": {"name": "get_metrics", "arguments": {}}})
    body = r.json()
    assert "error" in body
