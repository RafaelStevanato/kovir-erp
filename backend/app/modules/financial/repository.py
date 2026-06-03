from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.modules.financial.db_models import (
    ChartAccountDB,
    CostCenterDB,
    FinancialAccountDB,
    FinancialCategoryDB,
    PaymentTermDB,
)

FinancialDB = TypeVar("FinancialDB", ChartAccountDB, FinancialCategoryDB, CostCenterDB, FinancialAccountDB, PaymentTermDB)


def _decimal_to_str(value: Any) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _dt_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def chart_account_db_to_dict(row: ChartAccountDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "code": row.code,
        "name": row.name,
        "account_type": row.account_type,
        "parent_id": row.parent_id,
        "is_analytical": row.is_analytical,
        "normal_balance": row.normal_balance,
        "accepts_entries": row.accepts_entries,
        "status": row.status,
        "notes": row.notes,
        "metadata": row.metadata_json or {},
        "created_at": _dt_to_iso(row.created_at),
        "updated_at": _dt_to_iso(row.updated_at),
    }


def financial_category_db_to_dict(row: FinancialCategoryDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "code": row.code,
        "name": row.name,
        "category_type": row.category_type,
        "parent_id": row.parent_id,
        "chart_account_id": row.chart_account_id,
        "cash_flow_group": row.cash_flow_group,
        "affects_cash_flow": row.affects_cash_flow,
        "requires_cost_center": row.requires_cost_center,
        "status": row.status,
        "notes": row.notes,
        "metadata": row.metadata_json or {},
        "created_at": _dt_to_iso(row.created_at),
        "updated_at": _dt_to_iso(row.updated_at),
    }


def cost_center_db_to_dict(row: CostCenterDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "code": row.code,
        "name": row.name,
        "center_type": row.center_type,
        "parent_id": row.parent_id,
        "is_analytical": row.is_analytical,
        "responsible_name": row.responsible_name,
        "monthly_budget_amount": _decimal_to_str(row.monthly_budget_amount),
        "status": row.status,
        "notes": row.notes,
        "metadata": row.metadata_json or {},
        "created_at": _dt_to_iso(row.created_at),
        "updated_at": _dt_to_iso(row.updated_at),
    }


def financial_account_db_to_dict(row: FinancialAccountDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "name": row.name,
        "account_type": row.account_type,
        "institution_name": row.institution_name,
        "branch_number": row.branch_number,
        "account_number": row.account_number,
        "account_digit": row.account_digit,
        "pix_key": row.pix_key,
        "pix_key_type": row.pix_key_type,
        "currency": row.currency,
        "opening_balance_amount": _decimal_to_str(row.opening_balance_amount) or "0",
        "is_default_receivable": row.is_default_receivable,
        "is_default_payable": row.is_default_payable,
        "status": row.status,
        "notes": row.notes,
        "metadata": row.metadata_json or {},
        "created_at": _dt_to_iso(row.created_at),
        "updated_at": _dt_to_iso(row.updated_at),
    }


def payment_term_db_to_dict(row: PaymentTermDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "name": row.name,
        "term_type": row.term_type,
        "installments": row.installments,
        "first_due_days": row.first_due_days,
        "interval_days": row.interval_days,
        "generate_on_sale": row.generate_on_sale,
        "status": row.status,
        "notes": row.notes,
        "metadata": row.metadata_json or {},
        "created_at": _dt_to_iso(row.created_at),
        "updated_at": _dt_to_iso(row.updated_at),
    }


def add_row(db: Session, row: FinancialDB) -> FinancialDB:
    db.add(row)
    db.flush()
    return row


def get_by_id(db: Session, model: type[FinancialDB], row_id: str) -> FinancialDB | None:
    return db.get(model, row_id)


def get_by_company_code(db: Session, model: type[FinancialDB], company_id: str, code: str) -> FinancialDB | None:
    statement = select(model).where(model.company_id == company_id, model.code == code)  # type: ignore[attr-defined]
    return db.scalar(statement)


def get_payment_term_by_company_name(db: Session, company_id: str, name: str) -> PaymentTermDB | None:
    statement = select(PaymentTermDB).where(PaymentTermDB.company_id == company_id, PaymentTermDB.name == name)
    return db.scalar(statement)


def list_rows(
    db: Session,
    model: type[FinancialDB],
    *,
    company_id: str,
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    type_field: str | None = None,
    type_value: str | None = None,
    cash_flow_group: str | None = None,
) -> list[FinancialDB]:
    statement: Select[tuple[FinancialDB]] = select(model).where(model.company_id == company_id)  # type: ignore[attr-defined]

    if status is not None:
        statement = statement.where(model.status == status)  # type: ignore[attr-defined]

    if type_field is not None and type_value is not None:
        statement = statement.where(getattr(model, type_field) == type_value)

    if cash_flow_group is not None and hasattr(model, "cash_flow_group"):
        statement = statement.where(getattr(model, "cash_flow_group") == cash_flow_group)

    if search:
        normalized = f"%{search.strip()}%"
        clauses = [model.name.ilike(normalized)]  # type: ignore[attr-defined]
        if hasattr(model, "code"):
            clauses.append(getattr(model, "code").ilike(normalized))
        statement = statement.where(or_(*clauses))

    statement = statement.order_by(model.created_at.desc(), model.id.desc()).limit(limit).offset(offset)  # type: ignore[attr-defined]
    return list(db.scalars(statement).all())


def count_rows(db: Session, model: type[FinancialDB], company_id: str, status: str | None = None) -> int:
    statement = select(func.count()).select_from(model).where(model.company_id == company_id)  # type: ignore[attr-defined]
    if status is not None:
        statement = statement.where(model.status == status)  # type: ignore[attr-defined]
    return int(db.scalar(statement) or 0)
