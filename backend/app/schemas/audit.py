"""Pydantic schemas for audit endpoints."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    seq: int
    id: UUID
    event_type: str
    agent_id: UUID | None
    tenant_id: UUID | None
    payload: dict[str, Any]
    prev_hash: str
    hash: str
    signature: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditVerificationOut(BaseModel):
    total_events: int
    verified_events: int
    valid: bool
    broken_at_seq: int | None = None
    reason: str | None = None
    errors: list[str] = []
