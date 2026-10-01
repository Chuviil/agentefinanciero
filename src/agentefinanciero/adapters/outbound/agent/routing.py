from langgraph.graph import END

from agentefinanciero.adapters.outbound.agent.state import AgentState


def route_after_guard(state: AgentState) -> str:
    return "finalize_partial" if state.get("stop_reason") else "agent"


def route_after_agent(state: AgentState) -> str:
    if state.get("stop_reason"):
        return "finalize_partial"
    if getattr(state["messages"][-1], "tool_calls", None):
        return "tool_caller"
    return END
