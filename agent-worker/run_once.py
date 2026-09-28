"""
AgentShield — GitHub Actions runner.

Priority:
  1. Check Gmail for unread emails → process each with the real LLM email agent
  2. If inbox is empty → run one random scenario (keeps dashboard alive)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run-once")

AGENTSHIELD_URL   = os.getenv("AGENTSHIELD_URL", "http://localhost:8000").rstrip("/")
AGENTSHIELD_API_KEY = os.getenv("AGENTSHIELD_API_KEY", "")
GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


# ── Credentials ───────────────────────────────────────────────────────────────

def _post(path: str, body: dict, token: str = "") -> dict:
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{AGENTSHIELD_URL}/api/v1{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def provision_credentials() -> str:
    suffix = str(int(time.time()))[-6:]
    tenant = _post("/tenants", {"name": f"Email Agent {suffix}", "slug": f"email-agent-{suffix}"})
    ag = _post("/agents", {
        "tenant_id": tenant["id"],
        "name": "Autonomous Email Support Agent",
        "role": "support",
        "scopes": ["read:order", "read:customer", "write:refund", "write:email"],
    })
    api_key: str = ag["api_key"]
    log.info("━" * 60)
    log.info("✅ Provisioned. Set AGENTSHIELD_API_KEY = %s", api_key)
    log.info("━" * 60)
    try:
        tok = _post("/agents/token", {"api_key": api_key})
        _post(f"/policies/load-yaml?tenant_id={tenant['id']}&file_path=policies/demo.yaml",
              {}, token=tok.get("access_token", ""))
        log.info("✅ Demo policy loaded")
    except Exception as e:
        log.warning("Policy load skipped: %s", e)
    return api_key


def resolve_api_key() -> str:
    key = AGENTSHIELD_API_KEY
    if not key:
        log.info("No AGENTSHIELD_API_KEY — provisioning…")
        for attempt in range(5):
            try:
                return provision_credentials()
            except Exception as exc:
                wait = 15 * (attempt + 1)
                log.warning("Attempt %d failed: %s. Retry in %ds", attempt + 1, exc, wait)
                time.sleep(wait)
        log.error("Could not provision credentials")
        sys.exit(1)
    return key


def patch_shield(api_key: str) -> None:
    """Override the shield module's singleton client with the correct API key."""
    os.environ["AGENTSHIELD_API_KEY"] = api_key
    import shield as _s
    _s._default_client.api_key = api_key
    _s._default_client.token   = None


# ── Email mode ────────────────────────────────────────────────────────────────

def run_email_mode() -> int:
    """
    Fetch unread emails from Gmail and process each one.
    Returns the number of emails processed.
    """
    from email_client import GmailClient
    from email_agent  import EmailSupportAgent

    gmail = GmailClient(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    try:
        emails = gmail.fetch_unread()
    except Exception as exc:
        log.error("Gmail fetch failed: %s", exc)
        return 0

    if not emails:
        log.info("📭 No unread emails in inbox")
        return 0

    agent = EmailSupportAgent()

    for mail in emails:
        log.info("─" * 60)
        result = agent.process(mail)
        verdict = result.get("verdict", "?")
        reply   = result.get("reply", "")

        # Send the reply back to the sender
        try:
            gmail.send_reply(
                to      = mail.reply_to or mail.from_addr,
                subject = mail.subject,
                body    = reply,
            )
        except Exception as exc:
            log.error("Failed to send reply: %s", exc)

        log.info("✔ Email processed | verdict=%s | replied_to=%s",
                 verdict, mail.reply_to or mail.from_addr)

    return len(emails)


# ── Scenario fallback mode ────────────────────────────────────────────────────

def run_scenario_mode() -> None:
    """Run one random scenario to keep the dashboard active."""
    from agent     import CustomerSupportAgent
    from scenarios import pick_scenario

    scenario = pick_scenario()
    log.info("─" * 60)
    log.info("📋 Scenario fallback (no emails)")
    log.info("Scenario │ %s", scenario["label"])
    log.info("Prompt   │ %s", scenario["prompt"])

    try:
        agent  = CustomerSupportAgent()
        result = agent.run(scenario["prompt"])
        verdict = result.get("verdict", "?")
        tool    = result.get("tool", "?")
        icon    = {"ALLOW": "✅", "BLOCK": "⛔", "HITL": "⚠️ "}.get(verdict, "❓")
        log.info("%s %-8s │ tool=%s", icon, verdict, tool)
    except Exception as exc:
        log.error("Scenario error: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log.info("🛡️  AgentShield Email Agent — GitHub Actions run")
    log.info("   Gateway : %s", AGENTSHIELD_URL)
    log.info("   Gmail   : %s", GMAIL_ADDRESS or "(not configured)")

    api_key = resolve_api_key()
    patch_shield(api_key)

    if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
        processed = run_email_mode()
        if processed == 0:
            # No real emails — still keep dashboard alive with a scenario
            run_scenario_mode()
    else:
        log.info("Gmail credentials not set — running scenario mode only")
        run_scenario_mode()

    log.info("✔ Done")


if __name__ == "__main__":
    main()
