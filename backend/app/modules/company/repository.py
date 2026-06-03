from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.secrets import decrypt_secret, encrypt_secret
from app.modules.company.db_models import CompanyDB
from app.modules.company.models import (
    Company,
    CompanyAddress,
    CompanyFinancialSettings,
    CompanyFiscalSettings,
    CompanyOperationalSettings,
    CompanyStatus,
    FiscalEnvironment,
    TaxRegime,
)


def company_db_to_domain(company: CompanyDB) -> Company:
    return Company(
        id=company.id,
        legal_name=company.legal_name,
        trade_name=company.trade_name,
        cnpj=company.cnpj,
        email=company.email,
        phone=company.phone,
        responsible_name=company.responsible_name,
        status=CompanyStatus(company.status),
        address=CompanyAddress(
            street=company.address_street,
            number=company.address_number,
            complement=company.address_complement,
            district=company.address_district,
            city=company.address_city,
            state=company.address_state,
            zip_code=company.address_zip_code,
            ibge_municipality_code=company.address_ibge_municipality_code,
        ),
        fiscal_settings=CompanyFiscalSettings(
            tax_regime=TaxRegime(company.tax_regime),
            main_cnae=company.main_cnae,
            state_registration=company.state_registration,
            municipal_registration=company.municipal_registration,
            fiscal_environment=FiscalEnvironment(company.fiscal_environment),
            uses_fiscal_control=company.uses_fiscal_control,
            prepared_for_tax_reform=company.prepared_for_tax_reform,
            crt=company.crt,
            nfe_serie=company.nfe_serie,
            nfce_serie=company.nfce_serie,
            focus_nfe_token=decrypt_secret(company.focus_nfe_token),
        ),
        financial_settings=CompanyFinancialSettings(
            currency=company.currency,
            monthly_closing_day=company.monthly_closing_day,
            uses_accounts_receivable=company.uses_accounts_receivable,
            uses_accounts_payable=company.uses_accounts_payable,
            uses_cash_control=company.uses_cash_control,
            uses_cost_center=company.uses_cost_center,
            uses_chart_of_accounts=company.uses_chart_of_accounts,
        ),
        operational_settings=CompanyOperationalSettings(
            timezone=company.timezone,
            date_format=company.date_format,
            money_format=company.money_format,
            allow_manual_entries=company.allow_manual_entries,
            allow_imports=company.allow_imports,
        ),
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


def _apply_domain_to_db(company_db: CompanyDB, company: Company) -> None:
    company_db.legal_name = company.legal_name
    company_db.trade_name = company.trade_name
    company_db.cnpj = company.cnpj
    company_db.email = company.email
    company_db.phone = company.phone
    company_db.responsible_name = company.responsible_name
    company_db.status = company.status.value

    company_db.address_street = company.address.street
    company_db.address_number = company.address.number
    company_db.address_complement = company.address.complement
    company_db.address_district = company.address.district
    company_db.address_city = company.address.city
    company_db.address_state = company.address.state
    company_db.address_zip_code = company.address.zip_code
    company_db.address_ibge_municipality_code = company.address.ibge_municipality_code

    company_db.tax_regime = company.fiscal_settings.tax_regime.value
    company_db.main_cnae = company.fiscal_settings.main_cnae
    company_db.state_registration = company.fiscal_settings.state_registration
    company_db.municipal_registration = company.fiscal_settings.municipal_registration
    company_db.fiscal_environment = company.fiscal_settings.fiscal_environment.value
    company_db.uses_fiscal_control = company.fiscal_settings.uses_fiscal_control
    company_db.prepared_for_tax_reform = company.fiscal_settings.prepared_for_tax_reform
    company_db.crt = company.fiscal_settings.crt
    company_db.nfe_serie = company.fiscal_settings.nfe_serie
    company_db.nfce_serie = company.fiscal_settings.nfce_serie
    if company.fiscal_settings.focus_nfe_token is not None:
        company_db.focus_nfe_token = encrypt_secret(company.fiscal_settings.focus_nfe_token)

    company_db.currency = company.financial_settings.currency
    company_db.monthly_closing_day = company.financial_settings.monthly_closing_day
    company_db.uses_accounts_receivable = company.financial_settings.uses_accounts_receivable
    company_db.uses_accounts_payable = company.financial_settings.uses_accounts_payable
    company_db.uses_cash_control = company.financial_settings.uses_cash_control
    company_db.uses_cost_center = company.financial_settings.uses_cost_center
    company_db.uses_chart_of_accounts = company.financial_settings.uses_chart_of_accounts

    company_db.timezone = company.operational_settings.timezone
    company_db.date_format = company.operational_settings.date_format
    company_db.money_format = company.operational_settings.money_format
    company_db.allow_manual_entries = company.operational_settings.allow_manual_entries
    company_db.allow_imports = company.operational_settings.allow_imports

    company_db.created_at = company.created_at
    company_db.updated_at = company.updated_at


def create_company(db: Session, company: Company) -> CompanyDB:
    company_db = CompanyDB(id=company.id)
    _apply_domain_to_db(company_db, company)
    db.add(company_db)
    db.flush()
    return company_db


def update_company(db: Session, company_db: CompanyDB, company: Company) -> CompanyDB:
    _apply_domain_to_db(company_db, company)
    db.add(company_db)
    db.flush()
    return company_db


def list_companies(db: Session, limit: int = 50, offset: int = 0) -> list[CompanyDB]:
    statement: Select[tuple[CompanyDB]] = (
        select(CompanyDB)
        .where(CompanyDB.deleted_at.is_(None))
        .order_by(CompanyDB.created_at.desc(), CompanyDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def get_company(db: Session, company_id: str) -> CompanyDB | None:
    statement = select(CompanyDB).where(
        CompanyDB.id == company_id,
        CompanyDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_company_by_cnpj(db: Session, cnpj: str) -> CompanyDB | None:
    statement = select(CompanyDB).where(
        CompanyDB.cnpj == cnpj,
        CompanyDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def count_companies(db: Session) -> int:
    statement = select(func.count()).select_from(CompanyDB).where(
        CompanyDB.deleted_at.is_(None),
    )

    return int(db.scalar(statement) or 0)
