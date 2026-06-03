"""add payment methods and sale payment plans

Revision ID: 20260428_0010
Revises: 20260428_0009
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0010"
down_revision = "20260428_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("method_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requires_reference", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_due_behavior", sa.String(length=40), nullable=False, server_default="immediate"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "code", name="uq_payment_methods_company_code"),
    )
    op.create_index("ix_payment_methods_company_id", "payment_methods", ["company_id"])
    op.create_index("ix_payment_methods_company_code", "payment_methods", ["company_id", "code"])
    op.create_index("ix_payment_methods_company_type", "payment_methods", ["company_id", "method_type"])
    op.create_index("ix_payment_methods_company_status", "payment_methods", ["company_id", "status"])

    op.create_table(
        "sale_payment_plans",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method_id", sa.String(length=80), sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_method_code", sa.String(length=80), nullable=False),
        sa.Column("payment_method_name", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("installments", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="planned"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sale_payment_plans_company_id", "sale_payment_plans", ["company_id"])
    op.create_index("ix_sale_payment_plans_sale_id", "sale_payment_plans", ["sale_id"])
    op.create_index("ix_sale_payment_plans_company_sale", "sale_payment_plans", ["company_id", "sale_id"])
    op.create_index("ix_sale_payment_plans_company_method", "sale_payment_plans", ["company_id", "payment_method_id"])
    op.create_index("ix_sale_payment_plans_company_method_code", "sale_payment_plans", ["company_id", "payment_method_code"])
    op.create_index("ix_sale_payment_plans_company_due_date", "sale_payment_plans", ["company_id", "due_date"])
    op.create_index("ix_sale_payment_plans_company_status", "sale_payment_plans", ["company_id", "status"])

    op.alter_column("payment_methods", "requires_reference", server_default=None)
    op.alter_column("payment_methods", "default_due_behavior", server_default=None)
    op.alter_column("payment_methods", "status", server_default=None)
    op.alter_column("sale_payment_plans", "installments", server_default=None)
    op.alter_column("sale_payment_plans", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sale_payment_plans_company_status", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_company_due_date", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_company_method_code", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_company_method", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_company_sale", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_sale_id", table_name="sale_payment_plans")
    op.drop_index("ix_sale_payment_plans_company_id", table_name="sale_payment_plans")
    op.drop_table("sale_payment_plans")

    op.drop_index("ix_payment_methods_company_status", table_name="payment_methods")
    op.drop_index("ix_payment_methods_company_type", table_name="payment_methods")
    op.drop_index("ix_payment_methods_company_code", table_name="payment_methods")
    op.drop_index("ix_payment_methods_company_id", table_name="payment_methods")
    op.drop_table("payment_methods")
