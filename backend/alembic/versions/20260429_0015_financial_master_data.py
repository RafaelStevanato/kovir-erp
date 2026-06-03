"""create financial master data foundation

Revision ID: 20260429_0015
Revises: 20260428_0014
Create Date: 2026-04-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_0015"
down_revision = "20260428_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chart_accounts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("account_type", sa.String(length=40), nullable=False),
        sa.Column("parent_id", sa.String(length=80), sa.ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("is_analytical", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("normal_balance", sa.String(length=20), nullable=True),
        sa.Column("accepts_entries", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "code", name="uq_chart_accounts_company_code"),
    )
    op.create_index("ix_chart_accounts_company_id", "chart_accounts", ["company_id"])
    op.create_index("ix_chart_accounts_company_status", "chart_accounts", ["company_id", "status"])
    op.create_index("ix_chart_accounts_company_type", "chart_accounts", ["company_id", "account_type"])
    op.create_index("ix_chart_accounts_company_name", "chart_accounts", ["company_id", "name"])

    op.create_table(
        "financial_categories",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category_type", sa.String(length=40), nullable=False),
        sa.Column("parent_id", sa.String(length=80), sa.ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("chart_account_id", sa.String(length=80), sa.ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cash_flow_group", sa.String(length=80), nullable=True),
        sa.Column("affects_cash_flow", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_cost_center", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "code", name="uq_financial_categories_company_code"),
    )
    op.create_index("ix_financial_categories_company_id", "financial_categories", ["company_id"])
    op.create_index("ix_financial_categories_company_status", "financial_categories", ["company_id", "status"])
    op.create_index("ix_financial_categories_company_type", "financial_categories", ["company_id", "category_type"])
    op.create_index("ix_financial_categories_company_name", "financial_categories", ["company_id", "name"])
    op.create_index("ix_financial_categories_company_chart_account", "financial_categories", ["company_id", "chart_account_id"])

    op.create_table(
        "cost_centers",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("center_type", sa.String(length=40), nullable=False, server_default="other"),
        sa.Column("parent_id", sa.String(length=80), sa.ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("is_analytical", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("responsible_name", sa.String(length=160), nullable=True),
        sa.Column("monthly_budget_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "code", name="uq_cost_centers_company_code"),
    )
    op.create_index("ix_cost_centers_company_id", "cost_centers", ["company_id"])
    op.create_index("ix_cost_centers_company_status", "cost_centers", ["company_id", "status"])
    op.create_index("ix_cost_centers_company_type", "cost_centers", ["company_id", "center_type"])
    op.create_index("ix_cost_centers_company_name", "cost_centers", ["company_id", "name"])

    op.create_table(
        "financial_accounts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("account_type", sa.String(length=40), nullable=False),
        sa.Column("institution_name", sa.String(length=160), nullable=True),
        sa.Column("branch_number", sa.String(length=40), nullable=True),
        sa.Column("account_number", sa.String(length=80), nullable=True),
        sa.Column("account_digit", sa.String(length=20), nullable=True),
        sa.Column("pix_key", sa.String(length=255), nullable=True),
        sa.Column("pix_key_type", sa.String(length=40), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("opening_balance_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("is_default_receivable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_default_payable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_financial_accounts_company_id", "financial_accounts", ["company_id"])
    op.create_index("ix_financial_accounts_company_status", "financial_accounts", ["company_id", "status"])
    op.create_index("ix_financial_accounts_company_type", "financial_accounts", ["company_id", "account_type"])
    op.create_index("ix_financial_accounts_company_name", "financial_accounts", ["company_id", "name"])

    op.create_table(
        "payment_terms",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("term_type", sa.String(length=40), nullable=False, server_default="cash"),
        sa.Column("installments", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_due_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("generate_on_sale", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "name", name="uq_payment_terms_company_name"),
    )
    op.create_index("ix_payment_terms_company_id", "payment_terms", ["company_id"])
    op.create_index("ix_payment_terms_company_status", "payment_terms", ["company_id", "status"])
    op.create_index("ix_payment_terms_company_type", "payment_terms", ["company_id", "term_type"])

    op.alter_column("chart_accounts", "is_analytical", server_default=None)
    op.alter_column("chart_accounts", "accepts_entries", server_default=None)
    op.alter_column("chart_accounts", "status", server_default=None)
    op.alter_column("financial_categories", "affects_cash_flow", server_default=None)
    op.alter_column("financial_categories", "requires_cost_center", server_default=None)
    op.alter_column("financial_categories", "status", server_default=None)
    op.alter_column("cost_centers", "center_type", server_default=None)
    op.alter_column("cost_centers", "is_analytical", server_default=None)
    op.alter_column("cost_centers", "status", server_default=None)
    op.alter_column("financial_accounts", "currency", server_default=None)
    op.alter_column("financial_accounts", "opening_balance_amount", server_default=None)
    op.alter_column("financial_accounts", "is_default_receivable", server_default=None)
    op.alter_column("financial_accounts", "is_default_payable", server_default=None)
    op.alter_column("financial_accounts", "status", server_default=None)
    op.alter_column("payment_terms", "term_type", server_default=None)
    op.alter_column("payment_terms", "installments", server_default=None)
    op.alter_column("payment_terms", "first_due_days", server_default=None)
    op.alter_column("payment_terms", "interval_days", server_default=None)
    op.alter_column("payment_terms", "generate_on_sale", server_default=None)
    op.alter_column("payment_terms", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_payment_terms_company_type", table_name="payment_terms")
    op.drop_index("ix_payment_terms_company_status", table_name="payment_terms")
    op.drop_index("ix_payment_terms_company_id", table_name="payment_terms")
    op.drop_table("payment_terms")

    op.drop_index("ix_financial_accounts_company_name", table_name="financial_accounts")
    op.drop_index("ix_financial_accounts_company_type", table_name="financial_accounts")
    op.drop_index("ix_financial_accounts_company_status", table_name="financial_accounts")
    op.drop_index("ix_financial_accounts_company_id", table_name="financial_accounts")
    op.drop_table("financial_accounts")

    op.drop_index("ix_cost_centers_company_name", table_name="cost_centers")
    op.drop_index("ix_cost_centers_company_type", table_name="cost_centers")
    op.drop_index("ix_cost_centers_company_status", table_name="cost_centers")
    op.drop_index("ix_cost_centers_company_id", table_name="cost_centers")
    op.drop_table("cost_centers")

    op.drop_index("ix_financial_categories_company_chart_account", table_name="financial_categories")
    op.drop_index("ix_financial_categories_company_name", table_name="financial_categories")
    op.drop_index("ix_financial_categories_company_type", table_name="financial_categories")
    op.drop_index("ix_financial_categories_company_status", table_name="financial_categories")
    op.drop_index("ix_financial_categories_company_id", table_name="financial_categories")
    op.drop_table("financial_categories")

    op.drop_index("ix_chart_accounts_company_name", table_name="chart_accounts")
    op.drop_index("ix_chart_accounts_company_type", table_name="chart_accounts")
    op.drop_index("ix_chart_accounts_company_status", table_name="chart_accounts")
    op.drop_index("ix_chart_accounts_company_id", table_name="chart_accounts")
    op.drop_table("chart_accounts")
