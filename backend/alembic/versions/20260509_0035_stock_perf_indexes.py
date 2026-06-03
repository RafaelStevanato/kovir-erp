"""stock performance indexes

Revision ID: 20260509_0035
Revises: 20260509_0034
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0035"
down_revision = "20260509_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_company_created ON stock_movements (company_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_stock_movements_company_source ON stock_movements (company_id, source_type, source_id)",
        "CREATE INDEX IF NOT EXISTS ix_stock_balances_company_updated ON stock_balances (company_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_stock_purchase_entry_items_entry_created ON stock_purchase_entry_items (purchase_entry_id, created_at)",
    ):
        conn.execute(sa.text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for index_name in (
        "ix_stock_purchase_entry_items_entry_created",
        "ix_stock_balances_company_updated",
        "ix_stock_movements_company_source",
        "ix_stock_movements_company_created",
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
