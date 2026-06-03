from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.mercado_pago.db_models import (
    MercadoPagoAccountDB,
    MercadoPagoChargebackDB,
    MercadoPagoCheckoutPreferenceDB,
    MercadoPagoOAuthStateDB,
    MercadoPagoPaymentDB,
    MercadoPagoRefundDB,
    MercadoPagoReleaseDB,
    MercadoPagoWebhookEventDB,
)


def _as_iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def mercado_pago_account_db_to_dict(account: MercadoPagoAccountDB) -> dict[str, Any]:
    return {
        "id": account.id,
        "company_id": account.company_id,
        "participant_id": account.participant_id,
        "marketplace_account_id": account.marketplace_account_id,
        "display_name": account.display_name,
        "environment": account.environment,
        "status": account.status,
        "connection_status": account.connection_status,
        "external_user_id": account.external_user_id,
        "collector_id": account.collector_id,
        "application_id": account.application_id,
        "public_key_fingerprint": account.public_key_fingerprint,
        "credentials_status": account.credentials_status,
        "webhook_status": account.webhook_status,
        "last_healthcheck_at": _as_iso(account.last_healthcheck_at),
        "last_sync_at": _as_iso(account.last_sync_at),
        "credential_metadata": account.credential_metadata_json,
        "webhook_settings": account.webhook_settings_json,
        "payment_settings": account.payment_settings_json,
        "reconciliation_settings": account.reconciliation_settings_json,
        "notes": account.notes,
        "created_at": _as_iso(account.created_at),
        "updated_at": _as_iso(account.updated_at),
        "deleted_at": _as_iso(account.deleted_at),
    }


def simple_row_to_dict(row: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        data[column.name] = _as_iso(value)
    return data


def get_mercado_pago_account_by_company(db: Session, company_id: str) -> MercadoPagoAccountDB | None:
    statement = select(MercadoPagoAccountDB).where(
        MercadoPagoAccountDB.company_id == company_id,
        MercadoPagoAccountDB.deleted_at.is_(None),
    ).order_by(MercadoPagoAccountDB.created_at.asc(), MercadoPagoAccountDB.id.asc())
    return db.scalars(statement).first()


def get_mercado_pago_account(db: Session, account_id: str) -> MercadoPagoAccountDB | None:
    return db.get(MercadoPagoAccountDB, account_id)


def create_mercado_pago_account(db: Session, **data: Any) -> MercadoPagoAccountDB:
    account = MercadoPagoAccountDB(**data)
    db.add(account)
    db.flush()
    return account


def update_mercado_pago_account(db: Session, account: MercadoPagoAccountDB, **changes: Any) -> MercadoPagoAccountDB:
    for key, value in changes.items():
        if value is not None and hasattr(account, key):
            setattr(account, key, value)
    db.add(account)
    db.flush()
    return account


def count_accounts(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(MercadoPagoAccountDB).where(MercadoPagoAccountDB.deleted_at.is_(None))
    if company_id:
        statement = statement.where(MercadoPagoAccountDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_by_connection(db: Session, company_id: str) -> dict[str, int]:
    rows = db.execute(
        select(MercadoPagoAccountDB.connection_status, func.count())
        .where(MercadoPagoAccountDB.company_id == company_id, MercadoPagoAccountDB.deleted_at.is_(None))
        .group_by(MercadoPagoAccountDB.connection_status)
    ).all()
    return {str(status): int(total or 0) for status, total in rows}


def _count_table(db: Session, model: Any, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(model)
    if company_id:
        statement = statement.where(model.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_payments(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoPaymentDB, company_id)


def count_releases(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoReleaseDB, company_id)


def count_webhooks(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoWebhookEventDB, company_id)


def count_refunds(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoRefundDB, company_id)


def count_chargebacks(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoChargebackDB, company_id)


def count_preferences(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoCheckoutPreferenceDB, company_id)


def count_oauth_states(db: Session, company_id: str | None = None) -> int:
    return _count_table(db, MercadoPagoOAuthStateDB, company_id)


def _list_rows(db: Session, model: Any, *, company_id: str, limit: int = 50, offset: int = 0) -> list[Any]:
    statement: Select[tuple[Any]] = select(model).where(model.company_id == company_id)
    if hasattr(model, "created_at"):
        statement = statement.order_by(model.created_at.desc(), model.id.desc())
    statement = statement.limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def list_payments(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoPaymentDB, company_id=company_id, limit=limit, offset=offset)]


def list_releases(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoReleaseDB, company_id=company_id, limit=limit, offset=offset)]


def list_webhooks(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoWebhookEventDB, company_id=company_id, limit=limit, offset=offset)]


def list_refunds(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoRefundDB, company_id=company_id, limit=limit, offset=offset)]


def list_chargebacks(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoChargebackDB, company_id=company_id, limit=limit, offset=offset)]


def list_preferences(db: Session, *, company_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    return [simple_row_to_dict(row) for row in _list_rows(db, MercadoPagoCheckoutPreferenceDB, company_id=company_id, limit=limit, offset=offset)]
