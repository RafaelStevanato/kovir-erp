from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.modules.cash.schemas import ManualFinancialMovementCreate, ManualFinancialMovementReverse, SettlementCreate, SettlementReverse
from app.modules.cash.service import (
    create_manual_movement,
    get_cash_diagnostics,
    get_cash_rules,
    get_cash_summary,
    get_settlement_detail,
    list_account_balances,
    list_movements,
    list_settlements,
    receive_title,
    reverse_manual_movement,
    reverse_settlement,
)
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/cash", tags=["cash"])


def _error_response(error: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "message": str(error), "data": None},
    )


@router.get("/diagnostics", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def diagnostics():
    return {"success": True, "message": "Diagnóstico de recebimentos e movimentos carregado.", "data": get_cash_diagnostics()}


@router.get("/rules", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def rules():
    return {"success": True, "message": "Regras de recebimentos e movimentos carregadas.", "data": get_cash_rules()}


@router.get("/summary", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def summary(company_id: str = Query(...), db: Session = Depends(get_db)):
    try:
        return {"success": True, "message": "Resumo de caixa interno carregado.", "data": get_cash_summary(db, company_id=company_id)}
    except ValueError as error:
        return _error_response(error)


@router.post("/settlements", response_model=ApiResponse)
def create_settlement(
    payload: SettlementCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("cash.receive")),
):
    try:
        data = receive_title(db, payload, actor_id=principal.user_id, source=AuditSource.API)
        return {"success": True, "message": "Recebimento registrado com baixa do título e movimento financeiro.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.get("/settlements", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def get_settlements(
    company_id: str = Query(...),
    financial_title_id: str | None = Query(None),
    financial_account_id: str | None = Query(None),
    payment_method_id: str | None = Query(None),
    status: str | None = Query(None),
    settlement_from: date | None = Query(None),
    settlement_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = list_settlements(db, company_id=company_id, financial_title_id=financial_title_id, financial_account_id=financial_account_id, payment_method_id=payment_method_id, status=status, settlement_from=settlement_from, settlement_to=settlement_to, q=q, limit=limit, offset=offset)
        return {"success": True, "message": "Baixas/recebimentos carregados.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.get("/settlements/{settlement_id}", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def get_settlement(settlement_id: str, db: Session = Depends(get_db)):
    try:
        return {"success": True, "message": "Baixa/recebimento carregado.", "data": get_settlement_detail(db, settlement_id)}
    except ValueError as error:
        return _error_response(error)


@router.post("/settlements/{settlement_id}/reverse", response_model=ApiResponse)
def reverse(
    settlement_id: str,
    payload: SettlementReverse,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("cash.reverse")),
):
    try:
        data = reverse_settlement(db, settlement_id, payload, actor_id=principal.user_id, source=AuditSource.API)
        return {"success": True, "message": "Baixa/recebimento estornado com movimento financeiro removido.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.post("/movements", response_model=ApiResponse)
def post_manual_movement(
    payload: ManualFinancialMovementCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("cash.receive")),
):
    try:
        data = create_manual_movement(db, payload, actor_id=principal.user_id, source=AuditSource.API)
        return {"success": True, "message": "Movimento financeiro manual registrado.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.post("/movements/{movement_id}/reverse", response_model=ApiResponse)
def reverse_movement(
    movement_id: str,
    payload: ManualFinancialMovementReverse,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("cash.reverse")),
):
    try:
        data = reverse_manual_movement(db, movement_id, payload, company_id=principal.company_id, actor_id=principal.user_id, source=AuditSource.API)
        return {"success": True, "message": "Movimento financeiro manual estornado com contrapartida registrada.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.get("/movements", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def get_movements(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    direction: str | None = Query(None),
    movement_type: str | None = Query(None),
    status: str | None = Query(None),
    reconciliation_status: str | None = Query(None),
    movement_from: date | None = Query(None),
    movement_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        data = list_movements(db, company_id=company_id, financial_account_id=financial_account_id, direction=direction, movement_type=movement_type, status=status, reconciliation_status=reconciliation_status, movement_from=movement_from, movement_to=movement_to, q=q, limit=limit, offset=offset)
        return {"success": True, "message": "Movimentos financeiros carregados.", "data": data}
    except ValueError as error:
        return _error_response(error)


@router.get("/balances", response_model=ApiResponse, dependencies=[Depends(require_permission_dependency("view.cash"))])
def balances(company_id: str = Query(...), financial_account_id: str | None = Query(None), db: Session = Depends(get_db)):
    try:
        data = list_account_balances(db, company_id=company_id, financial_account_id=financial_account_id)
        return {"success": True, "message": "Saldos internos carregados.", "data": data}
    except ValueError as error:
        return _error_response(error)
