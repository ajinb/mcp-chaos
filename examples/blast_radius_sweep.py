"""Sweep injected per-call error rate x fan-out (TCAF) and measure blast radius.

Produces the measured curves behind Table 1 of the Tool-Call Plane paper:
for each (error_rate, fanout) cell, run the offline deterministic workload
across many seeds, with and without the resilience patterns, and report the
mean agent-task blast radius against the p^TCAF independence prediction.

Usage: python examples/blast_radius_sweep.py [--tasks 200] [--seeds 20]
"""

from __future__ import annotations

import argparse
import statistics

from mcp_chaos.resilience import ResilienceConfig
from mcp_chaos.sim.agent_loop import run_workload

ERROR_RATES = [0.005, 0.01, 0.02, 0.05, 0.10]
FANOUTS = [2, 4, 8, 16]


def cell(tasks: int, fanout: int, error_rate: float, seeds: range, resilience: ResilienceConfig):
    brs = [
        run_workload(tasks=tasks, fanout=fanout, error_rate=error_rate,
                     seed=s, resilience=resilience).blast_radius
        for s in seeds
    ]
    return statistics.mean(brs), (statistics.stdev(brs) if len(brs) > 1 else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()
    seeds = range(args.seeds)

    print(f"tasks/cell={args.tasks} seeds/cell={args.seeds} "
          f"({args.tasks * args.seeds} tasks per estimate)\n")
    print(f"{'err':>5} {'TCAF':>4} | {'predicted':>9} | {'BR no-res':>16} | {'BR resilient':>16}")
    print("-" * 62)
    for e in ERROR_RATES:
        for f in FANOUTS:
            predicted = 1 - (1 - e) ** f
            nr_m, nr_s = cell(args.tasks, f, e, seeds, ResilienceConfig.disabled())
            wr_m, wr_s = cell(args.tasks, f, e, seeds, ResilienceConfig.enabled())
            print(f"{e:>5.1%} {f:>4} | {predicted:>9.1%} | "
                  f"{nr_m:>7.1%} ±{nr_s:>6.1%} | {wr_m:>7.1%} ±{wr_s:>6.1%}")
        print()


if __name__ == "__main__":
    main()
