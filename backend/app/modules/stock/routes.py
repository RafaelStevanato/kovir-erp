from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.modules.stock.schemas import StockLocationCreate, StockLocationUpdate, StockMovementCreate, StockPurchaseEntryCreate, StockPurchaseXmlParsePayload
from app.modules.stock.service import (
    create_manual_stock_movement,
    create_purchase_stock_entry,
    create_stock_location,
    ensure_default_stock_location,
    get_item_availability,
    get_items_availability,
    get_stock_audit_events,
    get_stock_diagnostics,
    get_stock_rules,
    list_sale_stock_links_for_sale,
    list_stock_lots,
    list_stock_balances,
    parse_purchase_invoice_xml,
    list_stock_locations,
    list_purchase_stock_entries,
    list_stock_movements,
    update_location,
)
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Stock"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content=_api_response(success=False, message=message, data=None))


@router.get("/stock/diagnostics", response_model=ApiResponse)
def get_stock_diagnostics_route(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    return _api_response(success=True, message="Diagnóstico do módulo stock carregado com sucesso.", data=get_stock_diagnostics(db, company_id=company_id))


@router.get("/stock/rules", response_model=ApiResponse)
def get_stock_rules_route(
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    return _api_response(success=True, message="Regras do módulo stock carregadas com sucesso.", data=get_stock_rules())


@router.post("/stock/locations/default", response_model=ApiResponse)
def ensure_default_stock_location_route(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.move")),
):
    try:
        location = ensure_default_stock_location(db, company_id)
        db.commit()
        return _api_response(success=True, message="Local de estoque padrão disponível.", data=location)
    except ValueError as error:
        db.rollback()
        return _error_response(error)


@router.get("/stock/locations", response_model=ApiResponse)
def list_stock_locations_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Locais de estoque carregados com sucesso.",
            data=list_stock_locations(db, company_id=company_id, status=status_filter, limit=limit, offset=offset),
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/stock/locations", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_stock_location_route(
    payload: StockLocationCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.move")),
):
    try:
        location = create_stock_location(
            db,
            payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Local de estoque criado com sucesso.", data=location)
    except ValueError as error:
        return _error_response(error)


@router.patch("/stock/locations/{location_id}", response_model=ApiResponse)
def update_stock_location_route(
    location_id: str,
    payload: StockLocationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.move")),
):
    try:
        location = update_location(
            db,
            location_id,
            payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Local de estoque atualizado com sucesso.", data=location)
    except ValueError as error:
        return _error_response(error)


@router.post("/stock/movements", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_manual_stock_movement_route(
    payload: StockMovementCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.move")),
):
    try:
        movement = create_manual_stock_movement(
            db,
            payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Movimento de estoque criado com sucesso.", data=movement)
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/movements", response_model=ApiResponse)
def list_stock_movements_route(
    company_id: str = Query(...),
    item_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    movement_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Movimentos de estoque carregados com sucesso.",
            data=list_stock_movements(
                db,
                company_id=company_id,
                item_id=item_id,
                location_id=location_id,
                source_type=source_type,
                source_id=source_id,
                movement_type=movement_type,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/balances", response_model=ApiResponse)
def list_stock_balances_route(
    company_id: str = Query(...),
    item_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Saldos de estoque carregados com sucesso.",
            data=list_stock_balances(db, company_id=company_id, item_id=item_id, location_id=location_id, limit=limit, offset=offset),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/lots", response_model=ApiResponse)
def list_stock_lots_route(
    company_id: str = Query(...),
    item_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    only_positive: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Lotes de estoque carregados com sucesso.",
            data=list_stock_lots(
                db,
                company_id=company_id,
                item_id=item_id,
                location_id=location_id,
                only_positive=only_positive,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/items/availability", response_model=ApiResponse)
def get_items_availability_route(
    company_id: str = Query(...),
    item_ids: str = Query(..., description="IDs de itens separados por vírgula."),
    location_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        parsed_item_ids = [item_id.strip() for item_id in item_ids.split(",") if item_id.strip()]
        if len(parsed_item_ids) > 100:
            raise ValueError("Consulta de disponibilidade limitada a 100 itens por requisição.")
        return _api_response(
            success=True,
            message="Disponibilidade dos itens carregada com sucesso.",
            data=get_items_availability(db, company_id=company_id, item_ids=parsed_item_ids, location_id=location_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/items/{item_id}/availability", response_model=ApiResponse)
def get_item_availability_route(
    item_id: str,
    company_id: str = Query(...),
    location_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Disponibilidade do item carregada com sucesso.",
            data=get_item_availability(db, company_id=company_id, item_id=item_id, location_id=location_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/sale-links", response_model=ApiResponse)
def list_sale_stock_links_route(
    sale_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Vínculos venda/estoque carregados com sucesso.",
            data=list_sale_stock_links_for_sale(db, sale_id),
        )
    except ValueError as error:
        return _error_response(error)




@router.post("/stock/purchase-entries/parse-xml", response_model=ApiResponse)
def parse_purchase_invoice_xml_route(
    payload: StockPurchaseXmlParsePayload,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.purchase_entry")),
):
    try:
        return _api_response(
            success=True,
            message="XML de NF-e lido com sucesso. Confira os produtos antes de registrar a entrada.",
            data=parse_purchase_invoice_xml(db, payload),
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/stock/purchase-entries", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_stock_entry_route(
    payload: StockPurchaseEntryCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("stock.purchase_entry")),
):
    try:
        entry = create_purchase_stock_entry(
            db,
            payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Entrada de compra registrada e estoque atualizado com sucesso.", data=entry)
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/purchase-entries", response_model=ApiResponse)
def list_purchase_stock_entries_route(
    company_id: str = Query(...),
    supplier_participant_id: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    document_number: str | None = Query(default=None),
    include_items: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Entradas por nota/documento de compra carregadas com sucesso.",
            data=list_purchase_stock_entries(
                db,
                company_id=company_id,
                supplier_participant_id=supplier_participant_id,
                location_id=location_id,
                status=status_filter,
                document_number=document_number,
                include_items=include_items,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/stock/{entity_type}/{entity_id}/audit", response_model=ApiResponse)
def get_stock_audit_route(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.stock")),
):
    try:
        return _api_response(
            success=True,
            message="Eventos de auditoria do estoque carregados com sucesso.",
            data=get_stock_audit_events(db, entity_type=entity_type, entity_id=entity_id),
        )
    except ValueError as error:
        return _error_response(error)
