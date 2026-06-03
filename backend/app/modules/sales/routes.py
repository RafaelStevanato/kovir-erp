from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.sales.models import SaleStatus, SaleType
from app.modules.sales.schemas import SaleCreate, SaleReopenPayload, SaleStatusChange, SaleUpdate
from app.modules.sales.service import (
    cancel_sale,
    close_sale,
    confirm_sale,
    create_sale,
    emit_sale_invoice,
    get_sale,
    get_sale_audit_events,
    get_sale_invoice_readiness,
    get_sale_status_history,
    get_sales_summary,
    get_sales_diagnostics,
    list_operation_natures,
    list_payment_methods,
    list_catalog_item_fiscal_rules,
    list_sale_item_readiness,
    get_sales_rules,
    list_sales,
    pay_sale,
    reopen_sale,
    update_sale,
)
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Sales"])


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
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST

    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=_api_response(success=False, message=message, data=None),
    )


def _permission_error_response(error: PermissionError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=_api_response(success=False, message=str(error), data=None),
    )


@router.get("/sales", response_model=ApiResponse)
def list_sales_route(
    company_id: str | None = Query(default=None),
    participant_id: str | None = Query(default=None),
    sale_type: SaleType | None = Query(default=None),
    status_filter: SaleStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    try:
        resolved_company_id = company_id or principal.company_id
        sales = list_sales(
            db=db,
            company_id=resolved_company_id,
            participant_id=participant_id,
            sale_type=sale_type,
            status=status_filter,
            q=q,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

        return _api_response(
            success=True,
            message="Vendas carregadas com sucesso.",
            data=sales,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/summary", response_model=ApiResponse)
def get_sales_summary_route(
    company_id: str | None = Query(default=None),
    participant_id: str | None = Query(default=None),
    sale_type: SaleType | None = Query(default=None),
    status_filter: SaleStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    try:
        return _api_response(
            success=True,
            message="Resumo de pedidos carregado com sucesso.",
            data=get_sales_summary(
                db=db,
                company_id=company_id or principal.company_id,
                participant_id=participant_id,
                sale_type=sale_type,
                status=status_filter,
                q=q,
                date_from=date_from,
                date_to=date_to,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.post(
    "/sales",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sale_route(
    payload: SaleCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.create")),
):
    try:
        sale = create_sale(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Venda criada com sucesso.",
            data=sale,
        )
    except ValueError as error:
        return _error_response(error)

@router.get("/sales/payment-methods", response_model=ApiResponse)
def list_payment_methods_route(
    company_id: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Formas de pagamento carregadas com sucesso.",
            data=list_payment_methods(db=db, company_id=company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/operation-natures", response_model=ApiResponse)
def list_operation_natures_route(
    company_id: str = Query(...),
    sale_type: SaleType | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Naturezas de operação carregadas com sucesso.",
            data=list_operation_natures(db=db, company_id=company_id, sale_type=sale_type),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/item-readiness", response_model=ApiResponse)
def list_sale_item_readiness_route(
    company_id: str = Query(...),
    sale_type: SaleType = Query(...),
    operation_nature: str = Query(default="normal_sale"),
    operation_nature_id: str | None = Query(default=None),
    valid_on: str | None = Query(default=None),
    location_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    try:
        from datetime import date

        parsed_valid_on = date.fromisoformat(valid_on) if valid_on else None
        return _api_response(
            success=True,
            message="Prontidão operacional de itens carregada com sucesso.",
            data=list_sale_item_readiness(
                db=db,
                company_id=company_id,
                sale_type=sale_type,
                operation_nature=operation_nature,
                operation_nature_id=operation_nature_id,
                valid_on=parsed_valid_on,
                location_id=location_id,
                limit=limit,
                offset=offset,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/fiscal-rules", response_model=ApiResponse)
def list_catalog_item_fiscal_rules_route(
    company_id: str = Query(...),
    catalog_item_id: str | None = Query(default=None),
    operation_nature_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return _api_response(
            success=True,
            message="Regras fiscais por item carregadas com sucesso.",
            data=list_catalog_item_fiscal_rules(
                db=db,
                company_id=company_id,
                catalog_item_id=catalog_item_id,
                operation_nature_id=operation_nature_id,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/rules", response_model=ApiResponse)
def get_sales_rules_route():
    return _api_response(
        success=True,
        message="Regras de vendas carregadas com sucesso.",
        data=get_sales_rules(),
    )


@router.get("/sales/diagnostics", response_model=ApiResponse)
def get_sales_diagnostics_route(db: Session = Depends(get_db)):
    return _api_response(
        success=True,
        message="Diagnóstico do módulo sales carregado com sucesso.",
        data=get_sales_diagnostics(db),
    )


@router.get("/sales/{sale_id}", response_model=ApiResponse)
def get_sale_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    try:
        sale = get_sale(db, sale_id)

        return _api_response(
            success=True,
            message="Venda carregada com sucesso.",
            data=sale,
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/sales/{sale_id}", response_model=ApiResponse)
def update_sale_route(
    sale_id: str,
    payload: SaleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.create")),
):
    try:
        sale = update_sale(
            db=db,
            sale_id=sale_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Venda atualizada com sucesso.",
            data=sale,
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/sales/{sale_id}/confirm", response_model=ApiResponse)
def confirm_sale_route(
    sale_id: str,
    request: Request,
    payload: SaleStatusChange | None = None,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.close")),
):
    try:
        sale = confirm_sale(
            db=db,
            sale_id=sale_id,
            payload=payload or SaleStatusChange(reason="Pedido fechado."),
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Pedido fechado com sucesso.",
            data=sale,
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/sales/{sale_id}/cancel", response_model=ApiResponse)
def cancel_sale_route(
    sale_id: str,
    request: Request,
    payload: SaleStatusChange | None = None,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.cancel")),
):
    try:
        sale = cancel_sale(
            db=db,
            sale_id=sale_id,
            payload=payload or SaleStatusChange(),
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Venda cancelada com sucesso.",
            data=sale,
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/sales/{sale_id}/pay", response_model=ApiResponse)
def pay_sale_route(
    sale_id: str,
    request: Request,
    payload: SaleStatusChange | None = None,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.pay")),
):
    try:
        sale = pay_sale(
            db=db,
            sale_id=sale_id,
            payload=payload or SaleStatusChange(reason="Tentativa de recebimento direto pelo pedido."),
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Recebimento registrado com sucesso.", data=sale)
    except ValueError as error:
        return _error_response(error)


@router.post("/sales/{sale_id}/reopen", response_model=ApiResponse)
def reopen_sale_route(
    sale_id: str,
    request: Request,
    payload: SaleReopenPayload,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.unlock_closed")),
):
    try:
        sale = reopen_sale(
            db=db,
            sale_id=sale_id,
            master_password=payload.master_password,
            reason=payload.reason,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )
        return _api_response(success=True, message="Pedido reaberto com sucesso. Estoque estornado automaticamente.", data=sale)
    except PermissionError as error:
        return _permission_error_response(error)
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/{sale_id}/audit", response_model=ApiResponse)
def get_sale_audit_events_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    try:
        audit_events = get_sale_audit_events(db, sale_id)

        return _api_response(
            success=True,
            message="Eventos de auditoria da venda carregados com sucesso.",
            data=audit_events,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/{sale_id}/status-history", response_model=ApiResponse)
def get_sale_status_history_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    try:
        history = get_sale_status_history(db, sale_id)

        return _api_response(
            success=True,
            message="Histórico de status da venda carregado com sucesso.",
            data=history,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/{sale_id}/invoice-readiness", response_model=ApiResponse)
def get_sale_invoice_readiness_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    """Valida e retorna prontidão fiscal da venda para emissão de NF-e."""
    try:
        result = get_sale_invoice_readiness(db, sale_id)
        return _api_response(
            success=True,
            message="Prontidão fiscal avaliada com sucesso.",
            data=result,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/sales/{sale_id}/quote.pdf")
def get_sale_quote_pdf_route(
    sale_id: str,
    validity_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    from app.modules.sales.db_models import SaleDB as _SaleDB
    from app.modules.sales.quote_pdf import generate_quote_pdf

    sale = db.query(_SaleDB).filter(_SaleDB.id == sale_id).first()
    if not sale:
        return JSONResponse(status_code=404, content=_api_response(success=False, message="Venda não encontrada."))
    if sale.status == "cancelled":
        return JSONResponse(status_code=409, content=_api_response(success=False, message="Não é possível gerar orçamento para venda cancelada."))
    try:
        pdf_bytes = generate_quote_pdf(db, sale, validity_days=validity_days)
    except RuntimeError as exc:
        return JSONResponse(status_code=503, content=_api_response(success=False, message=str(exc)))
    except Exception as exc:
        return JSONResponse(status_code=500, content=_api_response(success=False, message=f"Erro ao gerar PDF: {exc}"))

    num = sale.sale_number_text or sale_id[:8]
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="orcamento_{num}.pdf"'},
    )


@router.get("/sales/{sale_id}/commercial-invoice.pdf")
def get_sale_commercial_invoice_pdf_route(
    sale_id: str,
    mode: str = Query(default="closed", pattern="^(closed|paid)$"),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    from typing import Literal
    from app.modules.sales.db_models import SaleDB as _SaleDB
    from app.modules.sales.commercial_invoice_pdf import generate_commercial_invoice_pdf

    sale = db.query(_SaleDB).filter(_SaleDB.id == sale_id).first()
    if not sale:
        return JSONResponse(status_code=404, content=_api_response(success=False, message="Venda não encontrada."))
    if mode == "paid" and sale.status != "paid":
        return JSONResponse(status_code=409, content=_api_response(success=False, message="Modo 'paid' exige venda com status PAID."))
    try:
        pdf_bytes = generate_commercial_invoice_pdf(db, sale, mode=mode)  # type: ignore[arg-type]
    except RuntimeError as exc:
        return JSONResponse(status_code=503, content=_api_response(success=False, message=str(exc)))
    except Exception as exc:
        return JSONResponse(status_code=500, content=_api_response(success=False, message=f"Erro ao gerar PDF: {exc}"))

    num = sale.paid_number_text if mode == "paid" else sale.sale_number_text
    num = num or sale_id[:8]
    prefix = "espelho_nfe" if mode == "paid" else "pedido_comercial"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{prefix}_{num}.pdf"'},
    )


@router.get("/sales/{sale_id}/fiscal-preview.pdf")
def get_sale_fiscal_preview_pdf_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("sales.view")),
):
    from app.modules.sales.db_models import SaleDB
    from app.modules.sales.fiscal_preview import generate_fiscal_preview_pdf

    sale = db.query(SaleDB).filter(SaleDB.id == sale_id).first()
    if not sale:
        return JSONResponse(
            status_code=404,
            content=_api_response(success=False, message="Venda não encontrada."),
        )

    try:
        pdf_bytes = generate_fiscal_preview_pdf(db, sale)
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content=_api_response(success=False, message=str(exc)),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=_api_response(success=False, message=f"Erro ao gerar PDF: {exc}"),
        )

    filename = f"previa_fiscal_{sale_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/sales/{sale_id}/invoice", response_model=ApiResponse)
def emit_sale_invoice_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.issue")),
):
    """Emite NF-e para pedido fechado via Focus NFe."""
    try:
        result = emit_sale_invoice(db, sale_id)
        return _api_response(
            success=True,
            message="NF-e enviada para a Focus NFe com sucesso.",
            data=result,
        )
    except ValueError as error:
        return _error_response(error)
