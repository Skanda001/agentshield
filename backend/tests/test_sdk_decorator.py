"""Tests for the @protect decorator (SDK fail-closed behaviour).

These are pure unit tests: they mock ShieldClient so they run without a
live gateway.  Each test scenario verifies the exact semantics specified
in the Phase 1 security audit:

  - ALLOW        → wrapped function executes, return value passed through
  - BLOCK        → ShieldBlocked raised, function does NOT execute
  - HITL/ESCALATE → ShieldEscalated raised, function does NOT execute
  - Connection error  + fail_closed=True  → ShieldError, function does NOT execute
  - Connection error  + fail_closed=False → function executes (fail-open)
  - Timeout           + fail_closed=True  → ShieldError, function does NOT execute
  - 500 response      + fail_closed=True  → ShieldError, function does NOT execute
  - Unknown verdict   + fail_closed=True  → ShieldError, function does NOT execute
  - Unknown verdict   + fail_closed=False → ShieldError still (never silently allow)
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from shield.decorator import protect
from shield.exceptions import ShieldBlocked, ShieldError, ShieldEscalated
from shield.models import Decision


def _make_decision(verdict: str, risk_score: float = 0.0) -> Decision:
    return Decision(
        verdict=verdict,
        risk_score=risk_score,
        reasons=[f"test: {verdict}"],
        decision_id="test-id",
        tool="test_tool",
        action="read",
        approval_id=None,
    )


def _mock_client(verdict: str, risk_score: float = 0.0):
    client = MagicMock()
    client.decide.return_value = _make_decision(verdict, risk_score)
    return client


# ── ALLOW ────────────────────────────────────────────────────────────────────

def test_allow_executes_function():
    """ALLOW verdict: the wrapped function runs and returns its value."""
    client = _mock_client("ALLOW")
    executed = []

    @protect(tool="test_tool", client=client)
    def my_tool(x: int) -> int:
        executed.append(x)
        return x * 2

    result = my_tool(21)
    assert result == 42
    assert executed == [21]
    client.decide.assert_called_once()


def test_allow_executes_async_function():
    """ALLOW verdict: async wrapped function runs and returns its value."""
    client = _mock_client("ALLOW")

    @protect(tool="test_tool", client=client)
    async def my_async_tool(x: int) -> int:
        return x + 1

    result = asyncio.get_event_loop().run_until_complete(my_async_tool(99))
    assert result == 100


# ── BLOCK ────────────────────────────────────────────────────────────────────

def test_block_raises_and_does_not_execute():
    """BLOCK verdict: ShieldBlocked is raised; the function body must NOT run."""
    client = _mock_client("BLOCK", risk_score=90.0)
    executed = []

    @protect(tool="test_tool", client=client)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldBlocked) as exc_info:
        my_tool()

    assert executed == [], "Function body must NOT execute on BLOCK"
    assert exc_info.value.risk_score == 90.0


# ── HITL / ESCALATE ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict", ["HITL", "ESCALATE"])
def test_hitl_raises_and_does_not_execute(verdict):
    """HITL/ESCALATE: ShieldEscalated raised; function must NOT execute."""
    client = _mock_client(verdict, risk_score=55.0)
    executed = []

    @protect(tool="test_tool", client=client)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldEscalated):
        my_tool()

    assert executed == [], "Function body must NOT execute on HITL/ESCALATE"


# ── FAIL-CLOSED (default) ─────────────────────────────────────────────────────

def test_connection_error_fail_closed_raises():
    """Gateway connection error with fail_closed=True (default): ShieldError, no execution."""
    client = MagicMock()
    client.decide.side_effect = ShieldError("connection refused")
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=True)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldError):
        my_tool()

    assert executed == [], "Function must NOT execute when gateway is unreachable (fail-closed)"


def test_timeout_fail_closed_raises():
    """Timeout (ShieldError subclass) with fail_closed=True: re-raised, no execution."""
    client = MagicMock()
    client.decide.side_effect = ShieldError("timed out after 10s")
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=True)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldError, match="timed out"):
        my_tool()

    assert executed == []


def test_500_response_fail_closed_raises():
    """Gateway returns 500 → ShieldClient raises ShieldError → fail-closed blocks."""
    client = MagicMock()
    client.decide.side_effect = ShieldError("Decision request failed: 500")
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=True)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldError, match="500"):
        my_tool()

    assert executed == []


def test_unknown_verdict_fail_closed_raises():
    """Unknown verdict string with fail_closed=True: ShieldError, no execution."""
    client = _mock_client("UNKNOWN_VERDICT")
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=True)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldError, match="Unknown verdict"):
        my_tool()

    assert executed == []


# ── FAIL-OPEN (explicit opt-in) ───────────────────────────────────────────────

def test_connection_error_fail_open_executes():
    """Gateway unreachable with fail_closed=False: function DOES execute (fail-open)."""
    client = MagicMock()
    client.decide.side_effect = ShieldError("connection refused")
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=False)
    def my_tool():
        executed.append(True)
        return "ran"

    result = my_tool()
    assert result == "ran"
    assert executed == [True], "Function MUST execute when gateway is down and fail_closed=False"


def test_unknown_verdict_fail_open_still_raises():
    """Unknown verdict string with fail_closed=False still raises ShieldError.

    An unknown verdict is NEVER silently allowed — a misconfigured or
    compromised gateway could send an unexpected string to bypass security.
    """
    client = _mock_client("ALLOW_BYPASS")  # attacker-controlled verdict
    executed = []

    @protect(tool="test_tool", client=client, fail_closed=False)
    def my_tool():
        executed.append(True)

    with pytest.raises(ShieldError, match="Unknown verdict"):
        my_tool()

    assert executed == [], "Unknown verdicts must NEVER silently execute the tool"
