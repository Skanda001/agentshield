"""Pydantic schemas for approvals."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalOut(BaseModel):
    id: UUID
    decision_id: UUID
    agent_id: UUID
    tenant_id: UUID
    status: str
    tool: str
    resource_type: Optional[str]
    request_context: dict[str, Any]
    decided_by: Optional[str]
    decision_note: Optional[str]
    decided_at: Optional[datetime]
    notified_at: Optional[datetime]
    notification_channel: Optional[str]
    notification_error: Optional[str]
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    approved: bool
    decided_by: str = Field(min_length=1, max_length=120)
    note: Optional[str] = Field(default=None, max_length=1000)