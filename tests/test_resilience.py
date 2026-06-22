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
