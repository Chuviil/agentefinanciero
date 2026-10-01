import uuid
from collections.abc import Callable

from agentefinanciero.application.ports.outbound import AnalysisEnginePort, MetricsPort
from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisRequest,
    AnalysisResult,
    Budget,
    ExecutionLimits,
)


class RunAnalysisService:
    def __init__(
        self,
        engine: AnalysisEnginePort,
        metrics: MetricsPort,
        limits: ExecutionLimits,
        request_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._engine = engine
        self._metrics = metrics
        self._limits = limits
        self._request_id_factory = request_id_factory

    async def execute(self, request: AnalysisRequest) -> AnalysisResult:
        context = AnalysisContext(
            analyst_id=request.analyst_id,
            session_id=request.session_id,
            request_id=self._request_id_factory(),
        )
        budget = Budget(max_usd=request.max_budget_usd, max_tokens=self._limits.max_tokens_budget)
        result = await self._engine.run(request.query, context, budget, self._limits)
        await self._metrics.record_completion(context, result)
        return result
