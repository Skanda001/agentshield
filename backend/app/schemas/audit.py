"""Pydantic schemas for audit endpoints."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    seq: int
    id: UUID
    event_type: str
    agent_id: Optional[UUID]
    tenant_id: Optional[UUID]
    payload: dict[str, Any]
    prev_hash: str
    hash: str
    signature: str
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditVerificationOut(BaseModel):
    total_events: int
    verified_events: int
    valid: bool
    broken_at_seq: Optional[int] = None
    reason: Optional[str] = None
    errors: list[str] = []