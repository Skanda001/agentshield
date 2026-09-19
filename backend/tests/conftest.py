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
os.environ.setdefault("AUDIT_HMAC_SECRET", "test-only-audit-secret-with-32-chars-000002")


# Windows: psycopg async requires SelectorEventLoop, not ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())