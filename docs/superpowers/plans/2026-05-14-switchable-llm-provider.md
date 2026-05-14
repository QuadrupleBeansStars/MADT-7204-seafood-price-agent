# Switchable LLM Provider (Azure ↔ Anthropic) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the agent's LLM provider switchable between Azure OpenAI (default) and Anthropic Claude via an `LLM_PROVIDER` env var, without removing the Azure path.

**Architecture:** `agent/llm.py` is already the single LLM factory. `get_chat_llm()` gains a branch keyed on `LLM_PROVIDER` — `anthropic` builds `ChatAnthropic`, anything else builds the existing `AzureChatOpenAI`. The CLI startup check, Streamlit secret bridging, the sidebar badge, and config examples are updated to know about both providers. No graph/tool/prompt behaviour changes.

**Tech Stack:** Python, LangChain (`langchain-openai`, `langchain-anthropic`), LangGraph, Streamlit, pytest.

**Environment note:** All `pytest` / `python` commands must be run after `conda activate MADT`. `langchain-anthropic` (v1.4.0) is already installed in that conda env; Task 4 adds it to `requirements.txt` for reproducibility.

---

## File Structure

- `agent/llm.py` — MODIFY. The LLM factory. Add `LLM_PROVIDER` branch + two private builder functions + a default-model constant.
- `tests/test_llm.py` — CREATE. Unit tests for the factory's provider selection.
- `agent/main.py` — MODIFY. Add a provider-aware `_required_env_vars()` helper and use it in the CLI startup check.
- `tests/test_main.py` — CREATE. Unit tests for `_required_env_vars()`.
- `app/main.py` — MODIFY. Bridge Anthropic secrets; make the sidebar badge provider-aware.
- `requirements.txt` — MODIFY. Add `langchain-anthropic`.
- `.env.example` — MODIFY (full rewrite). Add LLM-provider block.
- `.streamlit/secrets.toml.example` — MODIFY (full rewrite). List both providers + `LLM_PROVIDER`.
- `app/pages/chat.py` — MODIFY. Stale docstring line.
- `tests/test_reason.py` — MODIFY. Two stale "Claude" comments.

---

## Task 1: Switchable factory in `agent/llm.py`

**Files:**
- Create: `tests/test_llm.py`
- Modify: `agent/llm.py` (full rewrite — small file)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_llm.py` with exactly this content:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda activate MADT && pytest tests/test_llm.py -v`

Expected: the `anthropic` tests FAIL — the current `agent/llm.py` always returns `AzureChatOpenAI`, so `test_anthropic_when_provider_is_anthropic`, `test_default_anthropic_model_is_sonnet_4_6`, `test_anthropic_model_override_is_respected`, and `test_provider_value_is_case_insensitive` fail (returned object is not a `ChatAnthropic`). The azure tests pass.

- [ ] **Step 3: Rewrite `agent/llm.py` with the switchable factory**

Replace the entire contents of `agent/llm.py` with:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `conda activate MADT && pytest tests/test_llm.py -v`

Expected: all 7 tests PASS.

Note: if `get_chat_llm().model` raises `AttributeError`, the installed `langchain-anthropic` exposes the model as `.model_name` instead — update the two assertions in `tests/test_llm.py` to read `.model_name`. (v1.4.0 uses `.model`; this note covers a version drift only.)

- [ ] **Step 5: Run the full suite to confirm the refactor breaks nothing**

Run: `conda activate MADT && pytest -q`

Expected: all tests PASS. `agent/reason.py` tests patch `_build_reason_llm` and `agent/main.py`'s `agent_node` is not directly tested, so the factory refactor and the widened `BaseChatModel` return type should not affect them. `tests/test_oil_briefing.py` exercises the oil-briefing tool — confirm it still passes (it uses the factory but should be mocked).

- [ ] **Step 6: Commit**

```bash
git add agent/llm.py tests/test_llm.py
git commit -m "$(cat <<'EOF'
feat(agent): switchable LLM provider via LLM_PROVIDER env var

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Provider-aware startup check in `agent/main.py`

**Files:**
- Create: `tests/test_main.py`
- Modify: `agent/main.py` (add `_required_env_vars` helper near the other module-level defs; update the check inside `main()`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main.py` with exactly this content:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda activate MADT && pytest tests/test_main.py -v`

Expected: all 3 tests FAIL with `ImportError` / `AttributeError` — `_required_env_vars` does not exist in `agent/main.py` yet.

- [ ] **Step 3: Add the `_required_env_vars` helper to `agent/main.py`**

In `agent/main.py`, add this function immediately after the `TOOLS = ALL_TOOLS` line (just before the `# --- State ---` comment):

```python


def _required_env_vars(provider: str) -> tuple[str, ...]:
    """Env vars that must be set for the given LLM provider to work."""
    if provider == "anthropic":
        return ("ANTHROPIC_API_KEY",)
    return ("AZURE_OPENAI_API_KEY", "AZURE_ENDPOINT", "AZURE_API_VERSION")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `conda activate MADT && pytest tests/test_main.py -v`

Expected: all 3 tests PASS.

- [ ] **Step 5: Use the helper in `main()`'s startup check**

In `agent/main.py`, find this exact block inside `main()`:

```python
    # Check for required Azure OpenAI config
    missing = [k for k in ("AZURE_OPENAI_API_KEY", "AZURE_ENDPOINT", "AZURE_API_VERSION")
               if not os.getenv(k)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}. "
              f"Copy .env.example to .env and fill them in.")
        sys.exit(1)
