from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.purchases_payables.schemas import PayablePaymentCreate, PurchaseConfirmPayload, PurchaseCreate, PurchaseCreateAndConfirmPayload, PurchaseUpdate, StatusChangePayload
from app.modules.purchases_payables.service import (
    cancel_payable,
    cancel_purchase,
    create_and_confirm_purchase,
    confirm_purchase,
    create_purchase_draft,
    get_payable_audit_events,
    get_payable_detail,
    get_purchase_audit_events,
    get_purchase_detail,
    get_purchase_history,
    get_purchases_payables_diagnostics,
    get_purchases_payables_overview_evidence,
    get_purchases_payables_rules,
    get_purchases_payables_summary,
    list_payables,
    list_purchases,
    pay_payable,
    update_purchase,
)
from app.modules.security.dependencies import get_current_principal, require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/purchases-payables", tags=["purchases-payables"], dependencies=[Depends(require_permission_dependency("view.purchasesPayables"))])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content=_api_response(success=False, message=message, data=None))


def _kwargs(request: Request, principal: SecurityPrincipal) -> dict[str, Any]:
    request_id = request.headers.get("x-request-id")
    return {
        "actor_id": principal.user_id,
        "source": AuditSource.API,
        "request_id": request_id,
        "correlation_id": request.headers.get("x-correlation-id") or request_id,
    }


def _assert_company_scope(company_id: str, principal: SecurityPrincipal) -> None:
    if company_id != principal.company_id:
        raise ValueError("Sessão autenticada não pertence à empresa informada.")


def _permission_response(permission_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=_api_response(
            success=False,
            message=f"Ação bloqueada. Permissão obrigatória: {permission_code}.",
            data=None,
        ),
    )


@router.get("/diagnostics", response_model=ApiResponse)
def diagnostics():
    return _api_response(success=True, message="Diagnóstico de Compras e Contas a Pagar carregado.", data=get_purchases_payables_diagnostics())


@router.get("/rules", response_model=ApiResponse)
def rules():
    return _api_response(success=True, message="Regras de Compras e Contas a Pagar carregadas.", data=get_purchases_payables_rules())


@router.get("/summary", response_model=ApiResponse)
def summary(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        return _api_response(success=True, message="Resumo de Compras e Contas a Pagar carregado.", data=get_purchases_payables_summary(db, company_id=company_id))
    except ValueError as error:
        return _error_response(error)


@router.get("/overview-evidence", response_model=ApiResponse)
def overview_evidence(
    company_id: str = Query(...),
    block: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        data = get_purchases_payables_overview_evidence(db, company_id=company_id, block=block, limit=limit)
        return _api_response(success=True, message="Evidências da visão geral de Compras e Contas a Pagar carregadas.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.get("/purchases", response_model=ApiResponse)
def list_purchases_route(
    company_id: str = Query(...),
    participant_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    purchase_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        data = list_purchases(db, company_id=company_id, participant_id=participant_id, status=status_filter, purchase_type=purchase_type, date_from=date_from, date_to=date_to, q=q, limit=limit, offset=offset, include_items=False)
        return _api_response(success=True, message="Compras/despesas carregadas.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.get("/purchases/export", response_model=ApiResponse)
def export_purchases_route(
    company_id: str = Query(...),
    participant_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    purchase_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        data = list_purchases(
            db,
            company_id=company_id,
            participant_id=participant_id,
            status=status_filter,
            purchase_type=purchase_type,
            date_from=date_from,
            date_to=date_to,
            q=q,
            limit=limit,
            offset=0,
            include_items=False,
            max_limit=5000,
        )
        return _api_response(success=True, message="Exportação de compras/despesas carregada.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.post("/purchases", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_route(
    payload: PurchaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Compra/despesa criada em rascunho.", data=create_purchase_draft(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.post("/purchases/create-and-confirm", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_and_confirm_purchase_route(
    payload: PurchaseCreateAndConfirmPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        _assert_company_scope(payload.purchase.company_id, principal)
        return _api_response(success=True, message="Compra/despesa registrada e título a pagar gerado.", data=create_and_confirm_purchase(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/purchases/{purchase_id}", response_model=ApiResponse)
def get_purchase_route(
    purchase_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(success=True, message="Compra/despesa carregada.", data=get_purchase_detail(db, purchase_id, expected_company_id=principal.company_id))
    except ValueError as error:
        return _error_response(error)


@router.patch("/purchases/{purchase_id}", response_model=ApiResponse)
def update_purchase_route(
    purchase_id: str,
    payload: PurchaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        return _api_response(success=True, message="Compra/despesa atualizada.", data=update_purchase(db, purchase_id, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.post("/purchases/{purchase_id}/confirm", response_model=ApiResponse)
def confirm_purchase_route(
    purchase_id: str,
    payload: PurchaseConfirmPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        return _api_response(success=True, message="Compra/despesa confirmada e títulos a pagar gerados.", data=confirm_purchase(db, purchase_id, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.post("/purchases/{purchase_id}/cancel", response_model=ApiResponse)
def cancel_purchase_route(
    purchase_id: str,
    payload: StatusChangePayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        return _api_response(success=True, message="Compra/despesa cancelada.", data=cancel_purchase(db, purchase_id, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/purchases/{purchase_id}/history", response_model=ApiResponse)
def purchase_history_route(
    purchase_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(success=True, message="Histórico da compra/despesa carregado.", data=get_purchase_history(db, purchase_id, expected_company_id=principal.company_id))
    except ValueError as error:
        return _error_response(error)


@router.get("/purchases/{purchase_id}/audit", response_model=ApiResponse)
def purchase_audit_route(
    purchase_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(success=True, message="Auditoria da compra/despesa carregada.", data=get_purchase_audit_events(db, purchase_id, expected_company_id=principal.company_id))
    except ValueError as error:
        return _error_response(error)


@router.get("/payables", response_model=ApiResponse)
def list_payables_route(
    company_id: str = Query(...),
    participant_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    purchase_id: str | None = Query(None),
    financial_category_id: str | None = Query(None),
    cost_center_id: str | None = Query(None),
    expected_financial_account_id: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    open_amount_min: Decimal | None = Query(None),
    open_amount_max: Decimal | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        data = list_payables(
            db,
            company_id=company_id,
            participant_id=participant_id,
            status=status_filter,
            purchase_id=purchase_id,
            financial_category_id=financial_category_id,
            cost_center_id=cost_center_id,
            expected_financial_account_id=expected_financial_account_id,
            due_from=due_from,
            due_to=due_to,
            open_amount_min=open_amount_min,
            open_amount_max=open_amount_max,
            q=q,
            limit=limit,
            offset=offset,
        )
        return _api_response(success=True, message="Títulos a pagar carregados.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.get("/payables/export", response_model=ApiResponse)
def export_payables_route(
    company_id: str = Query(...),
    participant_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    purchase_id: str | None = Query(None),
    financial_category_id: str | None = Query(None),
    cost_center_id: str | None = Query(None),
    expected_financial_account_id: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    open_amount_min: Decimal | None = Query(None),
    open_amount_max: Decimal | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_company_scope(company_id, principal)
        data = list_payables(
            db,
            company_id=company_id,
            participant_id=participant_id,
            status=status_filter,
            purchase_id=purchase_id,
            financial_category_id=financial_category_id,
            cost_center_id=cost_center_id,
            expected_financial_account_id=expected_financial_account_id,
            due_from=due_from,
            due_to=due_to,
            open_amount_min=open_amount_min,
            open_amount_max=open_amount_max,
            q=q,
            limit=limit,
            offset=0,
            max_limit=5000,
        )
        return _api_response(success=True, message="Exportação de títulos a pagar carregada.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.get("/payables/{title_id}", response_model=ApiResponse)
def get_payable_route(
    title_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(success=True, message="Título a pagar carregado.", data=get_payable_detail(db, title_id, expected_company_id=principal.company_id))
    except ValueError as error:
        return _error_response(error)


@router.post("/payables/{title_id}/cancel", response_model=ApiResponse)
def cancel_payable_route(
    title_id: str,
    payload: StatusChangePayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        return _api_response(success=True, message="Título a pagar cancelado.", data=cancel_payable(db, title_id, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/payables/{title_id}/audit", response_model=ApiResponse)
def payable_audit_route(
    title_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(success=True, message="Auditoria do título a pagar carregada.", data=get_payable_audit_events(db, title_id, expected_company_id=principal.company_id))
    except ValueError as error:
        return _error_response(error)


@router.post("/payments", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def pay_payable_route(
    payload: PayablePaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if "payables.pay" not in principal.permission_codes:
            return _permission_response("payables.pay")
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Pagamento de título a pagar registrado.", data=pay_payable(db, payload, principal=principal, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)
