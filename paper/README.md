# Companion paper

This repository is the companion artifact for:

**The Tool-Call Plane: An Operational Reliability Model for MCP-Based Agent Infrastructure**

`mcp-chaos` implements the paper's operational fault taxonomy (§4), service-level
indicators (§5) — including the Tool-Call Amplification Factor (TCAF) and the
Effective Tool Availability decomposition (ETA = A × C) — the chaos-engineering
methodology (§6), and the resilience patterns (§7).

The `mcp-chaos demo` command reproduces the paper's headline result deterministically:
a 2% per-call failure rate at TCAF=8 compounds to a ~12% task blast radius, recovered
to ~0% once retry budgets and graceful degradation are enabled.

arXiv link: _to be added on preprint posting._
