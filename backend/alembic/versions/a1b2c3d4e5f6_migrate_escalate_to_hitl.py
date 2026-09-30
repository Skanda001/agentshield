"""Migrate ESCALATE → HITL in decisions.verdict.

Revision ID: a1b2c3d4e5f6
Revises: bfafc46d2ee7
Create Date: 2026-09-30

Background
----------
The canonical verdict terminology was standardised to HITL (Human-in-the-Loop).
Any rows written by earlier code versions use the old string 'ESCALATE'.
This migration renames them in-place so the database stays consistent
with the application code.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "bfafc46d2ee7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename all ESCALATE verdicts to HITL
    op.execute(
        sa.text("UPDATE decisions SET verdict = 'HITL' WHERE verdict = 'ESCALATE'")
    )


def downgrade() -> None:
    # Restore HITL → ESCALATE (rollback path)
    op.execute(
        sa.text("UPDATE decisions SET verdict = 'ESCALATE' WHERE verdict = 'HITL'")
    )
