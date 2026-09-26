"""Pydantic schemas for the /decide endpoint."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DecideRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    resource_type: Optional[str] = Field(default=None, max_length=80)
    data_classification: Optional[str] = Field(default=None, max_length=40)


class Signal(BaseModel):
    name: str
    value: Any
    points: float
    reason: str


class DecideResponse(BaseModel):
    decision_id: UUID
    verdict: str
    risk_score: float
    tool: str
    action: str
    reasons: list[str]
    signals: list[Signal]

    policy_id: Optional[UUID] = None
    policy_rule: Optional[str] = None
    policy_effect: Optional[str] = None

    injection_score: float = 0.0

    # PII / DLP (added Chunk 7)
    pii_classification: Optional[str] = None
    pii_labels: list[str] = Field(default_factory=list)

    approval_id: Optional[UUID] = None

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
    policy_rule: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}