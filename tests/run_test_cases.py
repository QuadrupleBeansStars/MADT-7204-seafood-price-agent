"""Live runner that simulates UI chat invocation for each test case.

Mirrors app/pages/chat.py: builds the same graph and feeds each prompt
through graph.invoke() with the AgentState shape the UI uses. For
clarification cases, runs a follow-up turn with a chosen option.

Output: prints a JSON list to stdout, one entry per case, capturing the
final reply text, the ordered tool-call sequence, the plan, the thinking
trace, and any pending clarification.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv()

from agent.main import build_graph  # noqa: E402
from agent.prompts.system import SYSTEM_PROMPT  # noqa: E402


CASES = [
    # --- Single-tool, EN ---
    {"id": "TC01", "category": "Single tool",
     "prompt": "How much is tiger prawn?",
     "expected_tools": ["query_seafood_prices"],
     "expected_behavior": "Look up tiger prawn prices across shops; return a list of prices with options/sizes and product links."},
    {"id": "TC02", "category": "Single tool",
     "prompt": "What's the price of salmon at PPNSeafood?",
     "expected_tools": ["query_seafood_prices"],
     "expected_behavior": "Look up salmon at PPNSeafood only; return prices with options and a product link."},
    {"id": "TC03", "category": "Single tool",
     "prompt": "What are today's best seafood deals?",
     "expected_tools": ["get_best_deals"],
     "expected_behavior": "Return up to 5 items priced >10% below cross-shop average, sorted by biggest discount."},
    {"id": "TC04", "category": "Single tool · TH",
     "prompt": "มีกุ้งลดราคาอยู่ไหม?",
     "expected_tools": ["get_best_deals"],
     "expected_behavior": "Return shrimp deals (category=shrimp / กุ้ง) in Thai."},
    {"id": "TC05", "category": "Single tool",
     "prompt": "Compare salmon prices across all shops",
     "expected_tools": ["get_price_trend"],
     "expected_behavior": "Return a date×shop trend table for salmon (or current spread fallback if only snapshot data)."},
    {"id": "TC06", "category": "Single tool · benchmark",
     "prompt": "What's the wholesale Talaad Thai reference price for white shrimp today?",
     "expected_tools": ["get_talaadthai_benchmark"],
     "expected_behavior": "Return the Talaad Thai wholesale benchmark for white shrimp / กุ้งขาว."},
    {"id": "TC07", "category": "Single tool · oil",
     "prompt": "How are diesel prices likely to affect shrimp prices right now?",
     "expected_tools": ["get_oil_context"],
     "expected_behavior": "Return oil↔seafood correlation context for shrimp."},
    {"id": "TC08", "category": "Single tool · oil",
     "prompt": "Give me this week's oil briefing in English.",
     "expected_tools": ["generate_oil_briefing"],
     "expected_behavior": "Return a markdown weekly oil briefing in English."},

    # --- Multi-step / chained ---
    {"id": "TC09", "category": "Multi-step",
     "prompt": "เปรียบเทียบราคากุ้งลายเสือทุกร้าน แล้วบอกว่าร้านที่ถูกที่สุดเป็นดีลจริงไหม",
     "expected_tools": ["query_seafood_prices", "get_best_deals"],
     "expected_behavior": "Look up tiger prawn at all shops, then check deals to verify the cheapest is really a bargain; conclude in Thai."},
    {"id": "TC10", "category": "Multi-step",
     "prompt": "Salmon looks expensive at PPNSeafood. How does it compare to other shops?",
     "expected_tools": ["query_seafood_prices", "get_price_trend"],
     "expected_behavior": "Look up salmon at PPNSeafood, then pull price trend / cross-shop spread, then recommend."},
    {"id": "TC11", "category": "Multi-step",
     "prompt": "ฉันต้องสั่งกุ้ง ปลาหมึก และปลากะพง ร้านไหนถูกที่สุดแต่ละอย่าง?",
     "expected_tools": ["query_seafood_prices", "query_seafood_prices", "query_seafood_prices"],
     "expected_behavior": "Look up shrimp, squid, and sea bass independently; recommend cheapest shop per item in Thai."},

    # --- Edge cases ---
    {"id": "TC12", "category": "Edge case",
     "prompt": "How much is lobster?",
     "expected_tools": ["query_seafood_prices"],
     "expected_behavior": "Tool finds no matches; agent reports honestly without hallucinating prices."},
    {"id": "TC13", "category": "Clarification",
     "prompt": "I want to buy some seafood",
     "expected_tools": [],
     "expected_behavior": "Reasoning layer asks one clarifying question with 3–5 options; no data tools called yet."},
    {"id": "TC14", "category": "Clarification follow-through",
     "prompt": "I want to buy some seafood",
     "follow_up": "Tiger prawn",
     "expected_tools": ["query_seafood_prices"],
     "expected_behavior": "After user picks 'Tiger prawn' button, agent proceeds to look up tiger prawn prices."},
]


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n\n".join(p for p in parts if p)
    return ""


def _capture(messages, pending, plan, thinking) -> dict:
    tool_calls = []
    final_text = ""
    for m in messages:
        if isinstance(m, AIMessage):
            t = _text_of(m.content)
            if t:
                final_text = t  # last AI text wins
            for tc in (m.tool_calls or []):
                tool_calls.append({"name": tc["name"], "args": tc.get("args", {})})
    return {
        "tool_calls": tool_calls,
        "final_text": final_text,
        "pending_clarification": pending,
        "plan": plan,
        "thinking": thinking,
    }


def run_case(graph, case: dict) -> dict:
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=case["prompt"])]
    state = {
        "messages": messages,
        "pending_clarification": None,
        "current_plan": None,
        "last_thinking": None,
    }
    result = graph.invoke(state)
    first = _capture(
        result["messages"],
        result.get("pending_clarification"),
        result.get("current_plan"),
        result.get("last_thinking"),
    )

    out = {"id": case["id"], "category": case["category"], "prompt": case["prompt"],
           "expected_tools": case["expected_tools"],
           "expected_behavior": case["expected_behavior"],
           "first_turn": first}

    if case.get("follow_up"):
        # Mimic UI: user clicks one of the clarification options.
        followup_messages = list(result["messages"]) + [HumanMessage(content=case["follow_up"])]
        state2 = {
            "messages": followup_messages,
            "pending_clarification": None,
            "current_plan": None,
            "last_thinking": None,
        }
        result2 = graph.invoke(state2)
        out["follow_up_prompt"] = case["follow_up"]
        out["second_turn"] = _capture(
            result2["messages"],
            result2.get("pending_clarification"),
            result2.get("current_plan"),
            result2.get("last_thinking"),
        )

    return out


def main():
    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    graph = build_graph()
    results = []
    for c in CASES:
        if only and c["id"] not in only:
            continue
        print(f"[run] {c['id']} {c['prompt'][:60]}", file=sys.stderr)
        try:
            results.append(run_case(graph, c))
        except Exception as exc:
            results.append({"id": c["id"], "error": repr(exc), "prompt": c["prompt"]})
            print(f"  ERROR: {exc!r}", file=sys.stderr)
    print(json.dumps(results, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
