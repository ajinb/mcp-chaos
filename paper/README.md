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

Reproducing the paper's measurements:

- Table I / Fig. 1 (blast-radius sweep): `python examples/blast_radius_sweep.py`
- Fig. 1 exactly (PDF + PNG): `python paper/figures/blast_radius_figure.py`
- Table II (correlated faults): `python examples/correlated_faults.py`
- Fig. 2 (reference architecture): `tectonic paper/figures/fig_architecture.tex`

arXiv link: _to be added on preprint posting._
