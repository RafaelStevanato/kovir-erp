from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.cash.db_models import FinancialAccountBalanceDB, FinancialMovementDB, SettlementDB
from app.modules.financial.db_models import FinancialAccountDB


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def settlement_to_dict(row: SettlementDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "direction": row.direction,
        "settlement_type": row.settlement_type,
        "financial_title_id": row.financial_title_id,
        "participant_id": row.participant_id,
        "financial_account_id": row.financial_account_id,
        "payment_method_id": row.payment_method_id,
        "settlement_date": _iso(row.settlement_date),
        "competency_date": _iso(row.competency_date),
        "received_amount": format(_money(row.received_amount), "f"),
        "discount_amount": format(_money(row.discount_amount), "f"),
        "interest_amount": format(_money(row.interest_amount), "f"),
        "penalty_amount": format(_money(row.penalty_amount), "f"),
        "fee_amount": format(_money(row.fee_amount), "f"),
        "title_settled_amount": format(_money(row.title_settled_amount), "f"),
        "movement_amount": format(_money(row.movement_amount), "f"),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "evidence_reference": row.evidence_reference,
        "notes": row.notes,
        "status": row.status,
        "reversal_of_settlement_id": row.reversal_of_settlement_id,
        "reversed_at": _iso(row.reversed_at),
        "metadata": row.metadata_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def movement_to_dict(row: FinancialMovementDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "direction": row.direction,
        "movement_type": row.movement_type,
        "movement_date": _iso(row.movement_date),
        "amount": format(_money(row.amount), "f"),
        "currency": row.currency,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "settlement_id": row.settlement_id,
        "financial_title_id": row.financial_title_id,
        "participant_id": row.participant_id,
        "description": row.description,
        "status": row.status,
        "reconciliation_status": row.reconciliation_status,
        "reversal_of_movement_id": row.reversal_of_movement_id,
        "metadata": row.metadata_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def balance_to_dict(row: FinancialAccountBalanceDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "current_balance_amount": format(_money(row.current_balance_amount), "f"),
        "last_movement_id": row.last_movement_id,
        "updated_at": _iso(row.updated_at),
    }


def create_settlement(db: Session, **data: Any) -> SettlementDB:
    row = SettlementDB(**data)
    db.add(row)
    db.flush()
    return row


def create_movement(db: Session, **data: Any) -> FinancialMovementDB:
    row = FinancialMovementDB(**data)
    db.add(row)
    db.flush()
    return row


def get_settlement(db: Session, settlement_id: str) -> SettlementDB | None:
    return db.scalar(select(SettlementDB).where(SettlementDB.id == settlement_id))


def get_settlement_for_update(db: Session, settlement_id: str) -> SettlementDB | None:
    return db.scalar(select(SettlementDB).where(SettlementDB.id == settlement_id).with_for_update())


def get_settlement_by_source(db: Session, *, company_id: str, source_type: str, source_id: str) -> SettlementDB | None:
    return db.scalar(select(SettlementDB).where(SettlementDB.company_id == company_id, SettlementDB.source_type == source_type, SettlementDB.source_id == source_id))


def get_movement_by_source(db: Session, *, company_id: str, source_type: str, source_id: str) -> FinancialMovementDB | None:
    return db.scalar(select(FinancialMovementDB).where(FinancialMovementDB.company_id == company_id, FinancialMovementDB.source_type == source_type, FinancialMovementDB.source_id == source_id))


def get_movement_for_update(db: Session, movement_id: str) -> FinancialMovementDB | None:
    return db.scalar(select(FinancialMovementDB).where(FinancialMovementDB.id == movement_id).with_for_update())


def get_reversal_movement_by_original_for_update(db: Session, movement_id: str) -> FinancialMovementDB | None:
    return db.scalar(
        select(FinancialMovementDB)
        .where(
            FinancialMovementDB.reversal_of_movement_id == movement_id,
            FinancialMovementDB.status == "posted",
        )
        .with_for_update()
    )


def get_posted_movement_by_settlement_for_update(db: Session, settlement_id: str) -> FinancialMovementDB | None:
    return db.scalar(
        select(FinancialMovementDB)
        .where(
            FinancialMovementDB.settlement_id == settlement_id,
            FinancialMovementDB.source_type == "settlement",
            FinancialMovementDB.status == "posted",
        )
        .with_for_update()
    )


def get_balance_for_update(db: Session, *, company_id: str, financial_account_id: str) -> FinancialAccountBalanceDB | None:
    return db.scalar(select(FinancialAccountBalanceDB).where(FinancialAccountBalanceDB.company_id == company_id, FinancialAccountBalanceDB.financial_account_id == financial_account_id).with_for_update())


def create_balance(db: Session, **data: Any) -> FinancialAccountBalanceDB:
    row = FinancialAccountBalanceDB(**data)
    db.add(row)
    db.flush()
    return row


def list_settlements(
    db: Session,
    *,
    company_id: str,
    financial_title_id: str | None = None,
    financial_account_id: str | None = None,
    payment_method_id: str | None = None,
    status: str | None = None,
    settlement_from: Any | None = None,
    settlement_to: Any | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SettlementDB]:
    stmt = select(SettlementDB).where(SettlementDB.company_id == company_id)
    if financial_title_id:
        stmt = stmt.where(SettlementDB.financial_title_id == financial_title_id)
    if financial_account_id:
        stmt = stmt.where(SettlementDB.financial_account_id == financial_account_id)
    if payment_method_id == "__none__":
        stmt = stmt.where(SettlementDB.payment_method_id.is_(None))
    elif payment_method_id:
        stmt = stmt.where(SettlementDB.payment_method_id == payment_method_id)
    if status:
        stmt = stmt.where(SettlementDB.status == status)
    if settlement_from:
        stmt = stmt.where(SettlementDB.settlement_date >= settlement_from)
    if settlement_to:
        stmt = stmt.where(SettlementDB.settlement_date <= settlement_to)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                SettlementDB.id.ilike(like),
                SettlementDB.financial_title_id.ilike(like),
                SettlementDB.participant_id.ilike(like),
                SettlementDB.financial_account_id.ilike(like),
                SettlementDB.payment_method_id.ilike(like),
                SettlementDB.evidence_reference.ilike(like),
                SettlementDB.notes.ilike(like),
                SettlementDB.source_type.ilike(like),
                SettlementDB.source_id.ilike(like),
            )
        )
    safe_limit = min(max(int(limit or 50), 1), 200)
    safe_offset = max(int(offset or 0), 0)
    return list(db.scalars(stmt.order_by(SettlementDB.settlement_date.desc(), SettlementDB.created_at.desc()).limit(safe_limit).offset(safe_offset)))


