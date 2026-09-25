"""Shared pytest configuration.

Fixes the Windows ProactorEventLoop issue for psycopg async.
Also seeds the required env vars so tests can import the app.
"""
import asyncio
import os
import sys

# Must run before any test module imports app.*
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://agentshield:agentshield@localhost:5433/agentshield")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("AGENTSHIELD_JWT_SECRET", "test-only-secret-with-at-least-32-chars-0001")
os.environ.setdefault("AUDIT_HMAC_SECRET", "dev-only-audit-secret-change-me-please-0987654321")


# Windows: psycopg async requires SelectorEventLoop, not ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())