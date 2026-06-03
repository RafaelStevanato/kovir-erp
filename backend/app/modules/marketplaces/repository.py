from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.marketplaces.db_models import (
    MarketplaceAccountDB,
    MarketplaceExternalOrderDB,
    MarketplacePaymentEventDB,
    MarketplaceSyncRunDB,
)
from app.modules.marketplaces.models import MarketplaceAccount, MarketplaceSyncRun


def marketplace_account_db_to_domain(account: MarketplaceAccountDB) -> MarketplaceAccount:
    return MarketplaceAccount(
        id=account.id,
        company_id=account.company_id,
        participant_id=account.participant_id,
        provider_code=account.provider_code,
        provider_name=account.provider_name,
        provider_type=account.provider_type,
        display_name=account.display_name,
        environment=account.environment,
        status=account.status,
        connection_status=account.connection_status,
        external_account_id=account.external_account_id,
        last_sync_at=account.last_sync_at,
        credential_metadata=account.credential_metadata_json,
        settings=account.settings_json,
        notes=account.notes,
        created_at=account.created_at,
        updated_at=account.updated_at,
        deleted_at=account.deleted_at,
    )


def marketplace_account_db_to_dict(account: MarketplaceAccountDB) -> dict[str, Any]:
    domain = marketplace_account_db_to_domain(account)
    return {
        "id": domain.id,
        "company_id": domain.company_id,
        "participant_id": domain.participant_id,
        "provider_code": domain.provider_code,
        "provider_name": domain.provider_name,
        "provider_type": domain.provider_type,
        "display_name": domain.display_name,
        "environment": domain.environment,
        "status": domain.status,
        "connection_status": domain.connection_status,
        "external_account_id": domain.external_account_id,
        "last_sync_at": domain.last_sync_at.isoformat() if domain.last_sync_at else None,
        "credential_metadata": domain.credential_metadata,
        "settings": domain.settings,
        "notes": domain.notes,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }


def marketplace_sync_run_db_to_domain(sync_run: MarketplaceSyncRunDB) -> MarketplaceSyncRun:
    return MarketplaceSyncRun(
        id=sync_run.id,
        company_id=sync_run.company_id,
        marketplace_account_id=sync_run.marketplace_account_id,
        sync_type=sync_run.sync_type,
        status=sync_run.status,
        started_at=sync_run.started_at,
        finished_at=sync_run.finished_at,
        external_cursor=sync_run.external_cursor,
        records_found=sync_run.records_found,
        records_created=sync_run.records_created,
        records_updated=sync_run.records_updated,
        records_failed=sync_run.records_failed,
        summary=sync_run.summary_json,
        error=sync_run.error_json,
        created_at=sync_run.created_at,
    )


def marketplace_sync_run_db_to_dict(sync_run: MarketplaceSyncRunDB) -> dict[str, Any]:
    domain = marketplace_sync_run_db_to_domain(sync_run)
    return {
        "id": domain.id,
        "company_id": domain.company_id,
        "marketplace_account_id": domain.marketplace_account_id,
        "sync_type": domain.sync_type,
        "status": domain.status,
        "started_at": domain.started_at.isoformat() if domain.started_at else None,
        "finished_at": domain.finished_at.isoformat() if domain.finished_at else None,
        "external_cursor": domain.external_cursor,
        "records_found": domain.records_found,
        "records_created": domain.records_created,
        "records_updated": domain.records_updated,
        "records_failed": domain.records_failed,
        "summary": domain.summary,
        "error": domain.error,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
    }


def create_marketplace_account(db: Session, **data: Any) -> MarketplaceAccountDB:
    account = MarketplaceAccountDB(**data)
    db.add(account)
    db.flush()
    return account


def get_marketplace_account(db: Session, account_id: str) -> MarketplaceAccountDB | None:
    return db.scalar(
        select(MarketplaceAccountDB).where(
            MarketplaceAccountDB.id == account_id,
            MarketplaceAccountDB.deleted_at.is_(None),
        )
    )


def get_marketplace_account_by_provider(
    db: Session,
    *,
    company_id: str,
    provider_code: str,
) -> MarketplaceAccountDB | None:
    return db.scalar(
        select(MarketplaceAccountDB).where(
            MarketplaceAccountDB.company_id == company_id,
            MarketplaceAccountDB.provider_code == provider_code,
            MarketplaceAccountDB.deleted_at.is_(None),
        ).order_by(MarketplaceAccountDB.created_at.asc(), MarketplaceAccountDB.id.asc())
    )


def list_marketplace_accounts(
    db: Session,
    *,
    company_id: str,
    provider_code: str | None = None,
    provider_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MarketplaceAccountDB]:
    statement: Select[tuple[MarketplaceAccountDB]] = select(MarketplaceAccountDB).where(
        MarketplaceAccountDB.company_id == company_id,
        MarketplaceAccountDB.deleted_at.is_(None),
    )
    if provider_code:
        statement = statement.where(MarketplaceAccountDB.provider_code == provider_code)
    if provider_type:
        statement = statement.where(MarketplaceAccountDB.provider_type == provider_type)
    if status:
        statement = statement.where(MarketplaceAccountDB.status == status)
    statement = statement.order_by(MarketplaceAccountDB.provider_name.asc(), MarketplaceAccountDB.display_name.asc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def update_marketplace_account(db: Session, account: MarketplaceAccountDB, **changes: Any) -> MarketplaceAccountDB:
    for key, value in changes.items():
        if value is not None and hasattr(account, key):
            setattr(account, key, value)
    db.add(account)
    db.flush()
    return account


def count_marketplace_accounts(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(MarketplaceAccountDB).where(MarketplaceAccountDB.deleted_at.is_(None))
    if company_id:
        statement = statement.where(MarketplaceAccountDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_marketplace_accounts_by_connection(db: Session, *, company_id: str) -> dict[str, int]:
    rows = db.execute(
        select(MarketplaceAccountDB.connection_status, func.count())
        .where(MarketplaceAccountDB.company_id == company_id, MarketplaceAccountDB.deleted_at.is_(None))
        .group_by(MarketplaceAccountDB.connection_status)
    ).all()
    return {str(status): int(total or 0) for status, total in rows}


def create_marketplace_sync_run(db: Session, **data: Any) -> MarketplaceSyncRunDB:
    sync_run = MarketplaceSyncRunDB(**data)
    db.add(sync_run)
    db.flush()
    return sync_run


def list_marketplace_sync_runs(
    db: Session,
    *,
    company_id: str,
    marketplace_account_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[MarketplaceSyncRunDB]:
    statement: Select[tuple[MarketplaceSyncRunDB]] = select(MarketplaceSyncRunDB).where(MarketplaceSyncRunDB.company_id == company_id)
    if marketplace_account_id:
        statement = statement.where(MarketplaceSyncRunDB.marketplace_account_id == marketplace_account_id)
    statement = statement.order_by(MarketplaceSyncRunDB.started_at.desc(), MarketplaceSyncRunDB.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def count_sync_runs(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(MarketplaceSyncRunDB)
    if company_id:
        statement = statement.where(MarketplaceSyncRunDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_external_orders(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(MarketplaceExternalOrderDB)
    if company_id:
        statement = statement.where(MarketplaceExternalOrderDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_payment_events(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(MarketplacePaymentEventDB)
    if company_id:
        statement = statement.where(MarketplacePaymentEventDB.company_id == company_id)
    return int(db.scalar(statement) or 0)
