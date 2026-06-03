from __future__ import annotations

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OperationNatureDB(Base):
    """Natureza de operação parametrizável por empresa.

    Evita tratar bonificação, amostra, troca e venda normal como texto solto em
    sales. A tela operacional escolhe a natureza; o backend usa esta tabela para
    derivar comportamento financeiro/fiscal inicial.
    """

    __tablename__ = "operation_natures"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(40), nullable=False, default="both")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_reason: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    affects_revenue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    affects_accounts_receivable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    affects_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_fiscal_document: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_receivable_behavior: Mapped[str] = mapped_column(String(40), nullable=False, default="full")
    default_invoice_behavior: Mapped[str] = mapped_column(String(40), nullable=False, default="full")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_operation_natures_company_id", "company_id"),
        Index("ix_operation_natures_company_code", "company_id", "code"),
        Index("ix_operation_natures_company_sale_type", "company_id", "sale_type"),
        Index("ix_operation_natures_company_status", "company_id", "status"),
    )


class CatalogItemFiscalRuleDB(Base):
    """Regra que liga item + natureza + classificação fiscal.

    Esta tabela prepara o ERP para resolver automaticamente a classificação fiscal
    aplicável à venda sem expor NCM/CFOP/CST ao operador do caixa.
    """

    __tablename__ = "catalog_item_fiscal_rules"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    catalog_item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False)
    fiscal_classification_id: Mapped[str] = mapped_column(String(80), ForeignKey("fiscal_classifications.id", ondelete="RESTRICT"), nullable=False)
    operation_nature_id: Mapped[str] = mapped_column(String(80), ForeignKey("operation_natures.id", ondelete="RESTRICT"), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[object | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[object | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_catalog_item_fiscal_rules_company_id", "company_id"),
        Index("ix_catalog_item_fiscal_rules_company_item", "company_id", "catalog_item_id"),
        Index("ix_catalog_item_fiscal_rules_company_classification", "company_id", "fiscal_classification_id"),
        Index("ix_catalog_item_fiscal_rules_company_nature", "company_id", "operation_nature_id"),
        Index("ix_catalog_item_fiscal_rules_company_type", "company_id", "sale_type"),
        Index("ix_catalog_item_fiscal_rules_company_status", "company_id", "status"),
    )

class PaymentMethodDB(Base):
    """Forma de pagamento parametrizável por empresa.

    A venda usa esta tabela para montar um plano de recebimento. Ainda não é baixa,
    recebimento ou conciliação; é a preparação financeira para Contas a Receber.
    """

    __tablename__ = "payment_methods"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    method_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_due_behavior: Mapped[str] = mapped_column(String(40), nullable=False, default="immediate")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_payment_methods_company_code"),
        Index("ix_payment_methods_company_id", "company_id"),
        Index("ix_payment_methods_company_code", "company_id", "code"),
        Index("ix_payment_methods_company_type", "company_id", "method_type"),
        Index("ix_payment_methods_company_status", "company_id", "status"),
    )


class SaleDB(Base):
    """Venda/pedido comercial persistido."""

    __tablename__ = "sales"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    establishment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    participant_id: Mapped[str] = mapped_column(String(80), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    sale_type: Mapped[str] = mapped_column(String(40), nullable=False, default="product")
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    operation_nature: Mapped[str] = mapped_column(String(80), nullable=False, default="normal_sale")
    operation_nature_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("operation_natures.id", ondelete="RESTRICT"), nullable=True)
    operation_nature_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_nature_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fiscal_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_classification")
    issue_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    operation_date: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    competency_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    subtotal_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    discount_type: Mapped[str] = mapped_column(String(40), nullable=False, default="amount")
    discount_percentage: Mapped[object | None] = mapped_column(Numeric(18, 6), nullable=True)
    discount_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    discount_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    freight_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    receivable_total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    invoice_total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    participant_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sale_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_number_text: Mapped[str | None] = mapped_column(String(20), nullable=True)
    paid_number_text: Mapped[str | None] = mapped_column(String(30), nullable=True)
    closed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    paid_by: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    unlocked_by: Mapped[str | None] = mapped_column(String(80), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    unlocked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["SaleItemDB"]] = relationship("SaleItemDB", back_populates="sale", cascade="all, delete-orphan", passive_deletes=True)
    payment_plans: Mapped[list["SalePaymentPlanDB"]] = relationship("SalePaymentPlanDB", back_populates="sale", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        Index("ix_sales_company_id", "company_id"),
        Index("ix_sales_company_status", "company_id", "status"),
        Index("ix_sales_company_type", "company_id", "sale_type"),
        Index("ix_sales_company_operation_nature", "company_id", "operation_nature"),
        Index("ix_sales_company_operation_nature_id", "company_id", "operation_nature_id"),
        Index("ix_sales_company_fiscal_status", "company_id", "fiscal_status"),
        Index("ix_sales_company_participant", "company_id", "participant_id"),
        Index("ix_sales_company_operation_date", "company_id", "operation_date"),
        Index("ix_sales_company_issue_date", "company_id", "issue_date"),
        Index("ix_sales_company_competency_date", "company_id", "competency_date"),
        Index("ix_sales_company_created", "company_id", "created_at"),
        Index("ix_sales_company_updated", "company_id", "updated_at"),
        Index("uix_sales_company_sale_number", "company_id", "sale_number", unique=True, postgresql_where=text("sale_number IS NOT NULL")),
    )


class SaleItemDB(Base):
    """Item da venda."""

    __tablename__ = "sale_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(80), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(80), ForeignKey("catalog_items.id", ondelete="RESTRICT"), nullable=False)
    stock_lot_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("stock_lots.id", ondelete="RESTRICT"), nullable=True)
    stock_lot_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    stock_lot_expiration_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    fiscal_classification_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("fiscal_classifications.id", ondelete="RESTRICT"), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(18, 4), nullable=False)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    freight_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tax_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    item_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fiscal_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    operation_nature_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    sale: Mapped[SaleDB] = relationship("SaleDB", back_populates="items")

    __table_args__ = (
        Index("ix_sale_items_company_id", "company_id"),
        Index("ix_sale_items_sale_id", "sale_id"),
        Index("ix_sale_items_company_item", "company_id", "item_id"),
        Index("ix_sale_items_company_stock_lot", "company_id", "stock_lot_id"),
        Index("ix_sale_items_company_stock_lot_code", "company_id", "stock_lot_code"),
        Index("ix_sale_items_company_fiscal_classification", "company_id", "fiscal_classification_id"),
        Index("ix_sale_items_company_created", "company_id", "created_at"),
    )

