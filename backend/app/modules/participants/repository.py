from __future__ import annotations

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.participants.db_models import ParticipantDB
from app.modules.participants.models import (
    Participant,
    ParticipantAddress,
    ParticipantFinancialSettings,
    ParticipantFiscalSettings,
    ParticipantStatus,
    ParticipantType,
    PersonType,
    TaxpayerType,
    participant_to_dict,
)


def _safe_participant_type(value: str) -> ParticipantType:
    return ParticipantType(value)


def _safe_person_type(value: str) -> PersonType:
    legacy_values = {
        "legal": PersonType.COMPANY,
        "juridical": PersonType.COMPANY,
        "juridica": PersonType.COMPANY,
        "company": PersonType.COMPANY,
        "natural": PersonType.INDIVIDUAL,
        "physical": PersonType.INDIVIDUAL,
        "fisica": PersonType.INDIVIDUAL,
        "individual": PersonType.INDIVIDUAL,
    }
    if value in legacy_values:
        return legacy_values[value]
    return PersonType(value)


def _safe_participant_status(value: str) -> ParticipantStatus:
    return ParticipantStatus(value)


def _safe_taxpayer_type(value: str | None) -> TaxpayerType:
    if value is None:
        return TaxpayerType.UNKNOWN
    return TaxpayerType(value)


def _address_from_json(data: dict | None) -> ParticipantAddress | None:
    if data is None:
        return None

    return ParticipantAddress(
        street=data.get("street"),
        number=data.get("number"),
        complement=data.get("complement"),
        district=data.get("district"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        country=data.get("country") or "BR",
        ibge_municipality_code=data.get("ibge_municipality_code"),
    )


def _fiscal_settings_from_json(data: dict | None) -> ParticipantFiscalSettings | None:
    if data is None:
        return None

    return ParticipantFiscalSettings(
        taxpayer_type=_safe_taxpayer_type(data.get("taxpayer_type")),
        tax_regime=data.get("tax_regime"),
        main_cnae=data.get("main_cnae"),
        state_registration=data.get("state_registration"),
        municipal_registration=data.get("municipal_registration"),
        suframa_registration=data.get("suframa_registration"),
        is_foreign=bool(data.get("is_foreign", False)),
        fiscal_notes=data.get("fiscal_notes"),
    )


def _financial_settings_from_json(data: dict | None) -> ParticipantFinancialSettings | None:
    if data is None:
        return None

    return ParticipantFinancialSettings(
        default_payment_method=data.get("default_payment_method"),
        default_payment_terms=data.get("default_payment_terms"),
        bank_name=data.get("bank_name"),
        bank_branch=data.get("bank_branch"),
        bank_account=data.get("bank_account"),
        pix_key=data.get("pix_key"),
        credit_limit=data.get("credit_limit"),
        payment_priority=data.get("payment_priority"),
    )


def participant_db_to_domain(participant: ParticipantDB) -> Participant:
    return Participant(
        id=participant.id,
        company_id=participant.company_id,
        participant_type=_safe_participant_type(participant.participant_type),
        person_type=_safe_person_type(participant.person_type),
        name=participant.name,
        trade_name=participant.trade_name,
        document=participant.document,
        email=participant.email,
        phone=participant.phone,
        secondary_phone=participant.secondary_phone,
        website=participant.website,
        contact_name=participant.contact_name,
        contact_phone=participant.contact_phone,
        contact_email=participant.contact_email,
        origin=participant.origin,
        tags=participant.tags,
        status=_safe_participant_status(participant.status),
        address=_address_from_json(participant.address_json),
        fiscal_settings=_fiscal_settings_from_json(participant.fiscal_settings_json),
        financial_settings=_financial_settings_from_json(participant.financial_settings_json),
        notes=participant.notes,
        created_at=participant.created_at,
        updated_at=participant.updated_at,
    )


def _apply_domain_to_db(participant_db: ParticipantDB, participant: Participant) -> None:
    data = participant_to_dict(participant)

    participant_db.company_id = participant.company_id
    participant_db.participant_type = participant.participant_type.value
    participant_db.person_type = participant.person_type.value
    participant_db.name = participant.name
    participant_db.trade_name = participant.trade_name
    participant_db.document = participant.document
    participant_db.email = participant.email
    participant_db.phone = participant.phone
    participant_db.secondary_phone = participant.secondary_phone
    participant_db.website = participant.website
    participant_db.contact_name = participant.contact_name
    participant_db.contact_phone = participant.contact_phone
    participant_db.contact_email = participant.contact_email
    participant_db.origin = participant.origin
    participant_db.tags = participant.tags
    participant_db.status = participant.status.value
    participant_db.address_json = data.get("address")
    participant_db.fiscal_settings_json = data.get("fiscal_settings")
    participant_db.financial_settings_json = data.get("financial_settings")
    participant_db.notes = participant.notes
    participant_db.created_at = participant.created_at
    participant_db.updated_at = participant.updated_at


def create_participant(db: Session, participant: Participant) -> ParticipantDB:
    participant_db = ParticipantDB(id=participant.id)
    _apply_domain_to_db(participant_db, participant)
    db.add(participant_db)
    db.flush()
    return participant_db


def update_participant(
    db: Session,
    participant_db: ParticipantDB,
    participant: Participant,
) -> ParticipantDB:
    _apply_domain_to_db(participant_db, participant)
    db.add(participant_db)
    db.flush()
    return participant_db


def _apply_participant_filters(
    statement: Select,
    *,
    company_id: str | None = None,
    participant_type: str | None = None,
    person_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> Select:
    statement = statement.where(
        ParticipantDB.deleted_at.is_(None)
    )

    if company_id is not None:
        statement = statement.where(ParticipantDB.company_id == company_id)

    if participant_type is not None:
        statement = statement.where(ParticipantDB.participant_type == participant_type)

    if person_type is not None:
        person_type_values = {
            PersonType.COMPANY.value: ["company", "legal", "juridical", "juridica"],
            PersonType.INDIVIDUAL.value: ["individual", "natural", "physical", "fisica"],
        }.get(person_type, [person_type])
        statement = statement.where(ParticipantDB.person_type.in_(person_type_values))

    if status is not None:
        statement = statement.where(ParticipantDB.status == status)

    if search is not None and search.strip():
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                ParticipantDB.name.ilike(pattern),
                ParticipantDB.trade_name.ilike(pattern),
                ParticipantDB.document.ilike(pattern),
                ParticipantDB.email.ilike(pattern),
                ParticipantDB.contact_name.ilike(pattern),
            )
        )

    return statement


