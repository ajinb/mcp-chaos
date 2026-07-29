from mcp_chaos.resilience import ResilienceConfig


def test_disabled_config_has_no_retries():
    cfg = ResilienceConfig.disabled()
    assert cfg.retry_budget == 0
    assert cfg.graceful_degradation is False


def test_enabled_config_defaults():
    cfg = ResilienceConfig.enabled()
    assert cfg.retry_budget >= 1
    assert cfg.graceful_degradation is True
    assert cfg.eta_breaker_threshold < 1.0


def test_breaker_trips_on_always_erroring_tool():
    from mcp_chaos.resilience import CircuitBreaker
    b = CircuitBreaker(threshold=0.5)
    for _ in range(4):
        b.observe("bad", responded=False, correct=False)
    assert b.is_open("bad") is True


def test_breaker_stays_closed_for_healthy_tool():
    from mcp_chaos.resilience import CircuitBreaker
    b = CircuitBreaker(threshold=0.5)
    for _ in range(10):
        b.observe("good", responded=True, correct=True)
    assert b.is_open("good") is False


def _tripped_breaker(probe_interval):
    from mcp_chaos.resilience import CircuitBreaker
    b = CircuitBreaker(threshold=0.5, probe_interval=probe_interval)
    for _ in range(4):
        b.observe("bad", responded=False, correct=False)
    assert b.is_open("bad") is True
    return b


def test_breaker_without_probes_never_reopens():
    b = _tripped_breaker(probe_interval=0)
    for _ in range(10):
        assert b.should_probe("bad") is False
    assert b.is_open("bad") is True


def test_breaker_probe_closes_after_successful_probe():
    b = _tripped_breaker(probe_interval=3)
    # Every third skipped call lets one half-open probe through.
    assert b.should_probe("bad") is False
    assert b.should_probe("bad") is False
    assert b.should_probe("bad") is True
    b.observe("bad", responded=True, correct=True)  # probe succeeded upstream
    assert b.is_open("bad") is False


def test_breaker_failed_probe_stays_open():
    b = _tripped_breaker(probe_interval=3)
    for _ in range(2):
        assert b.should_probe("bad") is False
    assert b.should_probe("bad") is True
    b.observe("bad", responded=False, correct=False)  # still degraded
    assert b.is_open("bad") is True
    # The probe cadence restarts after a failed probe.
    for _ in range(2):
        assert b.should_probe("bad") is False
    assert b.should_probe("bad") is True
