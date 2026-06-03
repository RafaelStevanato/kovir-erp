from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class FiscalRecordStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    EXPIRED = "expired"


class FiscalProfileType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    OPERATION = "operation"
    MIXED = "mixed"


class FiscalAppliesTo(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    BOTH = "both"
    OPERATION = "operation"


class TaxRegimeScope(str, Enum):
    SIMPLES_NACIONAL = "simples_nacional"
    LUCRO_PRESUMIDO = "lucro_presumido"
    LUCRO_REAL = "lucro_real"
    MEI = "mei"
    PRODUCER = "producer"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class FiscalSourceType(str, Enum):
    MANUAL = "manual"
    ACCOUNTANT = "accountant"
    OFFICIAL_RULE = "official_rule"
    IMPORTED_TABLE = "imported_table"
    INTEGRATION = "integration"
    LEGACY = "legacy"
    UNKNOWN = "unknown"


class FiscalAuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"


@dataclass
class FiscalAuditEvent:
    id: str
    entity_id: str
    entity_type: str
    action: FiscalAuditAction
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    changes: dict[str, Any]
    source: str
    request_id: str | None
    correlation_id: str | None
    occurred_at: datetime


@dataclass
class FiscalProfile:
    id: str
    company_id: str
    name: str
    description: str | None
    profile_type: FiscalProfileType
    applies_to: FiscalAppliesTo
    tax_regime: TaxRegimeScope
    status: FiscalRecordStatus
    valid_from: date | None
    valid_to: date | None
    source: FiscalSourceType
    source_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class FiscalClassification:
    id: str
    company_id: str
    fiscal_profile_id: str | None
    name: str
    description: str | None
    item_type: FiscalAppliesTo
    tax_regime: TaxRegimeScope
    ncm: str | None
    nbs: str | None
    cest: str | None
    ex_tipi: str | None
    origem_mercadoria: str | None
    cfop_default: str | None
    cst_icms: str | None
    cst_pis: str | None
    cst_cofins: str | None
    cst_ibs_cbs: str | None
    cclass_trib: str | None
    subject_to_icms: bool
    subject_to_iss: bool
    subject_to_pis_cofins: bool
    subject_to_ibs_cbs: bool
    subject_to_is: bool
    valid_from: date | None
    valid_to: date | None
    status: FiscalRecordStatus
    source: FiscalSourceType
    source_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if is_dataclass(value):
        return {key: _serialize_value(item) for key, item in asdict(value).items()}

    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    return value


def fiscal_profile_to_dict(profile: FiscalProfile) -> dict[str, Any]:
    return _serialize_value(profile)


def fiscal_classification_to_dict(
    classification: FiscalClassification,
) -> dict[str, Any]:
    return _serialize_value(classification)


def fiscal_audit_event_to_dict(event: FiscalAuditEvent) -> dict[str, Any]:
    return _serialize_value(event)
