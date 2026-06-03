from __future__ import annotations

from dataclasses import fields
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.repository import get_company as repository_get_company
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
from app.modules.participants.repository import (
    count_participants,
    count_participants_by_status,
    count_participants_by_type,
    create_participant as repository_create_participant,
    get_participant as repository_get_participant,
    get_participant_by_document,
    get_participant_quality_counts,
    list_participants as repository_list_participants,
    participant_db_to_domain,
    update_participant as repository_update_participant,
)
from app.modules.participants.schemas import ParticipantCreate, ParticipantUpdate
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
    if isinstance(value, Enum):
        return value.value

    return value


def _to_participant_type(value: ParticipantType | str) -> ParticipantType:
    if isinstance(value, ParticipantType):
        return value

    return ParticipantType(value)


def _to_person_type(value: PersonType | str) -> PersonType:
    if isinstance(value, PersonType):
        return value

    legacy_values = {
        "legal": PersonType.COMPANY,
        "juridical": PersonType.COMPANY,
        "juridica": PersonType.COMPANY,
        "natural": PersonType.INDIVIDUAL,
        "physical": PersonType.INDIVIDUAL,
        "fisica": PersonType.INDIVIDUAL,
    }
    if value in legacy_values:
        return legacy_values[value]

    return PersonType(value)


def _to_participant_status(value: ParticipantStatus | str) -> ParticipantStatus:
    if isinstance(value, ParticipantStatus):
        return value

    return ParticipantStatus(value)


def _to_taxpayer_type(value: TaxpayerType | str) -> TaxpayerType:
    if isinstance(value, TaxpayerType):
        return value

    return TaxpayerType(value)


def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _assert_participant_id(participant_id: str) -> None:
    assert_valid_id(participant_id, "part")


def _assert_actor_id(actor_id: str | None) -> None:
    if actor_id is not None:
        assert_valid_id(actor_id, "user")


def _assert_company_exists(db: Session, company_id: str) -> None:
    _assert_company_id(company_id)

    company = repository_get_company(db, company_id)

    if company is None:
        raise ValueError("Empresa vinculada ao participante não encontrada.")


def _get_participant_db_or_raise(
    db: Session,
    participant_id: str,
    *,
    expected_company_id: str | None = None,
):
    _assert_participant_id(participant_id)

    participant_db = repository_get_participant(db, participant_id)

    if participant_db is None:
        raise ValueError("Participante não encontrado.")

    if expected_company_id is not None and participant_db.company_id != expected_company_id:
        raise ValueError("Participante não encontrado.")

    return participant_db


def _assert_unique_document(
    db: Session,
    *,
    company_id: str,
    document: str | None,
    ignored_participant_id: str | None = None,
) -> None:
    if document is None:
        return

    participant = get_participant_by_document(
        db,
        company_id=company_id,
        document=document,
    )

    if participant is None:
        return

    if ignored_participant_id is not None and participant.id == ignored_participant_id:
        return

    raise ValueError(
        "Já existe um participante cadastrado com este documento nesta empresa."
    )


def _build_address(data: dict[str, Any]) -> ParticipantAddress:
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


def _build_fiscal_settings(data: dict[str, Any]) -> ParticipantFiscalSettings:
    return ParticipantFiscalSettings(
        taxpayer_type=_to_taxpayer_type(data.get("taxpayer_type")),
        tax_regime=data.get("tax_regime"),
        main_cnae=data.get("main_cnae"),
        state_registration=data.get("state_registration"),
        municipal_registration=data.get("municipal_registration"),
        suframa_registration=data.get("suframa_registration"),
        is_foreign=bool(data.get("is_foreign", False)),
        fiscal_notes=data.get("fiscal_notes"),
    )


def _build_financial_settings(data: dict[str, Any]) -> ParticipantFinancialSettings:
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


