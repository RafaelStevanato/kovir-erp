from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class CatalogItemType(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"


class CatalogItemStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class CatalogItemOrigin(str, Enum):
    MANUAL = "manual"
    IMPORTED = "imported"
    INTEGRATION = "integration"
    FISCAL_DOCUMENT = "fiscal_document"
    UNKNOWN = "unknown"


@dataclass
class CatalogItemFinancialSettings:
    default_sale_price: str | None = None
    default_cost_price: str | None = None
    allow_price_override: bool = True
    default_revenue_account_id: str | None = None
    default_expense_account_id: str | None = None
    default_cost_center_id: str | None = None


@dataclass
class CatalogItemFiscalSettings:
    ncm: str | None = None
    nbs: str | None = None
    cest: str | None = None
    cfop_default: str | None = None
    cst_icms: str | None = None
    cst_pis: str | None = None
    cst_cofins: str | None = None
    cst_ibs_cbs: str | None = None
    cclass_trib: str | None = None
    fiscal_classification_id: str | None = None
    fiscal_classification_name: str | None = None
    fiscal_tax_regime: str | None = None
    subject_to_tax: bool = True
    subject_to_icms: bool | None = None
    subject_to_iss: bool | None = None
    subject_to_pis_cofins: bool | None = None
    subject_to_ibs_cbs: bool | None = None
    subject_to_is: bool | None = None
    fiscal_source: str | None = None
    fiscal_source_reference: str | None = None
    fiscal_notes: str | None = None


@dataclass
class CatalogItemInventorySettings:
    track_stock: bool = False
    stock_unit: str | None = None
    minimum_stock: str | None = None
    allow_negative_stock: bool = False


@dataclass
class CatalogItem:
    id: str
    company_id: str
    item_type: CatalogItemType
    name: str
    description: str | None = None
    sku: str | None = None
    barcode: str | None = None
    unit: str = "UN"
    status: CatalogItemStatus = CatalogItemStatus.ACTIVE
    origin: CatalogItemOrigin = CatalogItemOrigin.MANUAL
    brand: str | None = None
    category: str | None = None
    financial_settings: CatalogItemFinancialSettings | None = None
    fiscal_settings: CatalogItemFiscalSettings | None = None
    inventory_settings: CatalogItemInventorySettings | None = None
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


def catalog_item_to_dict(item: CatalogItem) -> dict[str, Any]:
    return _serialize_value(item)
