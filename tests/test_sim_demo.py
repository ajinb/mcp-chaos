from mcp_chaos.resilience import ResilienceConfig
from mcp_chaos.sim.agent_loop import run_workload


def test_resilience_reduces_blast_radius():
    # Fan-out workload at TCAF=8, 2% per-call injected error, fixed seed.
    no_res = run_workload(tasks=200, fanout=8, error_rate=0.02, seed=42,
                          resilience=ResilienceConfig.disabled())
    with_res = run_workload(tasks=200, fanout=8, error_rate=0.02, seed=42,
                            resilience=ResilienceConfig.enabled())

    assert no_res.tcaf == 8.0
    # Naive fan-out compounds failures: a meaningful fraction of tasks fail.
    assert no_res.blast_radius > 0.08
    # Retry budget + graceful degradation recover most of the gap.
    assert with_res.blast_radius < no_res.blast_radius / 2
