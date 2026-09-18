"""create audit_log_seq sequence

Revision ID: 7283b1009a54
Revises: ee04823c3ea9
Create Date: 2026-09-18 20:56:42.356096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7283b1009a54'
down_revision: Union[str, None] = 'ee04823c3ea9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS audit_log_seq")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS audit_log_seq")