def list_participants(
    db: Session,
    *,
    company_id: str | None = None,
    participant_type: str | None = None,
    person_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ParticipantDB]:
    statement: Select[tuple[ParticipantDB]] = _apply_participant_filters(
        select(ParticipantDB),
        company_id=company_id,
        participant_type=participant_type,
        person_type=person_type,
        status=status,
        search=search,
    )

    statement = (
        statement
        .order_by(ParticipantDB.created_at.desc(), ParticipantDB.id.desc())
        .limit(limit)
        .offset(offset)
    )

    return list(db.scalars(statement).all())


def get_participant(db: Session, participant_id: str) -> ParticipantDB | None:
    statement = select(ParticipantDB).where(
        ParticipantDB.id == participant_id,
        ParticipantDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_participant_by_document(
    db: Session,
    *,
    company_id: str,
    document: str,
) -> ParticipantDB | None:
    statement = select(ParticipantDB).where(
        ParticipantDB.company_id == company_id,
        ParticipantDB.document == document,
        ParticipantDB.deleted_at.is_(None),
    )

    return db.scalar(statement)


def count_participants(
    db: Session,
    *,
    company_id: str | None = None,
    participant_type: str | None = None,
    person_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> int:
    statement = _apply_participant_filters(
        select(func.count()).select_from(ParticipantDB),
        company_id=company_id,
        participant_type=participant_type,
        person_type=person_type,
        status=status,
        search=search,
    )

    return int(db.scalar(statement) or 0)


def count_participants_by_status(db: Session, *, company_id: str) -> dict[str, int]:
    rows = db.execute(
        select(ParticipantDB.status, func.count())
        .where(
            ParticipantDB.company_id == company_id,
            ParticipantDB.deleted_at.is_(None),
        )
        .group_by(ParticipantDB.status)
    ).all()
    return {str(status): int(total or 0) for status, total in rows}


def count_participants_by_type(db: Session, *, company_id: str) -> dict[str, int]:
    rows = db.execute(
        select(ParticipantDB.participant_type, func.count())
        .where(
            ParticipantDB.company_id == company_id,
            ParticipantDB.deleted_at.is_(None),
        )
        .group_by(ParticipantDB.participant_type)
    ).all()
    return {str(participant_type): int(total or 0) for participant_type, total in rows}


def get_participant_quality_counts(db: Session, *, company_id: str) -> dict[str, int]:
    statement = select(
        func.count().label("total"),
        func.sum(
            case(
                (
                    or_(ParticipantDB.document.is_(None), ParticipantDB.document == ""),
                    0,
                ),
                else_=1,
            )
        ).label("with_document"),
        func.sum(case((ParticipantDB.address_json.is_(None), 0), else_=1)).label(
            "with_address"
        ),
        func.sum(
            case(
                (
                    or_(
                        ParticipantDB.email.is_(None),
                        ParticipantDB.email == "",
                        ParticipantDB.phone.is_(None),
                        ParticipantDB.phone == "",
                    ),
                    0,
                ),
                else_=1,
            )
        ).label("with_contact"),
        func.sum(
            case(
                (ParticipantDB.status.in_(["blocked", "inactive"]), 0),
                else_=1,
            )
        ).label("operational"),
    ).where(
        ParticipantDB.company_id == company_id,
        ParticipantDB.deleted_at.is_(None),
    )

    row = db.execute(statement).one()
    return {
        "total": int(row.total or 0),
        "with_document": int(row.with_document or 0),
        "with_address": int(row.with_address or 0),
        "with_contact": int(row.with_contact or 0),
        "operational": int(row.operational or 0),
    }
