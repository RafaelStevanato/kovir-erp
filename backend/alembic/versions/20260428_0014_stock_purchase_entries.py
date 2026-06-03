"""create stock purchase entry foundation

Revision ID: 20260428_0014
Revises: 20260428_0013
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0014"
down_revision = "20260428_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_purchase_entries",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_id", sa.String(length=80), sa.ForeignKey("stock_locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_type", sa.String(length=60), nullable=False, server_default="purchase_invoice"),
        sa.Column("document_number", sa.String(length=80), nullable=True),
        sa.Column("document_series", sa.String(length=40), nullable=True),
        sa.Column("access_key", sa.String(length=80), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("entry_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="posted"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("supplier_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("document_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_stock_purchase_entries_company_id", "stock_purchase_entries", ["company_id"])
    op.create_index("ix_stock_purchase_entries_company_status", "stock_purchase_entries", ["company_id", "status"])
    op.create_index("ix_stock_purchase_entries_company_supplier", "stock_purchase_entries", ["company_id", "supplier_participant_id"])
    op.create_index("ix_stock_purchase_entries_company_location", "stock_purchase_entries", ["company_id", "location_id"])
    op.create_index("ix_stock_purchase_entries_company_entry_date", "stock_purchase_entries", ["company_id", "entry_date"])
    op.create_index("ix_stock_purchase_entries_document", "stock_purchase_entries", ["company_id", "document_number", "document_series"])
    op.create_index("ix_stock_purchase_entries_access_key", "stock_purchase_entries", ["company_id", "access_key"])

    op.create_table(
        "stock_purchase_entry_items",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_entry_id", sa.String(length=80), sa.ForeignKey("stock_purchase_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(length=80), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stock_movement_id", sa.String(length=80), sa.ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("item_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stock_purchase_entry_items_company_id", "stock_purchase_entry_items", ["company_id"])
    op.create_index("ix_stock_purchase_entry_items_entry", "stock_purchase_entry_items", ["purchase_entry_id"])
    op.create_index("ix_stock_purchase_entry_items_item", "stock_purchase_entry_items", ["company_id", "item_id"])
    op.create_index("ix_stock_purchase_entry_items_movement", "stock_purchase_entry_items", ["stock_movement_id"])

    op.alter_column("stock_purchase_entries", "document_type", server_default=None)
    op.alter_column("stock_purchase_entries", "status", server_default=None)
    op.alter_column("stock_purchase_entries", "total_items", server_default=None)
    op.alter_column("stock_purchase_entries", "total_quantity", server_default=None)
    op.alter_column("stock_purchase_entries", "total_amount", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_stock_purchase_entry_items_movement", table_name="stock_purchase_entry_items")
    op.drop_index("ix_stock_purchase_entry_items_item", table_name="stock_purchase_entry_items")
    op.drop_index("ix_stock_purchase_entry_items_entry", table_name="stock_purchase_entry_items")
    op.drop_index("ix_stock_purchase_entry_items_company_id", table_name="stock_purchase_entry_items")
    op.drop_table("stock_purchase_entry_items")

    op.drop_index("ix_stock_purchase_entries_access_key", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_document", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_company_entry_date", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_company_location", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_company_supplier", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_company_status", table_name="stock_purchase_entries")
    op.drop_index("ix_stock_purchase_entries_company_id", table_name="stock_purchase_entries")
    op.drop_table("stock_purchase_entries")
