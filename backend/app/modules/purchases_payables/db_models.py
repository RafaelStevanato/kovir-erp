from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PurchaseDB(Base):
    """Compra/despesa operacional.

    Compra não é pagamento. Esta tabela registra a obrigação operacional que pode
    gerar títulos a pagar em financial_titles com direction="payable".
    """

    __tablename__ = "purchases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    establishment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    participant_id: Mapped[str] = mapped_column(String(80), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    purchase_type: Mapped[str] = mapped_column(String(40), nullable=False, default="expense")
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    operation_nature_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("operation_natures.id", ondelete="RESTRICT"), nullable=True)
    fiscal_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_document")

    issue_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    operation_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    competency_date: Mapped[object | None] = mapped_column(Date, nullable=True)

    subtotal_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    freight_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    payable_total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    invoice_total_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)

    financial_category_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True)
    cost_center_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True)
    expected_financial_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=True)

    document_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    document_series: Mapped[str | None] = mapped_column(String(40), nullable=True)
    access_key: Mapped[str | None] = mapped_column(String(80), nullable=True)

    participant_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    document_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["PurchaseItemDB"]] = relationship("PurchaseItemDB", back_populates="purchase", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("ix_purchases_company_id", "company_id"),
        Index("ix_purchases_company_status", "company_id", "status"),
        Index("ix_purchases_company_status_created", "company_id", "status", "created_at"),
        Index("ix_purchases_company_type", "company_id", "purchase_type"),
        Index("ix_purchases_company_participant", "company_id", "participant_id"),
        Index("ix_purchases_company_operation_date", "company_id", "operation_date"),
        Index("ix_purchases_company_competency", "company_id", "competency_date"),
        Index("ix_purchases_company_document", "company_id", "document_number"),
        Index("ix_purchases_company_category", "company_id", "financial_category_id"),
    )


class PurchaseItemDB(Base):
    """Item de compra/despesa."""

    __tablename__ = "purchase_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(80), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=True)
    fiscal_classification_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("fiscal_classifications.id", ondelete="RESTRICT"), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_cost: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    freight_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    item_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fiscal_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    purchase: Mapped[PurchaseDB] = relationship("PurchaseDB", back_populates="items")

    __table_args__ = (
        Index("ix_purchase_items_company_id", "company_id"),
        Index("ix_purchase_items_purchase", "purchase_id"),
        Index("ix_purchase_items_company_item", "company_id", "item_id"),
        Index("ix_purchase_items_company_fiscal", "company_id", "fiscal_classification_id"),
    )


class PurchaseFinancialLinkDB(Base):
    """Vínculo auditável entre compra/despesa e título a pagar."""

    __tablename__ = "purchase_financial_links"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(80), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    financial_title_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False)
    installment_number: Mapped[int] = mapped_column(nullable=False, default=1)
    installment_total: Mapped[int] = mapped_column(nullable=False, default=1)
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, default="generated_from_purchase")
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "purchase_id", "installment_number", name="uq_purchase_financial_links_installment"),
        UniqueConstraint("company_id", "financial_title_id", name="uq_purchase_financial_links_title"),
        Index("ix_purchase_financial_links_company_id", "company_id"),
        Index("ix_purchase_financial_links_company_purchase", "company_id", "purchase_id"),
        Index("ix_purchase_financial_links_company_title", "company_id", "financial_title_id"),
        Index("ix_purchase_financial_links_company_status", "company_id", "status"),
    )


class PurchaseStatusHistoryDB(Base):
    """Histórico de status de compra/despesa."""

    __tablename__ = "purchase_status_history"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(80), ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_purchase_status_history_company_id", "company_id"),
        Index("ix_purchase_status_history_purchase", "purchase_id"),
        Index("ix_purchase_status_history_company_purchase", "company_id", "purchase_id"),
        Index("ix_purchase_status_history_company_occurred", "company_id", "occurred_at"),
    )
