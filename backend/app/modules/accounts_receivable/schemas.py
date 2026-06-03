from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ReceivableStatus = Literal["draft", "open", "overdue", "partially_received", "received", "cancelled", "written_off", "renegotiated"]
CollectionStatus = Literal["not_started", "scheduled", "reminder_sent", "in_collection", "promised", "disputed", "paused", "closed"]
FiscalLinkStatus = Literal["pending_document", "linked", "not_required", "divergent"]
TitleType = Literal["sale", "manual", "adjustment", "marketplace", "gateway", "other"]
SourceType = Literal["sale", "sale_payment_plan", "manual", "marketplace_order", "gateway_payment", "other"]


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


def _decimal_text(value: Any, label: str, *, allow_negative: bool = False) -> str:
    if value is None:
        raise ValueError(f"{label} é obrigatório.")
    raw = str(value).strip().replace("R$", "").replace("r$", "").replace(" ", "")
    if raw == "":
        raise ValueError(f"{label} é obrigatório.")
    cleaned = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        parsed = Decimal(cleaned)
    except Exception as exc:
        raise ValueError(f"{label} deve ser numérico.") from exc
    if not allow_negative and parsed < Decimal("0"):
        raise ValueError(f"{label} não pode ser negativo.")
    return format(parsed, "f")


class FinancialTitleCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    participant_id: str = Field(min_length=1, max_length=80)
    title_type: TitleType = "manual"
    source_type: SourceType = "manual"
    source_id: str | None = Field(default=None, max_length=80)
    payment_method_id: str | None = Field(default=None, max_length=80)
    payment_method_code: str | None = Field(default=None, max_length=80)
    financial_category_id: str | None = Field(default=None, max_length=80)
    cost_center_id: str | None = Field(default=None, max_length=80)
    expected_financial_account_id: str | None = Field(default=None, max_length=80)
    document_reference: str | None = Field(default=None, max_length=120)
    installment_number: int = Field(default=1, ge=1, le=999)
    installment_total: int = Field(default=1, ge=1, le=999)
    issue_date: date | None = None
    competency_date: date | None = None
    due_date: date
    expected_payment_date: date | None = None
    gross_amount: str = Field(min_length=1, max_length=30)
    discount_amount: str = Field(default="0", max_length=30)
    interest_amount: str = Field(default="0", max_length=30)
    penalty_amount: str = Field(default="0", max_length=30)
    fee_amount: str = Field(default="0", max_length=30)
    fiscal_status: FiscalLinkStatus = "pending_document"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "participant_id", mode="before")
    @classmethod
    def required_text(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("source_id", "payment_method_id", "payment_method_code", "financial_category_id", "cost_center_id", "expected_financial_account_id", "document_reference", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("gross_amount", "discount_amount", "interest_amount", "penalty_amount", "fee_amount", mode="before")
    @classmethod
    def money(cls, value: Any) -> str:
        return _decimal_text(value, "Valor")

    @model_validator(mode="after")
    def validate_amounts(self):
        gross = Decimal(self.gross_amount)
        if gross <= Decimal("0"):
            raise ValueError("Valor bruto deve ser maior que zero.")
        if self.installment_number > self.installment_total:
            raise ValueError("Número da parcela não pode ser maior que o total de parcelas.")
        return self


class FinancialTitleUpdate(BaseModel):
    due_date: date | None = None
    expected_payment_date: date | None = None
    financial_category_id: str | None = Field(default=None, max_length=80)
    cost_center_id: str | None = Field(default=None, max_length=80)
    expected_financial_account_id: str | None = Field(default=None, max_length=80)
    document_reference: str | None = Field(default=None, max_length=120)
    collection_status: CollectionStatus | None = None
    fiscal_status: FiscalLinkStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("financial_category_id", "cost_center_id", "expected_financial_account_id", "document_reference", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)


class FinancialTitleStatusChange(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")


class GenerateReceivablesFromSalePayload(BaseModel):
    reason: str | None = Field(default="Geração manual de títulos a receber a partir do pedido fechado.", max_length=500)


class ReceivablesSummaryQuery(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
