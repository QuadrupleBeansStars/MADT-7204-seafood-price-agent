# Reasoning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reason_node to the LangGraph agent that uses extended thinking to decide whether to ask the user a clarifying question (rendered as clickable buttons) or create an execution plan before calling data tools.

**Architecture:** A new `reason_node` runs before `agent_node` on every user message. It resets clarification/plan state, calls Claude with extended thinking bound to two internal tools (`request_clarification`, `create_plan`), and routes to END (show buttons) or `agent_node` (execute plan). `chat.py` reads the extra state fields after each graph run and renders thinking, plan, and clarification UI.

**Tech Stack:** LangGraph, LangChain Anthropic (`langchain-anthropic>=0.3.0`), Streamlit, pytest + unittest.mock

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `tests/__init__.py` | makes tests a package |
| Create | `tests/test_reason.py` | unit tests for reason_node and routing |
| Create | `agent/reason.py` | internal tools, REASON_SYSTEM_PROMPT, reason_node |
| Modify | `agent/main.py` | AgentState + new fields, register reason_node, routing |
| Modify | `app/pages/chat.py` | pass full state, render thinking/plan/buttons |
| Modify | `requirements.txt` | add pytest |

---

## Task 1: Add pytest and test scaffold

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_reason.py`

- [ ] **Step 1: Add pytest to requirements**

Open `requirements.txt` and append:
```
pytest>=8.0.0
pytest-mock>=3.0.0
```

- [ ] **Step 2: Create the tests package**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 3: Write failing test scaffold**

Create `tests/test_reason.py`:

```python
"""Unit tests for agent/reason.py — reason_node and route_reason."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_state(messages=None, pending_clarification=None, current_plan=None, last_thinking=None):
    return {
        "messages": messages or [HumanMessage(content="cheapest fish")],
        "pending_clarification": pending_clarification,
        "current_plan": current_plan,
        "last_thinking": last_thinking,
    }


def _ai_with_tool_call(tool_name: str, args: dict) -> AIMessage:
    """Return an AIMessage that looks like Claude called a tool."""
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "args": args, "id": "call_123"}]
    return msg


# ── reason_node ───────────────────────────────────────────────────────────────

class TestReasonNode:

    def test_sets_pending_clarification_when_llm_calls_request_clarification(self):
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"question": "Which fish?", "options": ["Salmon", "Sea Bass", "Grouper"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] == {
            "question": "Which fish?",
            "options": ["Salmon", "Sea Bass", "Grouper"],
        }
        assert result["current_plan"] is None

    def test_sets_current_plan_when_llm_calls_create_plan(self):
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "create_plan",
            {"steps": ["query salmon prices", "rank by price_per_kg", "return best deal"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["current_plan"] == [
            "query salmon prices",
            "rank by price_per_kg",
            "return best deal",
        ]
        assert result["pending_clarification"] is None

    def test_always_resets_stale_state(self):
        """Even if previous state had pending_clarification, a new plan run clears it."""
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "create_plan",
            {"steps": ["query tiger prawn prices"]},
        )
        stale_state = _make_state(
            pending_clarification={"question": "old Q", "options": ["A"]},
            current_plan=["old step"],
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(stale_state)

        assert result["pending_clarification"] is None
        assert result["current_plan"] == ["query tiger prawn prices"]

    def test_falls_back_gracefully_when_no_tool_called(self):
        """If Claude returns plain text (no tool call), state has no plan/clarification."""
        from agent.reason import reason_node
        mock_response = AIMessage(content="I am not sure what to do.")
        mock_response.tool_calls = []
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] is None
        assert result["current_plan"] is None


# ── route_reason ──────────────────────────────────────────────────────────────

class TestRouteReason:

    def test_returns_end_when_pending_clarification_set(self):
        from agent.reason import route_reason
        from langgraph.graph import END
        state = _make_state(pending_clarification={"question": "Which fish?", "options": ["Salmon"]})
        assert route_reason(state) == END

    def test_returns_agent_when_current_plan_set(self):
        from agent.reason import route_reason
        state = _make_state(current_plan=["step 1"])
        assert route_reason(state) == "agent"

    def test_returns_agent_when_both_none_fallback(self):
        from agent.reason import route_reason
        state = _make_state()
        assert route_reason(state) == "agent"
```

- [ ] **Step 4: Run tests to confirm they all fail (import error expected)**

```bash
conda run -n MADT pytest tests/test_reason.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'reason_node' from 'agent.reason'` (module doesn't exist yet — that's correct).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py tests/test_reason.py
git commit -m "test: add failing tests for reason_node and route_reason"
```

---

## Task 2: Create `agent/reason.py` — tool schemas, prompt, and reason_node

**Files:**
- Create: `agent/reason.py`

- [ ] **Step 1: Create `agent/reason.py`**

```python
"""Reasoning layer — runs before agent_node on every user turn.

