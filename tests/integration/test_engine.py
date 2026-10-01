from dataclasses import asdict

import pytest

from agentefinanciero.adapters.outbound.agent.engine import (
    LangGraphAnalysisEngine,
    build_checkpointer,
)
from agentefinanciero.adapters.outbound.agent.tools import build_tools
from agentefinanciero.adapters.outbound.data.mock_financial_data import MockFinancialDataAdapter
from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisStatus,
    Budget,
    ExecutionLimits,
    StepMetric,
    StopReason,
)
from agentefinanciero.domain.pricing import TokenPricing
from tests.fakes import FakeChatModel, ai

PRICING = TokenPricing(input_per_mtok=0.25, cached_input_per_mtok=0.025, output_per_mtok=2.0)
CONTEXT = AnalysisContext("A01", "S001", "req-1")
STEP_FIELDS = {f for f in StepMetric.__dataclass_fields__}
SEARCH = "search_financial_data"
METRICS = ["revenue", "net_income", "total_assets", "total_liabilities", "equity", "operating_expenses"]


class CountingData(MockFinancialDataAdapter):
    def __init__(self, delay_s: float = 0.0) -> None:
        super().__init__(delay_s)
        self.calls = 0

    async def search(self, metric, period):
        self.calls += 1
        return await super().search(metric, period)


class RecordingMetrics:
    def __init__(self) -> None:
        self.steps: list[StepMetric] = []

    async def record_step(self, context, metric) -> None:
        self.steps.append(metric)

    async def record_completion(self, context, result) -> None: ...


def search(metric: str, period: str = "2024"):
    return (SEARCH, {"metric": metric, "period": period})


def distinct_calls(n: int, **usage):
    """n respuestas con tool_calls distintos (no disparan el circuit breaker)."""
    combos = [(m, p) for p in ("2022", "2023", "2024") for m in METRICS]
    return [ai(tool_calls=[search(m, p)], **usage) for m, p in combos[:n]]


def make_engine(script, *, delay_s=0.0, data=None, saver=None):
    model = FakeChatModel(script=script, delay_s=delay_s)
    data = data or CountingData()
    metrics = RecordingMetrics()
    saver = saver or build_checkpointer()
    engine = LangGraphAnalysisEngine(model, data, PRICING, metrics, saver)
    return engine, model, data, metrics, saver


async def run(engine, budget_usd=0.5, **limits):
    limits_obj = ExecutionLimits(**limits)
    budget = Budget(max_usd=budget_usd, max_tokens=limits_obj.max_tokens_budget)
    return await engine.run("¿Cuál fue el revenue 2024?", CONTEXT, budget, limits_obj)


async def test_completed_with_tool_then_final_answer():
    engine, _, data, metrics, _ = make_engine(
        [ai(tool_calls=[search("revenue")]), ai("El revenue 2024 fue 1500 millones.")]
    )

    result = await run(engine)

    assert result.status is AnalysisStatus.COMPLETED
    assert result.stop_reason is StopReason.COMPLETED
    assert result.warning is None
    assert "1500" in result.answer
    assert data.calls == 1
    assert [s.step_number for s in result.steps] == [1, 2]
    assert result.steps[0].tool_called == [SEARCH]
    assert result.steps[1].tool_called is None
    assert metrics.steps == result.steps


async def test_every_step_has_all_step_metric_fields_and_consistent_totals():
    engine, *_ = make_engine(
        [ai(tool_calls=[search("revenue")], input_tokens=1000, output_tokens=500), ai("ok")]
    )

    result = await run(engine)

    first, second = result.steps
    assert set(asdict(first)) == STEP_FIELDS
    assert first.tokens_used == 1500
    assert first.step_cost_usd == pytest.approx(PRICING.cost(1000, 500))
    assert second.cumulative_tokens == first.tokens_used + second.tokens_used
    assert second.cumulative_cost == pytest.approx(first.step_cost_usd + second.step_cost_usd)
    assert second.remaining_budget_usd == pytest.approx(0.5 - second.cumulative_cost)
    assert second.elapsed_time >= first.elapsed_time
    assert result.budget.tokens_used == second.cumulative_tokens


async def test_max_completion_tokens_is_bounded_to_remaining_budget():
    engine, model, *_ = make_engine(
        [ai(tool_calls=[search("revenue")], input_tokens=1000, output_tokens=500), ai("ok")]
    )

    await run(engine)

    assert [c["max_completion_tokens"] for c in model.calls] == [10_000, 8_500]


