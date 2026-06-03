"""BI Analytics service — leituras dimensionais e KPIs gerenciais.

Princípios:
    - Não cria fato financeiro: apenas agrega o que já existe (titles, settlements,
      movements, sales, purchases, balances).
    - Não corrige dado ruim: aponta a origem da divergência via `data_quality`.
    - Valores monetários sempre Decimal arredondado a 2 casas, serializado como string.
    - Datas em ISO-8601, decimal point — pronto para Power BI / Excel.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.shared.datetime import today_in_brazil
from app.shared.ids import assert_valid_id


MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.0001")
PERCENT_QUANT = Decimal("0.01")
ZERO = Decimal("0")
DEFAULT_AGING_BUCKETS = (
    ("bucket_0_30", 0, 30),
    ("bucket_31_60", 31, 60),
    ("bucket_61_90", 61, 90),
    ("bucket_91_180", 91, 180),
    ("bucket_180_plus", 181, None),
)


def _validate_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _default_period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = date.today()
    start = start_date or date(today.year, today.month, 1)
    end = end_date or date(today.year, today.month, monthrange(today.year, today.month)[1])
    if end < start:
        raise ValueError("Data final não pode ser menor que data inicial.")
    return start, end


def _money(value: Any) -> str:
    decimal_value = _to_decimal(value)
    return str(decimal_value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _percent(value: Any) -> str:
    decimal_value = _to_decimal(value)
    return str(decimal_value.quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP))


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator == ZERO:
        return None
    return (numerator / denominator)


def _rows(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        result = db.execute(text(sql), params)
        return [dict(row._mapping) for row in result.fetchall()]
    except SQLAlchemyError as exc:
        raise ValueError(
            "Falha ao consultar BI Analytics. "
            "Verifique se o PostgreSQL está online e se as migrations Alembic estão em head."
        ) from exc


def _one(db: Session, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(db, sql, params)
    return rows[0] if rows else None


def _get_company_or_raise(db: Session, company_id: str) -> dict[str, Any]:
    _validate_company_id(company_id)
    company = _one(
        db,
        """
        SELECT id, legal_name, trade_name, cnpj, status, tax_regime
        FROM companies
        WHERE id = :company_id AND deleted_at IS NULL
        """,
        {"company_id": company_id},
    )
    if not company:
        raise ValueError("Empresa não encontrada.")
    company["display_name"] = company.get("trade_name") or company.get("legal_name") or company.get("id")
    return company


def _assert_financial_account(db: Session, *, company_id: str, financial_account_id: str | None) -> None:
    if not financial_account_id:
        return
    account = _one(
        db,
        """
        SELECT id
        FROM financial_accounts
        WHERE id = :financial_account_id
          AND company_id = :company_id
          AND deleted_at IS NULL
        """,
        {"company_id": company_id, "financial_account_id": financial_account_id},
    )
    if not account:
        raise ValueError("Conta financeira não encontrada para a empresa.")


# -----------------------------------------------------------------------------
# 1) Working capital KPIs (DSO, DPO, CCC, current ratio, runway)
# -----------------------------------------------------------------------------


def get_working_capital_kpis(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """KPIs executivos de capital de giro e saúde financeira.

    Métricas:
        - revenue / purchases / gross_margin (proxy)
        - DSO (Days Sales Outstanding) = AR aberto / receita média diária
        - DPO (Days Payable Outstanding) = AP aberto / compras médias diárias
        - CCC (Cash Conversion Cycle) = DSO - DPO  (DIO omitido por enquanto)
        - working_capital = ativo circulante - passivo circulante (proxy: caixa+AR - AP)
        - current_ratio = ativo circulante / passivo circulante
        - cash_runway_days = saldo / burn rate diário (saídas líquidas)
    """
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    period_days = max(1, (end - start).days + 1)

    sales = _one(
        db,
        """
        SELECT COALESCE(SUM(total_amount), 0) AS revenue,
               COUNT(*) AS sales_count
        FROM sales
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {"revenue": 0, "sales_count": 0}

    purchases = _one(
        db,
        """
        SELECT COALESCE(SUM(total_amount), 0) AS purchases,
               COUNT(*) AS purchases_count
        FROM purchases
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {"purchases": 0, "purchases_count": 0}

    titles = _one(
        db,
        """
        SELECT
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN ('open','partially_paid','overdue','partially_received') THEN open_amount ELSE 0 END), 0) AS receivable_open,
            COALESCE(SUM(CASE WHEN direction = 'payable'    AND status IN ('open','partially_paid','overdue','partially_received') THEN open_amount ELSE 0 END), 0) AS payable_open,
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN ('open','partially_paid','overdue','partially_received') AND due_date < CURRENT_DATE THEN open_amount ELSE 0 END), 0) AS receivable_overdue,
            COALESCE(SUM(CASE WHEN direction = 'payable'    AND status IN ('open','partially_paid','overdue','partially_received') AND due_date < CURRENT_DATE THEN open_amount ELSE 0 END), 0) AS payable_overdue
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
        """,
        {"company_id": company_id},
    ) or {}

    cash_balance = _one(
        db,
        """
        SELECT COALESCE(SUM(current_balance_amount), 0) AS total_balance
        FROM financial_account_balances
        WHERE company_id = :company_id
        """,
        {"company_id": company_id},
    ) or {"total_balance": 0}

    realized_flow = _one(
        db,
        """
        SELECT
            COALESCE(SUM(CASE WHEN direction = 'inflow'  THEN amount ELSE 0 END), 0) AS inflow,
            COALESCE(SUM(CASE WHEN direction = 'outflow' THEN amount ELSE 0 END), 0) AS outflow
        FROM financial_movements
        WHERE company_id = :company_id
          AND status = 'posted'
          AND reversal_of_movement_id IS NULL
          AND movement_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {"inflow": 0, "outflow": 0}

    revenue = _to_decimal(sales.get("revenue"))
    purchases_amt = _to_decimal(purchases.get("purchases"))
    gross_profit = revenue - purchases_amt
    gross_margin_pct = _safe_div(gross_profit * Decimal("100"), revenue)

    receivable_open = _to_decimal(titles.get("receivable_open"))
    payable_open = _to_decimal(titles.get("payable_open"))
    cash_total = _to_decimal(cash_balance.get("total_balance"))

    daily_revenue = _safe_div(revenue, Decimal(period_days))
    daily_purchases = _safe_div(purchases_amt, Decimal(period_days))

    dso_days = _safe_div(receivable_open, daily_revenue) if daily_revenue else None
    dpo_days = _safe_div(payable_open, daily_purchases) if daily_purchases else None
    ccc_days = (dso_days - dpo_days) if (dso_days is not None and dpo_days is not None) else None

    current_assets = cash_total + receivable_open
    current_liabilities = payable_open
    working_capital = current_assets - current_liabilities
    current_ratio = _safe_div(current_assets, current_liabilities)

    realized_inflow = _to_decimal(realized_flow.get("inflow"))
    realized_outflow = _to_decimal(realized_flow.get("outflow"))
    net_burn = realized_outflow - realized_inflow
    daily_burn = _safe_div(net_burn, Decimal(period_days))
    runway_days: Decimal | None
    if daily_burn is not None and daily_burn > ZERO:
        runway_days = cash_total / daily_burn
    elif daily_burn is not None and daily_burn <= ZERO:
        runway_days = None  # Geração positiva de caixa: runway "infinito"
    else:
        runway_days = None

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat(), "days": period_days},
        "kpis": {
            "revenue_amount": _money(revenue),
            "sales_count": _int(sales.get("sales_count")),
            "purchases_amount": _money(purchases_amt),
            "purchases_count": _int(purchases.get("purchases_count")),
            "gross_profit_amount": _money(gross_profit),
            "gross_margin_percent": _percent(gross_margin_pct) if gross_margin_pct is not None else None,
            "accounts_receivable_open": _money(receivable_open),
            "accounts_receivable_overdue": _money(titles.get("receivable_overdue")),
            "accounts_payable_open": _money(payable_open),
            "accounts_payable_overdue": _money(titles.get("payable_overdue")),
            "cash_balance_total": _money(cash_total),
            "working_capital": _money(working_capital),
            "current_ratio": _percent(current_ratio) if current_ratio is not None else None,
            "dso_days": _percent(dso_days) if dso_days is not None else None,
            "dpo_days": _percent(dpo_days) if dpo_days is not None else None,
            "ccc_days": _percent(ccc_days) if ccc_days is not None else None,
            "realized_inflow": _money(realized_inflow),
            "realized_outflow": _money(realized_outflow),
            "realized_net": _money(realized_inflow - realized_outflow),
            "net_burn_rate_daily": _money(daily_burn) if daily_burn is not None else None,
            "cash_runway_days": _percent(runway_days) if runway_days is not None else None,
        },
        "interpretation": {
            "dso_days": "Tempo médio de recebimento. Menor é melhor. Calculado como AR aberto ÷ receita diária do período.",
            "dpo_days": "Tempo médio de pagamento a fornecedores. Maior pode ser melhor para caixa. Calculado como AP aberto ÷ compras diárias.",
            "ccc_days": "Cash Conversion Cycle = DSO − DPO. Quanto menor (ou negativo), melhor.",
            "current_ratio": "Liquidez corrente proxy: (caixa + AR) ÷ AP. Acima de 1.00 indica solvência de curto prazo.",
            "gross_margin_percent": "Margem bruta proxy. Compras tratadas como custo direto (proxy MVP — refine com COGS via stock).",
            "cash_runway_days": "Dias de caixa restantes ao burn rate atual. Vazio = geração positiva ou base insuficiente.",
        },
        "data_quality": {
            "uses_purchases_as_cogs_proxy": True,
            "note": "Margem bruta usa SUM(purchases) como proxy de COGS. Para acuracidade contábil, integre custo unitário do estoque (stock_lots).",
        },
    }


