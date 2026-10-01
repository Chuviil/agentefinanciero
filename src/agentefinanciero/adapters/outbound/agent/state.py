from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from agentefinanciero.domain.models import Budget, StepMetric, StopReason
from agentefinanciero.domain.policies import BreakerState


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    budget: Budget
    steps: list[StepMetric]
    breaker: BreakerState
    stop_reason: StopReason | None
    started_at: float
    answer: str
    warning: str | None
