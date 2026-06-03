"""settlements: add index on competency_date

Revision ID: 20260504_0023
Revises: 20260504_0022
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

revision = "20260504_0023"
down_revision = "20260504_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_settlements_competency_date
        ON settlements (competency_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_settlements_payment_method_id
        ON settlements (payment_method_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_settlements_payment_method_id")
    op.execute("DROP INDEX IF EXISTS ix_settlements_competency_date")
