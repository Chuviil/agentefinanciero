import os

import pytest

from agentefinanciero.config.container import build_use_case
from agentefinanciero.config.settings import Settings
from tests.fakes import FakeChatModel, ai

PRICES = {"price_input_per_mtok": 0.25, "price_cached_input_per_mtok": 0.025, "price_output_per_mtok": 2.0}


def test_missing_azure_variables_fail_with_clear_message():
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        build_use_case(Settings(_env_file=None, **PRICES))


def test_langsmith_tracing_is_disabled_without_api_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    build_use_case(Settings(_env_file=None, **PRICES), chat_model=FakeChatModel(script=[ai("x")]))
    assert os.environ["LANGSMITH_TRACING"] == "false"
