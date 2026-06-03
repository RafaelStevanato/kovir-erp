"""purchases payables overview indexes

Revision ID: 20260509_0034
Revises: 20260509_0033
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0034"
down_revision = "20260509_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_purchases_company_status_created ON purchases (company_id, status, created_at)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_purchases_company_status_created"))
