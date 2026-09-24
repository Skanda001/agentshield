"""Email model — synthetic inbox. Some emails contain prompt-injection payloads."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        Index("ix_emails_customer", "customer_id"),
        Index("ix_emails_received", "received_at"),
        Index("ix_emails_flags", "is_spam", "is_malicious"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_id: Mapped[int] = mapped_column(nullable=False, unique=True, index=True)

    # Emails are always tied to a customer in this demo
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification flags (seeded, not learned)
    is_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_malicious: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Processing state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moved_to_spam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )