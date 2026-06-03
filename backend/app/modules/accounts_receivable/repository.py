from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.db_models import FinancialTitleDB, FinancialTitleHistoryDB, SaleFinancialLinkDB
from app.shared.datetime import today_in_brazil


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def title_to_dict(title: FinancialTitleDB) -> dict[str, Any]:
    return {
        "id": title.id,
        "company_id": title.company_id,
        "direction": title.direction,
        "title_type": title.title_type,
        "source_type": title.source_type,
        "source_id": title.source_id,
        "source_snapshot": title.source_snapshot_json,
        "sale_id": title.sale_id,
        "sale_payment_plan_id": title.sale_payment_plan_id,
        "participant_id": title.participant_id,
        "participant_snapshot": title.participant_snapshot_json,
        "payment_method_id": title.payment_method_id,
        "payment_method_code": title.payment_method_code,
        "payment_method_name": title.payment_method_name,
        "financial_category_id": title.financial_category_id,
        "cost_center_id": title.cost_center_id,
        "expected_financial_account_id": title.expected_financial_account_id,
        "document_reference": title.document_reference,
        "installment_number": title.installment_number,
        "installment_total": title.installment_total,
        "issue_date": _iso(title.issue_date),
        "competency_date": _iso(title.competency_date),
        "due_date": _iso(title.due_date),
        "expected_payment_date": _iso(title.expected_payment_date),
        "gross_amount": format(_money(title.gross_amount), "f"),
        "discount_amount": format(_money(title.discount_amount), "f"),
        "interest_amount": format(_money(title.interest_amount), "f"),
        "penalty_amount": format(_money(title.penalty_amount), "f"),
        "fee_amount": format(_money(title.fee_amount), "f"),
        "net_amount": format(_money(title.net_amount), "f"),
        "paid_amount": format(_money(title.paid_amount), "f"),
        "open_amount": format(_money(title.open_amount), "f"),
        "status": title.status,
        "collection_status": title.collection_status,
        "fiscal_status": title.fiscal_status,
        "notes": title.notes,
        "metadata": title.metadata_json,
        "created_at": _iso(title.created_at),
        "updated_at": _iso(title.updated_at),
        "cancelled_at": _iso(title.cancelled_at),
    }


def history_to_dict(row: FinancialTitleHistoryDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "financial_title_id": row.financial_title_id,
        "previous_status": row.previous_status,
        "new_status": row.new_status,
        "previous_collection_status": row.previous_collection_status,
        "new_collection_status": row.new_collection_status,
        "reason": row.reason,
        "source": row.source,
        "actor_id": row.actor_id,
        "occurred_at": _iso(row.occurred_at),
    }


def create_title(db: Session, **data: Any) -> FinancialTitleDB:
    title = FinancialTitleDB(**data)
    db.add(title)
    db.flush()
    return title


def create_sale_financial_link(db: Session, **data: Any) -> SaleFinancialLinkDB:
    link = SaleFinancialLinkDB(**data)
    db.add(link)
    db.flush()
    return link


def create_title_history(db: Session, **data: Any) -> FinancialTitleHistoryDB:
    row = FinancialTitleHistoryDB(**data)
    db.add(row)
    db.flush()
    return row


def get_title(db: Session, title_id: str) -> FinancialTitleDB | None:
    return db.scalar(select(FinancialTitleDB).where(FinancialTitleDB.id == title_id, FinancialTitleDB.deleted_at.is_(None)))


def get_title_for_update(db: Session, title_id: str) -> FinancialTitleDB | None:
    return db.scalar(select(FinancialTitleDB).where(FinancialTitleDB.id == title_id, FinancialTitleDB.deleted_at.is_(None)).with_for_update())


def get_title_by_source(db: Session, *, company_id: str, source_type: str, source_id: str) -> FinancialTitleDB | None:
    return db.scalar(
        select(FinancialTitleDB).where(
            FinancialTitleDB.company_id == company_id,
            FinancialTitleDB.source_type == source_type,
            FinancialTitleDB.source_id == source_id,
            FinancialTitleDB.deleted_at.is_(None),
        )
    )