# -----------------------------------------------------------------------------
# 2) Aging buckets (receivable / payable)
# -----------------------------------------------------------------------------


def get_aging(
    db: Session,
    company_id: str,
    direction: str = "receivable",
    as_of: date | None = None,
) -> dict[str, Any]:
    if direction not in {"receivable", "payable"}:
        raise ValueError("direction deve ser receivable ou payable.")
    company = _get_company_or_raise(db, company_id)
    reference = as_of or date.today()

    rows = _rows(
        db,
        """
        SELECT
            ft.id,
            COALESCE(NULLIF(ft.title_name,''), ft.document_reference, ft.id) AS title_reference,
            ft.due_date,
            ft.open_amount,
            ft.status,
            p.id AS participant_id,
            COALESCE(p.name, '(sem participante)') AS participant_name,
            COALESCE(fc.name, '(sem categoria)') AS category_name,
            (:reference::date - ft.due_date) AS days_overdue
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        LEFT JOIN financial_categories fc ON fc.id = ft.financial_category_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND ft.direction = :direction
          AND ft.status IN ('open','partially_paid','overdue','partially_received')
        ORDER BY ft.due_date ASC
        """,
        {"company_id": company_id, "direction": direction, "reference": reference},
    )

    buckets = {
        "future": {"label": "A vencer (não vencido)", "count": 0, "amount": ZERO, "min_days": None, "max_days": -1},
        "bucket_0_30": {"label": "Vencido 0–30 dias", "count": 0, "amount": ZERO, "min_days": 0, "max_days": 30},
        "bucket_31_60": {"label": "Vencido 31–60 dias", "count": 0, "amount": ZERO, "min_days": 31, "max_days": 60},
        "bucket_61_90": {"label": "Vencido 61–90 dias", "count": 0, "amount": ZERO, "min_days": 61, "max_days": 90},
        "bucket_91_180": {"label": "Vencido 91–180 dias", "count": 0, "amount": ZERO, "min_days": 91, "max_days": 180},
        "bucket_180_plus": {"label": "Vencido 180+ dias", "count": 0, "amount": ZERO, "min_days": 181, "max_days": None},
    }

    total_count = 0
    total_amount = ZERO
    overdue_amount = ZERO

    for row in rows:
        amount = _to_decimal(row.get("open_amount"))
        days_overdue = int(row.get("days_overdue") or 0)
        total_count += 1
        total_amount += amount

        if days_overdue < 0:
            key = "future"
        elif days_overdue <= 30:
            key = "bucket_0_30"
        elif days_overdue <= 60:
            key = "bucket_31_60"
        elif days_overdue <= 90:
            key = "bucket_61_90"
        elif days_overdue <= 180:
            key = "bucket_91_180"
        else:
            key = "bucket_180_plus"

        buckets[key]["count"] += 1
        buckets[key]["amount"] += amount
        if days_overdue >= 0:
            overdue_amount += amount

    bucket_list = []
    for code, data in buckets.items():
        share_pct = _safe_div(data["amount"] * Decimal("100"), total_amount)
        bucket_list.append({
            "code": code,
            "label": data["label"],
            "min_days_overdue": data["min_days"],
            "max_days_overdue": data["max_days"],
            "count": data["count"],
            "amount": _money(data["amount"]),
            "share_percent": _percent(share_pct) if share_pct is not None else "0.00",
        })

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "direction": direction,
        "as_of": reference.isoformat(),
        "total_count": total_count,
        "total_amount": _money(total_amount),
        "overdue_amount": _money(overdue_amount),
        "overdue_share_percent": _percent(_safe_div(overdue_amount * Decimal("100"), total_amount) or ZERO),
        "buckets": bucket_list,
        "items": [
            {
                "id": row["id"],
                "title_reference": row["title_reference"],
                "due_date": row["due_date"].isoformat() if row.get("due_date") else None,
                "days_overdue": int(row.get("days_overdue") or 0),
                "open_amount": _money(row.get("open_amount")),
                "status": row.get("status"),
                "participant_id": row.get("participant_id"),
                "participant_name": row.get("participant_name"),
                "category_name": row.get("category_name"),
            }
            for row in rows
        ],
    }


