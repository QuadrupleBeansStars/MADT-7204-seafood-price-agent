# Reasoning Loop Design
**Date:** 2026-04-25
**Project:** MADT 7204 — Seafood Price Advisor

---

## Context

The current agent is a standard LangGraph ReAct loop: user message → agent node → tools → agent node → answer. It has no mechanism to recognise ambiguous queries or gather missing intent before acting. Users often ask open-ended questions ("build me a shopping list", "cheapest fish") that require clarification before any meaningful tool call can be made.

This design adds an explicit reasoning layer before the agent acts. The result is a full agentic loop: **perceive → reason → clarify (if needed, repeatedly) → plan → execute → respond**. This qualifies the system as both a reasoning agent and a planner agent.

---

## Desired Behaviour

**Ambiguous query:**
```
User:   cheapest fish
REASON: missing specifics → clarify
  Q: Which fish?   [Salmon] [Sea Bass] [Grouper] [Mackerel] [Other]
User:   *taps Salmon*
REASON: enough info → plan
  Plan: 1. query salmon prices across all shops
        2. rank by price_per_kg
        3. highlight best deal + link
→ tools → answer
```

**Complex query:**
```
User:   build me a shopping list for dinner
REASON: missing info → clarify
  Q: How many people?   [2–4] [5–10] [10+]
User:   *taps 5–10*
REASON: still missing → clarify
  Q: Budget per person?   [฿100–200] [฿200–400] [฿400+]
User:   *taps ฿200–400*
REASON: enough info → plan
  Plan: 1. query shrimp prices
        2. query fish prices
        3. filter to ฿200–400/head for 8 people
        4. rank by value + transport cost
        5. compile list
→ tools → answer
```

**Clear query (no clarification needed):**
```
User:   tiger prawn price at PPNSeafood
REASON: intent clear → plan immediately
  Plan: 1. query tiger prawn at PPNSeafood
→ tools → answer
```

---

## Architecture

### Graph (agent/main.py)

```
START
  │
  ▼
reason_node  ──── calls request_clarification ──▶  STOP (wait for user click)
  │                                                      │
  │                                              user clicks button
  │                                              injected as HumanMessage
  │◀─────────────────────────────────────────────────────┘
  │
  │──── calls create_plan ──▶  agent_node ──▶  tools ──▶  agent_node ──▶  END
```

The graph loops back to `reason_node` after each clarification round. The reason node keeps running until it calls `create_plan`, at which point control passes to the existing `agent_node`.

### New State Fields (AgentState)

```python
class AgentState(TypedDict):
    messages:             Annotated[list, add_messages]  # existing
    pending_clarification: dict | None   # {question, options} if waiting
    current_plan:          list[str] | None  # plan steps once resolved
```

### Nodes

**`reason_node`** — new, runs first on every user message
- Uses `claude-sonnet-4-5` with `extended_thinking` enabled (budget: 1500 tokens)
- Bound with two internal tools only: `request_clarification` and `create_plan`
- Temperature must be 1 (Anthropic requirement for extended thinking)
- **Always resets `pending_clarification=None` and `current_plan=None` at the start** — prevents stale state from a previous turn bleeding into the current one
- If it calls `request_clarification(question, options[])`:
  - Sets `pending_clarification` in state
  - Graph routes to END (Streamlit waits for button click)
- If it calls `create_plan(steps[])`:
  - Sets `current_plan` in state
  - Graph routes to `agent_node`

**`agent_node`** — existing, unchanged except:
- Plan steps injected as a SystemMessage prefix before tool calls: `"Execution plan:\n1. …\n2. …"`
- This guides Claude to follow the plan rather than re-derive it

**`tools` node** — existing, unchanged

### Routing

```python
def route_reason(state) -> str:
    if state.get("pending_clarification"):
        return END          # stop, render buttons in UI
    return "agent"          # proceed to execution
```

---

## New Files

### `agent/reason.py`
Contains:
- `REASON_SYSTEM_PROMPT` — instructs Claude to assess completeness, ask one question at a time, or produce a numbered action plan
- `request_clarification` tool schema (question: str, options: list[str])
- `create_plan` tool schema (steps: list[str])
- `reason_node(state) -> dict` function

The two internal tool schemas (`request_clarification`, `create_plan`) live inside `agent/reason.py` — no separate file needed. They must never be added to `agent/tools/__init__.py`'s `ALL_TOOLS` list, which is bound only to `agent_node`.

---

## Changes to Existing Files

### `agent/main.py`
- Import `reason_node`, `route_reason` from `agent/reason.py`
- Add `pending_clarification` and `current_plan` to `AgentState`
- Register `reason_node` in the graph
- Add `START → reason_node` edge (replaces `START → agent`)
- Add conditional edge `reason_node → route_reason`
- Keep all existing edges unchanged

### `app/pages/chat.py`
Three rendering additions in the assistant message loop:

1. **Thinking block** — if response contains `thinking` content blocks:
   ```
   ▶ Reasoning  (collapsed by default)
     [Claude's thinking text]
   ```

2. **Action plan** — if `current_plan` in state:
   ```
   ▶ Action plan  (collapsed by default)
     1. query shrimp prices across all shops
     2. filter by budget …
   ```

3. **Clarification buttons** — if `pending_clarification` in state:
   ```
   Which fish are you looking for?
   [Salmon]  [Sea Bass]  [Grouper]  [Mackerel]  [Other…]
   ```
   Each button click calls `st.session_state` to inject the selected value as a `HumanMessage` and triggers `st.rerun()`.

Button state must be cleared from `AgentState` after the user clicks so the buttons don't re-render on the next turn.

---

## Reason System Prompt (summary)

```
You are the reasoning layer of a seafood price advisor agent.

Your job:
1. Read the conversation so far.
2. Decide if you have enough information to act.
   - If NOT: call request_clarification with ONE question and 3–5 short options.
     Ask only the most important missing piece. Do not ask multiple questions at once.
   - If YES: call create_plan with a numbered list of concrete steps using
     the available tools (query_seafood_prices, get_best_deals, get_price_trend).

Never answer the user directly. Never call data tools. Only call request_clarification
or create_plan.
```

---

## Extended Thinking Configuration

```python
llm = ChatAnthropic(
    model="claude-sonnet-4-5",
    temperature=1,           # required for extended thinking
    thinking={
        "type": "enabled",
        "budget_tokens": 1500,
    },
)
```

Thinking content blocks are surfaced in the response and rendered in the collapsible UI expander.

---

## Error Handling

- If `reason_node` returns neither tool call (e.g. outputs plain text): fall back to `agent_node` directly, log a warning
- If extended thinking API call fails: fall back to reason_node without thinking (standard call), flag in UI
- If clarification round exceeds 3 loops without resolving: proceed to `create_plan` with best available context, note uncertainty in plan

---

## Verification

1. `conda activate MADT && streamlit run app/main.py`
2. Type `"cheapest fish"` → confirm clarification buttons appear, thinking expander visible
3. Click a button → confirm it injects as a message, buttons disappear, plan expander appears, tools run, answer returned
4. Type `"compare tiger prawn prices"` → confirm no clarification, plan appears directly, tools run
5. Type `"build me a shopping list for a restaurant"` → confirm multi-round clarification (2–3 questions) before plan
6. Confirm thinking expander is collapsed by default, expandable on click
7. Confirm plan expander is collapsed by default, expandable on click
