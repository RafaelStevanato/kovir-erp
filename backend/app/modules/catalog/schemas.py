from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.catalog.models import (
    CatalogItemOrigin,
    CatalogItemStatus,
    CatalogItemType,
)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    if cleaned == "":
        return None

    return cleaned


def _required_text(value: str | None, field_label: str) -> str:
    cleaned = _clean_text(value)

    if cleaned is None:
        raise ValueError(f"{field_label} é obrigatório.")

    return cleaned


def _normalize_upper(value: str | None) -> str | None:
    cleaned = _clean_text(value)

    if cleaned is None:
        return None

    return cleaned.upper()


def _normalize_digits(value: str | None) -> str | None:
    cleaned = _clean_text(value)

    if cleaned is None:
        return None

    normalized = "".join(char for char in cleaned if char.isdigit())

    if normalized == "":
        return None

    return normalized


def _validate_money_text(value: str | None, field_label: str) -> str | None:
    cleaned = _clean_text(value)

    if cleaned is None:
        return None

    normalized = cleaned.replace(",", ".")

    try:
        from decimal import Decimal

        Decimal(normalized)
    except Exception as error:
        raise ValueError(f"{field_label} deve ser um valor monetário válido.") from error

    if normalized.startswith("-"):
        raise ValueError(f"{field_label} não pode ser negativo.")

    return normalized


