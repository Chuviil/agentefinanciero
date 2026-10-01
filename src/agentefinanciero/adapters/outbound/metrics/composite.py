import logging

from agentefinanciero.application.ports.outbound import MetricsPort
from agentefinanciero.domain.models import AnalysisContext, AnalysisResult, StepMetric

logger = logging.getLogger(__name__)


class CompositeMetricsAdapter:
    """Reenvía a todos los destinos. El primero es el log JSON, que siempre debe mantenerse.

    Si un destino falla, se registra el error y los demás siguen funcionando.
    """

    def __init__(self, primary: MetricsPort, *secondary: MetricsPort) -> None:
        self._sinks = (primary, *secondary)

    async def record_step(self, context: AnalysisContext, metric: StepMetric) -> None:
        for sink in self._sinks:
            try:
                await sink.record_step(context, metric)
            except Exception:
                logger.exception(
                    "Falló record_step en %s (request_id=%s)", type(sink).__name__, context.request_id
                )

    async def record_completion(self, context: AnalysisContext, result: AnalysisResult) -> None:
        for sink in self._sinks:
            try:
                await sink.record_completion(context, result)
            except Exception:
                logger.exception(
                    "Falló record_completion en %s (request_id=%s)",
                    type(sink).__name__,
                    context.request_id,
                )
