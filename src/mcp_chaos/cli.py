"""mcp-chaos command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import sys

from .config import load_fault_plan
from .resilience import ResilienceConfig
from .sim.agent_loop import run_workload


def _row(label, s):
    return (f"{label:<16} TCAF={s.tcaf:.1f}  TCSR={s.tcsr:>5.2f}  "
            f"ETA={s.eta:>5.2f}  blast_radius={s.blast_radius:>5.2f}")


def cmd_demo(tasks=200, fanout=8, error_rate=0.02, seed=42) -> int:
    params = dict(tasks=tasks, fanout=fanout, error_rate=error_rate, seed=seed)
    no_res = run_workload(resilience=ResilienceConfig.disabled(), **params)
    with_res = run_workload(resilience=ResilienceConfig.enabled(), **params)
    print("mcp-chaos — tool-call-plane blast radius (fan-out, injected error)\n")
    print(_row("no resilience", no_res))
    print(_row("with resilience", with_res))
    return 0


def cmd_proxy(args) -> int:
    plan = load_fault_plan(args.plan) if args.plan else None
    if args.transport == "stdio":
        from .proxy.stdio import run_stdio_proxy
        return asyncio.run(run_stdio_proxy(args.server_cmd, plan, strict=args.strict))
    if args.transport == "http":
        import uvicorn
        from .proxy.http import build_app
        app = build_app(upstream=args.upstream, plan=plan, strict=args.strict)
        uvicorn.run(app, host="127.0.0.1", port=args.port)
        return 0
    raise SystemExit(f"unknown transport: {args.transport}")


class _StrippingNamespace(argparse.Namespace):
    """Post-processes server_cmd to strip a leading '--' left by argparse.REMAINDER."""

    def __setattr__(self, name, value):
        if name == "server_cmd" and isinstance(value, list) and value and value[0] == "--":
            value = value[1:]
        super().__setattr__(name, value)


class _StrippingParser(argparse.ArgumentParser):
    """ArgumentParser subclass that uses _StrippingNamespace by default."""

    def parse_args(self, args=None, namespace=None):
        if namespace is None:
            namespace = _StrippingNamespace()
        return super().parse_args(args, namespace)

    def parse_known_args(self, args=None, namespace=None):
        if namespace is None:
            namespace = _StrippingNamespace()
        return super().parse_known_args(args, namespace)


def build_parser() -> argparse.ArgumentParser:
    parser = _StrippingParser(prog="mcp-chaos")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="offline deterministic blast-radius reproduction")

    proxy = sub.add_parser("proxy", help="inject faults into a live MCP server")
    ptr = proxy.add_subparsers(dest="transport", required=True)

    stdio = ptr.add_parser("stdio", help="wrap a stdio MCP server command")
    stdio.add_argument("--plan")
    stdio.add_argument("--strict", action="store_true")
    stdio.add_argument("server_cmd", nargs=argparse.REMAINDER,
                       help="-- <server command and args>")

    http = ptr.add_parser("http", help="front an HTTP MCP server")
    http.add_argument("--plan")
    http.add_argument("--strict", action="store_true")
    http.add_argument("--upstream", required=True)
    http.add_argument("--port", type=int, default=8900)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        return cmd_demo()
    if args.command == "proxy":
        return cmd_proxy(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
