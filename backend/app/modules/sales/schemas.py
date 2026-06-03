from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.sales.models import SaleOperationNature, SaleOrigin, SaleStatus, SaleType


DISCOUNT_TYPES = {"amount", "percentage"}


DISCOUNT_CATEGORIES = {
    "coupon",
    "promotion",
    "commercial_negotiation",
    "customer_loyalty",
    "manager_authorization",
    "damaged_goods",
    "other",
}

PAYMENT_METHOD_CODES = {"pix", "credit_card", "debit_card", "cash", "boleto", "bank_transfer", "store_credit", "other"}


OPERATION_NATURES_REQUIRING_REASON = {
    "bonus",
    "sample",
    "exchange",
    "courtesy",
    "replacement",
    "other",
}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()

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


def _validate_decimal_text(
    value: str | int | float | Decimal | None,
    field_label: str,
    *,
    allow_zero: bool = True,
    allow_negative: bool = False,
) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip().replace(",", ".")

    if cleaned == "":
        return None

    try:
        parsed = Decimal(cleaned)
    except Exception as error:
        raise ValueError(f"{field_label} deve ser numérico.") from error

    if not allow_negative and parsed < Decimal("0"):
        raise ValueError(f"{field_label} não pode ser negativo.")

    if not allow_zero and parsed <= Decimal("0"):
        raise ValueError(f"{field_label} deve ser maior que zero.")

    return format(parsed, "f")


