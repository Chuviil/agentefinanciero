from typing import Protocol

from agentefinanciero.domain.models import AnalysisRequest, AnalysisResult


class AnalyzeQueryUseCase(Protocol):
    async def execute(self, request: AnalysisRequest) -> AnalysisResult: ...
