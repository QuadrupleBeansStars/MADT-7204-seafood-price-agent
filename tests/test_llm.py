"""Tests for the switchable LLM factory in agent/llm.py."""

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import AzureChatOpenAI


@pytest.fixture(autouse=True)
def _dummy_provider_env(monkeypatch):
    """Give both providers dummy credentials so construction never touches a
    real API or raises on missing config. Each test still controls
    LLM_PROVIDER / ANTHROPIC_MODEL itself."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy-azure-key")
    monkeypatch.setenv("AZURE_ENDPOINT", "https://dummy.openai.azure.com/")
    monkeypatch.setenv("AZURE_API_VERSION", "2024-08-01-preview")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


def test_defaults_to_azure_when_provider_unset():
    from agent.llm import get_chat_llm
    assert isinstance(get_chat_llm(), AzureChatOpenAI)


def test_azure_when_provider_is_azure(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    assert isinstance(get_chat_llm(), AzureChatOpenAI)


def test_anthropic_when_provider_is_anthropic(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert isinstance(get_chat_llm(), ChatAnthropic)


def test_default_anthropic_model_is_sonnet_4_6(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert get_chat_llm().model == "claude-sonnet-4-6"


def test_anthropic_model_override_is_respected(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    assert get_chat_llm().model == "claude-haiku-4-5"


def test_provider_value_is_case_insensitive(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "  Anthropic  ")
    assert isinstance(get_chat_llm(), ChatAnthropic)


def test_unknown_provider_falls_back_to_azure(monkeypatch):
    from agent.llm import get_chat_llm
    monkeypatch.setenv("LLM_PROVIDER", "bogus")
    assert isinstance(get_chat_llm(), AzureChatOpenAI)
