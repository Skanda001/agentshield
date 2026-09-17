"""Unit tests for the deterministic risk engine."""
from app.risk_engine.deterministic import evaluate


def test_read_order_is_low_risk():
    r = evaluate(tool="read_order", arguments={"order_id": "8211"})
    assert r.verdict == "ALLOW"
    assert r.risk_score < 40
    assert r.action == "read"


def test_delete_customer_escalates():
    """delete_customer = 40 (delete) + 25 (customer) = 65 -> ESCALATE."""
    r = evaluate(tool="delete_customer", arguments={"customer_id": "4821"})
    assert r.verdict == "ESCALATE"
    assert 40 <= r.risk_score <= 84
    assert r.action == "delete"


def test_bulk_customer_read_escalates():
    """read_customer with count=500 = 25 (customer) + 25 (volume) = 50 -> ESCALATE."""
    r = evaluate(tool="read_customer", arguments={"count": 500})
    assert r.verdict == "ESCALATE"
    assert 40 <= r.risk_score <= 84


def test_send_email_to_external_is_elevated():
    r = evaluate(
        tool="send_email",
        arguments={"to": "attacker@evil.example", "body": "..."},
    )
    assert r.risk_score >= 40
    names = {s.name for s in r.signals}
    assert "external_destination" in names


def test_block_only_at_very_high_score():
    """Force a BLOCK by stacking multiple high-risk signals."""
    r = evaluate(
        tool="delete_customer",
        arguments={
            "customer_ids": list(range(500)),      # volume 25
            "to": "attacker@evil.example",         # destination 15
        },
    )
    # 40 (delete) + 25 (customer) + 25 (volume) + 15 (destination) = 105 -> capped 100
    assert r.verdict == "BLOCK"
    assert r.risk_score >= 85