# -----------------------------------------------------------------------------
# 3) Customer / supplier concentration (Pareto + ABC)
# -----------------------------------------------------------------------------


def get_concentration(
    db: Session,
    company_id: str,
    kind: str = "customer",
    start_date: date | None = None,
    end_date: date | None = None,
    top: int = 20,
) -> dict[str, Any]:
    if kind not in {"customer", "supplier"}:
        raise ValueError("kind deve ser customer ou supplier.")
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    top = max(1, min(top, 100))

    if kind == "customer":
        sql = """
            SELECT
                p.id AS participant_id,
                COALESCE(p.name, '(sem participante)') AS participant_name,
                p.participant_type,
                COUNT(DISTINCT s.id) AS transactions,
                COALESCE(SUM(s.total_amount), 0) AS amount
            FROM sales s
            LEFT JOIN participants p ON p.id = s.participant_id
            WHERE s.company_id = :company_id
              AND s.cancelled_at IS NULL
              AND s.operation_date::date BETWEEN :start_date AND :end_date
            GROUP BY p.id, p.name, p.participant_type
            ORDER BY amount DESC
        """
    else:
        sql = """
            SELECT
                p.id AS participant_id,
                COALESCE(p.name, '(sem participante)') AS participant_name,
                p.participant_type,
                COUNT(DISTINCT pu.id) AS transactions,
                COALESCE(SUM(pu.total_amount), 0) AS amount
            FROM purchases pu
            LEFT JOIN participants p ON p.id = pu.participant_id
            WHERE pu.company_id = :company_id
              AND pu.cancelled_at IS NULL
              AND pu.operation_date::date BETWEEN :start_date AND :end_date
            GROUP BY p.id, p.name, p.participant_type
            ORDER BY amount DESC
        """

    rows = _rows(db, sql, {"company_id": company_id, "start_date": start, "end_date": end})
    total_amount = sum((_to_decimal(row.get("amount")) for row in rows), start=ZERO)

    cumulative = ZERO
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        amount = _to_decimal(row.get("amount"))
        share_pct = _safe_div(amount * Decimal("100"), total_amount) or ZERO
        cumulative += amount
        cumulative_pct = _safe_div(cumulative * Decimal("100"), total_amount) or ZERO
        # ABC: A=top 80%, B=80%-95%, C=95%-100%
        if cumulative_pct <= Decimal("80"):
            abc = "A"
        elif cumulative_pct <= Decimal("95"):
            abc = "B"
        else:
            abc = "C"
        enriched.append({
            "rank": index,
            "participant_id": row.get("participant_id"),
            "participant_name": row.get("participant_name"),
            "participant_type": row.get("participant_type"),
            "transactions": _int(row.get("transactions")),
            "amount": _money(amount),
            "share_percent": _percent(share_pct),
            "cumulative_amount": _money(cumulative),
            "cumulative_share_percent": _percent(cumulative_pct),
            "abc_class": abc,
        })

    top_items = enriched[:top]
    others = enriched[top:]
    others_amount = sum((_to_decimal(item["amount"]) for item in others), start=ZERO)

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "kind": kind,
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "total_amount": _money(total_amount),
        "total_participants": len(enriched),
        "top": top,
        "items": top_items,
        "others_summary": {
            "count": len(others),
            "amount": _money(others_amount),
            "share_percent": _percent(_safe_div(others_amount * Decimal("100"), total_amount) or ZERO),
        },
        "interpretation": {
            "abc_class": "A=concentra até 80% do volume; B=próximos 15%; C=últimos 5%. Use para priorizar gestão de relacionamento.",
            "share_percent": "Participação individual no volume total do período.",
            "cumulative_share_percent": "% acumulado — útil para enxergar Pareto (80/20).",
        },
    }


# -----------------------------------------------------------------------------
# 4) Revenue / DRE-like trend by month
# -----------------------------------------------------------------------------


