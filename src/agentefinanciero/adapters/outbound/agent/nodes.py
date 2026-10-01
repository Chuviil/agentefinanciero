import logging
import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from agentefinanciero.adapters.outbound.agent.partial import build_partial, is_error_message
from agentefinanciero.adapters.outbound.agent.state import AgentState
from agentefinanciero.application.ports.outbound import MetricsPort
from agentefinanciero.domain.models import AnalysisContext, StepMetric, StopReason
from agentefinanciero.domain.policies import CircuitBreaker, ExecutionGuard
from agentefinanciero.domain.pricing import TokenPricing

logger = logging.getLogger(__name__)


def make_guard_node(guard: ExecutionGuard):
    async def guard_node(state: AgentState) -> dict[str, Any]:
        reason = guard.evaluate(
            state["budget"],
            steps_done=len(state["steps"]),
            consecutive_errors=state["breaker"].consecutive_errors,
        )
        return {"stop_reason": reason}

    return guard_node


def make_agent_node(
    llm: BaseChatModel,
    pricing: TokenPricing,
    breaker: CircuitBreaker,
    metrics: MetricsPort,
):
    async def agent_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        context: AnalysisContext = config["configurable"]["context"]
        budget = state["budget"]
        response: AIMessage = await llm.ainvoke(
            state["messages"], max_completion_tokens=budget.remaining_tokens
        )

        usage = response.usage_metadata
        if usage is None:
            logger.warning("Respuesta del LLM sin usage_metadata (request_id=%s)", context.request_id)
        input_tokens = usage["input_tokens"] if usage else 0
        output_tokens = usage["output_tokens"] if usage else 0
        cached = (usage.get("input_token_details") or {}).get("cache_read", 0) if usage else 0
        cost = pricing.cost(input_tokens, output_tokens, cached)
        budget = budget.charge(cost, input_tokens + output_tokens)

        stop_reason: StopReason | None = None
        breaker_state = state["breaker"]
        if _truncated_while_reasoning(response):
            stop_reason = StopReason.TOKEN_BUDGET_EXCEEDED
        elif response.tool_calls:
            signatures = [breaker.signature(c["name"], c["args"]) for c in response.tool_calls]
            breaker_state, loop = breaker.register_calls(breaker_state, signatures)
            if loop:
                stop_reason = StopReason.LOOP_DETECTED

        metric = StepMetric(
            step_number=len(state["steps"]) + 1,
            tool_called=[c["name"] for c in response.tool_calls] or None,
            tokens_used=input_tokens + output_tokens,
            cumulative_tokens=budget.tokens_used,
            step_cost_usd=cost,
            cumulative_cost=budget.spent_usd,
            remaining_budget_usd=budget.remaining_usd,
            elapsed_time=time.monotonic() - state["started_at"],
        )
        await metrics.record_step(context, metric)

        return {
            "messages": [response],
            "budget": budget,
            "steps": [*state["steps"], metric],
            "breaker": breaker_state,
            "stop_reason": stop_reason,
        }

    return agent_node


def make_tool_caller_node(tool_node: ToolNode):
    async def tool_caller_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        update = await tool_node.ainvoke(state, config)
        breaker_state = state["breaker"]
        for message in update["messages"]:
            breaker_state = CircuitBreaker.register_result(breaker_state, is_error_message(message))
        return {"messages": update["messages"], "breaker": breaker_state}

    return tool_caller_node


async def finalize_partial_node(state: AgentState) -> dict[str, Any]:
    answer, warning = build_partial(state["messages"], state["stop_reason"])
    return {"answer": answer, "warning": warning}


def _truncated_while_reasoning(response: AIMessage) -> bool:
    finish_reason = response.response_metadata.get("finish_reason")
    return finish_reason == "length" and not response.content and not response.tool_calls
