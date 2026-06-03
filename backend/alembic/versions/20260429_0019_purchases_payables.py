"""purchases expenses and accounts payable

Revision ID: 20260429_0019
Revises: 20260429_0018
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260429_0019"
down_revision = "20260429_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchases",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("establishment_id", sa.String(length=80), nullable=True),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("purchase_type", sa.String(length=40), nullable=False, server_default="expense"),
        sa.Column("origin", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("operation_nature_id", sa.String(length=80), sa.ForeignKey("operation_natures.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("fiscal_status", sa.String(length=40), nullable=False, server_default="pending_document"),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("operation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("competency_date", sa.Date(), nullable=True),
        sa.Column("subtotal_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("freight_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("payable_total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("invoice_total_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("financial_category_id", sa.String(length=80), sa.ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cost_center_id", sa.String(length=80), sa.ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("expected_financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("document_type", sa.String(length=60), nullable=True),
        sa.Column("document_number", sa.String(length=120), nullable=True),
        sa.Column("document_series", sa.String(length=40), nullable=True),
        sa.Column("access_key", sa.String(length=80), nullable=True),
        sa.Column("participant_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_purchases_company_id", "purchases", ["company_id"])
    op.create_index("ix_purchases_company_status", "purchases", ["company_id", "status"])
    op.create_index("ix_purchases_company_type", "purchases", ["company_id", "purchase_type"])
    op.create_index("ix_purchases_company_participant", "purchases", ["company_id", "participant_id"])
    op.create_index("ix_purchases_company_operation_date", "purchases", ["company_id", "operation_date"])
    op.create_index("ix_purchases_company_competency", "purchases", ["company_id", "competency_date"])
    op.create_index("ix_purchases_company_document", "purchases", ["company_id", "document_number"])
    op.create_index("ix_purchases_company_category", "purchases", ["company_id", "financial_category_id"])

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_id", sa.String(length=80), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(length=80), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("fiscal_classification_id", sa.String(length=80), sa.ForeignKey("fiscal_classifications.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("freight_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("item_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fiscal_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_items_company_id", "purchase_items", ["company_id"])
    op.create_index("ix_purchase_items_purchase", "purchase_items", ["purchase_id"])
    op.create_index("ix_purchase_items_company_item", "purchase_items", ["company_id", "item_id"])
    op.create_index("ix_purchase_items_company_fiscal", "purchase_items", ["company_id", "fiscal_classification_id"])

    op.create_table(
        "purchase_financial_links",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_id", sa.String(length=80), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("financial_title_id", sa.String(length=80), sa.ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("installment_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("link_type", sa.String(length=40), nullable=False, server_default="generated_from_purchase"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "purchase_id", "installment_number", name="uq_purchase_financial_links_installment"),
        sa.UniqueConstraint("company_id", "financial_title_id", name="uq_purchase_financial_links_title"),
    )
    op.create_index("ix_purchase_financial_links_company_id", "purchase_financial_links", ["company_id"])
    op.create_index("ix_purchase_financial_links_company_purchase", "purchase_financial_links", ["company_id", "purchase_id"])
    op.create_index("ix_purchase_financial_links_company_title", "purchase_financial_links", ["company_id", "financial_title_id"])
    op.create_index("ix_purchase_financial_links_company_status", "purchase_financial_links", ["company_id", "status"])

    op.create_table(
        "purchase_status_history",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_id", sa.String(length=80), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_purchase_status_history_company_id", "purchase_status_history", ["company_id"])
    op.create_index("ix_purchase_status_history_purchase", "purchase_status_history", ["purchase_id"])
    op.create_index("ix_purchase_status_history_company_purchase", "purchase_status_history", ["company_id", "purchase_id"])
    op.create_index("ix_purchase_status_history_company_occurred", "purchase_status_history", ["company_id", "occurred_at"])

    for table, columns in {
        "purchases": ["status", "purchase_type", "origin", "fiscal_status", "subtotal_amount", "discount_amount", "freight_amount", "tax_amount", "total_amount", "payable_total_amount"],
        "purchase_items": ["discount_amount", "freight_amount", "tax_amount"],
        "purchase_financial_links": ["installment_number", "installment_total", "link_type", "status"],
    }.items():
        for column in columns:
            op.alter_column(table, column, server_default=None)


def downgrade() -> None:
    op.drop_index("ix_purchase_status_history_company_occurred", table_name="purchase_status_history")
    op.drop_index("ix_purchase_status_history_company_purchase", table_name="purchase_status_history")
    op.drop_index("ix_purchase_status_history_purchase", table_name="purchase_status_history")
    op.drop_index("ix_purchase_status_history_company_id", table_name="purchase_status_history")
    op.drop_table("purchase_status_history")

    op.drop_index("ix_purchase_financial_links_company_status", table_name="purchase_financial_links")
    op.drop_index("ix_purchase_financial_links_company_title", table_name="purchase_financial_links")
    op.drop_index("ix_purchase_financial_links_company_purchase", table_name="purchase_financial_links")
    op.drop_index("ix_purchase_financial_links_company_id", table_name="purchase_financial_links")
    op.drop_table("purchase_financial_links")

    op.drop_index("ix_purchase_items_company_fiscal", table_name="purchase_items")
    op.drop_index("ix_purchase_items_company_item", table_name="purchase_items")
    op.drop_index("ix_purchase_items_purchase", table_name="purchase_items")
    op.drop_index("ix_purchase_items_company_id", table_name="purchase_items")
    op.drop_table("purchase_items")

    op.drop_index("ix_purchases_company_category", table_name="purchases")
    op.drop_index("ix_purchases_company_document", table_name="purchases")
    op.drop_index("ix_purchases_company_competency", table_name="purchases")
    op.drop_index("ix_purchases_company_operation_date", table_name="purchases")
    op.drop_index("ix_purchases_company_participant", table_name="purchases")
    op.drop_index("ix_purchases_company_type", table_name="purchases")
    op.drop_index("ix_purchases_company_status", table_name="purchases")
    op.drop_index("ix_purchases_company_id", table_name="purchases")
    op.drop_table("purchases")
