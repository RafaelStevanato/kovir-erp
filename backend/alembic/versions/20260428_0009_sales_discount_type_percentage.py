"""add sale discount type and percentage

Revision ID: 20260428_0009
Revises: 20260428_0008
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0009"
down_revision = "20260428_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column("discount_type", sa.String(length=40), nullable=False, server_default="amount"),
    )
    op.add_column(
        "sales",
        sa.Column("discount_percentage", sa.Numeric(18, 6), nullable=True),
    )
    op.create_index("ix_sales_company_discount_type", "sales", ["company_id", "discount_type"])
    op.alter_column("sales", "discount_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sales_company_discount_type", table_name="sales")
    op.drop_column("sales", "discount_percentage")
    op.drop_column("sales", "discount_type")
