from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StressGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participants: int = Field(default=0, ge=0, le=200)
    fiscal_classifications: int = Field(default=0, ge=0, le=200)
    products: int = Field(default=0, ge=0, le=200)
    services: int = Field(default=0, ge=0, le=200)
    sales: int = Field(default=0, ge=0, le=200)
    receivables: int = Field(default=0, ge=0, le=200)
    purchases: int = Field(default=0, ge=0, le=200)
    confirm_sales: bool = True
    confirm_purchases: bool = True

    @model_validator(mode="after")
    def validate_at_least_one_generator(self):
        total_requested = (
            self.participants
            + self.fiscal_classifications
            + self.products
            + self.services
            + self.sales
            + self.receivables
            + self.purchases
        )
        if total_requested <= 0:
            raise ValueError("Informe ao menos uma quantidade maior que zero para gerar dados de stress.")
        return self

