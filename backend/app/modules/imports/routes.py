from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.imports.schemas import ImportRowsRequest, ImportTarget
from app.modules.imports.service import (
    commit_import_rows,
    get_import_template,
    list_import_templates,
    preview_import_rows,
)
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.shared.schemas import ApiResponse


router = APIRouter(prefix="/imports", tags=["Imports"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": data,
    }


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST

    if "nao encontrada" in message.lower() or "nao encontrado" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=_api_response(success=False, message=message, data=None),
    )


@router.get("/templates", response_model=ApiResponse)
def list_templates_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "view.imports")
    return _api_response(
        success=True,
        message="Modelos de importacao carregados com sucesso.",
        data=[item.model_dump(mode="json") for item in list_import_templates()],
    )


@router.get("/templates/{target}", response_model=ApiResponse)
def get_template_route(
    target: ImportTarget,
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "view.imports")
    return _api_response(
        success=True,
        message="Modelo de importacao carregado com sucesso.",
        data=get_import_template(target).model_dump(mode="json"),
    )


@router.post("/{target}/preview", response_model=ApiResponse)
def preview_import_route(
    target: ImportTarget,
    payload: ImportRowsRequest,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "imports.run")
    try:
        data = preview_import_rows(
            db,
            target=target,
            payload=payload,
            principal_company_id=principal.company_id,
        )
        return _api_response(
            success=True,
            message="Previa de importacao gerada com sucesso.",
            data=data.model_dump(mode="json"),
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/{target}/commit", response_model=ApiResponse)
def commit_import_route(
    target: ImportTarget,
    payload: ImportRowsRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    require_permission(principal, "imports.run")
    try:
        data = commit_import_rows(
            db,
            target=target,
            payload=payload,
            principal_company_id=principal.company_id,
            actor_id=principal.user_id,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(
            success=data.failed_rows == 0,
            message="Importacao concluida." if data.failed_rows == 0 else "Importacao concluida com falhas.",
            data=data.model_dump(mode="json"),
        )
    except ValueError as error:
        return _error_response(error)
