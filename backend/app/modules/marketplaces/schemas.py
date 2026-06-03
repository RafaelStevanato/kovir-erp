from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.marketplaces.models import (
    MarketplaceAccountStatus,
    MarketplaceConnectionStatus,
    MarketplaceEnvironment,
    MarketplaceProviderCode,
)


PROVIDER_CODES = {provider.value for provider in MarketplaceProviderCode}
ACCOUNT_STATUSES = {status.value for status in MarketplaceAccountStatus}
CONNECTION_STATUSES = {status.value for status in MarketplaceConnectionStatus}
ENVIRONMENTS = {environment.value for environment in MarketplaceEnvironment}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


class MarketplaceAccountUpdate(BaseModel):
    participant_id: str | None = Field(default=None, max_length=80)
    display_name: str | None = Field(default=None, max_length=160)
    environment: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=40)
    connection_status: str | None = Field(default=None, max_length=40)
    external_account_id: str | None = Field(default=None, max_length=160)
    credential_metadata: dict | None = None
    settings: dict | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("participant_id", "display_name", "environment", "status", "connection_status", "external_account_id", "notes", mode="before")
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
            raise ValueError("Ambiente de integração inválido.")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in ACCOUNT_STATUSES:
            raise ValueError("Status da conta de marketplace inválido.")
        return cleaned

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower()
        if cleaned not in CONNECTION_STATUSES:
            raise ValueError("Status de conexão inválido.")
        return cleaned


class MarketplaceAccountCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    provider_code: str = Field(min_length=1, max_length=80)
    participant_id: str | None = Field(default=None, max_length=80)
    display_name: str | None = Field(default=None, max_length=160)
    environment: str = Field(default="sandbox", max_length=40)
    status: str = Field(default="draft", max_length=40)
    connection_status: str = Field(default="not_connected", max_length=40)
    external_account_id: str | None = Field(default=None, max_length=160)
    credential_metadata: dict | None = None
    settings: dict | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id", "provider_code", mode="before")
    @classmethod
    def clean_required_text(cls, value: str | None) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Campo obrigatório não informado.")
        return cleaned

    @field_validator("participant_id", "display_name", "environment", "status", "connection_status", "external_account_id", "notes", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("provider_code")
    @classmethod
    def validate_provider_code(cls, value: str) -> str:
        cleaned = value.lower()
        if cleaned not in PROVIDER_CODES:
            raise ValueError("Provedor de marketplace/gateway inválido.")
        return cleaned

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str | None) -> str:
        cleaned = (value or "sandbox").lower()
        if cleaned not in ENVIRONMENTS:
            raise ValueError("Ambiente de integração inválido.")
        return cleaned

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str:
        cleaned = (value or "draft").lower()
        if cleaned not in ACCOUNT_STATUSES:
            raise ValueError("Status da conta de marketplace inválido.")
        return cleaned

    @field_validator("connection_status")
    @classmethod
    def validate_connection_status(cls, value: str | None) -> str:
        cleaned = (value or "not_connected").lower()
        if cleaned not in CONNECTION_STATUSES:
            raise ValueError("Status de conexão inválido.")
        return cleaned
