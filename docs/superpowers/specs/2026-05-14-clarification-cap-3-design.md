# Clarification Cap 3 + New Chat Button Design
**Date:** 2026-05-14
**Project:** MADT 7204 — Seafood Price Advisor

---

## Context

The Biz team reports that the agent can still get stuck in reasoning loops.
The reasoning layer (`agent/reason.py`) already has a hard guard that
suppresses clarifications, but it is currently set to a cap of **1** — after
a single clarifying question anywhere in the session, every further
clarification is suppressed and the agent is forced to answer.

Biz wants the agent to be allowed up to **3** clarifying exchanges before it
must commit. When that cap is hit, it should still produce a useful answer
from whatever was gathered in the conversation so far — not give up.

This is a re-tuning of the existing guard plus one UI affordance, not a new
subsystem.

---

## Desired Behaviour

```
User:   อยากซื้ออาหารทะเล
REASON: ambiguous → clarify (1/3)   Q: ประเภทไหน? [กุ้ง][ปลา][หมึก][ปู][หอย]
User:   *taps กุ้ง*
REASON: still broad → clarify (2/3) Q: ... [..]
User:   *answers*
REASON: still broad → clarify (3/3) Q: ... [..]
User:   *answers*
REASON: cap reached → suppress clarification, route to agent
AGENT:  answers best-effort using the full conversation history
```

The "answer best-effort" path is **already implemented**: when the guard
suppresses a clarification it returns state with both
`pending_clarification` and `current_plan` set to `None`, and
`route_reason` sends that to `agent_node`. `agent_node` then runs with the
full message history (every prior clarification Q + user answer) and no
plan, producing a best-effort answer. Raising the cap simply gives the user
3 swings before this fallback engages.

Separately, because the Streamlit app keeps **one continuous message
history** for the whole chat (no per-intent session boundary), a hard global
cap of 3 means clarifications stop for the rest of the page's lifetime. To
let users start a genuinely fresh intent, the chat page gets a **"New chat"**
button that clears the session state.

---

## Architecture / Changes

### 1. `agent/reason.py` — raise the cap 1 → 3

- **Line ~399**, in `reason_node`'s suppression guard:
  `_session_clarification_count(session_msgs) >= 1` → `>= 3`
- **`_session_clarification_count` docstring + the inline comment block
  (~lines 162–181)**: update wording from "after 1" / ">= 1" to reflect the
  new cap of 3.
- **`REASON_SYSTEM_PROMPT` hard rules (~lines 338–340)**: change
  `"After 1 clarification exchange in the conversation, you MUST call
  create_plan"` → `"After 3 clarification exchanges in the conversation,
  you MUST call create_plan"`. This keeps the LLM's own behaviour aligned
  with the programmatic guard, which remains the hard backstop.

**Unchanged on purpose:** every other loop guard stays exactly as-is —
`_options_are_banned`, `_question_is_banned`, `_is_scope_confusion_question`,
`_already_clarified` (per-turn), and `_is_renarrowing_question`. Those catch
*bad* clarifications regardless of count; only the raw session-count
threshold moves.

### 2. `app/pages/chat.py` — add a "New chat" button

- Placement: top of the page, near the title (e.g. a right-aligned column
  next to `st.title` / `st.caption`).
- On click:
  - reset `st.session_state["messages"]` to `[SystemMessage(content=SYSTEM_PROMPT)]`
  - set `pending_clarification`, `current_plan`, `last_thinking` to `None`
  - set `clarification_round` to `0`
  - `st.rerun()`

This mirrors the reset block already present in the `st.chat_input` handler
(chat.py:246–251), just triggered explicitly and also clearing `messages`.

### 3. Tests — `tests/test_reason.py`

- **`test_session_wide_clarification_loop_is_suppressed`** currently builds a
  history with **1** tagged clarification and asserts the next is
  suppressed. At cap 3 that is wrong. Rework it to build **3** tagged
  `is_clarification` AIMessages in history and assert the **4th** attempt is
  suppressed (`pending_clarification is None`, `current_plan is None` — falls
  through to agent).
- **Add a companion test:** with 1–2 prior tagged clarifications in history,
  a new clarification is **allowed** (within budget) — proves the cap is 3,
  not 1.
- `test_second_clarification_in_same_turn_is_suppressed` and
  `test_clarification_allowed_in_a_later_turn` do not depend on the
  threshold value and should continue to pass unchanged.

---

## Data Flow (unchanged shape, re-tuned threshold)

```
user msg → reason_node
  ├─ tagged clarifications in history < 3  → may clarify → END (show buttons)
  └─ tagged clarifications in history ≥ 3  → suppress    → agent_node answers
                                                            best-effort
```

---

## Out of Scope

- Per-intent / consecutive-only counter resets — explicitly rejected in
  favour of the hard global cap + "New chat" button.
- Any change to the other loop guards or to `agent_node` / `SYSTEM_PROMPT`
  answer formatting.
- Persisting clarification budget across page reloads.

---

## Testing

- Unit tests in `tests/test_reason.py` as described above.
- Manual check in the Streamlit chat page: ask a vague query, answer 3
  clarifications, confirm the 4th turn produces a best-effort answer instead
  of another question; confirm "New chat" clears history and restores a
  fresh clarification budget.
