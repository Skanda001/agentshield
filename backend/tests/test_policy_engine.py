"""Unit tests for the policy evaluator."""
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


def test_order_read_is_allowed():
    r = evaluate_policy(POLICY, _ctx("read", "order"))
    assert r.effect == "allow"
    assert r.matched_rule == "allow_order_read"


def test_customer_delete_is_denied():
    r = evaluate_policy(POLICY, _ctx("delete", "customer"))
    assert r.effect == "deny"
    assert r.matched_rule == "deny_customer_delete"


def test_bulk_customer_read_escalates():
    r = evaluate_policy(POLICY, _ctx("read", "customer", {"count": 500}))
    assert r.effect == "escalate"
    assert r.matched_rule == "escalate_bulk_customer_read"


def test_small_customer_read_falls_through_to_default():
    r = evaluate_policy(POLICY, _ctx("read", "customer", {"count": 3}))
    # No explicit allow_customer_read in the test policy, so default fires
    assert r.effect == "escalate"
    assert r.matched_rule == "default_escalate"


def test_unmatched_falls_through_to_default():
    r = evaluate_policy(POLICY, _ctx("write", "invoice"))
    assert r.matched_rule == "default_escalate"
    assert r.effect == "escalate"