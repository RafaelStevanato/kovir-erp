from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.company.db_models import CompanyDB
from app.modules.fiscal_classification.models import (
    FiscalAppliesTo,
    FiscalClassification,
    FiscalProfile,
    FiscalProfileType,
    FiscalRecordStatus,
    FiscalSourceType,
    TaxRegimeScope,
    fiscal_classification_to_dict,
    fiscal_profile_to_dict,
)
from app.modules.fiscal_classification.repository import (
    count_fiscal_classifications as repository_count_fiscal_classifications,
    count_fiscal_profiles as repository_count_fiscal_profiles,
    create_fiscal_classification as repository_create_fiscal_classification,
    create_fiscal_profile as repository_create_fiscal_profile,
    fiscal_classification_db_to_domain,
    fiscal_profile_db_to_domain,
    get_fiscal_classification as repository_get_fiscal_classification,
    get_fiscal_profile as repository_get_fiscal_profile,
    get_fiscal_profile_by_name,
    list_fiscal_classifications as repository_list_fiscal_classifications,
    list_fiscal_profiles as repository_list_fiscal_profiles,
    update_fiscal_classification as repository_update_fiscal_classification,
    update_fiscal_profile as repository_update_fiscal_profile,
)
from app.modules.fiscal_classification.schemas import (
    FiscalClassificationCreate,
    FiscalClassificationUpdate,
    FiscalProfileCreate,
    FiscalProfileUpdate,
)
from app.shared.audit import (
    AuditContext,
    AuditEntityType,
    AuditSource,
    build_created_event,
    build_updated_event,
)
from app.shared.audit_repository import (
    audit_event_db_to_dict,
    count_audit_events_for_company,
    create_audit_event,
    list_audit_events_for_entity,
)
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _to_profile_type(value: FiscalProfileType | str) -> FiscalProfileType:
    return value if isinstance(value, FiscalProfileType) else FiscalProfileType(value)


def _to_applies_to(value: FiscalAppliesTo | str) -> FiscalAppliesTo:
    return value if isinstance(value, FiscalAppliesTo) else FiscalAppliesTo(value)


def _to_tax_regime(value: TaxRegimeScope | str) -> TaxRegimeScope:
    return value if isinstance(value, TaxRegimeScope) else TaxRegimeScope(value)


def _to_status(value: FiscalRecordStatus | str) -> FiscalRecordStatus:
    return value if isinstance(value, FiscalRecordStatus) else FiscalRecordStatus(value)


def _to_source(value: FiscalSourceType | str) -> FiscalSourceType:
    return value if isinstance(value, FiscalSourceType) else FiscalSourceType(value)


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def _clean_digits(value: str | None, max_length: int | None = None) -> str | None:
    cleaned = _clean_text(value)

    if cleaned is None:
        return None

    digits = "".join(char for char in cleaned if char.isdigit())

    if not digits:
        return None

    if max_length is not None and len(digits) > max_length:
        raise ValueError(f"Campo aceita no máximo {max_length} dígitos.")

    return digits


def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _assert_profile_id(profile_id: str) -> None:
    assert_valid_id(profile_id, "fprof")


def _assert_classification_id(classification_id: str) -> None:
    assert_valid_id(classification_id, "fclass")


def _assert_company_exists(db: Session, company_id: str) -> None:
    _assert_company_id(company_id)

    exists = db.scalar(select(CompanyDB.id).where(CompanyDB.id == company_id))

    if exists is None:
        raise ValueError("Empresa não encontrada para o company_id informado.")


def _get_profile_db_or_raise(db: Session, profile_id: str):
    _assert_profile_id(profile_id)

    profile_db = repository_get_fiscal_profile(db, profile_id)

    if profile_db is None:
        raise ValueError("Perfil fiscal não encontrado.")

    return profile_db


def _get_classification_db_or_raise(db: Session, classification_id: str):
    _assert_classification_id(classification_id)

    classification_db = repository_get_fiscal_classification(db, classification_id)

    if classification_db is None:
        raise ValueError("Classificação fiscal não encontrada.")

    return classification_db


def _assert_valid_period(valid_from: date | None, valid_to: date | None) -> None:
    if valid_from and valid_to and valid_to < valid_from:
        raise ValueError("valid_to não pode ser anterior a valid_from.")


def _assert_profile_exists_for_company(
    db: Session,
    *,
    profile_id: str | None,
    company_id: str,
) -> None:
    if profile_id is None:
        return

    profile_db = _get_profile_db_or_raise(db, profile_id)

    if profile_db.company_id != company_id:
        raise ValueError("Perfil fiscal não pertence à empresa informada.")


