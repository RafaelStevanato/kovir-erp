"""cash performance indexes

Revision ID: 20260509_0031
Revises: 20260509_0030
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0031"
down_revision = "20260509_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_settlements_company_status_date ON settlements (company_id, status, settlement_date)",
        "CREATE INDEX IF NOT EXISTS ix_settlements_company_account_date ON settlements (company_id, financial_account_id, settlement_date)",
        "CREATE INDEX IF NOT EXISTS ix_settlements_company_payment_method_date ON settlements (company_id, payment_method_id, settlement_date)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_status_date ON financial_movements (company_id, status, movement_date)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_account_date ON financial_movements (company_id, financial_account_id, movement_date)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_direction_date ON financial_movements (company_id, direction, movement_date)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_type_date ON financial_movements (company_id, movement_type, movement_date)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_reconciliation_date ON financial_movements (company_id, reconciliation_status, movement_date)",
    ):
        conn.execute(sa.text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for index_name in (
        "ix_financial_movements_company_reconciliation_date",
        "ix_financial_movements_company_type_date",
        "ix_financial_movements_company_direction_date",
        "ix_financial_movements_company_account_date",
        "ix_financial_movements_company_status_date",
        "ix_settlements_company_payment_method_date",
        "ix_settlements_company_account_date",
        "ix_settlements_company_status_date",
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