Decides either to ask the user a clarifying question (request_clarification)
or to produce an execution plan (create_plan). Never answers the user directly
and never calls data tools.
"""
import logging
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Internal tool schemas ─────────────────────────────────────────────────────

class _ClarifyInput(BaseModel):
    question: str = Field(description="The single most important clarifying question to ask")
    options: list[str] = Field(description="3 to 5 short answer options for the user")


class _PlanInput(BaseModel):
    steps: list[str] = Field(
        description="Ordered list of concrete steps using query_seafood_prices, "
                    "get_best_deals, or get_price_trend"
    )


@tool(args_schema=_ClarifyInput)
def request_clarification(question: str, options: list[str]) -> str:
    """Ask the user one clarifying question with selectable answer options."""
    return "clarification_requested"


@tool(args_schema=_PlanInput)
def create_plan(steps: list[str]) -> str:
    """Commit to an execution plan before calling data tools."""
    return "plan_created"


_INTERNAL_TOOLS = [request_clarification, create_plan]

# ── System prompt ─────────────────────────────────────────────────────────────

REASON_SYSTEM_PROMPT = """\
You are the reasoning layer of a Gulf of Thailand seafood price advisor.

## Your only job
Read the conversation and decide ONE of two things:

1. **Need more information** → call `request_clarification`
   - Ask the single most important missing piece
   - Provide 3–5 short, specific options (e.g. fish names, budget ranges, party sizes)
   - Do NOT ask multiple questions at once
   - Do NOT ask if the information is already in the conversation

2. **Have enough information** → call `create_plan`
   - Write an ordered list of concrete steps using these tools:
     * query_seafood_prices — look up prices for a specific item / shop / category
     * get_best_deals — find the cheapest items across all shops
     * get_price_trend — show price history for an item
   - Be specific: name the item, shop, or category in each step

## Hard rules
- You MUST call exactly one tool per response: either request_clarification or create_plan
- Never answer the user directly
- Never call data tools yourself
- If in doubt, create a plan — do not over-clarify
- After 3 clarification exchanges in the conversation, you MUST call create_plan regardless

## Available shops
ไต้ก๋ง ซีฟู้ด, Sawasdee Seafood, HENG HENG Seafood, PPNSeafood,
supreme seafoods, siriratseafood, sirinfarm,
Gulf Fresh Co., PakPanang Direct, Cha-Am Seafood

