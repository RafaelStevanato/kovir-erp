from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.participants.models import (
    ParticipantOrigin,
    ParticipantStatus,
    ParticipantType,
    PersonType,
    TaxpayerType,
)


# ─── Helpers de limpeza ────────────────────────────────────────────────────────

def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _required_text(value: str | None, field_label: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise ValueError(f"{field_label} é obrigatório.")
    return cleaned


def _normalize_uf(value: str | None) -> str:
    cleaned = _required_text(value, "UF")
    normalized = cleaned.upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("UF deve conter exatamente 2 letras.")
    return normalized


def _normalize_country(value: str | None) -> str:
    cleaned = _clean_text(value) or "BR"
    normalized = cleaned.upper()
    if len(normalized) != 2 or not normalized.isalpha():
        raise ValueError("País deve conter exatamente 2 letras.")
    return normalized


def _only_digits_or_none(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    normalized = "".join(char for char in cleaned if char.isdigit())
    return normalized if normalized else None



def _normalize_document(value: str | None, required: bool = False) -> str | None:
    """Normaliza CPF/CNPJ removendo pontuação e valida dígitos verificadores."""
    cleaned = _clean_text(value)

    if cleaned is None:
        if required:
            raise ValueError("Documento do participante é obrigatório.")
        return None

    normalized = (
        cleaned.replace(".", "")
        .replace("/", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )

    if not normalized.isalnum():
        raise ValueError("Documento deve conter apenas letras e números.")

    if len(normalized) not in (11, 14):
        raise ValueError("Documento deve conter 11 dígitos (CPF) ou 14 (CNPJ/passaporte).")

    return normalized


# ─── Sub-schemas ──────────────────────────────────────────────────────────────

class ParticipantAddressSchema(BaseModel):
    street: str = Field(min_length=2, max_length=120)
    number: str = Field(min_length=1, max_length=20)
    complement: str | None = Field(default=None, max_length=80)
    district: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=2)
    zip_code: str = Field(min_length=8, max_length=8)
    country: str = Field(default="BR", min_length=2, max_length=2)
    ibge_municipality_code: str | None = Field(default=None, min_length=7, max_length=7)

    @field_validator("street", "number", "district", "city")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _required_text(value, "Campo de endereço")

    @field_validator("complement", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, value: str | None) -> str:
        return _normalize_uf(value)

    @field_validator("country", mode="before")
    @classmethod
    def validate_country(cls, value: str | None) -> str:
        return _normalize_country(value)

    @field_validator("zip_code", mode="before")
    @classmethod
    def validate_zip_code(cls, value: str | None) -> str:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            raise ValueError("CEP é obrigatório.")
        if len(normalized) != 8:
            raise ValueError("CEP deve conter 8 dígitos.")
        return normalized

    @field_validator("ibge_municipality_code", mode="before")
    @classmethod
    def validate_ibge_municipality_code(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) != 7:
            raise ValueError("Código IBGE deve conter 7 dígitos.")
        return normalized


class ParticipantFiscalSettingsSchema(BaseModel):
    taxpayer_type: TaxpayerType = TaxpayerType.UNKNOWN
    # tax_regime aceita string livre para compatibilidade com dados históricos;
    # o frontend deve usar o vocabulário controlado (TaxRegime) via select.
    tax_regime: str | None = Field(default=None, max_length=80)
    main_cnae: str | None = Field(default=None, min_length=7, max_length=7)
    state_registration: str | None = Field(default=None, max_length=30)
    municipal_registration: str | None = Field(default=None, max_length=30)
    suframa_registration: str | None = Field(default=None, max_length=30)
    is_foreign: bool = False
    fiscal_notes: str | None = Field(default=None, max_length=500)

    @field_validator("tax_regime", mode="before")
    @classmethod
    def clean_tax_regime(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("main_cnae", mode="before")
    @classmethod
    def validate_main_cnae(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) != 7:
            raise ValueError("CNAE principal deve conter 7 dígitos.")
        return normalized

    @field_validator(
        "state_registration",
        "municipal_registration",
        "suframa_registration",
        "fiscal_notes",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class ParticipantFinancialSettingsSchema(BaseModel):
    # Método e prazo agora opcionais — muitos participantes são cadastrados
    # antes de negociar condições financeiras formais.
    default_payment_method: str | None = Field(default=None, max_length=60)
    default_payment_terms: str | None = Field(default=None, max_length=80)
    bank_name: str | None = Field(default=None, max_length=80)
    bank_branch: str | None = Field(default=None, max_length=30)
    bank_account: str | None = Field(default=None, max_length=40)
    pix_key: str | None = Field(default=None, max_length=120)
    credit_limit: str | None = Field(default=None, max_length=30)
    payment_priority: str | None = Field(default=None, max_length=30)

    @field_validator(
        "default_payment_method",
        "default_payment_terms",
        "bank_name",
        "bank_branch",
        "bank_account",
        "pix_key",
        "credit_limit",
        "payment_priority",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


# ─── Create ───────────────────────────────────────────────────────────────────

class ParticipantCreate(BaseModel):
    company_id: str = Field(min_length=1)
    participant_type: ParticipantType
    person_type: PersonType
    name: str = Field(min_length=2, max_length=160)
    trade_name: str | None = Field(default=None, max_length=160)

    # Documento opcional: aceita CPF (11), CNPJ (14) ou doc estrangeiro alfanum.
    # Quando fornecido, CPF e CNPJ têm dígitos verificadores validados.
    document: str | None = Field(default=None)

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    secondary_phone: str | None = Field(default=None, max_length=50)

    # Contato operacional — pessoa de contato no dia-a-dia (PJ) ou dados extras (PF)
    website: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    contact_email: EmailStr | None = None

    # Origem e segmentação
    origin: ParticipantOrigin | None = None
    tags: list[str] = Field(default_factory=list)

    status: ParticipantStatus = ParticipantStatus.ACTIVE
    address: ParticipantAddressSchema | None = None
    fiscal_settings: ParticipantFiscalSettingsSchema | None = None
    financial_settings: ParticipantFinancialSettingsSchema | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id")
    @classmethod
    def validate_company_id_text(cls, value: str) -> str:
        return _required_text(value, "ID da empresa")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _required_text(value, "Nome/Razão social do participante")

    @field_validator("trade_name", "notes", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("document", mode="before")
    @classmethod
    def validate_document(cls, value: str | None) -> str | None:
        return _normalize_document(value, required=False)

    @field_validator("phone", "secondary_phone", mode="before")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) < 8:
            raise ValueError("Telefone deve conter pelo menos 8 dígitos.")
        return normalized

    @field_validator("contact_phone", mode="before")
    @classmethod
    def validate_contact_phone(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) < 8:
            raise ValueError("Telefone de contato deve conter pelo menos 8 dígitos.")
        return normalized

    @field_validator("website", "contact_name", mode="before")
    @classmethod
    def clean_contact_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, value: list | None) -> list[str]:
        if not value:
            return []
        return [tag.strip() for tag in value if isinstance(tag, str) and tag.strip()]


# ─── Update ───────────────────────────────────────────────────────────────────

class ParticipantUpdate(BaseModel):
    company_id: str | None = Field(default=None, min_length=1)
    participant_type: ParticipantType | None = None
    person_type: PersonType | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    trade_name: str | None = Field(default=None, max_length=160)
    document: str | None = Field(default=None)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    secondary_phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    contact_email: EmailStr | None = None
    origin: ParticipantOrigin | None = None
    tags: list[str] | None = None
    status: ParticipantStatus | None = None
    address: ParticipantAddressSchema | None = None
    fiscal_settings: ParticipantFiscalSettingsSchema | None = None
    financial_settings: ParticipantFinancialSettingsSchema | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id", mode="before")
    @classmethod
    def clean_company_id(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("trade_name", "notes", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("document", mode="before")
    @classmethod
    def validate_document(cls, value: str | None) -> str | None:
        return _normalize_document(value, required=False)

    @field_validator("phone", "secondary_phone", mode="before")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) < 8:
            raise ValueError("Telefone deve conter pelo menos 8 dígitos.")
        return normalized

    @field_validator("contact_phone", mode="before")
    @classmethod
    def validate_contact_phone(cls, value: str | None) -> str | None:
        normalized = _only_digits_or_none(value)
        if normalized is None:
            return None
        if len(normalized) < 8:
            raise ValueError("Telefone de contato deve conter pelo menos 8 dígitos.")
        return normalized

    @field_validator("website", "contact_name", mode="before")
    @classmethod
    def clean_contact_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, value: list | None) -> list[str] | None:
        if value is None:
            return None
        return [tag.strip() for tag in value if isinstance(tag, str) and tag.strip()]


# ─── Response ─────────────────────────────────────────────────────────────────

class ParticipantResponse(BaseModel):
    id: str
    company_id: str
    participant_type: ParticipantType
    person_type: PersonType
    name: str
    trade_name: str | None = None
    document: str | None = None
    email: str | None = None
    phone: str | None = None
    secondary_phone: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    origin: str | None = None
    tags: list[str] | None = None
    status: ParticipantStatus
    address: ParticipantAddressSchema | None = None
    fiscal_settings: ParticipantFiscalSettingsSchema | None = None
    financial_settings: ParticipantFinancialSettingsSchema | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
