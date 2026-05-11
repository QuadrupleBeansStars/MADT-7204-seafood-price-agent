"""Reasoning layer — runs before agent_node on every user turn.

Decides either to ask the user a clarifying question (request_clarification)
or to produce an execution plan (create_plan). Never answers the user directly
and never calls data tools.
"""
import logging

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END
from pydantic import BaseModel, Field

from agent.llm import get_chat_llm

logger = logging.getLogger(__name__)

# ── Internal tool schemas ─────────────────────────────────────────────────────

class _ClarifyInput(BaseModel):
    reasoning: str = Field(description="One sentence explaining what information is missing and why it matters")
    question: str = Field(description="The single most important clarifying question to ask")
    options: list[str] = Field(description="3 to 5 short answer options for the user")


class _PlanInput(BaseModel):
    reasoning: str = Field(description="One sentence explaining why you have enough information to proceed")
    steps: list[str] = Field(
        description="Ordered list of concrete steps using query_seafood_prices, "
                    "get_best_deals, or get_price_trend"
    )


@tool(args_schema=_ClarifyInput)
def request_clarification(reasoning: str, question: str, options: list[str]) -> str:
    """Ask the user one clarifying question with selectable answer options."""
    return "clarification_requested"


@tool(args_schema=_PlanInput)
def create_plan(reasoning: str, steps: list[str]) -> str:
    """Commit to an execution plan before calling data tools."""
    return "plan_created"


_INTERNAL_TOOLS = [request_clarification, create_plan]

# Names the agent must never offer as clarification options. The LLM was
# observed proposing shop names ("ไต้ก๋ง", "Sawasdee Seafood", …) and budget
# bands ("Below ฿500/kg", …) as clickable buttons, which created infinite
# clarification loops in production. The reasoning layer's job is to plan
# around these — never to push the choice onto the user.
_BANNED_OPTION_TOKENS = {
    # Shops
    "ไต้ก๋ง", "sawasdee", "heng heng", "ppnseafood", "supreme",
    "siriratseafood", "sirinfarm", "gulf fresh", "pakpanang", "cha-am",
    # Budget / per-kg price bands
    "thb/kg", "บาท/kg", "฿/kg",
    "below ", "above ",
    # Pieces-per-kg size bands
    "pieces/kg", "ตัวโล", "ตัว/โล",
}


def _options_are_banned(options: list[str]) -> bool:
    """True if any option string contains a banned token (shop / size / budget)."""
    for opt in options:
        low = (opt or "").lower()
        if any(tok in low for tok in _BANNED_OPTION_TOKENS):
            return True
    return False


def _already_clarified(messages: list) -> bool:
    """True if the conversation already contains a persisted clarification.

    Each clarification is stored as an AIMessage with no tool_calls (see
    reason_node below). One round is enough — never ask twice.
    """
    for m in messages:
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            return True
    return False

# ── System prompt ─────────────────────────────────────────────────────────────

