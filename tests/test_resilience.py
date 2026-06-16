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
