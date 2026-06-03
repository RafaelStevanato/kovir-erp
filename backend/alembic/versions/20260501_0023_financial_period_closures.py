"""create financial period closures table

Revision ID: 20260501_0023
Revises: 20260501_0022
Create Date: 2026-05-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260501_0023"
down_revision = "20260501_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_period_closures",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_financial_period_closures_date_range"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_period_closures_company_id",
        "financial_period_closures",
        ["company_id"],
    )
    op.create_index(
        "ix_financial_period_closures_company_status",
        "financial_period_closures",
        ["company_id", "status"],
    )
    op.create_index(
        "ix_financial_period_closures_company_period",
        "financial_period_closures",
        ["company_id", "start_date", "end_date"],
    )
    op.alter_column("financial_period_closures", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_financial_period_closures_company_period", table_name="financial_period_closures")
    op.drop_index("ix_financial_period_closures_company_status", table_name="financial_period_closures")
    op.drop_index("ix_financial_period_closures_company_id", table_name="financial_period_closures")
    op.drop_table("financial_period_closures")
