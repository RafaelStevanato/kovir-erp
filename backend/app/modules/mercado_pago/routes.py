from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.mercado_pago.schemas import MercadoPagoAccountUpdate
from app.modules.mercado_pago.service import (
    get_mercado_pago_audit_events,
    get_mercado_pago_diagnostics,
    get_mercado_pago_rules,
    get_or_create_mercado_pago_account,
    list_mercado_pago_chargebacks,
    list_mercado_pago_checkout_preferences,
    list_mercado_pago_payments,
    list_mercado_pago_refunds,
    list_mercado_pago_releases,
    list_mercado_pago_webhooks,
    mark_mercado_pago_preconfigured,
    update_mercado_pago_account,
)
from app.modules.security.dependencies import get_current_principal, require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Mercado Pago"], dependencies=[Depends(require_permission_dependency("users.manage"))])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    if "não encontr" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content=_api_response(success=False, message=message, data=None))


@router.get("/mercado-pago/diagnostics", response_model=ApiResponse)
def get_mercado_pago_diagnostics_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Diagnóstico do módulo Mercado Pago carregado com sucesso.",
            data=get_mercado_pago_diagnostics(db, company_id or principal.company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/rules", response_model=ApiResponse)
def get_mercado_pago_rules_route():
    return _api_response(success=True, message="Regras do módulo Mercado Pago carregadas com sucesso.", data=get_mercado_pago_rules())


@router.get("/mercado-pago/account", response_model=ApiResponse)
def get_mercado_pago_account_route(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Conta Mercado Pago carregada com sucesso.",
            data=get_or_create_mercado_pago_account(db, company_id=company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/mercado-pago/account/{account_id}", response_model=ApiResponse)
def update_mercado_pago_account_route(
    account_id: str,
    payload: MercadoPagoAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        account = update_mercado_pago_account(
            db,
            account_id=account_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Conta Mercado Pago atualizada com sucesso.", data=account)
    except ValueError as error:
        return _error_response(error)


@router.post("/mercado-pago/account/preconfigure", response_model=ApiResponse)
def preconfigure_mercado_pago_account_route(
    company_id: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        account = mark_mercado_pago_preconfigured(
            db,
            company_id=company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request) if request else None,
            correlation_id=_correlation_id_from_request(request) if request else None,
        )
        return _api_response(success=True, message="Mercado Pago marcado como pré-configurado.", data=account)
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/account/{account_id}/audit", response_model=ApiResponse)
def get_mercado_pago_account_audit_route(account_id: str, db: Session = Depends(get_db)):
    try:
        return _api_response(
            success=True,
            message="Auditoria da conta Mercado Pago carregada com sucesso.",
            data=get_mercado_pago_audit_events(db, account_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/payments", response_model=ApiResponse)
def list_mercado_pago_payments_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Pagamentos Mercado Pago carregados com sucesso.", data=list_mercado_pago_payments(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/releases", response_model=ApiResponse)
def list_mercado_pago_releases_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Liberações/repasses Mercado Pago carregados com sucesso.", data=list_mercado_pago_releases(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/webhooks", response_model=ApiResponse)
def list_mercado_pago_webhooks_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Webhooks Mercado Pago carregados com sucesso.", data=list_mercado_pago_webhooks(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/refunds", response_model=ApiResponse)
def list_mercado_pago_refunds_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Reembolsos Mercado Pago carregados com sucesso.", data=list_mercado_pago_refunds(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/chargebacks", response_model=ApiResponse)
def list_mercado_pago_chargebacks_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Chargebacks Mercado Pago carregados com sucesso.", data=list_mercado_pago_chargebacks(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.get("/mercado-pago/checkout-preferences", response_model=ApiResponse)
def list_mercado_pago_checkout_preferences_route(company_id: str = Query(...), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db)):
    try:
        return _api_response(success=True, message="Preferências Checkout Mercado Pago carregadas com sucesso.", data=list_mercado_pago_checkout_preferences(db, company_id=company_id, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)
