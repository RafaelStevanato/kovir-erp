from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import Select, String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.accounts_receivable.db_models import FinancialTitleDB, FinancialTitleHistoryDB
from app.modules.financial.db_models import CostCenterDB, FinancialAccountDB, FinancialCategoryDB
from app.modules.purchases_payables.db_models import PurchaseDB, PurchaseFinancialLinkDB, PurchaseItemDB, PurchaseStatusHistoryDB

MONEY_QUANT = Decimal("0.01")
QTY_QUANT = Decimal("0.0001")


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def qty(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def purchase_item_to_dict(item: PurchaseItemDB) -> dict[str, Any]:
    return {
        "id": item.id,
        "company_id": item.company_id,
        "purchase_id": item.purchase_id,
        "item_id": item.item_id,
        "fiscal_classification_id": item.fiscal_classification_id,
        "description": item.description,
        "quantity": format(qty(item.quantity), "f"),
        "unit": item.unit,
        "unit_cost": format(qty(item.unit_cost), "f"),
        "discount_amount": format(money(item.discount_amount), "f"),
        "freight_amount": format(money(item.freight_amount), "f"),
        "tax_amount": format(money(item.tax_amount), "f"),
        "total_amount": format(money(item.total_amount), "f"),
        "item_snapshot": item.item_snapshot_json,
        "fiscal_snapshot": item.fiscal_snapshot_json,
        "metadata": item.metadata_json,
        "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at),
    }


def purchase_to_dict(purchase: PurchaseDB, *, include_items: bool = True) -> dict[str, Any]:
    data = {
        "id": purchase.id,
        "company_id": purchase.company_id,
        "establishment_id": purchase.establishment_id,
        "participant_id": purchase.participant_id,
        "status": purchase.status,
        "purchase_type": purchase.purchase_type,
        "origin": purchase.origin,
        "operation_nature_id": purchase.operation_nature_id,
        "fiscal_status": purchase.fiscal_status,
        "issue_date": iso(purchase.issue_date),
        "operation_date": iso(purchase.operation_date),
        "competency_date": iso(purchase.competency_date),
        "subtotal_amount": format(money(purchase.subtotal_amount), "f"),
        "discount_amount": format(money(purchase.discount_amount), "f"),
        "freight_amount": format(money(purchase.freight_amount), "f"),
        "tax_amount": format(money(purchase.tax_amount), "f"),
        "total_amount": format(money(purchase.total_amount), "f"),
        "payable_total_amount": format(money(purchase.payable_total_amount), "f"),
        "invoice_total_amount": format(money(purchase.invoice_total_amount), "f") if purchase.invoice_total_amount is not None else None,
        "financial_category_id": purchase.financial_category_id,
        "cost_center_id": purchase.cost_center_id,
        "expected_financial_account_id": purchase.expected_financial_account_id,
        "document_type": purchase.document_type,
        "document_number": purchase.document_number,
        "document_series": purchase.document_series,
        "access_key": purchase.access_key,
        "participant_snapshot": purchase.participant_snapshot_json,
        "document_snapshot": purchase.document_snapshot_json,
        "metadata": purchase.metadata_json,
        "notes": purchase.notes,
        "created_at": iso(purchase.created_at),
        "updated_at": iso(purchase.updated_at),
        "confirmed_at": iso(purchase.confirmed_at),
        "cancelled_at": iso(purchase.cancelled_at),
    }
    if include_items:
        data["items"] = [purchase_item_to_dict(item) for item in purchase.items]
    return data


def payable_to_dict(title: FinancialTitleDB) -> dict[str, Any]:
    return {
        "id": title.id,
        "company_id": title.company_id,
        "direction": title.direction,
        "title_type": title.title_type,
        "source_type": title.source_type,
        "source_id": title.source_id,
        "source_snapshot": title.source_snapshot_json,
        "purchase_id": (title.source_snapshot_json or {}).get("purchase_id"),
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
        "issue_date": iso(title.issue_date),
        "competency_date": iso(title.competency_date),
        "due_date": iso(title.due_date),
        "expected_payment_date": iso(title.expected_payment_date),
        "gross_amount": format(money(title.gross_amount), "f"),
        "discount_amount": format(money(title.discount_amount), "f"),
        "interest_amount": format(money(title.interest_amount), "f"),
        "penalty_amount": format(money(title.penalty_amount), "f"),
        "fee_amount": format(money(title.fee_amount), "f"),
        "net_amount": format(money(title.net_amount), "f"),
        "paid_amount": format(money(title.paid_amount), "f"),
        "open_amount": format(money(title.open_amount), "f"),
        "status": title.status,
        "collection_status": title.collection_status,
        "fiscal_status": title.fiscal_status,
        "notes": title.notes,
        "metadata": title.metadata_json,
        "created_at": iso(title.created_at),
        "updated_at": iso(title.updated_at),
        "cancelled_at": iso(title.cancelled_at),
    }


def purchase_history_to_dict(row: PurchaseStatusHistoryDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "purchase_id": row.purchase_id,
        "previous_status": row.previous_status,
        "new_status": row.new_status,
        "reason": row.reason,
        "source": row.source,
        "actor_id": row.actor_id,
        "occurred_at": iso(row.occurred_at),
    }


def create_purchase(db: Session, **data: Any) -> PurchaseDB:
    row = PurchaseDB(**data)
    db.add(row)
    db.flush()
    return row


def create_purchase_item(db: Session, **data: Any) -> PurchaseItemDB:
    row = PurchaseItemDB(**data)
    db.add(row)
    db.flush()
    return row


def create_purchase_financial_link(db: Session, **data: Any) -> PurchaseFinancialLinkDB:
    row = PurchaseFinancialLinkDB(**data)
    db.add(row)
    db.flush()
    return row


def create_purchase_status_history(db: Session, **data: Any) -> PurchaseStatusHistoryDB:
    row = PurchaseStatusHistoryDB(**data)
    db.add(row)
    db.flush()
    return row


def create_financial_title_history(db: Session, **data: Any) -> FinancialTitleHistoryDB:
    row = FinancialTitleHistoryDB(**data)
    db.add(row)
    db.flush()
    return row


def create_payable_title(db: Session, **data: Any) -> FinancialTitleDB:
    row = FinancialTitleDB(**data)
    db.add(row)
    db.flush()
    return row


def get_purchase(db: Session, purchase_id: str) -> PurchaseDB | None:
    return db.scalar(select(PurchaseDB).options(selectinload(PurchaseDB.items)).where(PurchaseDB.id == purchase_id, PurchaseDB.deleted_at.is_(None)))


def get_purchase_for_update(db: Session, purchase_id: str) -> PurchaseDB | None:
    return db.scalar(select(PurchaseDB).options(selectinload(PurchaseDB.items)).where(PurchaseDB.id == purchase_id, PurchaseDB.deleted_at.is_(None)).with_for_update())


def list_purchases(
    db: Session,
    *,
    company_id: str,
    participant_id: str | None = None,
    status: str | None = None,
    purchase_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_items: bool = True,
    max_limit: int = 200,
) -> list[PurchaseDB]:
    statement: Select[tuple[PurchaseDB]] = select(PurchaseDB).where(PurchaseDB.company_id == company_id, PurchaseDB.deleted_at.is_(None))
    if include_items:
        statement = statement.options(selectinload(PurchaseDB.items))
    if participant_id:
        statement = statement.where(PurchaseDB.participant_id == participant_id)
    if status:
        statement = statement.where(PurchaseDB.status == status)
    if purchase_type:
        statement = statement.where(PurchaseDB.purchase_type == purchase_type)
    if date_from:
        statement = statement.where(PurchaseDB.issue_date >= date_from)
    if date_to:
        statement = statement.where(PurchaseDB.issue_date <= date_to)
    if q:
        like = f"%{q.strip()}%"
        statement = statement.where(or_(PurchaseDB.document_number.ilike(like), PurchaseDB.notes.ilike(like), PurchaseDB.id.ilike(like)))
    statement = statement.order_by(PurchaseDB.created_at.desc(), PurchaseDB.id.desc()).limit(min(max(limit, 1), max_limit)).offset(max(offset, 0))
    return list(db.scalars(statement).all())


def get_payable(db: Session, title_id: str) -> FinancialTitleDB | None:
    return db.scalar(select(FinancialTitleDB).where(FinancialTitleDB.id == title_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None)))


