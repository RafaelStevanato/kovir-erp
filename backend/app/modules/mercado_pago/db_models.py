from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MercadoPagoAccountDB(Base):
    """Conta Mercado Pago dedicada.

    Não armazena access_token, refresh_token, client_secret ou qualquer segredo em
    texto puro. A tabela guarda somente status, metadados e configuração operacional.
    """

    __tablename__ = "mercado_pago_accounts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    marketplace_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("marketplace_accounts.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False, default="sandbox")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    connection_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_connected")
    external_user_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    collector_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    application_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    public_key_fingerprint: Mapped[str | None] = mapped_column(String(80), nullable=True)
    credentials_status: Mapped[str] = mapped_column(String(40), nullable=False, default="missing")
    webhook_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_configured")
    last_healthcheck_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    webhook_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payment_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reconciliation_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "display_name", name="uq_mp_accounts_company_display"),
        Index("ix_mp_accounts_company_id", "company_id"),
        Index("ix_mp_accounts_company_status", "company_id", "status"),
        Index("ix_mp_accounts_company_connection", "company_id", "connection_status"),
        Index("ix_mp_accounts_company_credentials", "company_id", "credentials_status"),
        Index("ix_mp_accounts_external_user", "external_user_id"),
        Index("ix_mp_accounts_collector", "collector_id"),
    )


class MercadoPagoOAuthStateDB(Base):
    __tablename__ = "mercado_pago_oauth_states"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=True)
    state: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="created")
    redirect_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_scopes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "state", name="uq_mp_oauth_company_state"),
        Index("ix_mp_oauth_company_id", "company_id"),
        Index("ix_mp_oauth_account", "mercado_pago_account_id"),
        Index("ix_mp_oauth_company_status", "company_id", "status"),
        Index("ix_mp_oauth_expires", "expires_at"),
    )


class MercadoPagoWebhookEventDB(Base):
    __tablename__ = "mercado_pago_webhook_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="SET NULL"), nullable=True)
    event_source: Mapped[str] = mapped_column(String(80), nullable=False, default="webhook")
    external_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signature_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_verified")
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="received")
    related_payment_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    received_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_event_id", name="uq_mp_webhooks_company_external_event"),
        Index("ix_mp_webhooks_company_id", "company_id"),
        Index("ix_mp_webhooks_account", "mercado_pago_account_id"),
        Index("ix_mp_webhooks_company_topic", "company_id", "topic"),
        Index("ix_mp_webhooks_company_status", "company_id", "processing_status"),
        Index("ix_mp_webhooks_resource", "resource_type", "resource_id"),
        Index("ix_mp_webhooks_related_payment", "related_payment_id"),
        Index("ix_mp_webhooks_received", "company_id", "received_at"),
    )


class MercadoPagoCheckoutPreferenceDB(Base):
    __tablename__ = "mercado_pago_checkout_preferences"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False)
    sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    sale_payment_plan_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True)
    external_preference_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    checkout_type: Mapped[str] = mapped_column(String(60), nullable=False, default="checkout_pro")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    init_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_init_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_preference_id", name="uq_mp_preferences_company_external"),
        Index("ix_mp_preferences_company_id", "company_id"),
        Index("ix_mp_preferences_account", "mercado_pago_account_id"),
        Index("ix_mp_preferences_sale", "sale_id"),
        Index("ix_mp_preferences_payment_plan", "sale_payment_plan_id"),
        Index("ix_mp_preferences_company_status", "company_id", "status"),
    )


class MercadoPagoPaymentDB(Base):
    __tablename__ = "mercado_pago_payments"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False)
    sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    sale_payment_plan_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True)
    checkout_preference_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_checkout_preferences.id", ondelete="SET NULL"), nullable=True)
    external_payment_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_order_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    payment_method_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_type_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status_detail: Mapped[str | None] = mapped_column(String(160), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    gross_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    transaction_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_received_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payer_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    card_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_payment_id", name="uq_mp_payments_company_external_payment"),
        Index("ix_mp_payments_company_id", "company_id"),
        Index("ix_mp_payments_account", "mercado_pago_account_id"),
        Index("ix_mp_payments_sale", "sale_id"),
        Index("ix_mp_payments_payment_plan", "sale_payment_plan_id"),
        Index("ix_mp_payments_company_status", "company_id", "status"),
        Index("ix_mp_payments_method", "company_id", "payment_method_id"),
        Index("ix_mp_payments_external_reference", "external_reference"),
        Index("ix_mp_payments_created", "company_id", "created_at"),
    )


class MercadoPagoReleaseDB(Base):
    __tablename__ = "mercado_pago_releases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False)
    mercado_pago_payment_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True)
    external_release_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    release_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gross_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    expected_release_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    released_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_release_id", name="uq_mp_releases_company_external_release"),
        Index("ix_mp_releases_company_id", "company_id"),
        Index("ix_mp_releases_account", "mercado_pago_account_id"),
        Index("ix_mp_releases_payment", "mercado_pago_payment_id"),
        Index("ix_mp_releases_company_status", "company_id", "status"),
        Index("ix_mp_releases_expected_date", "company_id", "expected_release_date"),
        Index("ix_mp_releases_released_at", "company_id", "released_at"),
    )


class MercadoPagoRefundDB(Base):
    __tablename__ = "mercado_pago_refunds"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False)
    mercado_pago_payment_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True)
    external_refund_id: Mapped[str] = mapped_column(String(180), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    refunded_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_refund_id", name="uq_mp_refunds_company_external_refund"),
        Index("ix_mp_refunds_company_id", "company_id"),
        Index("ix_mp_refunds_account", "mercado_pago_account_id"),
        Index("ix_mp_refunds_payment", "mercado_pago_payment_id"),
        Index("ix_mp_refunds_external_payment", "external_payment_id"),
        Index("ix_mp_refunds_company_status", "company_id", "status"),
    )


class MercadoPagoChargebackDB(Base):
    __tablename__ = "mercado_pago_chargebacks"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    mercado_pago_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("mercado_pago_accounts.id", ondelete="CASCADE"), nullable=False)
    mercado_pago_payment_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("mercado_pago_payments.id", ondelete="SET NULL"), nullable=True)
    external_chargeback_id: Mapped[str] = mapped_column(String(180), nullable=False)
    external_payment_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage_eligible: Mapped[str | None] = mapped_column(String(40), nullable=True)
    documentation_required: Mapped[str | None] = mapped_column(String(40), nullable=True)
    due_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "external_chargeback_id", name="uq_mp_chargebacks_company_external_chargeback"),
        Index("ix_mp_chargebacks_company_id", "company_id"),
        Index("ix_mp_chargebacks_account", "mercado_pago_account_id"),
        Index("ix_mp_chargebacks_payment", "mercado_pago_payment_id"),
        Index("ix_mp_chargebacks_external_payment", "external_payment_id"),
        Index("ix_mp_chargebacks_company_status", "company_id", "status"),
        Index("ix_mp_chargebacks_due_date", "company_id", "due_date"),
    )
