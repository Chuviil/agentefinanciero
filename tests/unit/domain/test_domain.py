import pytest

from agentefinanciero.domain.models import Budget, ExecutionLimits, StopReason
from agentefinanciero.domain.policies import BreakerState, CircuitBreaker, ExecutionGuard
from agentefinanciero.domain.pricing import TokenPricing
from agentefinanciero.domain.ratio import calculate_ratio

PRICING = TokenPricing(input_per_mtok=0.25, cached_input_per_mtok=0.025, output_per_mtok=2.0)


def test_pricing_without_cache():
    assert PRICING.cost(1_000_000, 1_000_000) == pytest.approx(2.25)


def test_pricing_with_cached_tokens():
    # 600k normales + 400k cacheados + 0 salida
    assert PRICING.cost(1_000_000, 0, cached_tokens=400_000) == pytest.approx(0.15 + 0.01)


def test_pricing_cached_cannot_exceed_input():
    assert PRICING.cost(100, 0, cached_tokens=500) == PRICING.cost(100, 0, cached_tokens=100)


def test_ratio():
    assert calculate_ratio(10, 4) == {"result": 2.5}


def test_ratio_division_by_zero():
    assert calculate_ratio(10, 0) == {"error": "division by zero"}


def test_budget_charge_and_remaining():
    budget = Budget(max_usd=0.5, max_tokens=10_000).charge(0.1, 3_000)
    assert budget.remaining_usd == pytest.approx(0.4)
    assert budget.remaining_tokens == 7_000
    assert budget.can_afford(0.4, 7_000)
    assert not budget.can_afford(0.41, 100)
    assert not budget.can_afford(0.01, 7_001)


def test_budget_remaining_never_negative():
    budget = Budget(max_usd=0.01, max_tokens=100).charge(1.0, 500)
    assert budget.remaining_usd == 0.0
    assert budget.remaining_tokens == 0


def make_guard(**overrides) -> ExecutionGuard:
    return ExecutionGuard(ExecutionLimits(**overrides), PRICING)


def test_guard_allows_within_limits():
    assert make_guard().evaluate(Budget(0.5, 10_000), steps_done=0, consecutive_errors=0) is None


def test_guard_budget_usd():
    # 2000 tokens a precio de salida = 0.004 USD
    assert (
        make_guard().evaluate(Budget(0.0001, 10_000), 0, 0) is StopReason.BUDGET_EXCEEDED
    )


def test_guard_tokens():
    budget = Budget(0.5, 10_000).charge(0.0, 8_500)
    assert make_guard().evaluate(budget, 1, 0) is StopReason.TOKEN_BUDGET_EXCEEDED


def test_guard_max_steps():
    assert make_guard().evaluate(Budget(0.5, 10_000), 8, 0) is StopReason.MAX_STEPS_REACHED


def test_guard_consecutive_errors():
    assert make_guard().evaluate(Budget(0.5, 10_000), 1, 3) is StopReason.TOOL_ERRORS


def test_guard_evaluation_order():
    exhausted = Budget(0.0, 10_000).charge(0.0, 10_000)
    guard = make_guard()
    assert guard.evaluate(exhausted, 8, 3) is StopReason.TOOL_ERRORS
    assert guard.evaluate(exhausted, 8, 0) is StopReason.BUDGET_EXCEEDED
    assert guard.evaluate(Budget(0.5, 10_000).charge(0.0, 10_000), 8, 0) is (
        StopReason.TOKEN_BUDGET_EXCEEDED
    )


def test_signature_normalizes_args():
    a = CircuitBreaker.signature("search_financial_data", {"metric": " Revenue ", "period": "2024"})
    b = CircuitBreaker.signature("search_financial_data", {"period": "2024", "metric": "revenue"})
    assert a == b
    assert CircuitBreaker.signature("calculate_ratio", {"numerator": 1.0}) == (
        CircuitBreaker.signature("calculate_ratio", {"numerator": 1})
    )


def test_breaker_detects_repeated_signature():
    breaker = CircuitBreaker(max_repeats=2)
    sig = CircuitBreaker.signature("search_financial_data", {"metric": "revenue", "period": "2024"})
    state, loop = breaker.register_calls(BreakerState(), [sig])
    assert not loop
    _, loop = breaker.register_calls(state, [sig])
    assert loop


def test_breaker_different_args_are_not_a_loop():
    breaker = CircuitBreaker(max_repeats=2)
    s1 = CircuitBreaker.signature("search_financial_data", {"metric": "revenue", "period": "2023"})
    s2 = CircuitBreaker.signature("search_financial_data", {"metric": "revenue", "period": "2024"})
    state, _ = breaker.register_calls(BreakerState(), [s1])
    _, loop = breaker.register_calls(state, [s2])
    assert not loop


def test_breaker_consecutive_errors_reset_on_success():
    state = BreakerState()
    state = CircuitBreaker.register_result(state, is_error=True)
    state = CircuitBreaker.register_result(state, is_error=True)
    assert state.consecutive_errors == 2
    assert CircuitBreaker.register_result(state, is_error=False).consecutive_errors == 0


def test_breaker_state_is_immutable_between_calls():
    breaker = CircuitBreaker(max_repeats=3)
    original = BreakerState()
    breaker.register_calls(original, ["x"])
    assert dict(original.call_counts) == {}
