"""create sales tables

Revision ID: 20260428_0005
Revises: 20260428_0004
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260428_0005"
down_revision: str | None = "20260428_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("establishment_id", sa.String(length=80), nullable=True),
        sa.Column("participant_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("operation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("competency_date", sa.Date(), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("freight_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("participant_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_company_id", "sales", ["company_id"])
    op.create_index("ix_sales_company_status", "sales", ["company_id", "status"])
    op.create_index("ix_sales_company_participant", "sales", ["company_id", "participant_id"])
    op.create_index("ix_sales_company_operation_date", "sales", ["company_id", "operation_date"])
    op.create_index("ix_sales_company_issue_date", "sales", ["company_id", "issue_date"])
    op.create_index("ix_sales_company_competency_date", "sales", ["company_id", "competency_date"])
    op.create_index("ix_sales_company_created", "sales", ["company_id", "created_at"])
    op.create_index("ix_sales_company_updated", "sales", ["company_id", "updated_at"])

    op.create_table(
        "sale_items",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("sale_id", sa.String(length=80), nullable=False),
        sa.Column("item_id", sa.String(length=80), nullable=False),
        sa.Column("fiscal_classification_id", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("freight_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("item_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fiscal_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["catalog_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fiscal_classification_id"], ["fiscal_classifications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sale_items_company_id", "sale_items", ["company_id"])
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("ix_sale_items_company_item", "sale_items", ["company_id", "item_id"])
    op.create_index(
        "ix_sale_items_company_fiscal_classification",
        "sale_items",
        ["company_id", "fiscal_classification_id"],
    )
    op.create_index("ix_sale_items_company_created", "sale_items", ["company_id", "created_at"])

    op.create_table(
        "sale_status_history",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("sale_id", sa.String(length=80), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sale_status_history_company_id", "sale_status_history", ["company_id"])
    op.create_index("ix_sale_status_history_sale_id", "sale_status_history", ["sale_id"])
    op.create_index("ix_sale_status_history_company_sale", "sale_status_history", ["company_id", "sale_id"])
    op.create_index(
        "ix_sale_status_history_company_occurred",
        "sale_status_history",
        ["company_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sale_status_history_company_occurred", table_name="sale_status_history")
    op.drop_index("ix_sale_status_history_company_sale", table_name="sale_status_history")
    op.drop_index("ix_sale_status_history_sale_id", table_name="sale_status_history")
    op.drop_index("ix_sale_status_history_company_id", table_name="sale_status_history")
    op.drop_table("sale_status_history")

    op.drop_index("ix_sale_items_company_created", table_name="sale_items")
    op.drop_index("ix_sale_items_company_fiscal_classification", table_name="sale_items")
    op.drop_index("ix_sale_items_company_item", table_name="sale_items")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_index("ix_sale_items_company_id", table_name="sale_items")
    op.drop_table("sale_items")

    op.drop_index("ix_sales_company_updated", table_name="sales")
    op.drop_index("ix_sales_company_created", table_name="sales")
    op.drop_index("ix_sales_company_competency_date", table_name="sales")
    op.drop_index("ix_sales_company_issue_date", table_name="sales")
    op.drop_index("ix_sales_company_operation_date", table_name="sales")
    op.drop_index("ix_sales_company_participant", table_name="sales")
    op.drop_index("ix_sales_company_status", table_name="sales")
    op.drop_index("ix_sales_company_id", table_name="sales")
    op.drop_table("sales")
