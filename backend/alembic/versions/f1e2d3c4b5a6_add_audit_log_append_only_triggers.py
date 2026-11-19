"""Add append-only triggers to audit_log.

Revision ID: f1e2d3c4b5a6
Revises: a1b2c3d4e5f6
Create Date: 2026-11-19

Why
---
The audit chain is tamper-evident (HMAC-chained hashes) but database
administrators with direct write access can bypass the application layer.
Adding PostgreSQL triggers that raise an exception on UPDATE, DELETE, and
TRUNCATE makes the table append-only at the database level.

The application code never updates or deletes audit_log rows; these
operations are programming errors that should fail loudly.

Downgrade
---------
Drops the triggers and the trigger function so the table returns to its
previous state. Historical data is unaffected.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f1e2d3c4b5a6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_no_modify()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_log is append-only: % is not permitted. '
                'The integrity of the cryptographic audit chain depends on immutable rows.',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_no_modify();
    """)

    op.execute("""
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_no_modify();
    """)

    op.execute("""
        CREATE TRIGGER audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT
        EXECUTE FUNCTION audit_log_no_modify();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_no_modify();")
