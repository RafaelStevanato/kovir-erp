from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.repository import get_company as repository_get_company
from app.modules.marketplaces.repository import get_marketplace_account_by_provider
from app.modules.mercado_pago.repository import (
    count_accounts,
    count_by_connection,
    count_chargebacks,
    count_oauth_states,
    count_payments,
    count_preferences,
    count_refunds,
    count_releases,
    count_webhooks,
    create_mercado_pago_account,
    get_mercado_pago_account,
    get_mercado_pago_account_by_company,
    list_chargebacks,
    list_payments,
    list_preferences,
    list_refunds,
    list_releases,
    list_webhooks,
    mercado_pago_account_db_to_dict,
    update_mercado_pago_account as repository_update_account,
)
from app.modules.mercado_pago.schemas import MercadoPagoAccountUpdate
from app.modules.participants.repository import get_participant as repository_get_participant
from app.shared.audit import AuditContext, AuditEntityType, AuditSource, build_created_event, build_updated_event
from app.shared.audit_repository import audit_event_db_to_dict, count_audit_events_for_company, create_audit_event, list_audit_events_for_entity
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


DEFAULT_ACCOUNT_METADATA: dict[str, Any] = {
    "has_access_token": False,
    "has_refresh_token": False,
    "has_client_secret": False,
    "token_storage": "not_implemented",
    "secret_policy": "Não salvar tokens ou client_secret em texto puro. Usar cofre/criptografia em bloco futuro.",
}

DEFAULT_WEBHOOK_SETTINGS: dict[str, Any] = {
    "webhook_endpoint_planned": "/mercado-pago/webhooks",
    "signature_validation": "planned",
    "idempotency_strategy": "external_event_id + resource_type + resource_id",
    "topics_planned": ["payment", "merchant_order", "chargebacks", "refunds"],
}

DEFAULT_PAYMENT_SETTINGS: dict[str, Any] = {
    "supported_future_flows": ["checkout_pro", "checkout_api", "pix", "card", "boleto"],
    "idempotency_required": True,
    "sale_link_field": "sale_id",
    "payment_plan_link_field": "sale_payment_plan_id",
    "external_reference_strategy": "sale_id ou sale_payment_plan_id",
}

DEFAULT_RECONCILIATION_SETTINGS: dict[str, Any] = {
    "future_sources": ["payments_search", "released_money_report", "account_money_report", "webhooks"],
    "do_not_create_financial_movement_automatically": True,
    "planned_links": ["sale_payment_plans", "financial_titles", "financial_movements", "reconciliation_matches"],
}


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
        raise ValueError("Participante vinculado ao Mercado Pago não encontrado para esta empresa.")


