"""Property-based tests for the policy engine evaluator.

Uses pytest-parametrize (not Hypothesis) to avoid adding a new test
dependency. Each test verifies an algebraic property that must hold for
ALL policy configurations, not just specific examples.

Properties verified:
  1. Deny always beats allow at equal priority (restrictiveness ordering).
  2. Higher specificity beats lower at equal priority.
  3. Evaluation is deterministic — same inputs always produce same output.
  4. min_volume condition gates by count correctly.
  5. Missing data_classification fails a data_classification condition.
  6. Wildcard (None) field matches any value.
  7. No matching rule → effect=None, matched_rule=None.
"""
import pytest

from app.policy_engine.evaluator import EvalContext, evaluate_policy
from app.schemas.policy import PolicyDocument


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _doc(rules: list[dict]) -> PolicyDocument:
    return PolicyDocument.model_validate({"name": "prop-test", "version": 1, "rules": rules})


def _ctx(
    action: str = "read",
    resource: str = "order",
    args: dict | None = None,
    classification: str | None = None,
    agent: str = "bot",
    role: str = "support",
) -> EvalContext:
    return EvalContext(
        agent_name=agent,
        role=role,
        action=action,
        resource_type=resource,
        arguments=args or {},
        data_classification=classification,
    )


# ─── Property 1: deny > escalate > allow at equal priority ───────────────────

@pytest.mark.parametrize("loser,winner", [
    ("allow", "escalate"),
    ("allow", "deny"),
    ("escalate", "deny"),
])
def test_more_restrictive_effect_wins_at_equal_priority(loser, winner):
    """When two rules match at equal priority, the more restrictive effect wins."""
    doc = _doc([
        {"name": "rule-loser",  "effect": loser,  "action": "read", "priority": 10},
        {"name": "rule-winner", "effect": winner, "action": "read", "priority": 10},
    ])
    result = evaluate_policy(doc, _ctx(action="read"))
    assert result.effect == winner, (
        f"Expected {winner!r} to beat {loser!r} at equal priority, got {result.effect!r}"
    )


# ─── Property 2: higher specificity beats lower at equal priority ─────────────

def test_more_specific_rule_beats_catchall():
    """A rule with more constraints beats a catch-all at equal priority."""
    doc = _doc([
        {"name": "catchall",  "effect": "allow",   "priority": 5},
        {"name": "specific",  "effect": "escalate", "action": "delete", "resource": "customer", "priority": 5},
    ])
    result = evaluate_policy(doc, _ctx(action="delete", resource="customer"))
    assert result.matched_rule == "specific"
    assert result.effect == "escalate"


def test_less_specific_rule_wins_when_specific_does_not_match():
    """The catchall fires when the specific rule does not match the context."""
    doc = _doc([
        {"name": "catchall",  "effect": "allow",   "priority": 5},
        {"name": "specific",  "effect": "escalate", "action": "delete", "resource": "customer", "priority": 5},
    ])
    result = evaluate_policy(doc, _ctx(action="read", resource="order"))
    assert result.matched_rule == "catchall"
    assert result.effect == "allow"


# ─── Property 3: determinism ─────────────────────────────────────────────────

def test_evaluation_is_deterministic():
    """Running evaluate_policy twice with the same inputs returns the same result."""
    doc = _doc([
        {"name": "r1", "effect": "allow",   "action": "read",   "priority": 1},
        {"name": "r2", "effect": "escalate","action": "delete",  "priority": 5},
        {"name": "r3", "effect": "deny",    "action": "delete", "resource": "customer", "priority": 10},
    ])
    ctx = _ctx(action="delete", resource="customer")
    r1 = evaluate_policy(doc, ctx)
    r2 = evaluate_policy(doc, ctx)
    assert r1.effect == r2.effect
    assert r1.matched_rule == r2.matched_rule
    assert r1.priority == r2.priority


# ─── Property 4: min_volume semantics ────────────────────────────────────────

@pytest.mark.parametrize("count,expected_effect", [
    (1,   "allow"),    # below min_volume → specific rule does NOT match
    (49,  "allow"),    # still below threshold
    (50,  "escalate"), # at exactly min_volume → escalate fires
    (500, "escalate"), # well above threshold
])
def test_min_volume_condition_gates_correctly(count, expected_effect):
    """min_volume=50 must only match when count >= 50."""
    doc = _doc([
        {"name": "bulk-escalate", "effect": "escalate", "action": "read",
         "conditions": {"min_volume": 50}, "priority": 10},
        {"name": "default-allow",  "effect": "allow",   "action": "read", "priority": 1},
    ])
    result = evaluate_policy(doc, _ctx(action="read", args={"count": count}))
    assert result.effect == expected_effect, (
        f"count={count}: expected {expected_effect!r}, got {result.effect!r}"
    )


# ─── Property 5: missing data_classification fails condition ─────────────────

def test_missing_classification_fails_data_classification_condition():
    """A rule that requires data_classification must NOT match if it is absent."""
    doc = _doc([
        {"name": "pii-deny", "effect": "deny", "action": "read",
         "conditions": {"data_classification": "restricted"}, "priority": 10},
        {"name": "default",  "effect": "allow", "priority": 1},
    ])
    # classification=None → pii-deny should not match; default fires
    result = evaluate_policy(doc, _ctx(action="read", classification=None))
    assert result.matched_rule == "default"
    assert result.effect == "allow"


def test_matching_classification_fires_rule():
    """A rule with data_classification condition fires when classification matches."""
    doc = _doc([
        {"name": "pii-deny", "effect": "deny", "action": "read",
         "conditions": {"data_classification": "restricted"}, "priority": 10},
        {"name": "default",  "effect": "allow", "priority": 1},
    ])
    result = evaluate_policy(doc, _ctx(action="read", classification="restricted"))
    assert result.matched_rule == "pii-deny"
    assert result.effect == "deny"


# ─── Property 6: wildcard (None) field matches any value ─────────────────────

@pytest.mark.parametrize("action", ["read", "delete", "write", "transfer"])
def test_wildcard_rule_matches_any_action(action):
    """A rule with action=None (omitted) must match any action."""
    doc = _doc([
        {"name": "catchall", "effect": "escalate"},  # no action/resource constraint
    ])
    result = evaluate_policy(doc, _ctx(action=action))
    assert result.effect == "escalate"
    assert result.matched_rule == "catchall"


# ─── Property 7: no match → effect=None ──────────────────────────────────────

def test_no_matching_rule_returns_none_effect():
    """When no rule matches, effect and matched_rule are None."""
    doc = _doc([
        {"name": "specific", "effect": "deny", "action": "delete", "resource": "customer"},
    ])
    result = evaluate_policy(doc, _ctx(action="read", resource="order"))
    assert result.effect is None
    assert result.matched_rule is None
    assert result.priority == -1


# ─── Property 8: higher priority number wins over lower ──────────────────────

@pytest.mark.parametrize("high_pri,low_pri", [(100, 1), (10, 5), (50, 49)])
def test_higher_priority_wins(high_pri, low_pri):
    """The rule with the numerically higher priority wins, regardless of effect."""
    doc = _doc([
        {"name": "low-pri-deny",  "effect": "deny",  "action": "read", "priority": low_pri},
        {"name": "high-pri-allow","effect": "allow",  "action": "read", "priority": high_pri},
    ])
    result = evaluate_policy(doc, _ctx(action="read"))
    assert result.matched_rule == "high-pri-allow"
    assert result.effect == "allow"
