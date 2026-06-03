from dataclasses import is_dataclass
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.models import (
    Company,
    CompanyAddress,
    CompanyFinancialSettings,
    CompanyFiscalSettings,
    CompanyOperationalSettings,
    CompanyStatus,
    FiscalEnvironment,
    TaxRegime,
    company_to_dict,
)
from app.modules.company.repository import (
    company_db_to_domain,
    count_companies,
    create_company as repository_create_company,
    get_company as repository_get_company,
    get_company_by_cnpj,
    list_companies as repository_list_companies,
    update_company as repository_update_company,
)
from app.modules.company.schemas import CompanyCreate, CompanyUpdate
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


def _to_company_status(value: Any) -> CompanyStatus:
    if isinstance(value, CompanyStatus):
        return value

    return CompanyStatus(value)


def _to_tax_regime(value: Any) -> TaxRegime:
    if isinstance(value, TaxRegime):
        return value

    return TaxRegime(value)


def _to_fiscal_environment(value: Any) -> FiscalEnvironment:
    if isinstance(value, FiscalEnvironment):
        return value

    return FiscalEnvironment(value)


def _create_audit_context(
    actor_id: str | None = None,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditContext:
    return AuditContext(
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _get_company_db_or_raise(db: Session, company_id: str):
    _assert_company_id(company_id)

    company = repository_get_company(db, company_id)

    if company is None:
        raise ValueError("Empresa não encontrada.")

    return company


def _assert_unique_cnpj(
    db: Session,
    cnpj: str | None,
    ignored_company_id: str | None = None,
) -> None:
    if cnpj is None:
        return

    existing = get_company_by_cnpj(db, cnpj)

    if existing is None:
        return

    if ignored_company_id is not None and existing.id == ignored_company_id:
        return

    raise ValueError("Já existe uma empresa cadastrada com este CNPJ.")


def _build_address(data: dict[str, Any] | None) -> CompanyAddress:
    if data is None:
        return CompanyAddress()

    return CompanyAddress(**data)


def _build_fiscal_settings(data: dict[str, Any] | None) -> CompanyFiscalSettings:
    if data is None:
        return CompanyFiscalSettings()

    payload = dict(data)

    if "tax_regime" in payload:
        payload["tax_regime"] = _to_tax_regime(payload["tax_regime"])

    if "fiscal_environment" in payload:
        payload["fiscal_environment"] = _to_fiscal_environment(
            payload["fiscal_environment"]
        )

    return CompanyFiscalSettings(**payload)


def _build_financial_settings(data: dict[str, Any] | None) -> CompanyFinancialSettings:
    if data is None:
        return CompanyFinancialSettings()

    return CompanyFinancialSettings(**data)


def _build_operational_settings(
    data: dict[str, Any] | None,
) -> CompanyOperationalSettings:
    if data is None:
        return CompanyOperationalSettings()

    return CompanyOperationalSettings(**data)


def _build_company_from_create(payload: CompanyCreate) -> Company:
    data = payload.model_dump()

    now = utc_now()

    company = Company(
        id=generate_id("emp"),
        legal_name=data["legal_name"],
        trade_name=data.get("trade_name"),
        cnpj=data.get("cnpj"),
        email=data.get("email"),
        phone=data.get("phone"),
        responsible_name=data.get("responsible_name"),
        status=_to_company_status(data.get("status", CompanyStatus.ACTIVE)),
        address=_build_address(data.get("address")),
        fiscal_settings=_build_fiscal_settings(data.get("fiscal_settings")),
        financial_settings=_build_financial_settings(data.get("financial_settings")),
        operational_settings=_build_operational_settings(
            data.get("operational_settings")
        ),
        created_at=now,
        updated_at=now,
    )

    return company


def _merge_dataclass(target: Any, changes: dict[str, Any]) -> None:
    if not is_dataclass(target):
        raise ValueError("Objeto alvo deve ser dataclass.")

    for field_name, value in changes.items():
        if not hasattr(target, field_name):
            continue

        if field_name == "tax_regime":
            value = _to_tax_regime(value)

        if field_name == "fiscal_environment":
            value = _to_fiscal_environment(value)

        setattr(target, field_name, value)


def _apply_company_update(company: Company, payload: CompanyUpdate) -> None:
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise ValueError("Nenhum campo informado para atualização.")

    scalar_fields = {
        "legal_name",
        "trade_name",
        "cnpj",
        "email",
        "phone",
        "responsible_name",
        "status",
    }

    for field_name in scalar_fields:
        if field_name not in data:
            continue

        value = data[field_name]

        if field_name == "legal_name" and value is None:
            raise ValueError("Razão social não pode ser removida.")

        if field_name == "status" and value is not None:
            value = _to_company_status(value)

        setattr(company, field_name, value)

    if "address" in data and data["address"] is not None:
        _merge_dataclass(company.address, data["address"])

    if "fiscal_settings" in data and data["fiscal_settings"] is not None:
        _merge_dataclass(company.fiscal_settings, data["fiscal_settings"])

    if "financial_settings" in data and data["financial_settings"] is not None:
        _merge_dataclass(company.financial_settings, data["financial_settings"])

    if "operational_settings" in data and data["operational_settings"] is not None:
        _merge_dataclass(company.operational_settings, data["operational_settings"])

    company.updated_at = utc_now()


def create_company(
    db: Session,
    payload: CompanyCreate,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    company = _build_company_from_create(payload)

    _assert_unique_cnpj(db, company.cnpj)

    try:
        repository_create_company(db, company)

        context = _create_audit_context(
            actor_id=actor_id,
            source=source,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        event = build_created_event(
            entity_type=AuditEntityType.COMPANY,
            entity_id=company.id,
            context=context,
            after=company_to_dict(company),
        )

        create_audit_event(db, event, company_id=company.id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return company_to_dict(company)


def list_companies(db: Session, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    companies = repository_list_companies(db, limit=limit, offset=offset)

    return [
        company_to_dict(company_db_to_domain(company))
        for company in companies
    ]


def get_company(db: Session, company_id: str) -> dict[str, Any]:
    company_db = _get_company_db_or_raise(db, company_id)
    company = company_db_to_domain(company_db)

    return company_to_dict(company)


def update_company(
    db: Session,
    company_id: str,
    payload: CompanyUpdate,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    company_db = _get_company_db_or_raise(db, company_id)
    company = company_db_to_domain(company_db)

    before = company_to_dict(company)

    data = payload.model_dump(exclude_unset=True)

    if "cnpj" in data:
        _assert_unique_cnpj(db, data["cnpj"], ignored_company_id=company_id)

    _apply_company_update(company, payload)

    after = company_to_dict(company)

    try:
        repository_update_company(db, company_db, company)

        if before != after:
            context = _create_audit_context(
                actor_id=actor_id,
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
            )

            event = build_updated_event(
                entity_type=AuditEntityType.COMPANY,
                entity_id=company.id,
                context=context,
                before=before,
                after=after,
            )

            create_audit_event(db, event, company_id=company.id)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return after


def get_company_audit_events(db: Session, company_id: str) -> list[dict[str, Any]]:
    _get_company_db_or_raise(db, company_id)

    events = list_audit_events_for_entity(
        db,
        entity_type=AuditEntityType.COMPANY.value,
        entity_id=company_id,
        limit=100,
        offset=0,
    )

    return [audit_event_db_to_dict(event) for event in events]


def get_company_rules() -> dict[str, Any]:
    return {
        "entity": "company",
        "entity_type": AuditEntityType.COMPANY.value,
        "id_prefix": "emp",
        "id_format": "emp_<uuid-v4>",
        "status": [status.value for status in CompanyStatus],
        "tax_regimes": [tax_regime.value for tax_regime in TaxRegime],
        "fiscal_environments": [
            fiscal_environment.value
            for fiscal_environment in FiscalEnvironment
        ],
        "rules": [
            "Empresa usa prefixo emp.",
            "Nunca usar company como prefixo de ID.",
            "CNPJ deve ser string e suportar 14 caracteres alfanuméricos.",
            "Datas técnicas devem usar UTC.",
            "Criação e alteração de empresa devem gerar auditoria persistente.",
            "Configurações fiscais, financeiras e operacionais devem ser explícitas.",
            "Mesmo no MVP com uma empresa, a modelagem deve estar preparada para multiempresa.",
        ],
    }


def get_company_diagnostics(db: Session, *, company_id: str | None = None) -> dict[str, Any]:
    if company_id is not None:
        _get_company_db_or_raise(db, company_id)
        total_companies = 1
        total_audit_events = count_audit_events_for_company(db, company_id=company_id)
    else:
        total_companies = count_companies(db)
        total_audit_events = count_audit_events_for_company(db)

    return {
        "module": "company",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "id_prefix": "emp",
        "audit_enabled": True,
        "audit_persistence": "audit_events",
        "total_companies": total_companies,
        "total_audit_events": total_audit_events,
        "available_operations": [
            "create_company",
            "list_companies",
            "get_company",
            "update_company",
            "get_company_audit_events",
        ],
        "technical_notes": [
            "O módulo Company foi o primeiro migrado para PostgreSQL no Bloco 4.5.",
            "A camada service.py usa repository.py como fronteira de persistência.",
            "Criação e alteração de empresa geram auditoria persistente.",
            "Listagem já aceita limit/offset para não carregar tabela inteira.",
        ],
    }


def clear_company_memory_store() -> None:
    """Compatibilidade temporária com testes antigos do período em memória.

    O Bloco 4.5 não usa mais store autoritativo em memória para Company.
    """
    return None
