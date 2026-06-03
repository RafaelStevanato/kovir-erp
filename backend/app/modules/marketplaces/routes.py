from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.marketplaces.schemas import MarketplaceAccountCreate, MarketplaceAccountUpdate
from app.modules.marketplaces.service import (
    create_marketplace_account_from_payload,
    get_marketplace_audit_events,
    get_marketplaces_diagnostics,
    get_marketplaces_providers,
    get_marketplaces_rules,
    list_marketplace_accounts,
    list_marketplace_sync_runs,
    update_marketplace_account,
)
from app.modules.security.dependencies import get_current_principal, require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Marketplaces"], dependencies=[Depends(require_permission_dependency("users.manage"))])


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


@router.get("/marketplaces/diagnostics", response_model=ApiResponse)
def get_marketplaces_diagnostics_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        resolved_company_id = company_id or principal.company_id
        return _api_response(
            success=True,
            message="Diagnóstico do módulo marketplaces carregado com sucesso.",
            data=get_marketplaces_diagnostics(db, resolved_company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/marketplaces/rules", response_model=ApiResponse)
def get_marketplaces_rules_route():
    return _api_response(
        success=True,
        message="Regras do módulo marketplaces carregadas com sucesso.",
        data=get_marketplaces_rules(),
    )


@router.get("/marketplaces/providers", response_model=ApiResponse)
def get_marketplaces_providers_route():
    return _api_response(
        success=True,
        message="Provedores de marketplace/gateway carregados com sucesso.",
        data=get_marketplaces_providers(),
    )


@router.get("/marketplaces/accounts", response_model=ApiResponse)
def list_marketplace_accounts_route(
    company_id: str = Query(...),
    provider_code: str | None = Query(default=None),
    provider_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Contas de marketplaces carregadas com sucesso.",
            data=list_marketplace_accounts(
                db,
                company_id=company_id,
                provider_code=provider_code,
                provider_type=provider_type,
                status=status_filter,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/marketplaces/accounts", response_model=ApiResponse)
def create_marketplace_account_route(
    payload: MarketplaceAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        account = create_marketplace_account_from_payload(
            db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Conta de marketplace criada com sucesso.", data=account)
    except ValueError as error:
        return _error_response(error)


@router.patch("/marketplaces/accounts/{account_id}", response_model=ApiResponse)
def update_marketplace_account_route(
    account_id: str,
    payload: MarketplaceAccountUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        account = update_marketplace_account(
            db,
            account_id=account_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Conta de marketplace atualizada com sucesso.", data=account)
    except ValueError as error:
        return _error_response(error)


@router.get("/marketplaces/accounts/{account_id}/audit", response_model=ApiResponse)
def get_marketplace_account_audit_route(
    account_id: str,
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Auditoria da conta de marketplace carregada com sucesso.",
            data=get_marketplace_audit_events(db, account_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/marketplaces/sync-runs", response_model=ApiResponse)
def list_marketplace_sync_runs_route(
    company_id: str = Query(...),
    marketplace_account_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Histórico de sincronizações de marketplace carregado com sucesso.",
            data=list_marketplace_sync_runs(
                db,
                company_id=company_id,
                marketplace_account_id=marketplace_account_id,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)
