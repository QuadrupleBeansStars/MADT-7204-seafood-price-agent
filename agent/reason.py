"""Reasoning layer — runs before agent_node on every user turn.

Decides either to ask the user a clarifying question (request_clarification)
or to produce an execution plan (create_plan). Never answers the user directly
and never calls data tools.
"""
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END
from pydantic import BaseModel, Field

from agent.llm import get_chat_llm
from data.transport_rates import TRANSPORT_RATES

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

# Tokens we must never see in clarification options. The LLM was observed
# proposing shop names ("ไต้ก๋ง", …) and budget bands ("Below ฿500/kg", …)
# as clickable buttons, which created infinite clarification loops in
# production. Shop tokens are derived from TRANSPORT_RATES so adding a new
# shop there automatically extends this guard — no second source of truth.
_BANNED_OPTION_TOKENS: set[str] = (
    {s.lower() for s in TRANSPORT_RATES.keys()}
    | {
        # Budget / per-kg price bands
        "thb/kg", "บาท/kg", "฿/kg",
        "below ", "above ",
        # Pieces-per-kg size bands
        "pieces/kg", "ตัวโล", "ตัว/โล",
        # Shipping yes/no — Total Landed Cost is always default
        "free shipping", "ฟรีค่าขนส่ง", "include shipping",
        "รวมค่าขนส่ง", "รวมขนส่ง",
    }
)

# Banned phrases in the clarification QUESTION text itself (not the options).
# These are the shapes of question we observed looping in production:
# "Which shop would you like to compare?", "Which other shops…?",
# "Would you like to include shipping costs?", "What is the shipping rate
# for X?", "ร้านไหนที่จะเทียบ", "ร้านอื่นล่ะ".
_BANNED_QUESTION_PHRASES: tuple[str, ...] = (
    # Shop selection — agent must compare ALL shops
    "which shop", "which shops", "which other shop", "from which shop",
    "ร้านไหน", "ร้านอื่น", "เลือกร้าน",
    # Shipping — Total Landed Cost is always included by default
    "shipping cost", "shipping rate", "include shipping",
    "ค่าขนส่ง", "รวมค่าขนส่ง", "รวมขนส่ง",
    # Market choice — Talaad Thai is the only benchmark
    "which market", "ตลาดไหน",
)

# Out-of-scope category tokens. Asking the user "Are you looking for
# seafood OR pork prices?" mixes an in-scope category with an out-of-scope
# one — the answer is always "the out-of-scope thing", and the agent
# should reply with a 1-turn scope statement instead. PDF Issue F:
# user asked "ราคาเนื้อหมู?", agent looped this question 3 times then
# gave up. We catch the shape regardless of the option list because the
# loop happens whether options are ["Pork", "Seafood"] or ["Yes", "No"].
_OUT_OF_SCOPE_TOKENS: tuple[str, ...] = (
    "pork", "เนื้อหมู",
    "chicken", "เนื้อไก่",
    "beef", "เนื้อวัว",
    "vegetable", "ผัก",
    "facebook",
)


def _is_scope_confusion_question(question: str) -> bool:
    """Detect 'in-scope OR out-of-scope?' clarification loops.

    Fires when the question text mentions BOTH something we cover
    (seafood/ซีฟู้ด, or one of our 5 categories) AND an out-of-scope
    token. Such questions ARE the loop pattern from PDF Issue F —
    the user's answer cannot give us anything useful.
    """
    low = (question or "").lower()
    has_in_scope = any(
        tok in low for tok in (
            "seafood", "ซีฟู้ด", "shrimp", "กุ้ง", "fish ", "ปลา",
            "squid", "หมึก", "crab", "ปู ", "shellfish", "หอย",
        )
    )
    has_out_of_scope = any(tok in low for tok in _OUT_OF_SCOPE_TOKENS)
    return has_in_scope and has_out_of_scope


