"""Shared pytest configuration.

Fixes the Windows ProactorEventLoop issue for psycopg async.
Also seeds the required env vars so tests can import the app.
"""
import asyncio
import os
import sys

# Must run before any test module imports app.*
os.environ["DEMO_MODE"] = "true"
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://agentshield:agentshield@localhost:5433/agentshield")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AGENTSHIELD_JWT_SECRET", "test-only-secret-with-at-least-32-chars-0001")
os.environ.setdefault("AUDIT_HMAC_SECRET", "dev-only-audit-secret-change-me-please-0987654321")
os.environ.setdefault("API_KEY_HMAC_SECRET", "dev-only-api-key-secret-change-me-1234567890")

try:
    from app.core.config import settings
    settings.DEMO_MODE = True
except Exception:
    pass


# Windows: psycopg async requires SelectorEventLoop, not ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest

@pytest.fixture(autouse=True)
def enable_demo_mode_fixture(monkeypatch):
    """Ensure DEMO_MODE=True for all test suites."""
    try:
        from app.core.config import settings
        monkeypatch.setattr(settings, "DEMO_MODE", True)
    except Exception:
        pass