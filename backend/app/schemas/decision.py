"""Pydantic schemas for the /decide endpoint."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DecideRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    resource_type: Optional[str] = Field(default=None, max_length=80)


class Signal(BaseModel):
    name: str
    value: Any
    points: float
    reason: str


class DecideResponse(BaseModel):
    decision_id: UUID
    verdict: str          # ALLOW / BLOCK / ESCALATE
    risk_score: float
    tool: str
    action: str
    reasons: list[str]
    signals: list[Signal]
    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionOut(BaseModel):
    id: UUID
    agent_id: UUID
    tool: str
    action: str
    verdict: str
    risk_score: float
    reasons: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}