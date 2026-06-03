from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompanyDB(Base):
    """Modelo relacional da empresa raiz do Kovir ERP."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    responsible_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")

    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_complement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_ibge_municipality_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tax_regime: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")
    main_cnae: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state_registration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    municipal_registration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fiscal_environment: Mapped[str] = mapped_column(String(40), nullable=False, default="none")
    uses_fiscal_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prepared_for_tax_reform: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Campos para emissão de NF-e / NFC-e via Focus NFe
    crt: Mapped[str | None] = mapped_column(String(1), nullable=True)  # "1"=Simples, "2"=Simples Excesso, "3"=Regime Normal
    nfe_serie: Mapped[str] = mapped_column(String(3), nullable=False, default="1")
    nfce_serie: Mapped[str] = mapped_column(String(3), nullable=False, default="1")
    focus_nfe_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    monthly_closing_day: Mapped[int] = mapped_column(Integer, nullable=False, default=31)
    uses_accounts_receivable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uses_accounts_payable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uses_cash_control: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uses_cost_center: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uses_chart_of_accounts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="America/Sao_Paulo")
    date_format: Mapped[str] = mapped_column(String(40), nullable=False, default="YYYY-MM-DD")
    money_format: Mapped[str] = mapped_column(String(40), nullable=False, default="BRL")
    allow_manual_entries: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_imports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("cnpj", name="uq_companies_cnpj"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_created_at", "created_at"),
        Index("ix_companies_updated_at", "updated_at"),
    )