def _options_are_banned(options: list[str]) -> bool:
    """True if any option string contains a banned token (shop / size / budget)."""
    for opt in options:
        low = (opt or "").lower()
        if any(tok in low for tok in _BANNED_OPTION_TOKENS):
            return True
    return False


def _question_is_banned(question: str) -> bool:
    """True if the clarification's QUESTION text matches a banned shape.

    This catches loops where the LLM phrased a banned ask (Which shop?
    Include shipping?) but supplied innocuous-looking options like
    "Yes/No" that wouldn't trigger the option-token guard.
    """
    low = (question or "").lower()
    return any(phrase in low for phrase in _BANNED_QUESTION_PHRASES)


def _already_clarified(messages: list) -> bool:
    """True if THIS TURN already produced a clarification.

    A "turn" is the slice of messages from the most-recent HumanMessage
    onward — i.e. since the user last spoke. Within a single turn we
    refuse to clarify twice (that's how loops formed). But earlier turns
    in the same session must NOT count: the agent_node also produces
    AIMessages without tool_calls (final answers), and treating those as
    prior clarifications would block all further clarifications for the
    rest of the session.
    """
    # Find the most recent HumanMessage and only inspect messages after it.
    last_user_idx = -1
    for i, m in enumerate(messages):
        if isinstance(m, HumanMessage):
            last_user_idx = i
    current_turn = messages[last_user_idx + 1:] if last_user_idx >= 0 else messages
    for m in current_turn:
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            return True
    return False


def _session_clarification_count(messages: list) -> int:
    """Count clarifications already asked anywhere in the session.

    `_already_clarified` only sees the current turn, so it cannot stop a
    loop that spans turns: every option-button click is a fresh
    HumanMessage, which resets the "current turn" window, so the LLM was
    free to clarify again and again (screenshot loop: ปูม้า → ปูม้าสด →
    เนื้อปูม้าสด → … each click triggering another "ประเภทไหน?").

    reason_node tags each persisted clarification AIMessage with
    additional_kwargs["is_clarification"]; this counts those tags across
    the WHOLE history. Plain-text answers from agent_node are untagged,
    so they never inflate the count.
    """
    return sum(
        1
        for m in messages
        if isinstance(m, AIMessage)
        and getattr(m, "additional_kwargs", {}).get("is_clarification")
    )


def _is_renarrowing_question(question: str, messages: list) -> bool:
    """True if the question just echoes the user's last answer back at them.

    The screenshot loop: the user clicks "ปูม้าสด", and the next
    clarification is "คุณต้องการปูม้าสดประเภทไหน?" — the button label is
    literally a substring of the new question. That shape is always a
    re-narrowing loop: the user already answered, the agent should plan
    with that answer instead of asking a longer version of the same Q.
    """
    last_user = None
    for m in messages:
        if isinstance(m, HumanMessage):
            last_user = m
    if last_user is None:
        return False
    answer = (last_user.content or "").strip()
    # Require a non-trivial answer so a stray 1-2 char message can't match.
    if len(answer) < 3:
        return False
    return answer.lower() in (question or "").lower()

# ── System prompt ─────────────────────────────────────────────────────────────

