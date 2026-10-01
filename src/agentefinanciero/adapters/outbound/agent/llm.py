from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import AzureChatOpenAI


def build_rate_limiter(requests_per_second: float | None) -> InMemoryRateLimiter | None:
    if requests_per_second is None:
        return None
    return InMemoryRateLimiter(requests_per_second=requests_per_second)


def build_azure_chat_model(
    *,
    endpoint: str,
    api_key: str,
    deployment: str,
    api_version: str,
    reasoning_effort: str,
    rate_limiter: InMemoryRateLimiter | None,
    max_retries: int = 2,
) -> AzureChatOpenAI:
    # gpt-5-mini es un modelo de razonamiento: no se fija temperature (ADR-0002).
    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        azure_deployment=deployment,
        api_version=api_version,
        reasoning_effort=reasoning_effort,
        rate_limiter=rate_limiter,
        max_retries=max_retries,
    )
