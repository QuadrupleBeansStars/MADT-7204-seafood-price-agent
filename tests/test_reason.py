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
