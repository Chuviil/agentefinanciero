from dataclasses import asdict
from typing import Any

from langsmith.run_helpers import get_current_run_tree

from agentefinanciero.domain.models import AnalysisContext, AnalysisResult, StepMetric


class LangSmithMetrics:
    """Agrega las métricas FinOps como metadata del run activo; sin run activo no hace nada."""

    async def record_step(self, context: AnalysisContext, metric: StepMetric) -> None:
        self._add_metadata({"finops_step": asdict(metric)})

    async def record_completion(self, context: AnalysisContext, result: AnalysisResult) -> None:
        budget = result.budget
        self._add_metadata(
            {
                "finops_status": result.status.value,
                "finops_stop_reason": result.stop_reason.value,
                "finops_spent_usd": budget.spent_usd,
                "finops_tokens_used": budget.tokens_used,
                "finops_elapsed_time_s": result.elapsed_time_s,
            }
        )

    @staticmethod
    def _add_metadata(metadata: dict[str, Any]) -> None:
        run_tree = get_current_run_tree()
        if run_tree is not None:
            run_tree.add_metadata(metadata)
