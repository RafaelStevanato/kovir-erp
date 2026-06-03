from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.accounts_receivable.schemas import FinancialTitleCreate, FinancialTitleStatusChange, FinancialTitleUpdate, GenerateReceivablesFromSalePayload
from app.modules.accounts_receivable.service import (
    cancel_receivable,
    create_manual_receivable,
    generate_receivables_from_sale_id,
    get_accounts_receivable_diagnostics,
    get_accounts_receivable_rules,
    get_receivable,
    get_receivable_audit_events,
    get_receivable_history,
    get_receivables_summary,
    list_receivables,
    update_receivable,
)
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/accounts-receivable", tags=["accounts-receivable"])


def _api_response(success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    lowered = message.lower()
    if "sessao autenticada" in lowered or "sess?o autenticada" in lowered:
        status_code = status.HTTP_403_FORBIDDEN
    elif "nao encontrado" in lowered or "n?o encontrado" in lowered or "nao encontrada" in lowered or "n?o encontrada" in lowered:
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content=_api_response(False, message, None))


def _require_read(principal: SecurityPrincipal) -> None:
    require_permission(principal, "view.accountsReceivable")
    require_permission(principal, "finance.read")


def _require_write(principal: SecurityPrincipal) -> None:
    require_permission(principal, "view.accountsReceivable")
    require_permission(principal, "finance.write")


def _resolve_company_id(company_id: str, principal: SecurityPrincipal) -> str:
    if company_id != principal.company_id:
        raise ValueError("Sessao autenticada nao pertence a empresa informada.")
    return company_id


def _assert_payload_company(payload: FinancialTitleCreate, principal: SecurityPrincipal) -> None:
    if payload.company_id != principal.company_id:
        raise ValueError("Sessao autenticada nao pertence a empresa informada.")


def _kwargs(request: Request, principal: SecurityPrincipal) -> dict[str, Any]:
    return {
        "actor_id": principal.user_id,
        "source": AuditSource.API,
        "request_id": _request_id_from_request(request),
        "correlation_id": _correlation_id_from_request(request),
    }


@router.get("/diagnostics", response_model=ApiResponse)
def diagnostics(principal: SecurityPrincipal = Depends(get_current_principal)):
    _require_read(principal)
    return _api_response(True, "Diagnostico de Contas a Receber carregado.", get_accounts_receivable_diagnostics())


@router.get("/rules", response_model=ApiResponse)
def rules(principal: SecurityPrincipal = Depends(get_current_principal)):
    _require_read(principal)
    return _api_response(True, "Regras de Contas a Receber carregadas.", get_accounts_receivable_rules())


@router.get("/summary", response_model=ApiResponse)
def summary(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        data = get_receivables_summary(db, company_id=resolved_company_id)
        return _api_response(True, "Resumo de Contas a Receber carregado.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/titles", response_model=ApiResponse)
def list_titles(
    company_id: str = Query(...),
    participant_id: str | None = Query(None),
    status: str | None = Query(None),
    collection_status: str | None = Query(None),
    fiscal_status: str | None = Query(None),
    sale_id: str | None = Query(None),
    source_type: str | None = Query(None),
    due_from: date | None = Query(None),
    due_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        data = list_receivables(
            db,
            company_id=resolved_company_id,
            participant_id=participant_id,
            status=status,
            collection_status=collection_status,
            fiscal_status=fiscal_status,
            sale_id=sale_id,
            source_type=source_type,
            due_from=due_from,
            due_to=due_to,
            q=q,
            limit=limit,
            offset=offset,
        )
        return _api_response(True, "Titulos a receber carregados.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/titles", response_model=ApiResponse)
def create_title(
    payload: FinancialTitleCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_write(principal)
        _assert_payload_company(payload, principal)
        data = create_manual_receivable(db, payload, **_kwargs(request, principal))
        return _api_response(True, "Titulo a receber criado.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/titles/{title_id}", response_model=ApiResponse)
def get_title(
    title_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_read(principal)
        data = get_receivable(db, title_id, expected_company_id=principal.company_id)
        return _api_response(True, "Titulo a receber carregado.", data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/titles/{title_id}", response_model=ApiResponse)
def patch_title(
    title_id: str,
    payload: FinancialTitleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_write(principal)
        data = update_receivable(db, title_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal))
        return _api_response(True, "Titulo a receber atualizado.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/titles/{title_id}/cancel", response_model=ApiResponse)
def cancel_title(
    title_id: str,
    payload: FinancialTitleStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_write(principal)
        data = cancel_receivable(db, title_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal))
        return _api_response(True, "Titulo a receber cancelado.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/titles/{title_id}/history", response_model=ApiResponse)
def title_history(
    title_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_read(principal)
        data = get_receivable_history(db, title_id, expected_company_id=principal.company_id)
        return _api_response(True, "Historico do titulo carregado.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/titles/{title_id}/audit", response_model=ApiResponse)
def title_audit(
    title_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_read(principal)
        data = get_receivable_audit_events(db, title_id, expected_company_id=principal.company_id)
        return _api_response(True, "Auditoria do titulo carregada.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/from-sale/{sale_id}", response_model=ApiResponse)
def from_sale(
    sale_id: str,
    payload: GenerateReceivablesFromSalePayload,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_write(principal)
        data = generate_receivables_from_sale_id(
            db,
            sale_id,
            expected_company_id=principal.company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
            reason=payload.reason,
        )
        return _api_response(True, "Titulos a receber gerados a partir da venda.", data)
    except ValueError as error:
        return _error_response(error)
