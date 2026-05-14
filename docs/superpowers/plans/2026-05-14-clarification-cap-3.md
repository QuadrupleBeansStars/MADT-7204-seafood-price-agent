# Clarification Cap 3 + New Chat Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the per-session clarification cap in the reasoning layer from 1 to 3, and add a "New chat" button to the Streamlit chat page so users can start a fresh clarification budget.

**Architecture:** The cap already exists as a programmatic guard in `agent/reason.py` (`_session_clarification_count(...) >= 1`); we re-tune the threshold to 3 and align the system prompt wording. The "answer best-effort when cap hit" behaviour is already implemented (suppressed clarification → both state fields `None` → `route_reason` sends to `agent_node`). Because the Streamlit app keeps one continuous message history, a "New chat" button clears `st.session_state` so a new intent gets a fresh budget.

**Tech Stack:** Python, LangGraph, LangChain core messages, Streamlit, pytest.

**Environment note:** All `pytest` commands must be run after `conda activate MADT` — dependencies live in that conda env, not system Python.

---

## File Structure

- `agent/reason.py` — MODIFY. Reasoning node + loop guards. Change the cap threshold, a stale comment, and the system-prompt hard rule.
- `tests/test_reason.py` — MODIFY. Rework the existing session-cap test and add a within-budget test.
- `app/pages/chat.py` — MODIFY. Add a "New chat" button near the page title that resets session state.

---

## Task 1: Raise clarification cap from 1 to 3

**Files:**
- Modify: `agent/reason.py` (suppression guard ~line 399, stale comment ~line 396, system prompt ~lines 338-340)
- Test: `tests/test_reason.py` (replace `test_session_wide_clarification_loop_is_suppressed` ~lines 456-482, add one new test after it)

- [ ] **Step 1: Rework the session-cap test to expect a cap of 3**

In `tests/test_reason.py`, find this exact existing method and replace it:

```python
    def test_session_wide_clarification_loop_is_suppressed(self):
        """Screenshot bug: 'ปูม้าวันนี้ที่ไหนถูกสุด' → agent asked
        'ปูม้าประเภทไหน?', user clicked 'ปูม้าสด' (a new HumanMessage, which
        resets the per-turn guard), and the agent clarified AGAIN. Once a
        clarification has been asked anywhere in the session, the next one
        must be suppressed regardless of how many option clicks happened."""
        from agent.reason import reason_node
        messages = [
            HumanMessage(content="ปูม้าวันนี้ที่ไหนถูกสุด"),
            AIMessage(content="คุณต้องการปูม้าประเภทไหน?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="ปูม้าสด"),  # button click → fresh turn
        ]
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "still narrowing", "question": "คุณต้องการปูม้าแบบไหน?",
             "options": ["เนื้อปูม้าสด", "เนื้อปูม้าก้อน"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state(messages=messages))

        assert result["pending_clarification"] is None  # suppressed
        assert result["current_plan"] is None  # falls through to agent
```

Replace it with these TWO methods:

```python
    def test_fourth_clarification_in_session_is_suppressed(self):
        """Cap is 3 clarifying exchanges per session. Once 3 tagged
        clarifications exist in history, the 4th attempt is suppressed and
        the turn falls through to agent_node to answer best-effort."""
        from agent.reason import reason_node
        messages = [
            HumanMessage(content="อยากซื้ออาหารทะเล"),
            AIMessage(content="ประเภทไหน?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="กุ้ง"),
            AIMessage(content="ขนาดไหน?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="ตัวใหญ่"),
            AIMessage(content="งบเท่าไหร่?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="ไม่จำกัด"),
        ]
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "still narrowing", "question": "ยังต้องการถามอีกไหม?",
             "options": ["A", "B", "C"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state(messages=messages))

        assert result["pending_clarification"] is None  # suppressed
        assert result["current_plan"] is None  # falls through to agent

    def test_clarification_within_budget_is_allowed(self):
        """With fewer than 3 tagged clarifications in history, a new
        clarification is allowed — the cap is 3, not 1."""
        from agent.reason import reason_node
        messages = [
            HumanMessage(content="อยากซื้ออาหารทะเล"),
            AIMessage(content="ประเภทไหน?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="กุ้ง"),
            AIMessage(content="ขนาดไหน?",
                      additional_kwargs={"is_clarification": True}),
            HumanMessage(content="ไม่รู้"),
        ]
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "still ambiguous", "question": "ต้องการแบบไหน?",
             "options": ["ตัวเป็น", "แช่แข็ง", "แปรรูป"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state(messages=messages))

        assert result["pending_clarification"] == {
            "question": "ต้องการแบบไหน?",
            "options": ["ตัวเป็น", "แช่แข็ง", "แปรรูป"],
        }
```

- [ ] **Step 2: Run the new tests to verify the within-budget one fails**

Run: `conda activate MADT && pytest "tests/test_reason.py::TestClarificationGuards::test_clarification_within_budget_is_allowed" "tests/test_reason.py::TestClarificationGuards::test_fourth_clarification_in_session_is_suppressed" -v`

Note: both reworked tests live in the `TestClarificationGuards` class (the same class that held `test_session_wide_clarification_loop_is_suppressed`).

Expected: `test_clarification_within_budget_is_allowed` FAILS (under the current cap of 1, a history with 2 clarifications is suppressed, so `pending_clarification` is `None` instead of the expected dict). `test_fourth_clarification_in_session_is_suppressed` PASSES (3 ≥ 1 is already suppressed — this one is a regression guard).

- [ ] **Step 3: Raise the cap threshold in `agent/reason.py`**

In `agent/reason.py`, find this exact block in `reason_node`:

