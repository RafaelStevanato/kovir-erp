"""create mercado pago dedicated integration foundation

Revision ID: 20260428_0012
Revises: 20260428_0011
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_0012"
down_revision = "20260428_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mercado_pago_accounts",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("participant_id", sa.String(length=80), sa.ForeignKey("participants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("marketplace_account_id", sa.String(length=80), sa.ForeignKey("marketplace_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False, server_default="sandbox"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("connection_status", sa.String(length=40), nullable=False, server_default="not_connected"),
        sa.Column("external_user_id", sa.String(length=160), nullable=True),
        sa.Column("collector_id", sa.String(length=160), nullable=True),
        sa.Column("application_id", sa.String(length=160), nullable=True),
        sa.Column("public_key_fingerprint", sa.String(length=80), nullable=True),
        sa.Column("credentials_status", sa.String(length=40), nullable=False, server_default="missing"),
        sa.Column("webhook_status", sa.String(length=40), nullable=False, server_default="not_configured"),
        sa.Column("last_healthcheck_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("webhook_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payment_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reconciliation_settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "display_name", name="uq_mp_accounts_company_display"),
    )
    op.create_index("ix_mp_accounts_company_id", "mercado_pago_accounts", ["company_id"])
    op.create_index("ix_mp_accounts_company_status", "mercado_pago_accounts", ["company_id", "status"])
    op.create_index("ix_mp_accounts_company_connection", "mercado_pago_accounts", ["company_id", "connection_status"])
    op.create_index("ix_mp_accounts_company_credentials", "mercado_pago_accounts", ["company_id", "credentials_status"])
    op.create_index("ix_mp_accounts_external_user", "mercado_pago_accounts", ["external_user_id"])
    op.create_index("ix_mp_accounts_collector", "mercado_pago_accounts", ["collector_id"])

    op.create_table(
        "mercado_pago_oauth_states",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="created"),
        sa.Column("redirect_uri", sa.String(length=500), nullable=True),
        sa.Column("requested_scopes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "state", name="uq_mp_oauth_company_state"),
    )
    op.create_index("ix_mp_oauth_company_id", "mercado_pago_oauth_states", ["company_id"])
    op.create_index("ix_mp_oauth_account", "mercado_pago_oauth_states", ["mercado_pago_account_id"])
    op.create_index("ix_mp_oauth_company_status", "mercado_pago_oauth_states", ["company_id", "status"])
    op.create_index("ix_mp_oauth_expires", "mercado_pago_oauth_states", ["expires_at"])

    op.create_table(
        "mercado_pago_webhook_events",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_source", sa.String(length=80), nullable=False, server_default="webhook"),
        sa.Column("external_event_id", sa.String(length=160), nullable=True),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=True),
        sa.Column("resource_id", sa.String(length=160), nullable=True),
        sa.Column("resource_type", sa.String(length=120), nullable=True),
        sa.Column("signature_status", sa.String(length=40), nullable=False, server_default="not_verified"),
        sa.Column("processing_status", sa.String(length=40), nullable=False, server_default="received"),
        sa.Column("related_payment_id", sa.String(length=160), nullable=True),
        sa.Column("headers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_event_id", name="uq_mp_webhooks_company_external_event"),
    )
    op.create_index("ix_mp_webhooks_company_id", "mercado_pago_webhook_events", ["company_id"])
    op.create_index("ix_mp_webhooks_account", "mercado_pago_webhook_events", ["mercado_pago_account_id"])
    op.create_index("ix_mp_webhooks_company_topic", "mercado_pago_webhook_events", ["company_id", "topic"])
    op.create_index("ix_mp_webhooks_company_status", "mercado_pago_webhook_events", ["company_id", "processing_status"])
    op.create_index("ix_mp_webhooks_resource", "mercado_pago_webhook_events", ["resource_type", "resource_id"])
    op.create_index("ix_mp_webhooks_related_payment", "mercado_pago_webhook_events", ["related_payment_id"])
    op.create_index("ix_mp_webhooks_received", "mercado_pago_webhook_events", ["company_id", "received_at"])

    op.create_table(
        "mercado_pago_checkout_preferences",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sale_payment_plan_id", sa.String(length=80), sa.ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_preference_id", sa.String(length=180), nullable=True),
        sa.Column("checkout_type", sa.String(length=60), nullable=False, server_default="checkout_pro"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("init_point", sa.Text(), nullable=True),
        sa.Column("sandbox_init_point", sa.Text(), nullable=True),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_preference_id", name="uq_mp_preferences_company_external"),
    )
    op.create_index("ix_mp_preferences_company_id", "mercado_pago_checkout_preferences", ["company_id"])
    op.create_index("ix_mp_preferences_account", "mercado_pago_checkout_preferences", ["mercado_pago_account_id"])
    op.create_index("ix_mp_preferences_sale", "mercado_pago_checkout_preferences", ["sale_id"])
    op.create_index("ix_mp_preferences_payment_plan", "mercado_pago_checkout_preferences", ["sale_payment_plan_id"])
    op.create_index("ix_mp_preferences_company_status", "mercado_pago_checkout_preferences", ["company_id", "status"])

    op.create_table(
        "mercado_pago_payments",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_id", sa.String(length=80), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sale_payment_plan_id", sa.String(length=80), sa.ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("checkout_preference_id", sa.String(length=80), sa.ForeignKey("mercado_pago_checkout_preferences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_payment_id", sa.String(length=160), nullable=False),
        sa.Column("external_order_id", sa.String(length=160), nullable=True),
        sa.Column("external_reference", sa.String(length=180), nullable=True),
        sa.Column("payment_method_id", sa.String(length=120), nullable=True),
        sa.Column("payment_type_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("status_detail", sa.String(length=160), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="BRL"),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("transaction_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("net_received_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("installments", sa.Integer(), nullable=True),
        sa.Column("payer_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("card_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_payment_id", name="uq_mp_payments_company_external_payment"),
    )
    op.create_index("ix_mp_payments_company_id", "mercado_pago_payments", ["company_id"])
    op.create_index("ix_mp_payments_account", "mercado_pago_payments", ["mercado_pago_account_id"])
    op.create_index("ix_mp_payments_sale", "mercado_pago_payments", ["sale_id"])
    op.create_index("ix_mp_payments_payment_plan", "mercado_pago_payments", ["sale_payment_plan_id"])
    op.create_index("ix_mp_payments_company_status", "mercado_pago_payments", ["company_id", "status"])
    op.create_index("ix_mp_payments_method", "mercado_pago_payments", ["company_id", "payment_method_id"])
    op.create_index("ix_mp_payments_external_reference", "mercado_pago_payments", ["external_reference"])
    op.create_index("ix_mp_payments_created", "mercado_pago_payments", ["company_id", "created_at"])

    op.create_table(
        "mercado_pago_releases",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mercado_pago_payment_id", sa.String(length=80), sa.ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_release_id", sa.String(length=180), nullable=True),
        sa.Column("release_type", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("fee_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_release_date", sa.Date(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_release_id", name="uq_mp_releases_company_external_release"),
    )
    op.create_index("ix_mp_releases_company_id", "mercado_pago_releases", ["company_id"])
    op.create_index("ix_mp_releases_account", "mercado_pago_releases", ["mercado_pago_account_id"])
    op.create_index("ix_mp_releases_payment", "mercado_pago_releases", ["mercado_pago_payment_id"])
    op.create_index("ix_mp_releases_company_status", "mercado_pago_releases", ["company_id", "status"])
    op.create_index("ix_mp_releases_expected_date", "mercado_pago_releases", ["company_id", "expected_release_date"])
    op.create_index("ix_mp_releases_released_at", "mercado_pago_releases", ["company_id", "released_at"])

    op.create_table(
        "mercado_pago_refunds",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mercado_pago_payment_id", sa.String(length=80), sa.ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_refund_id", sa.String(length=180), nullable=False),
        sa.Column("external_payment_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_refund_id", name="uq_mp_refunds_company_external_refund"),
    )
    op.create_index("ix_mp_refunds_company_id", "mercado_pago_refunds", ["company_id"])
    op.create_index("ix_mp_refunds_account", "mercado_pago_refunds", ["mercado_pago_account_id"])
    op.create_index("ix_mp_refunds_payment", "mercado_pago_refunds", ["mercado_pago_payment_id"])
    op.create_index("ix_mp_refunds_external_payment", "mercado_pago_refunds", ["external_payment_id"])
    op.create_index("ix_mp_refunds_company_status", "mercado_pago_refunds", ["company_id", "status"])

    op.create_table(
        "mercado_pago_chargebacks",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("company_id", sa.String(length=80), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("mercado_pago_account_id", sa.String(length=80), sa.ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mercado_pago_payment_id", sa.String(length=80), sa.ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("external_chargeback_id", sa.String(length=180), nullable=False),
        sa.Column("external_payment_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("coverage_eligible", sa.String(length=40), nullable=True),
        sa.Column("documentation_required", sa.String(length=40), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "external_chargeback_id", name="uq_mp_chargebacks_company_external_chargeback"),
    )
    op.create_index("ix_mp_chargebacks_company_id", "mercado_pago_chargebacks", ["company_id"])
    op.create_index("ix_mp_chargebacks_account", "mercado_pago_chargebacks", ["mercado_pago_account_id"])
    op.create_index("ix_mp_chargebacks_payment", "mercado_pago_chargebacks", ["mercado_pago_payment_id"])
    op.create_index("ix_mp_chargebacks_external_payment", "mercado_pago_chargebacks", ["external_payment_id"])
    op.create_index("ix_mp_chargebacks_company_status", "mercado_pago_chargebacks", ["company_id", "status"])
    op.create_index("ix_mp_chargebacks_due_date", "mercado_pago_chargebacks", ["company_id", "due_date"])

    op.alter_column("mercado_pago_accounts", "environment", server_default=None)
    op.alter_column("mercado_pago_accounts", "status", server_default=None)
    op.alter_column("mercado_pago_accounts", "connection_status", server_default=None)
    op.alter_column("mercado_pago_accounts", "credentials_status", server_default=None)
    op.alter_column("mercado_pago_accounts", "webhook_status", server_default=None)
    op.alter_column("mercado_pago_oauth_states", "status", server_default=None)
    op.alter_column("mercado_pago_webhook_events", "event_source", server_default=None)
    op.alter_column("mercado_pago_webhook_events", "signature_status", server_default=None)
    op.alter_column("mercado_pago_webhook_events", "processing_status", server_default=None)
    op.alter_column("mercado_pago_checkout_preferences", "checkout_type", server_default=None)
    op.alter_column("mercado_pago_checkout_preferences", "status", server_default=None)
    op.alter_column("mercado_pago_checkout_preferences", "currency", server_default=None)
    op.alter_column("mercado_pago_payments", "currency", server_default=None)


def downgrade() -> None:
    op.drop_table("mercado_pago_chargebacks")
    op.drop_table("mercado_pago_refunds")
    op.drop_table("mercado_pago_releases")
    op.drop_table("mercado_pago_payments")
    op.drop_table("mercado_pago_checkout_preferences")
    op.drop_table("mercado_pago_webhook_events")
    op.drop_table("mercado_pago_oauth_states")
    op.drop_table("mercado_pago_accounts")
