"""sales fiscal operation foundation

Revision ID: 20260428_0008
Revises: 20260428_0007
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0008"
down_revision = "20260428_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_natures",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sale_type", sa.String(length=40), nullable=False, server_default="both"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requires_reason", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("affects_revenue", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("affects_accounts_receivable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("affects_stock", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_fiscal_document", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("default_receivable_behavior", sa.String(length=40), nullable=False, server_default="full"),
        sa.Column("default_invoice_behavior", sa.String(length=40), nullable=False, server_default="full"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_operation_natures_company_id", "operation_natures", ["company_id"])
    op.create_index("ix_operation_natures_company_code", "operation_natures", ["company_id", "code"])
    op.create_index("ix_operation_natures_company_sale_type", "operation_natures", ["company_id", "sale_type"])
    op.create_index("ix_operation_natures_company_status", "operation_natures", ["company_id", "status"])
    op.create_index(
        "uq_operation_natures_company_code_type_active",
        "operation_natures",
        ["company_id", "code", "sale_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "catalog_item_fiscal_rules",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("catalog_item_id", sa.String(length=80), sa.ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fiscal_classification_id", sa.String(length=80), sa.ForeignKey("fiscal_classifications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation_nature_id", sa.String(length=80), sa.ForeignKey("operation_natures.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_type", sa.String(length=40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_catalog_item_fiscal_rules_company_id", "catalog_item_fiscal_rules", ["company_id"])
    op.create_index("ix_catalog_item_fiscal_rules_company_item", "catalog_item_fiscal_rules", ["company_id", "catalog_item_id"])
    op.create_index("ix_catalog_item_fiscal_rules_company_classification", "catalog_item_fiscal_rules", ["company_id", "fiscal_classification_id"])
    op.create_index("ix_catalog_item_fiscal_rules_company_nature", "catalog_item_fiscal_rules", ["company_id", "operation_nature_id"])
    op.create_index("ix_catalog_item_fiscal_rules_company_type", "catalog_item_fiscal_rules", ["company_id", "sale_type"])
    op.create_index("ix_catalog_item_fiscal_rules_company_status", "catalog_item_fiscal_rules", ["company_id", "status"])

    op.add_column("sales", sa.Column("operation_nature_id", sa.String(length=80), nullable=True))
    op.add_column("sales", sa.Column("fiscal_status", sa.String(length=40), nullable=False, server_default="pending_classification"))
    op.add_column("sales", sa.Column("receivable_total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("sales", sa.Column("invoice_total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("sales", sa.Column("operation_nature_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key("fk_sales_operation_nature_id", "sales", "operation_natures", ["operation_nature_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_sales_company_operation_nature_id", "sales", ["company_id", "operation_nature_id"])
    op.create_index("ix_sales_company_fiscal_status", "sales", ["company_id", "fiscal_status"])

    op.execute("UPDATE sales SET receivable_total_amount = total_amount WHERE receivable_total_amount = 0")
    op.execute("UPDATE sales SET invoice_total_amount = total_amount WHERE invoice_total_amount = 0")
    op.execute("UPDATE sales SET operation_nature_snapshot_json = jsonb_build_object('code', operation_nature, 'name', operation_nature, 'source', 'legacy_text') WHERE operation_nature_snapshot_json IS NULL")

    op.add_column("sale_items", sa.Column("operation_nature_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("sale_items", "operation_nature_snapshot_json")

    op.drop_index("ix_sales_company_fiscal_status", table_name="sales")
    op.drop_index("ix_sales_company_operation_nature_id", table_name="sales")
    op.drop_constraint("fk_sales_operation_nature_id", "sales", type_="foreignkey")
    op.drop_column("sales", "operation_nature_snapshot_json")
    op.drop_column("sales", "invoice_total_amount")
    op.drop_column("sales", "receivable_total_amount")
    op.drop_column("sales", "fiscal_status")
    op.drop_column("sales", "operation_nature_id")

    op.drop_index("ix_catalog_item_fiscal_rules_company_status", table_name="catalog_item_fiscal_rules")
    op.drop_index("ix_catalog_item_fiscal_rules_company_type", table_name="catalog_item_fiscal_rules")
    op.drop_index("ix_catalog_item_fiscal_rules_company_nature", table_name="catalog_item_fiscal_rules")
    op.drop_index("ix_catalog_item_fiscal_rules_company_classification", table_name="catalog_item_fiscal_rules")
    op.drop_index("ix_catalog_item_fiscal_rules_company_item", table_name="catalog_item_fiscal_rules")
    op.drop_index("ix_catalog_item_fiscal_rules_company_id", table_name="catalog_item_fiscal_rules")
    op.drop_table("catalog_item_fiscal_rules")

    op.drop_index("uq_operation_natures_company_code_type_active", table_name="operation_natures")
    op.drop_index("ix_operation_natures_company_status", table_name="operation_natures")
    op.drop_index("ix_operation_natures_company_sale_type", table_name="operation_natures")
    op.drop_index("ix_operation_natures_company_code", table_name="operation_natures")
    op.drop_index("ix_operation_natures_company_id", table_name="operation_natures")
    op.drop_table("operation_natures")
