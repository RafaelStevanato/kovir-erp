from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SettlementDB(Base):
    """Baixa/liquidação de título financeiro.

    No MVP deste bloco tratamos recebimentos de Contas a Receber. A baixa reduz o
    saldo em aberto do título, registra evidência e cria movimento financeiro
    interno. Conciliação bancária permanece etapa posterior.
    """

    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="inflow")
    settlement_type: Mapped[str] = mapped_column(String(40), nullable=False, default="receipt")
    financial_title_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=False)
    participant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    payment_method_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("payment_methods.id", ondelete="RESTRICT"), nullable=True)

    settlement_date: Mapped[object] = mapped_column(Date, nullable=False)
    competency_date: Mapped[object | None] = mapped_column(Date, nullable=True)

    received_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    discount_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    interest_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    penalty_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    fee_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    title_settled_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    movement_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)

    source_type: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    reversal_of_settlement_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("settlements.id", ondelete="RESTRICT"), nullable=True)
    reversed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "source_type", "source_id", name="uq_settlements_company_source"),
        Index("ix_settlements_company_id", "company_id"),
        Index("ix_settlements_company_title", "company_id", "financial_title_id"),
        Index("ix_settlements_company_account", "company_id", "financial_account_id"),
        Index("ix_settlements_company_date", "company_id", "settlement_date"),
        Index("ix_settlements_company_status", "company_id", "status"),
        Index("ix_settlements_company_status_date", "company_id", "status", "settlement_date"),
        Index("ix_settlements_company_account_date", "company_id", "financial_account_id", "settlement_date"),
        Index("ix_settlements_company_payment_method_date", "company_id", "payment_method_id", "settlement_date"),
        Index("ix_settlements_company_source", "company_id", "source_type", "source_id"),
    )


class FinancialMovementDB(Base):
    """Movimento financeiro interno de caixa/banco/gateway.

    Movimento interno não é conciliação. Ele representa a entrada/saída registrada
    no ERP e ficará pendente de match com extrato/importação em bloco posterior.
    """

    __tablename__ = "financial_movements"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    movement_date: Mapped[object] = mapped_column(Date, nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")

    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False)
    settlement_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("settlements.id", ondelete="RESTRICT"), nullable=True)
    financial_title_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_titles.id", ondelete="RESTRICT"), nullable=True)
    participant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("participants.id", ondelete="RESTRICT"), nullable=True)

    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="posted")
    reconciliation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    reversal_of_movement_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_movements.id", ondelete="RESTRICT"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "source_type", "source_id", name="uq_financial_movements_company_source"),
        Index("ix_financial_movements_company_id", "company_id"),
        Index("ix_financial_movements_company_account", "company_id", "financial_account_id"),
        Index("ix_financial_movements_company_date", "company_id", "movement_date"),
        Index("ix_financial_movements_company_status", "company_id", "status"),
        Index("ix_financial_movements_company_reconciliation", "company_id", "reconciliation_status"),
        Index("ix_financial_movements_company_status_date", "company_id", "status", "movement_date"),
        Index("ix_financial_movements_company_account_date", "company_id", "financial_account_id", "movement_date"),
        Index("ix_financial_movements_company_direction_date", "company_id", "direction", "movement_date"),
        Index("ix_financial_movements_company_type_date", "company_id", "movement_type", "movement_date"),
        Index("ix_financial_movements_company_reconciliation_date", "company_id", "reconciliation_status", "movement_date"),
        Index("ix_financial_movements_company_account_reconciliation_date", "company_id", "financial_account_id", "reconciliation_status", "movement_date"),
        Index("ix_financial_movements_company_source", "company_id", "source_type", "source_id"),
        Index("ix_financial_movements_company_title", "company_id", "financial_title_id"),
    )


class FinancialAccountBalanceDB(Base):
    """Saldo interno materializado por conta financeira."""

    __tablename__ = "financial_account_balances"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    current_balance_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    last_movement_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("financial_movements.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "financial_account_id", name="uq_financial_account_balances_company_account"),
        Index("ix_financial_account_balances_company_id", "company_id"),
        Index("ix_financial_account_balances_account", "financial_account_id"),
    )
