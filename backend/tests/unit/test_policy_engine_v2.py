"""Expanded unit tests for the policy engine."""
import pytest

from app.policy_engine.evaluator import EvalContext, evaluate_policy
from app.schemas.policy import PolicyDocument


POLICY = PolicyDocument.model_validate({
    "name": "test_policy",
    "version": 1,
    "rules": [
        {"name": "allow_order_read", "effect": "allow", "action": "read", "resource": "order"},
        {"name": "deny_customer_delete", "effect": "deny", "action": "delete", "resource": "customer", "priority": 100},
        {
            "name": "escalate_bulk_customer_read",
            "effect": "escalate",
            "action": "read",
            "resource": "customer",
            "conditions": {"min_volume": 50},
            "priority": 50,
        },
        {"name": "default_escalate", "effect": "escalate", "priority": 1},
    ],
})


def _ctx(action: str, resource: str, args: dict | None = None, role: str = "support") -> EvalContext:
    return EvalContext(
        agent_name="support-bot",
        role=role,
        action=action,
        resource_type=resource,
        arguments=args or {},
        data_classification=None,
    )


class TestMatching:
    def test_explicit_allow_matches(self):
        r = evaluate_policy(POLICY, _ctx("read", "order"))
        assert r.matched_rule == "allow_order_read"
        assert r.effect == "allow"

    def test_explicit_deny_wins(self):
        r = evaluate_policy(POLICY, _ctx("delete", "customer"))
        assert r.matched_rule == "deny_customer_delete"
        assert r.effect == "deny"

    def test_condition_matches(self):
        r = evaluate_policy(POLICY, _ctx("read", "customer", {"count": 500}))
        assert r.matched_rule == "escalate_bulk_customer_read"

    def test_condition_does_not_match(self):
        r = evaluate_policy(POLICY, _ctx("read", "customer", {"count": 3}))
        assert r.matched_rule == "default_escalate"


class TestSpecificityFix:
    """The specificity-before-priority fix from Chunk 5."""

    def test_specific_rule_beats_default_even_at_lower_priority(self):
        # allow_order_read has specificity 2, priority 0.
        # default_escalate has specificity 0, priority 1.
        # The specificity fix means allow_order_read wins.
        r = evaluate_policy(POLICY, _ctx("read", "order"))
        assert r.effect == "allow"
        assert r.matched_rule == "allow_order_read"

    def test_priority_breaks_ties_among_equal_specificity(self):
        policy = PolicyDocument.model_validate({
            "name": "tiebreak",
            "version": 1,
            "rules": [
                {"name": "low", "effect": "allow", "action": "read", "priority": 1},
                {"name": "high", "effect": "escalate", "action": "read", "priority": 10},
            ],
        })
        r = evaluate_policy(policy, _ctx("read", "order"))
        assert r.matched_rule == "high"

    def test_equal_specificity_equal_priority_prefers_restrictive(self):
        policy = PolicyDocument.model_validate({
            "name": "tiebreak2",
            "version": 1,
            "rules": [
                {"name": "a", "effect": "allow", "action": "read"},
                {"name": "b", "effect": "deny", "action": "read"},
            ],
        })
        r = evaluate_policy(policy, _ctx("read", "order"))
        assert r.effect == "deny"


class TestNoMatch:
    def test_falls_through_to_default(self):
        r = evaluate_policy(POLICY, _ctx("write", "invoice"))
        assert r.matched_rule == "default_escalate"

    def test_empty_policy(self):
        empty = PolicyDocument.model_validate({
            "name": "empty",
            "version": 1,
            "rules": [{"name": "d", "effect": "escalate", "priority": 1}],
        })
        r = evaluate_policy(empty, _ctx("read", "order"))
        assert r.matched_rule == "d"