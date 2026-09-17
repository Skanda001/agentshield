"""End-to-end smoke test for tenant + agent + token + me flow."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_full_agent_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create tenant
        r = await client.post(
            "/api/v1/tenants",
            json={"name": "Acme Support", "slug": "acme-support"},
        )
        assert r.status_code in (201, 400), r.text  # 400 if test rerun
        if r.status_code == 201:
            tenant_id = r.json()["id"]
        else:
            # fetch not implemented yet; re-run in clean DB
            pytest.skip("Tenant already exists; run against a clean DB")

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