def list_titles(
    db: Session,
    *,
    company_id: str,
    participant_id: str | None = None,
    status: str | None = None,
    collection_status: str | None = None,
    fiscal_status: str | None = None,
    sale_id: str | None = None,
    source_type: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FinancialTitleDB]:
    statement: Select[tuple[FinancialTitleDB]] = select(FinancialTitleDB).where(
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
    )
    if participant_id:
        statement = statement.where(FinancialTitleDB.participant_id == participant_id)
    if status == "overdue":
        statement = statement.where(
            FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
            FinancialTitleDB.due_date < today_in_brazil(),
        )
    elif status:
        statement = statement.where(FinancialTitleDB.status == status)
    if collection_status:
        statement = statement.where(FinancialTitleDB.collection_status == collection_status)
    if fiscal_status:
        statement = statement.where(FinancialTitleDB.fiscal_status == fiscal_status)
    if sale_id:
        statement = statement.where(FinancialTitleDB.sale_id == sale_id)
    if source_type:
        statement = statement.where(FinancialTitleDB.source_type == source_type)
    if due_from:
        statement = statement.where(FinancialTitleDB.due_date >= due_from)
    if due_to:
        statement = statement.where(FinancialTitleDB.due_date <= due_to)
    if q:
        query = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                FinancialTitleDB.document_reference.ilike(query),
                FinancialTitleDB.notes.ilike(query),
                FinancialTitleDB.source_id.ilike(query),
                FinancialTitleDB.sale_id.ilike(query),
                FinancialTitleDB.payment_method_name.ilike(query),
                cast(FinancialTitleDB.participant_snapshot_json, String).ilike(query),
                cast(FinancialTitleDB.source_snapshot_json, String).ilike(query),
            )
        )
    statement = statement.order_by(FinancialTitleDB.due_date.asc(), FinancialTitleDB.created_at.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0))
    return list(db.scalars(statement).all())


def list_titles_by_sale(db: Session, *, company_id: str, sale_id: str) -> list[FinancialTitleDB]:
    return list(db.scalars(select(FinancialTitleDB).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.sale_id == sale_id, FinancialTitleDB.deleted_at.is_(None)).order_by(FinancialTitleDB.due_date.asc())).all())


def list_history(db: Session, title_id: str) -> list[FinancialTitleHistoryDB]:
    return list(db.scalars(select(FinancialTitleHistoryDB).where(FinancialTitleHistoryDB.financial_title_id == title_id).order_by(FinancialTitleHistoryDB.occurred_at.desc())).all())


def update_title_fields(title: FinancialTitleDB, **updates: Any) -> FinancialTitleDB:
    for key, value in updates.items():
        setattr(title, key, value)
    return title


