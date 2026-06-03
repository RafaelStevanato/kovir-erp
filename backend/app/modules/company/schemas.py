from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.company.models import (
    CompanyStatus,
    FiscalEnvironment,
    TaxRegime,
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    if cleaned == "":
        return None

    return cleaned


def _normalize_document(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = (
        value.strip()
        .replace(".", "")
        .replace("/", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )

    if cleaned == "":
        return None

    if not cleaned.isdigit():
        raise ValueError("CNPJ deve conter apenas números.")

    if len(cleaned) != 14:
        raise ValueError("CNPJ deve conter 14 dígitos.")

    return cleaned


def _normalize_uf(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip().upper()

    if cleaned == "":
        return None

    if len(cleaned) != 2 or not cleaned.isalpha():
        raise ValueError("UF deve conter exatamente 2 letras.")

    return cleaned


class CompanyAddressSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    street: str | None = None
    number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    ibge_municipality_code: str | None = None

    @field_validator(
        "street",
        "number",
        "complement",
        "district",
        "city",
        "zip_code",
        "ibge_municipality_code",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("state", mode="before")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return _normalize_uf(value)


class CompanyFiscalSettingsSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    tax_regime: TaxRegime = TaxRegime.UNKNOWN
    main_cnae: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    fiscal_environment: FiscalEnvironment = FiscalEnvironment.NONE
    uses_fiscal_control: bool = False
    prepared_for_tax_reform: bool = True
    crt: str | None = None
    nfe_serie: str = Field(default="1", min_length=1, max_length=3)
    nfce_serie: str = Field(default="1", min_length=1, max_length=3)
    focus_nfe_token: str | None = Field(default=None, max_length=255)

    @field_validator(
        "main_cnae",
        "state_registration",
        "municipal_registration",
        "focus_nfe_token",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("crt", mode="before")
    @classmethod
    def normalize_crt(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        if cleaned is None:
            return None
        if cleaned not in {"1", "2", "3"}:
            raise ValueError("CRT deve ser 1, 2 ou 3.")
        return cleaned

    @field_validator("nfe_serie", "nfce_serie", mode="before")
    @classmethod
    def normalize_fiscal_series(cls, value: str | None) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            return "1"
        if not cleaned.isdigit():
            raise ValueError("Série fiscal deve conter apenas números.")
        return cleaned


class CompanyFinancialSettingsSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    currency: str = "BRL"
    monthly_closing_day: int = Field(default=31, ge=1, le=31)
    uses_accounts_receivable: bool = True
    uses_accounts_payable: bool = True
    uses_cash_control: bool = True
    uses_cost_center: bool = False
    uses_chart_of_accounts: bool = False

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str:
        if value is None:
            return "BRL"

        cleaned = value.strip().upper()

        if cleaned == "":
            return "BRL"

        if len(cleaned) != 3:
            raise ValueError("Moeda deve usar código ISO de 3 letras, exemplo: BRL.")

        return cleaned


class CompanyOperationalSettingsSchema(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    timezone: str = "America/Sao_Paulo"
    date_format: str = "YYYY-MM-DD"
    money_format: str = "BRL"
    allow_manual_entries: bool = True
    allow_imports: bool = True

    @field_validator("timezone", "date_format", "money_format", mode="before")
    @classmethod
    def clean_required_text(cls, value: str | None) -> str:
        cleaned = _clean_text(value)

        if cleaned is None:
            raise ValueError("Campo obrigatório não pode ser vazio.")

        return cleaned


class CompanyCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    legal_name: str = Field(min_length=2, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    cnpj: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    responsible_name: str | None = Field(default=None, max_length=255)
    status: CompanyStatus = CompanyStatus.ACTIVE

    address: CompanyAddressSchema = Field(default_factory=CompanyAddressSchema)
    fiscal_settings: CompanyFiscalSettingsSchema = Field(
        default_factory=CompanyFiscalSettingsSchema
    )
    financial_settings: CompanyFinancialSettingsSchema = Field(
        default_factory=CompanyFinancialSettingsSchema
    )
    operational_settings: CompanyOperationalSettingsSchema = Field(
        default_factory=CompanyOperationalSettingsSchema
    )

    @field_validator("legal_name", mode="before")
    @classmethod
    def clean_legal_name(cls, value: str) -> str:
        cleaned = _clean_text(value)

        if cleaned is None:
            raise ValueError("Razão social é obrigatória.")

        return cleaned

    @field_validator("trade_name", "email", "phone", "responsible_name", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("cnpj", mode="before")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        return _normalize_document(value)


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    legal_name: str | None = Field(default=None, min_length=2, max_length=255)
    trade_name: str | None = Field(default=None, max_length=255)
    cnpj: str | None = None
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    responsible_name: str | None = Field(default=None, max_length=255)
    status: CompanyStatus | None = None

    address: CompanyAddressSchema | None = None
    fiscal_settings: CompanyFiscalSettingsSchema | None = None
    financial_settings: CompanyFinancialSettingsSchema | None = None
    operational_settings: CompanyOperationalSettingsSchema | None = None

    @field_validator("legal_name", "trade_name", "email", "phone", "responsible_name", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("cnpj", mode="before")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        return _normalize_document(value)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    legal_name: str
    trade_name: str | None = None
    cnpj: str | None = None
    email: str | None = None
    phone: str | None = None
    responsible_name: str | None = None
    status: CompanyStatus

    address: CompanyAddressSchema
    fiscal_settings: CompanyFiscalSettingsSchema
    financial_settings: CompanyFinancialSettingsSchema
    operational_settings: CompanyOperationalSettingsSchema

    created_at: str | None = None
    updated_at: str | None = None