async def test_loop_detected_does_not_execute_repeated_tool():
    engine, model, data, _, _ = make_engine([ai(tool_calls=[search("revenue")])])

    result = await run(engine)

    assert result.status is AnalysisStatus.PARTIAL
    assert result.stop_reason is StopReason.LOOP_DETECTED
    assert result.warning
    assert data.calls == 1
    assert len(model.calls) == 2
    assert "1500" in result.answer


async def test_very_low_usd_budget_stops_before_calling_llm():
    engine, model, *_ = make_engine([ai("no debería llamarse")])

    result = await run(engine, budget_usd=0.0001)

    assert result.stop_reason is StopReason.BUDGET_EXCEEDED
    assert result.status is AnalysisStatus.PARTIAL
    assert model.calls == []
    assert result.steps == []
    assert result.warning


async def test_usd_budget_exhausted_after_a_costly_call():
    # 2500 tokens de salida = 0.005 USD; quedan 0.001 < 0.004 estimados para la siguiente llamada
    engine, model, *_ = make_engine(distinct_calls(4, input_tokens=0, output_tokens=2500))

    result = await run(engine, budget_usd=0.006)

    assert result.stop_reason is StopReason.BUDGET_EXCEEDED
    assert len(model.calls) == 1
    assert "1200" in result.answer  # revenue 2022, primera combinación de distinct_calls


async def test_token_budget_exceeded():
    engine, model, *_ = make_engine(distinct_calls(5, input_tokens=3000, output_tokens=1500))

    result = await run(engine)

    # 4500 por llamada: tras dos llamadas quedan 1000 < 2000 estimados
    assert result.stop_reason is StopReason.TOKEN_BUDGET_EXCEEDED
    assert len(model.calls) == 2
    assert result.budget.tokens_used == 9_000


async def test_empty_response_truncated_by_length_is_token_budget_exceeded():
    engine, *_ = make_engine([ai("", finish_reason="length")])

    result = await run(engine)

    assert result.stop_reason is StopReason.TOKEN_BUDGET_EXCEEDED
    assert result.status is AnalysisStatus.PARTIAL
    assert len(result.steps) == 1


async def test_more_than_eight_steps_reaches_max_steps():
    engine, model, *_ = make_engine(distinct_calls(12))

    result = await run(engine)

    assert result.stop_reason is StopReason.MAX_STEPS_REACHED
    assert len(result.steps) == 8
    assert len(model.calls) == 8


async def test_consecutive_tool_errors_stop_execution():
    script = [ai(tool_calls=[search(f"inexistente{i}")]) for i in range(6)]
    engine, model, *_ = make_engine(script)

    result = await run(engine)

    assert result.stop_reason is StopReason.TOOL_ERRORS
    assert len(model.calls) == 3
    assert "[error]" in result.answer


async def test_ratio_with_zero_denominator_is_an_error_for_the_breaker():
    script = [ai(tool_calls=[("calculate_ratio", {"numerator": i, "denominator": 0})]) for i in range(1, 6)]
    engine, *_ = make_engine(script)

    result = await run(engine)

    assert result.stop_reason is StopReason.TOOL_ERRORS
    assert "division by zero" in result.answer


async def test_calculate_ratio_tool_returns_error_on_zero_denominator():
    _, calculate_ratio = build_tools(MockFinancialDataAdapter(0))
    assert await calculate_ratio.ainvoke({"numerator": 10, "denominator": 0}) == {
        "error": "division by zero"
    }
    assert await calculate_ratio.ainvoke({"numerator": 10, "denominator": 4}) == {"result": 2.5}


async def test_timeout_returns_partial_with_data_already_obtained():
    engine, *_ = make_engine(
        distinct_calls(5), data=CountingData(delay_s=0.4)
    )

    result = await run(engine, timeout_global_s=0.6)

    assert result.stop_reason is StopReason.TIMEOUT
    assert result.status is AnalysisStatus.PARTIAL
    assert "1200" in result.answer  # revenue 2022, obtenido antes del corte
    assert result.elapsed_time_s < 1.5


async def test_graph_recursion_error_returns_partial(monkeypatch):
    monkeypatch.setattr(ExecutionLimits, "recursion_limit", property(lambda self: 5))
    engine, *_ = make_engine(distinct_calls(8))

    result = await run(engine)

    assert result.stop_reason is StopReason.MAX_STEPS_REACHED
    assert result.status is AnalysisStatus.PARTIAL
    assert result.steps


async def test_checkpoint_is_released_after_each_request():
    saver = build_checkpointer()
    for engine_script in ([ai("hola")], distinct_calls(12)):
        engine, *_ = make_engine(engine_script, saver=saver)
        await run(engine)
    assert not saver.storage
