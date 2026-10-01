import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agentefinanciero.domain.models import Budget, ExecutionLimits, StopReason
from agentefinanciero.domain.pricing import TokenPricing


class ExecutionGuard:
    """Decide si se puede hacer otra llamada al LLM. Orden: errores, USD, tokens, pasos."""

    def __init__(self, limits: ExecutionLimits, pricing: TokenPricing) -> None:
        self._limits = limits
        self._estimated_tokens = limits.call_estimate_tokens
        # Se valoriza al precio de salida por ser el más alto.
        self._estimated_usd = pricing.cost(0, limits.call_estimate_tokens)

    def evaluate(
        self, budget: Budget, steps_done: int, consecutive_errors: int
    ) -> StopReason | None:
        if consecutive_errors >= self._limits.cb_max_consecutive_errors:
            return StopReason.TOOL_ERRORS
        if budget.remaining_usd < self._estimated_usd:
            return StopReason.BUDGET_EXCEEDED
        if budget.remaining_tokens < self._estimated_tokens:
            return StopReason.TOKEN_BUDGET_EXCEEDED
        if steps_done >= self._limits.max_steps:
            return StopReason.MAX_STEPS_REACHED
        return None


@dataclass(frozen=True)
class BreakerState:
    call_counts: Mapping[str, int] = field(default_factory=dict)
    consecutive_errors: int = 0


class CircuitBreaker:
    """Detecta firmas `(tool, args)` repetidas. El estado es inmutable y vive en el estado del grafo."""

    def __init__(self, max_repeats: int) -> None:
        self._max_repeats = max_repeats

    @staticmethod
    def signature(tool_name: str, args: Mapping[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(_normalize(args), sort_keys=True)}"

    def register_calls(
        self, state: BreakerState, signatures: Sequence[str]
    ) -> tuple[BreakerState, bool]:
        """Registra las llamadas pedidas; devuelve el nuevo estado y si se detectó un bucle.

        Un bucle se detecta cuando una firma alcanza `max_repeats` apariciones, contando la actual.
        """
        counts = dict(state.call_counts)
        loop = False
        for sig in signatures:
            counts[sig] = counts.get(sig, 0) + 1
            if counts[sig] >= self._max_repeats:
                loop = True
        return BreakerState(counts, state.consecutive_errors), loop

    @staticmethod
    def register_result(state: BreakerState, is_error: bool) -> BreakerState:
        errors = state.consecutive_errors + 1 if is_error else 0
        return BreakerState(state.call_counts, errors)


def _normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, Mapping):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value
