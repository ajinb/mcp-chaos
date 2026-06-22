"""Reproduce Paper A's tool-call-plane blast-radius result, offline, deterministically.

Run: python examples/blast_radius_demo.py
"""

from mcp_chaos.resilience import ResilienceConfig
from mcp_chaos.sim.agent_loop import run_workload

PARAMS = dict(tasks=200, fanout=8, error_rate=0.02, seed=42)


def _row(label, s):
    return (f"{label:<16} TCAF={s.tcaf:>4.1f}  TCSR={s.tcsr:>5.2f}  "
            f"ETA={s.eta:>5.2f}  blast_radius={s.blast_radius:>5.2f}")


def main():
    no_res = run_workload(resilience=ResilienceConfig.disabled(), **PARAMS)
    with_res = run_workload(resilience=ResilienceConfig.enabled(), **PARAMS)
    print("mcp-chaos — tool-call-plane blast radius (fan-out TCAF=8, 2% injected error)\n")
    print(_row("no resilience", no_res))
    print(_row("with resilience", with_res))
    print(f"\nrecovered: {no_res.blast_radius - with_res.blast_radius:.2f} of task blast radius")


if __name__ == "__main__":
    main()
