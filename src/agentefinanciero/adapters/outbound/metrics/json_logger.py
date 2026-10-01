import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TextIO

from agentefinanciero.domain.models import AnalysisContext, AnalysisResult, StepMetric


class JsonLoggerMetrics:
    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream

    async def record_step(self, context: AnalysisContext, metric: StepMetric) -> None:
        self._emit("analysis_step", context, asdict(metric))

    async def record_completion(self, context: AnalysisContext, result: AnalysisResult) -> None:
        budget = result.budget
        self._emit(
            "analysis_completed",
            context,
            {
                "status": result.status.value,
                "stop_reason": result.stop_reason.value,
                "warning": result.warning,
                "steps": len(result.steps),
                "spent_usd": budget.spent_usd,
                "remaining_usd": budget.remaining_usd,
                "tokens_used": budget.tokens_used,
                "remaining_tokens": budget.remaining_tokens,
                "elapsed_time_s": result.elapsed_time_s,
            },
        )

    def _emit(self, event: str, context: AnalysisContext, fields: dict[str, Any]) -> None:
        record = {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "analyst_id": context.analyst_id,
            "session_id": context.session_id,
            "request_id": context.request_id,
            **fields,
        }
        stream = self._stream or sys.stdout
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