def get_dre_monthly(
    db: Session,
    company_id: str,
    months: int = 12,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    months = max(1, min(months, 36))

    today = date.today()
    end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    # primeiro dia do mês "months-1" anterior
    year = end.year
    month = end.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)

    sales_rows = _rows(
        db,
        """
        SELECT
            TO_CHAR(operation_date::date, 'YYYY-MM') AS month_key,
            COUNT(*) AS sales_count,
            COALESCE(SUM(total_amount), 0) AS revenue
        FROM sales
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        GROUP BY 1
        ORDER BY 1
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )
    purchases_rows = _rows(
        db,
        """
        SELECT
            TO_CHAR(operation_date::date, 'YYYY-MM') AS month_key,
            COUNT(*) AS purchases_count,
            COALESCE(SUM(total_amount), 0) AS purchases_amount
        FROM purchases
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        GROUP BY 1
        ORDER BY 1
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )
    settlements_rows = _rows(
        db,
        """
        SELECT
            TO_CHAR(settlement_date, 'YYYY-MM') AS month_key,
            COALESCE(SUM(CASE WHEN direction = 'inflow'  THEN movement_amount ELSE 0 END), 0) AS realized_inflow,
            COALESCE(SUM(CASE WHEN direction = 'outflow' THEN movement_amount ELSE 0 END), 0) AS realized_outflow
        FROM settlements
        WHERE company_id = :company_id
          AND status <> 'cancelled'
          AND reversed_at IS NULL
          AND settlement_date BETWEEN :start_date AND :end_date
        GROUP BY 1
        ORDER BY 1
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    sales_map = {row["month_key"]: row for row in sales_rows}
    purchases_map = {row["month_key"]: row for row in purchases_rows}
    settlements_map = {row["month_key"]: row for row in settlements_rows}

    series: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        key = cursor.strftime("%Y-%m")
        sale = sales_map.get(key, {})
        purchase = purchases_map.get(key, {})
        settle = settlements_map.get(key, {})
        revenue = _to_decimal(sale.get("revenue"))
        purchases_amt = _to_decimal(purchase.get("purchases_amount"))
        gross_profit = revenue - purchases_amt
        gross_margin_pct = _safe_div(gross_profit * Decimal("100"), revenue)

        series.append({
            "month_key": key,
            "month_label": _month_label_pt(cursor),
            "year": cursor.year,
            "month": cursor.month,
            "revenue_amount": _money(revenue),
            "sales_count": _int(sale.get("sales_count")),
            "purchases_amount": _money(purchases_amt),
            "purchases_count": _int(purchase.get("purchases_count")),
            "gross_profit_amount": _money(gross_profit),
            "gross_margin_percent": _percent(gross_margin_pct) if gross_margin_pct is not None else None,
            "realized_inflow_amount": _money(settle.get("realized_inflow")),
            "realized_outflow_amount": _money(settle.get("realized_outflow")),
            "realized_net_amount": _money(_to_decimal(settle.get("realized_inflow")) - _to_decimal(settle.get("realized_outflow"))),
        })
        cursor = _add_one_month(cursor)

    # MoM e YoY
    by_key = {row["month_key"]: row for row in series}
    for index, row in enumerate(series):
        prev_month_key = _shift_month_key(row["month_key"], -1)
        prev_year_key = _shift_month_key(row["month_key"], -12)
        prev_revenue = _to_decimal(by_key.get(prev_month_key, {}).get("revenue_amount"))
        prev_year_revenue = _to_decimal(by_key.get(prev_year_key, {}).get("revenue_amount"))
        current_revenue = _to_decimal(row["revenue_amount"])

        mom_pct = _safe_div((current_revenue - prev_revenue) * Decimal("100"), prev_revenue)
        yoy_pct = _safe_div((current_revenue - prev_year_revenue) * Decimal("100"), prev_year_revenue)
        row["revenue_mom_percent"] = _percent(mom_pct) if mom_pct is not None else None
        row["revenue_yoy_percent"] = _percent(yoy_pct) if yoy_pct is not None else None
        # idx unused but kept for future tickers
        del index

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "months": months,
        "series": series,
    }


def _month_label_pt(d: date) -> str:
    names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{names[d.month - 1]}/{str(d.year)[-2:]}"


def _add_one_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _shift_month_key(key: str, delta: int) -> str:
    year, month = (int(part) for part in key.split("-"))
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


# -----------------------------------------------------------------------------
# 5) Cash flow 13-week rolling forecast
# -----------------------------------------------------------------------------


def get_cash_flow_13w(
    db: Session,
    company_id: str,
    weeks: int = 13,
    start_date: date | None = None,
    financial_account_id: str | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    _assert_financial_account(db, company_id=company_id, financial_account_id=financial_account_id)
    weeks = max(1, min(weeks, 26))
    start = start_date or today_in_brazil()
    # alinhar para segunda-feira da semana de start
    days_to_monday = start.weekday()
    week_start = start - timedelta(days=days_to_monday)
    end = week_start + timedelta(days=weeks * 7 - 1)

    account_filter = " AND financial_account_id = :financial_account_id" if financial_account_id else ""
    balance_params: dict[str, Any] = {"company_id": company_id}
    if financial_account_id:
        balance_params["financial_account_id"] = financial_account_id

    cash_balance = _one(
        db,
        f"""
        SELECT COALESCE(SUM(current_balance_amount), 0) AS total_balance
        FROM financial_account_balances
        WHERE company_id = :company_id
        {account_filter}
        """,
        balance_params,
    ) or {"total_balance": 0}
    opening_balance = _to_decimal(cash_balance.get("total_balance"))
    title_account_filter = " AND expected_financial_account_id = :financial_account_id" if financial_account_id else ""
    title_params = {"company_id": company_id, "start_date": week_start, "end_date": end}
    overdue_params = {"company_id": company_id, "start_date": week_start}
    if financial_account_id:
        title_params["financial_account_id"] = financial_account_id
        overdue_params["financial_account_id"] = financial_account_id

    expected_rows = _rows(
        db,
        f"""
        SELECT
            due_date,
            direction,
            COALESCE(SUM(open_amount), 0) AS amount,
            COUNT(*) AS title_count
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
          AND status IN ('open','partially_paid','overdue','partially_received')
          AND due_date BETWEEN :start_date AND :end_date
          {title_account_filter}
        GROUP BY due_date, direction
        ORDER BY due_date
        """,
        title_params,
    )

    overdue_rows = _one(
        db,
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN direction = 'receivable' THEN open_amount ELSE 0 END), 0) AS overdue_inflow,
            COALESCE(SUM(CASE WHEN direction = 'payable'    THEN open_amount ELSE 0 END), 0) AS overdue_outflow,
            COUNT(*) FILTER (WHERE direction = 'receivable') AS overdue_inflow_count,
            COUNT(*) FILTER (WHERE direction = 'payable') AS overdue_outflow_count
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
          AND status IN ('open','partially_paid','overdue','partially_received')
          AND due_date < :start_date
          {title_account_filter}
        """,
        overdue_params,
    ) or {}

    weekly = []
    cumulative_balance = opening_balance
    by_due_date: dict[date, dict[str, Decimal]] = {}
    for row in expected_rows:
        due = row["due_date"]
        bucket = by_due_date.setdefault(due, {"inflow": ZERO, "outflow": ZERO, "inflow_count": 0, "outflow_count": 0})
        if row["direction"] == "receivable":
            bucket["inflow"] += _to_decimal(row.get("amount"))
            bucket["inflow_count"] += int(row.get("title_count") or 0)
        elif row["direction"] == "payable":
            bucket["outflow"] += _to_decimal(row.get("amount"))
            bucket["outflow_count"] += int(row.get("title_count") or 0)

    overdue_inflow = _to_decimal(overdue_rows.get("overdue_inflow"))
    overdue_outflow = _to_decimal(overdue_rows.get("overdue_outflow"))
    overdue_inflow_count = _int(overdue_rows.get("overdue_inflow_count"))
    overdue_outflow_count = _int(overdue_rows.get("overdue_outflow_count"))

    for w in range(weeks):
        ws = week_start + timedelta(days=w * 7)
        we = ws + timedelta(days=6)
        inflow = ZERO
        outflow = ZERO
        inflow_count = 0
        outflow_count = 0
        cursor = ws
        while cursor <= we:
            bucket = by_due_date.get(cursor)
            if bucket:
                inflow += bucket["inflow"]
                outflow += bucket["outflow"]
                inflow_count += bucket["inflow_count"]
                outflow_count += bucket["outflow_count"]
            cursor += timedelta(days=1)
        # Vencidos entram na primeira semana, sinalizando atraso a recuperar.
        if w == 0:
            inflow += overdue_inflow
            outflow += overdue_outflow
            inflow_count += overdue_inflow_count
            outflow_count += overdue_outflow_count
        net = inflow - outflow
        cumulative_balance += net
        weekly.append({
            "week_index": w + 1,
            "week_start": ws.isoformat(),
            "week_end": we.isoformat(),
            "expected_inflow_amount": _money(inflow),
            "expected_inflow_count": inflow_count,
            "expected_outflow_amount": _money(outflow),
            "expected_outflow_count": outflow_count,
            "net_amount": _money(net),
            "projected_balance_amount": _money(cumulative_balance),
            "includes_overdue": w == 0,
        })

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "financial_account_id": financial_account_id,
        "weeks": weeks,
        "starting_week": week_start.isoformat(),
        "ending_week": end.isoformat(),
        "opening_balance_amount": _money(opening_balance),
        "overdue_inflow_amount": _money(overdue_inflow),
        "overdue_outflow_amount": _money(overdue_outflow),
        "overdue_inflow_count": overdue_inflow_count,
        "overdue_outflow_count": overdue_outflow_count,
        "weekly": weekly,
        "interpretation": {
            "method": "Forecast direto baseado em títulos financeiros em aberto, agregado por vencimento semanal.",
            "overdue_treatment": "Vencidos antes do início são somados à primeira semana e contam como itens a perseguir imediatamente.",
            "limitations": "Não considera previsão de novas vendas/compras nem sazonalidade. Para previsão estatística, exporte fact_titles e modele em Power BI.",
        },
    }


