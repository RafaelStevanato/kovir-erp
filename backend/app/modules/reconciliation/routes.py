from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.reconciliation.schemas import (
    BankStatementImportCreate,
    IgnoreStatementLine,
    OfxStatementImportText,
    ReconciliationMatchCreate,
    ReverseReconciliationMatch,
)
from app.modules.reconciliation.service import (
    confirm_match,
    get_reconciliation_diagnostics,
    get_reconciliation_overview_evidence,
    get_reconciliation_rules,
    get_reconciliation_summary,
    ignore_statement_line,
    import_ofx_statement_text,
    import_statement,
    list_reconciliation_matches,
    list_statement_imports,
    list_statement_lines,
    reverse_match,
    suggest_matches,
)
from app.modules.security.dependencies import get_current_principal, require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse

router = APIRouter(
    prefix="/reconciliation",
    tags=["reconciliation"],
    dependencies=[Depends(require_permission_dependency("view.reconciliation"))],
)


def _resolve_company(principal: SecurityPrincipal, company_id: str) -> str:
    if company_id != principal.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Empresa informada não corresponde ao contexto ativo do usuário.",
        )
    return company_id


def _error_response(error: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "message": str(error), "data": None},
    )


@router.get("/diagnostics", response_model=ApiResponse)
def diagnostics():
    return {"success": True, "message": "Diagnóstico de conciliação carregado.", "data": get_reconciliation_diagnostics()}


@router.get("/rules", response_model=ApiResponse)
def rules():
    return {"success": True, "message": "Regras de conciliação carregadas.", "data": get_reconciliation_rules()}


@router.get("/summary", response_model=ApiResponse)
def summary(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_reconciliation_summary(
            db,
            company_id=_resolve_company(principal, company_id),
            financial_account_id=financial_account_id,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Resumo de conciliação carregado.", "data": data}


@router.get("/overview-evidence", response_model=ApiResponse)
def overview_evidence(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    block: str | None = Query(None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_reconciliation_overview_evidence(
            db,
            company_id=_resolve_company(principal, company_id),
            financial_account_id=financial_account_id,
            limit=limit,
            block=block,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Evidências da visão geral de conciliação carregadas.", "data": data}


@router.post("/statement-imports", response_model=ApiResponse)
def post_statement_import(
    payload: BankStatementImportCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _resolve_company(principal, payload.company_id)
    try:
        data = import_statement(db, payload, actor_id=principal.user_id, source=AuditSource.API)
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Extrato importado e linhas criadas para conciliação.", "data": data}


@router.post("/statement-imports/ofx-text", response_model=ApiResponse)
def post_ofx_statement_import(
    payload: OfxStatementImportText,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _resolve_company(principal, payload.company_id)
    try:
        data = import_ofx_statement_text(db, payload, actor_id=principal.user_id, source=AuditSource.API)
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "OFX importado e convertido em linhas de extrato para conciliação.", "data": data}


@router.get("/statement-imports", response_model=ApiResponse)
def get_statement_imports(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = list_statement_imports(
            db,
            company_id=_resolve_company(principal, company_id),
            financial_account_id=financial_account_id,
            status=status,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Importações de extrato carregadas.", "data": data}


@router.get("/statement-lines", response_model=ApiResponse)
def get_statement_lines(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    statement_import_id: str | None = Query(None),
    status: str | None = Query(None),
    statuses: str | None = Query(None),
    line_from: date | None = Query(None),
    line_to: date | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = list_statement_lines(
            db,
            company_id=_resolve_company(principal, company_id),
            financial_account_id=financial_account_id,
            statement_import_id=statement_import_id,
            status=status,
            statuses=[item.strip() for item in statuses.split(",") if item.strip()] if statuses else None,
            line_from=line_from,
            line_to=line_to,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Linhas de extrato carregadas.", "data": data}


@router.get("/statement-lines/{statement_line_id}/suggestions", response_model=ApiResponse)
def suggestions(
    statement_line_id: str,
    company_id: str = Query(...),
    day_window: int = Query(3, ge=0, le=30),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = suggest_matches(
            db,
            company_id=_resolve_company(principal, company_id),
            statement_line_id=statement_line_id,
            day_window=day_window,
            limit=limit,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Sugestões de match carregadas.", "data": data}


@router.post("/matches", response_model=ApiResponse)
def post_match(
    payload: ReconciliationMatchCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _resolve_company(principal, payload.company_id)
    try:
        data = confirm_match(db, payload, actor_id=principal.user_id, source=AuditSource.API)
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Match de conciliação confirmado.", "data": data}


@router.get("/matches", response_model=ApiResponse)
def get_matches(
    company_id: str = Query(...),
    financial_account_id: str | None = Query(None),
    status: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = list_reconciliation_matches(
            db,
            company_id=_resolve_company(principal, company_id),
            financial_account_id=financial_account_id,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Matches de conciliação carregados.", "data": data}


@router.post("/matches/{match_id}/reverse", response_model=ApiResponse)
def reverse(
    match_id: str,
    payload: ReverseReconciliationMatch,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = reverse_match(
            db,
            match_id,
            payload,
            company_id=principal.company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Match de conciliação estornado.", "data": data}


@router.post("/statement-lines/{statement_line_id}/ignore", response_model=ApiResponse)
def ignore_line(
    statement_line_id: str,
    payload: IgnoreStatementLine,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = ignore_statement_line(
            db,
            statement_line_id,
            payload,
            company_id=principal.company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
        )
    except ValueError as error:
        return _error_response(error)
    return {"success": True, "message": "Linha de extrato ignorada com justificativa.", "data": data}
