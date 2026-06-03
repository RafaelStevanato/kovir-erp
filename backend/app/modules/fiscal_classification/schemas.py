from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from app.modules.fiscal_classification.models import (
    FiscalAppliesTo,
    FiscalProfileType,
    FiscalRecordStatus,
    FiscalSourceType,
    TaxRegimeScope,
)


class FiscalProfileCreate(BaseModel):
    company_id: str
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    profile_type: FiscalProfileType = FiscalProfileType.MIXED
    applies_to: FiscalAppliesTo = FiscalAppliesTo.BOTH
    tax_regime: TaxRegimeScope = TaxRegimeScope.UNKNOWN
    status: FiscalRecordStatus = FiscalRecordStatus.DRAFT
    valid_from: date | None = None
    valid_to: date | None = None
    source: FiscalSourceType = FiscalSourceType.MANUAL
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class FiscalProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    profile_type: FiscalProfileType | None = None
    applies_to: FiscalAppliesTo | None = None
    tax_regime: TaxRegimeScope | None = None
    status: FiscalRecordStatus | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    source: FiscalSourceType | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class FiscalClassificationCreate(BaseModel):
    company_id: str
    fiscal_profile_id: str | None = None
    name: str = Field(..., min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)

    item_type: FiscalAppliesTo = FiscalAppliesTo.BOTH
    tax_regime: TaxRegimeScope = TaxRegimeScope.UNKNOWN

    ncm: str | None = Field(default=None, max_length=8)
    nbs: str | None = Field(default=None, max_length=20)
    cest: str | None = Field(default=None, max_length=7)
    ex_tipi: str | None = Field(default=None, max_length=3)
    origem_mercadoria: str | None = Field(default=None, max_length=1)
    cfop_default: str | None = Field(default=None, max_length=4)

    cst_icms: str | None = Field(default=None, max_length=10)
    cst_pis: str | None = Field(default=None, max_length=10)
    cst_cofins: str | None = Field(default=None, max_length=10)
    cst_ibs_cbs: str | None = Field(default=None, max_length=20)
    cclass_trib: str | None = Field(default=None, max_length=20)

    subject_to_icms: bool = False
    subject_to_iss: bool = False
    subject_to_pis_cofins: bool = False
    subject_to_ibs_cbs: bool = True
    subject_to_is: bool = False

    valid_from: date | None = None
    valid_to: date | None = None

    status: FiscalRecordStatus = FiscalRecordStatus.DRAFT
    source: FiscalSourceType = FiscalSourceType.MANUAL
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class FiscalClassificationUpdate(BaseModel):
    fiscal_profile_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)

    item_type: FiscalAppliesTo | None = None
    tax_regime: TaxRegimeScope | None = None

    ncm: str | None = Field(default=None, max_length=8)
    nbs: str | None = Field(default=None, max_length=20)
    cest: str | None = Field(default=None, max_length=7)
    ex_tipi: str | None = Field(default=None, max_length=3)
    origem_mercadoria: str | None = Field(default=None, max_length=1)
    cfop_default: str | None = Field(default=None, max_length=4)

    cst_icms: str | None = Field(default=None, max_length=10)
    cst_pis: str | None = Field(default=None, max_length=10)
    cst_cofins: str | None = Field(default=None, max_length=10)
    cst_ibs_cbs: str | None = Field(default=None, max_length=20)
    cclass_trib: str | None = Field(default=None, max_length=20)

    subject_to_icms: bool | None = None
    subject_to_iss: bool | None = None
    subject_to_pis_cofins: bool | None = None
    subject_to_ibs_cbs: bool | None = None
    subject_to_is: bool | None = None

    valid_from: date | None = None
    valid_to: date | None = None

    status: FiscalRecordStatus | None = None
    source: FiscalSourceType | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class FiscalListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
