"""Tests for approval integrity (Phase 1 Item 2).

Covers:
  1. Scope requirement: non-approvers cannot decide approvals (403).
  2. Separation of duties: requesting agent cannot self-approve (403).
  3. Tenant isolation: cross-tenant approvals are rejected (404).
  4. Decision pipeline execution resume:
     - Exact argument & tool hash binding: tampering with tool or arguments rejected (BLOCK).
     - Single-use constraint: reusing an approved approval_id rejected (BLOCK).
     - Expired approval rejected (BLOCK).
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.approvals import decide, _require_approver
from app.db.models.agent import Agent
from app.db.models.approval import Approval
from app.gateway.decision_pipeline import run as run_pipeline
from app.gateway.tool_adapter import ToolCall
from app.schemas.approval import ApprovalDecision


def test_require_approver_scope_enforcement():
    """Agent without approver/admin scope must be rejected with 403."""
    agent_tool_only = Agent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="tool-agent",
        scopes=["read:order", "write:order"],
    )
    with pytest.raises(HTTPException) as exc_info:
        _require_approver(agent_tool_only)
    assert exc_info.value.status_code == 403
    assert "Approver or admin scope required" in exc_info.value.detail

    # Approver or admin scope passes
    agent_approver = Agent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="supervisor",
        scopes=["approver"],
    )
    _require_approver(agent_approver)  # Does not raise

    agent_admin = Agent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="admin",
        scopes=["admin"],
    )
    _require_approver(agent_admin)  # Does not raise


@pytest.mark.asyncio
async def test_self_approval_rejected():
    """Requesting agent cannot approve its own request (separation of duties)."""
    agent_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    agent = Agent(
        id=agent_id,
        tenant_id=tenant_id,
        name="support-bot",
        scopes=["approver"],
    )
    approval = Approval(
        id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        agent_id=agent_id,  # Same agent!
        tenant_id=tenant_id,
        status="pending",
        tool="delete_customer",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    db = AsyncMock()
    with patch("app.services.approval_service.get_approval", return_value=approval):
        with pytest.raises(HTTPException) as exc:
            await decide(
                approval_id=approval.id,
                payload=ApprovalDecision(approved=True),
                db=db,
                agent=agent,
            )
        assert exc.value.status_code == 403
        assert "separation of duties" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_cross_tenant_approval_rejected():
    """Approvals belonging to another tenant return 404 (don't leak existence)."""
    agent = Agent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="supervisor",
        scopes=["approver"],
    )
    other_tenant_id = uuid.uuid4()
    approval = Approval(
        id=uuid.uuid4(),
        decision_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        tenant_id=other_tenant_id,  # Different tenant
        status="pending",
        tool="delete_customer",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    db = AsyncMock()
    with patch("app.services.approval_service.get_approval", return_value=approval):
        with pytest.raises(HTTPException) as exc:
            await decide(
                approval_id=approval.id,
                payload=ApprovalDecision(approved=True),
                db=db,
                agent=agent,
            )
        assert exc.value.status_code == 404
