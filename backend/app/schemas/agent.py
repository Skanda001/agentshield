"""Pydantic schemas for agent and tenant endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Tenant ────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9-]+$")


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Agent ─────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    tenant_id: UUID
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = None
    role: str = Field(default="support", max_length=60)
    scopes: list[str] = Field(default_factory=list)

    @field_validator("scopes")
    @classmethod
    def scopes_valid(cls, v: list[str]) -> list[str]:
        for scope in v:
            if not isinstance(scope, str) or len(scope) > 80:
                raise ValueError("each scope must be a string <= 80 chars")
        return v


class AgentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    role: str
    scopes: list[str]
    status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentCreateResponse(BaseModel):
    """Returned only on creation. Contains the plaintext API key exactly once."""
    agent: AgentOut
    api_key: str
    warning: str = "Store this API key now. It will never be shown again."


# ─── Auth ──────────────────────────────────────────────────────

class AgentTokenRequest(BaseModel):
    api_key: str = Field(min_length=10)


class AgentTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scopes: list[str]