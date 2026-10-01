from typing import Any, Protocol

from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisResult,
    Budget,
    ExecutionLimits,
    StepMetric,
)


class AnalysisEnginePort(Protocol):
    async def run(
        self,
        query: str,
        context: AnalysisContext,
        budget: Budget,
        limits: ExecutionLimits,
    ) -> AnalysisResult: ...


class FinancialDataPort(Protocol):
    async def search(self, metric: str, period: str) -> dict[str, Any]: ...


class MetricsPort(Protocol):
    async def record_step(self, context: AnalysisContext, metric: StepMetric) -> None: ...

    async def record_completion(self, context: AnalysisContext, result: AnalysisResult) -> None: ...
