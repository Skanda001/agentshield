"""Pydantic schemas for kill switches."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class KillSwitchActivate(BaseModel):
    scope: str = Field(pattern=r"^(agent|tool|tenant|global)$")
    target_id: Optional[str] = Field(default=None, max_length=120)
    reason: str = Field(min_length=3, max_length=1000)
    activated_by: str = Field(min_length=1, max_length=120)

    @field_validator("target_id")
    @classmethod
    def target_required_for_non_global(cls, v, info):
        scope = info.data.get("scope")
        if scope in ("agent", "tool", "tenant") and not v:
            raise ValueError(f"target_id is required for scope '{scope}'")
        if scope == "global" and v:
            raise ValueError("target_id must be null for scope 'global'")
        return v


class KillSwitchDeactivate(BaseModel):
    deactivated_by: str = Field(min_length=1, max_length=120)
    note: Optional[str] = Field(default=None, max_length=1000)


class KillSwitchOut(BaseModel):
    id: UUID
    scope: str
    target_id: Optional[str]
    reason: str
    is_active: bool
    activated_by: str
    activated_at: datetime
    deactivated_by: Optional[str]
    deactivated_at: Optional[datetime]
    deactivation_note: Optional[str]

    model_config = {"from_attributes": True}


class KillSwitchCheck(BaseModel):
    blocked: bool
    reason: Optional[str] = None
    scope: Optional[str] = None
    kill_switch_id: Optional[UUID] = None