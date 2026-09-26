"""Supabase Security Call Logs API.

Endpoints for managing Supabase connection, viewing call logs
(ALLOWED, BLOCKED, ESCALATED with reasons), and running 1-click sync.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_optional_agent
from app.db.models.agent import Agent
from app.db.models.decision import Decision
from app.services import supabase_logger

logger = logging.getLogger("agentshield.supabase.api")
router = APIRouter(prefix="/supabase", tags=["supabase"])


class SupabaseConfigRequest(BaseModel):
    supabase_url: str = Field(min_length=5, description="https://<project-ref>.supabase.co")
    supabase_key: str = Field(min_length=10, description="Supabase Anon Key or Service Role Key")
    supabase_table: str = Field(default="agentshield_call_logs")


class CallLogItem(BaseModel):
    id: UUID
    created_at: datetime
    tool: str
    verdict: str
    reasons: list[str]
    primary_reason: str
    risk_score: float
    arguments: dict[str, Any]
    agent_id: UUID
    policy_rule: Optional[str] = None
    policy_effect: Optional[str] = None
    data_classification: Optional[str] = None


class SupabaseStatusResponse(BaseModel):
    is_configured: bool
    supabase_url: Optional[str] = None
    supabase_table: str
    total_calls_logged: int
    allowed_count: int
    escalated_count: int
    blocked_count: int
    connected: bool = False
    connection_message: str


@router.get("/status", response_model=SupabaseStatusResponse)
async def get_supabase_status(db: AsyncSession = Depends(get_db)):
    """Check configuration and call breakdown for Supabase logging."""
    res = await db.execute(select(Decision))
    all_decisions = list(res.scalars().all())

    allowed = sum(1 for d in all_decisions if d.verdict == "ALLOW")
    escalated = sum(1 for d in all_decisions if d.verdict == "ESCALATE")
    blocked = sum(1 for d in all_decisions if d.verdict == "BLOCK")

    is_configured = bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)
    connected = False
    msg = "Supabase URL and API Key not configured. Using local PostgreSQL audit logging."

    if is_configured:
        probe = await supabase_logger.test_supabase_connection(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
            settings.SUPABASE_TABLE,
        )
        connected = probe.get("connected", False)
        msg = "Connected to Supabase table successfully." if connected else probe.get("error", "Connection error")

    return SupabaseStatusResponse(
        is_configured=is_configured,
        supabase_url=settings.SUPABASE_URL or None,
        supabase_table=settings.SUPABASE_TABLE,
        total_calls_logged=len(all_decisions),
        allowed_count=allowed,
        escalated_count=escalated,
        blocked_count=blocked,
        connected=connected,
        connection_message=msg,
    )


@router.get("/schema")
async def get_sql_schema():
    """Return the SQL schema to execute in Supabase SQL Editor."""
    return {
        "table": settings.SUPABASE_TABLE,
        "sql": supabase_logger.SQL_SCHEMA,
    }


@router.get("/logs", response_model=list[CallLogItem])
async def list_call_logs(
    verdict: Optional[str] = Query(default=None, pattern=r"^(ALLOW|ESCALATE|BLOCK)$"),
    tool: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all logged calls with verdicts and explainability reasons."""
    stmt = select(Decision).order_by(desc(Decision.created_at))
    if verdict:
        stmt = stmt.where(Decision.verdict == verdict)
    if tool:
        stmt = stmt.where(Decision.tool == tool)

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    decisions = list(result.scalars().all())

    items = []
    for d in decisions:
        reasons = d.reasons or []
        primary = reasons[0] if reasons else ("Safe execution permitted" if d.verdict == "ALLOW" else "Policy enforcement")
        items.append(
            CallLogItem(
                id=d.id,
                created_at=d.created_at,
                tool=d.tool,
                verdict=d.verdict,
                reasons=reasons,
                primary_reason=primary,
                risk_score=d.risk_score,
                arguments=d.arguments or {},
                agent_id=d.agent_id,
                policy_rule=d.policy_rule,
                policy_effect=d.policy_effect,
                data_classification=d.pii_classification,
            )
        )
    return items


@router.post("/config")
async def update_supabase_config(
    payload: SupabaseConfigRequest,
):
    """Update Supabase credentials and verify connection."""
    settings.SUPABASE_URL = payload.supabase_url.strip()
    settings.SUPABASE_KEY = payload.supabase_key.strip()
    settings.SUPABASE_TABLE = payload.supabase_table.strip()

    probe = await supabase_logger.test_supabase_connection(
        settings.SUPABASE_URL,
        settings.SUPABASE_KEY,
        settings.SUPABASE_TABLE,
    )

    return {
        "ok": probe.get("connected", False),
        "is_configured": True,
        "url": settings.SUPABASE_URL,
        "table": settings.SUPABASE_TABLE,
        "probe": probe,
    }


@router.post("/sync")
async def trigger_supabase_sync(
    db: AsyncSession = Depends(get_db),
):
    """Sync all decisions from database to Supabase."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise HTTPException(
            status_code=400,
            detail="Supabase credentials not configured. Please provide SUPABASE_URL and SUPABASE_KEY.",
        )

    res = await supabase_logger.sync_all_decisions(
        db,
        url=settings.SUPABASE_URL,
        key=settings.SUPABASE_KEY,
        table=settings.SUPABASE_TABLE,
    )
    return res
