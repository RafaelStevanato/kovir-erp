"""reconciliation performance indexes

Revision ID: 20260509_0033
Revises: 20260509_0032
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0033"
down_revision = "20260509_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_bank_statement_lines_company_account_status_date ON bank_statement_lines (company_id, financial_account_id, status, line_date)",
        "CREATE INDEX IF NOT EXISTS ix_reconciliation_matches_company_account_status_created ON reconciliation_matches (company_id, financial_account_id, status, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_financial_movements_company_account_reconciliation_date ON financial_movements (company_id, financial_account_id, reconciliation_status, movement_date)",
    ):
        conn.execute(sa.text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for index_name in (
        "ix_financial_movements_company_account_reconciliation_date",
        "ix_reconciliation_matches_company_account_status_created",
        "ix_bank_statement_lines_company_account_status_date",
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
