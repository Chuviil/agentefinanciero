import asyncio
import itertools
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

_ids = itertools.count(1)


def ai(
    content: str = "",
    tool_calls: list[tuple[str, dict[str, Any]]] | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    finish_reason: str | None = None,
) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{next(_ids)}", "type": "tool_call"}
            for name, args in (tool_calls or [])
        ],
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        response_metadata={"finish_reason": finish_reason} if finish_reason else {},
    )


class FakeChatModel(BaseChatModel):
    """Chat model determinista: devuelve los mensajes del guion; repite el último si se acaba."""

    script: list[AIMessage]
    delay_s: float = 0.0
    calls: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("Solo async")

    async def _agenerate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        self.calls.append(kwargs)
        await asyncio.sleep(self.delay_s)
        index = min(len(self.calls) - 1, len(self.script) - 1)
        message = self.script[index].model_copy(update={"id": None})
        return ChatResult(generations=[ChatGeneration(message=message)])
