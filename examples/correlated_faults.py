"""Correlated-fault experiments: the paper's independence caveat, measured.

Independent per-call faults are the benign case. Here the same ~2% marginal
per-call error rate is injected three ways: iid, in temporal bursts (mean
length L calls), and as server-scoped degradation episodes (a whole server's
tools failing together for a mean of E consecutive tasks). Each condition runs
without resilience, with the Table-I resilience patterns (retry budget 2,
graceful degradation, ETA breaker), and with the breaker additionally allowed
half-open probes. Everything is offline and deterministic — no LLM involved —
mirroring examples/blast_radius_sweep.py.

`lock-in` counts seeds whose no-probe resilient blast radius exceeds 50%: runs
where a transient correlated fault tripped the cumulative-ETA breaker and,
with no half-open recovery, converted it into a permanent outage.

Usage: python examples/correlated_faults.py [--tasks 200] [--seeds 50]
"""

from __future__ import annotations

import argparse
import statistics

from mcp_chaos.faults import BurstErrorFault, ErrorInjectionFault, ServerDegradationFault
from mcp_chaos.resilience import ResilienceConfig
from mcp_chaos.sim.agent_loop import run_workload

RATE = 0.02         # marginal per-call error rate for every condition
FANOUT = 8          # TCAF: the paper's headline cell
PROBE_INTERVAL = 8  # skipped calls between half-open probes (~1 probe per 4 tasks/tool)
IID_PREDICTION = 1 - (1 - RATE) ** FANOUT


def cell(tasks: int, seeds: range, resilience: ResilienceConfig, make_fault):
    brs, marginals = [], []
    for s in seeds:
        summary = run_workload(tasks=tasks, fanout=FANOUT, error_rate=RATE, seed=s,
                               resilience=resilience, faults=[make_fault()])
        brs.append(summary.blast_radius)
        marginals.append(1.0 - summary.availability)
    return brs, statistics.mean(marginals)


def _fmt(brs: list[float]) -> str:
    mean = statistics.mean(brs)
    sd = statistics.stdev(brs) if len(brs) > 1 else 0.0
    return f"{mean:>6.1%} ±{sd:>6.1%}"


def row(label: str, tasks: int, seeds: range, make_fault) -> None:
    no_res, marginal = cell(tasks, seeds, ResilienceConfig.disabled(), make_fault)
    res, _ = cell(tasks, seeds, ResilienceConfig.enabled(), make_fault)
    probed, _ = cell(tasks, seeds, ResilienceConfig.enabled(probe_interval=PROBE_INTERVAL),
                     make_fault)
    lockins = sum(1 for br in res if br > 0.5)
    print(f"{label:>24} | {marginal:>8.1%} | {_fmt(no_res)} | {_fmt(res)} | "
          f"{lockins:>7}/{len(res)} | {_fmt(probed)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=50)
    args = ap.parse_args()
    seeds = range(args.seeds)

    print(f"marginal per-call error rate ~{RATE:.0%}, TCAF={FANOUT}, "
          f"iid prediction 1-(1-e)^TCAF = {IID_PREDICTION:.1%}")
    print(f"tasks/cell={args.tasks} seeds/cell={args.seeds} "
          f"({args.tasks * args.seeds} tasks per estimate); "
          f"probe interval={PROBE_INTERVAL} skipped calls\n")

    print(f"{'condition':>24} | {'marginal':>8} | {'BR no-res':>14} | "
          f"{'BR resilient':>14} | {'lock-in':>10} | {'BR res+probes':>14}")
    print("-" * 100)
    row("iid", args.tasks, seeds, lambda: ErrorInjectionFault(rate=RATE))
    for burst in (4, 16, 64):
        row(f"bursts, mean {burst} calls", args.tasks, seeds,
            lambda burst=burst: BurstErrorFault(rate=RATE, burst_len=burst))
    # 2 of 8 calls/task hit the degraded server => episode_rate 8% x 25% = 2% marginal.
    row("server episodes, mean 20", args.tasks, seeds,
        lambda: ServerDegradationFault(tools=["describe_service", "check_dependency"],
                                       episode_rate=0.08, episode_len=20))


if __name__ == "__main__":
    main()
