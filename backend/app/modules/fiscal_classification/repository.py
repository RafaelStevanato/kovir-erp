from __future__ import annotations

from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.fiscal_classification.db_models import (
    FiscalClassificationDB,
    FiscalProfileDB,
)
from app.modules.fiscal_classification.models import (
    FiscalAppliesTo,
    FiscalClassification,
    FiscalProfile,
    FiscalProfileType,
    FiscalRecordStatus,
    FiscalSourceType,
    TaxRegimeScope,
)


def _safe_profile_type(value: str) -> FiscalProfileType:
    return FiscalProfileType(value)


def _safe_applies_to(value: str) -> FiscalAppliesTo:
    return FiscalAppliesTo(value)


def _safe_tax_regime(value: str) -> TaxRegimeScope:
    return TaxRegimeScope(value)


def _safe_status(value: str) -> FiscalRecordStatus:
    return FiscalRecordStatus(value)


def _safe_source(value: str) -> FiscalSourceType:
    return FiscalSourceType(value)


def fiscal_profile_db_to_domain(profile: FiscalProfileDB) -> FiscalProfile:
    return FiscalProfile(
        id=profile.id,
        company_id=profile.company_id,
        name=profile.name,
        description=profile.description,
        profile_type=_safe_profile_type(profile.profile_type),
        applies_to=_safe_applies_to(profile.applies_to),
        tax_regime=_safe_tax_regime(profile.tax_regime),
        status=_safe_status(profile.status),
        valid_from=profile.valid_from,
        valid_to=profile.valid_to,
        source=_safe_source(profile.source),
        source_reference=profile.source_reference,
        notes=profile.notes,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def fiscal_classification_db_to_domain(
    classification: FiscalClassificationDB,
) -> FiscalClassification:
    return FiscalClassification(
        id=classification.id,
        company_id=classification.company_id,
        fiscal_profile_id=classification.fiscal_profile_id,
        name=classification.name,
        description=classification.description,
        item_type=_safe_applies_to(classification.item_type),
        tax_regime=_safe_tax_regime(classification.tax_regime),
        ncm=classification.ncm,
        nbs=classification.nbs,
        cest=getattr(classification, "cest", None),
        ex_tipi=getattr(classification, "ex_tipi", None),
        origem_mercadoria=getattr(classification, "origem_mercadoria", None),
        cfop_default=classification.cfop_default,
        cst_icms=classification.cst_icms,
        cst_pis=classification.cst_pis,
        cst_cofins=classification.cst_cofins,
        cst_ibs_cbs=classification.cst_ibs_cbs,
        cclass_trib=classification.cclass_trib,
        subject_to_icms=classification.subject_to_icms,
        subject_to_iss=classification.subject_to_iss,
        subject_to_pis_cofins=classification.subject_to_pis_cofins,
        subject_to_ibs_cbs=classification.subject_to_ibs_cbs,
        subject_to_is=classification.subject_to_is,
        valid_from=classification.valid_from,
        valid_to=classification.valid_to,
        status=_safe_status(classification.status),
        source=_safe_source(classification.source),
        source_reference=classification.source_reference,
        notes=classification.notes,
        created_at=classification.created_at,
        updated_at=classification.updated_at,
    )


def _apply_profile_domain_to_db(profile_db: FiscalProfileDB, profile: FiscalProfile) -> None:
    profile_db.company_id = profile.company_id
    profile_db.name = profile.name
    profile_db.description = profile.description
    profile_db.profile_type = profile.profile_type.value
    profile_db.applies_to = profile.applies_to.value
    profile_db.tax_regime = profile.tax_regime.value
    profile_db.status = profile.status.value
    profile_db.valid_from = profile.valid_from
    profile_db.valid_to = profile.valid_to
    profile_db.source = profile.source.value
    profile_db.source_reference = profile.source_reference
    profile_db.notes = profile.notes
    profile_db.created_at = profile.created_at
    profile_db.updated_at = profile.updated_at


def _apply_classification_domain_to_db(
    classification_db: FiscalClassificationDB,
    classification: FiscalClassification,
) -> None:
    classification_db.company_id = classification.company_id
    classification_db.fiscal_profile_id = classification.fiscal_profile_id
    classification_db.name = classification.name
    classification_db.description = classification.description
    classification_db.item_type = classification.item_type.value
    classification_db.tax_regime = classification.tax_regime.value
    classification_db.ncm = classification.ncm
    classification_db.nbs = classification.nbs
    classification_db.cest = getattr(classification, "cest", None)
    classification_db.ex_tipi = getattr(classification, "ex_tipi", None)
    classification_db.origem_mercadoria = getattr(classification, "origem_mercadoria", None)
    classification_db.cfop_default = classification.cfop_default
    classification_db.cst_icms = classification.cst_icms
    classification_db.cst_pis = classification.cst_pis
    classification_db.cst_cofins = classification.cst_cofins
    classification_db.cst_ibs_cbs = classification.cst_ibs_cbs
    classification_db.cclass_trib = classification.cclass_trib
    classification_db.subject_to_icms = classification.subject_to_icms
    classification_db.subject_to_iss = classification.subject_to_iss
    classification_db.subject_to_pis_cofins = classification.subject_to_pis_cofins
    classification_db.subject_to_ibs_cbs = classification.subject_to_ibs_cbs
    classification_db.subject_to_is = classification.subject_to_is
    classification_db.valid_from = classification.valid_from
    classification_db.valid_to = classification.valid_to
    classification_db.status = classification.status.value
    classification_db.source = classification.source.value
    classification_db.source_reference = classification.source_reference
    classification_db.notes = classification.notes
    classification_db.created_at = classification.created_at
    classification_db.updated_at = classification.updated_at


def create_fiscal_profile(db: Session, profile: FiscalProfile) -> FiscalProfileDB:
    profile_db = FiscalProfileDB(id=profile.id)
    _apply_profile_domain_to_db(profile_db, profile)
    db.add(profile_db)
    db.flush()
    return profile_db


def update_fiscal_profile(
    db: Session,
    profile_db: FiscalProfileDB,
    profile: FiscalProfile,
) -> FiscalProfileDB:
    _apply_profile_domain_to_db(profile_db, profile)
    db.add(profile_db)
    db.flush()
    return profile_db


def get_fiscal_profile(db: Session, profile_id: str) -> FiscalProfileDB | None:
    statement = select(FiscalProfileDB).where(
        FiscalProfileDB.id == profile_id,
        FiscalProfileDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_fiscal_profile_by_name(
    db: Session,
    *,
    company_id: str,
    name: str,
) -> FiscalProfileDB | None:
    statement = select(FiscalProfileDB).where(
        FiscalProfileDB.company_id == company_id,
        FiscalProfileDB.name == name,
        FiscalProfileDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def list_fiscal_profiles(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: str | None = None,
    profile_type: str | None = None,
    applies_to: str | None = None,
    tax_regime: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FiscalProfileDB]:
    statement = _apply_profile_filters(
        select(FiscalProfileDB),
        company_id=company_id,
        status_filter=status_filter,
        profile_type=profile_type,
        applies_to=applies_to,
        tax_regime=tax_regime,
        search=search,
    )

    statement = (
        statement
        .order_by(FiscalProfileDB.created_at.desc(), FiscalProfileDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def create_fiscal_classification(
    db: Session,
    classification: FiscalClassification,
) -> FiscalClassificationDB:
    classification_db = FiscalClassificationDB(id=classification.id)
    _apply_classification_domain_to_db(classification_db, classification)
    db.add(classification_db)
    db.flush()
    return classification_db


def update_fiscal_classification(
    db: Session,
    classification_db: FiscalClassificationDB,
    classification: FiscalClassification,
) -> FiscalClassificationDB:
    _apply_classification_domain_to_db(classification_db, classification)
    db.add(classification_db)
    db.flush()
    return classification_db


def get_fiscal_classification(
    db: Session,
    classification_id: str,
) -> FiscalClassificationDB | None:
    statement = select(FiscalClassificationDB).where(
        FiscalClassificationDB.id == classification_id,
        FiscalClassificationDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def list_fiscal_classifications(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: str | None = None,
    item_type: str | None = None,
    tax_regime: str | None = None,
    ncm: str | None = None,
    nbs: str | None = None,
    cfop: str | None = None,
    cst_ibs_cbs: str | None = None,
    cclass_trib: str | None = None,
    subject_to_ibs_cbs: bool | None = None,
    subject_to_is: bool | None = None,
    valid_on: date | None = None,
    validity_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FiscalClassificationDB]:
    statement = _apply_classification_filters(
        select(FiscalClassificationDB),
        company_id=company_id,
        status_filter=status_filter,
        item_type=item_type,
        tax_regime=tax_regime,
        ncm=ncm,
        nbs=nbs,
        cfop=cfop,
        cst_ibs_cbs=cst_ibs_cbs,
        cclass_trib=cclass_trib,
        subject_to_ibs_cbs=subject_to_ibs_cbs,
        subject_to_is=subject_to_is,
        valid_on=valid_on,
        validity_filter=validity_filter,
        search=search,
    )

    statement = (
        statement
        .order_by(FiscalClassificationDB.created_at.desc(), FiscalClassificationDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def count_fiscal_profiles(
    db: Session,
    company_id: str | None = None,
    status_filter: str | None = None,
    profile_type: str | None = None,
    applies_to: str | None = None,
    tax_regime: str | None = None,
    search: str | None = None,
) -> int:
    statement = _apply_profile_filters(
        select(func.count()).select_from(FiscalProfileDB),
        company_id=company_id,
        status_filter=status_filter,
        profile_type=profile_type,
        applies_to=applies_to,
        tax_regime=tax_regime,
        search=search,
    )

    return int(db.scalar(statement) or 0)


def count_fiscal_classifications(
    db: Session,
    company_id: str | None = None,
    status_filter: str | None = None,
    item_type: str | None = None,
    tax_regime: str | None = None,
    ncm: str | None = None,
    nbs: str | None = None,
    cfop: str | None = None,
    cst_ibs_cbs: str | None = None,
    cclass_trib: str | None = None,
    subject_to_ibs_cbs: bool | None = None,
    subject_to_is: bool | None = None,
    valid_on: date | None = None,
    validity_filter: str | None = None,
    search: str | None = None,
) -> int:
    statement = _apply_classification_filters(
        select(func.count()).select_from(FiscalClassificationDB),
        company_id=company_id,
        status_filter=status_filter,
        item_type=item_type,
        tax_regime=tax_regime,
        ncm=ncm,
        nbs=nbs,
        cfop=cfop,
        cst_ibs_cbs=cst_ibs_cbs,
        cclass_trib=cclass_trib,
        subject_to_ibs_cbs=subject_to_ibs_cbs,
        subject_to_is=subject_to_is,
        valid_on=valid_on,
        validity_filter=validity_filter,
        search=search,
    )

    return int(db.scalar(statement) or 0)


def _apply_profile_filters(
    statement: Select,
    *,
    company_id: str | None = None,
    status_filter: str | None = None,
    profile_type: str | None = None,
    applies_to: str | None = None,
    tax_regime: str | None = None,
    search: str | None = None,
) -> Select:
    statement = statement.where(FiscalProfileDB.deleted_at.is_(None))

    if company_id is not None:
        statement = statement.where(FiscalProfileDB.company_id == company_id)

    if status_filter is not None:
        statement = statement.where(FiscalProfileDB.status == status_filter)

    if profile_type is not None:
        statement = statement.where(FiscalProfileDB.profile_type == profile_type)

    if applies_to is not None:
        statement = statement.where(FiscalProfileDB.applies_to == applies_to)

    if tax_regime is not None:
        statement = statement.where(FiscalProfileDB.tax_regime == tax_regime)

    if search is not None and search.strip() != "":
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                FiscalProfileDB.name.ilike(pattern),
                FiscalProfileDB.description.ilike(pattern),
                FiscalProfileDB.source_reference.ilike(pattern),
            )
        )

    return statement


def _apply_classification_filters(
    statement: Select,
    *,
    company_id: str | None = None,
    status_filter: str | None = None,
    item_type: str | None = None,
    tax_regime: str | None = None,
    ncm: str | None = None,
    nbs: str | None = None,
    cfop: str | None = None,
    cst_ibs_cbs: str | None = None,
    cclass_trib: str | None = None,
    subject_to_ibs_cbs: bool | None = None,
    subject_to_is: bool | None = None,
    valid_on: date | None = None,
    validity_filter: str | None = None,
    search: str | None = None,
) -> Select:
    statement = statement.where(FiscalClassificationDB.deleted_at.is_(None))

    if company_id is not None:
        statement = statement.where(FiscalClassificationDB.company_id == company_id)

    if status_filter is not None:
        statement = statement.where(FiscalClassificationDB.status == status_filter)

    if item_type is not None:
        statement = statement.where(FiscalClassificationDB.item_type == item_type)

    if tax_regime is not None:
        statement = statement.where(FiscalClassificationDB.tax_regime == tax_regime)

    if ncm is not None:
        statement = statement.where(FiscalClassificationDB.ncm == ncm)

    if nbs is not None:
        statement = statement.where(FiscalClassificationDB.nbs == nbs)

    if cfop is not None:
        statement = statement.where(FiscalClassificationDB.cfop_default == cfop)

    if cst_ibs_cbs is not None:
        statement = statement.where(FiscalClassificationDB.cst_ibs_cbs == cst_ibs_cbs)

    if cclass_trib is not None:
        statement = statement.where(FiscalClassificationDB.cclass_trib == cclass_trib)

    if subject_to_ibs_cbs is not None:
        statement = statement.where(FiscalClassificationDB.subject_to_ibs_cbs == subject_to_ibs_cbs)

    if subject_to_is is not None:
        statement = statement.where(FiscalClassificationDB.subject_to_is == subject_to_is)

    if validity_filter == "future" and valid_on is not None:
        statement = statement.where(FiscalClassificationDB.valid_from > valid_on)
    elif validity_filter == "expired" and valid_on is not None:
        statement = statement.where(FiscalClassificationDB.valid_to < valid_on)
    elif valid_on is not None:
        statement = statement.where(
            (FiscalClassificationDB.valid_from.is_(None) | (FiscalClassificationDB.valid_from <= valid_on)),
            (FiscalClassificationDB.valid_to.is_(None) | (FiscalClassificationDB.valid_to >= valid_on)),
        )

    if search is not None and search.strip() != "":
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                FiscalClassificationDB.name.ilike(pattern),
                FiscalClassificationDB.description.ilike(pattern),
                FiscalClassificationDB.ncm.ilike(pattern),
                FiscalClassificationDB.nbs.ilike(pattern),
                FiscalClassificationDB.cfop_default.ilike(pattern),
                FiscalClassificationDB.cst_icms.ilike(pattern),
                FiscalClassificationDB.cst_pis.ilike(pattern),
                FiscalClassificationDB.cst_cofins.ilike(pattern),
                FiscalClassificationDB.cst_ibs_cbs.ilike(pattern),
                FiscalClassificationDB.cclass_trib.ilike(pattern),
            )
        )

    return statement