class CatalogItemFinancialSettingsSchema(BaseModel):
    default_sale_price: str | None = Field(default=None, max_length=30)
    default_cost_price: str | None = Field(default=None, max_length=30)
    allow_price_override: bool = True
    default_revenue_account_id: str | None = Field(default=None, max_length=80)
    default_expense_account_id: str | None = Field(default=None, max_length=80)
    default_cost_center_id: str | None = Field(default=None, max_length=80)

    @field_validator("default_sale_price", mode="before")
    @classmethod
    def validate_default_sale_price(cls, value: str | None) -> str | None:
        return _validate_money_text(value, "Preço padrão de venda")

    @field_validator("default_cost_price", mode="before")
    @classmethod
    def validate_default_cost_price(cls, value: str | None) -> str | None:
        return _validate_money_text(value, "Custo padrão")

    @field_validator(
        "default_revenue_account_id",
        "default_expense_account_id",
        "default_cost_center_id",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class CatalogItemFiscalSettingsSchema(BaseModel):
    ncm: str | None = Field(default=None, min_length=8, max_length=8)
    nbs: str | None = Field(default=None, min_length=9, max_length=9)
    cest: str | None = Field(default=None, max_length=7)
    cfop_default: str | None = Field(default=None, max_length=4)
    cst_icms: str | None = Field(default=None, max_length=10)
    cst_pis: str | None = Field(default=None, max_length=10)
    cst_cofins: str | None = Field(default=None, max_length=10)
    cst_ibs_cbs: str | None = Field(default=None, max_length=10)
    cclass_trib: str | None = Field(default=None, max_length=20)
    fiscal_classification_id: str | None = Field(default=None, max_length=80)
    fiscal_classification_name: str | None = Field(default=None, max_length=160)
    fiscal_tax_regime: str | None = Field(default=None, max_length=60)
    subject_to_tax: bool = True
    subject_to_icms: bool | None = None
    subject_to_iss: bool | None = None
    subject_to_pis_cofins: bool | None = None
    subject_to_ibs_cbs: bool | None = None
    subject_to_is: bool | None = None
    fiscal_source: str | None = Field(default=None, max_length=40)
    fiscal_source_reference: str | None = Field(default=None, max_length=500)
    fiscal_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("ncm", mode="before")
    @classmethod
    def validate_ncm(cls, value: str | None) -> str | None:
        normalized = _normalize_digits(value)

        if normalized is None:
            return None

        if len(normalized) != 8:
            raise ValueError("NCM deve conter 8 dígitos.")

        return normalized

    @field_validator("nbs", mode="before")
    @classmethod
    def validate_nbs(cls, value: str | None) -> str | None:
        normalized = _normalize_digits(value)

        if normalized is None:
            return None

        if len(normalized) != 9:
            raise ValueError("NBS deve conter 9 dígitos.")

        return normalized

    @field_validator(
        "cest",
        "cfop_default",
        "cst_icms",
        "cst_pis",
        "cst_cofins",
        "cst_ibs_cbs",
        "cclass_trib",
        mode="before",
    )
    @classmethod
    def normalize_optional_upper(cls, value: str | None) -> str | None:
        return _normalize_upper(value)

    @field_validator("fiscal_notes", mode="before")
    @classmethod
    def clean_fiscal_notes(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator(
        "fiscal_classification_id",
        "fiscal_classification_name",
        "fiscal_tax_regime",
        "fiscal_source",
        "fiscal_source_reference",
        mode="before",
    )
    @classmethod
    def clean_fiscal_links(cls, value: str | None) -> str | None:
        return _clean_text(value)


class CatalogItemInventorySettingsSchema(BaseModel):
    track_stock: bool = False
    stock_unit: str | None = Field(default=None, max_length=20)
    minimum_stock: str | None = Field(default=None, max_length=30)
    allow_negative_stock: bool = False

    @field_validator("stock_unit", mode="before")
    @classmethod
    def normalize_stock_unit(cls, value: str | None) -> str | None:
        return _normalize_upper(value)

    @field_validator("minimum_stock", mode="before")
    @classmethod
    def validate_minimum_stock(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)

        if cleaned is None:
            return None

        normalized = cleaned.replace(",", ".")

        try:
            from decimal import Decimal

            Decimal(normalized)
        except Exception as error:
            raise ValueError("Estoque mínimo deve ser numérico.") from error

        if normalized.startswith("-"):
            raise ValueError("Estoque mínimo não pode ser negativo.")

        return normalized


class CatalogItemCreate(BaseModel):
    company_id: str = Field(min_length=1)
    item_type: CatalogItemType
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    sku: str | None = Field(default=None, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    unit: str = Field(default="UN", min_length=1, max_length=20)
    status: CatalogItemStatus = CatalogItemStatus.ACTIVE
    origin: CatalogItemOrigin = CatalogItemOrigin.MANUAL
    brand: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    financial_settings: CatalogItemFinancialSettingsSchema = Field(
        default_factory=CatalogItemFinancialSettingsSchema
    )
    fiscal_settings: CatalogItemFiscalSettingsSchema = Field(
        default_factory=CatalogItemFiscalSettingsSchema
    )
    inventory_settings: CatalogItemInventorySettingsSchema = Field(
        default_factory=CatalogItemInventorySettingsSchema
    )
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id", mode="before")
    @classmethod
    def validate_company_id_text(cls, value: str | None) -> str:
        return _required_text(value, "ID da empresa")

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        return _required_text(value, "Nome do item")

    @field_validator("description", "sku", "barcode", "notes", "brand", "category", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str:
        return _required_text(_normalize_upper(value), "Unidade")

    @model_validator(mode="after")
    def validate_item_consistency(self):
        fiscal = self.fiscal_settings
        inventory = self.inventory_settings

        if self.item_type == CatalogItemType.PRODUCT:
            if fiscal.nbs is not None:
                raise ValueError("Produto não deve usar NBS. Use NCM.")

        if self.item_type == CatalogItemType.SERVICE:
            if fiscal.ncm is not None:
                raise ValueError("Serviço não deve usar NCM. Use NBS.")
            if inventory.track_stock:
                raise ValueError("Serviço não deve controlar estoque.")

        if inventory.track_stock and inventory.stock_unit is None:
            raise ValueError("Item com controle de estoque deve informar unidade de estoque.")

        return self


class CatalogItemUpdate(BaseModel):
    company_id: str | None = Field(default=None, min_length=1)
    item_type: CatalogItemType | None = None
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    sku: str | None = Field(default=None, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    status: CatalogItemStatus | None = None
    origin: CatalogItemOrigin | None = None
    brand: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    financial_settings: CatalogItemFinancialSettingsSchema | None = None
    fiscal_settings: CatalogItemFiscalSettingsSchema | None = None
    inventory_settings: CatalogItemInventorySettingsSchema | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("company_id", "name", "description", "sku", "barcode", "notes", "brand", "category", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_optional_unit(cls, value: str | None) -> str | None:
        return _normalize_upper(value)


class CatalogItemResponse(BaseModel):
    id: str
    company_id: str
    item_type: CatalogItemType
    name: str
    description: str | None = None
    sku: str | None = None
    barcode: str | None = None
    unit: str
    status: CatalogItemStatus
    origin: CatalogItemOrigin
    brand: str | None = None
    category: str | None = None
    financial_settings: CatalogItemFinancialSettingsSchema | None = None
    fiscal_settings: CatalogItemFiscalSettingsSchema | None = None
    inventory_settings: CatalogItemInventorySettingsSchema | None = None
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
