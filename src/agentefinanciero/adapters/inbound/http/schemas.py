from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from agentefinanciero.domain.models import AnalysisRequest, AnalysisResult, Budget

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnalysisQueryRequest(BaseModel):
    analyst_id: NonEmptyStr
    session_id: NonEmptyStr
    query: NonEmptyStr
    max_budget_usd: float = Field(gt=0)

    def to_domain(self) -> AnalysisRequest:
        return AnalysisRequest(
            analyst_id=self.analyst_id,
            session_id=self.session_id,
            query=self.query,
            max_budget_usd=self.max_budget_usd,
        )


class BudgetSchema(BaseModel):
    max_budget_usd: float
    spent_usd: float
    remaining_usd: float
    max_tokens: int
    tokens_used: int
    remaining_tokens: int

    @classmethod
    def from_domain(cls, budget: Budget) -> "BudgetSchema":
        return cls(
            max_budget_usd=budget.max_usd,
            spent_usd=budget.spent_usd,
            remaining_usd=budget.remaining_usd,
            max_tokens=budget.max_tokens,
            tokens_used=budget.tokens_used,
            remaining_tokens=budget.remaining_tokens,
        )


class StepMetricSchema(BaseModel):
    step_number: int
    tool_called: list[str] | None
    tokens_used: int
    cumulative_tokens: int
    step_cost_usd: float
    cumulative_cost: float
    remaining_budget_usd: float
    elapsed_time: float


class AnalysisQueryResponse(BaseModel):
    status: Literal["completed", "partial"]
    answer: str
    warning: str | None
    stop_reason: Literal[
        "completed",
        "budget_exceeded",
        "token_budget_exceeded",
        "max_steps_reached",
        "timeout",
        "loop_detected",
        "tool_errors",
    ]
    budget: BudgetSchema
    steps: list[StepMetricSchema]
    elapsed_time_s: float

    @classmethod
    def from_domain(cls, result: AnalysisResult) -> "AnalysisQueryResponse":
        return cls(
            status=result.status.value,
            answer=result.answer,
            warning=result.warning,
            stop_reason=result.stop_reason.value,
            budget=BudgetSchema.from_domain(result.budget),
            steps=[StepMetricSchema(**asdict(step)) for step in result.steps],
            elapsed_time_s=result.elapsed_time_s,
        )