def _build_participant_from_create(payload: ParticipantCreate) -> Participant:
    data = payload.model_dump()

    now = utc_now()

    participant = Participant(
        id=generate_id("part"),
        company_id=data["company_id"],
        participant_type=_to_participant_type(data["participant_type"]),
        person_type=_to_person_type(data["person_type"]),
        name=data["name"],
        trade_name=data.get("trade_name"),
        document=data.get("document"),
        email=str(data["email"]) if data.get("email") is not None else None,
        phone=data.get("phone"),
        secondary_phone=data.get("secondary_phone"),
        website=data.get("website"),
        contact_name=data.get("contact_name"),
        contact_phone=data.get("contact_phone"),
        contact_email=str(data["contact_email"]) if data.get("contact_email") is not None else None,
        origin=_enum_value(data.get("origin")),
        tags=data.get("tags") or [],
        status=_to_participant_status(data.get("status", ParticipantStatus.ACTIVE)),
        address=_build_address(data["address"]) if data.get("address") else None,
        fiscal_settings=_build_fiscal_settings(data["fiscal_settings"]) if data.get("fiscal_settings") else None,
        financial_settings=_build_financial_settings(data["financial_settings"]) if data.get("financial_settings") else None,
        notes=data.get("notes"),
        created_at=now,
        updated_at=now,
    )

    return participant


def _merge_dataclass(target: Any, changes: dict[str, Any]) -> None:
    valid_fields = {field.name for field in fields(target)}

    for key, value in changes.items():
        if key not in valid_fields:
            continue

        setattr(target, key, value)