class SalePaymentPlanDB(Base):
    """Plano de pagamento/recebimento previsto para a venda.

    Não representa dinheiro recebido. Prepara a geração futura de contas a receber,
    parcelas, baixas e conciliação.
    """

    __tablename__ = "sale_payment_plans"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(80), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    payment_method_id: Mapped[str] = mapped_column(String(80), ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=False)
    payment_method_code: Mapped[str] = mapped_column(String(80), nullable=False)
    payment_method_name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    due_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    installments: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    sale: Mapped[SaleDB] = relationship("SaleDB", back_populates="payment_plans")

    __table_args__ = (
        Index("ix_sale_payment_plans_company_id", "company_id"),
        Index("ix_sale_payment_plans_sale_id", "sale_id"),
        Index("ix_sale_payment_plans_company_sale", "company_id", "sale_id"),
        Index("ix_sale_payment_plans_company_method", "company_id", "payment_method_id"),
        Index("ix_sale_payment_plans_company_method_code", "company_id", "payment_method_code"),
        Index("ix_sale_payment_plans_company_due_date", "company_id", "due_date"),
        Index("ix_sale_payment_plans_company_status", "company_id", "status"),
    )


class SaleStatusHistoryDB(Base):
    """Histórico de status da venda."""

    __tablename__ = "sale_status_history"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(80), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_sale_status_history_company_id", "company_id"),
        Index("ix_sale_status_history_sale_id", "sale_id"),
        Index("ix_sale_status_history_company_sale", "company_id", "sale_id"),
        Index("ix_sale_status_history_company_occurred", "company_id", "occurred_at"),
    )


class SaleSequenceDB(Base):
    """Sequência de numeração humana de pedidos por empresa."""

    __tablename__ = "sale_sequences"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, unique=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_sale_sequences_company_id", "company_id"),
    )
