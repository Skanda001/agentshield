"""End-to-end smoke test for tenant + agent + token + me flow."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.models.agent import Agent
from app.db.models.tenant import Tenant
from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.mark.asyncio
async def test_full_agent_flow():
    transport = ASGITransport(app=app)
    slug = f"acme-support-{uuid.uuid4().hex[:8]}"
    tenant_id = None
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create tenant
        r = await client.post(
            "/api/v1/tenants",
            json={"name": f"Acme Support {slug}", "slug": slug},
        )
        assert r.status_code == 201, r.text
        tenant_id = r.json()["id"]

        # 2. Create agent
        r = await client.post(
            "/api/v1/agents",
            json={
                "tenant_id": tenant_id,
                "name": "support-bot",
                "description": "Test agent",
                "role": "support",
                "scopes": ["read:order", "read:customer"],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        api_key = body["api_key"]
        assert api_key.startswith("ash_")

        # 3. Exchange API key for JWT
        r = await client.post(
            "/api/v1/agents/token",
            json={"api_key": api_key},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]

        # 4. Use the JWT
        r = await client.get(
            "/api/v1/agents/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "support-bot"

        # 5. Bad API key is rejected
        r = await client.post(
            "/api/v1/agents/token",
            json={"api_key": "ash_totally_wrong_key_here"},
        )
        assert r.status_code == 401

    if tenant_id:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Agent).where(Agent.tenant_id == uuid.UUID(tenant_id)))
            await db.execute(delete(Tenant).where(Tenant.id == uuid.UUID(tenant_id)))
            await db.commit()