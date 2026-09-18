"""Slack notification adapter.

If SLACK_WEBHOOK_URL is not set, the adapter logs the message and returns
success — so the pipeline works in development without a real Slack.

The real code path (httpx POST to the webhook) is identical to production;
only the target URL differs.
"""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_approval_request(
    *,
    approval_id: str,
    tool: str,
    agent_name: str,
    risk_score: float,
    reasons: list[str],
    approve_url: str,
    deny_url: str,
) -> tuple[bool, Optional[str]]:
    """Post an interactive notification. Returns (success, error_message)."""
    webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)

    text = (
        f"*AgentShield approval required*\n"
        f"• Agent: `{agent_name}`\n"
        f"• Tool: `{tool}`\n"
        f"• Risk: `{risk_score:.0f}/100`\n"
        f"• Approval ID: `{approval_id}`\n"
        f"• Approve: {approve_url}\n"
        f"• Deny: {deny_url}\n\n"
        f"Reasons: " + "; ".join(reasons[:3])
    )

    if not webhook_url:
        # Development mode — log the notification that would be sent.
        logger.warning("[SLACK-MOCK] %s", text.replace("\n", " | "))
        return True, None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(webhook_url, json={"text": text})
            r.raise_for_status()
        return True, None
    except Exception as e:  # noqa: BLE001
        logger.exception("Slack notification failed: %s", e)
        return False, str(e)