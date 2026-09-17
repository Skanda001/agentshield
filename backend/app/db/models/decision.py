"""Decision model. One row per tool-call decision AgentShield makes."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_agent_created", "agent_id", "created_at"),
        Index("ix_decisions_verdict_created", "verdict", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The call being evaluated
    tool: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)  # read / write / delete / send
    resource_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    arguments: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # The outcome
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)  # ALLOW / BLOCK / ESCALATE
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    signals: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Optional: human-readable note (used later by policy / HITL)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )