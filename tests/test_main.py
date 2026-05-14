"""Tests for agent/main.py helpers."""


def test_required_env_vars_azure():
    from agent.main import _required_env_vars
    assert _required_env_vars("azure") == (
        "AZURE_OPENAI_API_KEY",
        "AZURE_ENDPOINT",
        "AZURE_API_VERSION",
    )


def test_required_env_vars_anthropic():
    from agent.main import _required_env_vars
    assert _required_env_vars("anthropic") == ("ANTHROPIC_API_KEY",)


def test_required_env_vars_unknown_falls_back_to_azure():
    from agent.main import _required_env_vars
    assert _required_env_vars("bogus") == (
        "AZURE_OPENAI_API_KEY",
        "AZURE_ENDPOINT",
        "AZURE_API_VERSION",
    )
