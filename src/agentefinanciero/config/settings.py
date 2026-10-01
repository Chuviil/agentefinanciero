from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agentefinanciero.domain.models import ExecutionLimits
from agentefinanciero.domain.pricing import TokenPricing


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_deployment: str | None = None
    openai_api_version: str | None = None
    llm_reasoning_effort: str = "low"

    price_input_per_mtok: float
    price_cached_input_per_mtok: float
    price_output_per_mtok: float

    langsmith_tracing: bool = True
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "financial-analysis-agent"

    max_steps: int = 8
    max_tokens_budget: int = 10_000
    timeout_global_s: float = 45.0
    rate_limit_rps: float | None = None
    cb_max_repeats: int = 2
    cb_max_consecutive_errors: int = 3
    initial_call_estimate_tokens: int = 2_000

    def to_limits(self) -> ExecutionLimits:
        return ExecutionLimits(
            max_steps=self.max_steps,
            max_tokens_budget=self.max_tokens_budget,
            timeout_global_s=self.timeout_global_s,
            cb_max_repeats=self.cb_max_repeats,
            cb_max_consecutive_errors=self.cb_max_consecutive_errors,
            call_estimate_tokens=self.initial_call_estimate_tokens,
        )

    def to_pricing(self) -> TokenPricing:
        return TokenPricing(
            input_per_mtok=self.price_input_per_mtok,
            cached_input_per_mtok=self.price_cached_input_per_mtok,
            output_per_mtok=self.price_output_per_mtok,
        )
