import io
import json
import logging

from agentefinanciero.adapters.outbound.data.mock_financial_data import MockFinancialDataAdapter
from agentefinanciero.adapters.outbound.metrics.composite import CompositeMetricsAdapter
from agentefinanciero.adapters.outbound.metrics.json_logger import JsonLoggerMetrics
from agentefinanciero.adapters.outbound.metrics.langsmith_metrics import LangSmithMetrics
from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
    Budget,
    StepMetric,
    StopReason,
)

CONTEXT = AnalysisContext("A01", "S001", "req-1")
STEP = StepMetric(1, ["search_financial_data"], 500, 500, 0.001, 0.001, 0.499, 2.1)
RESULT = AnalysisResult(
    AnalysisStatus.PARTIAL,
    "parcial",
    "Presupuesto agotado",
    StopReason.BUDGET_EXCEEDED,
    Budget(0.5, 10_000, 0.5, 500),
    [STEP],
    3.2,
)


async def test_mock_returns_deterministic_data():
    adapter = MockFinancialDataAdapter(delay_s=0)
    first = await adapter.search("Revenue", " 2024 ")
    assert first == await adapter.search("revenue", "2024")
    assert first["value"] == 1500.0


async def test_mock_unknown_metric_or_period_returns_error_without_raising():
    adapter = MockFinancialDataAdapter(delay_s=0)
    assert "error" in await adapter.search("unicornios", "2024")
    assert "error" in await adapter.search("revenue", "1999")


async def test_mock_waits_asynchronously(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    await MockFinancialDataAdapter().search("revenue", "2024")
    assert slept == [2.0]


async def test_json_logger_emits_step_and_completion_events():
    stream = io.StringIO()
    metrics = JsonLoggerMetrics(stream)

    await metrics.record_step(CONTEXT, STEP)
    await metrics.record_completion(CONTEXT, RESULT)

    step, done = (json.loads(line) for line in stream.getvalue().splitlines())
    assert step["event"] == "analysis_step"
    assert step["request_id"] == "req-1" and step["analyst_id"] == "A01"
    assert {"step_number", "tool_called", "tokens_used", "cumulative_tokens", "step_cost_usd",
            "cumulative_cost", "remaining_budget_usd", "elapsed_time"} <= step.keys()
    assert done["event"] == "analysis_completed"
    assert done["stop_reason"] == "budget_exceeded" and done["steps"] == 1


async def test_langsmith_metrics_is_noop_without_active_run():
    metrics = LangSmithMetrics()
    await metrics.record_step(CONTEXT, STEP)
    await metrics.record_completion(CONTEXT, RESULT)


class ExplodingMetrics:
    async def record_step(self, context, metric):
        raise RuntimeError("langsmith caído")

    async def record_completion(self, context, result):
        raise RuntimeError("langsmith caído")


async def test_composite_keeps_json_log_when_secondary_fails(caplog):
    stream = io.StringIO()
    composite = CompositeMetricsAdapter(JsonLoggerMetrics(stream), ExplodingMetrics())

    with caplog.at_level(logging.ERROR):
        await composite.record_step(CONTEXT, STEP)
        await composite.record_completion(CONTEXT, RESULT)

    assert len(stream.getvalue().splitlines()) == 2
    assert "ExplodingMetrics" in caplog.text


async def test_composite_continues_to_later_sinks_after_failure():
    stream = io.StringIO()
    composite = CompositeMetricsAdapter(ExplodingMetrics(), JsonLoggerMetrics(stream))
    await composite.record_step(CONTEXT, STEP)
    assert len(stream.getvalue().splitlines()) == 1
