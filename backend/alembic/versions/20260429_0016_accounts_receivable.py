"""accounts receivable foundation

Revision ID: 20260429_0016
Revises: 20260429_0015
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260429_0016"
down_revision = "20260429_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_titles",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False, server_default="receivable"),
        sa.Column("title_type", sa.String(length=40), nullable=False, server_default="sale"),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("source_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("sale_payment_plan_id", sa.String(length=80), sa.ForeignKey("sale_payment_plans.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("participant_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payment_method_id", sa.String(length=80), sa.ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("payment_method_code", sa.String(length=80), nullable=True),
        sa.Column("payment_method_name", sa.String(length=120), nullable=True),
        sa.Column("financial_category_id", sa.String(length=80), sa.ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("cost_center_id", sa.String(length=80), sa.ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("expected_financial_account_id", sa.String(length=80), sa.ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("document_reference", sa.String(length=120), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("installment_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("competency_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("expected_payment_date", sa.Date(), nullable=True),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("interest_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("penalty_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("open_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("collection_status", sa.String(length=40), nullable=False, server_default="not_started"),
        sa.Column("fiscal_status", sa.String(length=40), nullable=False, server_default="pending_document"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "source_type", "source_id", name="uq_financial_titles_company_source"),
    )
    op.create_index("ix_financial_titles_company_id", "financial_titles", ["company_id"])
    op.create_index("ix_financial_titles_company_direction", "financial_titles", ["company_id", "direction"])
    op.create_index("ix_financial_titles_company_status", "financial_titles", ["company_id", "status"])
    op.create_index("ix_financial_titles_company_collection", "financial_titles", ["company_id", "collection_status"])
    op.create_index("ix_financial_titles_company_fiscal", "financial_titles", ["company_id", "fiscal_status"])
    op.create_index("ix_financial_titles_company_participant", "financial_titles", ["company_id", "participant_id"])
    op.create_index("ix_financial_titles_company_due", "financial_titles", ["company_id", "due_date"])
    op.create_index("ix_financial_titles_company_source", "financial_titles", ["company_id", "source_type", "source_id"])
    op.create_index("ix_financial_titles_company_sale", "financial_titles", ["company_id", "sale_id"])
    op.create_index("ix_financial_titles_company_category", "financial_titles", ["company_id", "financial_category_id"])
    op.create_index("ix_financial_titles_company_account", "financial_titles", ["company_id", "expected_financial_account_id"])

    op.create_table(
        "sale_financial_links",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_payment_plan_id", sa.String(length=80), sa.ForeignKey("sale_payment_plans.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("financial_title_id", sa.String(length=80), sa.ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("link_type", sa.String(length=40), nullable=False, server_default="generated_from_sale"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "sale_payment_plan_id", "financial_title_id", name="uq_sale_financial_links_plan_title"),
    )
    op.create_index("ix_sale_financial_links_company_id", "sale_financial_links", ["company_id"])
    op.create_index("ix_sale_financial_links_company_sale", "sale_financial_links", ["company_id", "sale_id"])
    op.create_index("ix_sale_financial_links_company_plan", "sale_financial_links", ["company_id", "sale_payment_plan_id"])
    op.create_index("ix_sale_financial_links_company_title", "sale_financial_links", ["company_id", "financial_title_id"])
    op.create_index("ix_sale_financial_links_company_status", "sale_financial_links", ["company_id", "status"])

    op.create_table(
        "financial_title_history",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("financial_title_id", sa.String(length=80), sa.ForeignKey("financial_titles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("previous_collection_status", sa.String(length=40), nullable=True),
        sa.Column("new_collection_status", sa.String(length=40), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_financial_title_history_company_id", "financial_title_history", ["company_id"])
    op.create_index("ix_financial_title_history_title", "financial_title_history", ["financial_title_id"])
    op.create_index("ix_financial_title_history_company_title", "financial_title_history", ["company_id", "financial_title_id"])
    op.create_index("ix_financial_title_history_company_occurred", "financial_title_history", ["company_id", "occurred_at"])

    op.alter_column("financial_titles", "direction", server_default=None)
    op.alter_column("financial_titles", "title_type", server_default=None)
    op.alter_column("financial_titles", "discount_amount", server_default=None)
    op.alter_column("financial_titles", "interest_amount", server_default=None)
    op.alter_column("financial_titles", "penalty_amount", server_default=None)
    op.alter_column("financial_titles", "fee_amount", server_default=None)
    op.alter_column("financial_titles", "paid_amount", server_default=None)
    op.alter_column("financial_titles", "status", server_default=None)
    op.alter_column("financial_titles", "collection_status", server_default=None)
    op.alter_column("financial_titles", "fiscal_status", server_default=None)
    op.alter_column("sale_financial_links", "link_type", server_default=None)
    op.alter_column("sale_financial_links", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_financial_title_history_company_occurred", table_name="financial_title_history")
    op.drop_index("ix_financial_title_history_company_title", table_name="financial_title_history")
    op.drop_index("ix_financial_title_history_title", table_name="financial_title_history")
    op.drop_index("ix_financial_title_history_company_id", table_name="financial_title_history")
    op.drop_table("financial_title_history")

    op.drop_index("ix_sale_financial_links_company_status", table_name="sale_financial_links")
    op.drop_index("ix_sale_financial_links_company_title", table_name="sale_financial_links")
    op.drop_index("ix_sale_financial_links_company_plan", table_name="sale_financial_links")
    op.drop_index("ix_sale_financial_links_company_sale", table_name="sale_financial_links")
    op.drop_index("ix_sale_financial_links_company_id", table_name="sale_financial_links")
    op.drop_table("sale_financial_links")

    op.drop_index("ix_financial_titles_company_account", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_category", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_sale", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_source", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_due", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_participant", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_fiscal", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_collection", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_status", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_direction", table_name="financial_titles")
    op.drop_index("ix_financial_titles_company_id", table_name="financial_titles")
    op.drop_table("financial_titles")
