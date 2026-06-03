from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.catalog.models import CatalogItemStatus, CatalogItemType
from app.modules.catalog.schemas import CatalogItemCreate, CatalogItemUpdate
from app.modules.catalog.service import (
    create_catalog_item,
    get_catalog_diagnostics,
    get_catalog_item,
    get_catalog_item_audit_events,
    get_catalog_rules,
    get_catalog_summary,
    count_catalog_items,
    list_catalog_items,
    update_catalog_item,
)
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Catalog"])


def _api_response(
    *,
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
    return request.headers.get("x-correlation-id") or request.headers.get(
        "x-request-id"
    )


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)

    status_code = status.HTTP_400_BAD_REQUEST

    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=_api_response(
            success=False,
            message=message,
            data=None,
        ),
    )


def _resolve_company_id(company_id: str | None, principal: SecurityPrincipal) -> str:
    resolved = company_id or principal.company_id
    if resolved != principal.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Acesso bloqueado. A empresa informada não corresponde "
                "à empresa ativa da sessão."
            ),
        )
    return resolved


@router.get("/catalog/items", response_model=ApiResponse)
def list_catalog_items_route(
    company_id: str | None = Query(default=None),
    item_type: CatalogItemType | None = Query(default=None),
    status_filter: CatalogItemStatus | None = Query(default=None, alias="status"),
    origin: str | None = Query(default=None, pattern="^(manual|imported|integration|fiscal_document|unknown)$"),
    unit: str | None = Query(default=None, max_length=20),
    category: str | None = Query(default=None, max_length=100),
    search: str | None = Query(default=None, max_length=120),
    search_scope: str = Query(default="all", pattern="^(all|name|sku|barcode|id)$"),
    stock_filter: str | None = Query(default=None, pattern="^(tracked|not_tracked)$"),
    fiscal_filter: str | None = Query(default=None, pattern="^(with_ncm|with_nbs|without_classification)$"),
    min_sale_price: str | None = Query(default=None, max_length=30),
    max_sale_price: str | None = Query(default=None, max_length=30),
    min_cost_price: str | None = Query(default=None, max_length=30),
    max_cost_price: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    try:
        resolved_company_id = _resolve_company_id(company_id, principal)
        items = list_catalog_items(
            db=db,
            company_id=resolved_company_id,
            item_type=item_type,
            status=status_filter,
            origin=origin,
            unit=unit,
            category=category,
            search=search,
            search_scope=search_scope,
            stock_filter=stock_filter,
            fiscal_filter=fiscal_filter,
            min_sale_price=min_sale_price,
            max_sale_price=max_sale_price,
            min_cost_price=min_cost_price,
            max_cost_price=max_cost_price,
            limit=limit,
            offset=offset,
        )
        total = count_catalog_items(
            db=db,
            company_id=resolved_company_id,
            item_type=item_type,
            status=status_filter,
            origin=origin,
            unit=unit,
            category=category,
            search=search,
            search_scope=search_scope,
            stock_filter=stock_filter,
            fiscal_filter=fiscal_filter,
            min_sale_price=min_sale_price,
            max_sale_price=max_sale_price,
            min_cost_price=min_cost_price,
            max_cost_price=max_cost_price,
        )

        return _api_response(
            success=True,
            message="Itens do catálogo carregados com sucesso.",
            data={"items": items, "total": total, "limit": limit, "offset": offset},
        )
    except ValueError as error:
        return _error_response(error)


@router.post(
    "/catalog/items",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_item_route(
    payload: CatalogItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("catalog.write")),
):
    try:
        if payload.company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A empresa do item deve ser a empresa ativa da sessão.",
            )
        item = create_catalog_item(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Item do catálogo criado com sucesso.",
            data=item,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/catalog/items/{item_id}", response_model=ApiResponse)
def get_catalog_item_route(
    item_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    try:
        item = get_catalog_item(db, item_id, expected_company_id=principal.company_id)

        return _api_response(
            success=True,
            message="Item do catálogo carregado com sucesso.",
            data=item,
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/catalog/items/{item_id}", response_model=ApiResponse)
def update_catalog_item_route(
    item_id: str,
    payload: CatalogItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("catalog.write")),
):
    try:
        item = update_catalog_item(
            db=db,
            item_id=item_id,
            payload=payload,
            expected_company_id=principal.company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Item do catálogo atualizado com sucesso.",
            data=item,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/catalog/items/{item_id}/audit", response_model=ApiResponse)
def get_catalog_item_audit_events_route(
    item_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    try:
        audit_events = get_catalog_item_audit_events(
            db,
            item_id,
            expected_company_id=principal.company_id,
        )

        return _api_response(
            success=True,
            message="Eventos de auditoria do item carregados com sucesso.",
            data=audit_events,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/catalog/rules", response_model=ApiResponse)
def get_catalog_rules_route(
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    _ = principal
    return _api_response(
        success=True,
        message="Regras do catálogo do Kovir carregadas com sucesso.",
        data=get_catalog_rules(),
    )


@router.get("/catalog/summary", response_model=ApiResponse)
def get_catalog_summary_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    resolved_company_id = _resolve_company_id(company_id, principal)
    return _api_response(
        success=True,
        message="Resumo do catálogo carregado com sucesso.",
        data=get_catalog_summary(db, company_id=resolved_company_id),
    )


@router.get("/catalog/diagnostics", response_model=ApiResponse)
def get_catalog_diagnostics_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.catalog")),
):
    return _api_response(
        success=True,
        message="Diagnóstico do módulo catalog carregado com sucesso.",
        data=get_catalog_diagnostics(db, company_id=principal.company_id),
    )