```

Replace it with:

```python
    # Check for required LLM-provider config
    provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()
    missing = [k for k in _required_env_vars(provider) if not os.getenv(k)]
    if missing:
        print(f"ERROR: missing env vars for LLM_PROVIDER='{provider}': "
              f"{', '.join(missing)}. Copy .env.example to .env and fill them in.")
        sys.exit(1)
```

- [ ] **Step 6: Run the full suite to confirm nothing broke**

Run: `conda activate MADT && pytest -q`

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add agent/main.py tests/test_main.py
git commit -m "$(cat <<'EOF'
feat(agent): provider-aware env var check in CLI startup

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Bridge Anthropic secrets + provider-aware badge in `app/main.py`

**Files:**
- Modify: `app/main.py` (the `_BRIDGED_SECRETS` tuple; the `st.badge(...)` call inside `_render_sidebar`; one import)

This task has no unit test — `app/main.py` is Streamlit page-orchestration code with no testable pure functions added. It is verified by an `ast.parse` syntax check and `grep` (Step 4) plus the manual smoke check.

- [ ] **Step 1: Import the model-name constants from the factory**

In `app/main.py`, find this exact line:

```python
from auth import require_login
```

Replace it with:

```python
from auth import require_login

from agent.llm import DEFAULT_ANTHROPIC_MODEL, DEFAULT_DEPLOYMENT
```

(The `sys.path` insert above this line already makes `agent` importable; `auth` is imported first to keep the existing login-gate ordering untouched.)

- [ ] **Step 2: Add the Anthropic vars to `_BRIDGED_SECRETS`**

In `app/main.py`, find this exact tuple:

```python
_BRIDGED_SECRETS = (
    "AZURE_OPENAI_API_KEY",
    "AZURE_ENDPOINT",
    "AZURE_API_VERSION",
    "AZURE_DEPLOYMENT",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_HOST",
)
```

Replace it with:

```python
_BRIDGED_SECRETS = (
    "LLM_PROVIDER",
    "AZURE_OPENAI_API_KEY",
    "AZURE_ENDPOINT",
    "AZURE_API_VERSION",
    "AZURE_DEPLOYMENT",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_HOST",
)
```

- [ ] **Step 3: Make the sidebar badge provider-aware**

In `app/main.py`, inside `_render_sidebar`, find this exact line:

```python
        st.badge("Azure OpenAI · GPT-4o", icon=":material/smart_toy:", color="blue")
```

Replace it with:

```python
        _provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()
        if _provider == "anthropic":
            _badge = f"Anthropic · {os.getenv('ANTHROPIC_MODEL', DEFAULT_ANTHROPIC_MODEL)}"
        else:
            _badge = f"Azure OpenAI · {os.getenv('AZURE_DEPLOYMENT', DEFAULT_DEPLOYMENT)}"
        st.badge(_badge, icon=":material/smart_toy:", color="blue")
```

(`os` is already imported at the top of `app/main.py`.)

- [ ] **Step 4: Syntax + content check**

Run:
```bash
conda activate MADT && python -c "import ast; ast.parse(open('app/main.py').read()); print('app/main.py parses OK')" && grep -c "ANTHROPIC_API_KEY\|LLM_PROVIDER" app/main.py
```

Expected: prints `app/main.py parses OK`, then a count `>= 3` (the two new `_BRIDGED_SECRETS` entries plus the `LLM_PROVIDER` read in the badge logic).

- [ ] **Step 5: Manual smoke check**

Run: `conda activate MADT && streamlit run app/main.py --server.headless true`

Confirm the app boots without error and the sidebar badge reads `Azure OpenAI · gpt-4o` (default, since `LLM_PROVIDER` is unset). If you cannot run the Streamlit UI in this environment, say so explicitly rather than marking this step done.

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "$(cat <<'EOF'
feat(app): bridge Anthropic secrets + provider-aware sidebar badge

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Config examples + stale comments

**Files:**
- Modify: `requirements.txt` (add one line)
- Modify: `.env.example` (full rewrite)
- Modify: `.streamlit/secrets.toml.example` (full rewrite)
- Modify: `app/pages/chat.py` (line 1 docstring)
- Modify: `tests/test_reason.py` (two comment lines)

This task is documentation/config + comments — no unit tests. Verified by `grep` (Step 6) and the full suite still passing.

- [ ] **Step 1: Add `langchain-anthropic` to `requirements.txt`**

In `requirements.txt`, find this exact line:

```
langchain-openai>=0.2.0
```

Replace it with:

```
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0
```

- [ ] **Step 2: Rewrite `.env.example`**

Replace the entire contents of `.env.example` with:

```
# LLM provider — 'azure' (default) or 'anthropic'
LLM_PROVIDER=azure