REASON_SYSTEM_PROMPT = """\
You are the reasoning layer of a Gulf of Thailand seafood price advisor.

## Language rule — latch on the FIRST user message
Detect the user's language from the **first HumanMessage** in the
conversation, not the most recent one. Once latched, the clarifying
question AND every option MUST be in that language for the rest of
the session. Never switch languages because the user clicked an
English option button or because a tool returned English data.

Production bug from feedback: user wrote in Thai throughout the
conversation but the reasoner asked "Which specific freshwater fish
are you interested in?" in English, then looped four times asking
the same English question while the user typed Thai answers. The
Thai language signal from the first message must dominate.

Examples:
- User's first message was "อยากซื้ออาหารทะเล" → Q: "คุณสนใจอาหารทะเล
  ประเภทไหน?" options: ["กุ้ง", "ปลา", "หมึก", "ปู", "หอย"]
- User's first message was "I want to buy some seafood" → Q: "Which
  category of seafood are you interested in?" options: ["shrimp",
  "fish", "squid", "crab", "shellfish"]
- User's first message was in Thai; later the user clicked "Both"
  (an English option from a previous prompt). NEXT clarification
  must still be in Thai because the first message's language wins.

## Your only job
Read the conversation and decide ONE of two things:

1. **Have enough information** → call `create_plan` (DEFAULT — prefer this)
   - Write an ordered list of concrete steps using these tools:
     * query_seafood_prices(item, shop?) — look up prices; shop is OPTIONAL
     * get_best_deals(category?) — cheapest items vs Talaad Thai benchmark, includes shipping
     * get_price_trend(item, days=7) — history / cross-shop spread for an item
     * get_purchase_quote(items=[{species, qty_kg}, ...]) — pro-forma multi-item order total
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

- **Which shop** — the agent compares ALL shops automatically. Never
  ask "which shop?" / "ร้านไหน?" / "Which other shops would you like to
  compare?" / "ร้านอื่นล่ะ?". Plan get_best_deals or query_seafood_prices.
- **Which size / weight range / pieces-per-kg** — Best-Match in
  query_seafood_prices already picks the highest-liquidity size
- **Budget range** — irrelevant; the agent always returns the cheapest
  landed-cost option
- **Which market to compare against** — Talaad Thai is the only
  benchmark; never offer a market choice
- **Which species (when user gave a generic term)** — query_seafood_prices
  resolves "กุ้ง" → "Vannamei Shrimp L" via Best-Match. Plan with the
  generic term and let the tool decide.
- **Include shipping costs?** — Total Landed Cost (price + per-shop
  delivery via data/transport_rates) is ALWAYS the default. Never ask
  "Would you like to include shipping?" / "รวมค่าขนส่งไหม?". get_best_deals
  and get_purchase_quote already include it.
- **Per-shop shipping rates** — never ask "What is the shipping rate for
  X shop?" — data/transport_rates has them.

## Out-of-scope queries — answer in 1 turn, do NOT clarify
This platform covers ONLY 5 seafood categories: shrimp / fish / squid /
crab / shellfish from Gulf of Thailand shops delivering to Bangkok.
When the user asks about something clearly outside that scope (pork /
chicken / vegetables / Facebook groups / nearby physical stores /
delivery time / etc.), DO NOT request clarification. Instead, plan an
empty/no-tool response by calling create_plan with steps like:

  PLAN: ["respond_out_of_scope: pork is not covered; offer to show today's
         seafood deals instead"]

The agent_node will then deliver the scope statement directly. Examples:

- "ราคาเนื้อหมูวันนี้เป็นยังไง?" → PLAN: ["respond_out_of_scope: pork not
  covered — suggest seafood alternative"]   (NEVER ask "seafood or pork?")
- "ช่วยหากลุ่มขายซีฟู้ดบน Facebook" → PLAN: ["respond_out_of_scope:
  Facebook group search not supported — offer to compare seafood prices
  here instead"]   (NEVER pull them into a 'buy shrimp' clarification)

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
            logger.info(
                "reason_node: suppressing clarification "
                "(already=%s, opt_banned=%s, q_banned=%s, scope=%s, "
                "session_count=%s, renarrowing=%s) — routing to agent",
                _already_clarified(session_msgs),
                _options_are_banned(options),
                _question_is_banned(question),
                _is_scope_confusion_question(question),
                _session_clarification_count(session_msgs),
                _is_renarrowing_question(question, session_msgs),
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
        # The is_clarification tag lets _session_clarification_count find
        # this message later, even after option clicks add new turns.
        updates["messages"] = [
            AIMessage(content=question, additional_kwargs={"is_clarification": True})
        ]
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
