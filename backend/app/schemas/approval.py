"""Pydantic schemas for approvals."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalOut(BaseModel):
    id: UUID
    decision_id: UUID
    agent_id: UUID
    tenant_id: UUID
    status: str
    tool: str
    resource_type: str | None
    request_context: dict[str, Any]
    decided_by: str | None
    decision_note: str | None
    decided_at: datetime | None
    notified_at: datetime | None
    notification_channel: str | None
    notification_error: str | None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=1000)
