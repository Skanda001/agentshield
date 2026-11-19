"""Pydantic schemas for policies and versioning."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RuleSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    effect: str = Field(pattern=r"^(allow|deny|escalate|mask)$")
    agent: str | None = None
    role: str | None = None
    action: str | None = None
    resource: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=1000)


class PolicyDocument(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)
    description: str | None = None
    rules: list[RuleSchema]

    @field_validator("rules")
    @classmethod
    def at_least_one_rule(cls, v: list[RuleSchema]) -> list[RuleSchema]:
        if not v:
            raise ValueError("policy must contain at least one rule")
        return v


class PolicyCreate(BaseModel):
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    document: PolicyDocument


class PolicyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    current_version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyVersionOut(BaseModel):
    id: UUID
    policy_id: UUID
    version: int
    document: dict
    document_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyEvaluationPreview(BaseModel):
    """Response for the /policies/{id}/test endpoint."""
    matched_rule: str | None
    effect: str | None
    reason: str


class PolicySimulateRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    resource_type: str | None = None
    data_classification: str | None = None


class PolicySimulateResponse(BaseModel):
    verdict: str  # ALLOW, BLOCK, ESCALATE, MASK
    risk_score: float
    reasons: list[str]
    matched_rule: str | None = None
    policy_effect: str | None = None
    policy_reason: str | None = None
    action: str
    resource_type: str
    signals: list[dict[str, Any]] = Field(default_factory=list)
    injection_score: float = 0.0
    pii_detected: list[str] = Field(default_factory=list)
    masked: bool = False
    masked_arguments: dict[str, Any] | None = None
