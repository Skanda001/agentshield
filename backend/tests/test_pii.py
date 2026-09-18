"""Unit tests for PII detection."""
from app.detection.pii.indian_pii import find_all as find_indian

from app.detection.pii.presidio_wrapper import detect



def test_email_detected():
    r = detect({"to": "someone@example.com"})
    labels = [m.label for m in r.matches]
    assert "email" in labels
    assert r.highest_classification == "confidential"


def test_pan_detected():
    r = detect({"text": "My PAN is ABCDE1234F"})
    labels = [m.label for m in r.matches]
    assert "pan" in labels
    assert r.highest_classification == "restricted"


def test_aadhaar_detected_and_redacted():
    r = detect({"text": "Aadhaar 2345 6789 0123"})
    labels = [m.label for m in r.matches]
    assert "aadhaar" in labels
    # Redacted values should not contain the full digits
    for m in r.matches:
        if m.label == "aadhaar":
            assert "*" in m.value


def test_phone_detected():
    r = detect({"text": "Call me at +91 9876543210"})
    labels = [m.label for m in r.matches]
    assert "phone" in labels


def test_upi_detected():
    r = detect({"text": "Pay to user@okaxis"})
    labels = [m.label for m in r.matches]
    assert "upi" in labels


def test_restricted_beats_confidential():
    r = detect({"text": "PAN ABCDE1234F and email x@y.com"})
    assert r.highest_classification == "restricted"


def test_no_pii_returns_public():
    r = detect({"query": "read order 8211"})
    assert r.matches == []
    assert r.highest_classification == "public"
    assert r.total_points == 0


def test_nested_arguments_scanned():
    r = detect({"outer": {"inner": "contact: a@b.com"}})
    labels = [m.label for m in r.matches]
    assert "email" in labels


def test_credit_card_detected():
    r = detect({"card": "4111 1111 1111 1111"})
    labels = [m.label for m in r.matches]
    assert "credit_card" in labels
    assert r.highest_classification == "restricted"


def test_risk_engine_adds_pii_points():
    from app.risk_engine.deterministic import evaluate

    r = evaluate(
        tool="send_email",
        arguments={"to": "x@y.com", "body": "PAN ABCDE1234F"},
    )
    # send=25, email resource=0, dest=15, pii should add points
    assert r.risk_score >= 40
    names = {s.name for s in r.signals}
    assert "pii" in names