# -----------------------------------------------------------------------------
# 6) Cash flow by category (Operacional / Investimento / Financiamento)
# -----------------------------------------------------------------------------


def get_cash_flow_by_category(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    financial_account_id: str | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    _assert_financial_account(db, company_id=company_id, financial_account_id=financial_account_id)
    start, end = _default_period(start_date, end_date)
    account_filter = " AND s.financial_account_id = :financial_account_id" if financial_account_id else ""
    params: dict[str, Any] = {"company_id": company_id, "start_date": start, "end_date": end}
    if financial_account_id:
        params["financial_account_id"] = financial_account_id

    rows = _rows(
        db,
        f"""
        SELECT
            COALESCE(fc.cash_flow_group, 'operacional') AS cash_flow_group,
            COALESCE(fc.id, '(sem-categoria)') AS category_id,
            COALESCE(fc.name, '(sem categoria)') AS category_name,
            ft.direction,
            COUNT(DISTINCT s.id) AS settlement_count,
            COALESCE(SUM(s.movement_amount), 0) AS realized_amount
        FROM settlements s
        JOIN financial_titles ft ON ft.id = s.financial_title_id
        LEFT JOIN financial_categories fc ON fc.id = ft.financial_category_id
        WHERE s.company_id = :company_id
          AND s.status <> 'cancelled'
          AND s.reversed_at IS NULL
          AND s.settlement_date BETWEEN :start_date AND :end_date
          {account_filter}
        GROUP BY fc.cash_flow_group, fc.id, fc.name, ft.direction
        ORDER BY cash_flow_group, category_name
        """,
        params,
    )

    groups: dict[str, dict[str, Any]] = {}
    total_inflow = ZERO
    total_outflow = ZERO

    for row in rows:
        group = row["cash_flow_group"] or "operacional"
        bucket = groups.setdefault(group, {
            "cash_flow_group": group,
            "inflow_amount": ZERO,
            "outflow_amount": ZERO,
            "categories": {},
        })
        cat_key = row["category_id"]
        cat = bucket["categories"].setdefault(cat_key, {
            "category_id": cat_key,
            "category_name": row["category_name"],
            "inflow_amount": ZERO,
            "outflow_amount": ZERO,
            "settlement_count": 0,
        })
        amount = _to_decimal(row.get("realized_amount"))
        if row["direction"] == "receivable":
            cat["inflow_amount"] += amount
            bucket["inflow_amount"] += amount
            total_inflow += amount
        else:
            cat["outflow_amount"] += amount
            bucket["outflow_amount"] += amount
            total_outflow += amount
        cat["settlement_count"] += int(row.get("settlement_count") or 0)

    formatted_groups = []
    for group_key, group_data in groups.items():
        cats = []
        for cat in group_data["categories"].values():
            cats.append({
                "category_id": cat["category_id"],
                "category_name": cat["category_name"],
                "inflow_amount": _money(cat["inflow_amount"]),
                "outflow_amount": _money(cat["outflow_amount"]),
                "net_amount": _money(cat["inflow_amount"] - cat["outflow_amount"]),
                "settlement_count": cat["settlement_count"],
            })
        cats.sort(key=lambda c: _to_decimal(c["outflow_amount"]) + _to_decimal(c["inflow_amount"]), reverse=True)
        formatted_groups.append({
            "cash_flow_group": group_key,
            "label": _cash_flow_group_label(group_key),
            "inflow_amount": _money(group_data["inflow_amount"]),
            "outflow_amount": _money(group_data["outflow_amount"]),
            "net_amount": _money(group_data["inflow_amount"] - group_data["outflow_amount"]),
            "categories": cats,
        })

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "financial_account_id": financial_account_id,
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "total_inflow_amount": _money(total_inflow),
        "total_outflow_amount": _money(total_outflow),
        "total_net_amount": _money(total_inflow - total_outflow),
        "groups": formatted_groups,
        "interpretation": {
            "groups": "Operacional = atividades-fim do negócio. Investimento = ativos de longo prazo. Financiamento = empréstimos/sócios.",
            "source": "Baseado em settlements liquidados (caixa realizado) com cash_flow_group da categoria do título.",
            "fallback": "Títulos sem categoria entram em 'operacional' por convenção.",
        },
    }


def _cash_flow_group_label(group: str) -> str:
    labels = {
        "operacional": "Operacional",
        "investimento": "Investimento",
        "financiamento": "Financiamento",
    }
    return labels.get(group, group.title() if group else "Operacional")


# -----------------------------------------------------------------------------
# 7) Payment method mix
# -----------------------------------------------------------------------------


