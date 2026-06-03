from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.shared.datetime import utc_now
from app.shared.ids import generate_id, assert_valid_id


class AuditEventType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    SOFT_DELETED = "soft_deleted"
    RESTORED = "restored"
    CANCELLED = "cancelled"
    IMPORTED = "imported"
    EXPORTED = "exported"
    CALCULATED = "calculated"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUS_CHANGED = "status_changed"
    LOGIN = "login"
    LOGOUT = "logout"
    SYSTEM_EVENT = "system_event"


class AuditSource(str, Enum):
    API = "api"
    WEB = "web"
    SYSTEM = "system"
    IMPORT = "import"
    INTEGRATION = "integration"
    SCRIPT = "script"
    TEST = "test"


class AuditEntityType(str, Enum):
    COMPANY = "company"
    PARTICIPANT = "participant"
    ITEM = "item"
    SALE = "sale"
    PURCHASE = "purchase"
    ACCOUNT_RECEIVABLE = "account_receivable"
    ACCOUNT_PAYABLE = "account_payable"
    CASH_MOVEMENT = "cash_movement"
    FISCAL_DOCUMENT = "fiscal_document"
    TAX_CALCULATION = "tax_calculation"
    USER = "user"
    AUDIT = "audit"
    SYSTEM = "system"
    UNKNOWN = "unknown"
    CATALOG_ITEM = "catalog_item"
    FISCAL_PROFILE = "fiscal_profile"
    FISCAL_CLASSIFICATION = "fiscal_classification"
    MARKETPLACE_ACCOUNT = "marketplace_account"
    MERCADO_PAGO_ACCOUNT = "mercado_pago_account"
    STOCK_LOCATION = "stock_location"
    STOCK_MOVEMENT = "stock_movement"
    STOCK_PURCHASE_ENTRY = "stock_purchase_entry"
    FINANCIAL_ACCOUNT = "financial_account"
    FINANCIAL_CATEGORY = "financial_category"
    COST_CENTER = "cost_center"
    CHART_ACCOUNT = "chart_account"
    PAYMENT_TERM = "payment_term"
    RECONCILIATION_IMPORT = "reconciliation_import"
    RECONCILIATION_LINE = "reconciliation_line"
    RECONCILIATION_MATCH = "reconciliation_match"


ENTITY_PREFIX_MAP = {
    AuditEntityType.COMPANY: "emp",
    AuditEntityType.PARTICIPANT: "part",
    AuditEntityType.ITEM: "item",
    AuditEntityType.CATALOG_ITEM: "item",
    AuditEntityType.FISCAL_PROFILE: "fprof",
    AuditEntityType.FISCAL_CLASSIFICATION: "fclass",
    AuditEntityType.MARKETPLACE_ACCOUNT: "mkacc",
    AuditEntityType.MERCADO_PAGO_ACCOUNT: "mpacc",
    AuditEntityType.STOCK_LOCATION: "loc",
    AuditEntityType.STOCK_MOVEMENT: "stmov",
    AuditEntityType.STOCK_PURCHASE_ENTRY: "stpin",
    AuditEntityType.FINANCIAL_ACCOUNT: "bankacc",
    AuditEntityType.FINANCIAL_CATEGORY: "cat",
    AuditEntityType.COST_CENTER: "cc",
    AuditEntityType.CHART_ACCOUNT: "acc",
    AuditEntityType.PAYMENT_TERM: "term",
    AuditEntityType.RECONCILIATION_IMPORT: "stmtimp",
    AuditEntityType.RECONCILIATION_LINE: "stmtln",
    AuditEntityType.RECONCILIATION_MATCH: "recmatch",
    AuditEntityType.SALE: "sale",
    AuditEntityType.PURCHASE: "buy",
    AuditEntityType.ACCOUNT_RECEIVABLE: "ar",
    AuditEntityType.ACCOUNT_PAYABLE: "ap",
    AuditEntityType.CASH_MOVEMENT: "cash",
    AuditEntityType.FISCAL_DOCUMENT: "doc",
    AuditEntityType.TAX_CALCULATION: "tax",
    AuditEntityType.USER: "user",
    AuditEntityType.AUDIT: "audit",
}


ENTITY_ID_REQUIRED_EVENTS = {
    AuditEventType.CREATED,
    AuditEventType.UPDATED,
    AuditEventType.DELETED,
    AuditEventType.SOFT_DELETED,
    AuditEventType.RESTORED,
    AuditEventType.CANCELLED,
    AuditEventType.CALCULATED,
    AuditEventType.VALIDATED,
    AuditEventType.APPROVED,
    AuditEventType.REJECTED,
    AuditEventType.STATUS_CHANGED,
}


SENSITIVE_FIELD_PATTERNS = {
    "password",
    "senha",
    "token",
    "accesstoken",
    "refreshtoken",
    "secret",
    "apikey",
    "authorization",
    "cookie",
    "cpf",
    "cnpj",
    "taxid",
    "document",
    "docnumber",
    "pixkey",
    "chavepix",
    "bankaccount",
    "accountnumber",
    "agency",
    "agencia",
    "branch",
    "routing",
    "iban",
    "swift",
    "cardnumber",
    "cardtoken",
    "cvv",
    "securitycode",
}


