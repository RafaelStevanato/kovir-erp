from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.modules.company.repository import get_company as repository_get_company
from app.modules.financial.db_models import FinancialPeriodClosureDB
from app.modules.financial.period_schemas import FinancialPeriodClosureCreate, FinancialPeriodClosureDeactivate
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


def period_closure_to_dict(row: FinancialPeriodClosureDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
        "status": row.status,
        "reason": row.reason,
        "created_by_user_id": row.created_by_user_id,
        "metadata": row.metadata_json,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _normalize_event_date(event_date: date | datetime | None) -> date | None:
    if event_date is None:
        return None
    if isinstance(event_date, datetime):
        return event_date.date()
    return event_date


def _assert_company_exists(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    if repository_get_company(db, company_id) is None:
        raise ValueError("Empresa não encontrada.")


def _find_overlap(
    db: Session,
    *,
    company_id: str,
    start_date: date,
    end_date: date,
    exclude_id: str | None = None,
) -> FinancialPeriodClosureDB | None:
    stmt = select(FinancialPeriodClosureDB).where(
        FinancialPeriodClosureDB.company_id == company_id,
        FinancialPeriodClosureDB.status == "active",
        FinancialPeriodClosureDB.start_date <= end_date,
        FinancialPeriodClosureDB.end_date >= start_date,
    )
    if exclude_id:
        stmt = stmt.where(FinancialPeriodClosureDB.id != exclude_id)
    return db.scalar(stmt.order_by(FinancialPeriodClosureDB.start_date.asc()))


def list_period_closures(
    db: Session,
    *,
    company_id: str,
    status: str | None = "active",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    stmt = select(FinancialPeriodClosureDB).where(FinancialPeriodClosureDB.company_id == company_id)
    if status:
        stmt = stmt.where(FinancialPeriodClosureDB.status == status)
    rows = db.scalars(
        stmt.order_by(
            FinancialPeriodClosureDB.start_date.desc(),
            FinancialPeriodClosureDB.created_at.desc(),
        ).limit(limit).offset(offset)
    ).all()
    return [period_closure_to_dict(row) for row in rows]


def create_period_closure(
    db: Session,
    payload: FinancialPeriodClosureCreate,
    *,
    actor_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, payload.company_id)
    if actor_id is not None:
        assert_valid_id(actor_id, "user")
    overlap = _find_overlap(
        db,
        company_id=payload.company_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    if overlap is not None:
        raise ValueError(
            "Já existe fechamento ativo que conflita com o período informado: "
            f"{overlap.start_date.isoformat()} até {overlap.end_date.isoformat()}."
        )

    now = utc_now()
    row = FinancialPeriodClosureDB(
        id=generate_id("fclose"),
        company_id=payload.company_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="active",
        reason=payload.reason,
        created_by_user_id=actor_id,
        metadata_json=payload.metadata or {},
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.flush()
        data = period_closure_to_dict(row)
        db.commit()
        return data
    except Exception:
        db.rollback()
        raise


def deactivate_period_closure(
    db: Session,
    closure_id: str,
    payload: FinancialPeriodClosureDeactivate,
    *,
    expected_company_id: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    assert_valid_id(closure_id, "fclose")
    if actor_id is not None:
        assert_valid_id(actor_id, "user")
    row = db.scalar(select(FinancialPeriodClosureDB).where(FinancialPeriodClosureDB.id == closure_id).with_for_update())
    if row is None:
        raise ValueError("Fechamento de período não encontrado.")
    if row.company_id != expected_company_id:
        raise ValueError("Fechamento de período pertence a outra empresa.")
    if row.status != "active":
        raise ValueError("Fechamento de período já está inativo.")
    now = utc_now()
    row.status = "inactive"
    row.updated_at = now
    row.metadata_json = {
        **(row.metadata_json or {}),
        "deactivation_reason": payload.reason,
        "deactivated_at": now.isoformat(),
        "deactivated_by_user_id": actor_id,
    }
    try:
        db.flush()
        data = period_closure_to_dict(row)
        db.commit()
        return data
    except Exception:
        db.rollback()
        raise


def assert_period_open(
    db: Session,
    *,
    company_id: str,
    event_date: date | datetime | None,
    operation_label: str,
) -> None:
    normalized = _normalize_event_date(event_date)
    if normalized is None:
        return
    overlap = _find_overlap(
        db,
        company_id=company_id,
        start_date=normalized,
        end_date=normalized,
    )
    if overlap is None:
        return
    raise ValueError(
        "Período financeiro fechado para a data "
        f"{normalized.isoformat()} ({overlap.start_date.isoformat()} até {overlap.end_date.isoformat()}). "
        f"Operação bloqueada: {operation_label}."
    )


def assert_period_open_range(
    db: Session,
    *,
    company_id: str,
    start_date: date | datetime | None,
    end_date: date | datetime | None,
    operation_label: str,
) -> None:
    normalized_start = _normalize_event_date(start_date)
    normalized_end = _normalize_event_date(end_date)
    if normalized_start is None and normalized_end is None:
        return
    if normalized_start is None:
        normalized_start = normalized_end
    if normalized_end is None:
        normalized_end = normalized_start
    if normalized_end < normalized_start:
        normalized_start, normalized_end = normalized_end, normalized_start
    overlap = _find_overlap(
        db,
        company_id=company_id,
        start_date=normalized_start,
        end_date=normalized_end,
    )
    if overlap is None:
        return
    raise ValueError(
        "Período financeiro fechado no intervalo "
        f"{normalized_start.isoformat()} até {normalized_end.isoformat()} "
        f"(conflito com fechamento {overlap.start_date.isoformat()} até {overlap.end_date.isoformat()}). "
        f"Operação bloqueada: {operation_label}."
    )
