"""receipts settlements and financial movements

Revision ID: 20260429_0017
Revises: 20260429_0016
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260429_0017"
down_revision = "20260429_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settlements",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="inflow"),
        sa.Column("settlement_type", sa.String(length=40), nullable=False, server_default="receipt"),
        sa.Column("financial_title_id", sa.String(length=80), sa.ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_method_id", sa.String(length=80), sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("competency_date", sa.Date(), nullable=True),
        sa.Column("received_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("interest_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("penalty_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("title_settled_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("movement_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(length=80), nullable=True),
        sa.Column("evidence_reference", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("reversal_of_settlement_id", sa.String(length=80), sa.ForeignKey("settlements.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "source_type", "source_id", name="uq_settlements_company_source"),
    )
    op.create_index("ix_settlements_company_id", "settlements", ["company_id"])
    op.create_index("ix_settlements_company_title", "settlements", ["company_id", "financial_title_id"])
    op.create_index("ix_settlements_company_account", "settlements", ["company_id", "financial_account_id"])
    op.create_index("ix_settlements_company_date", "settlements", ["company_id", "settlement_date"])
    op.create_index("ix_settlements_company_status", "settlements", ["company_id", "status"])
    op.create_index("ix_settlements_company_source", "settlements", ["company_id", "source_type", "source_id"])

    op.create_table(
        "financial_movements",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("movement_type", sa.String(length=40), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("settlement_id", sa.String(length=80), sa.ForeignKey("settlements.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("financial_title_id", sa.String(length=80), sa.ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="posted"),
        sa.Column("reconciliation_status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("reversal_of_movement_id", sa.String(length=80), sa.ForeignKey("financial_movements.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "source_type", "source_id", name="uq_financial_movements_company_source"),
    )
    op.create_index("ix_financial_movements_company_id", "financial_movements", ["company_id"])
    op.create_index("ix_financial_movements_company_account", "financial_movements", ["company_id", "financial_account_id"])
    op.create_index("ix_financial_movements_company_date", "financial_movements", ["company_id", "movement_date"])
    op.create_index("ix_financial_movements_company_status", "financial_movements", ["company_id", "status"])
    op.create_index("ix_financial_movements_company_reconciliation", "financial_movements", ["company_id", "reconciliation_status"])
    op.create_index("ix_financial_movements_company_source", "financial_movements", ["company_id", "source_type", "source_id"])
    op.create_index("ix_financial_movements_company_title", "financial_movements", ["company_id", "financial_title_id"])

    op.create_table(
        "financial_account_balances",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("current_balance_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("last_movement_id", sa.String(length=80), sa.ForeignKey("financial_movements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "financial_account_id", name="uq_financial_account_balances_company_account"),
    )
    op.create_index("ix_financial_account_balances_company_id", "financial_account_balances", ["company_id"])
    op.create_index("ix_financial_account_balances_account", "financial_account_balances", ["financial_account_id"])

    op.alter_column("settlements", "direction", server_default=None)
    op.alter_column("settlements", "settlement_type", server_default=None)
    op.alter_column("settlements", "discount_amount", server_default=None)
    op.alter_column("settlements", "interest_amount", server_default=None)
    op.alter_column("settlements", "penalty_amount", server_default=None)
    op.alter_column("settlements", "fee_amount", server_default=None)
    op.alter_column("settlements", "source_type", server_default=None)
    op.alter_column("settlements", "status", server_default=None)
    op.alter_column("financial_movements", "currency", server_default=None)
    op.alter_column("financial_movements", "status", server_default=None)
    op.alter_column("financial_movements", "reconciliation_status", server_default=None)
    op.alter_column("financial_account_balances", "current_balance_amount", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_financial_account_balances_account", table_name="financial_account_balances")
    op.drop_index("ix_financial_account_balances_company_id", table_name="financial_account_balances")
    op.drop_table("financial_account_balances")

    op.drop_index("ix_financial_movements_company_title", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_source", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_reconciliation", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_status", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_date", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_account", table_name="financial_movements")
    op.drop_index("ix_financial_movements_company_id", table_name="financial_movements")
    op.drop_table("financial_movements")

    op.drop_index("ix_settlements_company_source", table_name="settlements")
    op.drop_index("ix_settlements_company_status", table_name="settlements")
    op.drop_index("ix_settlements_company_date", table_name="settlements")
    op.drop_index("ix_settlements_company_account", table_name="settlements")
    op.drop_index("ix_settlements_company_title", table_name="settlements")
    op.drop_index("ix_settlements_company_id", table_name="settlements")
    op.drop_table("settlements")
