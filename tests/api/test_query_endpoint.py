import httpx
import pytest

from agentefinanciero.adapters.outbound.data.mock_financial_data import MockFinancialDataAdapter
from agentefinanciero.config.container import build_use_case
from agentefinanciero.config.settings import Settings
from agentefinanciero.main import create_app
from tests.fakes import FakeChatModel, ai

URL = "/api/v1/analysis/query"
BODY = {"analyst_id": "A01", "session_id": "S001", "query": "revenue 2024", "max_budget_usd": 0.5}
STEP_FIELDS = {
    "step_number", "tool_called", "tokens_used", "cumulative_tokens",
    "step_cost_usd", "cumulative_cost", "remaining_budget_usd", "elapsed_time",
}
METRICS = ["revenue", "net_income", "total_assets", "total_liabilities", "equity", "operating_expenses"]


def search(metric, period="2024"):
    return ("search_financial_data", {"metric": metric, "period": period})


def distinct_calls(n):
    combos = [(m, p) for p in ("2022", "2023", "2024") for m in METRICS]
    return [ai(tool_calls=[search(m, p)]) for m, p in combos[:n]]


def make_client(script, *, tool_delay_s=0.0, **overrides) -> httpx.AsyncClient:
    settings = Settings(
        _env_file=None,
        price_input_per_mtok=0.25,
        price_cached_input_per_mtok=0.025,
        price_output_per_mtok=2.0,
        **overrides,
    )
    use_case = build_use_case(
        settings,
        chat_model=FakeChatModel(script=script),
        financial_data=MockFinancialDataAdapter(delay_s=tool_delay_s),
    )
    transport = httpx.ASGITransport(app=create_app(use_case))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def post(client, **changes):
    async with client:
        return await client.post(URL, json={**BODY, **changes})


async def test_completed_response_contract():
    client = make_client([ai(tool_calls=[search("revenue")]), ai("El revenue 2024 fue 1500.")])

    response = await post(client)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed" and data["stop_reason"] == "completed"
    assert data["warning"] is None
    assert data["answer"] == "El revenue 2024 fue 1500."
    assert set(data["budget"]) == {
        "max_budget_usd", "spent_usd", "remaining_usd", "max_tokens", "tokens_used", "remaining_tokens",
    }
    assert data["budget"]["max_budget_usd"] == 0.5 and data["budget"]["max_tokens"] == 10_000
    assert len(data["steps"]) == 2
    assert all(set(step) == STEP_FIELDS for step in data["steps"])
    assert data["elapsed_time_s"] >= 0


async def test_loop_detected_returns_200_partial():
    response = await post(make_client([ai(tool_calls=[search("revenue")])]))

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "partial" and data["stop_reason"] == "loop_detected"
    assert data["warning"]


async def test_very_low_budget_returns_partial_budget_exceeded():
    response = await post(make_client([ai("x")]), max_budget_usd=0.0001)

    data = response.json()
    assert response.status_code == 200
    assert data["stop_reason"] == "budget_exceeded" and data["status"] == "partial"
    assert data["steps"] == []
    assert data["budget"]["spent_usd"] == 0


async def test_more_than_eight_steps_returns_max_steps_reached():
    response = await post(make_client(distinct_calls(12)))

    data = response.json()
    assert data["stop_reason"] == "max_steps_reached"
    assert len(data["steps"]) == 8


async def test_timeout_returns_200_partial():
    client = make_client(distinct_calls(5), tool_delay_s=0.4, timeout_global_s=0.6)

    response = await post(client)

    assert response.status_code == 200
    assert response.json()["stop_reason"] == "timeout"
    assert response.json()["status"] == "partial"


async def test_ratio_with_zero_denominator_ends_in_tool_errors():
    script = [ai(tool_calls=[("calculate_ratio", {"numerator": i, "denominator": 0})]) for i in range(1, 6)]

    data = (await post(make_client(script))).json()

    assert data["stop_reason"] == "tool_errors"
    assert "division by zero" in data["answer"]


@pytest.mark.parametrize(
    "changes",
    [
        {"query": ""},
        {"query": "   "},
        {"max_budget_usd": 0},
        {"max_budget_usd": -1},
        {"analyst_id": ""},
        {"session_id": ""},
    ],
)
async def test_invalid_values_return_422(changes):
    response = await post(make_client([ai("x")]), **changes)
    assert response.status_code == 422


@pytest.mark.parametrize("missing", list(BODY))
async def test_missing_fields_return_422(missing):
    client = make_client([ai("x")])
    async with client:
        body = {k: v for k, v in BODY.items() if k != missing}
        response = await client.post(URL, json=body)
    assert response.status_code == 422
