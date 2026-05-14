"""Chat LLM factory.

Single place that knows which provider/model the agent uses, so swapping
providers (Azure OpenAI ↔ Anthropic ↔ etc.) only touches one file.

The provider is selected by the LLM_PROVIDER env var:
    LLM_PROVIDER=azure      → AzureChatOpenAI  (default when unset/unknown)
    LLM_PROVIDER=anthropic  → ChatAnthropic
"""

from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI


DEFAULT_DEPLOYMENT = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


def _build_azure_llm(temperature: float) -> AzureChatOpenAI:
    """AzureChatOpenAI from env: AZURE_OPENAI_API_KEY, AZURE_ENDPOINT,
    AZURE_API_VERSION; optional AZURE_DEPLOYMENT (defaults to 'gpt-4o')."""
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_DEPLOYMENT", DEFAULT_DEPLOYMENT),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        temperature=temperature,
    )


def _build_anthropic_llm(temperature: float) -> ChatAnthropic:
    """ChatAnthropic from env: ANTHROPIC_API_KEY; optional ANTHROPIC_MODEL
    (defaults to 'claude-sonnet-4-6')."""
    return ChatAnthropic(
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=temperature,
    )


def get_chat_llm(temperature: float = 0) -> BaseChatModel:
    """Return the chat LLM for the configured provider.

    Provider is chosen by the LLM_PROVIDER env var ('azure' is the default;
    'anthropic' selects Claude). Any unrecognised value falls back to Azure.
    """
    provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()
    if provider == "anthropic":
        return _build_anthropic_llm(temperature)
    return _build_azure_llm(temperature)