def summary_by_company(db: Session, *, company_id: str, today: date) -> dict[str, Any]:
    by_status: dict[str, dict[str, Any]] = {}
    active_statuses = {"open", "overdue", "partially_received"}
    base_filters = (
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
    )

    status_rows = db.execute(
        select(
            FinancialTitleDB.status,
            func.count(FinancialTitleDB.id),
            func.coalesce(func.sum(FinancialTitleDB.open_amount), Decimal("0.00")),
            func.coalesce(func.sum(FinancialTitleDB.net_amount), Decimal("0.00")),
            func.coalesce(func.sum(FinancialTitleDB.paid_amount), Decimal("0.00")),
        )
        .where(*base_filters)
        .group_by(FinancialTitleDB.status)
    ).all()
    for status, count, open_amount, net_amount, paid_amount in status_rows:
        by_status[str(status)] = {
            "count": int(count or 0),
            "open_amount": _money(open_amount),
            "net_amount": _money(net_amount),
            "paid_amount": _money(paid_amount),
        }

    active_condition = FinancialTitleDB.status.in_(active_statuses)
    overdue_condition = and_(active_condition, FinancialTitleDB.due_date < today)
    received_condition = FinancialTitleDB.status == "received"
    partial_condition = or_(
        FinancialTitleDB.status == "partially_received",
        and_(FinancialTitleDB.paid_amount > Decimal("0.00"), FinancialTitleDB.open_amount > Decimal("0.00")),
    )
    cancelled_condition = FinancialTitleDB.status == "cancelled"
    next_7_limit = today + timedelta(days=7)
    next_30_limit = today + timedelta(days=30)
    current_condition = and_(active_condition, FinancialTitleDB.due_date >= today)
    overdue_1_30_condition = and_(active_condition, FinancialTitleDB.due_date >= today - timedelta(days=30), FinancialTitleDB.due_date < today)
    overdue_31_60_condition = and_(active_condition, FinancialTitleDB.due_date >= today - timedelta(days=60), FinancialTitleDB.due_date < today - timedelta(days=30))
    overdue_61_90_condition = and_(active_condition, FinancialTitleDB.due_date >= today - timedelta(days=90), FinancialTitleDB.due_date < today - timedelta(days=60))
    overdue_90_plus_condition = and_(active_condition, FinancialTitleDB.due_date < today - timedelta(days=90))
    due_next_7_condition = and_(active_condition, FinancialTitleDB.due_date >= today, FinancialTitleDB.due_date <= next_7_limit)
    due_next_30_condition = and_(active_condition, FinancialTitleDB.due_date >= today, FinancialTitleDB.due_date <= next_30_limit)

    def count_when(condition: Any):
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    def sum_when(condition: Any, column: Any):
        return func.coalesce(func.sum(case((condition, column), else_=Decimal("0.00"))), Decimal("0.00"))

    totals = db.execute(
        select(
            func.count(FinancialTitleDB.id).label("total_count"),
            count_when(active_condition).label("open_count"),
            sum_when(active_condition, FinancialTitleDB.open_amount).label("open_amount"),
            count_when(overdue_condition).label("overdue_count"),
            sum_when(overdue_condition, FinancialTitleDB.open_amount).label("overdue_amount"),
            count_when(received_condition).label("received_count"),
            sum_when(received_condition, FinancialTitleDB.paid_amount).label("received_amount"),
            count_when(partial_condition).label("partially_received_count"),
            sum_when(partial_condition, FinancialTitleDB.open_amount).label("partially_received_open_amount"),
            count_when(cancelled_condition).label("cancelled_count"),
            sum_when(cancelled_condition, FinancialTitleDB.net_amount).label("cancelled_amount"),
            count_when(due_next_7_condition).label("due_next_7_count"),
            sum_when(due_next_7_condition, FinancialTitleDB.open_amount).label("due_next_7_amount"),
            count_when(due_next_30_condition).label("due_next_30_count"),
            sum_when(due_next_30_condition, FinancialTitleDB.open_amount).label("due_next_30_amount"),
            count_when(current_condition).label("aging_current_count"),
            sum_when(current_condition, FinancialTitleDB.open_amount).label("aging_current_amount"),
            count_when(overdue_1_30_condition).label("aging_overdue_1_30_count"),
            sum_when(overdue_1_30_condition, FinancialTitleDB.open_amount).label("aging_overdue_1_30_amount"),
            count_when(overdue_31_60_condition).label("aging_overdue_31_60_count"),
            sum_when(overdue_31_60_condition, FinancialTitleDB.open_amount).label("aging_overdue_31_60_amount"),
            count_when(overdue_61_90_condition).label("aging_overdue_61_90_count"),
            sum_when(overdue_61_90_condition, FinancialTitleDB.open_amount).label("aging_overdue_61_90_amount"),
            count_when(overdue_90_plus_condition).label("aging_overdue_90_plus_count"),
            sum_when(overdue_90_plus_condition, FinancialTitleDB.open_amount).label("aging_overdue_90_plus_amount"),
        ).where(*base_filters)
    ).one()

    def aging_bucket(count_key: str, amount_key: str) -> dict[str, Any]:
        return {"count": int(getattr(totals, count_key) or 0), "amount": format(_money(getattr(totals, amount_key)), "f")}

    aging = {
        "current": aging_bucket("aging_current_count", "aging_current_amount"),
        "overdue_1_30": aging_bucket("aging_overdue_1_30_count", "aging_overdue_1_30_amount"),
        "overdue_31_60": aging_bucket("aging_overdue_31_60_count", "aging_overdue_31_60_amount"),
        "overdue_61_90": aging_bucket("aging_overdue_61_90_count", "aging_overdue_61_90_amount"),
        "overdue_90_plus": aging_bucket("aging_overdue_90_plus_count", "aging_overdue_90_plus_amount"),
    }
    formatted_by_status = {
        status: {
            "count": int(values["count"]),
            "open_amount": format(_money(values["open_amount"]), "f"),
            "net_amount": format(_money(values["net_amount"]), "f"),
            "paid_amount": format(_money(values["paid_amount"]), "f"),
        }
        for status, values in by_status.items()
    }
    return {
        "company_id": company_id,
        "as_of": today.isoformat(),
        "by_status": formatted_by_status,
        "total_count": int(totals.total_count or 0),
        "open_count": int(totals.open_count or 0),
        "open_amount": format(_money(totals.open_amount), "f"),
        "overdue_count": int(totals.overdue_count or 0),
        "overdue_amount": format(_money(totals.overdue_amount), "f"),
        "received_count": int(totals.received_count or 0),
        "received_amount": format(_money(totals.received_amount), "f"),
        "partially_received_count": int(totals.partially_received_count or 0),
        "partially_received_open_amount": format(_money(totals.partially_received_open_amount), "f"),
        "cancelled_count": int(totals.cancelled_count or 0),
        "cancelled_amount": format(_money(totals.cancelled_amount), "f"),
        "due_next_7_count": int(totals.due_next_7_count or 0),
        "due_next_7_amount": format(_money(totals.due_next_7_amount), "f"),
        "due_next_30_count": int(totals.due_next_30_count or 0),
        "due_next_30_amount": format(_money(totals.due_next_30_amount), "f"),
        "aging": aging,
    }
