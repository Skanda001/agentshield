"""KillSwitch model. One row per active or historical suspension."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KillSwitch(Base):
    __tablename__ = "kill_switches"
    __table_args__ = (
        Index("ix_kill_switches_scope_active", "scope", "is_active"),
        Index("ix_kill_switches_target_active", "target_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Scope: "agent" | "tool" | "tenant" | "global"
    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Target identifier — meaning depends on scope:
    #   agent  -> agents.id (stringified UUID)
    #   tool   -> tool name (string)
    #   tenant -> tenants.id (stringified UUID)
    #   global -> null
    target_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    activated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    deactivated_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivation_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)