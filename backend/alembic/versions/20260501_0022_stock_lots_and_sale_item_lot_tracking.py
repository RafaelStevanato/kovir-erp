"""add stock lots and lot tracking in sales/stock movements

Revision ID: 20260501_0022
Revises: 20260430_0021
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260501_0022"
down_revision = "20260430_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_lots",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("item_id", sa.String(length=80), nullable=False),
        sa.Column("location_id", sa.String(length=80), nullable=False),
        sa.Column("lot_code", sa.String(length=80), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["catalog_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["stock_locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "item_id",
            "location_id",
            "lot_code",
            "expiration_date",
            name="uq_stock_lots_company_item_location_lot_expiration",
        ),
    )
    op.create_index("ix_stock_lots_company_id", "stock_lots", ["company_id"])
    op.create_index("ix_stock_lots_company_item", "stock_lots", ["company_id", "item_id"])
    op.create_index("ix_stock_lots_company_location", "stock_lots", ["company_id", "location_id"])
    op.create_index("ix_stock_lots_company_expiration", "stock_lots", ["company_id", "expiration_date"])
    op.create_index("ix_stock_lots_company_status", "stock_lots", ["company_id", "status"])

    op.add_column("stock_movements", sa.Column("lot_id", sa.String(length=80), nullable=True))
    op.add_column("stock_movements", sa.Column("lot_code", sa.String(length=80), nullable=True))
    op.add_column("stock_movements", sa.Column("expiration_date", sa.Date(), nullable=True))
    op.create_foreign_key("fk_stock_movements_lot_id", "stock_movements", "stock_lots", ["lot_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_stock_movements_company_lot", "stock_movements", ["company_id", "lot_id"])
    op.create_index(
        "ix_stock_movements_company_lot_code_expiration",
        "stock_movements",
        ["company_id", "lot_code", "expiration_date"],
    )

    op.add_column("stock_purchase_entry_items", sa.Column("lot_id", sa.String(length=80), nullable=True))
    op.add_column("stock_purchase_entry_items", sa.Column("lot_code", sa.String(length=80), nullable=True))
    op.add_column("stock_purchase_entry_items", sa.Column("expiration_date", sa.Date(), nullable=True))
    op.create_foreign_key(
        "fk_stock_purchase_entry_items_lot_id",
        "stock_purchase_entry_items",
        "stock_lots",
        ["lot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_stock_purchase_entry_items_lot", "stock_purchase_entry_items", ["company_id", "lot_id"])

    op.add_column("sale_items", sa.Column("stock_lot_id", sa.String(length=80), nullable=True))
    op.add_column("sale_items", sa.Column("stock_lot_code", sa.String(length=80), nullable=True))
    op.add_column("sale_items", sa.Column("stock_lot_expiration_date", sa.Date(), nullable=True))
    op.create_foreign_key("fk_sale_items_stock_lot_id", "sale_items", "stock_lots", ["stock_lot_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_sale_items_company_lot", "sale_items", ["company_id", "stock_lot_id"])

    op.alter_column("stock_lots", "quantity", server_default=None)
    op.alter_column("stock_lots", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_sale_items_company_lot", table_name="sale_items")
    op.drop_constraint("fk_sale_items_stock_lot_id", "sale_items", type_="foreignkey")
    op.drop_column("sale_items", "stock_lot_expiration_date")
    op.drop_column("sale_items", "stock_lot_code")
    op.drop_column("sale_items", "stock_lot_id")

    op.drop_index("ix_stock_purchase_entry_items_lot", table_name="stock_purchase_entry_items")
    op.drop_constraint("fk_stock_purchase_entry_items_lot_id", "stock_purchase_entry_items", type_="foreignkey")
    op.drop_column("stock_purchase_entry_items", "expiration_date")
    op.drop_column("stock_purchase_entry_items", "lot_code")
    op.drop_column("stock_purchase_entry_items", "lot_id")

    op.drop_index("ix_stock_movements_company_lot_code_expiration", table_name="stock_movements")
    op.drop_index("ix_stock_movements_company_lot", table_name="stock_movements")
    op.drop_constraint("fk_stock_movements_lot_id", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "expiration_date")
    op.drop_column("stock_movements", "lot_code")
    op.drop_column("stock_movements", "lot_id")

    op.drop_index("ix_stock_lots_company_status", table_name="stock_lots")
    op.drop_index("ix_stock_lots_company_expiration", table_name="stock_lots")
    op.drop_index("ix_stock_lots_company_location", table_name="stock_lots")
    op.drop_index("ix_stock_lots_company_item", table_name="stock_lots")
    op.drop_index("ix_stock_lots_company_id", table_name="stock_lots")
    op.drop_table("stock_lots")
