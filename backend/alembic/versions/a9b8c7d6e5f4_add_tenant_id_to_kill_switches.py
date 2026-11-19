"""Add tenant_id column to kill_switches table.

Revision ID: a9b8c7d6e5f4
Revises: f1e2d3c4b5a6
Create Date: 2026-11-19

Why
---
The KillSwitch model now carries a tenant_id so that:
  - Non-global switches can be scoped to a specific tenant.
  - GET /kill-switch only shows the caller's own switches + global ones.
  - The deactivate endpoint can verify the caller owns the switch.

Global switches (scope='global') have tenant_id=NULL; all other switches
should have tenant_id set to the activating agent's tenant.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kill_switches",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_kill_switches_tenant",
        "kill_switches",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_kill_switches_tenant", table_name="kill_switches")
    op.drop_column("kill_switches", "tenant_id")
