from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CompanyStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class TaxRegime(str, Enum):
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"
    MEI = "mei"
    UNKNOWN = "unknown"


class FiscalEnvironment(str, Enum):
    PRODUCTION = "production"
    HOMOLOGATION = "homologation"
    NONE = "none"


@dataclass
class CompanyAddress:
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    ibge_municipality_code: str | None = None


@dataclass
class CompanyFiscalSettings:
    tax_regime: TaxRegime = TaxRegime.UNKNOWN
    main_cnae: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    fiscal_environment: FiscalEnvironment = FiscalEnvironment.NONE
    uses_fiscal_control: bool = False
    prepared_for_tax_reform: bool = True
    crt: str | None = None
    nfe_serie: str = "1"
    nfce_serie: str = "1"
    focus_nfe_token: str | None = None


@dataclass
class CompanyFinancialSettings:
    currency: str = "BRL"
    monthly_closing_day: int = 31
    uses_accounts_receivable: bool = True
    uses_accounts_payable: bool = True
    uses_cash_control: bool = True
    uses_cost_center: bool = False
    uses_chart_of_accounts: bool = False


@dataclass
class CompanyOperationalSettings:
    timezone: str = "America/Sao_Paulo"
    date_format: str = "YYYY-MM-DD"
    money_format: str = "BRL"
    allow_manual_entries: bool = True
    allow_imports: bool = True


@dataclass
class Company:
    id: str
    legal_name: str
    trade_name: str | None = None
    cnpj: str | None = None
    email: str | None = None
    phone: str | None = None
    responsible_name: str | None = None
    status: CompanyStatus = CompanyStatus.DRAFT

    address: CompanyAddress = field(default_factory=CompanyAddress)
    fiscal_settings: CompanyFiscalSettings = field(default_factory=CompanyFiscalSettings)
    financial_settings: CompanyFinancialSettings = field(default_factory=CompanyFinancialSettings)
    operational_settings: CompanyOperationalSettings = field(default_factory=CompanyOperationalSettings)

    created_at: datetime | None = None
    updated_at: datetime | None = None


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: _serialize_value(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
        }

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {
            key: _serialize_value(item)
            for key, item in value.items()
        }

    return value


def company_to_dict(company: Company) -> dict[str, Any]:
    data = _serialize_value(company)
    fiscal_settings = data.get("fiscal_settings")
    if isinstance(fiscal_settings, dict):
        token = fiscal_settings.get("focus_nfe_token")
        fiscal_settings["focus_nfe_token_configured"] = bool(token)
        fiscal_settings["focus_nfe_token"] = None
    return data
