"""Agent model. Represents a registered AI agent that can call tools."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("uq_agents_tenant_name", "tenant_id", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hashed API key — never store the plaintext
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Scopes this agent is allowed to use (e.g. ["read:order", "read:customer"])
    scopes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Role for RBAC (e.g. "support", "admin")
    role: Mapped[str] = mapped_column(String(60), nullable=False, default="support")

    # Status: active | suspended | revoked
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="agents")  # noqa: F821