def get_payment_method_mix(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)

    rows = _rows(
        db,
        """
        SELECT
            COALESCE(spp.payment_method_code, '(desconhecido)') AS method_code,
            COALESCE(spp.payment_method_name, '(desconhecido)') AS method_name,
            COUNT(*) AS plan_count,
            COALESCE(SUM(spp.amount), 0) AS amount,
            SUM(CASE WHEN spp.installments > 1 THEN 1 ELSE 0 END) AS installments_count
        FROM sale_payment_plans spp
        JOIN sales s ON s.id = spp.sale_id
        WHERE spp.company_id = :company_id
          AND s.cancelled_at IS NULL
          AND s.operation_date::date BETWEEN :start_date AND :end_date
        GROUP BY spp.payment_method_code, spp.payment_method_name
        ORDER BY amount DESC
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )
    total = sum((_to_decimal(row.get("amount")) for row in rows), start=ZERO)

    items = []
    for row in rows:
        amount = _to_decimal(row.get("amount"))
        share_pct = _safe_div(amount * Decimal("100"), total) or ZERO
        items.append({
            "method_code": row["method_code"],
            "method_name": row["method_name"],
            "plan_count": _int(row.get("plan_count")),
            "amount": _money(amount),
            "share_percent": _percent(share_pct),
            "installments_count": _int(row.get("installments_count")),
        })

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "total_amount": _money(total),
        "items": items,
    }


# -----------------------------------------------------------------------------
# 8) Power BI manifest + fact / dim tables for export
# -----------------------------------------------------------------------------


def get_powerbi_manifest(api_base_url: str = "/api") -> dict[str, Any]:
    base = api_base_url.rstrip("/")
    return {
        "version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "format": {
            "encoding": "UTF-8 with BOM",
            "delimiter": ";",
            "quote_char": '"',
            "decimal_separator": ".",
            "thousand_separator": "(none)",
            "date_format": "YYYY-MM-DD",
            "datetime_format": "YYYY-MM-DD HH:MM:SS",
            "boolean_format": "true/false",
        },
        "auth": {
            "scheme": "Bearer",
            "header_name": "Authorization",
            "note": "No Power BI Desktop, use Web → Avançado → cabeçalho Authorization=Bearer <token>. Renove o token via /auth/login.",
        },
        "facts": [
            {"name": "fact_titles",      "endpoint": f"{base}/bi/exports/fact-titles?company_id={{company_id}}&format=csv",      "grain": "1 linha por título financeiro", "key": "title_id"},
            {"name": "fact_settlements", "endpoint": f"{base}/bi/exports/fact-settlements?company_id={{company_id}}&format=csv", "grain": "1 linha por baixa/liquidação", "key": "settlement_id"},
            {"name": "fact_movements",   "endpoint": f"{base}/bi/exports/fact-movements?company_id={{company_id}}&format=csv",   "grain": "1 linha por movimento financeiro interno", "key": "movement_id"},
            {"name": "fact_sales",       "endpoint": f"{base}/bi/exports/fact-sales?company_id={{company_id}}&format=csv",       "grain": "1 linha por venda (cabeçalho)", "key": "sale_id"},
            {"name": "fact_sale_items",  "endpoint": f"{base}/bi/exports/fact-sale-items?company_id={{company_id}}&format=csv",  "grain": "1 linha por item de venda", "key": "sale_item_id"},
            {"name": "fact_purchases",   "endpoint": f"{base}/bi/exports/fact-purchases?company_id={{company_id}}&format=csv",   "grain": "1 linha por compra (cabeçalho)", "key": "purchase_id"},
        ],
        "dimensions": [
            {"name": "dim_calendar",          "endpoint": f"{base}/bi/exports/dim-calendar?start_date={{start}}&end_date={{end}}&format=csv", "key": "date_key"},
            {"name": "dim_participant",       "endpoint": f"{base}/bi/exports/dim-participant?company_id={{company_id}}&format=csv",          "key": "participant_id"},
            {"name": "dim_financial_account", "endpoint": f"{base}/bi/exports/dim-financial-account?company_id={{company_id}}&format=csv",    "key": "financial_account_id"},
            {"name": "dim_category",          "endpoint": f"{base}/bi/exports/dim-category?company_id={{company_id}}&format=csv",             "key": "category_id"},
            {"name": "dim_cost_center",       "endpoint": f"{base}/bi/exports/dim-cost-center?company_id={{company_id}}&format=csv",          "key": "cost_center_id"},
            {"name": "dim_chart_account",     "endpoint": f"{base}/bi/exports/dim-chart-account?company_id={{company_id}}&format=csv",        "key": "chart_account_id"},
            {"name": "dim_product",           "endpoint": f"{base}/bi/exports/dim-product?company_id={{company_id}}&format=csv",              "key": "item_id"},
        ],
        "relationships": [
            {"from": "fact_titles.participant_id",         "to": "dim_participant.participant_id"},
            {"from": "fact_titles.financial_category_id",  "to": "dim_category.category_id"},
            {"from": "fact_titles.cost_center_id",         "to": "dim_cost_center.cost_center_id"},
            {"from": "fact_titles.due_date",               "to": "dim_calendar.date_key"},
            {"from": "fact_titles.competency_date",        "to": "dim_calendar.date_key"},
            {"from": "fact_settlements.settlement_date",   "to": "dim_calendar.date_key"},
            {"from": "fact_settlements.financial_account_id", "to": "dim_financial_account.financial_account_id"},
            {"from": "fact_movements.movement_date",       "to": "dim_calendar.date_key"},
            {"from": "fact_movements.financial_account_id","to": "dim_financial_account.financial_account_id"},
            {"from": "fact_sales.operation_date",          "to": "dim_calendar.date_key"},
            {"from": "fact_sales.participant_id",          "to": "dim_participant.participant_id"},
            {"from": "fact_sale_items.sale_id",            "to": "fact_sales.sale_id"},
            {"from": "fact_sale_items.item_id",            "to": "dim_product.item_id"},
            {"from": "fact_purchases.participant_id",      "to": "dim_participant.participant_id"},
        ],
        "powerbi_recommendations": [
            "Modelo: estrela (star schema). Cada fato → várias dims. Não use snowflake.",
            "dim_calendar deve ser marcada como 'Tabela de Datas' em Power BI.",
            "Use dim_calendar.is_business_day para slicers operacionais.",
            "Para DSO/DPO/CCC use medidas DAX baseadas em fact_titles + dim_calendar.",
            "Atualize manualmente ou agende refresh via Power BI Service apontando ao mesmo endpoint.",
        ],
        "power_query_template_m": _power_query_template(base),
    }


def _power_query_template(base_url: str) -> str:
    """Template Power Query M para colar no editor avançado."""
    return (
        "// Cole no Power BI Desktop > Obter Dados > Consulta em Branco > Editor Avançado.\n"
        "// Substitua TOKEN, COMPANY_ID e BASE_URL conforme seu ambiente.\n"
        "let\n"
        f"    BaseUrl  = \"{base_url}\",\n"
        "    Token    = \"COLAR_TOKEN_BEARER_AQUI\",\n"
        "    CompanyId= \"emp_xxxxxxx\",\n"
        "    Headers  = [#\"Authorization\" = \"Bearer \" & Token, #\"Accept\" = \"text/csv\"],\n"
        "    GetCsv   = (path as text) => Csv.Document(\n"
        "        Web.Contents(BaseUrl, [RelativePath=path, Headers=Headers]),\n"
        "        [Delimiter=\";\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]\n"
        "    ),\n"
        "    Promote  = (t as table) => Table.PromoteHeaders(t, [PromoteAllScalars=true]),\n"
        "    fact_titles      = Promote(GetCsv(\"/bi/exports/fact-titles?company_id=\" & CompanyId & \"&format=csv\")),\n"
        "    fact_settlements = Promote(GetCsv(\"/bi/exports/fact-settlements?company_id=\" & CompanyId & \"&format=csv\")),\n"
        "    fact_movements   = Promote(GetCsv(\"/bi/exports/fact-movements?company_id=\" & CompanyId & \"&format=csv\")),\n"
        "    fact_sales       = Promote(GetCsv(\"/bi/exports/fact-sales?company_id=\" & CompanyId & \"&format=csv\")),\n"
        "    dim_participant  = Promote(GetCsv(\"/bi/exports/dim-participant?company_id=\" & CompanyId & \"&format=csv\")),\n"
        "    dim_calendar     = Promote(GetCsv(\"/bi/exports/dim-calendar?start_date=2024-01-01&end_date=2030-12-31&format=csv\"))\n"
        "in\n"
        "    fact_titles\n"
    )


# -----------------------------------------------------------------------------
# 9) Fact / dim raw rows (consumidos pelos exports CSV nas rotas)
# -----------------------------------------------------------------------------


def fact_titles_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            ft.id                       AS title_id,
            ft.company_id,
            ft.direction,
            ft.title_type,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            ft.participant_id,
            COALESCE(p.name, '')        AS participant_name,
            ft.financial_category_id,
            ft.cost_center_id,
            ft.expected_financial_account_id AS financial_account_id,
            ft.payment_method_code,
            ft.payment_method_name,
            ft.document_reference,
            ft.title_name,
            ft.installment_number,
            ft.installment_total,
            ft.issue_date,
            ft.competency_date,
            ft.due_date,
            ft.expected_payment_date,
            ft.gross_amount,
            ft.discount_amount,
            ft.interest_amount,
            ft.penalty_amount,
            ft.fee_amount,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.status,
            ft.collection_status,
            ft.fiscal_status,
            CASE WHEN ft.status IN ('open','partially_paid','overdue','partially_received') AND ft.due_date < CURRENT_DATE THEN true ELSE false END AS is_overdue,
            CASE WHEN ft.status IN ('open','partially_paid','overdue','partially_received') AND ft.due_date < CURRENT_DATE THEN (CURRENT_DATE - ft.due_date) ELSE 0 END AS days_overdue,
            ft.created_at,
            ft.updated_at,
            ft.cancelled_at
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.deleted_at IS NULL
        ORDER BY ft.due_date, ft.id
        """,
        {"company_id": company_id},
    )


