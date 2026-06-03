"""add sale type and discount metadata

Revision ID: 20260428_0006
Revises: 20260428_0005
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260428_0006"
down_revision: str | None = "20260428_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column("sale_type", sa.String(length=40), nullable=False, server_default="product"),
    )
    op.add_column("sales", sa.Column("discount_category", sa.String(length=80), nullable=True))
    op.add_column("sales", sa.Column("discount_reason", sa.Text(), nullable=True))
    op.create_index("ix_sales_company_type", "sales", ["company_id", "sale_type"])


def downgrade() -> None:
    op.drop_index("ix_sales_company_type", table_name="sales")
    op.drop_column("sales", "discount_reason")
    op.drop_column("sales", "discount_category")
    op.drop_column("sales", "sale_type")
