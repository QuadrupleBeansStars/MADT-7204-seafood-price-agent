"""
Bangkok Seafood Price Comparison Agent
Main entry point: LangGraph ReAct agent with Langfuse tracing.

Usage:
    conda activate MADT
    python -m agent.main
"""

import os
import sys
from typing import Annotated, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from agent.prompts.system import SYSTEM_PROMPT
from agent.tools import ALL_TOOLS

load_dotenv()

# All tools available to the agent
TOOLS = ALL_TOOLS


# --- State ---

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    pending_clarification: Optional[dict]   # {question, options} — set by reason_node
    current_plan: Optional[list]            # list[str] — set by reason_node
    last_thinking: Optional[str]            # extended thinking text — set by reason_node


# --- Nodes ---

def get_llm():
    """Initialize Claude LLM bound with tools."""
    llm = ChatAnthropic(
        model="claude-sonnet-4-5",
        temperature=0,
    )
    return llm.bind_tools(TOOLS)


def agent_node(state: AgentState) -> dict:
    """LLM reasoning node — executes the plan produced by reason_node."""
    llm = get_llm()
    messages = list(state["messages"])

    plan = state.get("current_plan")
    system_content = SYSTEM_PROMPT
    if plan:
        plan_text = "\n\nExecution plan (follow these steps in order):\n" + "\n".join(
            f"{i+1}. {step}" for i, step in enumerate(plan)
        )
        system_content = SYSTEM_PROMPT + plan_text

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=system_content)] + messages
    else:
        messages = [SystemMessage(content=system_content)] + messages[1:]

    response = llm.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Conditional edge: route to tools or end."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


# --- Graph ---

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


def get_langfuse_handler():
    """Initialize Langfuse callback handler if credentials are available."""
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")

    if not secret_key or not public_key:
        print("[INFO] Langfuse credentials not found — running without tracing.")
        return None

    from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

    return LangfuseCallbackHandler(
        secret_key=secret_key,
        public_key=public_key,
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
    )


def main():
    """Interactive CLI loop for the seafood price agent."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    graph = build_graph()
    langfuse_handler = get_langfuse_handler()

    config = {}
    if langfuse_handler:
        config["callbacks"] = [langfuse_handler]

    print("=" * 60)
    print("  Bangkok Seafood Price Advisor")
    print("  Type your question or 'quit' to exit")
    print("=" * 60)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        messages.append(HumanMessage(content=user_input))

        result = graph.invoke(
            {"messages": messages},
            config=config,
        )

        # Get the final assistant message
        assistant_message = result["messages"][-1]
        print(f"\nAgent: {assistant_message.content}")

        # Update conversation history
        messages = result["messages"]

    # Flush Langfuse traces
    if langfuse_handler:
        langfuse_handler.flush()


if __name__ == "__main__":
    main()
