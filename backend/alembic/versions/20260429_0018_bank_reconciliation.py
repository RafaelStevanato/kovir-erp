"""bank reconciliation statements and matches

Revision ID: 20260429_0018
Revises: 20260429_0017
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260429_0018"
down_revision = "20260429_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("statement_start_date", sa.Date(), nullable=True),
        sa.Column("statement_end_date", sa.Date(), nullable=True),
        sa.Column("opening_balance_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("closing_balance_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_inflow_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_outflow_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="processed"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "financial_account_id", "source_type", "source_id", name="uq_bank_statement_imports_company_account_source"),
    )
    op.create_index("ix_bank_statement_imports_company_id", "bank_statement_imports", ["company_id"])
    op.create_index("ix_bank_statement_imports_company_account", "bank_statement_imports", ["company_id", "financial_account_id"])
    op.create_index("ix_bank_statement_imports_company_status", "bank_statement_imports", ["company_id", "status"])
    op.create_index("ix_bank_statement_imports_company_period", "bank_statement_imports", ["company_id", "statement_start_date", "statement_end_date"])

    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("statement_import_id", sa.String(length=80), sa.ForeignKey("bank_statement_imports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_id", sa.String(length=180), nullable=True),
        sa.Column("line_date", sa.Date(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("document_number", sa.String(length=120), nullable=True),
        sa.Column("counterparty_name", sa.String(length=180), nullable=True),
        sa.Column("counterparty_document", sa.String(length=80), nullable=True),
        sa.Column("bank_reference", sa.String(length=180), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("match_confidence", sa.String(length=40), nullable=True),
        sa.Column("matched_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("ignored_reason", sa.String(length=500), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "financial_account_id", "external_id", name="uq_bank_statement_lines_company_account_external"),
    )
    op.create_index("ix_bank_statement_lines_company_id", "bank_statement_lines", ["company_id"])
    op.create_index("ix_bank_statement_lines_company_account", "bank_statement_lines", ["company_id", "financial_account_id"])
    op.create_index("ix_bank_statement_lines_company_status", "bank_statement_lines", ["company_id", "status"])
    op.create_index("ix_bank_statement_lines_company_date", "bank_statement_lines", ["company_id", "line_date"])
    op.create_index("ix_bank_statement_lines_company_amount", "bank_statement_lines", ["company_id", "direction", "amount"])
    op.create_index("ix_bank_statement_lines_import", "bank_statement_lines", ["statement_import_id"])

    op.create_table(
        "reconciliation_matches",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("statement_line_id", sa.String(length=80), sa.ForeignKey("bank_statement_lines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_movement_id", sa.String(length=80), sa.ForeignKey("financial_movements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("match_type", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("matched_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("movement_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("difference_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tolerance_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="confirmed"),
        sa.Column("confirmation_reason", sa.String(length=500), nullable=True),
        sa.Column("reversed_reason", sa.String(length=500), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("statement_line_id", "financial_movement_id", name="uq_reconciliation_matches_line_movement"),
    )
    op.create_index("ix_reconciliation_matches_company_id", "reconciliation_matches", ["company_id"])
    op.create_index("ix_reconciliation_matches_company_account", "reconciliation_matches", ["company_id", "financial_account_id"])
    op.create_index("ix_reconciliation_matches_company_status", "reconciliation_matches", ["company_id", "status"])
    op.create_index("ix_reconciliation_matches_line", "reconciliation_matches", ["statement_line_id"])
    op.create_index("ix_reconciliation_matches_movement", "reconciliation_matches", ["financial_movement_id"])

    op.alter_column("bank_statement_imports", "source_type", server_default=None)
    op.alter_column("bank_statement_imports", "line_count", server_default=None)
    op.alter_column("bank_statement_imports", "total_inflow_amount", server_default=None)
    op.alter_column("bank_statement_imports", "total_outflow_amount", server_default=None)
    op.alter_column("bank_statement_imports", "status", server_default=None)
    op.alter_column("bank_statement_lines", "status", server_default=None)
    op.alter_column("bank_statement_lines", "matched_amount", server_default=None)
    op.alter_column("reconciliation_matches", "match_type", server_default=None)
    op.alter_column("reconciliation_matches", "difference_amount", server_default=None)
    op.alter_column("reconciliation_matches", "tolerance_amount", server_default=None)
    op.alter_column("reconciliation_matches", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_reconciliation_matches_movement", table_name="reconciliation_matches")
    op.drop_index("ix_reconciliation_matches_line", table_name="reconciliation_matches")
    op.drop_index("ix_reconciliation_matches_company_status", table_name="reconciliation_matches")
    op.drop_index("ix_reconciliation_matches_company_account", table_name="reconciliation_matches")
    op.drop_index("ix_reconciliation_matches_company_id", table_name="reconciliation_matches")
    op.drop_table("reconciliation_matches")

    op.drop_index("ix_bank_statement_lines_import", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_company_amount", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_company_date", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_company_status", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_company_account", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_company_id", table_name="bank_statement_lines")
    op.drop_table("bank_statement_lines")

    op.drop_index("ix_bank_statement_imports_company_period", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_company_status", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_company_account", table_name="bank_statement_imports")
    op.drop_index("ix_bank_statement_imports_company_id", table_name="bank_statement_imports")
    op.drop_table("bank_statement_imports")
