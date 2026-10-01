import pytest
from pydantic import ValidationError

from agentefinanciero.config.settings import Settings

PRICES = {
    "price_input_per_mtok": 0.25,
    "price_cached_input_per_mtok": 0.025,
    "price_output_per_mtok": 2.0,
}


def test_prices_are_required():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_match_claude_md():
    limits = Settings(_env_file=None, **PRICES).to_limits()
    assert (limits.max_steps, limits.max_tokens_budget, limits.timeout_global_s) == (8, 10_000, 45.0)
    assert (limits.cb_max_repeats, limits.cb_max_consecutive_errors) == (2, 3)
    assert limits.recursion_limit == 27


def test_env_overrides_and_empty_values_are_ignored(monkeypatch):
    monkeypatch.setenv("MAX_STEPS", "4")
    monkeypatch.setenv("RATE_LIMIT_RPS", "")
    settings = Settings(_env_file=None, **PRICES)
    assert settings.max_steps == 4
    assert settings.rate_limit_rps is None
    assert settings.to_limits().recursion_limit == 15


def test_to_pricing():
    assert Settings(_env_file=None, **PRICES).to_pricing().output_per_mtok == 2.0
