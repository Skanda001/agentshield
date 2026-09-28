"""
AgentShield Autonomous Email Support Worker
============================================
Runs 24/7 on Render as a Background Worker.

Every 30-90 seconds it generates a realistic email support ticket,
runs it through the CustomerSupportAgent, which calls @protect on
every tool → HTTP to AgentShield → ALLOW / BLOCK / HITL.

All decisions appear live on the AgentShield dashboard.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.request

from agent import CustomerSupportAgent
from scenarios import pick_scenario

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("worker")

AGENTSHIELD_URL = os.getenv("AGENTSHIELD_URL", "http://localhost:8000").rstrip("/")
AGENTSHIELD_API_KEY = os.getenv("AGENTSHIELD_API_KEY", "")
MIN_DELAY = int(os.getenv("MIN_DELAY_SECS", "45"))
MAX_DELAY = int(os.getenv("MAX_DELAY_SECS", "90"))


# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap helpers
# ──────────────────────────────────────────────────────────────────────────────

def _post(path: str, body: dict, token: str = "") -> dict:
    url = f"{AGENTSHIELD_URL}/api/v1{path}"
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def provision_credentials() -> str:
    """
    Auto-provision a fresh tenant + agent on AgentShield and return the API key.
    Called only when AGENTSHIELD_API_KEY is not set.
    The key is printed to logs — set it as an env var to avoid re-provisioning
    on every Render restart.
    """
    suffix = str(int(time.time()))[-6:]

    log.info("Provisioning tenant…")
    tenant = _post("/tenants", {
        "name": f"Email Worker {suffix}",
        "slug": f"email-worker-{suffix}",
    })
    tenant_id = tenant["id"]

    log.info("Provisioning agent…")
    agent_data = _post("/agents", {
        "tenant_id": tenant_id,
        "name": "Autonomous Email Support Agent",
        "role": "support",
        "scopes": ["read:order", "read:customer", "write:refund", "write:email"],
    })
    api_key: str = agent_data["api_key"]

    log.info("━" * 60)
    log.info("✅ Agent provisioned successfully.")
    log.info("   AGENTSHIELD_API_KEY = %s", api_key)
    log.info("   Set this in your Render env vars to persist across restarts.")
    log.info("━" * 60)

    # Load demo policy (best-effort)
    try:
        token_resp = _post("/agents/token", {"api_key": api_key})
        jwt = token_resp.get("access_token", "")
        _post(
            f"/policies/load-yaml?tenant_id={tenant_id}&file_path=policies/demo.yaml",
            {},
            token=jwt,
        )
        log.info("✅ Demo policy loaded")
    except Exception as e:
        log.warning("Demo policy load skipped (non-fatal): %s", e)

    return api_key


# ──────────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("🛡️  AgentShield Autonomous Email Worker starting…")
    log.info("   Gateway  : %s", AGENTSHIELD_URL)
    log.info("   Interval : %d–%d seconds", MIN_DELAY, MAX_DELAY)

    # Resolve API key
    api_key = AGENTSHIELD_API_KEY
    if not api_key:
        log.info("AGENTSHIELD_API_KEY not set — auto-provisioning…")
        for attempt in range(5):
            try:
                api_key = provision_credentials()
                break
            except Exception as exc:
                wait = 15 * (attempt + 1)
                log.warning("Provision attempt %d failed: %s. Retrying in %ds…",
                            attempt + 1, exc, wait)
                time.sleep(wait)
        else:
            log.error("❌ Could not provision credentials after 5 attempts. Exiting.")
            raise SystemExit(1)

    # Make the key available to the shield SDK
    os.environ["AGENTSHIELD_API_KEY"] = api_key

    agent = CustomerSupportAgent()
    run_count = 0

    log.info("🔄 Entering processing loop…")

    while True:
        run_count += 1
        scenario = pick_scenario()
        prompt = scenario["prompt"]
        label = scenario["label"]

        log.info("─" * 60)
        log.info("Run #%-4d │ %s", run_count, label)
        log.info("Prompt   │ %s", prompt)

        try:
            result = agent.run(prompt)
            verdict = result.get("verdict", "?")
            tool    = result.get("tool", "?")
            icon = {"ALLOW": "✅", "BLOCK": "⛔", "HITL": "⚠️ "}.get(verdict, "❓")

            log.info("%s %-8s │ tool=%s", icon, verdict, tool)

            if verdict in ("BLOCK", "HITL"):
                reason = result.get("reason", result.get("text", ""))
                log.info("         │ %s", reason[:120])

        except Exception as exc:
            log.error("❌ Agent error: %s", exc)

        delay = random.randint(MIN_DELAY, MAX_DELAY)
        log.info("💤 Next run in %ds", delay)
        time.sleep(delay)


if __name__ == "__main__":
    main()
