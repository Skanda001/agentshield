"""Supabase Security Logging & Centralized Telemetry Service.

Streams all tool calls evaluated by AgentShield (ALLOWED, BLOCKED, ESCALATED)
along with full explainability reasons, risk scores, and arguments to Supabase.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.decision import Decision

logger = logging.getLogger("agentshield.supabase")

SQL_SCHEMA = """-- AgentShield Centralized Security Call Logs Table for Supabase
CREATE TABLE IF NOT EXISTS agentshield_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    tool TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'ESCALATE', 'BLOCK', 'HITL')),
    reasons TEXT[] DEFAULT '{}',
    primary_reason TEXT,
    risk_score NUMERIC DEFAULT 0,
    arguments JSONB DEFAULT '{}'::jsonb,
    agent_id TEXT,
    agent_name TEXT,
    policy_rule TEXT,
    policy_effect TEXT,
    data_classification TEXT,
    pii_labels TEXT[] DEFAULT '{}'
);

-- Optimize queries for SOC alerts, compliance audits, and analytics
CREATE INDEX IF NOT EXISTS idx_call_logs_verdict ON agentshield_call_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_call_logs_tool ON agentshield_call_logs(tool);
CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON agentshield_call_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_logs_agent ON agentshield_call_logs(agent_name);
"""


def _get_supabase_headers(key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "return=minimal",
    }


async def send_to_supabase(
    record: dict[str, Any],
    url: Optional[str] = None,
    key: Optional[str] = None,
    table: Optional[str] = None,
) -> bool:
    """Send a single record or list of records to Supabase via PostgREST."""
    target_url = (url or settings.SUPABASE_URL).rstrip("/")
    target_key = key or settings.SUPABASE_KEY
    target_table = table or settings.SUPABASE_TABLE

    if not target_url or not target_key:
        return False

    endpoint = f"{target_url}/rest/v1/{target_table}"
    payload = json.dumps(record, default=str).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers=_get_supabase_headers(target_key),
        method="POST",
    )

    def _sync_post():
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status in (200, 201, 204)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            logger.warning("Supabase insert HTTP error %s: %s", e.code, err_body)
            return False
        except Exception as e:
            logger.warning("Supabase connection error: %s", e)
            return False

    return await asyncio.to_thread(_sync_post)


def log_decision_async(
    *,
    decision_id: UUID | str,
    tool: str,
    verdict: str,
    reasons: list[str],
    risk_score: float,
    arguments: dict[str, Any],
    agent_id: Optional[UUID | str] = None,
    agent_name: Optional[str] = None,
    policy_rule: Optional[str] = None,
    policy_effect: Optional[str] = None,
    data_classification: Optional[str] = None,
    pii_labels: Optional[list[str]] = None,
    created_at: Optional[datetime] = None,
) -> None:
    """Fire-and-forget logging to Supabase without blocking the gateway pipeline."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return

    primary_reason = reasons[0] if reasons else ("Safe execution permitted" if verdict == "ALLOW" else "Policy enforcement")

    record = {
        "id": str(decision_id),
        "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
        "tool": tool,
        "verdict": verdict,
        "reasons": reasons or [],
        "primary_reason": primary_reason,
        "risk_score": float(risk_score),
        "arguments": arguments or {},
        "agent_id": str(agent_id) if agent_id else None,
        "agent_name": agent_name or "Agent",
        "policy_rule": policy_rule,
        "policy_effect": policy_effect,
        "data_classification": data_classification,
        "pii_labels": pii_labels or [],
    }

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_to_supabase(record))
    except RuntimeError:
        pass


async def sync_all_decisions(
    db: AsyncSession,
    url: Optional[str] = None,
    key: Optional[str] = None,
    table: Optional[str] = None,
) -> dict[str, Any]:
    """Sync all decisions from the local PostgreSQL database into Supabase."""
    stmt = select(Decision).order_by(Decision.created_at.asc())
    result = await db.execute(stmt)
    decisions = list(result.scalars().all())

    records = []
    for d in decisions:
        reasons = d.reasons or []
        primary = reasons[0] if reasons else (
            "Safe operation permitted" if d.verdict == "ALLOW" else "Policy enforcement"
        )
        records.append({
            "id": str(d.id),
            "created_at": d.created_at.isoformat(),
            "tool": d.tool,
            "verdict": d.verdict,
            "reasons": reasons,
            "primary_reason": primary,
            "risk_score": float(d.risk_score),
            "arguments": d.arguments or {},
            "agent_id": str(d.agent_id),
            "policy_rule": d.policy_rule,
            "policy_effect": d.policy_effect,
            "data_classification": d.pii_classification,
            "pii_labels": d.pii_labels or [],
        })

    if not records:
        return {"synced": 0, "message": "No decisions to sync"}

    success = await send_to_supabase(records, url=url, key=key, table=table)
    return {
        "total": len(records),
        "synced": len(records) if success else 0,
        "success": success,
        "message": f"Successfully synced {len(records)} decision call logs to Supabase."
        if success
        else "Supabase batch insert failed. Verify URL, API key, and that the table exists.",
    }


async def test_supabase_connection(url: str, key: str, table: str = "agentshield_call_logs") -> dict[str, Any]:
    """Test connection to Supabase table."""
    clean_url = url.rstrip("/")
    endpoint = f"{clean_url}/rest/v1/{table}?limit=1"
    req = urllib.request.Request(
        endpoint,
        headers=_get_supabase_headers(key),
        method="GET",
    )

    def _probe():
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"connected": True, "status": resp.status, "rows_found": len(data)}
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8")
            if e.code == 404 or "relation" in err:
                return {
                    "connected": False,
                    "error": f"Table '{table}' does not exist yet. Run the SQL schema script in your Supabase SQL Editor.",
                    "code": e.code,
                }
            return {"connected": False, "error": f"HTTP {e.code}: {err}", "code": e.code}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    return await asyncio.to_thread(_probe)
