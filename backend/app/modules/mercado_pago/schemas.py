from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


ENVIRONMENTS = {"sandbox", "production"}
ACCOUNT_STATUSES = {"draft", "active", "inactive", "blocked"}
CONNECTION_STATUSES = {"not_connected", "configured", "connected", "needs_reauth", "error", "disabled"}
CREDENTIAL_STATUSES = {"missing", "metadata_only", "configured", "expired", "revoked", "error"}
WEBHOOK_STATUSES = {"not_configured", "configured", "verified", "error"}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


class MercadoPagoAccountUpdate(BaseModel):
    participant_id: str | None = Field(default=None, max_length=80)
    marketplace_account_id: str | None = Field(default=None, max_length=80)
    display_name: str | None = Field(default=None, max_length=160)
    environment: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=40)
    connection_status: str | None = Field(default=None, max_length=40)
    external_user_id: str | None = Field(default=None, max_length=160)
    collector_id: str | None = Field(default=None, max_length=160)
    application_id: str | None = Field(default=None, max_length=160)
    public_key_fingerprint: str | None = Field(default=None, max_length=80)
    credentials_status: str | None = Field(default=None, max_length=40)
    webhook_status: str | None = Field(default=None, max_length=40)
    credential_metadata: dict | None = None
    webhook_settings: dict | None = None
    payment_settings: dict | None = None
    reconciliation_settings: dict | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "participant_id",
        "marketplace_account_id",
        "display_name",
        "environment",
        "status",
        "connection_status",
        "external_user_id",
        "collector_id",
        "application_id",
        "public_key_fingerprint",
        "credentials_status",
        "webhook_status",
        "notes",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in ENVIRONMENTS:
            raise ValueError("Ambiente do Mercado Pago inválido.")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in ACCOUNT_STATUSES:
            raise ValueError("Status da conta Mercado Pago inválido.")
        return cleaned

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in CONNECTION_STATUSES:
            raise ValueError("Status de conexão Mercado Pago inválido.")
        return cleaned

    @field_validator("credentials_status")
    @classmethod
    def validate_credentials_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in CREDENTIAL_STATUSES:
            raise ValueError("Status de credenciais Mercado Pago inválido.")
        return cleaned

    @field_validator("webhook_status")
    @classmethod
    def validate_webhook_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in WEBHOOK_STATUSES:
            raise ValueError("Status de webhook Mercado Pago inválido.")
        return cleaned