@dataclass(frozen=True)
class AuditContext:
    actor_id: str | None = None
    source: AuditSource = AuditSource.SYSTEM
    request_id: str | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    id: str
    event_type: AuditEventType
    entity_type: AuditEntityType
    entity_id: str | None
    occurred_at: datetime
    actor_id: str | None
    source: AuditSource
    request_id: str | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_sensitive_key(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


def is_sensitive_key(key: str) -> bool:
    normalized_key = normalize_sensitive_key(key)

    return any(
        sensitive_pattern in normalized_key
        for sensitive_pattern in SENSITIVE_FIELD_PATTERNS
    )


def mask_sensitive_fields(data: Any) -> Any:
    if data is None:
        return None

    if isinstance(data, dict):
        masked: dict[str, Any] = {}

        for key, value in data.items():
            key_as_text = str(key)

            if is_sensitive_key(key_as_text):
                if isinstance(value, dict):
                    masked[key] = mask_sensitive_fields(value)
                elif isinstance(value, list):
                    masked[key] = [
                        mask_sensitive_fields(item)
                        if isinstance(item, dict | list | tuple)
                        else "***MASKED***"
                        for item in value
                    ]
                elif isinstance(value, tuple):
                    masked[key] = tuple(
                        mask_sensitive_fields(item)
                        if isinstance(item, dict | list | tuple)
                        else "***MASKED***"
                        for item in value
                    )
                else:
                    masked[key] = "***MASKED***"
            else:
                masked[key] = mask_sensitive_fields(value)

        return masked

    if isinstance(data, list):
        return [mask_sensitive_fields(item) for item in data]

    if isinstance(data, tuple):
        return tuple(mask_sensitive_fields(item) for item in data)

    return data


def diff_dicts(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    ignored_fields: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    ignored_fields = ignored_fields or set()

    before = before or {}
    after = after or {}

    changes: dict[str, dict[str, Any]] = {}

    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        if key in ignored_fields:
            continue

        old_value = before.get(key)
        new_value = after.get(key)

        if old_value != new_value:
            changes[key] = {
                "before": old_value,
                "after": new_value,
            }

    return changes


def get_expected_prefix_for_entity(entity_type: AuditEntityType) -> str | None:
    return ENTITY_PREFIX_MAP.get(entity_type)


def assert_valid_audit_context(context: AuditContext) -> None:
    if context.actor_id is not None:
        assert_valid_id(context.actor_id, "user")


def assert_valid_audit_entity_reference(
    event_type: AuditEventType,
    entity_type: AuditEntityType,
    entity_id: str | None,
    expected_entity_prefix: str | None = None,
) -> None:
    if event_type in ENTITY_ID_REQUIRED_EVENTS and entity_id is None:
        raise ValueError(
            f"entity_id é obrigatório para eventos do tipo '{event_type.value}'."
        )

    if entity_id is None:
        return

    resolved_prefix = expected_entity_prefix or get_expected_prefix_for_entity(entity_type)

    if resolved_prefix is not None:
        assert_valid_id(entity_id, resolved_prefix)
    else:
        assert_valid_id(entity_id)


def build_audit_event(
    event_type: AuditEventType,
    entity_type: AuditEntityType,
    entity_id: str | None,
    context: AuditContext,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    expected_entity_prefix: str | None = None,
) -> AuditEvent:
    assert_valid_audit_context(context)

    assert_valid_audit_entity_reference(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        expected_entity_prefix=expected_entity_prefix,
    )

    safe_before = mask_sensitive_fields(before)
    safe_after = mask_sensitive_fields(after)

    changes = diff_dicts(
        safe_before,
        safe_after,
        ignored_fields={"updated_at", "atualizado_em"},
    )

    safe_metadata = mask_sensitive_fields(metadata or {})

    return AuditEvent(
        id=generate_id("audit"),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        occurred_at=utc_now(),
        actor_id=context.actor_id,
        source=context.source,
        request_id=context.request_id,
        correlation_id=context.correlation_id,
        ip_address=context.ip_address,
        user_agent=context.user_agent,
        before=safe_before,
        after=safe_after,
        changes=changes,
        metadata=safe_metadata,
    )


def build_created_event(
    entity_type: AuditEntityType,
    entity_id: str,
    context: AuditContext,
    after: dict[str, Any],
    expected_entity_prefix: str | None = None,
) -> AuditEvent:
    return build_audit_event(
        event_type=AuditEventType.CREATED,
        entity_type=entity_type,
        entity_id=entity_id,
        context=context,
        before=None,
        after=after,
        expected_entity_prefix=expected_entity_prefix,
    )


def build_updated_event(
    entity_type: AuditEntityType,
    entity_id: str,
    context: AuditContext,
    before: dict[str, Any],
    after: dict[str, Any],
    expected_entity_prefix: str | None = None,
) -> AuditEvent:
    return build_audit_event(
        event_type=AuditEventType.UPDATED,
        entity_type=entity_type,
        entity_id=entity_id,
        context=context,
        before=before,
        after=after,
        expected_entity_prefix=expected_entity_prefix,
    )


def build_status_changed_event(
    entity_type: AuditEntityType,
    entity_id: str,
    context: AuditContext,
    old_status: str,
    new_status: str,
    expected_entity_prefix: str | None = None,
) -> AuditEvent:
    return build_audit_event(
        event_type=AuditEventType.STATUS_CHANGED,
        entity_type=entity_type,
        entity_id=entity_id,
        context=context,
        before={"status": old_status},
        after={"status": new_status},
        metadata={
            "old_status": old_status,
            "new_status": new_status,
        },
        expected_entity_prefix=expected_entity_prefix,
    )


def serialize_audit_event(event: AuditEvent) -> dict[str, Any]:
    data = asdict(event)

    data["event_type"] = event.event_type.value
    data["entity_type"] = event.entity_type.value
    data["source"] = event.source.value
    data["occurred_at"] = event.occurred_at.isoformat()

    return data
