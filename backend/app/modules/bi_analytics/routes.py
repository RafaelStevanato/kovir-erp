"""BI Analytics — endpoints de KPIs, aging, concentração e exports Power BI."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal
from app.modules.bi_analytics.service import (
    dim_calendar_rows,
    dim_category_rows,
    dim_chart_account_rows,
    dim_cost_center_rows,
    dim_financial_account_rows,
    dim_participant_rows,
    dim_product_rows,
    fact_movements_rows,
    fact_purchases_rows,
    fact_sale_items_rows,
    fact_sales_rows,
    fact_settlements_rows,
    fact_titles_rows,
    get_aging,
    get_bi_rules,
    get_cash_flow_13w,
    get_cash_flow_by_category,
    get_concentration,
    get_dre_monthly,
    get_payment_method_mix,
    get_powerbi_manifest,
    get_working_capital_kpis,
)
from app.shared.schemas import ApiResponse


router = APIRouter(prefix="/bi", tags=["BI Analytics"])


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    code = status.HTTP_400_BAD_REQUEST
    if "não encontrada" in message.lower() or "não encontrado" in message.lower():
        code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=code,
        content=_api_response(success=False, message=message, data=None),
    )


def _resolve_company(principal: SecurityPrincipal, company_id: str | None) -> str:
    resolved = company_id or principal.company_id
    if resolved != principal.company_id:
        raise ValueError("Empresa informada não corresponde ao contexto ativo do usuário.")
    return resolved


def _csv_value(value: Any) -> str:
    """Converte Python → string CSV plug-and-play com Power BI/Excel.

    - None → '' (vazio)
    - bool → 'true'/'false' minúsculo (Power BI auto-detecta)
    - Decimal/float → ponto decimal, sem separador de milhar
    - date → ISO YYYY-MM-DD
    - datetime → ISO YYYY-MM-DD HH:MM:SS
    - resto → str(value)
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _to_csv_bytes(rows: list[dict[str, Any]], columns: list[str] | None = None) -> bytes:
    """Serializa lista de dicts para CSV UTF-8 BOM, separador ';', RFC 4180.

    Cabeçalho na 1ª linha. Power BI Desktop, Excel e Pandas leem direto.
    """
    buffer = io.StringIO()
    if not rows:
        # Mesmo vazio, mantém cabeçalho se columns foi fornecido
        if columns:
            writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
            writer.writerow(columns)
        return ("﻿" + buffer.getvalue()).encode("utf-8")

    fieldnames = columns or list(rows[0].keys())
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(fieldnames)
    for row in rows:
        writer.writerow([_csv_value(row.get(col)) for col in fieldnames])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _csv_response(rows: list[dict[str, Any]], filename: str, columns: list[str] | None = None) -> Response:
    body = _to_csv_bytes(rows, columns=columns)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.csv"',
            "Cache-Control": "no-store",
        },
    )


