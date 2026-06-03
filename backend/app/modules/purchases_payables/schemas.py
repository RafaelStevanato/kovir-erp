from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PurchaseStatus = Literal["draft", "confirmed", "cancelled"]
PurchaseType = Literal["inventory_purchase", "expense", "service", "tax", "asset", "other"]
PurchaseOrigin = Literal["manual", "stock_entry", "import", "marketplace", "other"]
PayableStatus = Literal["draft", "open", "overdue", "partially_paid", "paid", "cancelled", "written_off"]
FiscalLinkStatus = Literal["pending_document", "linked", "not_required", "divergent"]
PaymentSourceType = Literal["manual", "purchase_payment", "bank_payment", "gateway_payment", "other"]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _required_text(value: Any, label: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise ValueError(f"{label} é obrigatório.")
    return cleaned


def _decimal_text(value: Any, label: str, *, allow_zero: bool = True) -> str:
    if value is None:
        raise ValueError(f"{label} é obrigatório.")
    raw = str(value).strip()
    if raw == "":
        raise ValueError(f"{label} é obrigatório.")
    cleaned = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        parsed = Decimal(cleaned)
    except Exception as exc:
        raise ValueError(f"{label} deve ser numérico.") from exc
    if parsed < Decimal("0"):
        raise ValueError(f"{label} não pode ser negativo.")
    if not allow_zero and parsed <= Decimal("0"):
        raise ValueError(f"{label} deve ser maior que zero.")
    return format(parsed, "f")


class PurchaseItemCreate(BaseModel):
    item_id: str | None = Field(default=None, max_length=80)
    fiscal_classification_id: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=255)
    quantity: str = Field(min_length=1, max_length=30)
    unit: str = Field(default="UN", min_length=1, max_length=20)
    unit_cost: str = Field(min_length=1, max_length=30)
    discount_amount: str = Field(default="0", max_length=30)
    freight_amount: str = Field(default="0", max_length=30)
    tax_amount: str = Field(default="0", max_length=30)
    metadata: dict[str, Any] | None = None

    @field_validator("description", "unit", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("item_id", "fiscal_classification_id", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("quantity", "unit_cost", mode="before")
    @classmethod
    def positive_decimal(cls, value: Any) -> str:
        return _decimal_text(value, "Valor", allow_zero=False)

    @field_validator("discount_amount", "freight_amount", "tax_amount", mode="before")
    @classmethod
    def money(cls, value: Any) -> str:
        return _decimal_text(value, "Valor")


class PurchaseCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    participant_id: str = Field(min_length=1, max_length=80)
    purchase_type: PurchaseType = "expense"
    origin: PurchaseOrigin = "manual"
    establishment_id: str | None = Field(default=None, max_length=80)
    operation_nature_id: str | None = Field(default=None, max_length=80)
    fiscal_status: FiscalLinkStatus = "pending_document"
    issue_date: date | None = None
    operation_date: datetime | None = None
    competency_date: date | None = None
    financial_category_id: str | None = Field(default=None, max_length=80)
    cost_center_id: str | None = Field(default=None, max_length=80)
    expected_financial_account_id: str | None = Field(default=None, max_length=80)
    document_type: str | None = Field(default="invoice", max_length=60)
    document_number: str | None = Field(default=None, max_length=120)
    document_series: str | None = Field(default=None, max_length=40)
    access_key: str | None = Field(default=None, max_length=80)
    invoice_total_amount: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None
    items: list[PurchaseItemCreate] = Field(default_factory=list, min_length=1, max_length=200)

    @field_validator("company_id", "participant_id", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("establishment_id", "operation_nature_id", "financial_category_id", "cost_center_id", "expected_financial_account_id", "document_type", "document_number", "document_series", "access_key", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("invoice_total_amount", mode="before")
    @classmethod
    def optional_money(cls, value: Any) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _decimal_text(value, "Valor da nota")


class PurchaseUpdate(BaseModel):
    issue_date: date | None = None
    competency_date: date | None = None
    financial_category_id: str | None = Field(default=None, max_length=80)
    cost_center_id: str | None = Field(default=None, max_length=80)
    expected_financial_account_id: str | None = Field(default=None, max_length=80)
    fiscal_status: FiscalLinkStatus | None = None
    document_number: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("financial_category_id", "cost_center_id", "expected_financial_account_id", "document_number", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)


class PayableInstallmentCreate(BaseModel):
    due_date: date
    amount: str = Field(min_length=1, max_length=30)
    expected_payment_date: date | None = None
    expected_financial_account_id: str | None = Field(default=None, max_length=80)
    payment_method_id: str | None = Field(default=None, max_length=80)
    payment_method_code: str | None = Field(default=None, max_length=80)
    document_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def positive_money(cls, value: Any) -> str:
        return _decimal_text(value, "Valor da parcela", allow_zero=False)

    @field_validator("expected_financial_account_id", "payment_method_id", "payment_method_code", "document_reference", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)


class PurchaseConfirmPayload(BaseModel):
    reason: str | None = Field(default="Confirmação da compra/despesa e geração de Contas a Pagar.", max_length=500)
    installments: list[PayableInstallmentCreate] = Field(default_factory=list, min_length=1, max_length=120)

    @field_validator("reason", mode="before")
    @classmethod
    def optional_reason(cls, value: Any) -> str | None:
        return _clean_text(value)


class PurchaseCreateAndConfirmPayload(BaseModel):
    purchase: PurchaseCreate
    confirmation: PurchaseConfirmPayload

    @model_validator(mode="after")
    def validate_payload(self) -> "PurchaseCreateAndConfirmPayload":
        if not self.confirmation.installments:
            raise ValueError("Informe ao menos uma parcela para gerar o título a pagar.")
        return self


class PayablePaymentCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    financial_title_id: str = Field(min_length=1, max_length=80)
    financial_account_id: str = Field(min_length=1, max_length=80)
    payment_method_id: str | None = Field(default=None, max_length=80)
    payment_date: date
    competency_date: date | None = None
    paid_amount: str = Field(min_length=1, max_length=30)
    discount_amount: str = Field(default="0", max_length=30)
    interest_amount: str = Field(default="0", max_length=30)
    penalty_amount: str = Field(default="0", max_length=30)
    fee_amount: str = Field(default="0", max_length=30)
    source_type: PaymentSourceType = "manual"
    source_id: str | None = Field(default=None, max_length=80)
    approval_request_id: str | None = Field(default=None, max_length=80)
    evidence_reference: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "financial_title_id", "financial_account_id", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("payment_method_id", "source_id", "approval_request_id", "evidence_reference", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("paid_amount", mode="before")
    @classmethod
    def positive_paid(cls, value: Any) -> str:
        return _decimal_text(value, "Valor pago", allow_zero=False)

    @field_validator("discount_amount", "interest_amount", "penalty_amount", "fee_amount", mode="before")
    @classmethod
    def money(cls, value: Any) -> str:
        return _decimal_text(value, "Valor")

    @model_validator(mode="after")
    def validate_payment(self):
        paid = Decimal(self.paid_amount)
        discount = Decimal(self.discount_amount)
        if paid <= Decimal("0") and discount <= Decimal("0"):
            raise ValueError("Pagamento precisa reduzir o saldo do título.")
        return self


class StatusChangePayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")
