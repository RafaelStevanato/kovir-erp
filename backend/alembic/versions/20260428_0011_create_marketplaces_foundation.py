"""create marketplaces integration foundation

Revision ID: 20260428_0011
Revises: 20260428_0010
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0011"
down_revision = "20260428_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_accounts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_code", sa.String(length=80), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False, server_default="sandbox"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("connection_status", sa.String(length=40), nullable=False, server_default="not_connected"),
        sa.Column("external_account_id", sa.String(length=160), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "provider_code", "display_name", name="uq_marketplace_accounts_company_provider_display"),
    )
    op.create_index("ix_marketplace_accounts_company_id", "marketplace_accounts", ["company_id"])
    op.create_index("ix_marketplace_accounts_company_provider", "marketplace_accounts", ["company_id", "provider_code"])
    op.create_index("ix_marketplace_accounts_company_type", "marketplace_accounts", ["company_id", "provider_type"])
    op.create_index("ix_marketplace_accounts_company_status", "marketplace_accounts", ["company_id", "status"])
    op.create_index("ix_marketplace_accounts_company_connection", "marketplace_accounts", ["company_id", "connection_status"])

    op.create_table(
        "marketplace_sync_runs",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("marketplace_account_id", sa.String(length=80), sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sync_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_cursor", sa.String(length=255), nullable=True),
        sa.Column("records_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_marketplace_sync_runs_company_id", "marketplace_sync_runs", ["company_id"])
    op.create_index("ix_marketplace_sync_runs_account", "marketplace_sync_runs", ["marketplace_account_id"])
    op.create_index("ix_marketplace_sync_runs_company_account", "marketplace_sync_runs", ["company_id", "marketplace_account_id"])
    op.create_index("ix_marketplace_sync_runs_company_type", "marketplace_sync_runs", ["company_id", "sync_type"])
    op.create_index("ix_marketplace_sync_runs_company_status", "marketplace_sync_runs", ["company_id", "status"])
    op.create_index("ix_marketplace_sync_runs_company_started", "marketplace_sync_runs", ["company_id", "started_at"])

    op.create_table(
        "marketplace_external_orders",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("marketplace_account_id", sa.String(length=80), sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_code", sa.String(length=80), nullable=False),
        sa.Column("external_order_id", sa.String(length=160), nullable=False),
        sa.Column("external_status", sa.String(length=80), nullable=True),
        sa.Column("linked_sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("buyer_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("amounts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="imported"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "provider_code", "external_order_id", name="uq_marketplace_orders_company_provider_external"),
    )
    op.create_index("ix_marketplace_orders_company_id", "marketplace_external_orders", ["company_id"])
    op.create_index("ix_marketplace_orders_account", "marketplace_external_orders", ["marketplace_account_id"])
    op.create_index("ix_marketplace_orders_company_account", "marketplace_external_orders", ["company_id", "marketplace_account_id"])
    op.create_index("ix_marketplace_orders_company_provider", "marketplace_external_orders", ["company_id", "provider_code"])
    op.create_index("ix_marketplace_orders_company_status", "marketplace_external_orders", ["company_id", "status"])
    op.create_index("ix_marketplace_orders_linked_sale", "marketplace_external_orders", ["linked_sale_id"])

    op.create_table(
        "marketplace_payment_events",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("marketplace_account_id", sa.String(length=80), sa.ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_code", sa.String(length=80), nullable=False),
        sa.Column("external_payment_id", sa.String(length=160), nullable=False),
        sa.Column("external_order_id", sa.String(length=160), nullable=True),
        sa.Column("linked_sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_sale_payment_plan_id", sa.String(length=80), sa.ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_status", sa.String(length=80), nullable=True),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("release_status", sa.String(length=80), nullable=True),
        sa.Column("expected_release_date", sa.Date(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "provider_code", "external_payment_id", name="uq_marketplace_payments_company_provider_external"),
    )
    op.create_index("ix_marketplace_payments_company_id", "marketplace_payment_events", ["company_id"])
    op.create_index("ix_marketplace_payments_account", "marketplace_payment_events", ["marketplace_account_id"])
    op.create_index("ix_marketplace_payments_company_account", "marketplace_payment_events", ["company_id", "marketplace_account_id"])
    op.create_index("ix_marketplace_payments_company_provider", "marketplace_payment_events", ["company_id", "provider_code"])
    op.create_index("ix_marketplace_payments_status", "marketplace_payment_events", ["company_id", "payment_status"])
    op.create_index("ix_marketplace_payments_linked_sale", "marketplace_payment_events", ["linked_sale_id"])
    op.create_index("ix_marketplace_payments_linked_payment_plan", "marketplace_payment_events", ["linked_sale_payment_plan_id"])

    op.alter_column("marketplace_accounts", "environment", server_default=None)
    op.alter_column("marketplace_accounts", "status", server_default=None)
    op.alter_column("marketplace_accounts", "connection_status", server_default=None)
    op.alter_column("marketplace_sync_runs", "records_found", server_default=None)
    op.alter_column("marketplace_sync_runs", "records_created", server_default=None)
    op.alter_column("marketplace_sync_runs", "records_updated", server_default=None)
    op.alter_column("marketplace_sync_runs", "records_failed", server_default=None)
    op.alter_column("marketplace_external_orders", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_marketplace_payments_linked_payment_plan", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_linked_sale", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_status", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_company_provider", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_company_account", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_account", table_name="marketplace_payment_events")
    op.drop_index("ix_marketplace_payments_company_id", table_name="marketplace_payment_events")
    op.drop_table("marketplace_payment_events")

    op.drop_index("ix_marketplace_orders_linked_sale", table_name="marketplace_external_orders")
    op.drop_index("ix_marketplace_orders_company_status", table_name="marketplace_external_orders")
    op.drop_index("ix_marketplace_orders_company_provider", table_name="marketplace_external_orders")
    op.drop_index("ix_marketplace_orders_company_account", table_name="marketplace_external_orders")
    op.drop_index("ix_marketplace_orders_account", table_name="marketplace_external_orders")
    op.drop_index("ix_marketplace_orders_company_id", table_name="marketplace_external_orders")
    op.drop_table("marketplace_external_orders")

    op.drop_index("ix_marketplace_sync_runs_company_started", table_name="marketplace_sync_runs")
    op.drop_index("ix_marketplace_sync_runs_company_status", table_name="marketplace_sync_runs")
    op.drop_index("ix_marketplace_sync_runs_company_type", table_name="marketplace_sync_runs")
    op.drop_index("ix_marketplace_sync_runs_company_account", table_name="marketplace_sync_runs")
    op.drop_index("ix_marketplace_sync_runs_account", table_name="marketplace_sync_runs")
    op.drop_index("ix_marketplace_sync_runs_company_id", table_name="marketplace_sync_runs")
    op.drop_table("marketplace_sync_runs")

    op.drop_index("ix_marketplace_accounts_company_connection", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_accounts_company_status", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_accounts_company_type", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_accounts_company_provider", table_name="marketplace_accounts")
    op.drop_index("ix_marketplace_accounts_company_id", table_name="marketplace_accounts")
    op.drop_table("marketplace_accounts")
