from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.company.schemas import CompanyCreate, CompanyUpdate
from app.modules.company.service import (
    create_company,
    get_company,
    get_company_audit_events,
    get_company_diagnostics,
    get_company_rules,
    list_companies,
    update_company,
)
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.shared.audit import AuditSource


router = APIRouter(tags=["Company"])


def _api_response(
    success: bool,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": data,
    }


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(exc: ValueError) -> JSONResponse:
    message = str(exc)

    status_code = status.HTTP_400_BAD_REQUEST

    if "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=_api_response(
            success=False,
            message=message,
            data=None,
        ),
    )


@router.get("/companies")
def list_companies_route(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _ = (limit, offset)
    companies = [get_company(db, principal.company_id)]

    return _api_response(
        success=True,
        message="Empresas carregadas com sucesso.",
        data=companies,
    )


@router.post("/companies", status_code=status.HTTP_201_CREATED)
def create_company_route(
    payload: CompanyCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        require_permission(principal, "users.manage")
        company = create_company(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Empresa criada com sucesso.",
            data=company,
        )

    except ValueError as exc:
        return _error_response(exc)


@router.get("/companies/{company_id}")
def get_company_route(
    company_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        if company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado. Empresa fora da sessão autenticada.",
            )
        company = get_company(db, company_id)

        return _api_response(
            success=True,
            message="Empresa carregada com sucesso.",
            data=company,
        )

    except ValueError as exc:
        return _error_response(exc)


@router.patch("/companies/{company_id}")
def update_company_route(
    company_id: str,
    payload: CompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        require_permission(principal, "company.write")
        if company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado. Empresa fora da sessão autenticada.",
            )
        company = update_company(
            db=db,
            company_id=company_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Empresa atualizada com sucesso.",
            data=company,
        )

    except ValueError as exc:
        return _error_response(exc)


@router.get("/companies/{company_id}/audit")
def get_company_audit_events_route(
    company_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        require_permission(principal, "view.company")
        if company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado. Empresa fora da sessão autenticada.",
            )
        audit_events = get_company_audit_events(db, company_id)

        return _api_response(
            success=True,
            message="Eventos de auditoria da empresa carregados com sucesso.",
            data=audit_events,
        )

    except ValueError as exc:
        return _error_response(exc)


@router.get("/system/company-rules")
def get_company_rules_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "view.company")
    return _api_response(
        success=True,
        message="Regras de empresa do Kovir carregadas com sucesso.",
        data=get_company_rules(),
    )


@router.get("/system/company-diagnostics")
def get_company_diagnostics_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "view.company")
    return _api_response(
        success=True,
        message="Diagnóstico técnico do módulo Company carregado com sucesso.",
        data={
            **get_company_diagnostics(db, company_id=principal.company_id),
            "total_companies": 1,
            "actor_company_id": principal.company_id,
            "scope": "session_company_only",
        },
    )