class SaleItemCreate(BaseModel):
    item_id: str = Field(min_length=1, max_length=80)
    stock_lot_id: str | None = Field(default=None, max_length=80)
    stock_lot_code: str | None = Field(default=None, max_length=80)
    stock_lot_expiration_date: date | None = None
    fiscal_classification_id: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    quantity: str = Field(default="1", max_length=30)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: str | None = Field(default=None, max_length=30)
    discount_amount: str = Field(default="0", max_length=30)
    freight_amount: str = Field(default="0", max_length=30)
    tax_amount: str = Field(default="0", max_length=30)

    @field_validator("item_id", mode="before")
    @classmethod
    def validate_item_id(cls, value: str | None) -> str:
        return _required_text(value, "ID do item")

    @field_validator("stock_lot_id", "fiscal_classification_id", "description", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("stock_lot_code", mode="before")
    @classmethod
    def normalize_lot_code(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        return cleaned.upper() if cleaned else None

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        return _normalize_upper(value)

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: str | int | float | Decimal | None) -> str:
        parsed = _validate_decimal_text(
            value,
            "Quantidade",
            allow_zero=False,
            allow_negative=False,
        )

        if parsed is None:
            raise ValueError("Quantidade é obrigatória.")

        return parsed

    @field_validator("unit_price", mode="before")
    @classmethod
    def validate_unit_price(cls, value: str | int | float | Decimal | None) -> str | None:
        return _validate_decimal_text(
            value,
            "Preço unitário",
            allow_zero=True,
            allow_negative=False,
        )

    @field_validator("discount_amount", "freight_amount", "tax_amount", mode="before")
    @classmethod
    def validate_amounts(cls, value: str | int | float | Decimal | None) -> str:
        parsed = _validate_decimal_text(
            value,
            "Valor",
            allow_zero=True,
            allow_negative=False,
        )

        return parsed or "0"


class SalePaymentPlanCreate(BaseModel):
    payment_method_id: str | None = Field(default=None, max_length=80)
    payment_method_code: str | None = Field(default="pix", max_length=80)
    amount: str = Field(max_length=30)
    due_date: date | None = None
    installments: int = Field(default=1, ge=1, le=48)
    notes: str | None = Field(default=None, max_length=500)
    metadata: dict | None = None

    @field_validator("payment_method_id", "notes", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("payment_method_code", mode="before")
    @classmethod
    def clean_payment_method_code(cls, value: str | None) -> str | None:
        cleaned = (_clean_text(value) or "pix").lower()
        if cleaned not in PAYMENT_METHOD_CODES:
            raise ValueError("Forma de pagamento inválida.")
        return cleaned

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: str | int | float | Decimal | None) -> str:
        parsed = _validate_decimal_text(
            value,
            "Valor da forma de pagamento",
            allow_zero=False,
            allow_negative=False,
        )
        if parsed is None:
            raise ValueError("Valor da forma de pagamento é obrigatório.")
        return parsed


class SaleCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    establishment_id: str | None = Field(default=None, max_length=80)
    participant_id: str | None = Field(default=None, max_length=80)
    sale_type: SaleType = SaleType.PRODUCT
    origin: SaleOrigin = SaleOrigin.MANUAL
    operation_nature: SaleOperationNature = SaleOperationNature.NORMAL_SALE
    operation_nature_id: str | None = Field(default=None, max_length=80)
    operation_nature_reason: str | None = Field(default=None, max_length=1000)
    issue_date: date | None = None
    operation_date: datetime | None = None
    competency_date: date | None = None
    discount_amount: str = Field(default="0", max_length=30)
    discount_type: str = Field(default="amount", max_length=40)
    discount_percentage: str | None = Field(default=None, max_length=30)
    discount_category: str | None = Field(default=None, max_length=80)
    discount_reason: str | None = Field(default=None, max_length=1000)
    freight_amount: str = Field(default="0", max_length=30)
    tax_amount: str = Field(default="0", max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    payment_plans: list[SalePaymentPlanCreate] = Field(default_factory=list)
    items: list[SaleItemCreate] = Field(min_length=1)

    @field_validator("company_id", mode="before")
    @classmethod
    def validate_required_ids(cls, value: str | None) -> str:
        return _required_text(value, "ID")

    @field_validator("establishment_id", "operation_nature_id", "notes", "discount_reason", "operation_nature_reason", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("discount_type", mode="before")
    @classmethod
    def clean_discount_type(cls, value: str | None) -> str:
        cleaned = (_clean_text(value) or "amount").lower()
        if cleaned not in DISCOUNT_TYPES:
            raise ValueError("Tipo de desconto inválido.")
        return cleaned

    @field_validator("discount_category", mode="before")
    @classmethod
    def clean_discount_category(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        if cleaned is None:
            return None
        return cleaned.lower()

    @field_validator("discount_amount", "discount_percentage", "freight_amount", "tax_amount", mode="before")
    @classmethod
    def validate_amounts(cls, value: str | int | float | Decimal | None) -> str:
        parsed = _validate_decimal_text(
            value,
            "Valor",
            allow_zero=True,
            allow_negative=False,
        )

        return parsed or "0"

    @model_validator(mode="after")
    def validate_participant_required(self):
        if self.origin != SaleOrigin.PDV:
            cleaned = _clean_text(self.participant_id)
            if not cleaned:
                raise ValueError("Participante é obrigatório para vendas fora do PDV.")
            self.participant_id = cleaned
        return self

    @model_validator(mode="after")
    def validate_operation_nature(self):
        if self.operation_nature.value in OPERATION_NATURES_REQUIRING_REASON and not self.operation_nature_reason:
            raise ValueError("Motivo da natureza da operação é obrigatório para bonificação, cortesia, amostra, troca, reposição ou outro.")
        if self.operation_nature == SaleOperationNature.NORMAL_SALE:
            self.operation_nature_reason = None
        return self

    @model_validator(mode="after")
    def validate_discount_metadata(self):
        header_discount = Decimal(self.discount_amount or "0")
        discount_percentage = Decimal(self.discount_percentage or "0") if self.discount_percentage is not None else Decimal("0")
        if self.discount_type == "percentage" and (discount_percentage <= Decimal("0") or discount_percentage > Decimal("100")):
            raise ValueError("Percentual de desconto deve ser maior que zero e menor ou igual a 100.")
        if self.discount_type == "amount" and self.discount_percentage is not None:
            self.discount_percentage = None
        has_discount = header_discount > Decimal("0") or discount_percentage > Decimal("0") or any(
            Decimal(item.discount_amount or "0") > Decimal("0") for item in self.items
        )

        if has_discount:
            if not self.discount_category:
                raise ValueError("Categoria do desconto é obrigatória quando há desconto.")
            if self.discount_category not in DISCOUNT_CATEGORIES:
                raise ValueError("Categoria de desconto inválida.")
            if not self.discount_reason:
                raise ValueError("Motivo do desconto é obrigatório quando há desconto.")
        else:
            self.discount_type = "amount"
            self.discount_percentage = None
            self.discount_category = None
            self.discount_reason = None

        return self


class SaleUpdate(BaseModel):
    establishment_id: str | None = Field(default=None, max_length=80)
    participant_id: str | None = Field(default=None, max_length=80)
    sale_type: SaleType | None = None
    origin: SaleOrigin | None = None
    operation_nature: SaleOperationNature | None = None
    operation_nature_id: str | None = Field(default=None, max_length=80)
    operation_nature_reason: str | None = Field(default=None, max_length=1000)
    issue_date: date | None = None
    operation_date: datetime | None = None
    competency_date: date | None = None
    discount_amount: str | None = Field(default=None, max_length=30)
    discount_type: str | None = Field(default=None, max_length=40)
    discount_percentage: str | None = Field(default=None, max_length=30)
    discount_category: str | None = Field(default=None, max_length=80)
    discount_reason: str | None = Field(default=None, max_length=1000)
    freight_amount: str | None = Field(default=None, max_length=30)
    tax_amount: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    payment_plans: list[SalePaymentPlanCreate] | None = None
    items: list[SaleItemCreate] | None = None

    @field_validator("establishment_id", "participant_id", "operation_nature_id", "notes", "discount_reason", "operation_nature_reason", mode="before")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("discount_type", mode="before")
    @classmethod
    def clean_discount_type(cls, value: str | None) -> str:
        cleaned = (_clean_text(value) or "amount").lower()
        if cleaned not in DISCOUNT_TYPES:
            raise ValueError("Tipo de desconto inválido.")
        return cleaned

    @field_validator("discount_category", mode="before")
    @classmethod
    def clean_discount_category(cls, value: str | None) -> str | None:
        cleaned = _clean_text(value)
        if cleaned is None:
            return None
        return cleaned.lower()

    @field_validator("discount_amount", "discount_percentage", "freight_amount", "tax_amount", mode="before")
    @classmethod
    def validate_optional_amounts(
        cls,
        value: str | int | float | Decimal | None,
    ) -> str | None:
        return _validate_decimal_text(
            value,
            "Valor",
            allow_zero=True,
            allow_negative=False,
        )

    @model_validator(mode="after")
    def validate_update_has_data(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("Nenhum dado enviado para atualização.")

        if self.discount_category and self.discount_category not in DISCOUNT_CATEGORIES:
            raise ValueError("Categoria de desconto inválida.")

        if self.discount_type == "percentage" and self.discount_percentage is not None:
            percentage = Decimal(self.discount_percentage or "0")
            if percentage <= Decimal("0") or percentage > Decimal("100"):
                raise ValueError("Percentual de desconto deve ser maior que zero e menor ou igual a 100.")

        if self.operation_nature is not None:
            if self.operation_nature.value in OPERATION_NATURES_REQUIRING_REASON and not self.operation_nature_reason:
                raise ValueError("Motivo da natureza da operação é obrigatório para bonificação, cortesia, amostra, troca, reposição ou outro.")
            if self.operation_nature == SaleOperationNature.NORMAL_SALE:
                self.operation_nature_reason = None

        return self


class SaleStatusChange(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return _clean_text(value)


class SaleReopenPayload(BaseModel):
    master_password: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("master_password", mode="before")
    @classmethod
    def validate_master_password(cls, value: str | None) -> str:
        return _required_text(value, "Senha mestre")

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return _clean_text(value)
