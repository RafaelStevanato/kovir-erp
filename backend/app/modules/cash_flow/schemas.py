from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CashFlowBasis = Literal["realized", "projected", "mixed"]
CashFlowPeriodGranularity = Literal["daily"]


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


class CashFlowPeriodQuery(BaseModel):
    company_id: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date
    financial_account_id: str | None = Field(default=None, max_length=80)

    @field_validator("company_id", "financial_account_id", mode="before")
    @classmethod
    def clean_ids(cls, value: object) -> str | None:
        return _clean_text(value)

    @model_validator(mode="after")
    def validate_period(self):
        if self.end_date < self.start_date:
            raise ValueError("Data final não pode ser anterior à data inicial.")
        return self


class CashFlowDiagnostics(BaseModel):
    module: str
    status: str
    storage: str
    persistence: str
    tables_consumed: list[str]
    tables_created: list[str]
    integrations: list[str]
    safety: list[str]


class CashFlowRules(BaseModel):
    principles: list[str]
    indicators: list[str]
    flows: dict[str, str]
    correction_policy: dict[str, str]
