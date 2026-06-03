"""financial_titles performance indexes

Revision ID: 20260509_0030
Revises: 20260508_0029
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0030"
down_revision = "20260508_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_financial_titles_company_direction_status_due "
            "ON financial_titles (company_id, direction, status, due_date)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_financial_titles_company_direction_status_due"))
