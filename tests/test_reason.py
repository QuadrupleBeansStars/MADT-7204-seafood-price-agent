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
            {"reasoning": "User said 'fish' but did not specify which type.", "question": "Which fish?", "options": ["Salmon", "Sea Bass", "Grouper"]},
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

    def test_clarification_persists_question_as_ai_message(self):
        """Regression: previously, the clarifying question lived only in
        pending_clarification, never in messages. After the user clicked an
        option a HumanMessage was appended directly after the original
        HumanMessage, with no assistant turn between them, and the next
        reason_node call re-asked the same clarification (loop)."""
        from agent.reason import reason_node
        from langchain_core.messages import AIMessage

        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "Ambiguous", "question": "Which type of prawn?",
             "options": ["Tiger Prawn", "Giant Freshwater Prawn"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert "messages" in result, "clarification must persist as a message"
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert result["messages"][0].content == "Which type of prawn?"

    def test_plan_path_does_not_emit_extra_message(self):
        """The non-clarification path should not push a synthetic AIMessage."""
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "create_plan",
            {"reasoning": "clear", "steps": ["query"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert "messages" not in result

    def test_sets_current_plan_when_llm_calls_create_plan(self):
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "create_plan",
            {"reasoning": "User asked for salmon prices — item and intent are clear.", "steps": ["query salmon prices", "rank by price_per_kg", "return best deal"]},
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
            {"reasoning": "Enough context now.", "steps": ["query tiger prawn prices"]},
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

    def test_reasoning_field_stored_as_last_thinking(self):
        """reasoning arg from tool call is surfaced as last_thinking for the UI."""
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "create_plan",
            {"reasoning": "Item and intent are clear.", "steps": ["query salmon prices"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["last_thinking"] == "Item and intent are clear."

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

    def test_falls_back_when_llm_raises_exception(self):
        """If the LLM call raises, reason_node returns all-None state (routes to agent)."""
        from agent.reason import reason_node
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.side_effect = Exception("API timeout")
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] is None
        assert result["current_plan"] is None
        assert result["last_thinking"] is None


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


# ── guards against over-asking ───────────────────────────────────────────────

class TestClarificationGuards:

    def test_shop_options_are_suppressed(self):
        """If the LLM proposes shop names as options, drop the clarification
        and route to agent (Best-Match resolves on its own)."""
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "Asking which shop", "question": "Which shop?",
             "options": ["ไต้ก๋ง ซีฟู้ด", "Sawasdee Seafood", "PPNSeafood"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] is None
        assert result["current_plan"] is None  # falls through to agent

    def test_budget_options_are_suppressed(self):
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "Asking budget", "question": "What budget?",
             "options": ["Below ฿500/kg", "฿500-฿1000/kg", "Above ฿1000/kg"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] is None

    def test_size_pieces_per_kg_options_are_suppressed(self):
        from agent.reason import reason_node
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "Asking size", "question": "Which size?",
             "options": ["Small (10-20 pieces/kg)", "Medium (21-30 pieces/kg)"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state())

        assert result["pending_clarification"] is None

    def test_second_clarification_in_same_turn_is_suppressed(self):
        """Within a single turn (no new HumanMessage), a second clarification
        attempt is suppressed. This guards against any code path that would
        invoke reason_node twice for the same user input."""
        from agent.reason import reason_node
        # No HumanMessage at the end → the prior AIMessage is in the
        # CURRENT turn, so this counts as already-clarified.
        messages = [
            HumanMessage(content="seafood"),
            AIMessage(content="Which category?"),  # persisted clarification
        ]
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "still vague", "question": "Which species?",
             "options": ["กุ้งขาว", "กุ้งลายเสือ", "กุ้งกุลาดำ"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state(messages=messages))

        assert result["pending_clarification"] is None  # suppressed

    def test_clarification_allowed_in_a_later_turn(self):
        """Regression: an earlier over-broad implementation walked the
        ENTIRE message history and returned True for any AIMessage without
        tool_calls — which includes plain text answers from agent_node.
        That suppressed all clarifications for the rest of the session.

        Setup: a fully-completed prior turn (user → assistant answer),
        followed by a NEW ambiguous user question. The new question must
        be allowed to receive a fresh clarification."""
        from agent.reason import reason_node
        messages = [
            HumanMessage(content="cheapest salmon"),
            AIMessage(content="Salmon at Shop X is ฿430/pack."),  # past answer
            HumanMessage(content="seafood"),  # NEW turn, ambiguous
        ]
        mock_response = _ai_with_tool_call(
            "request_clarification",
            {"reasoning": "ambiguous", "question": "Which category?",
             "options": ["shrimp", "fish", "squid"]},
        )
        with patch("agent.reason._build_reason_llm") as mock_llm_factory:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_llm_factory.return_value = mock_llm

            result = reason_node(_make_state(messages=messages))

        # MUST NOT be suppressed — first clarification of the new turn.
        assert result["pending_clarification"] == {
            "question": "Which category?",
            "options": ["shrimp", "fish", "squid"],
        }
