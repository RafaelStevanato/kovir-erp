from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.modules.stress_tests.schemas import StressGeneratePayload
from app.modules.stress_tests.service import (
    get_stress_rules,
    get_stress_summary,
    run_stress_generation,
)
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/stress-tests", tags=["stress-tests"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    if "não encontrada" in message.lower() or "não encontrado" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=status_code,
        content=_api_response(success=False, message=message, data=None),
    )


def _request_ids(request: Request) -> dict[str, str | None]:
    request_id = request.headers.get("x-request-id")
    return {
        "request_id": request_id,
        "correlation_id": request.headers.get("x-correlation-id") or request_id,
    }


def _assert_stress_permission(principal: SecurityPrincipal) -> None:
    require_permission(principal, "users.manage")


@router.get("/rules", response_model=ApiResponse)
def get_rules_route(principal: SecurityPrincipal = Depends(get_current_principal)):
    _assert_stress_permission(principal)
    return _api_response(
        success=True,
        message="Regras do módulo Stress e Testes carregadas.",
        data=get_stress_rules(),
    )


@router.get("/summary", response_model=ApiResponse)
def get_summary_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _assert_stress_permission(principal)
    return _api_response(
        success=True,
        message="Resumo de dados da empresa logada carregado.",
        data=get_stress_summary(db, principal=principal),
    )


@router.post("/generate", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def generate_route(
    payload: StressGeneratePayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _assert_stress_permission(principal)
        data = run_stress_generation(
            db,
            principal=principal,
            payload=payload,
            **_request_ids(request),
        )
        return _api_response(
            success=True,
            message="Massa de stress gerada com sucesso na empresa da sessão.",
            data=data,
        )
    except ValueError as error:
        return _error_response(error)