def ensure_default_mercado_pago_account(db: Session, company_id: str) -> None:
    _assert_company_exists(db, company_id)
    existing = get_mercado_pago_account_by_company(db, company_id)
    if existing is not None:
        return

    now = utc_now()
    generic_account = get_marketplace_account_by_provider(db, company_id=company_id, provider_code="mercado_pago")
    create_mercado_pago_account(
        db,
        id=generate_id("mpacc"),
        company_id=company_id,
        participant_id=None,
        marketplace_account_id=generic_account.id if generic_account else None,
        display_name="Mercado Pago",
        environment="sandbox",
        status="draft",
        connection_status="not_connected",
        external_user_id=None,
        collector_id=None,
        application_id=None,
        public_key_fingerprint=None,
        credentials_status="missing",
        webhook_status="not_configured",
        last_healthcheck_at=None,
        last_sync_at=None,
        credential_metadata_json=DEFAULT_ACCOUNT_METADATA,
        webhook_settings_json=DEFAULT_WEBHOOK_SETTINGS,
        payment_settings_json=DEFAULT_PAYMENT_SETTINGS,
        reconciliation_settings_json=DEFAULT_RECONCILIATION_SETTINGS,
        notes="Conta Mercado Pago preparada para OAuth, pagamentos, webhooks, repasses, reembolsos, chargebacks e conciliação futura.",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.commit()


def get_or_create_mercado_pago_account(db: Session, *, company_id: str) -> dict[str, Any]:
    ensure_default_mercado_pago_account(db, company_id)
    account = get_mercado_pago_account_by_company(db, company_id)
    if account is None:
        raise ValueError("Conta Mercado Pago não encontrada.")
    return mercado_pago_account_db_to_dict(account)


def update_mercado_pago_account(
    db: Session,
    *,
    account_id: str,
    payload: MercadoPagoAccountUpdate,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.API,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    assert_valid_id(account_id, "mpacc")
    account = get_mercado_pago_account(db, account_id)
    if account is None:
        raise ValueError("Conta Mercado Pago não encontrada.")
    _assert_participant_belongs_to_company(db, company_id=account.company_id, participant_id=payload.participant_id)

    before = mercado_pago_account_db_to_dict(account)
    changes: dict[str, Any] = {}
    field_map = {
        "participant_id": "participant_id",
        "marketplace_account_id": "marketplace_account_id",
        "display_name": "display_name",
        "environment": "environment",
        "status": "status",
        "connection_status": "connection_status",
        "external_user_id": "external_user_id",
        "collector_id": "collector_id",
        "application_id": "application_id",
        "public_key_fingerprint": "public_key_fingerprint",
        "credentials_status": "credentials_status",
        "webhook_status": "webhook_status",
        "notes": "notes",
    }
    data = payload.model_dump(exclude_unset=True)
    for payload_key, db_key in field_map.items():
        if payload_key in data:
            changes[db_key] = data[payload_key]
    if "credential_metadata" in data:
        changes["credential_metadata_json"] = data["credential_metadata"]
    if "webhook_settings" in data:
        changes["webhook_settings_json"] = data["webhook_settings"]
    if "payment_settings" in data:
        changes["payment_settings_json"] = data["payment_settings"]
    if "reconciliation_settings" in data:
        changes["reconciliation_settings_json"] = data["reconciliation_settings"]
    changes["updated_at"] = utc_now()

    updated = repository_update_account(db, account, **changes)
    after = mercado_pago_account_db_to_dict(updated)
    context = AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    event = build_updated_event(
        entity_type=AuditEntityType.MERCADO_PAGO_ACCOUNT,
        entity_id=account.id,
        context=context,
        before=before,
        after=after,
        expected_entity_prefix="mpacc",
    )
    create_audit_event(db, event, company_id=account.company_id)
    db.commit()
    return after


def mark_mercado_pago_preconfigured(
    db: Session,
    *,
    company_id: str,
    actor_id: str | None = None,
    source: AuditSource = AuditSource.API,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    account = get_or_create_mercado_pago_account(db, company_id=company_id)
    payload = MercadoPagoAccountUpdate(
        status="active",
        connection_status="configured",
        credentials_status="metadata_only",
        webhook_status="configured",
        credential_metadata={**DEFAULT_ACCOUNT_METADATA, "has_basic_metadata": True, "token_storage": "future_vault_required"},
    )
    return update_mercado_pago_account(
        db,
        account_id=account["id"],
        payload=payload,
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def get_mercado_pago_audit_events(db: Session, account_id: str) -> list[dict[str, Any]]:
    assert_valid_id(account_id, "mpacc")
    if get_mercado_pago_account(db, account_id) is None:
        raise ValueError("Conta Mercado Pago não encontrada.")
    rows = list_audit_events_for_entity(db, "mercado_pago_account", account_id, limit=100, offset=0)
    return [audit_event_db_to_dict(row) for row in rows]


def get_mercado_pago_diagnostics(db: Session, company_id: str | None = None) -> dict[str, Any]:
    if company_id:
        ensure_default_mercado_pago_account(db, company_id)
    return {
        "module": "mercado_pago",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "integration_status": "prepared_not_connected",
        "database_tables": [
            "mercado_pago_accounts",
            "mercado_pago_oauth_states",
            "mercado_pago_webhook_events",
            "mercado_pago_checkout_preferences",
            "mercado_pago_payments",
            "mercado_pago_releases",
            "mercado_pago_refunds",
            "mercado_pago_chargebacks",
        ],
        "total_accounts": count_accounts(db, company_id),
        "accounts_by_connection_status": count_by_connection(db, company_id) if company_id else {},
        "total_oauth_states": count_oauth_states(db, company_id),
        "total_webhook_events": count_webhooks(db, company_id),
        "total_checkout_preferences": count_preferences(db, company_id),
        "total_payments": count_payments(db, company_id),
        "total_releases": count_releases(db, company_id),
        "total_refunds": count_refunds(db, company_id),
        "total_chargebacks": count_chargebacks(db, company_id),
        "total_audit_events": count_audit_events_for_company(db, company_id),
        "technical_notes": [
            "Mercado Pago agora possui módulo próprio, separado da aba genérica Marketplaces.",
            "A estrutura diferencia pagamento externo, plano de pagamento da venda, título financeiro futuro, baixa e conciliação.",
            "Webhooks entram em mercado_pago_webhook_events antes de alterar qualquer entidade financeira.",
            "Pagamentos normalizados entram em mercado_pago_payments e podem se vincular a sale_payment_plans.",
            "Repasses/liberações ficam em mercado_pago_releases para futura conciliação com conta financeira.",
            "Reembolsos e chargebacks ficam separados para não distorcer recebíveis e fluxo de caixa.",
            "Tokens e client_secret não são armazenados neste bloco; integração real exige cofre/criptografia.",
        ],
    }


def get_mercado_pago_rules() -> dict[str, Any]:
    return {
        "module": "mercado_pago",
        "principles": [
            "Mercado Pago é gateway/intermediador financeiro, não marketplace de pedidos como Shopee.",
            "Pagamento aprovado no Mercado Pago não deve ser tratado automaticamente como conciliação bancária.",
            "Webhook não é fonte única de verdade; deve ser idempotente, auditável e reconciliável com consultas/relatórios.",
            "Reembolso, chargeback, taxa, repasse e liberação de dinheiro precisam ser entidades separadas.",
            "access_token, refresh_token e client_secret não devem ser gravados em texto puro.",
        ],
        "prepared_flow": [
            "sales / sale_payment_plans",
            "mercado_pago_checkout_preferences, se a venda gerar link/preferência futura",
            "mercado_pago_webhook_events para notificações recebidas",
            "mercado_pago_payments para pagamento normalizado",
            "mercado_pago_releases para liberações/repasses",
            "financial_titles futuro",
            "financial_movements futuro",
            "reconciliation_matches futuro",
        ],
        "future_api_surfaces": [
            "OAuth/autorização",
            "Payments API",
            "Payment Search",
            "Webhooks",
            "Refunds",
            "Chargebacks",
            "Released money report",
            "Account money report",
            "Split payments, se o Kovir virar marketplace/plataforma",
        ],
    }


def list_mercado_pago_payments(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_payments(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))


def list_mercado_pago_releases(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_releases(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))


def list_mercado_pago_webhooks(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_webhooks(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))


def list_mercado_pago_refunds(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_refunds(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))


def list_mercado_pago_chargebacks(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_chargebacks(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))


def list_mercado_pago_checkout_preferences(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    return list_preferences(db, company_id=company_id, limit=max(1, min(limit, 200)), offset=max(0, offset))
