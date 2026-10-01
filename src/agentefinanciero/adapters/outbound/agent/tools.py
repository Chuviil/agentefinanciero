from typing import Any

from langchain_core.tools import BaseTool, tool

from agentefinanciero.application.ports.outbound import FinancialDataPort
from agentefinanciero.domain.ratio import calculate_ratio as compute_ratio


def build_tools(financial_data: FinancialDataPort) -> list[BaseTool]:
    @tool
    async def search_financial_data(metric: str, period: str) -> dict[str, Any]:
        """Busca el valor de una métrica financiera para un periodo.

        Métricas: revenue, net_income, total_assets, total_liabilities, equity,
        operating_expenses. Periodos: 2022, 2023, 2024. Valores en USD millones.
        """
        return await financial_data.search(metric, period)

    @tool
    async def calculate_ratio(numerator: float, denominator: float) -> dict[str, Any]:
        """Calcula numerator / denominator. Si el denominador es 0 devuelve un error."""
        return compute_ratio(numerator, denominator)

    return [search_financial_data, calculate_ratio]
