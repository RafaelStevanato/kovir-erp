from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

StatementLineDirection = Literal["inflow", "outflow"]
StatementLineStatus = Literal["pending", "matched", "divergent", "ignored"]
ReconciliationMatchStatus = Literal["confirmed", "confirmed_with_difference", "reversed"]
ImportSourceType = Literal["manual", "ofx", "csv", "api", "gateway", "marketplace", "pix", "other"]


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


class StatementLinePayload(BaseModel):
    external_id: str | None = Field(default=None, max_length=180)
    line_date: date
    direction: StatementLineDirection
    amount: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=255)
    document_number: str | None = Field(default=None, max_length=120)
    counterparty_name: str | None = Field(default=None, max_length=180)
    counterparty_document: str | None = Field(default=None, max_length=80)
    bank_reference: str | None = Field(default=None, max_length=180)
    raw_payload: dict[str, Any] | None = None

    @field_validator("external_id", "description", "document_number", "counterparty_name", "counterparty_document", "bank_reference", mode="before")
    @classmethod
    def clean_optional(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_text(cls, value: Any) -> str:
        return _decimal_text(value, "Valor da linha")

    @model_validator(mode="after")
    def validate_amount(self):
        if Decimal(self.amount) <= Decimal("0"):
            raise ValueError("Valor da linha do extrato precisa ser maior que zero.")
        return self


class BankStatementImportCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    financial_account_id: str = Field(min_length=1, max_length=80)
    source_type: ImportSourceType = "manual"
    source_id: str | None = Field(default=None, max_length=120)
    file_name: str | None = Field(default=None, max_length=255)
    statement_start_date: date | None = None
    statement_end_date: date | None = None
    opening_balance_amount: str | None = Field(default=None, max_length=30)
    closing_balance_amount: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=1000)
    raw_payload: dict[str, Any] | None = None
    lines: list[StatementLinePayload] = Field(default_factory=list, min_length=1, max_length=500)

    @field_validator("company_id", "financial_account_id", mode="before")
    @classmethod
    def required_ids(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("source_id", "file_name", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("opening_balance_amount", "closing_balance_amount", mode="before")
    @classmethod
    def optional_money(cls, value: Any) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _decimal_text(value, "Saldo", allow_negative=True)

    @model_validator(mode="after")
    def validate_period(self):
        if self.statement_start_date and self.statement_end_date and self.statement_end_date < self.statement_start_date:
            raise ValueError("Data final do extrato não pode ser anterior à data inicial.")
        return self



class OfxStatementImportText(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    financial_account_id: str = Field(min_length=1, max_length=80)
    file_name: str | None = Field(default=None, max_length=255)
    source_id: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    ofx_content: str = Field(min_length=20)

    @field_validator("company_id", "financial_account_id", mode="before")
    @classmethod
    def required_ids(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("file_name", "source_id", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("ofx_content", mode="before")
    @classmethod
    def required_content(cls, value: Any) -> str:
        cleaned = _required_text(value, "Conteúdo OFX")
        if "<OFX" not in cleaned.upper():
            raise ValueError("Conteúdo informado não parece ser OFX.")
        return cleaned
class ReconciliationMatchCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    statement_line_id: str = Field(min_length=1, max_length=80)
    financial_movement_id: str = Field(min_length=1, max_length=80)
    match_type: Literal["manual", "exact", "suggested", "forced"] = "manual"
    tolerance_amount: str = Field(default="0.00", max_length=30)
    allow_difference: bool = False
    confirmation_reason: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "statement_line_id", "financial_movement_id", mode="before")
    @classmethod
    def required_ids(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("confirmation_reason", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("tolerance_amount", mode="before")
    @classmethod
    def tolerance_text(cls, value: Any) -> str:
        return _decimal_text(value, "Tolerância")


class ReverseReconciliationMatch(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")


class IgnoreStatementLine(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def reason_required(cls, value: Any) -> str:
        return _required_text(value, "Motivo")