def fact_settlements_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            s.id              AS settlement_id,
            s.company_id,
            s.financial_title_id,
            s.financial_account_id,
            s.direction,
            s.settlement_date,
            s.received_amount,
            s.discount_amount,
            s.fee_amount,
            s.interest_amount,
            s.penalty_amount,
            s.movement_amount,
            s.title_settled_amount,
            s.status,
            s.created_at,
            s.reversed_at
        FROM settlements s
        WHERE s.company_id = :company_id
        ORDER BY s.settlement_date, s.id
        """,
        {"company_id": company_id},
    )


def fact_movements_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            fm.id                  AS movement_id,
            fm.company_id,
            fm.financial_account_id,
            fm.financial_title_id,
            fm.settlement_id,
            fm.participant_id,
            fm.direction,
            fm.movement_type,
            fm.movement_date,
            fm.amount,
            fm.currency,
            fm.source_type,
            fm.source_id,
            fm.description,
            fm.status,
            fm.reconciliation_status,
            fm.created_at
        FROM financial_movements fm
        WHERE fm.company_id = :company_id
          AND fm.reversal_of_movement_id IS NULL
          AND fm.status <> 'reversed'
        ORDER BY fm.movement_date, fm.id
        """,
        {"company_id": company_id},
    )


def fact_sales_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            s.id                AS sale_id,
            s.company_id,
            s.participant_id,
            COALESCE(p.name, '') AS participant_name,
            s.sale_type,
            s.operation_nature,
            s.fiscal_status,
            s.status,
            s.issue_date,
            s.operation_date::date AS operation_date,
            s.total_amount,
            s.discount_amount,
            s.freight_amount,
            s.tax_amount,
            s.created_at,
            s.cancelled_at
        FROM sales s
        LEFT JOIN participants p ON p.id = s.participant_id
        WHERE s.company_id = :company_id
        ORDER BY s.operation_date, s.id
        """,
        {"company_id": company_id},
    )


def fact_sale_items_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            si.id              AS sale_item_id,
            si.company_id,
            si.sale_id,
            si.item_id,
            si.description     AS item_description,
            si.quantity,
            si.unit,
            si.unit_price,
            si.discount_amount,
            si.freight_amount,
            si.tax_amount,
            si.total_amount,
            si.fiscal_classification_id,
            si.stock_lot_id,
            si.created_at
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        WHERE si.company_id = :company_id
          AND s.cancelled_at IS NULL
        ORDER BY si.created_at, si.id
        """,
        {"company_id": company_id},
    )


def fact_purchases_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            pu.id              AS purchase_id,
            pu.company_id,
            pu.participant_id,
            COALESCE(p.name, '') AS participant_name,
            pu.purchase_type,
            pu.fiscal_status,
            pu.status,
            pu.issue_date,
            pu.operation_date::date AS operation_date,
            pu.total_amount,
            pu.document_type,
            pu.document_number,
            pu.document_series,
            pu.access_key,
            pu.created_at,
            pu.cancelled_at
        FROM purchases pu
        LEFT JOIN participants p ON p.id = pu.participant_id
        WHERE pu.company_id = :company_id
        ORDER BY pu.operation_date, pu.id
        """,
        {"company_id": company_id},
    )


def dim_participant_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            p.id                AS participant_id,
            p.company_id,
            p.name              AS participant_name,
            p.trade_name,
            p.participant_type,
            p.person_type,
            p.document,
            p.email,
            p.phone,
            p.status,
            p.created_at
        FROM participants p
        WHERE p.company_id = :company_id
          AND p.deleted_at IS NULL
        ORDER BY p.name
        """,
        {"company_id": company_id},
    )


