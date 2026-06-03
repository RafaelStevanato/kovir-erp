from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SettlementStatus = Literal["active", "reversed", "cancelled"]
MovementDirection = Literal["inflow", "outflow"]
MovementStatus = Literal["posted", "reversed", "cancelled"]
ReconciliationStatus = Literal["pending", "matched", "divergent", "ignored"]
SettlementSourceType = Literal["manual", "gateway", "marketplace", "bank_import", "adjustment", "other"]
ManualMovementType = Literal["adjustment", "fee", "tax", "other"]
ManualMovementSourceType = Literal["manual"]


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


def _decimal_text(value: Any, label: str, *, allow_negative: bool = False, required: bool = True) -> str:
    if value is None:
        if required:
            raise ValueError(f"{label} é obrigatório.")
        return "0"
    raw = str(value).strip()
    if raw == "":
        if required:
            raise ValueError(f"{label} é obrigatório.")
        return "0"
    cleaned = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        parsed = Decimal(cleaned)
    except Exception as exc:
        raise ValueError(f"{label} deve ser numérico.") from exc
    if not allow_negative and parsed < Decimal("0"):
        raise ValueError(f"{label} não pode ser negativo.")
    return format(parsed, "f")


class SettlementCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    financial_title_id: str = Field(min_length=1, max_length=80)
    financial_account_id: str = Field(min_length=1, max_length=80)
    payment_method_id: str | None = Field(default=None, max_length=80)
    settlement_date: date
    competency_date: date | None = None
    received_amount: str = Field(min_length=1, max_length=30)
    discount_amount: str = Field(default="0", max_length=30)
    interest_amount: str = Field(default="0", max_length=30)
    penalty_amount: str = Field(default="0", max_length=30)
    fee_amount: str = Field(default="0", max_length=30)
    source_type: SettlementSourceType = "manual"
    source_id: str | None = Field(default=None, max_length=80)
    evidence_reference: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "financial_title_id", "financial_account_id", mode="before")
    @classmethod
    def required_ids(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("payment_method_id", "source_id", "evidence_reference", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("received_amount", "discount_amount", "interest_amount", "penalty_amount", "fee_amount", mode="before")
    @classmethod
    def money(cls, value: Any) -> str:
        return _decimal_text(value, "Valor")

    @model_validator(mode="after")
    def validate_values(self):
        received = Decimal(self.received_amount)
        discount = Decimal(self.discount_amount)
        interest = Decimal(self.interest_amount)
        penalty = Decimal(self.penalty_amount)
        fee = Decimal(self.fee_amount)
        if received <= Decimal("0") and discount <= Decimal("0"):
            raise ValueError("Baixa precisa ter valor recebido ou desconto/abatimento maior que zero.")
        movement = received + interest + penalty - fee
        if movement < Decimal("0"):
            raise ValueError("Valor líquido do movimento financeiro não pode ficar negativo.")
        return self


class SettlementReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")


class ManualFinancialMovementReverse(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")


class ManualFinancialMovementCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    financial_account_id: str = Field(min_length=1, max_length=80)
    direction: MovementDirection
    movement_type: ManualMovementType
    movement_date: date
    amount: str = Field(min_length=1, max_length=30)
    description: str = Field(min_length=5, max_length=255)
    source_type: ManualMovementSourceType = "manual"
    source_id: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "financial_account_id", mode="before")
    @classmethod
    def required_text(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("description", mode="before")
    @classmethod
    def description_required(cls, value: Any) -> str:
        return _required_text(value, "Justificativa")

    @field_validator("source_id", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_text(cls, value: Any) -> str:
        return _decimal_text(value, "Valor")

    @model_validator(mode="after")
    def validate_amount(self):
        if Decimal(self.amount) <= Decimal("0"):
            raise ValueError("Movimento financeiro manual precisa ter valor maior que zero.")
        return self
