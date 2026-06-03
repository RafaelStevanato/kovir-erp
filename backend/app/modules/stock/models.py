from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class StockLocationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class StockLocationType(str, Enum):
    MAIN = "main"
    STORE = "store"
    WAREHOUSE = "warehouse"
    DAMAGED = "damaged"
    TRANSIT = "transit"
    OTHER = "other"


class StockMovementType(str, Enum):
    INITIAL_BALANCE = "initial_balance"
    ADJUSTMENT_IN = "adjustment_in"
    ADJUSTMENT_OUT = "adjustment_out"
    SALE_OUT = "sale_out"
    SALE_OUT_REVERSAL = "sale_out_reversal"
    PURCHASE_IN = "purchase_in"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class StockMovementDirection(str, Enum):
    IN = "in"
    OUT = "out"


class StockMovementStatus(str, Enum):
    POSTED = "posted"
    REVERSED = "reversed"
    CANCELLED = "cancelled"


class StockPurchaseEntryStatus(str, Enum):
    POSTED = "posted"
    CANCELLED = "cancelled"


@dataclass
class StockLocation:
    id: str
    company_id: str
    establishment_id: str | None
    code: str
    name: str
    location_type: StockLocationType
    is_default: bool
    status: StockLocationStatus
    settings: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class StockMovement:
    id: str
    company_id: str
    item_id: str
    location_id: str
    movement_type: StockMovementType
    direction: StockMovementDirection
    movement_date: datetime
    quantity: str
    unit: str
    unit_cost: str | None
    total_cost: str | None
    source_type: str | None
    source_id: str | None
    lot_id: str | None
    lot_code: str | None
    expiration_date: date | None
    sale_id: str | None
    sale_item_id: str | None
    status: StockMovementStatus
    notes: str | None
    source_snapshot: dict[str, Any] | None
    metadata: dict[str, Any] | None
    created_at: datetime
    created_by: str | None = None


@dataclass
class StockBalance:
    company_id: str
    item_id: str
    location_id: str
    quantity: str
    average_cost: str | None
    updated_at: datetime


@dataclass
class StockLot:
    id: str
    company_id: str
    item_id: str
    location_id: str
    lot_code: str
    expiration_date: date
    quantity: str
    average_cost: str | None
    status: str
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


@dataclass
class SaleStockLink:
    id: str
    company_id: str
    sale_id: str
    sale_item_id: str
    stock_movement_id: str
    link_type: str
    quantity: str
    status: str
    created_at: datetime


@dataclass
class StockPurchaseEntry:
    id: str
    company_id: str
    supplier_participant_id: str | None
    location_id: str
    document_type: str
    document_number: str | None
    document_series: str | None
    access_key: str | None
    issue_date: date | None
    entry_date: datetime
    status: StockPurchaseEntryStatus
    total_items: int
    total_quantity: str
    total_amount: str
    supplier_snapshot: dict[str, Any] | None
    document_snapshot: dict[str, Any] | None
    metadata: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    items: list[dict[str, Any]] | None = None


@dataclass
class StockPurchaseEntryItem:
    id: str
    company_id: str
    purchase_entry_id: str
    item_id: str
    lot_id: str | None
    lot_code: str | None
    expiration_date: date | None
    stock_movement_id: str
    description: str
    quantity: str
    unit: str
    unit_cost: str | None
    total_cost: str | None
    item_snapshot: dict[str, Any] | None
    created_at: datetime


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


def stock_location_to_dict(location: StockLocation) -> dict[str, Any]:
    return _serialize_value(location)


def stock_movement_to_dict(movement: StockMovement) -> dict[str, Any]:
    return _serialize_value(movement)


def stock_balance_to_dict(balance: StockBalance) -> dict[str, Any]:
    return _serialize_value(balance)


def stock_lot_to_dict(lot: StockLot) -> dict[str, Any]:
    return _serialize_value(lot)


def sale_stock_link_to_dict(link: SaleStockLink) -> dict[str, Any]:
    return _serialize_value(link)


def stock_purchase_entry_to_dict(entry: StockPurchaseEntry) -> dict[str, Any]:
    return _serialize_value(entry)


def stock_purchase_entry_item_to_dict(item: StockPurchaseEntryItem) -> dict[str, Any]:
    return _serialize_value(item)
