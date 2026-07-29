"""Correlated fault modes: temporal bursts and server-scoped degradation.

These test the paper's caveat experiment: independent per-call faults are the
benign case, so the harness must be able to inject *correlated* faults (whole
bursts / whole servers failing together) at a matched marginal per-call rate.
"""

from __future__ import annotations

import itertools

from mcp_chaos.faults import (
    BurstErrorFault,
    ErrorInjectionFault,
    FaultPlan,
    ServerDegradationFault,
)
from mcp_chaos.resilience import ResilienceConfig
from mcp_chaos.sim.agent_loop import run_workload
from mcp_chaos.types import FaultTag, ToolCall, ToolResult


def _drive(plan: FaultPlan, calls: list[tuple[str, str]]) -> list[bool]:
    """Apply the plan to a sequence of (task_id, tool) calls; return injected flags."""
    flags = []
    for task_id, tool in calls:
        call = ToolCall(tool=tool, task_id=task_id)
        result = plan.apply_response(call, ToolResult(content={}, latency_ms=1.0))
        flags.append(result.injected is not FaultTag.NONE)
    return flags


def _conditional_failure_rate(flags: list[bool]) -> float:
    """P(fail at i | fail at i-1)."""
    prior_failures = [b for a, b in itertools.pairwise(flags) if a]
    return sum(prior_failures) / len(prior_failures) if prior_failures else 0.0


# ---------------------------------------------------------------- BurstErrorFault

def test_burst_marginal_rate_matches_target():
    plan = FaultPlan(faults=[BurstErrorFault(rate=0.02, burst_len=8)], seed=1)
    flags = _drive(plan, [(f"t{i // 8}", "get_metrics") for i in range(200_000)])
    marginal = sum(flags) / len(flags)
    assert 0.016 <= marginal <= 0.024  # matched to 2% within tolerance


def test_burst_failures_are_bursty():
    plan = FaultPlan(faults=[BurstErrorFault(rate=0.02, burst_len=8)], seed=2)
    flags = _drive(plan, [(f"t{i // 8}", "get_metrics") for i in range(200_000)])
    # Mean burst length 8 => continue probability 1 - 1/8 = 0.875 >> marginal rate.
    assert _conditional_failure_rate(flags) > 0.5


def test_burst_len_one_is_iid_like():
    plan = FaultPlan(faults=[BurstErrorFault(rate=0.02, burst_len=1)], seed=3)
    flags = _drive(plan, [(f"t{i // 8}", "get_metrics") for i in range(200_000)])
    marginal = sum(flags) / len(flags)
    assert 0.016 <= marginal <= 0.024
    # No memory beyond a single call: conditional rate collapses to ~marginal.
    assert _conditional_failure_rate(flags) < 0.1


def test_burst_deterministic_per_seed():
    calls = [(f"t{i // 8}", "get_metrics") for i in range(5_000)]
    a = _drive(FaultPlan(faults=[BurstErrorFault(rate=0.05, burst_len=4)], seed=7), calls)
    b = _drive(FaultPlan(faults=[BurstErrorFault(rate=0.05, burst_len=4)], seed=7), calls)
    assert a == b


def test_fault_state_resets_across_plans():
    # Reusing the same fault instance in a new plan must not leak burst state.
    fault = BurstErrorFault(rate=0.05, burst_len=4)
    calls = [(f"t{i // 8}", "get_metrics") for i in range(5_000)]
    a = _drive(FaultPlan(faults=[fault], seed=7), calls)
    b = _drive(FaultPlan(faults=[fault], seed=7), calls)
    assert a == b


def test_burst_injects_burst_error_tag():
    plan = FaultPlan(faults=[BurstErrorFault(rate=1.0, burst_len=4)], seed=0)
    call = ToolCall(tool="get_metrics", task_id="t0")
    result = plan.apply_response(call, ToolResult(content={}))
    assert result.injected is FaultTag.BURST_ERROR
    assert result.error is not None


# --------------------------------------------------------- ServerDegradationFault

def test_server_degradation_scopes_to_tools():
    plan = FaultPlan(
        faults=[ServerDegradationFault(tools=["b1", "b2"], episode_rate=0.5, episode_len=5)],
        seed=4,
    )
    a_flags, b_flags = [], []
    for i in range(2_000):
        for tool in ("a1", "b1", "b2"):
            call = ToolCall(tool=tool, task_id=f"t{i}")
            result = plan.apply_response(call, ToolResult(content={}))
            (b_flags if tool.startswith("b") else a_flags).append(
                result.injected is not FaultTag.NONE
            )
    assert not any(a_flags)          # non-hosted tools never affected
    assert any(b_flags)              # hosted tools affected during episodes
    assert not all(b_flags)          # ... but not always (episodes end)


def test_server_degradation_all_or_nothing_within_task():
    plan = FaultPlan(
        faults=[ServerDegradationFault(tools=["b1", "b2"], episode_rate=0.3, episode_len=5)],
        seed=5,
    )
    for i in range(2_000):
        flags = []
        # Multiple calls to the degraded server within one task (incl. a retry-like repeat):
        for tool in ("b1", "b2", "b1"):
            call = ToolCall(tool=tool, task_id=f"t{i}")
            result = plan.apply_response(call, ToolResult(content={}))
            flags.append(result.injected is not FaultTag.NONE)
        assert len(set(flags)) == 1  # the whole server is either up or down for the task


