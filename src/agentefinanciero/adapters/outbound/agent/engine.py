import asyncio
import logging
import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.errors import GraphRecursionError

from agentefinanciero.adapters.outbound.agent.graph import build_graph
from agentefinanciero.adapters.outbound.agent.partial import build_partial
from agentefinanciero.adapters.outbound.agent.tools import build_tools
from agentefinanciero.application.ports.outbound import FinancialDataPort, MetricsPort
from agentefinanciero.domain.models import (
    AnalysisContext,
    AnalysisResult,
    AnalysisStatus,
    Budget,
    ExecutionLimits,
    StopReason,
)
from agentefinanciero.domain.policies import BreakerState
from agentefinanciero.domain.pricing import TokenPricing

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un asistente de análisis financiero para analistas de un banco. "
    "Usa las herramientas para obtener datos y calcular ratios; no inventes cifras. "
    "Responde en español, de forma concisa."
)


def build_checkpointer() -> InMemorySaver:
    """Checkpointer en memoria que permite deserializar los tipos de dominio guardados en el estado."""
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("agentefinanciero.domain.models", "Budget"),
            ("agentefinanciero.domain.models", "StepMetric"),
            ("agentefinanciero.domain.models", "StopReason"),
            ("agentefinanciero.domain.policies", "BreakerState"),
        ]
    )
    return InMemorySaver(serde=serde)


class LangGraphAnalysisEngine:
    def __init__(
        self,
        chat_model: BaseChatModel,
        financial_data: FinancialDataPort,
        pricing: TokenPricing,
        metrics: MetricsPort,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self._chat_model = chat_model
        self._tools = build_tools(financial_data)
        self._pricing = pricing
        self._metrics = metrics
        self._checkpointer = checkpointer or build_checkpointer()

    async def run(
        self,
        query: str,
        context: AnalysisContext,
        budget: Budget,
        limits: ExecutionLimits,
    ) -> AnalysisResult:
        graph = build_graph(
            self._chat_model, self._tools, self._pricing, limits, self._metrics, self._checkpointer
        )
        thread_id = f"{context.session_id}:{context.request_id}"
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id, "context": context},
            "recursion_limit": limits.recursion_limit,
            "metadata": {
                "analyst_id": context.analyst_id,
                "session_id": context.session_id,
                "request_id": context.request_id,
            },
            "tags": [
                f"analyst:{context.analyst_id}",
                f"session:{context.session_id}",
                f"request:{context.request_id}",
            ],
        }
        started_at = time.monotonic()
        initial: dict[str, Any] = {
            "messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(query)],
            "budget": budget,
            "steps": [],
            "breaker": BreakerState(),
            "stop_reason": None,
            "started_at": started_at,
        }

        forced_reason: StopReason | None = None
        try:
            values = await asyncio.wait_for(
                graph.ainvoke(initial, config), timeout=limits.timeout_global_s
            )
        except TimeoutError:
            forced_reason = StopReason.TIMEOUT
            logger.warning("Timeout global; stop_reason=%s thread_id=%s", forced_reason, thread_id)
            values = (await graph.aget_state(config)).values
        except GraphRecursionError:
            forced_reason = StopReason.MAX_STEPS_REACHED
            logger.warning("GraphRecursionError; stop_reason=%s thread_id=%s", forced_reason, thread_id)
            values = (await graph.aget_state(config)).values
        finally:
            await self._checkpointer.adelete_thread(thread_id)

        elapsed = time.monotonic() - started_at
        messages = values.get("messages", initial["messages"])
        steps = values.get("steps", [])
        final_budget = values.get("budget", budget)

        if forced_reason is not None:
            answer, warning = build_partial(messages, forced_reason)
            reason = forced_reason
        else:
            reason = values.get("stop_reason") or StopReason.COMPLETED
            if reason is StopReason.COMPLETED:
                answer, warning = _final_text(messages), None
            else:
                answer, warning = values["answer"], values["warning"]

        return AnalysisResult(
            status=(
                AnalysisStatus.COMPLETED if reason is StopReason.COMPLETED else AnalysisStatus.PARTIAL
            ),
            answer=answer,
            warning=warning,
            stop_reason=reason,
            budget=final_budget,
            steps=steps,
            elapsed_time_s=elapsed,
        )


def _final_text(messages: list) -> str:
    last = messages[-1]
    if not isinstance(last, AIMessage):
        return ""
    if isinstance(last.content, str):
        return last.content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block) for block in last.content
    )
