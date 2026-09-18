"""Integration test for the decision pipeline.

Requires a live Postgres (Docker). Uses the ASGI app + a real DB session.
Creates an isolated tenant + agent, exercises /decide, then cleans up.
"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.models.agent import Agent
from app.db.models.decision import Decision
from app.db.models.policy import Policy, PolicyVersion
from app.db.models.tenant import Tenant
from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.mark.asyncio
async def test_policy_deny_blocks_delete_customer():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        slug = f"test-{uuid.uuid4().hex[:8]}"

        # 1. Tenant
        r = await client.post(
            "/api/v1/tenants",
            json={"name": "Test Tenant", "slug": slug},
        )
        assert r.status_code == 201, r.text
        tenant_id = r.json()["id"]

        # 2. Agent
        r = await client.post(
            "/api/v1/agents",
            json={
                "tenant_id": tenant_id,
                "name": "support-bot",
                "role": "support",
                "scopes": ["read:order", "read:customer"],
            },
        )
        assert r.status_code == 201, r.text
        api_key = r.json()["api_key"]

        # 3. Token
        r = await client.post("/api/v1/agents/token", json={"api_key": api_key})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        # 4. Load a policy that denies delete_customer
        policy_doc = {
            "name": f"test-policy-{slug}",
            "version": 1,
            "rules": [
                {
                    "name": "allow_order_read",
                    "effect": "allow",
                    "agent": "support-bot",
                    "action": "read",
                    "resource": "order",
                },
                {
                    "name": "deny_customer_delete",
                    "effect": "deny",
                    "action": "delete",
                    "resource": "customer",
                    "priority": 100,
                },
                {"name": "default_escalate", "effect": "escalate", "priority": 1},
            ],
        }
        r = await client.post(
            "/api/v1/policies",
            json={
                "tenant_id": tenant_id,
                "name": policy_doc["name"],
                "description": "test",
                "document": policy_doc,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201, r.text

        # 5. decide: delete_customer → BLOCK (policy deny)
        r = await client.post(
            "/api/v1/decide",
            json={"tool": "delete_customer", "arguments": {"customer_id": "4821"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verdict"] == "BLOCK"
        assert body["policy_rule"] == "deny_customer_delete"
        assert body["risk_score"] == 0.0  # short-circuited

        # 6. decide: read_order → ALLOW
        r = await client.post(
            "/api/v1/decide",
            json={"