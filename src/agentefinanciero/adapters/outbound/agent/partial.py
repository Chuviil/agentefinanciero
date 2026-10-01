import json
from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

from agentefinanciero.domain.models import StopReason

WARNINGS: dict[StopReason, str] = {
    StopReason.BUDGET_EXCEEDED: "Se alcanzó el presupuesto en USD de la consulta.",
    StopReason.TOKEN_BUDGET_EXCEEDED: "Se alcanzó el presupuesto de tokens de la consulta.",
    StopReason.MAX_STEPS_REACHED: "Se alcanzó el número máximo de pasos.",
    StopReason.TIMEOUT: "Se alcanzó el tiempo máximo de ejecución.",
    StopReason.LOOP_DETECTED: "Se detectó una llamada repetida a una herramienta y se detuvo la ejecución.",
    StopReason.TOOL_ERRORS: "Las herramientas devolvieron errores consecutivos y se detuvo la ejecución.",
}


def is_error_message(message: ToolMessage) -> bool:
    if message.status == "error":
        return True
    content = message.content
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except ValueError:
            return False
    return isinstance(content, dict) and "error" in content


def build_partial(messages: Sequence[AnyMessage], reason: StopReason) -> tuple[str, str]:
    """Arma (respuesta, advertencia) desde los resultados de tools, sin llamar al LLM."""
    calls = {
        call["id"]: call
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    lines = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        call = calls.get(message.tool_call_id)
        label = _format_call(call["name"], call["args"]) if call else message.name or "tool"
        suffix = " [error]" if is_error_message(message) else ""
        lines.append(f"- {label}: {message.content}{suffix}")

    warning = f"{WARNINGS[reason]} La respuesta es parcial."
    if lines:
        answer = "Resultados obtenidos hasta el momento:\n" + "\n".join(lines)
    else:
        answer = "No se obtuvieron datos antes de que se detuviera la ejecución."
    return answer, warning


def _format_call(name: str, args: dict) -> str:
    return f"{name}({', '.join(f'{k}={v}' for k, v in args.items())})"
