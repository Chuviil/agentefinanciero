from dataclasses import dataclass, field
from enum import StrEnum


class StopReason(StrEnum):
    COMPLETED = "completed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    MAX_STEPS_REACHED = "max_steps_reached"
    TIMEOUT = "timeout"
    LOOP_DETECTED = "loop_detected"
    TOOL_ERRORS = "tool_errors"


class AnalysisStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"


@dataclass(frozen=True)
class AnalysisRequest:
    analyst_id: str
    session_id: str
    query: str
    max_budget_usd: float


@dataclass(frozen=True)
class AnalysisContext:
    analyst_id: str
    session_id: str
    request_id: str


@dataclass(frozen=True)
class ExecutionLimits:
    max_steps: int = 8
    max_tokens_budget: int = 10_000
    timeout_global_s: float = 45.0
    cb_max_repeats: int = 2
    cb_max_consecutive_errors: int = 3
    call_estimate_tokens: int = 2_000

    @property
    def recursion_limit(self) -> int:
        return 3 * self.max_steps + 3


@dataclass(frozen=True)
class Budget:
    max_usd: float
    max_tokens: int
    spent_usd: float = 0.0
    tokens_used: int = 0

    @property
    def remaining_usd(self) -> float:
        return max(self.max_usd - self.spent_usd, 0.0)

    @property
    def remaining_tokens(self) -> int:
        return max(self.max_tokens - self.tokens_used, 0)

    def can_afford(self, estimated_usd: float, estimated_tokens: int) -> bool:
        return self.remaining_usd >= estimated_usd and self.remaining_tokens >= estimated_tokens

    def charge(self, cost_usd: float, tokens: int) -> "Budget":
        return Budget(
            max_usd=self.max_usd,
            max_tokens=self.max_tokens,
            spent_usd=self.spent_usd + cost_usd,
            tokens_used=self.tokens_used + tokens,
        )


@dataclass(frozen=True)
class StepMetric:
    step_number: int
    tool_called: list[str] | None
    tokens_used: int
    cumulative_tokens: int
    step_cost_usd: float
    cumulative_cost: float
    remaining_budget_usd: float
    elapsed_time: float


@dataclass(frozen=True)
class AnalysisResult:
    status: AnalysisStatus
    answer: str
    warning: str | None
    stop_reason: StopReason
    budget: Budget
    steps: list[StepMetric] = field(default_factory=list)
    elapsed_time_s: float = 0.0
