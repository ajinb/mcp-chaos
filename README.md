# mcp-chaos

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

> Chaos engineering for the **MCP tool-call plane**. Inject operational faults into MCP tool calls and measure their **agent-task blast radius** — the reliability-testing counterpart to [mcp-gateway](https://github.com/ajinb/mcp-gateway).

Most MCP tooling is studied as a *security* surface. `mcp-chaos` treats the tool-call path as what it has become in production: a distributed-systems tier with its own reliability properties. It injects latency, dropped tools, schema drift, partial results, registry inconsistency, iid errors, **correlated burst errors**, and **server-scoped degradation episodes** — then reports the SLIs that actually predict whether your agent works.

Companion to the paper *The Tool-Call Plane: An Operational Reliability Model for MCP-Based Agent Infrastructure* (see [`paper/`](paper/)).

## Install

```bash
pip install -e ".[dev]"     # includes proxy extras for stdio + http
```

Requires Python 3.11+.

## The 30-second demo (offline, no API key)

```bash
mcp-chaos demo
```

Runs a fan-out workload (TCAF=8) with 2% injected per-call failure, with and without resilience patterns, and prints the before/after blast radius:

```
no resilience    TCAF=8.0  TCSR= 0.98  ETA= 0.98  blast_radius= 0.12
with resilience  TCAF=8.0  TCSR= 1.00  ETA= 1.00  blast_radius= 0.00
```

A 2% per-call failure compounds to a **12% task blast radius** at TCAF=8 — and retry budgets plus graceful degradation recover all of it. That is the tool-call-plane reliability story in one command, reproduced deterministically (seed 42).

## Inject faults into a real MCP server

```bash
# stdio server (what Claude Desktop / Claude Code spawn locally)
mcp-chaos proxy stdio --plan fault-plan.example.yaml -- python -m your_mcp_server

# HTTP server
mcp-chaos proxy http --plan fault-plan.example.yaml --upstream http://localhost:8000/mcp
```

Faults are declared in a YAML plan ([`fault-plan.example.yaml`](fault-plan.example.yaml)). The proxy **fails safe**: any internal error forwards the original traffic unless you pass `--strict`.

## Correlated faults (paper §6, Table II)

Independent per-call faults are the benign case. The correlated sweep re-runs the
headline cell (~2% marginal per-call error, TCAF=8) with the same marginal rate
delivered as temporal bursts and as server-scoped degradation episodes:

```bash
python examples/correlated_faults.py
```

Three measured effects: correlation concentrates failure into heavy tails (mean
blast radius *below* the iid prediction, variance way up); retry budgets stop
working (retries land inside the burst that failed the first attempt); and a
circuit breaker without half-open probes becomes a liability — a transient
episode trips it permanently, locking tools out for the rest of the run.
`ResilienceConfig.enabled(probe_interval=8)` enables half-open probes, which
eliminate lock-in; server-scoped outages additionally need structural
containment (bulkheads/failover), not per-call patterns.

## Metrics (paper §5)

| SLI | Meaning |
|---|---|
| **TCSR** | tool-call success rate |
| **ETA = A × C** | effective tool availability: responded (A) × correct (C) |
| **SCR** | schema-conformance rate |
| **TCAF** | tool-call amplification factor (calls per user intent) |
| **Deadline Adherence** | calls completing within the agent's step budget |
| **Blast Radius** | fraction of agent tasks that fail |

The key insight ETA captures: a tool can be 99.9% *available* and still wrong 10% of the time — `ETA = A × C` separates "the tool answered" from "the tool answered correctly," which raw uptime hides.

## How it's built

One pure, transport-agnostic core (`faults → interceptor → metrics`) speaking a common `ToolCall`/`ToolResult` vocabulary, driven by three adapters: an offline deterministic simulator (`sim/`) and two live proxies (`proxy/stdio.py`, `proxy/http.py`). Fault logic is written once and proven by the offline demo, then runs unchanged against live servers.

## License

Apache-2.0.
