"""create catalog items table

Revision ID: 20260428_0003
Revises: 20260428_0002
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260428_0003"
down_revision: str | None = "20260428_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("company_id", sa.String(length=80), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(length=80), nullable=True),
        sa.Column("barcode", sa.String(length=80), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False),
        sa.Column("ncm", sa.String(length=8), nullable=True),
        sa.Column("nbs", sa.String(length=9), nullable=True),
        sa.Column("sale_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("standard_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("track_stock", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("stock_unit", sa.String(length=20), nullable=True),
        sa.Column("financial_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fiscal_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("inventory_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_catalog_items_company_id", "catalog_items", ["company_id"], unique=False)
    op.create_index("ix_catalog_items_company_status", "catalog_items", ["company_id", "status"], unique=False)
    op.create_index("ix_catalog_items_company_created", "catalog_items", ["company_id", "created_at"], unique=False)
    op.create_index("ix_catalog_items_company_updated", "catalog_items", ["company_id", "updated_at"], unique=False)
    op.create_index("ix_catalog_items_company_item_type", "catalog_items", ["company_id", "item_type"], unique=False)
    op.create_index("ix_catalog_items_company_sku", "catalog_items", ["company_id", "sku"], unique=False)
    op.create_index("ix_catalog_items_company_barcode", "catalog_items", ["company_id", "barcode"], unique=False)
    op.create_index("ix_catalog_items_company_name", "catalog_items", ["company_id", "name"], unique=False)
    op.create_index("ix_catalog_items_company_ncm", "catalog_items", ["company_id", "ncm"], unique=False)
    op.create_index("ix_catalog_items_company_nbs", "catalog_items", ["company_id", "nbs"], unique=False)
    op.create_index(
        "uq_catalog_items_company_sku_not_empty",
        "catalog_items",
        ["company_id", "sku"],
        unique=True,
        postgresql_where=sa.text("sku IS NOT NULL AND sku <> ''"),
    )
    op.create_index(
        "uq_catalog_items_company_barcode_not_empty",
        "catalog_items",
        ["company_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL AND barcode <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_catalog_items_company_barcode_not_empty", table_name="catalog_items")
    op.drop_index("uq_catalog_items_company_sku_not_empty", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_nbs", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_ncm", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_name", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_barcode", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_sku", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_item_type", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_updated", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_created", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_status", table_name="catalog_items")
    op.drop_index("ix_catalog_items_company_id", table_name="catalog_items")
    op.drop_table("catalog_items")
