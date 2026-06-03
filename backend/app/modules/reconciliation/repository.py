from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.cash.db_models import FinancialMovementDB
from app.modules.reconciliation.db_models import BankStatementImportDB, BankStatementLineDB, ReconciliationMatchDB


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def statement_import_to_dict(row: BankStatementImportDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "file_name": row.file_name,
        "statement_start_date": _iso(row.statement_start_date),
        "statement_end_date": _iso(row.statement_end_date),
        "opening_balance_amount": format(_money(row.opening_balance_amount), "f") if row.opening_balance_amount is not None else None,
        "closing_balance_amount": format(_money(row.closing_balance_amount), "f") if row.closing_balance_amount is not None else None,
        "line_count": row.line_count,
        "total_inflow_amount": format(_money(row.total_inflow_amount), "f"),
        "total_outflow_amount": format(_money(row.total_outflow_amount), "f"),
        "status": row.status,
        "notes": row.notes,
        "raw_payload": row.raw_payload_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def statement_line_to_dict(row: BankStatementLineDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "statement_import_id": row.statement_import_id,
        "external_id": row.external_id,
        "line_date": _iso(row.line_date),
        "posted_at": _iso(row.posted_at),
        "direction": row.direction,
        "amount": format(_money(row.amount), "f"),
        "description": row.description,
        "document_number": row.document_number,
        "counterparty_name": row.counterparty_name,
        "counterparty_document": row.counterparty_document,
        "bank_reference": row.bank_reference,
        "status": row.status,
        "match_confidence": row.match_confidence,
        "matched_amount": format(_money(row.matched_amount), "f"),
        "ignored_reason": row.ignored_reason,
        "raw_payload": row.raw_payload_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def reconciliation_match_to_dict(row: ReconciliationMatchDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "statement_line_id": row.statement_line_id,
        "financial_movement_id": row.financial_movement_id,
        "match_type": row.match_type,
        "matched_amount": format(_money(row.matched_amount), "f"),
        "line_amount": format(_money(row.line_amount), "f"),
        "movement_amount": format(_money(row.movement_amount), "f"),
        "difference_amount": format(_money(row.difference_amount), "f"),
        "tolerance_amount": format(_money(row.tolerance_amount), "f"),
        "status": row.status,
        "confirmation_reason": row.confirmation_reason,
        "reversed_reason": row.reversed_reason,
        "confirmed_at": _iso(row.confirmed_at),
        "reversed_at": _iso(row.reversed_at),
        "metadata": row.metadata_json,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def movement_candidate_to_dict(row: FinancialMovementDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_account_id": row.financial_account_id,
        "direction": row.direction,
        "movement_type": row.movement_type,
        "movement_date": _iso(row.movement_date),
        "amount": format(_money(row.amount), "f"),
        "source_type": row.source_type,
        "source_id": row.source_id,
        "settlement_id": row.settlement_id,
        "financial_title_id": row.financial_title_id,
        "participant_id": row.participant_id,
        "description": row.description,
        "status": row.status,
        "reconciliation_status": row.reconciliation_status,
    }


def create_statement_import(db: Session, **data: Any) -> BankStatementImportDB:
    row = BankStatementImportDB(**data)
    db.add(row)
    db.flush()
    return row


def create_statement_line(db: Session, **data: Any) -> BankStatementLineDB:
    row = BankStatementLineDB(**data)
    db.add(row)
    db.flush()
    return row


def create_reconciliation_match(db: Session, **data: Any) -> ReconciliationMatchDB:
    row = ReconciliationMatchDB(**data)
    db.add(row)
    db.flush()
    return row


def get_import_by_source(db: Session, *, company_id: str, financial_account_id: str, source_type: str, source_id: str) -> BankStatementImportDB | None:
    return db.scalar(select(BankStatementImportDB).where(BankStatementImportDB.company_id == company_id, BankStatementImportDB.financial_account_id == financial_account_id, BankStatementImportDB.source_type == source_type, BankStatementImportDB.source_id == source_id))


def get_line_by_external_id(db: Session, *, company_id: str, financial_account_id: str, external_id: str) -> BankStatementLineDB | None:
    return db.scalar(select(BankStatementLineDB).where(BankStatementLineDB.company_id == company_id, BankStatementLineDB.financial_account_id == financial_account_id, BankStatementLineDB.external_id == external_id))


def get_statement_line(db: Session, line_id: str) -> BankStatementLineDB | None:
    return db.scalar(select(BankStatementLineDB).where(BankStatementLineDB.id == line_id))


def get_statement_line_for_update(db: Session, line_id: str) -> BankStatementLineDB | None:
    return db.scalar(select(BankStatementLineDB).where(BankStatementLineDB.id == line_id).with_for_update())


def get_financial_movement_for_update(db: Session, movement_id: str) -> FinancialMovementDB | None:
    return db.scalar(select(FinancialMovementDB).where(FinancialMovementDB.id == movement_id).with_for_update())


def get_match(db: Session, match_id: str) -> ReconciliationMatchDB | None:
    return db.scalar(select(ReconciliationMatchDB).where(ReconciliationMatchDB.id == match_id))


def get_match_for_update(db: Session, match_id: str) -> ReconciliationMatchDB | None:
    return db.scalar(select(ReconciliationMatchDB).where(ReconciliationMatchDB.id == match_id).with_for_update())


def get_active_match_for_line_or_movement(db: Session, *, statement_line_id: str, financial_movement_id: str) -> ReconciliationMatchDB | None:
    return db.scalar(select(ReconciliationMatchDB).where(ReconciliationMatchDB.status.in_(["confirmed", "confirmed_with_difference"]), or_(ReconciliationMatchDB.statement_line_id == statement_line_id, ReconciliationMatchDB.financial_movement_id == financial_movement_id)))


def list_imports(db: Session, *, company_id: str, financial_account_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> list[BankStatementImportDB]:
    stmt = select(BankStatementImportDB).where(BankStatementImportDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(BankStatementImportDB.financial_account_id == financial_account_id)
    if status:
        stmt = stmt.where(BankStatementImportDB.status == status)
    return list(db.scalars(stmt.order_by(BankStatementImportDB.created_at.desc()).limit(limit).offset(offset)))


def list_lines(db: Session, *, company_id: str, financial_account_id: str | None = None, statement_import_id: str | None = None, status: str | None = None, statuses: list[str] | None = None, line_from: Any | None = None, line_to: Any | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[BankStatementLineDB]:
    stmt = select(BankStatementLineDB).where(BankStatementLineDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(BankStatementLineDB.financial_account_id == financial_account_id)
    if statement_import_id:
        stmt = stmt.where(BankStatementLineDB.statement_import_id == statement_import_id)
    if status:
        stmt = stmt.where(BankStatementLineDB.status == status)
    if statuses:
        stmt = stmt.where(BankStatementLineDB.status.in_(statuses))
    if line_from:
        stmt = stmt.where(BankStatementLineDB.line_date >= line_from)
    if line_to:
        stmt = stmt.where(BankStatementLineDB.line_date <= line_to)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(BankStatementLineDB.description.ilike(like), BankStatementLineDB.external_id.ilike(like), BankStatementLineDB.bank_reference.ilike(like), BankStatementLineDB.counterparty_name.ilike(like)))
    return list(db.scalars(stmt.order_by(BankStatementLineDB.line_date.desc(), BankStatementLineDB.created_at.desc()).limit(limit).offset(offset)))


def list_matches(db: Session, *, company_id: str, financial_account_id: str | None = None, status: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[ReconciliationMatchDB]:
    stmt = select(ReconciliationMatchDB).where(ReconciliationMatchDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(ReconciliationMatchDB.financial_account_id == financial_account_id)
    if status:
        stmt = stmt.where(ReconciliationMatchDB.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ReconciliationMatchDB.id.ilike(like),
                ReconciliationMatchDB.statement_line_id.ilike(like),
                ReconciliationMatchDB.financial_movement_id.ilike(like),
                ReconciliationMatchDB.match_type.ilike(like),
                ReconciliationMatchDB.status.ilike(like),
                ReconciliationMatchDB.confirmation_reason.ilike(like),
                ReconciliationMatchDB.reversed_reason.ilike(like),
            )
        )
    return list(db.scalars(stmt.order_by(ReconciliationMatchDB.created_at.desc()).limit(limit).offset(offset)))


def list_matches_by_statuses(db: Session, *, company_id: str, statuses: list[str], financial_account_id: str | None = None, limit: int = 50, offset: int = 0) -> list[ReconciliationMatchDB]:
    stmt = select(ReconciliationMatchDB).where(
        ReconciliationMatchDB.company_id == company_id,
        ReconciliationMatchDB.status.in_(statuses),
    )
    if financial_account_id:
        stmt = stmt.where(ReconciliationMatchDB.financial_account_id == financial_account_id)
    return list(db.scalars(stmt.order_by(ReconciliationMatchDB.created_at.desc()).limit(limit).offset(offset)))


def list_movements_for_reconciliation(db: Session, *, company_id: str, financial_account_id: str | None = None, reconciliation_status: str | None = None, limit: int = 5000, offset: int = 0) -> list[FinancialMovementDB]:
    stmt = select(FinancialMovementDB).where(
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
    )
    if financial_account_id:
        stmt = stmt.where(FinancialMovementDB.financial_account_id == financial_account_id)
    if reconciliation_status:
        stmt = stmt.where(FinancialMovementDB.reconciliation_status == reconciliation_status)
    return list(db.scalars(stmt.order_by(FinancialMovementDB.movement_date.desc(), FinancialMovementDB.created_at.desc()).limit(limit).offset(offset)))


def find_candidate_movements(db: Session, *, company_id: str, financial_account_id: str, direction: str, amount: Decimal, line_date: Any, day_window: int = 3, limit: int = 10) -> list[FinancialMovementDB]:
    from datetime import timedelta
    start = line_date - timedelta(days=day_window)
    end = line_date + timedelta(days=day_window)
    stmt = select(FinancialMovementDB).where(
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.financial_account_id == financial_account_id,
        FinancialMovementDB.direction == direction,
        FinancialMovementDB.amount == amount,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reconciliation_status == "pending",
        FinancialMovementDB.movement_date >= start,
        FinancialMovementDB.movement_date <= end,
    ).order_by(FinancialMovementDB.movement_date.asc(), FinancialMovementDB.created_at.asc()).limit(limit)
    return list(db.scalars(stmt))


def _line_stats_by_status(db: Session, *, company_id: str, financial_account_id: str | None) -> dict[str, tuple[int, Decimal]]:
    stmt = select(
        BankStatementLineDB.status,
        func.count(BankStatementLineDB.id),
        func.coalesce(func.sum(BankStatementLineDB.amount), 0),
    ).where(BankStatementLineDB.company_id == company_id)
    if financial_account_id:
        stmt = stmt.where(BankStatementLineDB.financial_account_id == financial_account_id)
    rows = db.execute(stmt.group_by(BankStatementLineDB.status)).all()
    return {status: (int(count or 0), _money(amount)) for status, count, amount in rows}


def _movement_stats_by_reconciliation_status(db: Session, *, company_id: str, financial_account_id: str | None) -> dict[str, tuple[int, Decimal]]:
    stmt = select(
        FinancialMovementDB.reconciliation_status,
        func.count(FinancialMovementDB.id),
        func.coalesce(func.sum(FinancialMovementDB.amount), 0),
    ).where(
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
    )
    if financial_account_id:
        stmt = stmt.where(FinancialMovementDB.financial_account_id == financial_account_id)
    rows = db.execute(stmt.group_by(FinancialMovementDB.reconciliation_status)).all()
    return {status: (int(count or 0), _money(amount)) for status, count, amount in rows}


def _match_stats(db: Session, *, company_id: str, financial_account_id: str | None) -> tuple[int, Decimal, Decimal]:
    stmt = select(
        func.count(ReconciliationMatchDB.id),
        func.coalesce(func.sum(ReconciliationMatchDB.matched_amount), 0),
        func.coalesce(func.sum(ReconciliationMatchDB.difference_amount), 0),
    ).where(
        ReconciliationMatchDB.company_id == company_id,
        ReconciliationMatchDB.status.in_(["confirmed", "confirmed_with_difference"]),
    )
    if financial_account_id:
        stmt = stmt.where(ReconciliationMatchDB.financial_account_id == financial_account_id)
    count, amount, difference = db.execute(stmt).one()
    return int(count or 0), _money(amount), _money(difference)


def summary_by_company(db: Session, *, company_id: str, financial_account_id: str | None = None) -> dict[str, Any]:
    line_stats = _line_stats_by_status(db, company_id=company_id, financial_account_id=financial_account_id)
    movement_stats = _movement_stats_by_reconciliation_status(db, company_id=company_id, financial_account_id=financial_account_id)
    pending_lines, pending_lines_amount = line_stats.get("pending", (0, Decimal("0.00")))
    matched_lines, matched_lines_amount = line_stats.get("matched", (0, Decimal("0.00")))
    divergent_lines, divergent_lines_amount = line_stats.get("divergent", (0, Decimal("0.00")))
    ignored_lines, ignored_lines_amount = line_stats.get("ignored", (0, Decimal("0.00")))
    pending_movements, pending_movements_amount = movement_stats.get("pending", (0, Decimal("0.00")))
    divergent_movements, divergent_movements_amount = movement_stats.get("divergent", (0, Decimal("0.00")))
    confirmed_matches, confirmed_matches_amount, confirmed_matches_difference_amount = _match_stats(db, company_id=company_id, financial_account_id=financial_account_id)
    return {
        "company_id": company_id,
        "financial_account_id": financial_account_id,
        "pending_statement_lines": pending_lines,
        "pending_statement_lines_amount": format(pending_lines_amount, "f"),
        "matched_statement_lines": matched_lines,
        "matched_statement_lines_amount": format(matched_lines_amount, "f"),
        "divergent_statement_lines": divergent_lines,
        "divergent_statement_lines_amount": format(divergent_lines_amount, "f"),
        "ignored_statement_lines": ignored_lines,
        "ignored_statement_lines_amount": format(ignored_lines_amount, "f"),
        "pending_financial_movements": pending_movements,
        "pending_financial_movements_amount": format(pending_movements_amount, "f"),
        "divergent_financial_movements": divergent_movements,
        "divergent_financial_movements_amount": format(divergent_movements_amount, "f"),
        "confirmed_matches": confirmed_matches,
        "confirmed_matches_amount": format(confirmed_matches_amount, "f"),
        "confirmed_matches_difference_amount": format(confirmed_matches_difference_amount, "f"),
    }
