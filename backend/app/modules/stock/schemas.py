from __future__ import annotations

from datetime import date
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _required_text(value: str | None, field_label: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise ValueError(f"{field_label} é obrigatório.")
    return cleaned


def _validate_decimal_text(value: str | int | float | Decimal | None, field_label: str, *, allow_zero: bool = False) -> str:
    if value is None:
        raise ValueError(f"{field_label} é obrigatório.")
    cleaned = str(value).strip().replace(",", ".")
    try:
        parsed = Decimal(cleaned)
    except Exception as error:
        raise ValueError(f"{field_label} deve ser numérico.") from error
    if allow_zero:
        if parsed < Decimal("0"):
            raise ValueError(f"{field_label} não pode ser negativo.")
    elif parsed <= Decimal("0"):
        raise ValueError(f"{field_label} deve ser maior que zero.")
    return format(parsed, "f")


class StockLocationCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    establishment_id: str | None = Field(default=None, max_length=80)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    location_type: str = Field(default="main", max_length=40)
    is_default: bool = False
    status: str = Field(default="active", max_length=40)
    settings: dict | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id", "code", "name", mode="before")
    @classmethod
    def validate_required(cls, value: str | None) -> str:
        return _required_text(value, "Campo")

    @field_validator("establishment_id", "notes", mode="before")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str | None) -> str:
        return _required_text(value, "Código do local").lower().replace(" ", "_")


class StockLocationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    location_type: str | None = Field(default=None, max_length=40)
    is_default: bool | None = None
    status: str | None = Field(default=None, max_length=40)
    settings: dict | None = None
    notes: str | None = Field(default=None, max_length=1000)


class StockMovementCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    item_id: str = Field(min_length=1, max_length=80)
    location_id: str | None = Field(default=None, max_length=80)
    movement_type: str = Field(max_length=60)
    quantity: str = Field(max_length=30)
    unit: str | None = Field(default=None, max_length=20)
    unit_cost: str | None = Field(default=None, max_length=30)
    lot_code: str = Field(min_length=1, max_length=80)
    expiration_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict | None = None

    @field_validator("company_id", "item_id", "movement_type", mode="before")
    @classmethod
    def validate_required(cls, value: str | None) -> str:
        return _required_text(value, "Campo")

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: str | int | float | Decimal | None) -> str:
        return _validate_decimal_text(value, "Quantidade")

    @field_validator("unit_cost", mode="before")
    @classmethod
    def validate_unit_cost(cls, value: str | int | float | Decimal | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _validate_decimal_text(value, "Custo unitário", allow_zero=True)

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        return cleaned.upper() if cleaned else None

    @field_validator("lot_code", mode="before")
    @classmethod
    def validate_lot_code(cls, value: str | None) -> str:
        return _required_text(value, "Lote").upper()


class StockPurchaseEntryItemCreate(BaseModel):
    item_id: str = Field(min_length=1, max_length=80)
    quantity: str = Field(max_length=30)
    unit_cost: str | None = Field(default=None, max_length=30)
    unit: str | None = Field(default=None, max_length=20)
    lot_code: str = Field(min_length=1, max_length=80)
    expiration_date: date | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("item_id", mode="before")
    @classmethod
    def validate_item_id(cls, value: str | None) -> str:
        return _required_text(value, "Produto")

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: str | int | float | Decimal | None) -> str:
        return _validate_decimal_text(value, "Quantidade")

    @field_validator("unit_cost", mode="before")
    @classmethod
    def validate_unit_cost(cls, value: str | int | float | Decimal | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _validate_decimal_text(value, "Custo unitário", allow_zero=True)

    @field_validator("unit", "description", mode="before")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("lot_code", mode="before")
    @classmethod
    def validate_lot_code(cls, value: str | None) -> str:
        return _required_text(value, "Lote").upper()


class StockPurchaseEntryCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    supplier_participant_id: str | None = Field(default=None, max_length=80)
    location_id: str | None = Field(default=None, max_length=80)
    document_type: str = Field(default="purchase_invoice", max_length=60)
    document_number: str | None = Field(default=None, max_length=80)
    document_series: str | None = Field(default=None, max_length=40)
    access_key: str | None = Field(default=None, max_length=80)
    issue_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict | None = None
    items: list[StockPurchaseEntryItemCreate] = Field(min_length=1, max_length=100)

    @field_validator("company_id", "document_type", mode="before")
    @classmethod
    def validate_required(cls, value: str | None) -> str:
        return _required_text(value, "Campo")

    @field_validator("supplier_participant_id", "location_id", "document_number", "document_series", "access_key", "notes", mode="before")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("access_key", mode="before")
    @classmethod
    def normalize_access_key(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        if cleaned is None:
            return None
        return "".join(ch for ch in cleaned if ch.isalnum())

    @model_validator(mode="after")
    def validate_document_identity(self) -> "StockPurchaseEntryCreate":
        if not self.document_number and not self.access_key:
            raise ValueError("Informe ao menos número da nota/documento ou chave de acesso.")
        return self


class StockPurchaseXmlParsePayload(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    xml_text: str = Field(min_length=20)

    @field_validator("company_id", "xml_text", mode="before")
    @classmethod
    def validate_required(cls, value: str | None) -> str:
        return _required_text(value, "Campo")
