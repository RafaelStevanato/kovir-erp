from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class FinancialPeriodClosureCreate(BaseModel):
    company_id: str = Field(min_length=5, max_length=80)
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, Any] | None = None

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date < self.start_date:
            raise ValueError("Data final do período não pode ser anterior à data inicial.")
        return self


class FinancialPeriodClosureDeactivate(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
