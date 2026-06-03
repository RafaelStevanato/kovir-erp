from __future__ import annotations

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChartAccountDB(Base):
    """Plano de contas / conta contábil-financeira parametrizável por empresa."""

    __tablename__ = "chart_accounts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True)
    is_analytical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    normal_balance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accepts_entries: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_chart_accounts_company_code"),
        Index("ix_chart_accounts_company_id", "company_id"),
        Index("ix_chart_accounts_company_status", "company_id", "status"),
        Index("ix_chart_accounts_company_type", "company_id", "account_type"),
        Index("ix_chart_accounts_company_name", "company_id", "name"),
    )


class FinancialCategoryDB(Base):
    """Categoria financeira operacional, mapeável para plano de contas."""

    __tablename__ = "financial_categories"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_categories.id", ondelete="RESTRICT"), nullable=True)
    chart_account_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("chart_accounts.id", ondelete="RESTRICT"), nullable=True)
    cash_flow_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    affects_cash_flow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_cost_center: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_financial_categories_company_code"),
        Index("ix_financial_categories_company_id", "company_id"),
        Index("ix_financial_categories_company_status", "company_id", "status"),
        Index("ix_financial_categories_company_type", "company_id", "category_type"),
        Index("ix_financial_categories_company_name", "company_id", "name"),
        Index("ix_financial_categories_company_chart_account", "company_id", "chart_account_id"),
    )


class CostCenterDB(Base):
    """Centro de custo / resultado gerencial."""

    __tablename__ = "cost_centers"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    center_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    parent_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True)
    is_analytical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    responsible_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    monthly_budget_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_cost_centers_company_code"),
        Index("ix_cost_centers_company_id", "company_id"),
        Index("ix_cost_centers_company_status", "company_id", "status"),
        Index("ix_cost_centers_company_type", "company_id", "center_type"),
        Index("ix_cost_centers_company_name", "company_id", "name"),
    )


class FinancialAccountDB(Base):
    """Conta financeira: banco, caixa, gateway, marketplace ou intermediador."""

    __tablename__ = "financial_accounts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    branch_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    account_digit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pix_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pix_key_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    opening_balance_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    is_default_receivable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default_payable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_financial_accounts_company_id", "company_id"),
        Index("ix_financial_accounts_company_status", "company_id", "status"),
        Index("ix_financial_accounts_company_type", "company_id", "account_type"),
        Index("ix_financial_accounts_company_name", "company_id", "name"),
    )


class PaymentTermDB(Base):
    """Condição de pagamento/recebimento reutilizável em vendas, compras e títulos."""

    __tablename__ = "payment_terms"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    term_type: Mapped[str] = mapped_column(String(40), nullable=False, default="cash")
    installments: Mapped[int] = mapped_column(nullable=False, default=1)
    first_due_days: Mapped[int] = mapped_column(nullable=False, default=0)
    interval_days: Mapped[int] = mapped_column(nullable=False, default=30)
    generate_on_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_payment_terms_company_name"),
        Index("ix_payment_terms_company_id", "company_id"),
        Index("ix_payment_terms_company_status", "company_id", "status"),
        Index("ix_payment_terms_company_type", "company_id", "term_type"),
    )


class FinancialPeriodClosureDB(Base):
    """Fechamento de período financeiro por empresa."""

    __tablename__ = "financial_period_closures"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    start_date: Mapped[object] = mapped_column(Date, nullable=False)
    end_date: Mapped[object] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_financial_period_closures_company_id", "company_id"),
        Index("ix_financial_period_closures_company_status", "company_id", "status"),
        Index("ix_financial_period_closures_company_period", "company_id", "start_date", "end_date"),
    )
