from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal
from app.modules.technical_regression.service import (
    get_available_companies,
    get_database_health,
    get_financial_integrity,
    get_schema_contract,
    get_technical_regression_rules,
    run_technical_regression,
)
from app.shared.schemas import ApiResponse


router = APIRouter(prefix="/technical-regression", tags=["Technical Regression"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    lowered = message.lower()
    code = status.HTTP_400_BAD_REQUEST
    if "nÃ£o encontrada" in lowered or "nÃ£o encontrado" in lowered:
        code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=code,
        content=_api_response(success=False, message=message, data=None),
    )


def _require_technical_permission(principal: SecurityPrincipal, permission: str) -> None:
    if "users.manage" in principal.permission_codes or permission in principal.permission_codes:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permissao obrigatoria: {permission}.",
    )


@router.get("/rules", response_model=ApiResponse)
def get_technical_regression_rules_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.read")
    return _api_response(
        success=True,
        message="Regras de regressÃ£o tÃ©cnica carregadas com sucesso.",
        data=get_technical_regression_rules(),
    )


@router.get("/available-companies", response_model=ApiResponse)
def get_available_companies_route(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.read")
    try:
        raw = get_available_companies(db, limit=max(1, limit))
        scoped_items = [
            item
            for item in (raw.get("items") or [])
            if item.get("id") == principal.company_id
        ]
        return _api_response(
            success=True,
            message="Empresas disponÃ­veis para regressÃ£o tÃ©cnica carregadas com sucesso.",
            data={
                **raw,
                "items": scoped_items,
                "total_returned": len(scoped_items),
                "notes": ["Lista limitada ÃƒÂ  empresa da sessÃƒÂ£o autenticada."],
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/database-health", response_model=ApiResponse)
def get_database_health_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.read")
    try:
        return _api_response(
            success=True,
            message="SaÃºde tÃ©cnica do banco carregada com sucesso.",
            data=get_database_health(db),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/schema-contract", response_model=ApiResponse)
def get_schema_contract_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.read")
    try:
        return _api_response(
            success=True,
            message="Contrato relacional V6 carregado com sucesso.",
            data=get_schema_contract(db),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/financial-integrity", response_model=ApiResponse)
def get_financial_integrity_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.read")
    try:
        resolved_company_id = company_id or principal.company_id
        return _api_response(
            success=True,
            message="Integridade financeira crÃ­tica carregada com sucesso.",
            data=get_financial_integrity(db, company_id=resolved_company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/run", response_model=ApiResponse)
def run_technical_regression_route(
    company_id: str | None = Query(default=None),
    profile: str = Query(default="quick", pattern="^(quick|full)$"),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _require_technical_permission(principal, "technical.run")
    try:
        resolved_company_id = company_id or principal.company_id
        return _api_response(
            success=True,
            message="RegressÃ£o tÃ©cnica executada com sucesso.",
            data=run_technical_regression(
                db,
                company_id=resolved_company_id,
                profile=profile,
            ),
        )
    except ValueError as error:
        return _error_response(error)