def list_movements(
    db: Session,
    *,
    company_id: str,
    financial_account_id: str | None = None,
    direction: str | None = None,
    movement_type: str | None = None,
    status: str | None = None,
    reconciliation_status: str | None = None,
    movement_from: Any | None = None,
    movement_to: Any | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FinancialMovementDB]:
    stmt = select(FinancialMovementDB).where(FinancialMovementDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(FinancialMovementDB.financial_account_id == financial_account_id)
    if direction:
        stmt = stmt.where(FinancialMovementDB.direction == direction)
    if movement_type:
        stmt = stmt.where(FinancialMovementDB.movement_type == movement_type)
    if status:
        stmt = stmt.where(FinancialMovementDB.status == status)
    if reconciliation_status:
        stmt = stmt.where(FinancialMovementDB.reconciliation_status == reconciliation_status)
    if movement_from:
        stmt = stmt.where(FinancialMovementDB.movement_date >= movement_from)
    if movement_to:
        stmt = stmt.where(FinancialMovementDB.movement_date <= movement_to)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                FinancialMovementDB.id.ilike(like),
                FinancialMovementDB.description.ilike(like),
                FinancialMovementDB.source_type.ilike(like),
                FinancialMovementDB.source_id.ilike(like),
                FinancialMovementDB.settlement_id.ilike(like),
                FinancialMovementDB.financial_title_id.ilike(like),
                FinancialMovementDB.participant_id.ilike(like),
                FinancialMovementDB.financial_account_id.ilike(like),
            )
        )
    safe_limit = min(max(int(limit or 50), 1), 200)
    safe_offset = max(int(offset or 0), 0)
    return list(db.scalars(stmt.order_by(FinancialMovementDB.movement_date.desc(), FinancialMovementDB.created_at.desc()).limit(safe_limit).offset(safe_offset)))


