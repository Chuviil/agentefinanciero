from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPricing:
    input_per_mtok: float
    cached_input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
        cached = min(max(cached_tokens, 0), input_tokens)
        return (
            (input_tokens - cached) * self.input_per_mtok
            + cached * self.cached_input_per_mtok
            + output_tokens * self.output_per_mtok
        ) / 1e6