def get_payable_for_update(db: Session, title_id: str) -> FinancialTitleDB | None:
    return db.scalar(select(FinancialTitleDB).where(FinancialTitleDB.id == title_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None)).with_for_update())


def get_payable_by_source(db: Session, *, company_id: str, source_type: str, source_id: str) -> FinancialTitleDB | None:
    return db.scalar(select(FinancialTitleDB).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.source_type == source_type, FinancialTitleDB.source_id == source_id, FinancialTitleDB.deleted_at.is_(None)))


def list_payables(
    db: Session,
    *,
    company_id: str,
    participant_id: str | None = None,
    status: str | None = None,
    purchase_id: str | None = None,
    financial_category_id: str | None = None,
    cost_center_id: str | None = None,
    expected_financial_account_id: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    open_amount_min: Decimal | None = None,
    open_amount_max: Decimal | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    max_limit: int = 200,
) -> list[FinancialTitleDB]:
    statement: Select[tuple[FinancialTitleDB]] = select(FinancialTitleDB).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None))
    if participant_id:
        statement = statement.where(FinancialTitleDB.participant_id == participant_id)
    if status:
        statement = statement.where(FinancialTitleDB.status == status)
    if purchase_id:
        statement = statement.where(FinancialTitleDB.source_id.ilike(f"{purchase_id}:%"))
    if financial_category_id:
        statement = statement.where(FinancialTitleDB.financial_category_id == financial_category_id)
    if cost_center_id:
        statement = statement.where(FinancialTitleDB.cost_center_id == cost_center_id)
    if expected_financial_account_id:
        statement = statement.where(FinancialTitleDB.expected_financial_account_id == expected_financial_account_id)
    if due_from:
        statement = statement.where(FinancialTitleDB.due_date >= due_from)
    if due_to:
        statement = statement.where(FinancialTitleDB.due_date <= due_to)
    if open_amount_min is not None:
        statement = statement.where(FinancialTitleDB.open_amount >= money(open_amount_min))
    if open_amount_max is not None:
        statement = statement.where(FinancialTitleDB.open_amount <= money(open_amount_max))
    if q:
        like = f"%{q.strip()}%"
        statement = (
            statement.outerjoin(FinancialCategoryDB, FinancialCategoryDB.id == FinancialTitleDB.financial_category_id)
            .outerjoin(CostCenterDB, CostCenterDB.id == FinancialTitleDB.cost_center_id)
            .outerjoin(FinancialAccountDB, FinancialAccountDB.id == FinancialTitleDB.expected_financial_account_id)
        )
        statement = statement.where(
            or_(
                FinancialTitleDB.id.ilike(like),
                FinancialTitleDB.document_reference.ilike(like),
                FinancialTitleDB.notes.ilike(like),
                FinancialTitleDB.source_id.ilike(like),
                FinancialTitleDB.payment_method_name.ilike(like),
                cast(FinancialTitleDB.participant_snapshot_json, String).ilike(like),
                cast(FinancialTitleDB.source_snapshot_json, String).ilike(like),
                FinancialCategoryDB.name.ilike(like),
                CostCenterDB.name.ilike(like),
                FinancialAccountDB.name.ilike(like),
                FinancialAccountDB.institution_name.ilike(like),
            )
        )
    statement = statement.order_by(FinancialTitleDB.due_date.asc(), FinancialTitleDB.created_at.desc()).limit(min(max(limit, 1), max_limit)).offset(max(offset, 0))
    return list(db.scalars(statement).all())


