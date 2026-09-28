"""
Single-shot runner — used by GitHub Actions cron.
Picks ONE random scenario, runs it through AgentShield, then exits.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

# Add agent-worker dir to path when called from repo root
sys.path.insert(0, os.path.dirname(__file__))

from agent import CustomerSupportAgent
from scenarios import pick_scenario

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run-once")

AGENTSHIELD_URL = os.getenv("AGENTSHIELD_URL", "http://localhost:8000").rstrip("/")
AGENTSHIELD_API_KEY = os.getenv("AGENTSHIELD_API_KEY", "")


def provision_credentials() -> str:
    """Auto-provision a tenant+agent and return API key."""
    suffix = str(int(time.time()))[-6:]

    def post(path: str, body: dict) -> dict:
        req = urllib.request.Request(
            f"{AGENTSHIELD_URL}/api/v1{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())

    tenant = post("/tenants", {"name": f"GH Worker {suffix}", "slug": f"gh-worker-{suffix}"})
    agent_data = post("/agents", {
        "tenant_id": tenant["id"],
        "name": "GitHub Actions Email Agent",
        "role": "support",
        "scopes": ["read:order", "read:customer", "write:refund", "write:email"],
    })
    api_key: str = agent_data["api_key"]

    log.info("━" * 60)
    log.info("✅ Provisioned new agent.")
    log.info("   Add this as GitHub secret AGENTSHIELD_API_KEY:")
    log.info("   %s", api_key)
    log.info("━" * 60)

    # Load demo policy (best-effort)
    try:
        token_res = post("/agents/token", {"api_key": api_key})
        jwt = token_res.get("access_token", "")
        req = urllib.request.Request(
            f"{AGENTSHIELD_URL}/api/v1/policies/load-yaml?tenant_id={tenant['id']}&file_path=policies/demo.yaml",
            data=b"{}",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        log.info("✅ Demo policy loaded")
    except Exception as e:
        log.warning("Policy load skipped: %s", e)

    return api_key


def main() -> None:
    log.info("🛡️  AgentShield — GitHub Actions single-shot run")
    log.info("   Gateway: %s", AGENTSHIELD_URL)

    api_key = AGENTSHIELD_API_KEY
    if not api_key:
        log.info("AGENTSHIELD_API_KEY not set — provisioning once…")
        try:
            api_key = provision_credentials()
        except Exception as exc:
            log.error("❌ Provision failed: %s", exc)
            sys.exit(1)

    os.environ["AGENTSHIELD_API_KEY"] = api_key

    scenario = pick_scenario()
    log.info("─" * 60)
    log.info("Scenario │ %s", scenario["label"])
    log.info("Prompt   │ %s", scenario["prompt"])

    try:
        agent = CustomerSupportAgent()
        result = agent.run(scenario["prompt"])
        verdict = result.get("verdict", "?")
        tool    = result.get("tool", "?")
        icon    = {"ALLOW": "✅", "BLOCK": "⛔", "HITL": "⚠️ "}.get(verdict, "❓")

        log.info("%s %-8s │ tool=%s", icon, verdict, tool)
        if verdict in ("BLOCK", "HITL"):
            log.info("         │ %s", str(result.get("reason", ""))[:120])

        log.info("✔ Done — decision recorded in AgentShield dashboard")
    except Exception as exc:
        log.error("❌ Agent error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