## Available categories
shrimp (กุ้ง), fish (ปลา), squid (หมึก), crab (ปู), shellfish (หอย)
"""

# ── LLM factory (extracted for test-patching) ────────────────────────────────

def _build_reason_llm():
    llm = ChatAnthropic(
        model="claude-sonnet-4-5",
        temperature=1,
        thinking={"type": "enabled", "budget_tokens": 1500},
    )
    return llm.bind_tools(_INTERNAL_TOOLS, tool_choice="any")


# ── Node ──────────────────────────────────────────────────────────────────────

def reason_node(state: dict) -> dict:
    """Reasoning node — resets clarification/plan state then decides: clarify or plan."""
    # Always start clean so stale state from a previous turn never bleeds through
    updates: dict = {
        "pending_clarification": None,
        "current_plan": None,
        "last_thinking": None,
    }

    messages = state.get("messages", [])
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=REASON_SYSTEM_PROMPT)] + list(messages)
    else:
        messages = [SystemMessage(content=REASON_SYSTEM_PROMPT)] + list(messages[1:])

    llm = _build_reason_llm()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.warning("reason_node: LLM call failed, falling back to agent", exc_info=True)
        return updates  # both None → route_reason sends to agent

    # Extract extended thinking text if present
    if isinstance(response.content, list):
        thinking_parts = [
            b.get("thinking", "")
            for b in response.content
            if isinstance(b, dict) and b.get("type") == "thinking"
        ]
        if thinking_parts:
            updates["last_thinking"] = "\n\n".join(thinking_parts)

    # Parse tool call
    tool_calls = getattr(response, "tool_calls", []) or []
    if not tool_calls:
        logger.warning("reason_node: no tool called, routing to agent as fallback")
        return updates

    call = tool_calls[0]
    if call["name"] == "request_clarification":
        updates["pending_clarification"] = {
            "question": call["args"]["question"],
            "options": call["args"]["options"],
        }
    elif call["name"] == "create_plan":
        updates["current_plan"] = call["args"]["steps"]
    else:
        logger.warning("reason_node: unexpected tool %s, routing to agent", call["name"])

    return updates


# ── Router ────────────────────────────────────────────────────────────────────

def route_reason(state: dict) -> str:
    """Route to END (show clarification buttons) or 'agent' (execute plan)."""
    if state.get("pending_clarification"):
        return END
    return "agent"
```

- [ ] **Step 2: Run the tests**

```bash
conda run -n MADT pytest tests/test_reason.py -v 2>&1
```

Expected: all 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add agent/reason.py
git commit -m "feat: add reason_node with extended thinking and internal tools"
```

---

## Task 3: Update `agent/main.py` — state fields, register reason_node, routing

**Files:**
- Modify: `agent/main.py`

- [ ] **Step 1: Update `AgentState` to include new fields**

In `agent/main.py`, replace the `AgentState` class:

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    pending_clarification: Optional[dict]   # {question, options} — set by reason_node
    current_plan: Optional[list]            # list[str] — set by reason_node
    last_thinking: Optional[str]            # extended thinking text — set by reason_node
```

Add `from typing import Optional` to imports at the top of the file.

- [ ] **Step 2: Update `agent_node` to inject plan as context**

Replace the existing `agent_node` function:

```python
def agent_node(state: AgentState) -> dict:
    """LLM reasoning node — executes the plan produced by reason_node."""
    llm = get_llm()
    messages = list(state["messages"])

    plan = state.get("current_plan")
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    else:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages[1:]

    if plan:
        plan_text = "Execution plan (follow these steps in order):\n" + "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(plan)
        )
        messages = [messages[0], SystemMessage(content=plan_text)] + messages[1:]

    response = llm.invoke(messages)
    return {"messages": [response]}
```

- [ ] **Step 3: Update `build_graph` to wire in reason_node**

Replace the `build_graph` function:

```python
def build_graph():
    """Build the LangGraph agent with reason → (clarify | plan → tools) flow."""
    from agent.reason import reason_node, route_reason

    graph = StateGraph(AgentState)

    graph.add_node("reason", reason_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "reason")
    graph.add_conditional_edges(
        "reason",
        route_reason,
        {END: END, "agent": "agent"},
    )
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()
```

- [ ] **Step 4: Verify the graph compiles without error**

```bash
conda run -n MADT python -c "
from agent.main import build_graph
g = build_graph()
print('Graph OK:', list(g.nodes.keys()))
"
```

Expected output:
```
Graph OK: ['__start__', 'reason', 'agent', 'tools']
```

- [ ] **Step 5: Run all tests to confirm nothing broke**

```bash
conda run -n MADT pytest tests/test_reason.py -v
```

Expected: all 7 PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/main.py
git commit -m "feat: wire reason_node into LangGraph with plan injection"
```

---

## Task 4: Update `chat.py` — pass full state and render thinking + plan + buttons

**Files:**
- Modify: `app/pages/chat.py`

This task has no unit tests — Streamlit rendering is verified visually in Task 5.

- [ ] **Step 1: Update `_invoke_agent` to pass and read full graph state**

Replace the `_invoke_agent` function:

```python
def _invoke_agent(user_text: str) -> None:
    graph = _graph()
    handler = _langfuse()
    config = {"callbacks": [handler]} if handler else {}

    messages = st.session_state.get("messages", [SystemMessage(content=SYSTEM_PROMPT)])
    messages.append(HumanMessage(content=user_text))

    try:
        spinner_msg = "🐟 Thinking..."
        with st.spinner(spinner_msg):
            result = graph.invoke(
                {
                    "messages": messages,
                    "pending_clarification": None,
                    "current_plan": None,
                    "last_thinking": None,
                },
                config=config,
            )
        st.session_state["messages"] = result["messages"]
        st.session_state["pending_clarification"] = result.get("pending_clarification")
        st.session_state["current_plan"] = result.get("current_plan")
        st.session_state["last_thinking"] = result.get("last_thinking")
        st.session_state.pop("last_error", None)
    except Exception as exc:
        st.session_state["last_error"] = repr(exc)
```

- [ ] **Step 2: Add `_render_thinking_expander` helper**

Add this function after `_render_tool_expander`:

```python
def _render_thinking_expander(thinking: str | None) -> None:
    if not thinking:
        return
    with st.expander("Reasoning", expanded=False, icon=":material/psychology:"):
        st.markdown(thinking)


def _render_plan_expander(plan: list | None) -> None:
    if not plan:
        return
    with st.expander("Action plan", expanded=False, icon=":material/list:"):
        for i, step in enumerate(plan, 1):
            st.markdown(f"{i}. {step}")
```

- [ ] **Step 3: Add `_render_clarification` helper**

Add this function after `_render_plan_expander`:

```python
def _render_clarification(clarification: dict | None) -> None:
    """Render the clarifying question and clickable option buttons."""
    if not clarification:
        return
    with st.chat_message("assistant"):
        st.markdown(f"**{clarification['question']}**")
        cols = st.columns(len(clarification["options"]))
        for idx, option in enumerate(clarification["options"]):
            with cols[idx]:
                if st.button(option, use_container_width=True, key=f"clarify_{idx}_{option}"):
                    # Inject user's choice as a HumanMessage and continue
                    st.session_state["pending_clarification"] = None
                    st.session_state["pending_prompt"] = option
                    st.rerun()
```

- [ ] **Step 4: Update the page body to render thinking, plan, and clarification**

Replace the page body section (everything after `if "messages" not in st.session_state:`) with:

```python
if "messages" not in st.session_state:
    st.session_state["messages"] = [SystemMessage(content=SYSTEM_PROMPT)]

# Consume a queued prompt (example button click or clarification button click)
if prompt := st.session_state.pop("pending_prompt", None):
    _invoke_agent(prompt)

non_system = [m for m in st.session_state["messages"] if not isinstance(m, SystemMessage)]
if not non_system:
    _render_welcome()
else:
    _render_history(st.session_state["messages"])

# Render reasoning and plan expanders after the history
_render_thinking_expander(st.session_state.get("last_thinking"))
_render_plan_expander(st.session_state.get("current_plan"))

# Render clarification buttons (if agent is waiting for user input)
_render_clarification(st.session_state.get("pending_clarification"))

if err := st.session_state.get("last_error"):
    st.error("Something went wrong while contacting the agent.")
    with st.expander("Details"):
        st.code(err)

if user_input := st.chat_input("e.g. Which shop has cheapest white shrimp today?"):
    # Clear previous reasoning state before new query
    st.session_state["pending_clarification"] = None
    st.session_state["current_plan"] = None
    st.session_state["last_thinking"] = None
    _invoke_agent(user_input)
    st.rerun()
```

- [ ] **Step 5: Update the page title caption**

Replace line:
```python
st.caption("Ask me about seafood prices, best deals, or build a shopping list.")
```
with:
```python
st.caption("Ask me anything — I'll clarify if needed, then find the best answer.")
```

- [ ] **Step 6: Commit**

```bash
git add app/pages/chat.py
git commit -m "feat: render thinking, plan, and clarification buttons in chat UI"
```

---

## Task 5: End-to-end verification

**Files:** none — manual testing only

- [ ] **Step 1: Start the app**

```bash
conda activate MADT && streamlit run app/main.py
```

- [ ] **Step 2: Test ambiguous query → clarification → plan → answer**

Type: `cheapest fish`

Expected sequence:
1. Spinner shows "🐟 Thinking..."
2. Assistant bubble appears with a bold question e.g. "Which fish are you looking for?"
3. Option buttons appear (Salmon, Sea Bass, Grouper, etc.)
4. Click one button — it disappears, spinner re-appears
5. "Reasoning" expander appears (collapsed) — click to see thinking text
6. "Action plan" expander appears (collapsed) — click to see numbered steps
7. Tool calls expander appears with data query results
8. Final answer appears with prices

- [ ] **Step 3: Test clear query → no clarification**

Type: `tiger prawn price at PPNSeafood`

Expected:
1. No clarification buttons
2. "Reasoning" expander visible (collapsed)
3. "Action plan" expander visible (collapsed)
4. Tools run, answer appears directly

- [ ] **Step 4: Test multi-round clarification**

Type: `build me a shopping list`

Expected:
1. First clarification: party size buttons
2. Click one → second clarification: budget buttons
3. Click one → plan appears, tools run, shopping list returned

- [ ] **Step 5: Test that example prompt buttons still work**

Click "🦐 ดีลวันนี้" on the welcome screen — confirm full flow completes without error.

- [ ] **Step 6: Run unit tests one final time**

```bash
conda run -n MADT pytest tests/test_reason.py -v
```

Expected: 7/7 PASS.

- [ ] **Step 7: Push to remote**

```bash
git push origin main
```