def list_payables_for_overview(db: Session, *, company_id: str, block: str, today: date, limit: int = 500) -> list[FinancialTitleDB]:
    active_statuses = ["open", "overdue", "partially_paid"]
    statement: Select[tuple[FinancialTitleDB]] = select(FinancialTitleDB).where(
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
    )
    if block == "open_payables":
        statement = statement.where(FinancialTitleDB.status.in_(active_statuses))
    elif block == "overdue_payables":
        statement = statement.where(FinancialTitleDB.status.in_(active_statuses), FinancialTitleDB.due_date < today)
    elif block == "paid_payables":
        statement = statement.where(FinancialTitleDB.status == "paid")
    else:
        raise ValueError("Bloco de evidência de contas a pagar inválido.")
    statement = statement.order_by(FinancialTitleDB.due_date.asc(), FinancialTitleDB.created_at.desc()).limit(min(max(limit, 1), 5000))
    return list(db.scalars(statement).all())


def list_purchases_for_overview(db: Session, *, company_id: str, status: str, limit: int = 500) -> list[PurchaseDB]:
    statement: Select[tuple[PurchaseDB]] = (
        select(PurchaseDB)
        .where(PurchaseDB.company_id == company_id, PurchaseDB.status == status, PurchaseDB.deleted_at.is_(None))
        .order_by(PurchaseDB.created_at.desc(), PurchaseDB.id.desc())
        .limit(min(max(limit, 1), 5000))
    )
    return list(db.scalars(statement).all())


