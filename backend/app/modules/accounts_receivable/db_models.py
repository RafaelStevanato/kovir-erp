from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FinancialTitleDB(Base):
    """Título financeiro.

    Neste bloco usamos direction="receivable". A tabela nasce genérica o suficiente
    para Contas a Pagar no futuro, mas o service de Contas a Receber só cria AR.
    Venda, documento fiscal, baixa e conciliação permanecem conceitos separados.
    """

    __tablename__ = "financial_titles"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="receivable")
    title_type: Mapped[str] = mapped_column(String(40), nullable=False, default="sale")
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    sale_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True)
    sale_payment_plan_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_payment_plans.id", ondelete="RESTRICT"), nullable=True)

    participant_id: Mapped[str] = mapped_column(String(80), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=False)
    participant_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    payment_method_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=True)
    payment_method_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_method_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    financial_category_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True)
    cost_center_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True)
    expected_financial_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=True)

    document_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    installment_number: Mapped[int] = mapped_column(nullable=False, default=1)
    installment_total: Mapped[int] = mapped_column(nullable=False, default=1)

    issue_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    competency_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[object] = mapped_column(Date, nullable=False)
    expected_payment_date: Mapped[object | None] = mapped_column(Date, nullable=True)

    gross_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    interest_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    penalty_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    fee_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    net_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    open_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    collection_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_started")
    fiscal_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_document")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    links: Mapped[list["SaleFinancialLinkDB"]] = relationship("SaleFinancialLinkDB", back_populates="financial_title")

    __table_args__ = (
        UniqueConstraint("company_id", "source_type", "source_id", name="uq_financial_titles_company_source"),
        Index("ix_financial_titles_company_id", "company_id"),
        Index("ix_financial_titles_company_direction", "company_id", "direction"),
        Index("ix_financial_titles_company_status", "company_id", "status"),
        Index("ix_financial_titles_company_direction_status_due", "company_id", "direction", "status", "due_date"),
        Index("ix_financial_titles_company_collection", "company_id", "collection_status"),
        Index("ix_financial_titles_company_fiscal", "company_id", "fiscal_status"),
        Index("ix_financial_titles_company_participant", "company_id", "participant_id"),
        Index("ix_financial_titles_company_due", "company_id", "due_date"),
        Index("ix_financial_titles_company_source", "company_id", "source_type", "source_id"),
        Index("ix_financial_titles_company_sale", "company_id", "sale_id"),
        Index("ix_financial_titles_company_category", "company_id", "financial_category_id"),
        Index("ix_financial_titles_company_account", "company_id", "expected_financial_account_id"),
        Index("ix_financial_titles_company_direction_account_due", "company_id", "direction", "expected_financial_account_id", "due_date"),
    )


class SaleFinancialLinkDB(Base):
    """Vínculo flexível entre venda, plano previsto e título financeiro."""

    __tablename__ = "sale_financial_links"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(80), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    sale_payment_plan_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("sale_payment_plans.id", ondelete="RESTRICT"), nullable=True)
    financial_title_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, default="generated_from_sale")
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    financial_title: Mapped[FinancialTitleDB] = relationship("FinancialTitleDB", back_populates="links")

    __table_args__ = (
        UniqueConstraint("company_id", "sale_payment_plan_id", "financial_title_id", name="uq_sale_financial_links_plan_title"),
        Index("ix_sale_financial_links_company_id", "company_id"),
        Index("ix_sale_financial_links_company_sale", "company_id", "sale_id"),
        Index("ix_sale_financial_links_company_plan", "company_id", "sale_payment_plan_id"),
        Index("ix_sale_financial_links_company_title", "company_id", "financial_title_id"),
        Index("ix_sale_financial_links_company_status", "company_id", "status"),
    )


class FinancialTitleHistoryDB(Base):
    """Histórico de alterações de status de um título financeiro."""

    __tablename__ = "financial_title_history"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_title_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_titles.id", ondelete="CASCADE"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_collection_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_collection_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_financial_title_history_company_id", "company_id"),
        Index("ix_financial_title_history_title", "financial_title_id"),
        Index("ix_financial_title_history_company_title", "company_id", "financial_title_id"),
        Index("ix_financial_title_history_company_occurred", "company_id", "occurred_at"),
    )