def _create_audit_context(
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditContext:
    _assert_actor_id(actor_id)

    if not isinstance(source, AuditSource):
        source = AuditSource(source)

    return AuditContext(
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def _apply_participant_update(
    participant: Participant,
    payload: ParticipantUpdate,
) -> None:
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise ValueError("Nenhum dado enviado para atualização.")

    if "company_id" in data and data["company_id"] != participant.company_id:
        raise ValueError("Não é permitido alterar a empresa do participante.")

    if "participant_type" in data:
        participant.participant_type = _to_participant_type(data["participant_type"])

    if "person_type" in data:
        participant.person_type = _to_person_type(data["person_type"])

    if "name" in data:
        if data["name"] is None:
            raise ValueError("Nome/Razão social do participante não pode ser removido.")

        participant.name = data["name"]

    if "trade_name" in data:
        participant.trade_name = data["trade_name"]

    if "document" in data:
        participant.document = data["document"]

    if "email" in data:
        participant.email = str(data["email"]) if data["email"] is not None else None

    if "phone" in data:
        participant.phone = data["phone"]

    if "status" in data:
        participant.status = _to_participant_status(data["status"])

    if "notes" in data:
        participant.notes = data["notes"]

    if "secondary_phone" in data:
        participant.secondary_phone = data["secondary_phone"]

    if "website" in data:
        participant.website = data["website"]

    if "contact_name" in data:
        participant.contact_name = data["contact_name"]

    if "contact_phone" in data:
        participant.contact_phone = data["contact_phone"]

    if "contact_email" in data:
        participant.contact_email = str(data["contact_email"]) if data["contact_email"] is not None else None

    if "origin" in data:
        participant.origin = _enum_value(data["origin"])

    if "tags" in data and data["tags"] is not None:
        participant.tags = data["tags"]

    if "address" in data and data["address"] is not None:
        if participant.address is None:
            participant.address = _build_address(data["address"])
        else:
            _merge_dataclass(participant.address, data["address"])

    if "fiscal_settings" in data and data["fiscal_settings"] is not None:
        fiscal_data = dict(data["fiscal_settings"])

        if "taxpayer_type" in fiscal_data:
            fiscal_data["taxpayer_type"] = _to_taxpayer_type(
                fiscal_data["taxpayer_type"]
            )

        if participant.fiscal_settings is None:
            participant.fiscal_settings = _build_fiscal_settings(fiscal_data)
        else:
            _merge_dataclass(participant.fiscal_settings, fiscal_data)

    if "financial_settings" in data and data["financial_settings"] is not None:
        if participant.financial_settings is None:
            participant.financial_settings = _build_financial_settings(
                data["financial_settings"]
            )
        else:
            _merge_dataclass(
                participant.financial_settings,
                data["financial_settings"],
            )

    participant.updated_at = utc_now()


def create_participant(
    db: Session,
    payload: ParticipantCreate,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)

    participant = _build_participant_from_create(payload)

    _assert_unique_document(
        db,
        company_id=participant.company_id,
        document=participant.document,
    )

    after = participant_to_dict(participant)

    try:
        repository_create_participant(db, participant)

        context = _create_audit_context(
            actor_id=actor_id,
            source=source,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        event = build_created_event(
            entity_type=AuditEntityType.PARTICIPANT,
            entity_id=participant.id,
            context=context,
            after=after,
        )

        create_audit_event(db, event, company_id=participant.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def list_participants(
    db: Session,
    *,
    company_id: str | None = None,
    participant_type: ParticipantType | str | None = None,
    person_type: PersonType | str | None = None,
    status: ParticipantStatus | str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    participant_type_value = None
    person_type_value = None
    status_value = None

    if company_id is not None:
        _assert_company_exists(db, company_id)

    if participant_type is not None:
        participant_type_value = _to_participant_type(participant_type).value

    if person_type is not None:
        person_type_value = _to_person_type(person_type).value

    if status is not None:
        status_value = _to_participant_status(status).value

    participants = repository_list_participants(
        db,
        company_id=company_id,
        participant_type=participant_type_value,
        person_type=person_type_value,
        status=status_value,
        search=search,
        limit=limit,
        offset=offset,
    )

    return [
        participant_to_dict(participant_db_to_domain(participant))
        for participant in participants
    ]


def count_filtered_participants(
    db: Session,
    *,
    company_id: str | None = None,
    participant_type: ParticipantType | str | None = None,
    person_type: PersonType | str | None = None,
    status: ParticipantStatus | str | None = None,
    search: str | None = None,
) -> int:
    participant_type_value = None
    person_type_value = None
    status_value = None

    if company_id is not None:
        _assert_company_exists(db, company_id)

    if participant_type is not None:
        participant_type_value = _to_participant_type(participant_type).value

    if person_type is not None:
        person_type_value = _to_person_type(person_type).value

    if status is not None:
        status_value = _to_participant_status(status).value

    return count_participants(
        db,
        company_id=company_id,
        participant_type=participant_type_value,
        person_type=person_type_value,
        status=status_value,
        search=search,
    )


def get_participant(
    db: Session,
    participant_id: str,
    *,
    expected_company_id: str | None = None,
) -> dict[str, Any]:
    participant_db = _get_participant_db_or_raise(
        db,
        participant_id,
        expected_company_id=expected_company_id,
    )

    return participant_to_dict(participant_db_to_domain(participant_db))


def update_participant(
    db: Session,
    participant_id: str,
    payload: ParticipantUpdate,
    *,
    expected_company_id: str | None = None,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    participant_db = _get_participant_db_or_raise(
        db,
        participant_id,
        expected_company_id=expected_company_id,
    )
    participant = participant_db_to_domain(participant_db)

    before = participant_to_dict(participant)

    update_data = payload.model_dump(exclude_unset=True)
    new_document = update_data.get("document", participant.document)

    _assert_unique_document(
        db,
        company_id=participant.company_id,
        document=new_document,
        ignored_participant_id=participant.id,
    )

    _apply_participant_update(participant, payload)

    after = participant_to_dict(participant)

    try:
        repository_update_participant(db, participant_db, participant)

        if before != after:
            context = _create_audit_context(
                actor_id=actor_id,
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
            )

            event = build_updated_event(
                entity_type=AuditEntityType.PARTICIPANT,
                entity_id=participant.id,
                context=context,
                before=before,
                after=after,
            )

            create_audit_event(db, event, company_id=participant.company_id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def get_participant_audit_events(
    db: Session,
    participant_id: str,
    *,
    expected_company_id: str | None = None,
) -> list[dict[str, Any]]:
    participant_db = _get_participant_db_or_raise(
        db,
        participant_id,
        expected_company_id=expected_company_id,
    )

    events = list_audit_events_for_entity(
        db,
        entity_type=AuditEntityType.PARTICIPANT.value,
        entity_id=participant_id,
        limit=100,
        offset=0,
    )

    return [audit_event_db_to_dict(event) for event in events]


def get_participant_summary(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    status_counts = count_participants_by_status(db, company_id=company_id)
    type_counts = count_participants_by_type(db, company_id=company_id)
    quality_counts = get_participant_quality_counts(db, company_id=company_id)

    return {
        "total_participants": quality_counts["total"],
        "status_counts": {
            status.value: status_counts.get(status.value, 0)
            for status in ParticipantStatus
        },
        "type_counts": {
            participant_type.value: type_counts.get(participant_type.value, 0)
            for participant_type in ParticipantType
        },
        "quality_counts": quality_counts,
        "total_audit_events": count_audit_events_for_company(db, company_id=company_id),
    }


def get_participant_rules() -> dict[str, Any]:
    return {
        "entity": "participant",
        "entity_type": AuditEntityType.PARTICIPANT.value,
        "id_prefix": "part",
        "id_format": "part_<uuid-v4>",
        "belongs_to": {
            "entity": "company",
            "id_prefix": "emp",
            "field": "company_id",
            "relationship": "participants.company_id -> companies.id",
        },
        "participant_types": [participant_type.value for participant_type in ParticipantType],
        "person_types": [person_type.value for person_type in PersonType],
        "statuses": [status.value for status in ParticipantStatus],
        "taxpayer_types": [taxpayer_type.value for taxpayer_type in TaxpayerType],
        "required_on_create": [
            "company_id",
            "participant_type",
            "person_type",
            "name",
            "document",
            "email",
            "phone",
            "address",
            "fiscal_settings",
            "financial_settings",
        ],
        "rules": [
            "Participante usa prefixo part.",
            "Participante deve pertencer a uma empresa existente com prefixo emp.",
            "participants.company_id possui chave estrangeira para companies.id.",
            "Documento deve ser string e suportar CPF/CNPJ com 11 ou 14 caracteres alfanuméricos.",
            "Documento não pode duplicar dentro da mesma empresa.",
            "Criação e alteração de participante devem gerar auditoria persistente.",
            "Não permitir alteração de company_id após criação.",
            "Participante será base para clientes, fornecedores, transportadoras, bancos, gateways, marketplaces e terceiros.",
        ],
    }


def get_participant_diagnostics(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    total_participants = count_participants(db, company_id=company_id)
    total_audit_events = count_audit_events_for_company(db, company_id=company_id)

    return {
        "module": "participants",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "id_prefix": "part",
        "company_dependency": "emp",
        "database_table": "participants",
        "audit_enabled": True,
        "audit_persistence": "audit_events",
        "total_participants": total_participants,
        "total_audit_events": total_audit_events,
        "available_operations": [
            "create_participant",
            "list_participants",
            "get_participant",
            "update_participant",
            "get_participant_audit_events",
            "get_participant_rules",
            "get_participant_diagnostics",
        ],
        "technical_notes": [
            "O módulo Participants foi migrado para PostgreSQL no Bloco 4.5.",
            "A camada service.py usa repository.py como fronteira de persistência.",
            "participants.company_id possui chave estrangeira real para companies.id.",
            "Criação e alteração de participante geram auditoria persistente.",
            "Listagem aceita limit/offset para não carregar tabela inteira.",
            "address_json, fiscal_settings_json e financial_settings_json permanecem JSONB no MVP; campos filtráveis seguem em colunas reais.",
        ],
    }


def clear_participant_memory_store() -> None:
    """Compatibilidade temporária com testes antigos do período em memória.

    O Bloco 4.5 não usa mais store autoritativo em memória para Participants.
    """
    return None