def dim_financial_account_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            fa.id                AS financial_account_id,
            fa.company_id,
            fa.name              AS account_name,
            fa.account_type,
            fa.institution_name,
            fa.currency,
            fa.opening_balance_amount,
            COALESCE(fab.current_balance_amount, fa.opening_balance_amount) AS current_balance_amount,
            fa.is_default_receivable,
            fa.is_default_payable,
            fa.status
        FROM financial_accounts fa
        LEFT JOIN financial_account_balances fab ON fab.financial_account_id = fa.id AND fab.company_id = fa.company_id
        WHERE fa.company_id = :company_id
          AND fa.deleted_at IS NULL
        ORDER BY fa.name
        """,
        {"company_id": company_id},
    )


def dim_category_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            fc.id                  AS category_id,
            fc.company_id,
            fc.code,
            fc.name                AS category_name,
            fc.category_type,
            fc.parent_id,
            fc.chart_account_id,
            fc.cash_flow_group,
            fc.affects_cash_flow,
            fc.requires_cost_center,
            fc.status
        FROM financial_categories fc
        WHERE fc.company_id = :company_id
          AND fc.deleted_at IS NULL
        ORDER BY fc.code, fc.name
        """,
        {"company_id": company_id},
    )


def dim_cost_center_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            cc.id                  AS cost_center_id,
            cc.company_id,
            cc.code,
            cc.name                AS cost_center_name,
            cc.center_type,
            cc.parent_id,
            cc.is_analytical,
            cc.responsible_name,
            cc.monthly_budget_amount,
            cc.status
        FROM cost_centers cc
        WHERE cc.company_id = :company_id
          AND cc.deleted_at IS NULL
        ORDER BY cc.code, cc.name
        """,
        {"company_id": company_id},
    )


def dim_chart_account_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            ca.id              AS chart_account_id,
            ca.company_id,
            ca.code,
            ca.name            AS chart_account_name,
            ca.account_type,
            ca.parent_id,
            ca.is_analytical,
            ca.normal_balance,
            ca.accepts_entries,
            ca.status
        FROM chart_accounts ca
        WHERE ca.company_id = :company_id
          AND ca.deleted_at IS NULL
        ORDER BY ca.code
        """,
        {"company_id": company_id},
    )


def dim_product_rows(db: Session, company_id: str) -> list[dict[str, Any]]:
    _validate_company_id(company_id)
    return _rows(
        db,
        """
        SELECT
            ci.id                AS item_id,
            ci.company_id,
            ci.sku               AS item_code,
            ci.name              AS item_name,
            ci.item_type,
            ci.unit,
            ci.barcode,
            ci.ncm,
            ci.sale_price,
            ci.standard_cost,
            ci.track_stock,
            ci.status,
            ci.created_at
        FROM catalog_items ci
        WHERE ci.company_id = :company_id
          AND ci.deleted_at IS NULL
        ORDER BY ci.name
        """,
        {"company_id": company_id},
    )


def dim_calendar_rows(start_date: date, end_date: date) -> list[dict[str, Any]]:
    if end_date < start_date:
        raise ValueError("Data final não pode ser menor que data inicial.")
    if (end_date - start_date).days > 366 * 10:
        raise ValueError("Período de calendário muito grande (máximo 10 anos).")
    holidays_pt = {
        (1, 1): "Confraternização Universal",
        (4, 21): "Tiradentes",
        (5, 1): "Dia do Trabalho",
        (9, 7): "Independência",
        (10, 12): "Nossa Senhora Aparecida",
        (11, 2): "Finados",
        (11, 15): "Proclamação da República",
        (12, 25): "Natal",
    }
    rows: list[dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date:
        weekday = cursor.weekday()  # 0=Mon..6=Sun
        is_weekend = weekday >= 5
        holiday_name = holidays_pt.get((cursor.month, cursor.day))
        is_business_day = not is_weekend and holiday_name is None
        # quarter
        quarter = (cursor.month - 1) // 3 + 1
        rows.append({
            "date_key": cursor.isoformat(),
            "year": cursor.year,
            "quarter": quarter,
            "quarter_label": f"{cursor.year}-Q{quarter}",
            "month": cursor.month,
            "month_key": cursor.strftime("%Y-%m"),
            "month_label_pt": _month_label_pt(cursor),
            "day": cursor.day,
            "day_of_week": weekday + 1,
            "day_name_pt": ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][weekday],
            "iso_week": cursor.isocalendar().week,
            "is_weekend": is_weekend,
            "is_business_day": is_business_day,
            "holiday_name_pt": holiday_name,
            "year_month": int(cursor.strftime("%Y%m")),
        })
        cursor += timedelta(days=1)
    return rows


# -----------------------------------------------------------------------------
# 10) BI rules (descritivo)
# -----------------------------------------------------------------------------


def get_bi_rules() -> dict[str, Any]:
    return {
        "module": "bi_analytics",
        "name": "BI Analytics — KPIs gerenciais e exports Power BI",
        "version": "1.0.0",
        "principles": [
            "Não cria fato financeiro — agrega o que já existe.",
            "Toda exportação CSV é UTF-8 com BOM, separador ';', decimal '.', datas ISO.",
            "Respeita escopo de empresa via security/tenant_scope.",
            "Star schema sugerido: facts × dimensions com chaves diretas.",
        ],
        "kpi_endpoints": [
            "/bi/working-capital-kpis",
            "/bi/aging-receivables",
            "/bi/aging-payables",
            "/bi/customer-concentration",
            "/bi/supplier-concentration",
            "/bi/dre-monthly",
            "/bi/cash-flow-13w",
            "/bi/cash-flow-by-category",
            "/bi/payment-method-mix",
        ],
        "export_endpoints": [
            "/bi/exports/fact-titles",
            "/bi/exports/fact-settlements",
            "/bi/exports/fact-movements",
            "/bi/exports/fact-sales",
            "/bi/exports/fact-sale-items",
            "/bi/exports/fact-purchases",
            "/bi/exports/dim-calendar",
            "/bi/exports/dim-participant",
            "/bi/exports/dim-financial-account",
            "/bi/exports/dim-category",
            "/bi/exports/dim-cost-center",
            "/bi/exports/dim-chart-account",
            "/bi/exports/dim-product",
        ],
        "manifest_endpoint": "/bi/powerbi-manifest",
    }
