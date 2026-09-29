"""Pydantic schemas for policies and versioning."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RuleSchema(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    effect: str = Field(pattern=r"^(allow|deny|escalate|mask)$")
    agent: Optional[str] = None
    role: Optional[str] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=1000)


class PolicyDocument(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)
    description: Optional[str] = None
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
    description: Optional[str] = None
    document: PolicyDocument


class PolicyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
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
    matched_rule: Optional[str]
    effect: Optional[str]
    reason: str


class PolicySimulateRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)
    resource_type: Optional[str] = None
    data_classification: Optional[str] = None


class PolicySimulateResponse(BaseModel):
    verdict: str  # ALLOW, BLOCK, ESCALATE, MASK
    risk_score: float
    reasons: list[str]
    matched_rule: Optional[str] = None
    policy_effect: Optional[str] = None
    policy_reason: Optional[str] = None
    action: str
    resource_type: str
    signals: list[dict[str, Any]] = Field(default_factory=list)
    injection_score: float = 0.0
    pii_detected: list[str] = Field(default_factory=list)
    masked: bool = False
    masked_arguments: Optional[dict[str, Any]] = None