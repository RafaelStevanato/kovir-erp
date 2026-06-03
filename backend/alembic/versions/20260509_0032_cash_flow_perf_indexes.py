"""cash flow performance indexes

Revision ID: 20260509_0032
Revises: 20260509_0031
Create Date: 2026-05-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0032"
down_revision = "20260509_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_financial_titles_company_direction_account_due ON financial_titles (company_id, direction, expected_financial_account_id, due_date)",
        "CREATE INDEX IF NOT EXISTS ix_bank_statement_lines_company_account_date ON bank_statement_lines (company_id, financial_account_id, line_date)",
        "CREATE INDEX IF NOT EXISTS ix_bank_statement_lines_company_status_date ON bank_statement_lines (company_id, status, line_date)",
        "CREATE INDEX IF NOT EXISTS ix_reconciliation_matches_company_account_created ON reconciliation_matches (company_id, financial_account_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_reconciliation_matches_company_status_created ON reconciliation_matches (company_id, status, created_at)",
    ):
        conn.execute(sa.text(statement))


def downgrade() -> None:
    conn = op.get_bind()
    for index_name in (
        "ix_reconciliation_matches_company_status_created",
        "ix_reconciliation_matches_company_account_created",
        "ix_bank_statement_lines_company_status_date",
        "ix_bank_statement_lines_company_account_date",
        "ix_financial_titles_company_direction_account_due",
    ):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
