"""Chat page — LangGraph ReAct agent backed by Claude Sonnet 4.5.

Each assistant "turn" (one or more AI/Tool messages between user inputs)
renders as a single chat bubble: the final text on top, with a collapsed
expander listing every tool call that ran. Claude returns list-of-blocks
for intermediate tool-use messages, so raw content is filtered to text
before render to avoid leaking dict reprs.
"""

import json
import sys
from pathlib import Path

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.main import build_graph, get_langfuse_handler
from agent.prompts.system import SYSTEM_PROMPT


EXAMPLE_PROMPTS = [
    ("🦐 Today's best deals", "What are today's best seafood deals?"),
    ("🐟 Shrimp at Makro", "How much is white shrimp at Makro today?"),
    ("📈 Salmon trend", "Has salmon gone up this week?"),
    (
        "🛒 Build a basket",
        "Compare white shrimp across all shops today and tell me if the cheapest one is a genuine deal.",
    ),
]


@st.cache_resource
def _graph():
    return build_graph()


@st.cache_resource
def _langfuse():
    return get_langfuse_handler()


def _text_of(content) -> str:
    """Extract displayable text from an AIMessage.content that may be a
    string OR a list of content-block dicts (Claude's tool-use format)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n\n".join(p for p in parts if p)
    return ""


def _format_tool_result(content) -> str:
    """ToolMessage.content is usually a JSON string; pretty-print if so."""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            return content
    return str(content)


def _render_tool_expander(tool_calls: list[dict], tool_results: dict[str, ToolMessage]) -> None:
    if not tool_calls:
        return
    label = f"🔧 Used {len(tool_calls)} tool{'s' if len(tool_calls) != 1 else ''}"
    with st.expander(label, expanded=False):
        for call in tool_calls:
            st.markdown(f"**`{call['name']}`**")
            args = call.get("args") or {}
            if args:
                st.markdown("_Arguments:_")
                st.code(json.dumps(args, indent=2, ensure_ascii=False), language="json")
            result_msg = tool_results.get(call["id"])
            if result_msg is not None:
                st.markdown("_Result:_")
                st.code(_format_tool_result(result_msg.content), language="json")
            st.divider()


def _render_history(messages: list) -> None:
    """Render the message list, merging each assistant turn into one bubble.

    A "turn" is a run of AI/Tool messages between user inputs. The final
    AIMessage (the one with no tool_calls) carries the user-facing answer;
    earlier AIMessages only exist to trigger tools, so their text (if any)
    is appended but their raw tool_use blocks are surfaced in an expander.
    """
    i = 0
    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, SystemMessage):
            i += 1
            continue

        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
            i += 1
            continue

        if isinstance(msg, AIMessage):
            turn_texts: list[str] = []
            turn_tool_calls: list[dict] = []
            turn_tool_results: dict[str, ToolMessage] = {}

            while i < len(messages) and isinstance(messages[i], (AIMessage, ToolMessage)):
                cur = messages[i]
                if isinstance(cur, AIMessage):
                    text = _text_of(cur.content)
                    if text:
                        turn_texts.append(text)
                    if cur.tool_calls:
                        turn_tool_calls.extend(cur.tool_calls)
                elif isinstance(cur, ToolMessage):
                    turn_tool_results[cur.tool_call_id] = cur
                i += 1

            with st.chat_message("assistant"):
                final_text = "\n\n".join(turn_texts).strip()
                if final_text:
                    st.markdown(final_text)
                else:
                    st.info("_(No text response — see tool calls below.)_")
                _render_tool_expander(turn_tool_calls, turn_tool_results)
            continue

        i += 1


def _render_welcome() -> None:
    st.markdown(
        "#### 🐟 Ask me about Bangkok seafood prices.\n"
        "I can check prices at specific shops, spot today's best deals, "
        "or show you a 7-day trend. Try one of these to get started:"
    )
    cols = st.columns(2)
    for idx, (label, prompt) in enumerate(EXAMPLE_PROMPTS):
        with cols[idx % 2]:
            if st.button(label, use_container_width=True, key=f"ex_{idx}"):
                st.session_state["pending_prompt"] = prompt
                st.rerun()


def _invoke_agent(user_text: str) -> None:
    graph = _graph()
    handler = _langfuse()
    config = {"callbacks": [handler]} if handler else {}

    messages = st.session_state["messages"]
    messages.append(HumanMessage(content=user_text))

    try:
        with st.spinner("🐟 Consulting Bangkok markets..."):
            result = graph.invoke({"messages": messages}, config=config)
        st.session_state["messages"] = result["messages"]
        st.session_state.pop("last_error", None)
    except Exception as exc:  # surface to UI, keep running
        st.session_state["last_error"] = repr(exc)


# --- Page body ---------------------------------------------------------------

st.title("Bangkok Seafood Price Advisor 🐟")
st.caption("Ask me about seafood prices, best deals, or build a shopping list.")

if "messages" not in st.session_state:
    st.session_state["messages"] = [SystemMessage(content=SYSTEM_PROMPT)]

# Consume a queued example-prompt click, if any.
if prompt := st.session_state.pop("pending_prompt", None):
    _invoke_agent(prompt)

non_system = [m for m in st.session_state["messages"] if not isinstance(m, SystemMessage)]
if not non_system:
    _render_welcome()
else:
    _render_history(st.session_state["messages"])

if err := st.session_state.get("last_error"):
    st.error("Something went wrong while contacting the agent.")
    with st.expander("Details"):
        st.code(err)

if user_input := st.chat_input("e.g. Which shop has cheapest white shrimp today?"):
    _invoke_agent(user_input)
    st.rerun()
