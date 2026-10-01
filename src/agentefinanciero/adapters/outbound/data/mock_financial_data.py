import asyncio
from typing import Any

# Valores en millones de USD, deterministas.
_DATA: dict[str, dict[str, float]] = {
    "revenue": {"2022": 1200.0, "2023": 1350.0, "2024": 1500.0},
    "net_income": {"2022": 180.0, "2023": 216.0, "2024": 255.0},
    "total_assets": {"2022": 9800.0, "2023": 10500.0, "2024": 11400.0},
    "total_liabilities": {"2022": 8300.0, "2023": 8900.0, "2024": 9600.0},
    "equity": {"2022": 1500.0, "2023": 1600.0, "2024": 1800.0},
    "operating_expenses": {"2022": 760.0, "2023": 820.0, "2024": 890.0},
}


class MockFinancialDataAdapter:
    def __init__(self, delay_s: float = 2.0) -> None:
        self._delay_s = delay_s

    async def search(self, metric: str, period: str) -> dict[str, Any]:
        await asyncio.sleep(self._delay_s)
        metric_key = metric.strip().lower()
        period_key = period.strip()
        periods = _DATA.get(metric_key)
        if periods is None:
            return {
                "error": f"Métrica desconocida: '{metric}'. Disponibles: {', '.join(sorted(_DATA))}"
            }
        value = periods.get(period_key)
        if value is None:
            return {
                "error": f"Periodo desconocido: '{period}'. Disponibles: {', '.join(sorted(periods))}"
            }
        return {"metric": metric_key, "period": period_key, "value": value, "unit": "USD millones"}
