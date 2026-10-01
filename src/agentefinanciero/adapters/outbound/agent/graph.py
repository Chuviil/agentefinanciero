from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agentefinanciero.adapters.outbound.agent.nodes import (
    finalize_partial_node,
    make_agent_node,
    make_guard_node,
    make_tool_caller_node,
)
from agentefinanciero.adapters.outbound.agent.routing import route_after_agent, route_after_guard
from agentefinanciero.adapters.outbound.agent.state import AgentState
from agentefinanciero.application.ports.outbound import MetricsPort
from agentefinanciero.domain.models import ExecutionLimits
from agentefinanciero.domain.policies import CircuitBreaker, ExecutionGuard
from agentefinanciero.domain.pricing import TokenPricing


def build_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    pricing: TokenPricing,
    limits: ExecutionLimits,
    metrics: MetricsPort,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("guard", make_guard_node(ExecutionGuard(limits, pricing)))
    builder.add_node(
        "agent",
        make_agent_node(
            llm.bind_tools(tools), pricing, CircuitBreaker(limits.cb_max_repeats), metrics
        ),
    )
    builder.add_node(
        "tool_caller", make_tool_caller_node(ToolNode(tools, handle_tool_errors=True))
    )
    builder.add_node("finalize_partial", finalize_partial_node)

    builder.add_edge(START, "guard")
    builder.add_conditional_edges(
        "guard", route_after_guard, {"agent": "agent", "finalize_partial": "finalize_partial"}
    )
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tool_caller": "tool_caller", "finalize_partial": "finalize_partial", END: END},
    )
    builder.add_edge("tool_caller", "guard")
    builder.add_edge("finalize_partial", END)
    return builder.compile(checkpointer=checkpointer)