```python
        # Programmatic guards: even if the LLM ignores its system prompt,
        # never let banned options/questions through and never clarify twice.
        session_msgs = state.get("messages", [])
        if (
            _options_are_banned(options)
            or _question_is_banned(question)
            or _is_scope_confusion_question(question)
            or _already_clarified(session_msgs)
            or _session_clarification_count(session_msgs) >= 1
            or _is_renarrowing_question(question, session_msgs)
        ):
```

Replace it with:

```python
        # Programmatic guards: even if the LLM ignores its system prompt,
        # never let banned options/questions through and never exceed the
        # 3-clarification-per-session cap.
        session_msgs = state.get("messages", [])
        if (
            _options_are_banned(options)
            or _question_is_banned(question)
            or _is_scope_confusion_question(question)
            or _already_clarified(session_msgs)
            or _session_clarification_count(session_msgs) >= 3
            or _is_renarrowing_question(question, session_msgs)
        ):
```

- [ ] **Step 4: Align the system-prompt hard rule in `agent/reason.py`**

In `agent/reason.py`, inside `REASON_SYSTEM_PROMPT`, find this exact text:

```
- After 1 clarification exchange in the conversation, you MUST call
  create_plan — never loop. If the user's reply is still vague, plan with
  best-effort defaults rather than asking again.
```

Replace it with:

```
- After 3 clarification exchanges in the conversation, you MUST call
  create_plan — never loop. If the user's reply is still vague, plan with
  best-effort defaults rather than asking again.
```

- [ ] **Step 5: Run the two tests to verify both pass**

Run: `conda activate MADT && pytest tests/test_reason.py -v -k "within_budget or fourth_clarification"`

Expected: both `test_clarification_within_budget_is_allowed` and `test_fourth_clarification_in_session_is_suppressed` PASS.

- [ ] **Step 6: Run the full reason test file to check for regressions**

Run: `conda activate MADT && pytest tests/test_reason.py -v`

Expected: all tests PASS. In particular `test_second_clarification_in_same_turn_is_suppressed` and `test_clarification_allowed_in_a_later_turn` still pass — they do not depend on the cap value. If any other test asserts the old cap of 1, update it the same way (build 3 tagged clarifications for a "suppressed" expectation).

- [ ] **Step 7: Commit**

```bash
git add agent/reason.py tests/test_reason.py
git commit -m "$(cat <<'EOF'
feat(agent): raise clarification cap to 3 per session

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add "New chat" button to the chat page

**Files:**
- Modify: `app/pages/chat.py` (page body, ~lines 217-218 — the `st.title` / `st.caption` block)

This task has no unit test — Streamlit page rendering is verified manually (Step 3). The change is small and self-contained.

- [ ] **Step 1: Add the "New chat" button next to the page title**

In `app/pages/chat.py`, find this exact block in the page body:

```python
st.title("Thailand Seafood Price Advisor")
st.caption("Ask me anything — I'll clarify if needed, then find the best answer.")
```

Replace it with:

```python
title_col, newchat_col = st.columns([4, 1])
with title_col:
    st.title("Thailand Seafood Price Advisor")
with newchat_col:
    st.write("")  # nudge the button down to roughly align with the title
    if st.button("New chat", use_container_width=True):
        st.session_state["messages"] = [SystemMessage(content=SYSTEM_PROMPT)]
        st.session_state["pending_clarification"] = None
        st.session_state["current_plan"] = None
        st.session_state["last_thinking"] = None
        st.session_state["clarification_round"] = 0
        st.session_state.pop("last_error", None)
        st.rerun()
st.caption("Ask me anything — I'll clarify if needed, then find the best answer.")
```

Note: `SystemMessage` and `SYSTEM_PROMPT` are already imported at the top of `chat.py` (lines 15 and 22) — no new imports needed.

- [ ] **Step 2: Smoke-check the page imports cleanly**

Run: `conda activate MADT && python -c "import ast; ast.parse(open('app/pages/chat.py').read()); print('chat.py parses OK')"`

Expected: prints `chat.py parses OK` (no `SyntaxError`).

- [ ] **Step 3: Manual verification in the running app**

Run: `conda activate MADT && streamlit run app/main.py`

In the browser, on the chat page:
1. Confirm a "New chat" button appears at the top-right, next to the title.
2. Ask a vague query (e.g. `อยากซื้ออาหารทะเล`), answer the clarification options 3 times, and confirm the 4th turn produces a best-effort answer instead of another clarifying question.
3. Click "New chat" — confirm the chat history clears, the welcome screen reappears, and asking a new vague query again offers clarification (fresh budget).

If you cannot run the Streamlit UI in this environment, say so explicitly rather than marking this step done.

- [ ] **Step 4: Commit**

```bash
git add app/pages/chat.py
git commit -m "$(cat <<'EOF'
feat(chat): add New chat button to reset session

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** Cap 1→3 (Task 1, Steps 3 + 5), system-prompt alignment (Task 1, Step 4), stale "never clarify twice" comment (Task 1, Step 3), test rework + companion test (Task 1, Steps 1-2), "answer best-effort when cap hit" — already implemented, asserted by `test_fourth_clarification_in_session_is_suppressed` (`current_plan is None`), "New chat" button (Task 2). All spec sections covered.
- **Out-of-scope items** from the spec (per-intent counter resets, changes to other loop guards / `agent_node` / `SYSTEM_PROMPT` formatting, cross-reload persistence) are intentionally not touched.
- **Type consistency:** `_session_clarification_count`, `reason_node`, `_make_state`, `_ai_with_tool_call` referenced exactly as they exist in the codebase; session-state keys (`messages`, `pending_clarification`, `current_plan`, `last_thinking`, `clarification_round`, `last_error`) match those used elsewhere in `chat.py`.
