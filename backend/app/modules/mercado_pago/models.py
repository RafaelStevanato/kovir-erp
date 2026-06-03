from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class MercadoPagoAccount:
    id: str
    company_id: str
    participant_id: str | None
    marketplace_account_id: str | None
    display_name: str
    environment: str
    status: str
    connection_status: str
    external_user_id: str | None
    collector_id: str | None
    application_id: str | None
    public_key_fingerprint: str | None
    credentials_status: str
    webhook_status: str
    last_healthcheck_at: datetime | None
    last_sync_at: datetime | None
    credential_metadata: dict[str, Any] | None
    webhook_settings: dict[str, Any] | None
    payment_settings: dict[str, Any] | None
    reconciliation_settings: dict[str, Any] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
