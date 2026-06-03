from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ParticipantType(str, Enum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    CARRIER = "carrier"
    SERVICE_PROVIDER = "service_provider"
    MARKETPLACE = "marketplace"
    GATEWAY = "gateway"
    BANK = "bank"
    OTHER = "other"


class PersonType(str, Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"


class ParticipantStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class TaxpayerType(str, Enum):
    TAXPAYER = "taxpayer"
    NON_TAXPAYER = "non_taxpayer"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"


class TaxRegime(str, Enum):
    SIMPLES_NACIONAL = "simples_nacional"
    MEI = "mei"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"
    LUCRO_ARBITRADO = "lucro_arbitrado"
    IMUNE = "imune"
    ISENTO = "isento"
    NAO_CONTRIBUINTE = "nao_contribuinte"
    NAO_SE_APLICA = "nao_se_aplica"


class ParticipantOrigin(str, Enum):
    DIRECT = "direct"
    MARKETPLACE = "marketplace"
    REFERRAL = "referral"
    IMPORT = "import"
    ORGANIC = "organic"
    MANUAL = "manual"
    OTHER = "other"


@dataclass
class ParticipantAddress:
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    district: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "BR"
    ibge_municipality_code: str | None = None


@dataclass
class ParticipantFiscalSettings:
    taxpayer_type: TaxpayerType = TaxpayerType.UNKNOWN
    tax_regime: str | None = None
    main_cnae: str | None = None
    state_registration: str | None = None
    municipal_registration: str | None = None
    suframa_registration: str | None = None
    is_foreign: bool = False
    fiscal_notes: str | None = None


@dataclass
class ParticipantFinancialSettings:
    default_payment_method: str | None = None
    default_payment_terms: str | None = None
    bank_name: str | None = None
    bank_branch: str | None = None
    bank_account: str | None = None
    pix_key: str | None = None
    credit_limit: str | None = None
    payment_priority: str | None = None


@dataclass
class Participant:
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
    status: ParticipantStatus = ParticipantStatus.ACTIVE
    address: ParticipantAddress | None = None
    fiscal_settings: ParticipantFiscalSettings | None = None
    financial_settings: ParticipantFinancialSettings | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if is_dataclass(value):
        return {
            key: _serialize_value(item_value)
            for key, item_value in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            key: _serialize_value(item_value)
            for key, item_value in value.items()
        }

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    return value


def participant_to_dict(participant: Participant) -> dict[str, Any]:
    return _serialize_value(participant)