# Azure OpenAI (used when LLM_PROVIDER=azure)
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here
AZURE_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-08-01-preview
# Optional; defaults to gpt-4o
AZURE_DEPLOYMENT=gpt-4o

# Anthropic Claude (used when LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY=sk-ant-your-key-here
# Optional; defaults to claude-sonnet-4-6
ANTHROPIC_MODEL=claude-sonnet-4-6

# Streamlit login gate (also settable via .streamlit/secrets.toml as app_password)
APP_PASSWORD=change-me

# Langfuse Observability (self-hosted)
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_HOST=http://localhost:3000
```

- [ ] **Step 3: Rewrite `.streamlit/secrets.toml.example`**

Replace the entire contents of `.streamlit/secrets.toml.example` with:

```
# Copy this file to .streamlit/secrets.toml and fill in real values.
# On Streamlit Community Cloud, paste the same key/value pairs into the
# app's "Secrets" section in the dashboard instead of creating the file.

# Login gate password (shared across the team)
app_password = "lk;[k'Fr]"

# LLM provider — "azure" (default) or "anthropic"
LLM_PROVIDER = "azure"

# Azure OpenAI — required when LLM_PROVIDER = "azure".
AZURE_OPENAI_API_KEY = "your-azure-openai-api-key-here"
AZURE_ENDPOINT = "https://your-resource.openai.azure.com/"
AZURE_API_VERSION = "2024-08-01-preview"
# Optional; defaults to gpt-4o
AZURE_DEPLOYMENT = "gpt-4o"

# Anthropic Claude — required when LLM_PROVIDER = "anthropic".
ANTHROPIC_API_KEY = "sk-ant-..."
# Optional; defaults to claude-sonnet-4-6
ANTHROPIC_MODEL = "claude-sonnet-4-6"

# Langfuse observability (optional — leave unset to disable tracing)
# LANGFUSE_SECRET_KEY = "sk-lf-..."
# LANGFUSE_PUBLIC_KEY = "pk-lf-..."
# LANGFUSE_HOST = "http://localhost:3000"
```

- [ ] **Step 4: Fix the stale docstring in `app/pages/chat.py`**

In `app/pages/chat.py`, find this exact line (line 1):

```python
"""Chat page — LangGraph ReAct agent backed by Claude Sonnet 4.5.
```

Replace it with:

```python
"""Chat page — LangGraph ReAct agent backed by the configured LLM provider.
```

- [ ] **Step 5: Fix the stale "Claude" comments in `tests/test_reason.py`**

In `tests/test_reason.py`, find this exact line:

```python
    """Return an AIMessage that looks like Claude called a tool."""
```

Replace it with:

```python
    """Return an AIMessage that looks like the LLM called a tool."""
```

Then find this exact line:

```python
        """If Claude returns plain text (no tool call), state has no plan/clarification."""
```

Replace it with:

```python
        """If the LLM returns plain text (no tool call), state has no plan/clarification."""
```

- [ ] **Step 6: Verify the changes landed and the suite still passes**

Run:
```bash
conda activate MADT && grep -c langchain-anthropic requirements.txt && grep -rin "claude sonnet 4.5\|backed by Claude" app/pages/chat.py tests/test_reason.py | wc -l && pytest -q
```

Expected: prints `1` (langchain-anthropic in requirements), then `0` (no stale Claude references left in those two files), then the full suite PASSES.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example .streamlit/secrets.toml.example app/pages/chat.py tests/test_reason.py
git commit -m "$(cat <<'EOF'
chore: config examples + comments for switchable LLM provider

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:**
  - `agent/llm.py` switchable factory → Task 1.
  - Default Azure / `anthropic` opt-in / case-insensitive / unknown→Azure → Task 1 tests.
  - `claude-sonnet-4-6` default + `ANTHROPIC_MODEL` override → Task 1 (`DEFAULT_ANTHROPIC_MODEL`, tests).
  - `BaseChatModel` return annotation → Task 1 Step 3.
  - Provider-aware CLI startup check → Task 2.
  - `app/main.py` secret bridging + provider badge → Task 3.
  - `requirements.txt`, `.env.example`, `.streamlit/secrets.toml.example` → Task 4 Steps 1–3.
  - Stale comments (`chat.py`, `test_reason.py`) → Task 4 Steps 4–5.
  - "Verify `tool_choice="any"` works on Anthropic" — covered by the spec's optional manual check (needs a real key); the automated suite proves construction + wiring. Not a separate task because it cannot be done hermetically.
- **Out-of-scope items** (removing Azure, per-request provider selection, retry/backoff, prompt/temperature changes) are intentionally not touched.
- **Type consistency:** `get_chat_llm` returns `BaseChatModel`; `_build_azure_llm` / `_build_anthropic_llm` are the private builders used only inside Task 1. `_required_env_vars(provider: str) -> tuple[str, ...]` defined in Task 2 Step 3, consumed in Step 5 and tested in Step 1. `DEFAULT_ANTHROPIC_MODEL` / `DEFAULT_DEPLOYMENT` defined in Task 1, imported in Task 3 Step 1. Constant and function names match across all tasks.
