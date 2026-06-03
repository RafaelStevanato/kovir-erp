from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MarketplaceAccountDB(Base):
    """Conta/canal de marketplace ou gateway preparado para integração futura.

    Esta tabela não armazena token sensível em texto puro. Ela guarda somente
    configuração operacional, status de conexão e metadados não secretos.
    Credenciais reais devem entrar futuramente por cofre/criptografia.
    """

    __tablename__ = "marketplace_accounts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    provider_code: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False, default="sandbox")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    connection_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_connected")
    external_account_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    last_sync_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credential_metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sync_runs: Mapped[list["MarketplaceSyncRunDB"]] = relationship("MarketplaceSyncRunDB", back_populates="account")

    __table_args__ = (
        UniqueConstraint("company_id", "provider_code", "display_name", name="uq_marketplace_accounts_company_provider_display"),
        Index("ix_marketplace_accounts_company_id", "company_id"),
        Index("ix_marketplace_accounts_company_provider", "company_id", "provider_code"),
        Index("ix_marketplace_accounts_company_type", "company_id", "provider_type"),
        Index("ix_marketplace_accounts_company_status", "company_id", "status"),
        Index("ix_marketplace_accounts_company_connection", "company_id", "connection_status"),
    )


class MarketplaceSyncRunDB(Base):
    """Execução de sincronização/importação futura com marketplace/gateway."""

    __tablename__ = "marketplace_sync_runs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    marketplace_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    records_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    account: Mapped[MarketplaceAccountDB] = relationship("MarketplaceAccountDB", back_populates="sync_runs")

    __table_args__ = (
        Index("ix_marketplace_sync_runs_company_id", "company_id"),
        Index("ix_marketplace_sync_runs_account", "marketplace_account_id"),
        Index("ix_marketplace_sync_runs_company_account", "company_id", "marketplace_account_id"),
        Index("ix_marketplace_sync_runs_company_type", "company_id", "sync_type"),
        Index("ix_marketplace_sync_runs_company_status", "company_id", "status"),
        Index("ix_marketplace_sync_runs_company_started", "company_id", "started_at"),
    )


class MarketplaceExternalOrderDB(Base):
    """Pedido externo importado ou identificado em marketplace.

    Ainda não substitui vendas do Kovir. Serve como camada intermediária futura
    para transformar pedido externo em sales/sale_items com rastreabilidade.
    """

    __tablename__ = "marketplace_external_orders"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    marketplace_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(80), nullable=False)
    external_order_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    linked_sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    buyer_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    amounts_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="imported")
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "provider_code", "external_order_id", name="uq_marketplace_orders_company_provider_external"),
        Index("ix_marketplace_orders_company_id", "company_id"),
        Index("ix_marketplace_orders_account", "marketplace_account_id"),
        Index("ix_marketplace_orders_company_account", "company_id", "marketplace_account_id"),
        Index("ix_marketplace_orders_company_provider", "company_id", "provider_code"),
        Index("ix_marketplace_orders_company_status", "company_id", "status"),
        Index("ix_marketplace_orders_linked_sale", "linked_sale_id"),
    )


class MarketplacePaymentEventDB(Base):
    """Evento financeiro externo vindo de gateway/marketplace.

    Prepara Mercado Pago, Shopee e outros intermediadores para vincular pagamento,
    taxa, repasse, chargeback e liberação futura ao financeiro do Kovir.
    """

    __tablename__ = "marketplace_payment_events"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    marketplace_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("marketplace_accounts.id", ondelete="CASCADE"), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(80), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_order_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    linked_sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    linked_sale_payment_plan_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_payment_plans.id", ondelete="SET NULL"), nullable=True)
    payment_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gross_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    release_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expected_release_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    released_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    imported_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "provider_code", "external_payment_id", name="uq_marketplace_payments_company_provider_external"),
        Index("ix_marketplace_payments_company_id", "company_id"),
        Index("ix_marketplace_payments_account", "marketplace_account_id"),
        Index("ix_marketplace_payments_company_account", "company_id", "marketplace_account_id"),
        Index("ix_marketplace_payments_company_provider", "company_id", "provider_code"),
        Index("ix_marketplace_payments_status", "company_id", "payment_status"),
        Index("ix_marketplace_payments_linked_sale", "linked_sale_id"),
        Index("ix_marketplace_payments_linked_payment_plan", "linked_sale_payment_plan_id"),
    )
