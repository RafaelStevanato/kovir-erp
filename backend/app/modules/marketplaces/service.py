from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.repository import get_company as repository_get_company
from app.modules.marketplaces.models import (
    MarketplaceConnectionStatus,
    MarketplaceEnvironment,
    MarketplaceProviderCode,
    MarketplaceProviderType,
    MarketplaceAccountStatus,
)
from app.modules.marketplaces.repository import (
    count_external_orders,
    count_marketplace_accounts,
    count_marketplace_accounts_by_connection,
    count_payment_events,
    count_sync_runs,
    create_marketplace_account,
    get_marketplace_account,
    get_marketplace_account_by_provider,
    list_marketplace_accounts as repository_list_accounts,
    list_marketplace_sync_runs as repository_list_sync_runs,
    marketplace_account_db_to_dict,
    marketplace_sync_run_db_to_dict,
    update_marketplace_account as repository_update_account,
)
from app.modules.marketplaces.schemas import MarketplaceAccountCreate, MarketplaceAccountUpdate
from app.modules.participants.repository import get_participant as repository_get_participant
from app.shared.audit import AuditContext, AuditEntityType, AuditSource, build_created_event, build_updated_event
from app.shared.audit_repository import create_audit_event, count_audit_events_for_company, list_audit_events_for_entity, audit_event_db_to_dict
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


DEFAULT_PROVIDERS: list[dict[str, Any]] = [
    {
        "provider_code": MarketplaceProviderCode.MERCADO_PAGO.value,
        "provider_name": "Mercado Pago",
        "provider_type": MarketplaceProviderType.PAYMENT_GATEWAY.value,
        "display_name": "Mercado Pago",
        "environment": MarketplaceEnvironment.SANDBOX.value,
        "status": MarketplaceAccountStatus.DRAFT.value,
        "connection_status": MarketplaceConnectionStatus.NOT_CONNECTED.value,
        "settings_json": {
            "future_scopes": ["payments", "settlements", "refunds", "chargebacks"],
            "future_financial_links": ["sale_payment_plans", "financial_titles", "financial_movements", "reconciliation_matches"],
            "secret_storage": "future_vault_or_encrypted_column",
            "notes": "Preparado para integração futura. Não armazenar access_token em texto puro.",
        },
        "credential_metadata_json": {
            "has_client_id": False,
            "has_client_secret": False,
            "has_access_token": False,
            "has_refresh_token": False,
            "sensitive_storage_ready": False,
        },
        "notes": "Gateway/intermediador preparado para pagamentos, taxas, repasses e conciliação futura.",
    },
    {
        "provider_code": MarketplaceProviderCode.SHOPEE.value,
        "provider_name": "Shopee",
        "provider_type": MarketplaceProviderType.MARKETPLACE.value,
        "display_name": "Shopee",
        "environment": MarketplaceEnvironment.SANDBOX.value,
        "status": MarketplaceAccountStatus.DRAFT.value,
        "connection_status": MarketplaceConnectionStatus.NOT_CONNECTED.value,
        "settings_json": {
            "future_scopes": ["orders", "catalog", "payments", "settlements", "returns"],
            "future_operational_links": ["marketplace_external_orders", "sales", "sale_items", "catalog_items", "stock_movements"],
            "future_financial_links": ["sale_payment_plans", "financial_titles", "financial_movements", "reconciliation_matches"],
            "secret_storage": "future_vault_or_encrypted_column",
            "notes": "Preparado para importação de pedidos, repasses e vínculo com vendas do Kovir.",
        },
        "credential_metadata_json": {
            "has_partner_id": False,
            "has_partner_key": False,
            "has_shop_id": False,
            "has_access_token": False,
            "has_refresh_token": False,
            "sensitive_storage_ready": False,
        },
        "notes": "Marketplace preparado para pedidos externos, venda, estoque, taxas e repasses futuros.",
    },
]


