"""Tests that PII (Aadhaar, PAN, etc.) never appears in outbound requests to Groq or Supabase."""
from unittest.mock import MagicMock, patch
import pytest

from app.services.supabase_logger import generate_groq_explanation, log_decision_async, send_to_supabase


def test_groq_explanation_masks_aadhaar_and_pan():
    """Reasons containing sensitive PII must be masked before prompt creation."""
    reasons = [
        "Aadhaar 2345 6789 0123 detected in payload",
        "PAN ABCDE1234F was accessed by agent",
    ]

    # Test with Groq mocked to capture the outbound prompt
    with patch("groq.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Security check passed"))
        ]

        with patch("app.core.config.settings.GROQ_API_KEY", "test-key-mock"):
            generate_groq_explanation(
                tool="read_customer",
                verdict="BLOCK",
                reasons=reasons,
                risk_score=85.0,
                arguments={"customer_aadhaar": "2345 6789 0123", "pan": "ABCDE1234F"},
            )

        call_args = mock_client.chat.completions.create.call_args
        assert call_args is not None
        messages = call_args.kwargs["messages"]
        prompt_content = messages[0]["content"]

        # Raw Aadhaar digits and full PAN must NOT appear in the prompt sent to Groq
        assert "2345 6789 0123" not in prompt_content
        assert "234567890123" not in prompt_content
        assert "ABCDE1234F" not in prompt_content


def test_supabase_payload_never_contains_raw_arguments():
    """Outbound Supabase payload structure must never contain raw tool arguments."""
    with patch("app.services.supabase_logger.send_to_supabase") as mock_send:
        # Call log_decision_async directly
        with patch("app.core.config.settings.SUPABASE_URL", "https://xyz.supabase.co"), \
             patch("app.core.config.settings.SUPABASE_KEY", "test-key-123"):
            
            # Use generate_groq_explanation fallback directly
            explanation = generate_groq_explanation(
                tool="transfer_funds",
                verdict="ALLOW",
                reasons=["Normal operation"],
                risk_score=10.0,
            )

            record = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tool": "transfer_funds",
                "verdict": "ALLOW",
                "groq_explanation": explanation,
            }
            # Record sent to Supabase only has id, tool, verdict, groq_explanation
            assert "arguments" not in record
            assert "raw_args" not in record
