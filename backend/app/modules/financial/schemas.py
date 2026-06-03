from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RecordStatus = Literal["draft", "active", "inactive", "blocked", "archived"]
ChartAccountType = Literal["asset", "liability", "equity", "revenue", "cost", "expense", "tax", "other"]
CategoryType = Literal["income", "expense", "cost", "tax", "fee", "deduction", "transfer", "other"]
CashFlowGroup = Literal[
    "operating_inflows",
    "operating_outflows",
    "investing_inflows",
    "investing_outflows",
    "financing_inflows",
    "financing_outflows",
    "transfers",
]
CostCenterType = Literal["administrative", "commercial", "financial", "technology", "marketplace", "store", "project", "logistics", "other"]
FinancialAccountType = Literal["bank_account", "cash", "gateway", "marketplace", "credit_card", "digital_wallet", "other"]
PaymentTermType = Literal["cash", "installments", "recurring", "custom"]
NormalBalance = Literal["debit", "credit"]
PixKeyType = Literal["cpf", "cnpj", "email", "phone", "random", "other"]


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


def _normalize_code(value: Any) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    return cleaned.upper()


def _decimal_text(value: Any, label: str, *, allow_negative: bool = False) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace(".", "").replace(",", ".") if "," in str(value) else str(value).strip()
    if cleaned == "":
        return None
    try:
        parsed = Decimal(cleaned)
    except Exception as exc:
        raise ValueError(f"{label} deve ser numérico.") from exc
    if not allow_negative and parsed < Decimal("0"):
        raise ValueError(f"{label} não pode ser negativo.")
    return format(parsed, "f")


class ChartAccountCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    account_type: ChartAccountType = "expense"
    parent_id: str | None = Field(default=None, max_length=80)
    is_analytical: bool = True
    normal_balance: NormalBalance | None = None
    accepts_entries: bool = True
    status: RecordStatus = "active"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "code", "name", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: Any) -> str:
        return _required_text(_normalize_code(value), "Código")

    @field_validator("parent_id", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @model_validator(mode="after")
    def validate_entries(self):
        if not self.is_analytical and self.accepts_entries:
            raise ValueError("Conta sintética não deve receber lançamento direto.")
        return self


class ChartAccountUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=160)
    account_type: ChartAccountType | None = None
    parent_id: str | None = Field(default=None, max_length=80)
    is_analytical: bool | None = None
    normal_balance: NormalBalance | None = None
    accepts_entries: bool | None = None
    status: RecordStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_optional_code(cls, value: Any) -> str | None:
        return _normalize_code(value)

    @field_validator("name", "parent_id", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)


class FinancialCategoryCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category_type: CategoryType = "expense"
    parent_id: str | None = Field(default=None, max_length=80)
    chart_account_id: str | None = Field(default=None, max_length=80)
    cash_flow_group: CashFlowGroup | None = Field(default=None, max_length=80)
    affects_cash_flow: bool = True
    requires_cost_center: bool = False
    status: RecordStatus = "active"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "name", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_optional_code(cls, value: Any) -> str | None:
        return _normalize_code(value)

    @field_validator("parent_id", "chart_account_id", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("cash_flow_group", mode="before")
    @classmethod
    def normalize_cash_flow_group(cls, value: Any) -> str | None:
        cleaned = _clean_text(value)
        return cleaned.lower() if cleaned is not None else None


class FinancialCategoryUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=160)
    category_type: CategoryType | None = None
    parent_id: str | None = Field(default=None, max_length=80)
    chart_account_id: str | None = Field(default=None, max_length=80)
    cash_flow_group: CashFlowGroup | None = Field(default=None, max_length=80)
    affects_cash_flow: bool | None = None
    requires_cost_center: bool | None = None
    status: RecordStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_optional_code(cls, value: Any) -> str | None:
        return _normalize_code(value)

    @field_validator("name", "parent_id", "chart_account_id", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("cash_flow_group", mode="before")
    @classmethod
    def normalize_cash_flow_group(cls, value: Any) -> str | None:
        cleaned = _clean_text(value)
        return cleaned.lower() if cleaned is not None else None


class CostCenterCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    center_type: CostCenterType = "other"
    parent_id: str | None = Field(default=None, max_length=80)
    is_analytical: bool = True
    responsible_name: str | None = Field(default=None, max_length=160)
    monthly_budget_amount: str | None = Field(default=None, max_length=30)
    status: RecordStatus = "active"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "code", "name", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: Any) -> str:
        return _required_text(_normalize_code(value), "Código")

    @field_validator("parent_id", "responsible_name", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("monthly_budget_amount", mode="before")
    @classmethod
    def validate_money(cls, value: Any) -> str | None:
        return _decimal_text(value, "Orçamento mensal")


class CostCenterUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=160)
    center_type: CostCenterType | None = None
    parent_id: str | None = Field(default=None, max_length=80)
    is_analytical: bool | None = None
    responsible_name: str | None = Field(default=None, max_length=160)
    monthly_budget_amount: str | None = Field(default=None, max_length=30)
    status: RecordStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_optional_code(cls, value: Any) -> str | None:
        return _normalize_code(value)

    @field_validator("name", "parent_id", "responsible_name", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("monthly_budget_amount", mode="before")
    @classmethod
    def validate_money(cls, value: Any) -> str | None:
        return _decimal_text(value, "Orçamento mensal")


class FinancialAccountCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    account_type: FinancialAccountType = "bank_account"
    institution_name: str | None = Field(default=None, max_length=160)
    branch_number: str | None = Field(default=None, max_length=40)
    account_number: str | None = Field(default=None, max_length=80)
    account_digit: str | None = Field(default=None, max_length=20)
    pix_key: str | None = Field(default=None, max_length=255)
    pix_key_type: PixKeyType | None = None
    currency: str = Field(default="BRL", max_length=10)
    opening_balance_amount: str = Field(default="0", max_length=30)
    is_default_receivable: bool = False
    is_default_payable: bool = False
    status: RecordStatus = "active"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "name", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("institution_name", "branch_number", "account_number", "account_digit", "pix_key", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        return (_clean_text(value) or "BRL").upper()

    @field_validator("opening_balance_amount", mode="before")
    @classmethod
    def validate_opening_balance(cls, value: Any) -> str:
        return _decimal_text(value, "Saldo inicial", allow_negative=True) or "0"

    @model_validator(mode="after")
    def validate_bank_fields(self):
        if self.account_type == "bank_account" and not self.institution_name:
            raise ValueError("Conta bancária deve informar instituição.")
        if self.pix_key and not self.pix_key_type:
            raise ValueError("Chave Pix deve informar tipo.")
        return self


class FinancialAccountUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    account_type: FinancialAccountType | None = None
    institution_name: str | None = Field(default=None, max_length=160)
    branch_number: str | None = Field(default=None, max_length=40)
    account_number: str | None = Field(default=None, max_length=80)
    account_digit: str | None = Field(default=None, max_length=20)
    pix_key: str | None = Field(default=None, max_length=255)
    pix_key_type: PixKeyType | None = None
    currency: str | None = Field(default=None, max_length=10)
    opening_balance_amount: str | None = Field(default=None, max_length=30)
    is_default_receivable: bool | None = None
    is_default_payable: bool | None = None
    status: RecordStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("name", "institution_name", "branch_number", "account_number", "account_digit", "pix_key", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: Any) -> str | None:
        cleaned = _clean_text(value)
        return cleaned.upper() if cleaned else None

    @field_validator("opening_balance_amount", mode="before")
    @classmethod
    def validate_opening_balance(cls, value: Any) -> str | None:
        return _decimal_text(value, "Saldo inicial", allow_negative=True)


class PaymentTermCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    term_type: PaymentTermType = "cash"
    installments: int = Field(default=1, ge=1, le=60)
    first_due_days: int = Field(default=0, ge=0, le=365)
    interval_days: int = Field(default=30, ge=0, le=365)
    generate_on_sale: bool = True
    status: RecordStatus = "active"
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", "name", mode="before")
    @classmethod
    def required(cls, value: Any) -> str:
        return _required_text(value, "Campo")

    @field_validator("notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)

    @model_validator(mode="after")
    def validate_installments(self):
        if self.term_type == "cash" and self.installments != 1:
            raise ValueError("Condição à vista deve ter uma parcela.")
        if self.installments > 1 and self.interval_days <= 0:
            raise ValueError("Condição parcelada deve ter intervalo maior que zero.")
        return self


class PaymentTermUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    term_type: PaymentTermType | None = None
    installments: int | None = Field(default=None, ge=1, le=60)
    first_due_days: int | None = Field(default=None, ge=0, le=365)
    interval_days: int | None = Field(default=None, ge=0, le=365)
    generate_on_sale: bool | None = None
    status: RecordStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("name", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        return _clean_text(value)
