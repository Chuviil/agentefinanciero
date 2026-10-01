from agentefinanciero.application.services.run_analysis import RunAnalysisService
from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisRequest,
    AnalysisResult,
    AnalysisStatus,
    Budget,
    ExecutionLimits,
    StepMetric,
    StopReason,
)

REQUEST = AnalysisRequest(
    analyst_id="A01", session_id="S001", query="margen neto 2024", max_budget_usd=0.5
)


class FakeEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, AnalysisContext, Budget, ExecutionLimits]] = []

    async def run(self, query, context, budget, limits) -> AnalysisResult:
        self.calls.append((query, context, budget, limits))
        return AnalysisResult(
            status=AnalysisStatus.COMPLETED,
            answer="ok",
            warning=None,
            stop_reason=StopReason.COMPLETED,
            budget=budget,
        )


class FakeMetrics:
    def __init__(self) -> None:
        self.steps: list[StepMetric] = []
        self.completions: list[tuple[AnalysisContext, AnalysisResult]] = []

    async def record_step(self, context, metric) -> None:
        self.steps.append(metric)

    async def record_completion(self, context, result) -> None:
        self.completions.append((context, result))


async def test_builds_budget_and_context_for_engine():
    engine, metrics = FakeEngine(), FakeMetrics()
    limits = ExecutionLimits(max_tokens_budget=5_000)
    service = RunAnalysisService(engine, metrics, limits, request_id_factory=lambda: "req-1")

    await service.execute(REQUEST)

    query, context, budget, passed_limits = engine.calls[0]
    assert query == "margen neto 2024"
    assert context == AnalysisContext("A01", "S001", "req-1")
    assert budget == Budget(max_usd=0.5, max_tokens=5_000)
    assert passed_limits is limits


async def test_records_completion_and_returns_engine_result():
    engine, metrics = FakeEngine(), FakeMetrics()
    service = RunAnalysisService(engine, metrics, ExecutionLimits(), lambda: "req-1")

    result = await service.execute(REQUEST)

    assert result.status is AnalysisStatus.COMPLETED
    assert metrics.completions == [(AnalysisContext("A01", "S001", "req-1"), result)]


async def test_each_request_gets_its_own_request_id():
    engine, metrics = FakeEngine(), FakeMetrics()
    service = RunAnalysisService(engine, metrics, ExecutionLimits())

    await service.execute(REQUEST)
    await service.execute(REQUEST)

    ids = {call[1].request_id for call in engine.calls}
    assert len(ids) == 2