def _flatten_for_csv(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aplana valores aninhados (dict/list) em JSON string para o CSV ficar tabular."""
    flat: list[dict[str, Any]] = []
    for row in payload:
        new_row: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                import json

                new_row[key] = json.dumps(value, ensure_ascii=False, default=str)
            else:
                new_row[key] = value
        flat.append(new_row)
    return flat


# -----------------------------------------------------------------------------
# Rules / manifest
# -----------------------------------------------------------------------------


@router.get("/rules", response_model=ApiResponse)
def get_rules_route():
    return _api_response(success=True, message="Regras de BI Analytics carregadas.", data=get_bi_rules())


@router.get("/powerbi-manifest", response_model=ApiResponse)
def get_powerbi_manifest_route():
    return _api_response(
        success=True,
        message="Manifest Power BI carregado.",
        data=get_powerbi_manifest(api_base_url="/api"),
    )


# -----------------------------------------------------------------------------
# KPIs
# -----------------------------------------------------------------------------


@router.get("/working-capital-kpis", response_model=ApiResponse)
def working_capital_kpis_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="KPIs de capital de giro carregados.",
            data=get_working_capital_kpis(
                db,
                company_id=_resolve_company(principal, company_id),
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/aging-receivables", response_model=ApiResponse)
def aging_receivables_route(
    company_id: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Aging de recebíveis carregado.",
            data=get_aging(
                db,
                company_id=_resolve_company(principal, company_id),
                direction="receivable",
                as_of=as_of,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/aging-payables", response_model=ApiResponse)
def aging_payables_route(
    company_id: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Aging de pagáveis carregado.",
            data=get_aging(
                db,
                company_id=_resolve_company(principal, company_id),
                direction="payable",
                as_of=as_of,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/customer-concentration", response_model=ApiResponse)
def customer_concentration_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    top: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Concentração de clientes carregada.",
            data=get_concentration(
                db,
                company_id=_resolve_company(principal, company_id),
                kind="customer",
                start_date=start_date,
                end_date=end_date,
                top=top,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/supplier-concentration", response_model=ApiResponse)
def supplier_concentration_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    top: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Concentração de fornecedores carregada.",
            data=get_concentration(
                db,
                company_id=_resolve_company(principal, company_id),
                kind="supplier",
                start_date=start_date,
                end_date=end_date,
                top=top,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/dre-monthly", response_model=ApiResponse)
def dre_monthly_route(
    company_id: str | None = Query(default=None),
    months: int = Query(default=12, ge=1, le=36),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="DRE mensal carregada.",
            data=get_dre_monthly(
                db,
                company_id=_resolve_company(principal, company_id),
                months=months,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/cash-flow-13w", response_model=ApiResponse)
def cash_flow_13w_route(
    company_id: str | None = Query(default=None),
    weeks: int = Query(default=13, ge=1, le=26),
    start_date: date | None = Query(default=None),
    financial_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Forecast de fluxo de caixa 13 semanas carregado.",
            data=get_cash_flow_13w(
                db,
                company_id=_resolve_company(principal, company_id),
                weeks=weeks,
                start_date=start_date,
                financial_account_id=financial_account_id,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/cash-flow-by-category", response_model=ApiResponse)
def cash_flow_by_category_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    financial_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Fluxo de caixa por categoria carregado.",
            data=get_cash_flow_by_category(
                db,
                company_id=_resolve_company(principal, company_id),
                start_date=start_date,
                end_date=end_date,
                financial_account_id=financial_account_id,
            ),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/payment-method-mix", response_model=ApiResponse)
def payment_method_mix_route(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(
            success=True,
            message="Mix de meios de pagamento carregado.",
            data=get_payment_method_mix(
                db,
                company_id=_resolve_company(principal, company_id),
                start_date=start_date,
                end_date=end_date,
            ),
        )
    except ValueError as error:
        return _error_response(error)


# -----------------------------------------------------------------------------
# Power BI exports — facts + dims
#
# Cada endpoint suporta `?format=csv` retornando text/csv UTF-8 BOM (default JSON).
# -----------------------------------------------------------------------------


def _export_endpoint(
    fetcher: Callable[[Session, str], list[dict[str, Any]]],
    name: str,
):
    """Fábrica de export (fact_* / dim_*) que retorna JSON ou CSV."""

    def handler(
        company_id: str | None = Query(default=None),
        format: str = Query(default="json", pattern="^(json|csv)$"),
        db: Session = Depends(get_db),
        principal: SecurityPrincipal = Depends(get_current_principal),
    ):
        try:
            resolved = _resolve_company(principal, company_id)
            rows = fetcher(db, resolved)
            if format == "csv":
                return _csv_response(rows, filename=f"{name}_{resolved}")
            return _api_response(
                success=True,
                message=f"{name} carregado ({len(rows)} linhas).",
                data={"company_id": resolved, "row_count": len(rows), "rows": rows},
            )
        except ValueError as error:
            return _error_response(error)

    handler.__name__ = f"{name}_route"
    return handler


router.get("/exports/fact-titles",       response_model=None)(_export_endpoint(fact_titles_rows,       "fact_titles"))
router.get("/exports/fact-settlements",  response_model=None)(_export_endpoint(fact_settlements_rows,  "fact_settlements"))
router.get("/exports/fact-movements",    response_model=None)(_export_endpoint(fact_movements_rows,    "fact_movements"))
router.get("/exports/fact-sales",        response_model=None)(_export_endpoint(fact_sales_rows,        "fact_sales"))
router.get("/exports/fact-sale-items",   response_model=None)(_export_endpoint(fact_sale_items_rows,   "fact_sale_items"))
router.get("/exports/fact-purchases",    response_model=None)(_export_endpoint(fact_purchases_rows,    "fact_purchases"))
router.get("/exports/dim-participant",       response_model=None)(_export_endpoint(dim_participant_rows,       "dim_participant"))
router.get("/exports/dim-financial-account", response_model=None)(_export_endpoint(dim_financial_account_rows, "dim_financial_account"))
router.get("/exports/dim-category",          response_model=None)(_export_endpoint(dim_category_rows,          "dim_category"))
router.get("/exports/dim-cost-center",       response_model=None)(_export_endpoint(dim_cost_center_rows,       "dim_cost_center"))
router.get("/exports/dim-chart-account",     response_model=None)(_export_endpoint(dim_chart_account_rows,     "dim_chart_account"))
router.get("/exports/dim-product",           response_model=None)(_export_endpoint(dim_product_rows,           "dim_product"))


# Calendar é especial — não depende de company_id, depende de período
@router.get("/exports/dim-calendar", response_model=None)
def dim_calendar_export(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    principal: SecurityPrincipal = Depends(get_current_principal),  # noqa: ARG001 (auth)
):
    try:
        rows = dim_calendar_rows(start_date, end_date)
        if format == "csv":
            return _csv_response(rows, filename=f"dim_calendar_{start_date}_{end_date}")
        return _api_response(
            success=True,
            message=f"dim_calendar carregado ({len(rows)} linhas).",
            data={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "row_count": len(rows), "rows": rows},
        )
    except ValueError as error:
        return _error_response(error)


# -----------------------------------------------------------------------------
# CSV passthrough para os principais KPIs (download direto)
# -----------------------------------------------------------------------------


@router.get("/exports/aging-receivables.csv", response_model=None)
def export_aging_receivables_csv(
    company_id: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_aging(db, company_id=_resolve_company(principal, company_id), direction="receivable", as_of=as_of)
        return _csv_response(_flatten_for_csv(data["items"]), filename=f"aging_receivables_{data['company_id']}_{data['as_of']}")
    except ValueError as error:
        return _error_response(error)


@router.get("/exports/aging-payables.csv", response_model=None)
def export_aging_payables_csv(
    company_id: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_aging(db, company_id=_resolve_company(principal, company_id), direction="payable", as_of=as_of)
        return _csv_response(_flatten_for_csv(data["items"]), filename=f"aging_payables_{data['company_id']}_{data['as_of']}")
    except ValueError as error:
        return _error_response(error)


@router.get("/exports/dre-monthly.csv", response_model=None)
def export_dre_monthly_csv(
    company_id: str | None = Query(default=None),
    months: int = Query(default=12, ge=1, le=36),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_dre_monthly(db, company_id=_resolve_company(principal, company_id), months=months)
        return _csv_response(data["series"], filename=f"dre_monthly_{data['company_id']}")
    except ValueError as error:
        return _error_response(error)


@router.get("/exports/cash-flow-13w.csv", response_model=None)
def export_cash_flow_13w_csv(
    company_id: str | None = Query(default=None),
    weeks: int = Query(default=13, ge=1, le=26),
    start_date: date | None = Query(default=None),
    financial_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_cash_flow_13w(db, company_id=_resolve_company(principal, company_id), weeks=weeks, start_date=start_date, financial_account_id=financial_account_id)
        return _csv_response(data["weekly"], filename=f"cash_flow_13w_{data['company_id']}_{data['starting_week']}")
    except ValueError as error:
        return _error_response(error)


@router.get("/exports/cash-flow-by-category.csv", response_model=None)
def export_cash_flow_by_category_csv(
    company_id: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    financial_account_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = get_cash_flow_by_category(
            db,
            company_id=_resolve_company(principal, company_id),
            start_date=start_date,
            end_date=end_date,
            financial_account_id=financial_account_id,
        )
        rows = [
            {
                "cash_flow_group": group["cash_flow_group"],
                "group_label": group["label"],
                "category_id": category["category_id"],
                "category_name": category["category_name"],
                "inflow_amount": category["inflow_amount"],
                "outflow_amount": category["outflow_amount"],
                "net_amount": category["net_amount"],
                "settlement_count": category["settlement_count"],
            }
            for group in data["groups"]
            for category in group["categories"]
        ]
        return _csv_response(rows, filename=f"cash_flow_by_category_{data['company_id']}_{data['period']['start_date']}_{data['period']['end_date']}")
    except ValueError as error:
        return _error_response(error)