def _assert_profile_name_is_unique(
    db: Session,
    *,
    company_id: str,
    name: str,
    ignored_profile_id: str | None = None,
) -> None:
    existing = get_fiscal_profile_by_name(db, company_id=company_id, name=name)

    if existing is not None and existing.id != ignored_profile_id:
        raise ValueError("Já existe um perfil fiscal com este nome para a empresa.")


def _assert_not_empty_update(values: dict[str, Any]) -> None:
    if not values:
        raise ValueError("Nenhum campo enviado para atualização.")


def _validate_profile_business_rules(
    *,
    name: str,
    valid_from: date | None,
    valid_to: date | None,
) -> None:
    if not name.strip():
        raise ValueError("Nome do perfil fiscal é obrigatório.")

    _assert_valid_period(valid_from, valid_to)


def _validate_classification_business_rules(
    *,
    name: str,
    item_type: FiscalAppliesTo,
    ncm: str | None,
    nbs: str | None,
    cfop_default: str | None,
    valid_from: date | None,
    valid_to: date | None,
) -> None:
    if not name.strip():
        raise ValueError("Nome da classificação fiscal é obrigatório.")

    if ncm and not ncm.isdigit():
        raise ValueError("NCM deve conter apenas dígitos.")

    if ncm and len(ncm) > 8:
        raise ValueError("NCM deve conter no máximo 8 dígitos.")

    if nbs and not all(char.isdigit() or char == "." for char in nbs):
        raise ValueError("NBS deve conter apenas dígitos e pontos.")

    if cfop_default and (not cfop_default.isdigit() or len(cfop_default) > 4):
        raise ValueError("CFOP padrão deve conter até 4 dígitos.")

    if item_type == FiscalAppliesTo.PRODUCT and not ncm:
        raise ValueError("Classificação de produto deve informar NCM.")

    if item_type == FiscalAppliesTo.SERVICE and not nbs:
        raise ValueError("Classificação de serviço deve informar NBS.")

    _assert_valid_period(valid_from, valid_to)


def _create_audit_context(
    *,
    actor_id: str | None,
    source: AuditSource | str,
    request_id: str | None,
    correlation_id: str | None,
) -> AuditContext:
    return AuditContext(
        actor_id=actor_id,
        source=source if isinstance(source, AuditSource) else AuditSource(source),
        request_id=request_id,
        correlation_id=correlation_id,
    )


def _profile_update_data(payload: FiscalProfileUpdate) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


def _classification_update_data(payload: FiscalClassificationUpdate) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


def _build_profile_from_create(payload: FiscalProfileCreate) -> FiscalProfile:
    now = utc_now()

    return FiscalProfile(
        id=generate_id("fprof"),
        company_id=payload.company_id,
        name=payload.name.strip(),
        description=_clean_text(payload.description),
        profile_type=payload.profile_type,
        applies_to=payload.applies_to,
        tax_regime=payload.tax_regime,
        status=payload.status,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        source=payload.source,
        source_reference=_clean_text(payload.source_reference),
        notes=_clean_text(payload.notes),
        created_at=now,
        updated_at=now,
    )


def _build_classification_from_create(
    payload: FiscalClassificationCreate,
) -> FiscalClassification:
    now = utc_now()

    return FiscalClassification(
        id=generate_id("fclass"),
        company_id=payload.company_id,
        fiscal_profile_id=_clean_text(payload.fiscal_profile_id),
        name=payload.name.strip(),
        description=_clean_text(payload.description),
        item_type=payload.item_type,
        tax_regime=payload.tax_regime,
        ncm=_clean_digits(payload.ncm, max_length=8),
        nbs=_clean_text(payload.nbs),
        cest=_clean_digits(getattr(payload, "cest", None), max_length=7),
        ex_tipi=_clean_digits(getattr(payload, "ex_tipi", None), max_length=3),
        origem_mercadoria=_clean_text(getattr(payload, "origem_mercadoria", None)),
        cfop_default=_clean_digits(payload.cfop_default, max_length=4),
        cst_icms=_clean_text(payload.cst_icms),
        cst_pis=_clean_text(payload.cst_pis),
        cst_cofins=_clean_text(payload.cst_cofins),
        cst_ibs_cbs=_clean_text(payload.cst_ibs_cbs),
        cclass_trib=_clean_text(payload.cclass_trib),
        subject_to_icms=payload.subject_to_icms,
        subject_to_iss=payload.subject_to_iss,
        subject_to_pis_cofins=payload.subject_to_pis_cofins,
        subject_to_ibs_cbs=payload.subject_to_ibs_cbs,
        subject_to_is=payload.subject_to_is,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        status=payload.status,
        source=payload.source,
        source_reference=_clean_text(payload.source_reference),
        notes=_clean_text(payload.notes),
        created_at=now,
        updated_at=now,
    )


