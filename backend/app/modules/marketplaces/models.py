from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class MarketplaceProviderCode(str, Enum):
    MERCADO_PAGO = "mercado_pago"
    SHOPEE = "shopee"


class MarketplaceProviderType(str, Enum):
    PAYMENT_GATEWAY = "payment_gateway"
    MARKETPLACE = "marketplace"


class MarketplaceAccountStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class MarketplaceConnectionStatus(str, Enum):
    NOT_CONNECTED = "not_connected"
    CONFIGURED = "configured"
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    ERROR = "error"
    DISABLED = "disabled"


class MarketplaceEnvironment(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class MarketplaceSyncType(str, Enum):
    ORDERS = "orders"
    PAYMENTS = "payments"
    SETTLEMENTS = "settlements"
    CATALOG = "catalog"
    FULL = "full"


class MarketplaceSyncStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class MarketplaceAccount:
    id: str
    company_id: str
    participant_id: str | None
    provider_code: str
    provider_name: str
    provider_type: str
    display_name: str
    environment: str
    status: str
    connection_status: str
    external_account_id: str | None
    last_sync_at: datetime | None
    credential_metadata: dict[str, Any] | None
    settings: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass(slots=True)
class MarketplaceSyncRun:
    id: str
    company_id: str
    marketplace_account_id: str
    sync_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    external_cursor: str | None
    records_found: int
    records_created: int
    records_updated: int
    records_failed: int
    summary: dict[str, Any] | None
    error: dict[str, Any] | None
    created_at: datetime


@dataclass(slots=True)
class MarketplaceExternalOrder:
    id: str
    company_id: str
    marketplace_account_id: str
    provider_code: str
    external_order_id: str
    external_status: str | None
    linked_sale_id: str | None
    buyer_snapshot: dict[str, Any] | None
    amounts: dict[str, Any] | None
    raw_payload: dict[str, Any] | None
    status: str
    imported_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MarketplacePaymentEvent:
    id: str
    company_id: str
    marketplace_account_id: str
    provider_code: str
    external_payment_id: str
    external_order_id: str | None
    linked_sale_id: str | None
    linked_sale_payment_plan_id: str | None
    payment_status: str | None
    gross_amount: Decimal | None
    fee_amount: Decimal | None
    net_amount: Decimal | None
    release_status: str | None
    expected_release_date: date | None
    released_at: datetime | None
    raw_payload: dict[str, Any] | None
    imported_at: datetime | None
    created_at: datetime
    updated_at: datetime


def marketplace_account_to_dict(account: MarketplaceAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "company_id": account.company_id,
        "participant_id": account.participant_id,
        "provider_code": account.provider_code,
        "provider_name": account.provider_name,
        "provider_type": account.provider_type,
        "display_name": account.display_name,
        "environment": account.environment,
        "status": account.status,
        "connection_status": account.connection_status,
        "external_account_id": account.external_account_id,
        "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "credential_metadata": account.credential_metadata,
        "settings": account.settings,
        "notes": account.notes,
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def marketplace_sync_run_to_dict(sync_run: MarketplaceSyncRun) -> dict[str, Any]:
    return {
        "id": sync_run.id,
        "company_id": sync_run.company_id,
        "marketplace_account_id": sync_run.marketplace_account_id,
        "sync_type": sync_run.sync_type,
        "status": sync_run.status,
        "started_at": sync_run.started_at.isoformat() if sync_run.started_at else None,
        "finished_at": sync_run.finished_at.isoformat() if sync_run.finished_at else None,
        "external_cursor": sync_run.external_cursor,
        "records_found": sync_run.records_found,
        "records_created": sync_run.records_created,
        "records_updated": sync_run.records_updated,
        "records_failed": sync_run.records_failed,
        "summary": sync_run.summary,
        "error": sync_run.error,
        "created_at": sync_run.created_at.isoformat() if sync_run.created_at else None,
    }
