"""Supabase Security Logging & Centralized Telemetry Service.

Streams only essential call logs to Supabase:
id, created_at, tool, verdict, and a Groq-generated natural language explanation
explaining why the action was ALLOWED, BLOCKED, or ESCALATED.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
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

SQL_SCHEMA = """-- AgentShield Call Logs Table for Supabase
-- Contains ONLY: id, created_at, tool, verdict, and groq_explanation
DROP TABLE IF EXISTS agentshield_call_logs CASCADE;

CREATE TABLE agentshield_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    tool TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'ESCALATE', 'BLOCK', 'HITL')),
    groq_explanation TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_call_logs_verdict ON agentshield_call_logs(verdict);
CREATE INDEX IF NOT EXISTS idx_call_logs_created_at ON agentshield_call_logs(created_at DESC);

ALTER TABLE agentshield_call_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access to call logs" 
ON agentshield_call_logs FOR SELECT USING (true);

CREATE POLICY "Allow insert access to call logs" 
ON agentshield_call_logs FOR INSERT WITH CHECK (true);
"""


def _get_supabase_headers(key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "return=minimal",
    }


def generate_groq_explanation(
    tool: str,
    verdict: str,
    reasons: list[str],
    risk_score: float,
    arguments: Optional[dict[str, Any]] = None,
) -> str:
    """Generate a concise 1-2 sentence explanation of why this call was ALLOWED, BLOCKED, or ESCALATED using Groq."""
    groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if groq_api_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_api_key)
            r_str = ", ".join(reasons) if reasons else "Security policy check"
            prompt = (
                "You are an AI security explanation engine for AgentShield.\n"
                f"In 1-2 clear, direct sentences, explain why this tool execution was {verdict}:\n"
                f"- Tool: {tool}\n"
                f"- Verdict: {verdict}\n"
                f"- Policy & Gate Reasons: {r_str}\n"
                f"- Risk Score: {risk_score}/100\n"
                "Be concise, professional, and explain the exact security reasoning without preamble."
            )
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="qwen/qwen3.8-27b",
                max_tokens=100,
                temperature=0.3,
            )
            ans = res.choices[0].message.content.strip()
            if ans:
                return ans
        except Exception as e:
            logger.warning("Groq explanation failed: %s", e)

    # Fallback explanation
    if reasons:
        return f"Action was {verdict.lower()}ed: {reasons[0]}"
    if verdict == "ALLOW":
        return f"Action '{tool}' was allowed based on verified permissions and low risk score ({risk_score}/100)."
    elif verdict == "BLOCK":
        return f"Action '{tool}' was blocked to prevent high-risk unauthorized operation ({risk_score}/100)."
    else:
        return f"Action '{tool}' was escalated for supervisor review due to sensitive policy constraints ({risk_score}/100)."


async def send_to_supabase(
    record: dict[str, Any] | list[dict[str, Any]],
    url: Optional[str] = None,
    key: Optional[str] = None,
    table: Optional[str] = None,
) -> bool:
    """Send a record or list of records to Supabase via PostgREST."""
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
    """Fire-and-forget logging to Supabase with Groq explanation."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return

    async def _async_log():
        # Generate Groq explanation in background thread
        groq_exp = await asyncio.to_thread(
            generate_groq_explanation,
            tool,
            verdict,
            reasons,
            risk_score,
            arguments,
        )

        record = {
            "id": str(decision_id),
            "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
            "tool": tool,
            "verdict": verdict,
            "groq_explanation": groq_exp,
        }
        await send_to_supabase(record)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_log())
    except RuntimeError:
        pass


async def sync_all_decisions(
    db: AsyncSession,
    url: Optional[str] = None,
    key: Optional[str] = None,
    table: Optional[str] = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Sync recent decisions from local database into Supabase with Groq explanations."""
    stmt = select(Decision).order_by(Decision.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    decisions = list(result.scalars().all())

    if not decisions:
        return {"synced": 0, "message": "No decisions to sync"}

    import concurrent.futures

    def _format_decision(d: Decision) -> dict[str, Any]:
        reasons = d.reasons or []
        groq_exp = generate_groq_explanation(
            tool=d.tool,
            verdict=d.verdict,
            reasons=reasons,
            risk_score=float(d.risk_score),
            arguments=d.arguments,
        )
        return {
            "id": str(d.id),
            "created_at": d.created_at.isoformat(),
            "tool": d.tool,
            "verdict": d.verdict,
            "groq_explanation": groq_exp,
        }

    def _parallel_process():
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            return list(pool.map(_format_decision, reversed(decisions)))

    records = await asyncio.to_thread(_parallel_process)
    success = await send_to_supabase(records, url=url, key=key, table=table)
    return {
        "total": len(records),
        "synced": len(records) if success else 0,
        "success": success,
        "message": f"Successfully synced {len(records)} call logs with Groq explanations to Supabase."
        if success
        else "Supabase batch insert failed. Verify URL, API key, and table schema.",
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
