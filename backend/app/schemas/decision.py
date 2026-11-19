"""Pydantic schemas for the /decide endpoint."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DecideRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    resource_type: str | None = Field(default=None, max_length=80)
    data_classification: str | None = Field(default=None, max_length=40)
    approval_id: UUID | None = None  # Resuming an approved HITL escalation


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

    policy_id: UUID | None = None
    policy_rule: str | None = None
    policy_effect: str | None = None

    injection_score: float = 0.0

    # PII / DLP
    pii_classification: str | None = None
    pii_labels: list[str] = Field(default_factory=list)
    masked: bool = False
    masked_arguments: dict[str, Any] | None = None

    approval_id: UUID | None = None

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
    policy_rule: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    injection_score: float = 0.0
    pii_labels: list[str] = Field(default_factory=list)
    masked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}