def _apply_profile_update(profile: FiscalProfile, payload: FiscalProfileUpdate) -> None:
    values = _profile_update_data(payload)
    _assert_not_empty_update(values)

    if "name" in values and values["name"] is not None:
        profile.name = values["name"].strip()

    if "description" in values:
        profile.description = _clean_text(values["description"])

    if "profile_type" in values and values["profile_type"] is not None:
        profile.profile_type = _to_profile_type(values["profile_type"])

    if "applies_to" in values and values["applies_to"] is not None:
        profile.applies_to = _to_applies_to(values["applies_to"])

    if "tax_regime" in values and values["tax_regime"] is not None:
        profile.tax_regime = _to_tax_regime(values["tax_regime"])

    if "status" in values and values["status"] is not None:
        profile.status = _to_status(values["status"])

    if "valid_from" in values:
        profile.valid_from = values["valid_from"]

    if "valid_to" in values:
        profile.valid_to = values["valid_to"]

    if "source" in values and values["source"] is not None:
        profile.source = _to_source(values["source"])

    if "source_reference" in values:
        profile.source_reference = _clean_text(values["source_reference"])

    if "notes" in values:
        profile.notes = _clean_text(values["notes"])

    profile.updated_at = utc_now()


def _apply_classification_update(
    classification: FiscalClassification,
    payload: FiscalClassificationUpdate,
) -> None:
    values = _classification_update_data(payload)
    _assert_not_empty_update(values)

    if "fiscal_profile_id" in values:
        classification.fiscal_profile_id = _clean_text(values["fiscal_profile_id"])

    if "name" in values and values["name"] is not None:
        classification.name = values["name"].strip()

    if "description" in values:
        classification.description = _clean_text(values["description"])

    if "item_type" in values and values["item_type"] is not None:
        classification.item_type = _to_applies_to(values["item_type"])

    if "tax_regime" in values and values["tax_regime"] is not None:
        classification.tax_regime = _to_tax_regime(values["tax_regime"])

    if "ncm" in values:
        classification.ncm = _clean_digits(values["ncm"], max_length=8)

    if "nbs" in values:
        classification.nbs = _clean_text(values["nbs"])

    if "cest" in values:
        classification.cest = _clean_digits(values["cest"], max_length=7)

    if "ex_tipi" in values:
        classification.ex_tipi = _clean_digits(values["ex_tipi"], max_length=3)

    if "origem_mercadoria" in values:
        classification.origem_mercadoria = _clean_text(values["origem_mercadoria"])

    if "cfop_default" in values:
        classification.cfop_default = _clean_digits(values["cfop_default"], max_length=4)

    for field_name in [
        "cst_icms",
        "cst_pis",
        "cst_cofins",
        "cst_ibs_cbs",
        "cclass_trib",
        "source_reference",
        "notes",
    ]:
        if field_name in values:
            setattr(classification, field_name, _clean_text(values[field_name]))

    for field_name in [
        "subject_to_icms",
        "subject_to_iss",
        "subject_to_pis_cofins",
        "subject_to_ibs_cbs",
        "subject_to_is",
    ]:
        if field_name in values and values[field_name] is not None:
            setattr(classification, field_name, bool(values[field_name]))

    if "valid_from" in values:
        classification.valid_from = values["valid_from"]

    if "valid_to" in values:
        classification.valid_to = values["valid_to"]

    if "status" in values and values["status"] is not None:
        classification.status = _to_status(values["status"])

    if "source" in values and values["source"] is not None:
        classification.source = _to_source(values["source"])

    classification.updated_at = utc_now()