def _assert_company_exists(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    if repository_get_company(db, company_id) is None:
        raise ValueError("Empresa não encontrada.")


def _assert_participant_belongs_to_company(db: Session, *, company_id: str, participant_id: str | None) -> None:
    if participant_id is None:
        return
    assert_valid_id(participant_id, "part")
    participant = repository_get_participant(db, participant_id)
    if participant is None or participant.company_id != company_id:
        raise ValueError("Participante vinculado ao marketplace não encontrado para esta empresa.")


def ensure_default_marketplace_accounts(db: Session, company_id: str) -> None:
    _assert_company_exists(db, company_id)
    now = utc_now()
    created_any = False
    for provider in DEFAULT_PROVIDERS:
        existing = get_marketplace_account_by_provider(db, company_id=company_id, provider_code=provider["provider_code"])
        if existing is not None:
            continue
        create_marketplace_account(
            db,
            id=generate_id("mkacc"),
            company_id=company_id,
            participant_id=None,
            provider_code=provider["provider_code"],
            provider_name=provider["provider_name"],
            provider_type=provider["provider_type"],
            display_name=provider["display_name"],
            environment=provider["environment"],
            status=provider["status"],
            connection_status=provider["connection_status"],
            external_account_id=None,
            credential_metadata_json=provider["credential_metadata_json"],
            settings_json=provider["settings_json"],
            notes=provider["notes"],
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        created_any = True
    if created_any:
        db.commit()


def list_marketplace_accounts(
    db: Session,
    *,
    company_id: str,
    provider_code: str | None = None,
    provider_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    ensure_default_marketplace_accounts(db, company_id)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    accounts = repository_list_accounts(
        db,
        company_id=company_id,
        provider_code=provider_code,
        provider_type=provider_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [marketplace_account_db_to_dict(account) for account in accounts]


def create_marketplace_account_from_payload(
    db: Session,
    *,
    payload: MarketplaceAccountCreate,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.API,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)
    _assert_participant_belongs_to_company(db, company_id=payload.company_id, participant_id=payload.participant_id)
    provider = next((item for item in DEFAULT_PROVIDERS if item["provider_code"] == payload.provider_code), None)
    if provider is None:
        raise ValueError("Provedor de marketplace/gateway inválido.")
    now = utc_now()
    account = create_marketplace_account(
        db,
        id=generate_id("mkacc"),
        company_id=payload.company_id,
        participant_id=payload.participant_id,
        provider_code=payload.provider_code,
        provider_name=provider["provider_name"],
        provider_type=provider["provider_type"],
        display_name=payload.display_name or provider["display_name"],
        environment=payload.environment,
        status=payload.status,
        connection_status=payload.connection_status,
        external_account_id=payload.external_account_id,
        credential_metadata_json=payload.credential_metadata or provider["credential_metadata_json"],
        settings_json=payload.settings or provider["settings_json"],
        notes=payload.notes,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    result = marketplace_account_db_to_dict(account)
    context = AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    event = build_created_event(
        entity_type=AuditEntityType.MARKETPLACE_ACCOUNT,
        entity_id=account.id,
        context=context,
        after=result,
        expected_entity_prefix="mkacc",
    )
    create_audit_event(db, event, company_id=payload.company_id)
    db.commit()
    return result


def update_marketplace_account(
    db: Session,
    *,
    account_id: str,
    payload: MarketplaceAccountUpdate,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.API,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    assert_valid_id(account_id, "mkacc")
    account = get_marketplace_account(db, account_id)
    if account is None:
        raise ValueError("Conta de marketplace não encontrada.")
    _assert_participant_belongs_to_company(db, company_id=account.company_id, participant_id=payload.participant_id)
    before = marketplace_account_db_to_dict(account)
    changes: dict[str, Any] = {}
    if payload.participant_id is not None:
        changes["participant_id"] = payload.participant_id
    if payload.display_name is not None:
        changes["display_name"] = payload.display_name
    if payload.environment is not None:
        changes["environment"] = payload.environment
    if payload.status is not None:
        changes["status"] = payload.status
    if payload.connection_status is not None:
        changes["connection_status"] = payload.connection_status
    if payload.external_account_id is not None:
        changes["external_account_id"] = payload.external_account_id
    if payload.credential_metadata is not None:
        changes["credential_metadata_json"] = payload.credential_metadata
    if payload.settings is not None:
        changes["settings_json"] = payload.settings
    if payload.notes is not None:
        changes["notes"] = payload.notes
    changes["updated_at"] = utc_now()
    updated = repository_update_account(db, account, **changes)
    after = marketplace_account_db_to_dict(updated)
    context = AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    event = build_updated_event(
        entity_type=AuditEntityType.MARKETPLACE_ACCOUNT,
        entity_id=account.id,
        context=context,
        before=before,
        after=after,
        expected_entity_prefix="mkacc",
    )
    create_audit_event(db, event, company_id=account.company_id)
    db.commit()
    return after


def list_marketplace_sync_runs(
    db: Session,
    *,
    company_id: str,
    marketplace_account_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    if marketplace_account_id is not None:
        assert_valid_id(marketplace_account_id, "mkacc")
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    rows = repository_list_sync_runs(db, company_id=company_id, marketplace_account_id=marketplace_account_id, limit=limit, offset=offset)
    return [marketplace_sync_run_db_to_dict(row) for row in rows]


def get_marketplace_audit_events(db: Session, account_id: str) -> list[dict[str, Any]]:
    assert_valid_id(account_id, "mkacc")
    if get_marketplace_account(db, account_id) is None:
        raise ValueError("Conta de marketplace não encontrada.")
    rows = list_audit_events_for_entity(db, "marketplace_account", account_id, limit=100, offset=0)
    return [audit_event_db_to_dict(row) for row in rows]


def get_marketplaces_diagnostics(db: Session, company_id: str | None = None) -> dict[str, Any]:
    if company_id:
        ensure_default_marketplace_accounts(db, company_id)
    return {
        "module": "marketplaces",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "database_tables": [
            "marketplace_accounts",
            "marketplace_sync_runs",
            "marketplace_external_orders",
            "marketplace_payment_events",
        ],
        "future_integrations": ["shopee", "other_marketplaces"],
        "total_accounts": count_marketplace_accounts(db, company_id),
        "accounts_by_connection_status": count_marketplace_accounts_by_connection(db, company_id=company_id) if company_id else {},
        "total_sync_runs": count_sync_runs(db, company_id),
        "total_external_orders": count_external_orders(db, company_id),
        "total_payment_events": count_payment_events(db, company_id),
        "total_audit_events": count_audit_events_for_company(db, company_id),
        "technical_notes": [
            "Mercado Pago foi separado para o módulo dedicado /mercado-pago.",
            "Shopee foi modelada como marketplace/canal de venda.",
            "A aba Marketplaces ainda não faz OAuth nem chamada externa real.",
            "Credenciais sensíveis não devem ser salvas em texto puro; usar cofre/criptografia em bloco futuro.",
            "Pedidos externos entram primeiro como marketplace_external_orders e só depois viram sales/sale_items.",
            "Pagamentos externos entram como marketplace_payment_events e só depois vinculam baixa, movimento financeiro e conciliação.",
        ],
    }


def get_marketplaces_providers() -> list[dict[str, Any]]:
    return [
        {
            "provider_code": provider["provider_code"],
            "provider_name": provider["provider_name"],
            "provider_type": provider["provider_type"],
            "default_environment": provider["environment"],
            "future_scopes": provider["settings_json"].get("future_scopes", []),
            "notes": provider["notes"],
        }
        for provider in DEFAULT_PROVIDERS
    ]


def get_marketplaces_rules() -> dict[str, Any]:
    return {
        "module": "marketplaces",
        "principles": [
            "Integração externa não deve gravar pedido diretamente como venda sem camada intermediária.",
            "Marketplace/gateway deve pertencer à empresa e possuir status próprio.",
            "Credenciais sensíveis não devem ser armazenadas em texto puro.",
            "Pedido externo, pagamento externo, título financeiro, baixa e conciliação são conceitos diferentes.",
            "Toda sincronização futura deve gerar histórico em marketplace_sync_runs.",
        ],
        "prepared_flow": [
            "marketplace_accounts",
            "marketplace_sync_runs",
            "marketplace_external_orders",
            "sales/sale_items",
            "sale_payment_plans",
            "marketplace_payment_events",
            "financial_titles futuro",
            "financial_movements futuro",
            "reconciliation_matches futuro",
        ],
        "providers": get_marketplaces_providers(),
    }