def test_server_degradation_active_fraction_matches_rate():
    plan = FaultPlan(
        faults=[ServerDegradationFault(tools=["b1"], episode_rate=0.08, episode_len=20)],
        seed=6,
    )
    flags = _drive(plan, [(f"t{i}", "b1") for i in range(50_000)])
    active = sum(flags) / len(flags)
    assert 0.05 <= active <= 0.11  # stationary fraction ~= episode_rate (correlated, fixed seed)


def test_server_degradation_tag():
    plan = FaultPlan(
        faults=[ServerDegradationFault(tools=["b1"], episode_rate=1.0, episode_len=5)],
        seed=0,
    )
    result = plan.apply_response(ToolCall(tool="b1", task_id="t0"), ToolResult(content={}))
    assert result.injected is FaultTag.SERVER_DEGRADATION
    assert result.error is not None


# ------------------------------------------------------------- run_workload wiring

def test_run_workload_accepts_custom_faults():
    default = run_workload(tasks=100, fanout=8, error_rate=0.02, seed=11,
                           resilience=ResilienceConfig.disabled())
    explicit = run_workload(tasks=100, fanout=8, error_rate=0.02, seed=11,
                            resilience=ResilienceConfig.disabled(),
                            faults=[ErrorInjectionFault(rate=0.02)])
    assert explicit.blast_radius == default.blast_radius
    assert explicit.tcaf == default.tcaf


def test_bursts_defeat_retry_budget():
    """The caveat, in test form: at the same 2% marginal rate and TCAF=8,
    long bursts push measured blast radius *below* the independence prediction
    (failures concentrate) while resilient blast radius rises well above ~0%
    (retries land inside the same burst)."""
    iid_pred = 1 - (1 - 0.02) ** 8  # 14.9%
    no_res, res = [], []
    for seed in range(10):
        no_res.append(run_workload(
            tasks=200, fanout=8, error_rate=0.02, seed=seed,
            resilience=ResilienceConfig.disabled(),
            faults=[BurstErrorFault(rate=0.02, burst_len=16)]).blast_radius)
        res.append(run_workload(
            tasks=200, fanout=8, error_rate=0.02, seed=seed,
            resilience=ResilienceConfig.enabled(),
            faults=[BurstErrorFault(rate=0.02, burst_len=16)]).blast_radius)
    assert sum(no_res) / len(no_res) < iid_pred * 0.75
    assert sum(res) / len(res) > 0.005  # iid recovery was 0.0%


def test_server_outage_defeats_recovery():
    """Server-scoped episodes at a matched ~2% marginal rate: per-call retry and
    graceful degradation recover almost none of it (the server is down for the
    whole task, and its tools sit in critical slots)."""
    fault = {"tools": ["describe_service", "check_dependency"],
             "episode_rate": 0.08, "episode_len": 20}
    no_res, res = [], []
    for seed in range(10):
        no_res.append(run_workload(
            tasks=200, fanout=8, error_rate=0.02, seed=seed,
            resilience=ResilienceConfig.disabled(),
            faults=[ServerDegradationFault(**fault)]).blast_radius)
        res.append(run_workload(
            tasks=200, fanout=8, error_rate=0.02, seed=seed,
            resilience=ResilienceConfig.enabled(),
            faults=[ServerDegradationFault(**fault)]).blast_radius)
    mean_no_res = sum(no_res) / len(no_res)
    mean_res = sum(res) / len(res)
    assert mean_no_res > 0.01
    assert mean_res > 0.7 * mean_no_res  # recovery collapses vs iid's 15.2% -> 0.0%


def test_probes_recover_breaker_lockin():
    """Seed 6 is a measured catastrophic seed: a burst at run start trips the
    cumulative-ETA breaker on three tools, and without half-open probes the
    breaker never closes again -> ~100% blast radius. Probes must recover it."""
    kwargs = {"tasks": 200, "fanout": 8, "error_rate": 0.02, "seed": 6,
              "faults": [BurstErrorFault(rate=0.02, burst_len=16)]}
    locked = run_workload(resilience=ResilienceConfig.enabled(), **kwargs).blast_radius
    probed = run_workload(resilience=ResilienceConfig.enabled(probe_interval=8),
                          **kwargs).blast_radius
    assert locked > 0.9
    assert probed < 0.2


# ------------------------------------------------------------------- YAML parity

def test_yaml_registry_has_correlated_faults(tmp_path):
    from mcp_chaos.config import load_fault_plan
    cfg = tmp_path / "plan.yaml"
    cfg.write_text(
        "seed: 9\n"
        "faults:\n"
        "  - type: burst_error\n"
        "    rate: 0.02\n"
        "    burst_len: 16\n"
        "  - type: server_degradation\n"
        "    tools: [get_logs]\n"
        "    episode_rate: 0.05\n"
        "    episode_len: 10\n"
    )
    plan = load_fault_plan(str(cfg))
    assert len(plan.faults) == 2
    assert isinstance(plan.faults[0], BurstErrorFault)
    assert isinstance(plan.faults[1], ServerDegradationFault)
