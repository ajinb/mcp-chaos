"""HTTP transport proxy: a FastAPI app that forwards JSON-RPC to an upstream MCP
HTTP endpoint, applying faults via ProxyEngine on the request and response.
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .common import ProxyEngine


def build_app(upstream: str, plan, strict: bool = False,
              _http_client_factory=None) -> FastAPI:
    """Build the FastAPI proxy app.

    Args:
        upstream: URL of the upstream MCP HTTP endpoint.
        plan: FaultPlan to apply.
        strict: Raise on internal errors instead of failing safe.
        _http_client_factory: Optional callable returning an async context manager
            that behaves like ``httpx.AsyncClient(timeout=30)``. Used in tests to
            inject a fake HTTP client without patching the global class.
    """
    app = FastAPI(title="mcp-chaos http proxy")
    engine = ProxyEngine(plan, strict=strict)
    _make_client = _http_client_factory or (lambda: httpx.AsyncClient(timeout=30))

    @app.post("/mcp")
    async def proxy(request: Request) -> JSONResponse:
        msg = await request.json()
        msg = engine.on_request_message(msg)
        async with _make_client() as client:
            upstream_resp = await client.post(upstream, json=msg)
        out = engine.on_response_message(upstream_resp.json())
        return JSONResponse(out)

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> dict:
        return engine.metrics.summary_dict()

    return app
