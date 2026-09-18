"""AuditLog — append-only, hash-chained, HMAC-signed."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Sequence for total ordering of audit events
audit_seq = Sequence("audit_log_seq")


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_agent_created", "agent_id", "created_at"),
        Index("ix_audit_log_event_type_created", "event_type", "created_at"),
    )

    # Monotonic sequence: total order, no gaps under concurrent inserts
    seq: Mapped[int] = mapped_column(
        BigInteger, audit_seq, primary_key=True, autoincrement=True
    )

    # Application-level id for external references
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )

    # What happened
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # examples: decision.made, policy.created, agent.registered, approval.requested

    # Who
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Payload — free-form but typically contains decision snapshot
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Chain
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)

    # Optional reason / free text
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )