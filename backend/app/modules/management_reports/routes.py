from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.modules.management_reports.service import (
    get_accountant_pack,
    get_available_companies,
    get_company_context,
    get_financial_close_mvp,
    get_financial_cycle_report,
    get_health_indicator_details,
    get_management_report_rules,
    get_mvp_health,
    get_operational_backlog,
    get_preparatory_fiscal_documents,
    get_title_references,
)
from app.shared.schemas import ApiResponse


router = APIRouter(prefix="/management-reports", tags=["Management Reports"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    code = status.HTTP_400_BAD_REQUEST
    lowered = message.lower()
    if "não encontrada" in lowered or "não encontrado" in lowered:
        code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=code,
        content=_api_response(success=False, message=message, data=None),
    )


def _resolve_report_company_id(company_id: str | None, principal: SecurityPrincipal) -> str:
    resolved = company_id or principal.company_id
    if resolved != principal.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Relatório bloqueado: empresa solicitada não pertence à sessão autenticada.",
        )
    return resolved


@router.get("/rules", response_model=ApiResponse)
def get_management_report_rules_route():
    return _api_response(
        success=True,
        message="Regras de relatórios gerenciais carregadas com sucesso.",
        data=get_management_report_rules(),
    )


@router.get("/available-companies", response_model=ApiResponse)
def get_available_companies_route(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        raw = get_available_companies(db, limit=max(1, limit))
        scoped_items = [
            item
            for item in (raw.get("items") or [])
            if item.get("id") == principal.company_id
        ]
        return _api_response(
            success=True,
            message="Empresas disponíveis para relatórios carregadas com sucesso.",
            data={
                **raw,
                "items": scoped_items,
                "total_returned": len(scoped_items),
                "notes": ["Lista limitada à empresa da sessão autenticada."],
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/company-context", response_model=ApiResponse)
def get_company_context_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Contexto executivo da empresa carregado com sucesso.",
            data=get_company_context(db, company_id=resolved_company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/financial-cycle", response_model=ApiResponse)
def get_financial_cycle_report_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Relatório do ciclo financeiro carregado com sucesso.",
            data=get_financial_cycle_report(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/mvp-health", response_model=ApiResponse)
def get_mvp_health_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Saúde do Kovir carregada com sucesso.",
            data=get_mvp_health(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/health-indicator-details", response_model=ApiResponse)
def get_health_indicator_details_route(
    indicator: str = Query(...),
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Detalhes do indicador carregados com sucesso.",
            data=get_health_indicator_details(
                db,
                company_id=resolved_company_id,
                indicator=indicator,
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/backlog", response_model=ApiResponse)
def get_operational_backlog_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Pendências operacionais carregadas com sucesso.",
            data=get_operational_backlog(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/title-references", response_model=ApiResponse)
def get_title_references_route(
    company_id: str | None = Query(default=None),
    direction: str | None = Query(default=None, description="receivable ou payable"),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    due_from: date | None = Query(default=None),
    due_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    export_all: bool = Query(default=False),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Referências humanas de títulos carregadas com sucesso.",
            data=get_title_references(
                db,
                company_id=resolved_company_id,
                direction=direction,
                status=status_filter,
                search=search,
                due_from=due_from,
                due_to=due_to,
                limit=limit,
                offset=offset,
                export_all=export_all,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/preparatory-fiscal-documents", response_model=ApiResponse)
def get_preparatory_fiscal_documents_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    export_all: bool = Query(default=False),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Documentos fiscais preparatórios carregados com sucesso.",
            data=get_preparatory_fiscal_documents(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                export_all=export_all,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/financial-close-mvp", response_model=ApiResponse)
def get_financial_close_mvp_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Prontidão de fechamento financeiro carregada com sucesso.",
            data=get_financial_close_mvp(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/accountant-pack", response_model=ApiResponse)
def get_accountant_pack_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_details: bool = Query(default=False),
    export_all: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("reports.read")),
):
    try:
        resolved_company_id = _resolve_report_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Relatório para contador carregado com sucesso.",
            data=get_accountant_pack(
                db,
                company_id=resolved_company_id,
                start_date=start_date,
                end_date=end_date,
                include_details=include_details,
                export_all=export_all,
                limit=limit,
            ),
        )
    except ValueError as error:
        return _error_response(error)
