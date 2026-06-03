from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned:
        raise ValueError("E-mail inválido.")
    return cleaned


def _normalize_role_codes(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        cleaned = (value or "").strip().lower()
        if not cleaned:
            continue
        normalized.append(cleaned)
    if not normalized:
        raise ValueError("Informe ao menos um papel.")
    return sorted(set(normalized))


ALLOWED_APP_VIEWS = {
    "overview",
    "company",
    "participants",
    "catalog",
    "fiscalClassification",
    "imports",
    "orders",
    "productSales",
    "serviceSales",
    "marketplaces",
    "mercadoPago",
    "stock",
    "financial",
    "accountsReceivable",
    "cash",
    "reconciliation",
    "cashFlow",
    "purchasesPayables",
    "managementReports",
    "biAnalytics",
    "ai",
    "technicalRegression",
    "security",
    "stressTests",
}


def _normalize_allowed_views(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        if cleaned not in ALLOWED_APP_VIEWS:
            raise ValueError(f"Aba inválida: {cleaned}.")
        normalized.append(cleaned)
    if not normalized:
        raise ValueError("Informe ao menos uma aba permitida.")
    if "overview" not in normalized:
        normalized.append("overview")
    return sorted(set(normalized))


class BootstrapAdminPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    email: str
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=120)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Nome completo é obrigatório.")
        return cleaned


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    company_id: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class CreateCompanyUserPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str
    email: str
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=120)
    role_codes: list[str] | None = None
    allowed_views: list[str] | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Nome completo é obrigatório.")
        return cleaned

    @field_validator("role_codes", mode="before")
    @classmethod
    def normalize_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_role_codes(value or [])

    @field_validator("allowed_views", mode="before")
    @classmethod
    def normalize_views(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_allowed_views(value or [])

    @model_validator(mode="after")
    def ensure_access_payload(self) -> CreateCompanyUserPayload:
        if self.role_codes or self.allowed_views:
            return self
        self.allowed_views = ["overview"]
        return self


class UpdateCompanyUserRolesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_codes: list[str] | None = None
    allowed_views: list[str] | None = None

    @field_validator("role_codes", mode="before")
    @classmethod
    def normalize_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_role_codes(value or [])

    @field_validator("allowed_views", mode="before")
    @classmethod
    def normalize_views(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_allowed_views(value or [])

    @model_validator(mode="after")
    def ensure_access_payload(self) -> UpdateCompanyUserRolesPayload:
        if self.role_codes or self.allowed_views:
            return self
        raise ValueError("Informe role_codes ou allowed_views para atualizar permissões.")


class ApprovalPolicyUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    required_permission_code: str = Field(default="approval.decide", min_length=3, max_length=120)
    allow_self_approval: bool = False

    @field_validator("required_permission_code", mode="before")
    @classmethod
    def normalize_permission_code(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Permissão de aprovação é obrigatória.")
        return cleaned.lower()


class ApprovalDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return _clean_text(value)


class CreatePaymentApprovalRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_title_id: str
    requested_amount: Decimal = Field(ge=Decimal("0.01"))
    reason: str = Field(min_length=5, max_length=500)
    payload_snapshot: dict[str, object] = Field(default_factory=dict)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Motivo da alçada é obrigatório.")
        return cleaned


class SetMasterPasswordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=6, max_length=200)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if cleaned is None:
            raise ValueError("Senha mestre é obrigatória.")
        return cleaned
