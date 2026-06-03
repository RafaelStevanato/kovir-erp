from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.cash_flow.service import (
    get_cash_flow_accounts,
    get_cash_flow_daily,
    get_cash_flow_diagnostics,
    get_cash_flow_overview_evidence,
    get_cash_flow_pending,
    get_cash_flow_reconciliation_status,
    get_cash_flow_rules,
    get_cash_flow_summary,
)
from app.modules.security.dependencies import require_permission_dependency
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/cash-flow", tags=["cash-flow"], dependencies=[Depends(require_permission_dependency("view.cashFlow"))])


@router.get("/diagnostics", response_model=ApiResponse)
def diagnostics():
    return {"success": True, "message": "Diagnóstico de fluxo de caixa carregado.", "data": get_cash_flow_diagnostics()}


@router.get("/rules", response_model=ApiResponse)
def rules():
    return {"success": True, "message": "Regras de fluxo de caixa carregadas.", "data": get_cash_flow_rules()}


@router.get("/summary", response_model=ApiResponse)
def summary(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), db: Session = Depends(get_db)):
    data = get_cash_flow_summary(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id)
    return {"success": True, "message": "Resumo de fluxo de caixa carregado.", "data": data}


@router.get("/daily", response_model=ApiResponse)
def daily(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), db: Session = Depends(get_db)):
    data = get_cash_flow_daily(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id)
    return {"success": True, "message": "Fluxo de caixa diário carregado.", "data": data}


@router.get("/accounts", response_model=ApiResponse)
def accounts(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    data = get_cash_flow_accounts(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id, limit=limit, offset=offset)
    return {"success": True, "message": "Fluxo de caixa por conta carregado.", "data": data}


@router.get("/pending", response_model=ApiResponse)
def pending(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    data = get_cash_flow_pending(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id, limit=limit)
    return {"success": True, "message": "Pendências de fluxo de caixa carregadas.", "data": data}


@router.get("/overview-evidence", response_model=ApiResponse)
def overview_evidence(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), limit: int = Query(5000, ge=1, le=5000), db: Session = Depends(get_db)):
    data = get_cash_flow_overview_evidence(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id, limit=limit)
    return {"success": True, "message": "Evidências da visão geral do fluxo de caixa carregadas.", "data": data}


@router.get("/reconciliation-status", response_model=ApiResponse)
def reconciliation_status(company_id: str = Query(...), start_date: date | None = Query(None), end_date: date | None = Query(None), financial_account_id: str | None = Query(None), db: Session = Depends(get_db)):
    data = get_cash_flow_reconciliation_status(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id)
    return {"success": True, "message": "Status de conciliação do fluxo de caixa carregado.", "data": data}
