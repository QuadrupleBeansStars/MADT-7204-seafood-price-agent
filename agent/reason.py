"""Reasoning layer — runs before agent_node on every user turn.

Decides either to ask the user a clarifying question (request_clarification)
or to produce an execution plan (create_plan). Never answers the user directly
and never calls data tools.
"""
import logging

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
