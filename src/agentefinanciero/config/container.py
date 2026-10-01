import os

from langchain_core.language_models import BaseChatModel

from agentefinanciero.adapters.outbound.agent.engine import LangGraphAnalysisEngine
from agentefinanciero.adapters.outbound.agent.llm import build_azure_chat_model, build_rate_limiter
from agentefinanciero.adapters.outbound.data.mock_financial_data import MockFinancialDataAdapter
from agentefinanciero.adapters.outbound.metrics.composite import CompositeMetricsAdapter
from agentefinanciero.adapters.outbound.metrics.json_logger import JsonLoggerMetrics
from agentefinanciero.adapters.outbound.metrics.langsmith_metrics import LangSmithMetrics
from agentefinanciero.application.ports.inbound import AnalyzeQueryUseCase
from agentefinanciero.application.ports.outbound import FinancialDataPort
from agentefinanciero.application.services.run_analysis import RunAnalysisService
from agentefinanciero.config.settings import Settings


def build_use_case(
    settings: Settings,
    *,
    chat_model: BaseChatModel | None = None,
    financial_data: FinancialDataPort | None = None,
) -> AnalyzeQueryUseCase:
    """Único punto que instancia adaptadores. Los parámetros opcionales permiten inyectar dobles."""
    _export_langsmith_env(settings)
    metrics = CompositeMetricsAdapter(JsonLoggerMetrics(), LangSmithMetrics())
    engine = LangGraphAnalysisEngine(
        chat_model=chat_model or _build_chat_model(settings),
        financial_data=financial_data or MockFinancialDataAdapter(),
        pricing=settings.to_pricing(),
        metrics=metrics,
    )
    return RunAnalysisService(engine, metrics, settings.to_limits())


def _build_chat_model(settings: Settings) -> BaseChatModel:
    required = {
        "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
        "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
        "AZURE_OPENAI_DEPLOYMENT": settings.azure_openai_deployment,
        "OPENAI_API_VERSION": settings.openai_api_version,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(f"Faltan variables de entorno del LLM: {', '.join(missing)}")
    return build_azure_chat_model(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key.get_secret_value(),
        deployment=settings.azure_openai_deployment,
        api_version=settings.openai_api_version,
        reasoning_effort=settings.llm_reasoning_effort,
        rate_limiter=build_rate_limiter(settings.rate_limit_rps),
    )


def _export_langsmith_env(settings: Settings) -> None:
    """LangSmith lee su configuración de os.environ; pydantic-settings no la exporta desde .env.

    Sin API key el tracing se desactiva para no generar errores de envío en cada run.
    """
    api_key = settings.langsmith_api_key
    tracing = settings.langsmith_tracing and api_key is not None
    os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if api_key is not None:
        os.environ["LANGSMITH_API_KEY"] = api_key.get_secret_value()
