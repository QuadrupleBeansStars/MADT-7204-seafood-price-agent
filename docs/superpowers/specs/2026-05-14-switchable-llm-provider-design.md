# Switchable LLM Provider (Azure ↔ Anthropic) Design
**Date:** 2026-05-14
**Project:** MADT 7204 — Seafood Price Advisor

---

## Context

The agent currently runs exclusively on Azure OpenAI `gpt-4o`. The team
switched away from Anthropic Claude on 2026-05-09 after hitting rate limits,
and the Anthropic code path was fully removed: `langchain-anthropic` is no
longer in `requirements.txt`, `agent/llm.py` only builds `AzureChatOpenAI`,
and `.env.example` has no Anthropic vars.

Biz wants Claude available again. To avoid being stuck if Claude rate limits
return, the provider should be **switchable via an env var** rather than a
hard replacement. Azure stays the default; Claude is opt-in.

This is a contained change: `agent/llm.py` is already the single LLM factory
("one place that knows which provider/model the agent uses"), so the core
change touches one file. The rest is config examples, a provider-aware
startup check, secret bridging, and clearing stale comments.

---

## Decisions (from brainstorming)

- **Switchable, not replace** — `agent/llm.py` returns `ChatAnthropic` or
  `AzureChatOpenAI` based on an `LLM_PROVIDER` env var.
- **Default provider: Azure** — unset `LLM_PROVIDER` behaves exactly as
  today. Claude is opt-in via `LLM_PROVIDER=anthropic`.
- **Claude model: `claude-sonnet-4-6`** — overridable via `ANTHROPIC_MODEL`.
- **Factory structure: simple branch** — a small `if provider == "anthropic"`
  in `get_chat_llm()` with two private builders. No registry/dict — YAGNI for
  two providers.

---

## Architecture / Changes

### 1. `agent/llm.py` — the only behaviour change

`get_chat_llm(temperature: float = 0)` becomes:

- Read `provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()`.
- `provider == "anthropic"` → `_build_anthropic_llm(temperature)`:
  `ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
  api_key=os.getenv("ANTHROPIC_API_KEY"), temperature=temperature)`.
- Anything else → `_build_azure_llm(temperature)`: the existing
  `AzureChatOpenAI(...)` construction, unchanged.
- Return type annotation widens from `AzureChatOpenAI` to
  `BaseChatModel` (`from langchain_core.language_models import BaseChatModel`).
- `DEFAULT_DEPLOYMENT = "gpt-4o"` stays; add
  `DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"`.

**No change needed** in `agent/main.py::agent_node` or `agent/reason.py`:
both already obtain their LLM through `get_chat_llm()`.
`agent/tools/oil_briefing.py` likewise uses the factory and is covered
automatically. The `tool_choice="any"` argument in
`agent/reason.py` works on both Anthropic and OpenAI via langchain (an
existing in-code comment states this) — the implementation plan will
verify it with the provider-switch test run.

### 2. `agent/main.py` — provider-aware startup check

`main()` currently hard-fails when `AZURE_OPENAI_API_KEY`, `AZURE_ENDPOINT`,
or `AZURE_API_VERSION` are missing. Make the required-vars list depend on
`LLM_PROVIDER`:

- `LLM_PROVIDER=anthropic` → require `ANTHROPIC_API_KEY`.
- otherwise → require the three `AZURE_*` vars (current behaviour).

The error message names the missing vars for the active provider.

### 3. `app/main.py` — secret bridging + provider badge

- Add `ANTHROPIC_API_KEY` and `LLM_PROVIDER` to the `_BRIDGED_SECRETS`
  tuple so Streamlit Cloud (secrets dashboard) works for the Anthropic
  path, identically to how Azure secrets are bridged today.
- The hardcoded sidebar badge `"Azure OpenAI · GPT-4o"` becomes
  provider-aware: read `LLM_PROVIDER` and show either
  `"Anthropic · <model>"` or `"Azure OpenAI · <deployment>"`.

### 4. Config examples

- `requirements.txt` — add `langchain-anthropic>=0.2.0`.
- `.env.example` — add an `# LLM provider` block: `LLM_PROVIDER=azure`
  (with a comment that `anthropic` is the alternative), `ANTHROPIC_API_KEY`,
  and `ANTHROPIC_MODEL=claude-sonnet-4-6` (marked optional).
- `.streamlit/secrets.toml.example` — currently inconsistent: it lists
  `ANTHROPIC_API_KEY` but no Azure keys at all, despite the code running on
  Azure. Fix it to list **both** providers plus `LLM_PROVIDER`, matching
  `.env.example`.

### 5. Stale comments

- `app/pages/chat.py:1` — module docstring says "backed by Claude
  Sonnet 4.5". Make it provider-neutral (e.g. "backed by the configured
  LLM provider — see agent/llm.py").
- `tests/test_reason.py` — two comments say "Claude" (lines ~25, ~154).
  Make them provider-neutral ("the LLM") since the reasoning layer is
  provider-agnostic.

---

## Data Flow (unchanged)

```
agent_node / reason_node / oil_briefing tool
        │  get_chat_llm()
        ▼
   agent/llm.py  ──reads LLM_PROVIDER──▶  AzureChatOpenAI  (default)
                                    └──▶  ChatAnthropic    (LLM_PROVIDER=anthropic)
```

The provider is selected once per `get_chat_llm()` call; nothing else in
the graph or tools is provider-aware.

---

## Error Handling

- Missing keys for the active provider: caught at CLI startup by the
  provider-aware check in `agent/main.py` (Step 2). In the Streamlit app,
  a missing key surfaces as the existing `last_error` path in `chat.py`
  when the LLM call fails — no new handling needed.
- Unknown `LLM_PROVIDER` value (typo): falls through to the Azure branch
  (the `else`). This is intentional — Azure is the safe default — and will
  be covered by a test.

---

## Out of Scope

- Removing or deprecating the Azure path.
- Per-request or per-page provider selection — it's a single process-wide
  env var.
- Changing models, prompts, temperature, or any agent behaviour beyond
  provider construction.
- Retry/backoff logic for rate limits (the original reason for leaving
  Claude) — not introduced here; the env-var fallback to Azure is the
  mitigation.

---

## Testing

New unit tests for `agent/llm.py` (patch env vars with `monkeypatch`; no
real API keys needed — construction does not call the API):

- `LLM_PROVIDER` unset → `get_chat_llm()` returns an `AzureChatOpenAI`
  instance.
- `LLM_PROVIDER=azure` → returns `AzureChatOpenAI`.
- `LLM_PROVIDER=anthropic` → returns `ChatAnthropic`.
- `LLM_PROVIDER=anthropic` + `ANTHROPIC_MODEL=claude-haiku-4-5` → returned
  `ChatAnthropic` uses that model (proves the override is wired).
- Unknown `LLM_PROVIDER=bogus` → falls back to `AzureChatOpenAI`.

Plus: run the full existing suite to confirm the type-annotation change and
factory refactor break nothing (`agent/reason.py` and `agent/main.py` tests
exercise the factory via mocks, so they should be unaffected).

Manual check (optional, needs a real key): set `LLM_PROVIDER=anthropic` +
`ANTHROPIC_API_KEY`, run a chat query, confirm a tool call round-trips
(verifies `tool_choice="any"` works on Anthropic).
