"""add sale operation nature metadata

Revision ID: 20260428_0007
Revises: 20260428_0006
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0007"
down_revision = "20260428_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column(
            "operation_nature",
            sa.String(length=80),
            nullable=False,
            server_default="normal_sale",
        ),
    )
    op.add_column(
        "sales",
        sa.Column("operation_nature_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_sales_company_operation_nature",
        "sales",
        ["company_id", "operation_nature"],
    )
    op.alter_column("sales", "operation_nature", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sales_company_operation_nature", table_name="sales")
    op.drop_column("sales", "operation_nature_reason")
    op.drop_column("sales", "operation_nature")
