"""Chat LLM factory.

Single place that knows which provider/model the agent uses, so swapping
providers (Azure OpenAI ↔ Anthropic ↔ etc.) only touches one file.
"""

from __future__ import annotations

import os

from langchain_openai import AzureChatOpenAI


DEFAULT_DEPLOYMENT = "gpt-4o"


def get_chat_llm(temperature: float = 0) -> AzureChatOpenAI:
    """Return an AzureChatOpenAI configured from environment.

    Required env vars:
        AZURE_OPENAI_API_KEY
        AZURE_ENDPOINT
        AZURE_API_VERSION

    Optional:
        AZURE_DEPLOYMENT (defaults to 'gpt-4o')
    """
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_DEPLOYMENT", DEFAULT_DEPLOYMENT),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        temperature=temperature,
    )
