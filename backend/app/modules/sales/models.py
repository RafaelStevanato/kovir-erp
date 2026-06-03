from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class SaleStatus(str, Enum):
    QUOTE = "quote"
    CLOSED = "closed"
    PAID = "paid"
    CANCELLED = "cancelled"


class SaleType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"


class SaleOrigin(str, Enum):
    MANUAL = "manual"
    IMPORTED = "imported"
    INTEGRATION = "integration"
    MARKETPLACE = "marketplace"
    PDV = "pdv"
    UNKNOWN = "unknown"


class SaleOperationNature(str, Enum):
    NORMAL_SALE = "normal_sale"
    BONUS = "bonus"
    SAMPLE = "sample"
    EXCHANGE = "exchange"
    COURTESY = "courtesy"
    REPLACEMENT = "replacement"
    OTHER = "other"


class SaleDiscountType(str, Enum):
    AMOUNT = "amount"
    PERCENTAGE = "percentage"


class SalePaymentPlanStatus(str, Enum):
    PLANNED = "planned"
    GENERATED = "generated"
    CANCELLED = "cancelled"


class SaleFiscalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING_CLASSIFICATION = "pending_classification"
    FISCAL_READY = "fiscal_ready"
    PENDING_DOCUMENT = "pending_document"
    DOCUMENT_GENERATED = "document_generated"
    DOCUMENT_CANCELLED = "document_cancelled"
    BLOCKED = "blocked"

@dataclass
class PaymentMethod:
    id: str
    company_id: str
    code: str
    name: str
    method_type: str
    description: str | None
    requires_reference: bool
    default_due_behavior: str
    status: str
    settings: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class OperationNature:
    id: str
    company_id: str
    code: str
    name: str
    sale_type: str
    description: str | None
    requires_reason: bool
    affects_revenue: bool
    affects_accounts_receivable: bool
    affects_stock: bool
    requires_fiscal_document: bool
    default_receivable_behavior: str
    default_invoice_behavior: str
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class CatalogItemFiscalRule:
    id: str
    company_id: str
    catalog_item_id: str
    fiscal_classification_id: str
    operation_nature_id: str
    sale_type: str
    valid_from: date | None
    valid_to: date | None
    priority: int
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class SaleItem:
    id: str
    company_id: str
    sale_id: str
    item_id: str
    stock_lot_id: str | None
    stock_lot_code: str | None
    stock_lot_expiration_date: date | None
    fiscal_classification_id: str | None
    description: str
    quantity: str
    unit: str
    unit_price: str
    discount_amount: str
    freight_amount: str
    tax_amount: str
    total_amount: str
    item_snapshot: dict[str, Any]
    fiscal_snapshot: dict[str, Any] | None
    operation_nature_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

@dataclass
class SalePaymentPlan:
    id: str
    company_id: str
    sale_id: str
    payment_method_id: str
    payment_method_code: str
    payment_method_name: str
    amount: str
    due_date: date | None
    installments: int
    status: SalePaymentPlanStatus
    notes: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


@dataclass
class Sale:
    id: str
    company_id: str
    establishment_id: str | None
    participant_id: str
    status: SaleStatus
    sale_type: SaleType
    origin: SaleOrigin
    operation_nature: SaleOperationNature
    operation_nature_id: str | None
    operation_nature_reason: str | None
    operation_nature_snapshot: dict[str, Any] | None
    fiscal_status: SaleFiscalStatus
    issue_date: date | None
    operation_date: datetime
    competency_date: date | None
    subtotal_amount: str
    discount_amount: str
    discount_type: SaleDiscountType
    discount_percentage: str | None
    discount_category: str | None
    discount_reason: str | None
    freight_amount: str
    tax_amount: str
    total_amount: str
    receivable_total_amount: str
    invoice_total_amount: str
    participant_snapshot: dict[str, Any]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    sale_number: int | None
    sale_number_text: str | None
    paid_number_text: str | None
    closed_at: datetime | None
    paid_at: datetime | None
    closed_by: str | None
    paid_by: str | None
    unlocked_by: str | None
    unlocked_at: datetime | None
    items: list[SaleItem]
    payment_plans: list[SalePaymentPlan]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if is_dataclass(value):
        return {key: _serialize_value(item_value) for key, item_value in asdict(value).items()}

    if isinstance(value, dict):
        return {key: _serialize_value(item_value) for key, item_value in value.items()}

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    return value


def operation_nature_to_dict(nature: OperationNature) -> dict[str, Any]:
    return _serialize_value(nature)


def catalog_item_fiscal_rule_to_dict(rule: CatalogItemFiscalRule) -> dict[str, Any]:
    return _serialize_value(rule)


def sale_item_to_dict(item: SaleItem) -> dict[str, Any]:
    return _serialize_value(item)


def sale_to_dict(sale: Sale) -> dict[str, Any]:
    return _serialize_value(sale)