def list_balances(db: Session, *, company_id: str, financial_account_id: str | None = None) -> list[FinancialAccountBalanceDB]:
    stmt = select(FinancialAccountBalanceDB).where(FinancialAccountBalanceDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(FinancialAccountBalanceDB.financial_account_id == financial_account_id)
    return list(db.scalars(stmt.order_by(FinancialAccountBalanceDB.updated_at.desc())))


def summary_by_company(db: Session, *, company_id: str) -> dict[str, Any]:
    active_settlements = db.scalar(select(func.coalesce(func.sum(SettlementDB.received_amount), 0)).where(SettlementDB.company_id == company_id, SettlementDB.status == "active"))
    active_discounts = db.scalar(select(func.coalesce(func.sum(SettlementDB.discount_amount), 0)).where(SettlementDB.company_id == company_id, SettlementDB.status == "active"))
    active_movement_filters = (
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reconciliation_status != "reversed",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
    )
    inflows = db.scalar(select(func.coalesce(func.sum(FinancialMovementDB.amount), 0)).where(*active_movement_filters, FinancialMovementDB.direction == "inflow"))
    outflows = db.scalar(select(func.coalesce(func.sum(FinancialMovementDB.amount), 0)).where(*active_movement_filters, FinancialMovementDB.direction == "outflow"))
    pending_reconciliation = db.scalar(select(func.count(FinancialMovementDB.id)).where(*active_movement_filters, FinancialMovementDB.reconciliation_status == "pending"))
    pending_reconciliation_amount = db.scalar(select(func.coalesce(func.sum(FinancialMovementDB.amount), 0)).where(*active_movement_filters, FinancialMovementDB.reconciliation_status == "pending"))
    account_rows = db.execute(
        select(
            FinancialAccountDB.id,
            FinancialAccountDB.opening_balance_amount,
            FinancialAccountBalanceDB.current_balance_amount,
        )
        .outerjoin(
            FinancialAccountBalanceDB,
            (FinancialAccountBalanceDB.company_id == FinancialAccountDB.company_id)
            & (FinancialAccountBalanceDB.financial_account_id == FinancialAccountDB.id),
        )
        .where(
            FinancialAccountDB.company_id == company_id,
            FinancialAccountDB.status == "active",
            FinancialAccountDB.deleted_at.is_(None),
        )
    ).all()
    internal_balance_total = sum((_money(row.current_balance_amount) if row.current_balance_amount is not None else _money(row.opening_balance_amount)) for row in account_rows)
    materialized_balance_count = sum(1 for row in account_rows if row.current_balance_amount is not None)
    return {
        "company_id": company_id,
        "received_amount": format(_money(active_settlements), "f"),
        "discount_amount": format(_money(active_discounts), "f"),
        "inflow_amount": format(_money(inflows), "f"),
        "outflow_amount": format(_money(outflows), "f"),
        "net_internal_balance_delta": format(_money(inflows) - _money(outflows), "f"),
        "pending_reconciliation_count": int(pending_reconciliation or 0),
        "pending_reconciliation_amount": format(_money(pending_reconciliation_amount), "f"),
        "internal_balance_total": format(_money(internal_balance_total), "f"),
        "financial_account_count": len(account_rows),
        "materialized_balance_count": materialized_balance_count,
    }
