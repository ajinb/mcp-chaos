# Contributing

Thanks for your interest in mcp-chaos.

- Run `pip install -e ".[dev]"`, then `pytest -q` and `ruff check src tests` before opening a PR.
- New faults go in `src/mcp_chaos/faults.py` as small, pure, seeded transformers with a unit test in `tests/test_faults.py`.
- New SLIs go in `src/mcp_chaos/metrics.py` with a `MetricsCollector` test in `tests/test_metrics.py`.
- Keep the core (`faults`, `interceptor`, `metrics`, `types`) transport-agnostic; transport specifics live under `proxy/`.
- Faults must stamp `result.injected` so metrics can separate injected faults from real upstream failures.
