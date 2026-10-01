from fastapi import APIRouter, Depends, Request

from agentefinanciero.adapters.inbound.http.schemas import (
    AnalysisQueryRequest,
    AnalysisQueryResponse,
)
from agentefinanciero.application.ports.inbound import AnalyzeQueryUseCase

router = APIRouter(prefix="/api/v1/analysis")


def get_use_case(request: Request) -> AnalyzeQueryUseCase:
    return request.app.state.use_case


@router.post("/query", response_model=AnalysisQueryResponse)
async def query(
    body: AnalysisQueryRequest,
    use_case: AnalyzeQueryUseCase = Depends(get_use_case),
) -> AnalysisQueryResponse:
    result = await use_case.execute(body.to_domain())
    return AnalysisQueryResponse.from_domain(result)
