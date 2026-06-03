"""create stock operational foundation

Revision ID: 20260428_0013
Revises: 20260428_0012
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0013"
down_revision = "20260428_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_locations",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("establishment_id", sa.String(length=80), nullable=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("location_type", sa.String(length=40), nullable=False, server_default="main"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "code", name="uq_stock_locations_company_code"),
    )
    op.create_index("ix_stock_locations_company_id", "stock_locations", ["company_id"])
    op.create_index("ix_stock_locations_company_status", "stock_locations", ["company_id", "status"])
    op.create_index("ix_stock_locations_company_default", "stock_locations", ["company_id", "is_default"])
    op.create_index("ix_stock_locations_company_type", "stock_locations", ["company_id", "location_type"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", sa.String(length=80), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.String(length=80), sa.ForeignKey("stock_locations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(length=60), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.String(length=80), nullable=True),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sale_item_id", sa.String(length=80), sa.ForeignKey("sale_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="posted"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_stock_movements_company_id", "stock_movements", ["company_id"])
    op.create_index("ix_stock_movements_company_item", "stock_movements", ["company_id", "item_id"])
    op.create_index("ix_stock_movements_company_location", "stock_movements", ["company_id", "location_id"])
    op.create_index("ix_stock_movements_company_type", "stock_movements", ["company_id", "movement_type"])
    op.create_index("ix_stock_movements_company_status", "stock_movements", ["company_id", "status"])
    op.create_index("ix_stock_movements_company_date", "stock_movements", ["company_id", "movement_date"])
    op.create_index("ix_stock_movements_sale", "stock_movements", ["sale_id"])
    op.create_index("ix_stock_movements_sale_item", "stock_movements", ["sale_item_id"])
    op.create_index("ix_stock_movements_source", "stock_movements", ["source_type", "source_id"])

    op.create_table(
        "stock_balances",
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("item_id", sa.String(length=80), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("location_id", sa.String(length=80), sa.ForeignKey("stock_locations.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stock_balances_company_id", "stock_balances", ["company_id"])
    op.create_index("ix_stock_balances_company_item", "stock_balances", ["company_id", "item_id"])
    op.create_index("ix_stock_balances_company_location", "stock_balances", ["company_id", "location_id"])

    op.create_table(
        "sale_stock_links",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_item_id", sa.String(length=80), sa.ForeignKey("sale_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_movement_id", sa.String(length=80), sa.ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("link_type", sa.String(length=60), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sale_stock_links_company_id", "sale_stock_links", ["company_id"])
    op.create_index("ix_sale_stock_links_sale", "sale_stock_links", ["sale_id"])
    op.create_index("ix_sale_stock_links_sale_item", "sale_stock_links", ["sale_item_id"])
    op.create_index("ix_sale_stock_links_movement", "sale_stock_links", ["stock_movement_id"])
    op.create_index("ix_sale_stock_links_company_status", "sale_stock_links", ["company_id", "status"])

    op.alter_column("stock_locations", "location_type", server_default=None)
    op.alter_column("stock_locations", "is_default", server_default=None)
    op.alter_column("stock_locations", "status", server_default=None)
    op.alter_column("stock_movements", "status", server_default=None)
    op.alter_column("stock_balances", "quantity", server_default=None)
    op.alter_column("sale_stock_links", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sale_stock_links_company_status", table_name="sale_stock_links")
    op.drop_index("ix_sale_stock_links_movement", table_name="sale_stock_links")
    op.drop_index("ix_sale_stock_links_sale_item", table_name="sale_stock_links")
    op.drop_index("ix_sale_stock_links_sale", table_name="sale_stock_links")
    op.drop_index("ix_sale_stock_links_company_id", table_name="sale_stock_links")
    op.drop_table("sale_stock_links")

    op.drop_index("ix_stock_balances_company_location", table_name="stock_balances")
    op.drop_index("ix_stock_balances_company_item", table_name="stock_balances")
    op.drop_index("ix_stock_balances_company_id", table_name="stock_balances")
    op.drop_table("stock_balances")

    op.drop_index("ix_stock_movements_source", table_name="stock_movements")
    op.drop_index("ix_stock_movements_sale_item", table_name="stock_movements")
    op.drop_index("ix_stock_movements_sale", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_date", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_status", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_type", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_location", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_item", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_id", table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index("ix_stock_locations_company_type", table_name="stock_locations")
    op.drop_index("ix_stock_locations_company_default", table_name="stock_locations")
    op.drop_index("ix_stock_locations_company_status", table_name="stock_locations")
    op.drop_index("ix_stock_locations_company_id", table_name="stock_locations")
    op.drop_table("stock_locations")