REASON_SYSTEM_PROMPT = """\
You are the reasoning layer of a Gulf of Thailand seafood price advisor.

## Language rule (applies to clarifying questions and their options)
Mirror the user's language. If the user wrote in Thai, the clarifying
question and ALL options MUST be in Thai. If in English, both must be
in English. Never ask a Thai user a clarifying question in English.

Examples:
- User: "อยากซื้ออาหารทะเล" → Q: "คุณสนใจอาหารทะเลประเภทไหน?"
  options: ["กุ้ง", "ปลา", "หมึก", "ปู", "หอย"]
- User: "I want to buy some seafood" → Q: "Which category of seafood
  are you interested in?" options: ["shrimp", "fish", "squid", "crab",
  "shellfish"]

## Your only job
Read the conversation and decide ONE of two things:

1. **Have enough information** → call `create_plan` (DEFAULT — prefer this)
   - Write an ordered list of concrete steps using these tools:
     * query_seafood_prices(item, shop?) — look up prices; shop is OPTIONAL
     * get_best_deals(category?) — cheapest items; category is OPTIONAL (omit = all)
     * get_price_trend(item, days=7) — history / cross-shop spread for an item
     * get_talaadthai_benchmark(species) — wholesale Talaad Thai reference price
     * get_oil_context(species?) — diesel↔seafood correlation context
     * generate_oil_briefing(period, language) — oil briefing markdown
   - Be specific: name the item, shop, or category in each step

2. **Need more information** → call `request_clarification` (RARE — only if truly ambiguous)
   - Ask the single most important missing piece
   - Provide 3–5 short, specific options
   - Do NOT ask multiple questions at once
   - Do NOT ask if the information is already in the conversation

## Forbidden clarifications (NEVER ask the user about these)
The agent must resolve all of these on its own. Asking the user about
them is over-engineering and creates clarification loops:

- **Which shop** — the agent compares ALL shops automatically
- **Which size / weight range / pieces-per-kg** — Best-Match in
  query_seafood_prices already picks the highest-liquidity size
- **Budget range** — irrelevant; the agent always returns the cheapest
  landed-cost option
- **Which market to compare against** — Talaad Thai is the only
  benchmark; never offer a market choice
- **Which species (when user gave a generic term)** — query_seafood_prices
  resolves "กุ้ง" → "Vannamei Shrimp L" via Best-Match. Plan with the
  generic term and let the tool decide.

## When to plan vs clarify
ALWAYS plan if the user names ANY of: a category (กุ้ง, fish, squid…),
a specific item (tiger prawn, salmon…), an intent (deals, trend, quote,
briefing, benchmark), or a quantity (e.g. "30 kg shrimp"). Missing
optional parameters are NOT a reason to clarify.

ONLY clarify when the request has no item AND no clear intent, e.g.:
   - "I want to buy some seafood" → ask which category
   - "Help me decide" → ask what they're deciding between

## Examples
- "How much is tiger prawn?" → PLAN: query_seafood_prices(item="tiger prawn")
- "Compare salmon prices across all shops" → PLAN: get_price_trend(item="salmon")
- "What are today's best seafood deals?" → PLAN: get_best_deals()
- "มีกุ้งลดราคาอยู่ไหม?" → PLAN: get_best_deals(category="shrimp")
- "Give me this week's oil briefing in English." → PLAN: generate_oil_briefing(period="weekly", language="en")
- "How does diesel affect shrimp prices?" → PLAN: get_oil_context(species="shrimp")
- "Wholesale Talaad Thai price for white shrimp" → PLAN: get_talaadthai_benchmark(species="กุ้งขาว")
- "How much is lobster?" → PLAN: query_seafood_prices(item="lobster")  (let tool report no match)
- "ฉันต้องสั่งกุ้ง ปลาหมึก และปลากะพง ร้านไหนถูกที่สุดแต่ละอย่าง?" →
  PLAN: query_seafood_prices(item="กุ้ง") + query_seafood_prices(item="ปลาหมึก") + query_seafood_prices(item="ปลากะพง")
  (Don't ask for subtypes — the category-level item names are valid input.)
- "ราคากุ้งลายเสือเทียบกับตลาด" → PLAN: query_seafood_prices(item="กุ้งลายเสือ")
  + get_talaadthai_benchmark(species="กุ้งลายเสือ")
  (NEVER ask "which market?" — Talaad Thai is the only benchmark.)
- "ถ้าฉันซื้อกุ้ง 30 กก กับปลาหมึก 20 กก วันนี้จ่ายเท่าไหร่" →
  PLAN: get_purchase_quote(items=[{"species":"กุ้ง","qty_kg":30},
                                   {"species":"ปลาหมึก","qty_kg":20}])
  (NEVER ask for subtype, size, or shop — the quote tool resolves all of it.)
- "อยากลดต้นทุนวัตถุดิบในสัปดาห์นี้ Agent มีแผนการจัดซื้อแนะนำไหม?" →
  PLAN: get_best_deals() + get_oil_context()  (then synthesize a plan.)
- "I want to buy some seafood" → CLARIFY: which category?

## Conversation continuity
If the previous assistant message was a clarifying question and the user's
latest message is a short answer (a category, an item name, a button label),
TREAT IT AS THE ANSWER and plan immediately. NEVER re-ask the same question.

## Hard rules
- You MUST call exactly one tool per response: either request_clarification or create_plan
- Never answer the user directly in text — always use a tool
- Never call data tools yourself
- Always fill in the `reasoning` field to explain your decision in one sentence
- After 1 clarification exchange in the conversation, you MUST call
  create_plan — never loop. If the user's reply is still vague, plan with
  best-effort defaults rather than asking again.

## Available categories (the ONLY valid clarification options for "what kind?")
shrimp (กุ้ง), fish (ปลา), squid (หมึก), crab (ปู), shellfish (หอย)
"""

# ── LLM factory (extracted for test-patching) ────────────────────────────────

def _build_reason_llm():
    # tool_choice="any" works on both Anthropic and OpenAI via langchain
    # (mapped to OpenAI's "required" under the hood for Azure/OpenAI).
    return get_chat_llm().bind_tools(_INTERNAL_TOOLS, tool_choice="any")


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

    # Parse tool call
    tool_calls = getattr(response, "tool_calls", []) or []
    if not tool_calls:
        logger.warning("reason_node: no tool called, routing to agent as fallback")
        return updates

    call = tool_calls[0]
    updates["last_thinking"] = call["args"].get("reasoning")

    if call["name"] == "request_clarification":
        question = call["args"]["question"]
        options = call["args"]["options"]

        # Programmatic guards: even if the LLM ignores its system prompt,
        # never let banned options through and never clarify twice.
        if _options_are_banned(options) or _already_clarified(state.get("messages", [])):
            logger.info(
                "reason_node: suppressing clarification "
                "(already_clarified=%s, banned=%s) — routing to agent",
                _already_clarified(state.get("messages", [])),
                _options_are_banned(options),
            )
            return updates  # both None → falls through to agent_node

        updates["pending_clarification"] = {
            "question": question,
            "options": options,
        }
        # Persist the clarifying question as an AI turn so the next
        # reason_node call sees a proper user→assistant→user sequence
        # instead of two consecutive HumanMessages (which caused the
        # model to treat the user's button click as a fresh ambiguous
        # query and re-ask the same clarification — clarification loop).
        updates["messages"] = [AIMessage(content=question)]
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
