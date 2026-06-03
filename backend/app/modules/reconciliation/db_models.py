from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BankStatementImportDB(Base):
    """Lote/importação de extrato bancário ou de intermediador.

    O lote é uma evidência externa. Ele não movimenta saldo interno sozinho; apenas
    fornece linhas para conciliar contra financial_movements.
    """

    __tablename__ = "bank_statement_imports"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    source_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statement_start_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    statement_end_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    opening_balance_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    closing_balance_amount: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    line_count: Mapped[int] = mapped_column(nullable=False, default=0)
    total_inflow_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_outflow_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="processed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "financial_account_id", "source_type", "source_id", name="uq_bank_statement_imports_company_account_source"),
        Index("ix_bank_statement_imports_company_id", "company_id"),
        Index("ix_bank_statement_imports_company_account", "company_id", "financial_account_id"),
        Index("ix_bank_statement_imports_company_status", "company_id", "status"),
        Index("ix_bank_statement_imports_company_period", "company_id", "statement_start_date", "statement_end_date"),
    )


class BankStatementLineDB(Base):
    """Linha de extrato externa a ser conciliada.

    Cada linha é uma evidência de banco/gateway/marketplace. A linha só vira
    conciliação quando houver match confirmado com movimento interno.
    """

    __tablename__ = "bank_statement_lines"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    statement_import_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("bank_statement_imports.id", ondelete="SET NULL"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    line_date: Mapped[object] = mapped_column(Date, nullable=False)
    posted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    counterparty_document: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    match_confidence: Mapped[str | None] = mapped_column(String(40), nullable=True)
    matched_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    ignored_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "financial_account_id", "external_id", name="uq_bank_statement_lines_company_account_external"),
        Index("ix_bank_statement_lines_company_id", "company_id"),
        Index("ix_bank_statement_lines_company_account", "company_id", "financial_account_id"),
        Index("ix_bank_statement_lines_company_status", "company_id", "status"),
        Index("ix_bank_statement_lines_company_date", "company_id", "line_date"),
        Index("ix_bank_statement_lines_company_account_date", "company_id", "financial_account_id", "line_date"),
        Index("ix_bank_statement_lines_company_status_date", "company_id", "status", "line_date"),
        Index("ix_bank_statement_lines_company_account_status_date", "company_id", "financial_account_id", "status", "line_date"),
        Index("ix_bank_statement_lines_company_amount", "company_id", "direction", "amount"),
        Index("ix_bank_statement_lines_import", "statement_import_id"),
    )


class ReconciliationMatchDB(Base):
    """Vínculo auditável entre linha externa e movimento financeiro interno."""

    __tablename__ = "reconciliation_matches"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(80), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False)
    financial_account_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_accounts.id", ondelete="RESTRICT"), nullable=False)
    statement_line_id: Mapped[str] = mapped_column(String(80), ForeignKey("bank_statement_lines.id", ondelete="RESTRICT"), nullable=False)
    financial_movement_id: Mapped[str] = mapped_column(String(80), ForeignKey("financial_movements.id", ondelete="RESTRICT"), nullable=False)
    match_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    matched_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    line_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    movement_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    difference_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tolerance_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="confirmed")
    confirmation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reversed_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("statement_line_id", "financial_movement_id", name="uq_reconciliation_matches_line_movement"),
        Index("ix_reconciliation_matches_company_id", "company_id"),
        Index("ix_reconciliation_matches_company_account", "company_id", "financial_account_id"),
        Index("ix_reconciliation_matches_company_status", "company_id", "status"),
        Index("ix_reconciliation_matches_company_account_created", "company_id", "financial_account_id", "created_at"),
        Index("ix_reconciliation_matches_company_status_created", "company_id", "status", "created_at"),
        Index("ix_reconciliation_matches_company_account_status_created", "company_id", "financial_account_id", "status", "created_at"),
        Index("ix_reconciliation_matches_line", "statement_line_id"),
        Index("ix_reconciliation_matches_movement", "financial_movement_id"),
    )