def create_fiscal_profile(
    db: Session,
    payload: FiscalProfileCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)

    profile = _build_profile_from_create(payload)

    _validate_profile_business_rules(
        name=profile.name,
        valid_from=profile.valid_from,
        valid_to=profile.valid_to,
    )
    _assert_profile_name_is_unique(db, company_id=profile.company_id, name=profile.name)

    after = fiscal_profile_to_dict(profile)

    try:
        repository_create_fiscal_profile(db, profile)

        event = build_created_event(
            entity_type=AuditEntityType.FISCAL_PROFILE,
            entity_id=profile.id,
            context=_create_audit_context(
                actor_id=actor_id,
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
            ),
            after=after,
        )
        create_audit_event(db, event, company_id=profile.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def list_fiscal_profiles(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: FiscalRecordStatus | str | None = None,
    profile_type: FiscalProfileType | str | None = None,
    applies_to: FiscalAppliesTo | str | None = None,
    tax_regime: TaxRegimeScope | str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    if company_id is not None:
        _assert_company_exists(db, company_id)

    profiles = repository_list_fiscal_profiles(
        db,
        company_id=company_id,
        status_filter=_enum_value(status_filter),
        profile_type=_enum_value(profile_type),
        applies_to=_enum_value(applies_to),
        tax_regime=_enum_value(tax_regime),
        search=search,
        limit=limit,
        offset=offset,
    )

    return [fiscal_profile_to_dict(fiscal_profile_db_to_domain(profile)) for profile in profiles]


def count_fiscal_profiles(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: FiscalRecordStatus | str | None = None,
    profile_type: FiscalProfileType | str | None = None,
    applies_to: FiscalAppliesTo | str | None = None,
    tax_regime: TaxRegimeScope | str | None = None,
    search: str | None = None,
) -> int:
    if company_id is not None:
        _assert_company_exists(db, company_id)

    return repository_count_fiscal_profiles(
        db,
        company_id=company_id,
        status_filter=_enum_value(status_filter),
        profile_type=_enum_value(profile_type),
        applies_to=_enum_value(applies_to),
        tax_regime=_enum_value(tax_regime),
        search=search,
    )


def get_fiscal_profile(db: Session, profile_id: str) -> dict[str, Any]:
    profile_db = _get_profile_db_or_raise(db, profile_id)

    return fiscal_profile_to_dict(fiscal_profile_db_to_domain(profile_db))


def update_fiscal_profile(
    db: Session,
    profile_id: str,
    payload: FiscalProfileUpdate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    profile_db = _get_profile_db_or_raise(db, profile_id)
    profile = fiscal_profile_db_to_domain(profile_db)

    before = fiscal_profile_to_dict(profile)

    update_values = _profile_update_data(payload)
    new_name = update_values.get("name", profile.name)
    if new_name is not None:
        _assert_profile_name_is_unique(
            db,
            company_id=profile.company_id,
            name=new_name.strip(),
            ignored_profile_id=profile.id,
        )

    _apply_profile_update(profile, payload)

    _validate_profile_business_rules(
        name=profile.name,
        valid_from=profile.valid_from,
        valid_to=profile.valid_to,
    )

    after = fiscal_profile_to_dict(profile)

    try:
        repository_update_fiscal_profile(db, profile_db, profile)

        if before != after:
            event = build_updated_event(
                entity_type=AuditEntityType.FISCAL_PROFILE,
                entity_id=profile.id,
                context=_create_audit_context(
                    actor_id=actor_id,
                    source=source,
                    request_id=request_id,
                    correlation_id=correlation_id,
                ),
                before=before,
                after=after,
            )
            create_audit_event(db, event, company_id=profile.company_id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def get_fiscal_profile_audit(db: Session, profile_id: str) -> list[dict[str, Any]]:
    _get_profile_db_or_raise(db, profile_id)

    events = list_audit_events_for_entity(
        db,
        entity_type=AuditEntityType.FISCAL_PROFILE.value,
        entity_id=profile_id,
        limit=100,
        offset=0,
    )

    return [_audit_event_to_legacy_fiscal_dict(event) for event in events]


def create_fiscal_classification(
    db: Session,
    payload: FiscalClassificationCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)

    classification = _build_classification_from_create(payload)

    _assert_profile_exists_for_company(
        db,
        profile_id=classification.fiscal_profile_id,
        company_id=classification.company_id,
    )

    _validate_classification_business_rules(
        name=classification.name,
        item_type=classification.item_type,
        ncm=classification.ncm,
        nbs=classification.nbs,
        cfop_default=classification.cfop_default,
        valid_from=classification.valid_from,
        valid_to=classification.valid_to,
    )

    after = fiscal_classification_to_dict(classification)

    try:
        repository_create_fiscal_classification(db, classification)

        event = build_created_event(
            entity_type=AuditEntityType.FISCAL_CLASSIFICATION,
            entity_id=classification.id,
            context=_create_audit_context(
                actor_id=actor_id,
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
            ),
            after=after,
        )
        create_audit_event(db, event, company_id=classification.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def list_fiscal_classifications(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: FiscalRecordStatus | str | None = None,
    item_type: FiscalAppliesTo | str | None = None,
    tax_regime: TaxRegimeScope | str | None = None,
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
) -> list[dict[str, Any]]:
    if company_id is not None:
        _assert_company_exists(db, company_id)

    classifications = repository_list_fiscal_classifications(
        db,
        company_id=company_id,
        status_filter=_enum_value(status_filter),
        item_type=_enum_value(item_type),
        tax_regime=_enum_value(tax_regime),
        ncm=_clean_digits(ncm, max_length=8),
        nbs=_clean_text(nbs),
        cfop=_clean_digits(cfop, max_length=4),
        cst_ibs_cbs=_clean_text(cst_ibs_cbs),
        cclass_trib=_clean_text(cclass_trib),
        subject_to_ibs_cbs=subject_to_ibs_cbs,
        subject_to_is=subject_to_is,
        valid_on=valid_on or (date.today() if validity_filter is not None else None),
        validity_filter=validity_filter,
        search=search,
        limit=limit,
        offset=offset,
    )

    return [
        fiscal_classification_to_dict(fiscal_classification_db_to_domain(classification))
        for classification in classifications
    ]


def count_fiscal_classifications(
    db: Session,
    *,
    company_id: str | None = None,
    status_filter: FiscalRecordStatus | str | None = None,
    item_type: FiscalAppliesTo | str | None = None,
    tax_regime: TaxRegimeScope | str | None = None,
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
    if company_id is not None:
        _assert_company_exists(db, company_id)

    return repository_count_fiscal_classifications(
        db,
        company_id=company_id,
        status_filter=_enum_value(status_filter),
        item_type=_enum_value(item_type),
        tax_regime=_enum_value(tax_regime),
        ncm=_clean_digits(ncm, max_length=8),
        nbs=_clean_text(nbs),
        cfop=_clean_digits(cfop, max_length=4),
        cst_ibs_cbs=_clean_text(cst_ibs_cbs),
        cclass_trib=_clean_text(cclass_trib),
        subject_to_ibs_cbs=subject_to_ibs_cbs,
        subject_to_is=subject_to_is,
        valid_on=valid_on or (date.today() if validity_filter is not None else None),
        validity_filter=validity_filter,
        search=search,
    )


def get_fiscal_classification(db: Session, classification_id: str) -> dict[str, Any]:
    classification_db = _get_classification_db_or_raise(db, classification_id)

    return fiscal_classification_to_dict(
        fiscal_classification_db_to_domain(classification_db)
    )


def update_fiscal_classification(
    db: Session,
    classification_id: str,
    payload: FiscalClassificationUpdate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    classification_db = _get_classification_db_or_raise(db, classification_id)
    classification = fiscal_classification_db_to_domain(classification_db)

    before = fiscal_classification_to_dict(classification)

    _apply_classification_update(classification, payload)

    _assert_profile_exists_for_company(
        db,
        profile_id=classification.fiscal_profile_id,
        company_id=classification.company_id,
    )

    _validate_classification_business_rules(
        name=classification.name,
        item_type=classification.item_type,
        ncm=classification.ncm,
        nbs=classification.nbs,
        cfop_default=classification.cfop_default,
        valid_from=classification.valid_from,
        valid_to=classification.valid_to,
    )

    after = fiscal_classification_to_dict(classification)

    try:
        repository_update_fiscal_classification(db, classification_db, classification)

        if before != after:
            event = build_updated_event(
                entity_type=AuditEntityType.FISCAL_CLASSIFICATION,
                entity_id=classification.id,
                context=_create_audit_context(
                    actor_id=actor_id,
                    source=source,
                    request_id=request_id,
                    correlation_id=correlation_id,
                ),
                before=before,
                after=after,
            )
            create_audit_event(db, event, company_id=classification.company_id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def get_fiscal_classification_audit(
    db: Session,
    classification_id: str,
) -> list[dict[str, Any]]:
    _get_classification_db_or_raise(db, classification_id)

    events = list_audit_events_for_entity(
        db,
        entity_type=AuditEntityType.FISCAL_CLASSIFICATION.value,
        entity_id=classification_id,
        limit=100,
        offset=0,
    )

    return [_audit_event_to_legacy_fiscal_dict(event) for event in events]


def _audit_event_to_legacy_fiscal_dict(event: Any) -> dict[str, Any]:
    data = audit_event_db_to_dict(event)
    data["action"] = data.get("event_type")
    return data


def get_fiscal_rules() -> dict[str, Any]:
    return {
        "module": "fiscal_classification",
        "block": "Bloco 4 — Classificação Fiscal e Tributária",
        "scope": "Cadastro, parametrização, vigência e auditoria de classificações fiscais.",
        "not_in_scope": [
            "cálculo oficial de imposto",
            "apuração de IBS/CBS/IS",
            "split payment operacional",
            "emissão fiscal homologada",
            "integração oficial Receita/SEFAZ/CGIBS",
        ],
        "id_prefixes": {
            "profile": "fprof_",
            "classification": "fclass_",
            "company": "emp_",
        },
        "profile_types": [item.value for item in FiscalProfileType],
        "applies_to": [item.value for item in FiscalAppliesTo],
        "tax_regimes": [item.value for item in TaxRegimeScope],
        "statuses": [item.value for item in FiscalRecordStatus],
        "sources": [item.value for item in FiscalSourceType],
        "classification_fields": {
            "current_tax_fields": [
                "ncm",
                "nbs",
                "cfop_default",
                "cst_icms",
                "cst_pis",
                "cst_cofins",
            ],
            "tax_reform_fields": [
                "cst_ibs_cbs",
                "cclass_trib",
                "subject_to_ibs_cbs",
                "subject_to_is",
            ],
            "validity_fields": [
                "valid_from",
                "valid_to",
                "source",
                "source_reference",
            ],
        },
        "business_rules": [
            "Toda classificação fiscal pertence a uma empresa existente.",
            "company_id deve usar prefixo emp_.",
            "fiscal_profiles.company_id possui chave estrangeira para companies.id.",
            "fiscal_classifications.company_id possui chave estrangeira para companies.id.",
            "Perfil fiscal usa prefixo fprof_.",
            "Classificação fiscal usa prefixo fclass_.",
            "Produto deve informar NCM.",
            "Serviço deve informar NBS.",
            "NCM, NBS, CFOP, CST e cClassTrib são strings, não números.",
            "valid_to não pode ser anterior a valid_from.",
            "O Bloco 4 não calcula imposto oficial.",
            "Alterações relevantes geram auditoria persistente.",
            "Listagens aceitam limit/offset para evitar carregar tabela inteira.",
        ],
    }


def get_fiscal_diagnostics(db: Session) -> dict[str, Any]:
    total_profiles = count_fiscal_profiles(db)
    total_classifications = count_fiscal_classifications(db)

    return {
        "module": "fiscal_classification",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "id_prefixes": {
            "profile": "fprof",
            "classification": "fclass",
            "company": "emp",
        },
        "database_tables": [
            "fiscal_profiles",
            "fiscal_classifications",
        ],
        "audit_enabled": True,
        "audit_persistence": "audit_events",
        "total_profiles": total_profiles,
        "total_classifications": total_classifications,
        "total_profile_audit_events": count_audit_events_for_company(db),
        "total_classification_audit_events": count_audit_events_for_company(db),
        "available_operations": [
            "create_fiscal_profile",
            "list_fiscal_profiles",
            "get_fiscal_profile",
            "update_fiscal_profile",
            "get_fiscal_profile_audit",
            "create_fiscal_classification",
            "list_fiscal_classifications",
            "get_fiscal_classification",
            "update_fiscal_classification",
            "get_fiscal_classification_audit",
            "get_fiscal_rules",
            "get_fiscal_diagnostics",
        ],
        "technical_notes": [
            "O módulo Fiscal Classification foi migrado para PostgreSQL no Bloco 4.5.",
            "A camada service.py usa repository.py como fronteira de persistência.",
            "fiscal_profiles.company_id e fiscal_classifications.company_id possuem chave estrangeira real para companies.id.",
            "fiscal_classifications.fiscal_profile_id referencia fiscal_profiles.id quando informado.",
            "Criação e alteração de perfil/classificação geram auditoria persistente.",
            "Listagens aceitam limit/offset para não carregar tabela inteira.",
            "NCM, NBS, CFOP, CST IBS/CBS e cClassTrib são colunas reais porque são filtros fiscais relevantes.",
            "O módulo organiza cadastro fiscal; não calcula imposto oficial e não substitui contador.",
        ],
    }


def clear_fiscal_classification_memory_store() -> None:
    """Compatibilidade temporária com testes antigos do período em memória.

    O Bloco 4.5 não usa mais store autoritativo em memória para Fiscal Classification.
    """
    return None