def list_purchase_history(db: Session, purchase_id: str) -> list[PurchaseStatusHistoryDB]:
    return list(db.scalars(select(PurchaseStatusHistoryDB).where(PurchaseStatusHistoryDB.purchase_id == purchase_id).order_by(PurchaseStatusHistoryDB.occurred_at.desc())).all())


def list_purchase_payables(db: Session, *, company_id: str, purchase_id: str) -> list[FinancialTitleDB]:
    return list(db.scalars(select(FinancialTitleDB).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.source_id.ilike(f"{purchase_id}:%"), FinancialTitleDB.deleted_at.is_(None)).order_by(FinancialTitleDB.due_date.asc())).all())


def update_purchase_fields(row: PurchaseDB, **updates: Any) -> PurchaseDB:
    for key, value in updates.items():
        setattr(row, key, value)
    return row


def update_title_fields(row: FinancialTitleDB, **updates: Any) -> FinancialTitleDB:
    for key, value in updates.items():
        setattr(row, key, value)
    return row


def summary_by_company(db: Session, *, company_id: str, today: date) -> dict[str, Any]:
    purchase_rows = list(db.execute(select(PurchaseDB.status, func.count(PurchaseDB.id), func.coalesce(func.sum(PurchaseDB.total_amount), 0)).where(PurchaseDB.company_id == company_id, PurchaseDB.deleted_at.is_(None)).group_by(PurchaseDB.status)).all())
    title_rows = list(db.execute(select(FinancialTitleDB.status, func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0), func.coalesce(func.sum(FinancialTitleDB.net_amount), 0), func.coalesce(func.sum(FinancialTitleDB.paid_amount), 0)).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None)).group_by(FinancialTitleDB.status)).all())
    overdue = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None), FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]), FinancialTitleDB.due_date < today)).one()
    open_total = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None), FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]))).one()
    paid_total = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.paid_amount), 0)).where(FinancialTitleDB.company_id == company_id, FinancialTitleDB.direction == "payable", FinancialTitleDB.deleted_at.is_(None), FinancialTitleDB.status == "paid")).one()
    return {
        "company_id": company_id,
        "purchases_by_status": {status: {"count": int(count), "total_amount": format(money(total), "f")} for status, count, total in purchase_rows},
        "payables_by_status": {status: {"count": int(count), "open_amount": format(money(open_amount), "f"), "net_amount": format(money(net_amount), "f"), "paid_amount": format(money(paid_amount), "f")} for status, count, open_amount, net_amount, paid_amount in title_rows},
        "open_payable_count": int(open_total[0] or 0),
        "open_payable_amount": format(money(open_total[1]), "f"),
        "overdue_payable_count": int(overdue[0] or 0),
        "overdue_payable_amount": format(money(overdue[1]), "f"),
        "paid_payable_count": int(paid_total[0] or 0),
        "paid_payable_amount": format(money(paid_total[1]), "f"),
    }
