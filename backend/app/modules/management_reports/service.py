from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.shared.datetime import today_in_brazil
from app.shared.ids import assert_valid_id


MONEY_QUANT = Decimal("0.01")
ACTIVE_TITLE_STATUS_SQL = "('open', 'partially_paid', 'partially_received', 'overdue')"
RECONCILED_MOVEMENT_STATUS_SQL = "('matched')"
PENDING_RECONCILIATION_STATUS_SQL = "('pending', 'divergent')"
PENDING_STATEMENT_STATUS_SQL = "('pending', 'divergent')"
TITLE_EXPORT_LIMIT = 5000
FISCAL_REPORT_EXPORT_LIMIT = 5000
ACCOUNTANT_EXPORT_LIMIT = 5000
PENDING_SALE_FISCAL_STATUS_SQL = "('pending_classification', 'pending_document', 'blocked', 'document_cancelled', 'draft')"
PENDING_PURCHASE_FISCAL_STATUS_SQL = "('pending_document', 'pending_classification', 'draft', 'divergent')"
PENDING_TITLE_FISCAL_STATUS_SQL = "('pending_document', 'pending_classification', 'draft', 'divergent', 'blocked', 'document_cancelled')"
PENDING_FISCAL_DOCUMENT_STATUS_SQL = "('pending', 'processing', 'contingency')"
ERROR_FISCAL_DOCUMENT_STATUS_SQL = "('error', 'denied')"
AUTHORIZED_FISCAL_DOCUMENT_STATUS_SQL = "('authorized', 'issued')"
TITLE_STATUS_VALUES = {
    "draft",
    "open",
    "overdue",
    "partially_received",
    "received",
    "partially_paid",
    "paid",
    "cancelled",
    "written_off",
    "renegotiated",
}


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
    if value is None:
        value = Decimal("0")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _rows(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        result = db.execute(text(sql), params)
        return [dict(row._mapping) for row in result.fetchall()]
    except SQLAlchemyError as exc:
        raise ValueError(
            "Falha ao consultar relatórios gerenciais. "
            "Confirme se o PostgreSQL está online, se as migrations Alembic estão em head "
            "e se a base possui as tabelas do ciclo financeiro."
        ) from exc


def _one(db: Session, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(db, sql, params)
    return rows[0] if rows else None


def _normalize_money_fields(payload: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    normalized = dict(payload)
    for field in fields:
        if field in normalized:
            normalized[field] = _money(normalized[field])
    return normalized


def get_management_report_rules() -> dict[str, Any]:
    return {
        "module": "management_reports",
        "name": "Relatórios gerenciais, qualidade do ciclo financeiro e saúde do MVP",
        "version": "1.3-backend-only",
        "goal": (
            "Consolidar o ciclo financeiro já existente em leituras executivas, "
            "sem criar fato financeiro novo e sem corrigir dado ruim no relatório."
        ),
        "critical_distinctions": [
            "Venda não é recebimento.",
            "Compra não é pagamento.",
            "Título financeiro não é dinheiro.",
            "Baixa/liquidação não é conciliação.",
            "Extrato bancário não altera saldo interno.",
            "Match de conciliação não cria operação original.",
            "Relatório lê fatos consistentes; não deve mascarar inconsistência operacional.",
        ],
        "backend_guarantees": [
            "Todas as rotas exigem company_id válido com prefixo emp_, exceto /rules.",
            "Leituras usam tabelas persistentes já existentes; nenhuma migration nova foi adicionada.",
            "Valores monetários são serializados como string decimal com 2 casas.",
            "Listagens operacionais possuem limit/offset.",
            "Documentos fiscais preparatórios e fechamento MVP são read-only e não criam fatos financeiros.",
            "O frontend futuro poderá consumir estes endpoints sem calcular regra financeira oficial.",
        ],
        "endpoints": [
            "/management-reports/rules",
            "/management-reports/available-companies",
            "/management-reports/company-context",
            "/management-reports/financial-cycle",
            "/management-reports/mvp-health",
            "/management-reports/backlog",
            "/management-reports/title-references",
            "/management-reports/preparatory-fiscal-documents",
            "/management-reports/financial-close-mvp",
            "/management-reports/accountant-pack",
        ],
    }


def get_available_companies(db: Session, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    companies = _rows(
        db,
        """
        SELECT
            id,
            legal_name,
            trade_name,
            cnpj,
            status,
            tax_regime,
            fiscal_environment,
            created_at,
            updated_at
        FROM companies
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC, id ASC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    return {
        "total_returned": len(companies),
        "items": [
            {
                **company,
                "display_name": company.get("trade_name")
                or company.get("legal_name")
                or company.get("id"),
            }
            for company in companies
        ],
        "notes": [
            "Use um company_id existente nos relatórios gerenciais.",
            "O relatório não deve aceitar empresa inexistente, mesmo quando consultas agregadas retornam zero.",
        ],
    }


def _get_company_or_raise(db: Session, company_id: str) -> dict[str, Any]:
    _validate_company_id(company_id)
    company = _one(
        db,
        """
        SELECT
            id,
            legal_name,
            trade_name,
            cnpj,
            status,
            tax_regime,
            fiscal_environment,
            uses_accounts_receivable,
            uses_accounts_payable,
            uses_cash_control,
            uses_cost_center,
            uses_chart_of_accounts,
            prepared_for_tax_reform,
            created_at,
            updated_at
        FROM companies
        WHERE id = :company_id
          AND deleted_at IS NULL
        """,
        {"company_id": company_id},
    )
    if not company:
        raise ValueError("Empresa não encontrada.")

    company["display_name"] = company.get("trade_name") or company.get("legal_name") or company.get("id")
    return company


def get_company_context(db: Session, company_id: str) -> dict[str, Any]:
    return _get_company_or_raise(db, company_id)


def get_financial_cycle_report(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)

    titles = _rows(
        db,
        f"""
        SELECT
            direction,
            COUNT(*) AS total_titles,
            COALESCE(SUM(gross_amount), 0) AS gross_amount,
            COALESCE(SUM(net_amount), 0) AS net_amount,
            COALESCE(SUM(paid_amount), 0) AS paid_amount,
            COALESCE(SUM(open_amount), 0) AS open_amount,
            COALESCE(SUM(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS active_open_amount,
            COUNT(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS active_titles,
            COUNT(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN 1 END) AS overdue_titles,
            COALESCE(SUM(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN open_amount ELSE 0 END), 0) AS overdue_amount,
            COUNT(CASE WHEN participant_id IS NULL THEN 1 END) AS titles_without_participant,
            COUNT(CASE WHEN COALESCE(source_type, '') = '' AND COALESCE(source_id, '') = '' AND sale_id IS NULL AND document_reference IS NULL THEN 1 END) AS titles_without_clear_origin
        FROM financial_titles
        WHERE company_id = :company_id
          AND due_date BETWEEN :start_date AND :end_date
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
        GROUP BY direction
        ORDER BY direction
        """,
        {"company_id": company_id, "start_date": start, "end_date": end, "today": today_in_brazil()},
    )

    movements = _rows(
        db,
        f"""
        SELECT
            direction,
            COUNT(*) AS total_movements,
            COALESCE(SUM(amount), 0) AS amount,
            COALESCE(SUM(CASE WHEN reconciliation_status IN {RECONCILED_MOVEMENT_STATUS_SQL} THEN amount ELSE 0 END), 0) AS reconciled_amount,
            COALESCE(SUM(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN amount ELSE 0 END), 0) AS unreconciled_amount,
            COUNT(CASE WHEN reconciliation_status IN {RECONCILED_MOVEMENT_STATUS_SQL} THEN 1 END) AS reconciled_movements,
            COUNT(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN 1 END) AS unreconciled_movements
        FROM financial_movements
        WHERE company_id = :company_id
          AND movement_date BETWEEN :start_date AND :end_date
          AND reversal_of_movement_id IS NULL
          AND status = 'posted'
          AND reconciliation_status <> 'reversed'
        GROUP BY direction
        ORDER BY direction
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    settlements = _rows(
        db,
        """
        SELECT
            direction,
            COUNT(*) AS total_settlements,
            COALESCE(SUM(received_amount), 0) AS received_amount,
            COALESCE(SUM(title_settled_amount), 0) AS title_settled_amount,
            COALESCE(SUM(movement_amount), 0) AS movement_amount
        FROM settlements
        WHERE company_id = :company_id
          AND settlement_date BETWEEN :start_date AND :end_date
          AND reversed_at IS NULL
          AND status = 'active'
        GROUP BY direction
        ORDER BY direction
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    balances = _rows(
        db,
        """
        SELECT
            fa.id AS financial_account_id,
            fa.name AS financial_account_name,
            fa.account_type,
            'BRL' AS currency,
            fab.current_balance_amount AS balance_amount
        FROM financial_account_balances fab
        JOIN financial_accounts fa ON fa.id = fab.financial_account_id
        WHERE fab.company_id = :company_id
        ORDER BY fa.name
        """,
        {"company_id": company_id},
    )

    titles = [
        _normalize_money_fields(
            row,
            [
                "gross_amount",
                "net_amount",
                "paid_amount",
                "open_amount",
                "active_open_amount",
                "overdue_amount",
            ],
        )
        for row in titles
    ]
    movements = [
        _normalize_money_fields(row, ["amount", "reconciled_amount", "unreconciled_amount"])
        for row in movements
    ]
    settlements = [
        _normalize_money_fields(row, ["received_amount", "title_settled_amount", "movement_amount"])
        for row in settlements
    ]
    balances = [_normalize_money_fields(row, ["balance_amount"]) for row in balances]

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "titles_by_direction": titles,
        "settlements_by_direction": settlements,
        "movements_by_direction": movements,
        "financial_account_balances": balances,
        "interpretation_rules": [
            "titles_by_direction mostra direitos/obrigações por vencimento.",
            "settlements_by_direction mostra baixas/liquidações realizadas.",
            "movements_by_direction mostra dinheiro interno movimentado.",
            "financial_account_balances mostra saldo interno materializado por conta financeira.",
            "Conciliação é conferência posterior; não deve ser confundida com baixa.",
        ],
    }


def get_operational_backlog(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    limit = max(1, min(limit, 100))

    today = today_in_brazil()

    overdue_titles = _rows(
        db,
        f"""
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            ft.due_date,
            ft.status,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            p.name AS participant_name
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND ft.status IN {ACTIVE_TITLE_STATUS_SQL}
          AND ft.due_date < :today
        ORDER BY ft.due_date ASC, ft.open_amount DESC
        LIMIT :limit
        """,
        {"company_id": company_id, "today": today, "limit": limit},
    )

    origin_pendencies = _rows(
        db,
        """
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            ft.due_date,
            ft.status,
            ft.net_amount,
            ft.open_amount,
            p.name AS participant_name
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND COALESCE(ft.source_type, '') = ''
          AND COALESCE(ft.source_id, '') = ''
          AND ft.sale_id IS NULL
          AND ft.document_reference IS NULL
        ORDER BY ft.created_at DESC
        LIMIT :limit
        """,
        {"company_id": company_id, "limit": limit},
    )

    unreconciled_movements = _rows(
        db,
        f"""
        SELECT
            fm.id,
            fm.direction,
            fm.movement_date,
            fm.amount,
            fm.reconciliation_status,
            fm.description,
            fa.name AS financial_account_name,
            p.name AS participant_name
        FROM financial_movements fm
        JOIN financial_accounts fa ON fa.id = fm.financial_account_id
        LEFT JOIN participants p ON p.id = fm.participant_id
        WHERE fm.company_id = :company_id
          AND fm.reversal_of_movement_id IS NULL
          AND fm.status = 'posted'
          AND fm.reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
          AND fm.movement_date BETWEEN :start_date AND :end_date
        ORDER BY fm.movement_date DESC, fm.created_at DESC
        LIMIT :limit
        """,
        {"company_id": company_id, "start_date": start, "end_date": end, "limit": limit},
    )

    statement_pendencies = _rows(
        db,
        f"""
        SELECT
            bsl.id,
            COALESCE(bsl.posted_at::date, bsl.line_date) AS statement_date,
            bsl.description,
            bsl.amount,
            bsl.direction,
            bsl.status,
            fa.name AS financial_account_name
        FROM bank_statement_lines bsl
        JOIN financial_accounts fa ON fa.id = bsl.financial_account_id
        WHERE bsl.company_id = :company_id
          AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
          AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date
        ORDER BY COALESCE(bsl.posted_at::date, bsl.line_date) DESC
        LIMIT :limit
        """,
        {"company_id": company_id, "start_date": start, "end_date": end, "limit": limit},
    )

    totals = _one(
        db,
        f"""
        SELECT
            (SELECT COUNT(*)
             FROM financial_titles ft
             WHERE ft.company_id = :company_id
               AND ft.cancelled_at IS NULL
               AND ft.deleted_at IS NULL
               AND ft.status IN {ACTIVE_TITLE_STATUS_SQL}
               AND ft.due_date < :today) AS overdue_titles,
            (SELECT COALESCE(SUM(ft.open_amount), 0)
             FROM financial_titles ft
             WHERE ft.company_id = :company_id
               AND ft.cancelled_at IS NULL
               AND ft.deleted_at IS NULL
               AND ft.status IN {ACTIVE_TITLE_STATUS_SQL}
               AND ft.due_date < :today) AS overdue_titles_amount,
            (SELECT COUNT(*)
             FROM financial_titles ft
             WHERE ft.company_id = :company_id
               AND ft.cancelled_at IS NULL
               AND ft.deleted_at IS NULL
               AND COALESCE(ft.source_type, '') = ''
               AND COALESCE(ft.source_id, '') = ''
               AND ft.sale_id IS NULL
               AND ft.document_reference IS NULL) AS titles_without_clear_origin,
            (SELECT COALESCE(SUM(ft.open_amount), 0)
             FROM financial_titles ft
             WHERE ft.company_id = :company_id
               AND ft.cancelled_at IS NULL
               AND ft.deleted_at IS NULL
               AND COALESCE(ft.source_type, '') = ''
               AND COALESCE(ft.source_id, '') = ''
               AND ft.sale_id IS NULL
               AND ft.document_reference IS NULL) AS titles_without_clear_origin_amount,
            (SELECT COUNT(*)
             FROM financial_movements fm
             WHERE fm.company_id = :company_id
               AND fm.reversal_of_movement_id IS NULL
               AND fm.status = 'posted'
               AND fm.reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
               AND fm.movement_date BETWEEN :start_date AND :end_date) AS unreconciled_movements,
            (SELECT COALESCE(SUM(fm.amount), 0)
             FROM financial_movements fm
             WHERE fm.company_id = :company_id
               AND fm.reversal_of_movement_id IS NULL
               AND fm.status = 'posted'
               AND fm.reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
               AND fm.movement_date BETWEEN :start_date AND :end_date) AS unreconciled_movements_amount,
            (SELECT COUNT(*)
             FROM bank_statement_lines bsl
             WHERE bsl.company_id = :company_id
               AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
               AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date) AS unmatched_bank_statement_lines,
            (SELECT COALESCE(SUM(bsl.amount), 0)
             FROM bank_statement_lines bsl
             WHERE bsl.company_id = :company_id
               AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
               AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date) AS unmatched_bank_statement_amount
        """,
        {"company_id": company_id, "start_date": start, "end_date": end, "today": today},
    ) or {}

    total_count_keys = [
        "overdue_titles",
        "titles_without_clear_origin",
        "unreconciled_movements",
        "unmatched_bank_statement_lines",
    ]
    total_amount_keys = [
        "overdue_titles_amount",
        "titles_without_clear_origin_amount",
        "unreconciled_movements_amount",
        "unmatched_bank_statement_amount",
    ]
    total_counts = {key: _int(totals.get(key)) for key in total_count_keys}
    total_amounts = {key: _money(totals.get(key)) for key in total_amount_keys}
    money_fields = ["net_amount", "paid_amount", "open_amount", "amount"]
    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "limit": limit,
        "totals": {
            **total_counts,
            **total_amounts,
            "total_pendencies": sum(total_counts.values()),
            "is_limited": any(value > limit for value in total_counts.values()),
        },
        "overdue_titles": [_normalize_money_fields(row, money_fields) for row in overdue_titles],
        "titles_without_clear_origin": [_normalize_money_fields(row, money_fields) for row in origin_pendencies],
        "unreconciled_movements": [_normalize_money_fields(row, money_fields) for row in unreconciled_movements],
        "unmatched_bank_statement_lines": [_normalize_money_fields(row, money_fields) for row in statement_pendencies],
    }


def get_title_references(
    db: Session,
    company_id: str,
    direction: str | None = None,
    status: str | None = None,
    search: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
    export_all: bool = False,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    if due_from and due_to and due_to < due_from:
        raise ValueError("due_to deve ser maior ou igual a due_from.")
    limit = TITLE_EXPORT_LIMIT if export_all else max(1, min(limit, 200))
    offset = 0 if export_all else max(0, offset)

    where = ["ft.company_id = :company_id", "ft.cancelled_at IS NULL", "ft.deleted_at IS NULL"]
    params: dict[str, Any] = {"company_id": company_id, "limit": limit, "offset": offset}
    if direction:
        if direction not in {"receivable", "payable"}:
            raise ValueError("direction deve ser receivable ou payable.")
        where.append("ft.direction = :direction")
        params["direction"] = direction
    if status:
        if status not in TITLE_STATUS_VALUES:
            raise ValueError("status de título financeiro inválido.")
        where.append("ft.status = :status")
        params["status"] = status
    if due_from:
        where.append("ft.due_date >= :due_from")
        params["due_from"] = due_from
    if due_to:
        where.append("ft.due_date <= :due_to")
        params["due_to"] = due_to
    if search:
        where.append(
            "("
            "ft.id ILIKE :search OR "
            "COALESCE(ft.title_name, '') ILIKE :search OR "
            "COALESCE(ft.document_reference, '') ILIKE :search OR "
            "COALESCE(ft.source_id, '') ILIKE :search OR "
            "COALESCE(p.name, '') ILIKE :search OR "
            "COALESCE(p.document, '') ILIKE :search OR "
            "COALESCE(s.sale_number_text, '') ILIKE :search OR "
            "COALESCE(ft.notes, '') ILIKE :search"
            ")"
        )
        params["search"] = f"%{search}%"

    where_sql = " AND ".join(where)
    rows = _rows(
        db,
        f"""
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, CONCAT(
                CASE WHEN ft.direction = 'receivable' THEN 'CR' ELSE 'CP' END,
                '-',
                TO_CHAR(ft.due_date, 'YYYYMMDD'),
                '-',
                UPPER(RIGHT(REPLACE(ft.id, '-', ''), 6))
            )) AS human_reference,
            ft.title_name,
            ft.title_type,
            ft.document_reference,
            ft.installment_number,
            ft.installment_total,
            ft.status,
            ft.collection_status,
            ft.fiscal_status,
            ft.issue_date,
            ft.competency_date,
            ft.due_date,
            ft.expected_payment_date,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            s.sale_number_text,
            ft.payment_method_name,
            fa.name AS expected_financial_account_name,
            p.name AS participant_name,
            p.document AS participant_document,
            p.participant_type,
            COALESCE(c.trade_name, c.legal_name, c.id) AS company_display_name
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        LEFT JOIN sales s ON s.id = ft.sale_id
        LEFT JOIN financial_accounts fa ON fa.id = ft.expected_financial_account_id
        JOIN companies c ON c.id = ft.company_id
        WHERE {where_sql}
        ORDER BY ft.due_date ASC, ft.created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    count_row = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(ft.net_amount), 0) AS total_net_amount,
            COALESCE(SUM(ft.paid_amount), 0) AS total_paid_amount,
            COALESCE(SUM(ft.open_amount), 0) AS total_open_amount,
            COUNT(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS active_count,
            COALESCE(SUM(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} THEN ft.open_amount ELSE 0 END), 0) AS active_open_amount,
            COUNT(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} AND ft.due_date < :today THEN 1 END) AS overdue_count,
            COALESCE(SUM(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} AND ft.due_date < :today THEN ft.open_amount ELSE 0 END), 0) AS overdue_open_amount
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        LEFT JOIN sales s ON s.id = ft.sale_id
        WHERE {where_sql}
        """,
        {**params, "today": today_in_brazil()},
    ) or {"total": 0}
    total = _int(count_row.get("total"))

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "filters": {
            "direction": direction,
            "status": status,
            "search": search,
            "due_from": due_from.isoformat() if due_from else None,
            "due_to": due_to.isoformat() if due_to else None,
            "limit": limit,
            "offset": offset,
            "export_all": export_all,
        },
        "total": total,
        "summary": {
            "total_count": total,
            "total_net_amount": _money(count_row.get("total_net_amount")),
            "total_paid_amount": _money(count_row.get("total_paid_amount")),
            "total_open_amount": _money(count_row.get("total_open_amount")),
            "active_count": _int(count_row.get("active_count")),
            "active_open_amount": _money(count_row.get("active_open_amount")),
            "overdue_count": _int(count_row.get("overdue_count")),
            "overdue_open_amount": _money(count_row.get("overdue_open_amount")),
            "page_count": len(rows),
            "has_previous": offset > 0,
            "has_next": (offset + len(rows)) < total,
            "is_export_limited": export_all and total > len(rows),
        },
        "items": [
            _normalize_money_fields(row, ["net_amount", "paid_amount", "open_amount"])
            for row in rows
        ],
        "notes": [
            "human_reference prioriza title_name; quando ausente, usa document_reference ou referência derivada de direção, vencimento e sufixo do ID.",
            "A referência humana não substitui o ID técnico; ela melhora leitura de tela, filtros e relatórios.",
            "Título financeiro não é dinheiro; baixa, movimento financeiro e conciliação são fatos separados.",
            f"export_all retorna no máximo {TITLE_EXPORT_LIMIT} registros por chamada para proteger o ambiente.",
        ],
    }


def get_mvp_health(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    today = today_in_brazil()

    counts = _one(
        db,
        """
        SELECT
            (SELECT COUNT(*) FROM participants WHERE company_id = :company_id AND deleted_at IS NULL) AS participants_count,
            (SELECT COUNT(*) FROM catalog_items WHERE company_id = :company_id AND deleted_at IS NULL) AS catalog_items_count,
            (SELECT COUNT(*) FROM fiscal_classifications WHERE company_id = :company_id AND deleted_at IS NULL) AS fiscal_classifications_count,
            (SELECT COUNT(*) FROM sales WHERE company_id = :company_id AND cancelled_at IS NULL) AS sales_count,
            (SELECT COUNT(*) FROM purchases WHERE company_id = :company_id AND cancelled_at IS NULL) AS purchases_count,
            (SELECT COUNT(*) FROM financial_titles WHERE company_id = :company_id AND cancelled_at IS NULL AND deleted_at IS NULL) AS titles_count,
            (SELECT COUNT(*) FROM settlements WHERE company_id = :company_id AND reversed_at IS NULL AND status = 'active') AS settlements_count,
            (SELECT COUNT(*) FROM financial_movements WHERE company_id = :company_id AND reversal_of_movement_id IS NULL AND status = 'posted' AND reconciliation_status <> 'reversed') AS movements_count,
            (SELECT COUNT(*) FROM reconciliation_matches WHERE company_id = :company_id AND reversed_at IS NULL) AS reconciliation_matches_count
        """,
        {"company_id": company_id},
    ) or {}

    pendencies = _one(
        db,
        f"""
        SELECT
            COUNT(CASE WHEN ft.participant_id IS NULL THEN 1 END) AS titles_without_participant,
            COALESCE(SUM(CASE WHEN ft.participant_id IS NULL THEN ft.open_amount ELSE 0 END), 0) AS titles_without_participant_amount,
            COUNT(CASE WHEN COALESCE(ft.source_type, '') = '' AND COALESCE(ft.source_id, '') = '' AND ft.sale_id IS NULL AND ft.document_reference IS NULL THEN 1 END) AS titles_without_clear_origin,
            COALESCE(SUM(CASE WHEN COALESCE(ft.source_type, '') = '' AND COALESCE(ft.source_id, '') = '' AND ft.sale_id IS NULL AND ft.document_reference IS NULL THEN ft.open_amount ELSE 0 END), 0) AS titles_without_clear_origin_amount,
            COUNT(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} AND ft.due_date < :today THEN 1 END) AS overdue_titles,
            COALESCE(SUM(CASE WHEN ft.status IN {ACTIVE_TITLE_STATUS_SQL} AND ft.due_date < :today THEN ft.open_amount ELSE 0 END), 0) AS overdue_amount
        FROM financial_titles ft
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
        """,
        {"company_id": company_id, "today": today},
    ) or {}

    unreconciled = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS unreconciled_movements,
            COALESCE(SUM(amount), 0) AS unreconciled_amount
        FROM financial_movements
        WHERE company_id = :company_id
          AND reversal_of_movement_id IS NULL
          AND status = 'posted'
          AND reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
          AND movement_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    unmatched_statements = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS unmatched_bank_statement_lines,
            COALESCE(SUM(amount), 0) AS unmatched_bank_statement_amount
        FROM bank_statement_lines
        WHERE company_id = :company_id
          AND status IN {PENDING_STATEMENT_STATUS_SQL}
          AND COALESCE(posted_at::date, line_date) BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    numeric_counts = {key: _int(value) for key, value in counts.items()}
    money_pendency_fields = {
        "overdue_amount",
        "titles_without_participant_amount",
        "titles_without_clear_origin_amount",
    }
    numeric_pendencies = {key: _int(value) for key, value in pendencies.items() if key not in money_pendency_fields}
    unreconciled_count = _int(unreconciled.get("unreconciled_movements"))
    unmatched_statement_count = _int(unmatched_statements.get("unmatched_bank_statement_lines"))

    overdue_amount = _decimal(pendencies.get("overdue_amount"))
    origin_amount = _decimal(pendencies.get("titles_without_clear_origin_amount"))
    participant_amount = _decimal(pendencies.get("titles_without_participant_amount"))
    unreconciled_amount = _decimal(unreconciled.get("unreconciled_amount"))
    unmatched_statement_amount = _decimal(unmatched_statements.get("unmatched_bank_statement_amount"))

    def amount_penalty(value: Decimal, *, unit: Decimal = Decimal("1000.00"), cap: int = 10) -> int:
        absolute = abs(_decimal(value))
        if absolute <= Decimal("0.00"):
            return 0
        return min(cap, int((absolute / unit).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

    score_components = {
        "titles_without_clear_origin": min(
            20,
            numeric_pendencies.get("titles_without_clear_origin", 0) * 3
            + amount_penalty(origin_amount, cap=8),
        ),
        "titles_without_participant": min(
            15,
            numeric_pendencies.get("titles_without_participant", 0) * 5
            + amount_penalty(participant_amount, cap=5),
        ),
        "overdue_titles": min(
            30,
            numeric_pendencies.get("overdue_titles", 0) * 2
            + amount_penalty(overdue_amount, cap=15),
        ),
        "unreconciled_movements": min(
            20,
            unreconciled_count * 2 + amount_penalty(unreconciled_amount, cap=10),
        ),
        "unmatched_bank_statement_lines": min(10, unmatched_statement_count * 2),
    }

    score = max(0, 100 - sum(score_components.values()))

    blockers: list[str] = []
    warnings: list[str] = []
    if numeric_counts.get("titles_count", 0) == 0:
        blockers.append("Ainda não existem títulos financeiros para demonstrar ciclo de recebíveis/pagáveis.")
    if numeric_counts.get("movements_count", 0) == 0:
        warnings.append("Ainda não existem movimentos financeiros realizados.")
    if numeric_pendencies.get("titles_without_clear_origin", 0) > 0:
        warnings.append("Existem títulos sem origem clara; isso reduz rastreabilidade.")
    if numeric_pendencies.get("titles_without_participant", 0) > 0:
        warnings.append("Existem títulos sem participante vinculado; isso compromete cobrança, pagamento e auditoria.")
    if numeric_pendencies.get("overdue_titles", 0) > 0:
        warnings.append("Existem títulos vencidos em aberto.")
    if unreconciled_count > 0:
        warnings.append("Existem movimentos não conciliados no período informado.")
    if unmatched_statement_count > 0:
        warnings.append("Existem linhas de extrato bancário sem match no período informado.")

    status = "healthy"
    if blockers or score < 60:
        status = "blocked"
    elif score < 85 or warnings:
        status = "attention"

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "reference_date": today.isoformat(),
        "status": status,
        "score": score,
        "counts": numeric_counts,
        "pendencies": {
            **numeric_pendencies,
            "overdue_amount": _money(overdue_amount),
            "titles_without_participant_amount": _money(participant_amount),
            "titles_without_clear_origin_amount": _money(origin_amount),
            "unreconciled_movements": unreconciled_count,
            "unreconciled_amount": _money(unreconciled_amount),
            "unmatched_bank_statement_lines": unmatched_statement_count,
            "unmatched_bank_statement_amount": _money(unmatched_statement_amount),
        },
        "score_components": score_components,
        "blockers": blockers,
        "warnings": warnings,
        "next_backend_priorities": [
            "Conferir origem e participante dos títulos financeiros.",
            "Validar conciliação dos movimentos e extratos do período.",
            "Priorizar títulos vencidos pelo valor financeiro em aberto.",
            "Preparar relatórios/fechamento sem mascarar pendências.",
            "Só considerar a saúde confiável quando bloqueios e alertas estiverem zerados.",
        ],
        "calculation_notes": [
            "Contadores cadastrais são históricos da empresa ativa.",
            "Pendências de vencimento consideram títulos em aberto, parcialmente pagos ou parcialmente recebidos.",
            "Pendências de conciliação consideram movimentos postados não estornados e linhas de extrato sem match no período selecionado.",
            "Score pondera quantidade e valor financeiro; ele é indicador operacional, não substitui auditoria contábil.",
        ],
    }


HEALTH_INDICATOR_LABELS = {
    "participants": "Participantes",
    "titles": "Títulos",
    "movements": "Movimentos",
    "sales": "Vendas",
    "purchases": "Compras",
    "reconciliation_matches": "Conciliações",
    "overdue_titles": "Títulos vencidos",
    "titles_without_clear_origin": "Títulos sem origem clara",
    "titles_without_participant": "Títulos sem participante",
    "unreconciled_movements": "Movimentos sem conciliação",
    "unmatched_bank_statement_lines": "Extratos sem match",
}

HEALTH_INDICATOR_MONEY_FIELDS = {
    "gross_amount",
    "discount_amount",
    "interest_amount",
    "penalty_amount",
    "fee_amount",
    "net_amount",
    "paid_amount",
    "open_amount",
    "subtotal_amount",
    "freight_amount",
    "tax_amount",
    "total_amount",
    "receivable_total_amount",
    "payable_total_amount",
    "invoice_total_amount",
    "amount",
    "matched_amount",
    "line_amount",
    "movement_amount",
    "difference_amount",
    "tolerance_amount",
}

HEALTH_INDICATOR_QUERIES: dict[str, tuple[list[str], str]] = {
    "participants": (
        [
            "id",
            "name",
            "trade_name",
            "participant_type",
            "person_type",
            "document",
            "email",
            "phone",
            "status",
            "origin",
            "created_at",
            "updated_at",
        ],
        f"""
        SELECT
            id,
            name,
            trade_name,
            participant_type,
            person_type,
            document,
            email,
            phone,
            status,
            origin,
            created_at,
            updated_at
        FROM participants
        WHERE company_id = :company_id
          AND deleted_at IS NULL
        ORDER BY name ASC, created_at DESC, id ASC
        """,
    ),
    "titles": (
        [
            "id",
            "direction",
            "title_reference",
            "participant_name",
            "status",
            "collection_status",
            "fiscal_status",
            "issue_date",
            "competency_date",
            "due_date",
            "gross_amount",
            "net_amount",
            "paid_amount",
            "open_amount",
            "source_type",
            "source_id",
            "sale_id",
            "document_reference",
            "installment_number",
            "installment_total",
            "created_at",
        ],
        f"""
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            p.name AS participant_name,
            ft.status,
            ft.collection_status,
            ft.fiscal_status,
            ft.issue_date,
            ft.competency_date,
            ft.due_date,
            ft.gross_amount,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            ft.document_reference,
            ft.installment_number,
            ft.installment_total,
            ft.created_at
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
        ORDER BY ft.due_date ASC, ft.created_at DESC, ft.id ASC
        """,
    ),
    "movements": (
        [
            "id",
            "direction",
            "movement_type",
            "movement_date",
            "amount",
            "status",
            "reconciliation_status",
            "financial_account_name",
            "participant_name",
            "source_type",
            "source_id",
            "financial_title_id",
            "settlement_id",
            "description",
            "created_at",
        ],
        f"""
        SELECT
            fm.id,
            fm.direction,
            fm.movement_type,
            fm.movement_date,
            fm.amount,
            fm.status,
            fm.reconciliation_status,
            fa.name AS financial_account_name,
            p.name AS participant_name,
            fm.source_type,
            fm.source_id,
            fm.financial_title_id,
            fm.settlement_id,
            fm.description,
            fm.created_at
        FROM financial_movements fm
        JOIN financial_accounts fa ON fa.id = fm.financial_account_id
        LEFT JOIN participants p ON p.id = fm.participant_id
        WHERE fm.company_id = :company_id
          AND fm.reversal_of_movement_id IS NULL
          AND fm.status = 'posted'
          AND fm.reconciliation_status <> 'reversed'
        ORDER BY fm.movement_date DESC, fm.created_at DESC, fm.id ASC
        """,
    ),
    "sales": (
        [
            "id",
            "sale_number_text",
            "participant_name",
            "status",
            "sale_type",
            "origin",
            "operation_nature",
            "fiscal_status",
            "issue_date",
            "operation_date",
            "competency_date",
            "subtotal_amount",
            "discount_amount",
            "freight_amount",
            "tax_amount",
            "total_amount",
            "receivable_total_amount",
            "invoice_total_amount",
            "closed_at",
            "paid_at",
            "created_at",
        ],
        f"""
        SELECT
            s.id,
            s.sale_number_text,
            p.name AS participant_name,
            s.status,
            s.sale_type,
            s.origin,
            s.operation_nature,
            s.fiscal_status,
            s.issue_date,
            s.operation_date,
            s.competency_date,
            s.subtotal_amount,
            s.discount_amount,
            s.freight_amount,
            s.tax_amount,
            s.total_amount,
            s.receivable_total_amount,
            s.invoice_total_amount,
            s.closed_at,
            s.paid_at,
            s.created_at
        FROM sales s
        LEFT JOIN participants p ON p.id = s.participant_id
        WHERE s.company_id = :company_id
          AND s.cancelled_at IS NULL
        ORDER BY s.operation_date DESC, s.created_at DESC, s.id ASC
        """,
    ),
    "purchases": (
        [
            "id",
            "participant_name",
            "status",
            "purchase_type",
            "origin",
            "fiscal_status",
            "issue_date",
            "operation_date",
            "competency_date",
            "subtotal_amount",
            "discount_amount",
            "freight_amount",
            "tax_amount",
            "total_amount",
            "payable_total_amount",
            "invoice_total_amount",
            "document_type",
            "document_number",
            "document_series",
            "confirmed_at",
            "created_at",
        ],
        """
        SELECT
            pu.id,
            p.name AS participant_name,
            pu.status,
            pu.purchase_type,
            pu.origin,
            pu.fiscal_status,
            pu.issue_date,
            pu.operation_date,
            pu.competency_date,
            pu.subtotal_amount,
            pu.discount_amount,
            pu.freight_amount,
            pu.tax_amount,
            pu.total_amount,
            pu.payable_total_amount,
            pu.invoice_total_amount,
            pu.document_type,
            pu.document_number,
            pu.document_series,
            pu.confirmed_at,
            pu.created_at
        FROM purchases pu
        LEFT JOIN participants p ON p.id = pu.participant_id
        WHERE pu.company_id = :company_id
          AND pu.cancelled_at IS NULL
        ORDER BY pu.operation_date DESC, pu.created_at DESC, pu.id ASC
        """,
    ),
    "reconciliation_matches": (
        [
            "id",
            "financial_account_name",
            "match_type",
            "status",
            "matched_amount",
            "line_amount",
            "movement_amount",
            "difference_amount",
            "tolerance_amount",
            "statement_line_id",
            "financial_movement_id",
            "confirmation_reason",
            "confirmed_at",
            "created_at",
        ],
        """
        SELECT
            rm.id,
            fa.name AS financial_account_name,
            rm.match_type,
            rm.status,
            rm.matched_amount,
            rm.line_amount,
            rm.movement_amount,
            rm.difference_amount,
            rm.tolerance_amount,
            rm.statement_line_id,
            rm.financial_movement_id,
            rm.confirmation_reason,
            rm.confirmed_at,
            rm.created_at
        FROM reconciliation_matches rm
        JOIN financial_accounts fa ON fa.id = rm.financial_account_id
        WHERE rm.company_id = :company_id
          AND rm.reversed_at IS NULL
        ORDER BY rm.confirmed_at DESC NULLS LAST, rm.created_at DESC, rm.id ASC
        """,
    ),
    "overdue_titles": (
        [
            "id",
            "direction",
            "title_reference",
            "participant_name",
            "status",
            "due_date",
            "net_amount",
            "paid_amount",
            "open_amount",
            "source_type",
            "source_id",
            "sale_id",
            "document_reference",
            "installment_number",
            "installment_total",
            "created_at",
        ],
        f"""
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            p.name AS participant_name,
            ft.status,
            ft.due_date,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            ft.document_reference,
            ft.installment_number,
            ft.installment_total,
            ft.created_at
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND ft.status IN {ACTIVE_TITLE_STATUS_SQL}
          AND ft.due_date < :today
        ORDER BY ft.due_date ASC, ft.open_amount DESC, ft.id ASC
        """,
    ),
    "titles_without_clear_origin": (
        [
            "id",
            "direction",
            "title_reference",
            "participant_name",
            "status",
            "due_date",
            "net_amount",
            "paid_amount",
            "open_amount",
            "source_type",
            "source_id",
            "sale_id",
            "document_reference",
            "installment_number",
            "installment_total",
            "created_at",
        ],
        """
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            p.name AS participant_name,
            ft.status,
            ft.due_date,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            ft.document_reference,
            ft.installment_number,
            ft.installment_total,
            ft.created_at
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND COALESCE(ft.source_type, '') = ''
          AND COALESCE(ft.source_id, '') = ''
          AND ft.sale_id IS NULL
          AND ft.document_reference IS NULL
        ORDER BY ft.created_at DESC, ft.id ASC
        """,
    ),
    "titles_without_participant": (
        [
            "id",
            "direction",
            "title_reference",
            "status",
            "due_date",
            "net_amount",
            "paid_amount",
            "open_amount",
            "source_type",
            "source_id",
            "sale_id",
            "document_reference",
            "installment_number",
            "installment_total",
            "created_at",
        ],
        """
        SELECT
            ft.id,
            ft.direction,
            COALESCE(NULLIF(ft.title_name, ''), ft.document_reference, ft.source_id, ft.id) AS title_reference,
            ft.status,
            ft.due_date,
            ft.net_amount,
            ft.paid_amount,
            ft.open_amount,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            ft.document_reference,
            ft.installment_number,
            ft.installment_total,
            ft.created_at
        FROM financial_titles ft
        WHERE ft.company_id = :company_id
          AND ft.cancelled_at IS NULL
          AND ft.deleted_at IS NULL
          AND ft.participant_id IS NULL
        ORDER BY ft.created_at DESC, ft.id ASC
        """,
    ),
    "unreconciled_movements": (
        [
            "id",
            "direction",
            "movement_type",
            "movement_date",
            "amount",
            "status",
            "reconciliation_status",
            "financial_account_name",
            "participant_name",
            "source_type",
            "source_id",
            "financial_title_id",
            "settlement_id",
            "description",
            "created_at",
        ],
        f"""
        SELECT
            fm.id,
            fm.direction,
            fm.movement_type,
            fm.movement_date,
            fm.amount,
            fm.status,
            fm.reconciliation_status,
            fa.name AS financial_account_name,
            p.name AS participant_name,
            fm.source_type,
            fm.source_id,
            fm.financial_title_id,
            fm.settlement_id,
            fm.description,
            fm.created_at
        FROM financial_movements fm
        JOIN financial_accounts fa ON fa.id = fm.financial_account_id
        LEFT JOIN participants p ON p.id = fm.participant_id
        WHERE fm.company_id = :company_id
          AND fm.reversal_of_movement_id IS NULL
          AND fm.status = 'posted'
          AND fm.reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
          AND fm.movement_date BETWEEN :start_date AND :end_date
        ORDER BY fm.movement_date DESC, fm.created_at DESC, fm.id ASC
        """,
    ),
    "unmatched_bank_statement_lines": (
        [
            "id",
            "statement_date",
            "financial_account_name",
            "direction",
            "amount",
            "status",
            "description",
            "document_number",
            "counterparty_name",
            "counterparty_document",
            "bank_reference",
            "external_id",
            "matched_amount",
            "created_at",
        ],
        f"""
        SELECT
            bsl.id,
            COALESCE(bsl.posted_at::date, bsl.line_date) AS statement_date,
            fa.name AS financial_account_name,
            bsl.direction,
            bsl.amount,
            bsl.status,
            bsl.description,
            bsl.document_number,
            bsl.counterparty_name,
            bsl.counterparty_document,
            bsl.bank_reference,
            bsl.external_id,
            bsl.matched_amount,
            bsl.created_at
        FROM bank_statement_lines bsl
        JOIN financial_accounts fa ON fa.id = bsl.financial_account_id
        WHERE bsl.company_id = :company_id
          AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
          AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date
        ORDER BY COALESCE(bsl.posted_at::date, bsl.line_date) DESC, bsl.created_at DESC, bsl.id ASC
        """,
    ),
}


def get_health_indicator_details(
    db: Session,
    company_id: str,
    indicator: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    normalized_indicator = indicator.strip()

    if normalized_indicator not in HEALTH_INDICATOR_QUERIES:
        raise ValueError("Indicador de saúde do Kovir inválido.")

    columns, sql = HEALTH_INDICATOR_QUERIES[normalized_indicator]
    rows = _rows(
        db,
        sql,
        {
            "company_id": company_id,
            "start_date": start,
            "end_date": end,
            "today": today_in_brazil(),
        },
    )
    money_fields = [field for field in HEALTH_INDICATOR_MONEY_FIELDS if field in columns]

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "reference_date": today_in_brazil().isoformat(),
        "indicator": normalized_indicator,
        "label": HEALTH_INDICATOR_LABELS[normalized_indicator],
        "total": len(rows),
        "columns": columns,
        "rows": [
            _normalize_money_fields(row, money_fields)
            for row in rows
        ],
    }


def get_preparatory_fiscal_documents(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 20,
    export_all: bool = False,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    limit = max(1, min(limit, 100))
    page_limit = FISCAL_REPORT_EXPORT_LIMIT if export_all else limit

    sales_pending_where = f"""
        s.company_id = :company_id
        AND s.cancelled_at IS NULL
        AND s.status IN ('closed', 'paid')
        AND (
            COALESCE(s.fiscal_status, 'pending_classification') IN {PENDING_SALE_FISCAL_STATUS_SQL}
            OR (
                COALESCE(s.fiscal_status, 'pending_classification') = 'fiscal_ready'
                AND s.issue_date IS NULL
            )
        )
        AND s.operation_date::date BETWEEN :start_date AND :end_date
    """

    purchase_pending_where = f"""
        p.company_id = :company_id
        AND p.cancelled_at IS NULL
        AND p.deleted_at IS NULL
        AND COALESCE(p.fiscal_status, 'pending_document') <> 'not_required'
        AND (
            p.issue_date IS NULL
            OR COALESCE(p.document_number, '') = ''
            OR COALESCE(p.fiscal_status, 'pending_document') IN {PENDING_PURCHASE_FISCAL_STATUS_SQL}
        )
        AND p.operation_date::date BETWEEN :start_date AND :end_date
    """

    title_base_where = """
        ft.company_id = :company_id
        AND ft.cancelled_at IS NULL
        AND ft.deleted_at IS NULL
        AND ft.due_date BETWEEN :start_date AND :end_date
    """

    title_pending_where = f"""
        {title_base_where}
        AND COALESCE(ft.fiscal_status, 'pending_document') IN {PENDING_TITLE_FISCAL_STATUS_SQL}
    """

    fiscal_document_where = """
        fd.company_id = :company_id
        AND fd.created_at::date BETWEEN :start_date AND :end_date
    """

    params = {
        "company_id": company_id,
        "start_date": start,
        "end_date": end,
        "limit": page_limit,
    }

    sales_summary = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS pending_sales_documents,
            COALESCE(SUM(s.total_amount), 0) AS pending_sales_amount
        FROM sales s
        WHERE {sales_pending_where}
        """,
        params,
    ) or {"pending_sales_documents": 0, "pending_sales_amount": 0}

    sales_documents = _rows(
        db,
        f"""
        SELECT
            s.id AS sale_id,
            s.sale_number_text,
            s.status,
            s.sale_type,
            s.operation_nature,
            s.fiscal_status,
            s.issue_date,
            s.operation_date::date AS operation_date,
            p.name AS participant_name,
            s.total_amount,
            (
                s.issue_date IS NULL
                AND COALESCE(s.fiscal_status, 'pending_classification') <> 'document_generated'
            ) AS missing_issue_date,
            (COALESCE(s.fiscal_status, 'pending_classification') IN {PENDING_SALE_FISCAL_STATUS_SQL}) AS pending_fiscal_status,
            (COALESCE(s.fiscal_status, '') = 'blocked') AS blocked_fiscal_status,
            (COALESCE(s.fiscal_status, '') = 'document_cancelled') AS cancelled_fiscal_document_status
        FROM sales s
        LEFT JOIN participants p ON p.id = s.participant_id
        WHERE {sales_pending_where}
        ORDER BY s.operation_date DESC, s.id ASC
        LIMIT :limit
        """,
        params,
    )

    purchase_summary = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS pending_purchase_documents,
            COALESCE(SUM(p.total_amount), 0) AS pending_purchase_amount
        FROM purchases p
        WHERE {purchase_pending_where}
        """,
        params,
    ) or {"pending_purchase_documents": 0, "pending_purchase_amount": 0}

    purchase_documents = _rows(
        db,
        f"""
        SELECT
            p.id AS purchase_id,
            p.status,
            p.purchase_type,
            p.fiscal_status,
            p.issue_date,
            p.operation_date::date AS operation_date,
            pt.name AS participant_name,
            p.total_amount,
            p.document_type,
            p.document_number,
            p.document_series,
            p.access_key,
            (p.issue_date IS NULL) AS missing_issue_date,
            (COALESCE(p.document_number, '') = '') AS missing_document_number,
            (COALESCE(p.fiscal_status, 'pending_document') IN {PENDING_PURCHASE_FISCAL_STATUS_SQL}) AS pending_fiscal_status,
            (COALESCE(p.fiscal_status, '') = 'divergent') AS divergent_fiscal_status
        FROM purchases p
        LEFT JOIN participants pt ON pt.id = p.participant_id
        WHERE {purchase_pending_where}
        ORDER BY p.operation_date DESC, p.id ASC
        LIMIT :limit
        """,
        params,
    )

    title_fiscal_status = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS total_titles,
            COUNT(CASE WHEN COALESCE(ft.fiscal_status, 'pending_document') IN {PENDING_TITLE_FISCAL_STATUS_SQL} THEN 1 END) AS pending_fiscal_titles,
            COALESCE(SUM(CASE WHEN COALESCE(ft.fiscal_status, 'pending_document') IN {PENDING_TITLE_FISCAL_STATUS_SQL} THEN ft.open_amount ELSE 0 END), 0) AS pending_fiscal_open_amount,
            COALESCE(SUM(CASE WHEN COALESCE(ft.fiscal_status, 'pending_document') IN {PENDING_TITLE_FISCAL_STATUS_SQL} THEN ft.net_amount ELSE 0 END), 0) AS pending_fiscal_net_amount
        FROM financial_titles ft
        WHERE {title_base_where}
        """,
        params,
    ) or {"total_titles": 0, "pending_fiscal_titles": 0, "pending_fiscal_open_amount": 0, "pending_fiscal_net_amount": 0}

    title_documents = _rows(
        db,
        f"""
        SELECT
            ft.id,
            ft.direction,
            ft.title_type,
            ft.status,
            ft.fiscal_status,
            ft.issue_date,
            ft.due_date,
            ft.document_reference,
            ft.source_type,
            ft.source_id,
            ft.sale_id,
            s.sale_number_text,
            p.name AS participant_name,
            p.document AS participant_document,
            ft.net_amount,
            ft.open_amount,
            ft.installment_number,
            ft.installment_total
        FROM financial_titles ft
        LEFT JOIN participants p ON p.id = ft.participant_id
        LEFT JOIN sales s ON s.id = ft.sale_id
        WHERE {title_pending_where}
        ORDER BY ft.due_date ASC, ft.id ASC
        LIMIT :limit
        """,
        params,
    )

    fiscal_document_summary = _one(
        db,
        f"""
        SELECT
            COUNT(*) AS fiscal_documents_total,
            COUNT(CASE WHEN fd.status IN {AUTHORIZED_FISCAL_DOCUMENT_STATUS_SQL} THEN 1 END) AS fiscal_documents_authorized,
            COUNT(CASE WHEN fd.status IN {PENDING_FISCAL_DOCUMENT_STATUS_SQL} THEN 1 END) AS fiscal_documents_pending,
            COUNT(CASE WHEN fd.status IN {ERROR_FISCAL_DOCUMENT_STATUS_SQL} THEN 1 END) AS fiscal_documents_error,
            COUNT(CASE WHEN fd.status = 'cancelled' THEN 1 END) AS fiscal_documents_cancelled
        FROM fiscal_documents fd
        WHERE {fiscal_document_where}
        """,
        params,
    ) or {
        "fiscal_documents_total": 0,
        "fiscal_documents_authorized": 0,
        "fiscal_documents_pending": 0,
        "fiscal_documents_error": 0,
        "fiscal_documents_cancelled": 0,
    }

    fiscal_documents = _rows(
        db,
        f"""
        SELECT
            fd.id,
            fd.sale_id,
            s.sale_number_text,
            p.name AS participant_name,
            s.total_amount AS sale_total_amount,
            fd.document_type,
            fd.model,
            fd.serie,
            fd.number,
            fd.reference,
            fd.status,
            fd.focus_status,
            fd.access_key,
            fd.protocol,
            fd.error_code,
            fd.error_message,
            fd.danfe_url,
            fd.xml_url,
            fd.issued_at,
            fd.authorized_at,
            fd.cancelled_at,
            fd.created_at,
            fd.updated_at
        FROM fiscal_documents fd
        LEFT JOIN sales s ON s.id = fd.sale_id
        LEFT JOIN participants p ON p.id = s.participant_id
        WHERE {fiscal_document_where}
        ORDER BY fd.created_at DESC, fd.id ASC
        LIMIT :limit
        """,
        params,
    )

    sales_documents = [_normalize_money_fields(row, ["total_amount"]) for row in sales_documents]
    purchase_documents = [_normalize_money_fields(row, ["total_amount"]) for row in purchase_documents]
    title_documents = [_normalize_money_fields(row, ["net_amount", "open_amount"]) for row in title_documents]
    fiscal_documents = [_normalize_money_fields(row, ["sale_total_amount"]) for row in fiscal_documents]

    pending_sales = _int(sales_summary.get("pending_sales_documents"))
    pending_purchases = _int(purchase_summary.get("pending_purchase_documents"))
    pending_titles = _int(title_fiscal_status.get("pending_fiscal_titles"))
    fiscal_docs_pending = _int(fiscal_document_summary.get("fiscal_documents_pending"))
    fiscal_docs_error = _int(fiscal_document_summary.get("fiscal_documents_error"))
    blocking_items = pending_sales + pending_purchases + pending_titles + fiscal_docs_error
    attention_items = blocking_items + fiscal_docs_pending
    report_status = "READY" if attention_items == 0 else ("BLOCKED" if blocking_items > 0 else "ATTENTION")

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "limit": page_limit,
        "export_all": export_all,
        "summary": {
            "pending_sales_documents": pending_sales,
            "pending_purchase_documents": pending_purchases,
            "pending_fiscal_titles": pending_titles,
            "pending_sales_amount": _money(sales_summary.get("pending_sales_amount")),
            "pending_purchase_amount": _money(purchase_summary.get("pending_purchase_amount")),
            "pending_fiscal_open_amount": _money(title_fiscal_status.get("pending_fiscal_open_amount")),
            "fiscal_documents_total": _int(fiscal_document_summary.get("fiscal_documents_total")),
            "fiscal_documents_authorized": _int(fiscal_document_summary.get("fiscal_documents_authorized")),
            "fiscal_documents_pending": fiscal_docs_pending,
            "fiscal_documents_error": fiscal_docs_error,
            "fiscal_documents_cancelled": _int(fiscal_document_summary.get("fiscal_documents_cancelled")),
            "blocking_items": blocking_items,
            "status": report_status,
        },
        "sales_documents": sales_documents,
        "purchase_documents": purchase_documents,
        "title_documents": title_documents,
        "fiscal_documents": fiscal_documents,
        "title_fiscal_status": {
            "total_titles": _int(title_fiscal_status.get("total_titles")),
            "pending_fiscal_titles": pending_titles,
            "pending_fiscal_open_amount": _money(title_fiscal_status.get("pending_fiscal_open_amount")),
            "pending_fiscal_net_amount": _money(title_fiscal_status.get("pending_fiscal_net_amount")),
        },
        "returned_rows": {
            "sales_documents": len(sales_documents),
            "purchase_documents": len(purchase_documents),
            "title_documents": len(title_documents),
            "fiscal_documents": len(fiscal_documents),
        },
        "required_fields_by_flow": {
            "sales": ["sale_id", "sale_number_text", "operation_date", "participant_name", "total_amount", "fiscal_status", "issue_date"],
            "purchases": [
                "purchase_id",
                "operation_date",
                "participant_name",
                "total_amount",
                "document_type",
                "document_number",
                "document_series",
                "access_key",
                "fiscal_status",
                "issue_date",
            ],
            "titles": ["id", "direction", "participant_name", "document_reference", "fiscal_status", "due_date", "open_amount"],
            "fiscal_documents": ["id", "sale_id", "document_type", "status", "reference", "access_key", "protocol"],
        },
        "notes": [
            "Este endpoint não emite documento fiscal; ele lê pendências preparatórias e documentos fiscais já registrados.",
            "Vendas em orçamento não entram como pendência fiscal operacional da v1.0; apenas pedidos fechados/pagos são avaliados.",
            "Compra sem documento só é pendência quando o vínculo fiscal não está marcado como não exigido.",
            "Título financeiro não é documento fiscal nem dinheiro; o status fiscal do título é apenas sinalização de vínculo documental.",
        ],
    }


def get_financial_close_mvp(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    today = today_in_brazil()
    generated_at = datetime.now(timezone.utc).isoformat()
    fiscal_precheck = get_preparatory_fiscal_documents(
        db,
        company_id=company_id,
        start_date=start,
        end_date=end,
        limit=20,
    )

    titles_snapshot = _one(
        db,
        f"""
        SELECT
            COUNT(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS open_receivable_count,
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS open_receivable_amount,
            COUNT(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS open_payable_count,
            COALESCE(SUM(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS open_payable_amount,
            COUNT(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN 1 END) AS overdue_count,
            COALESCE(SUM(CASE WHEN status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN open_amount ELSE 0 END), 0) AS overdue_amount
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
          AND due_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end, "today": today},
    ) or {}

    movement_snapshot = _one(
        db,
        f"""
        SELECT
            COUNT(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN 1 END) AS unreconciled_movements,
            COALESCE(SUM(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN amount ELSE 0 END), 0) AS unreconciled_amount,
            COUNT(CASE WHEN reconciliation_status = 'divergent' THEN 1 END) AS divergent_movements
        FROM financial_movements
        WHERE company_id = :company_id
          AND reversal_of_movement_id IS NULL
          AND status = 'posted'
          AND reconciliation_status <> 'reversed'
          AND movement_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    statement_snapshot = _one(
        db,
        f"""
        SELECT
            COUNT(CASE WHEN status IN {PENDING_STATEMENT_STATUS_SQL} THEN 1 END) AS pending_statement_lines,
            COUNT(CASE WHEN status = 'divergent' THEN 1 END) AS divergent_statement_lines
        FROM bank_statement_lines
        WHERE company_id = :company_id
          AND COALESCE(posted_at::date, line_date) BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    duplicate_balances = _one(
        db,
        """
        SELECT COUNT(*) AS duplicate_rows
        FROM (
            SELECT company_id, financial_account_id, COUNT(*) AS total
            FROM financial_account_balances
            WHERE company_id = :company_id
            GROUP BY company_id, financial_account_id
            HAVING COUNT(*) > 1
        ) duplicates
        """,
        {"company_id": company_id},
    ) or {"duplicate_rows": 0}

    fiscal_summary = fiscal_precheck.get("summary", {})
    fiscal_preparatory_pending = (
        _int(fiscal_summary.get("pending_sales_documents"))
        + _int(fiscal_summary.get("pending_purchase_documents"))
        + _int(fiscal_summary.get("pending_fiscal_titles"))
    )
    fiscal_documents_pending = _int(fiscal_summary.get("fiscal_documents_pending"))
    fiscal_documents_error = _int(fiscal_summary.get("fiscal_documents_error"))
    fiscal_attention_items = fiscal_preparatory_pending + fiscal_documents_pending
    unreconciled_movements = _int(movement_snapshot.get("unreconciled_movements"))
    pending_statement_lines = _int(statement_snapshot.get("pending_statement_lines"))
    divergent_count = _int(movement_snapshot.get("divergent_movements")) + _int(statement_snapshot.get("divergent_statement_lines"))
    duplicate_rows = _int(duplicate_balances.get("duplicate_rows"))
    overdue_count = _int(titles_snapshot.get("overdue_count"))
    overdue_amount = _money(titles_snapshot.get("overdue_amount"))
    unreconciled_amount = _money(movement_snapshot.get("unreconciled_amount"))

    checklist: list[dict[str, Any]] = [
        {
            "code": "fiscal_errors",
            "label": "Documentos fiscais sem erro de emissao",
            "status": "PASS" if fiscal_documents_error == 0 else "FAIL",
            "blocking": True,
            "evidence": {"fiscal_documents_error": fiscal_documents_error},
        },
        {
            "code": "fiscal_precheck",
            "label": "Pendencias fiscais preparatorias saneadas",
            "status": "PASS" if fiscal_attention_items == 0 else "WARN",
            "blocking": False,
            "evidence": {
                "pending_items": fiscal_attention_items,
                "pending_sales_documents": _int(fiscal_summary.get("pending_sales_documents")),
                "pending_purchase_documents": _int(fiscal_summary.get("pending_purchase_documents")),
                "pending_fiscal_titles": _int(fiscal_summary.get("pending_fiscal_titles")),
                "fiscal_documents_pending": fiscal_documents_pending,
                "pending_fiscal_open_amount": _money(fiscal_summary.get("pending_fiscal_open_amount")),
            },
        },
        {
            "code": "reconciliation_clean",
            "label": "Conciliacao e extrato sem pendencias criticas",
            "status": "PASS" if unreconciled_movements == 0 and pending_statement_lines == 0 and divergent_count == 0 else "FAIL",
            "blocking": True,
            "evidence": {
                "unreconciled_movements": unreconciled_movements,
                "unreconciled_amount": unreconciled_amount,
                "pending_statement_lines": pending_statement_lines,
                "divergent_items": divergent_count,
            },
        },
        {
            "code": "balances_consistency",
            "label": "Saldos internos sem duplicidade estrutural",
            "status": "PASS" if duplicate_rows == 0 else "FAIL",
            "blocking": True,
            "evidence": {"duplicate_balance_rows": duplicate_rows},
        },
        {
            "code": "overdue_review",
            "label": "Titulos vencidos revisados",
            "status": "PASS" if overdue_count == 0 else "WARN",
            "blocking": False,
            "evidence": {
                "overdue_count": overdue_count,
                "overdue_amount": overdue_amount,
            },
        },
    ]

    blocking_failures = [item for item in checklist if item["blocking"] and item["status"] == "FAIL"]
    warning_items = [item for item in checklist if item["status"] == "WARN"]
    can_close_with_warnings = len(blocking_failures) == 0

    if blocking_failures:
        close_status = "BLOCKED"
        can_close_mvp = False
    elif warning_items:
        close_status = "ATTENTION"
        can_close_mvp = False
    else:
        close_status = "READY"
        can_close_mvp = True

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "generated_at": generated_at,
        "reference_date": today.isoformat(),
        "close_status": close_status,
        "can_close_mvp": can_close_mvp,
        "can_close_with_warnings": can_close_with_warnings,
        "snapshot": {
            "open_receivable_count": _int(titles_snapshot.get("open_receivable_count")),
            "open_receivable_amount": _money(titles_snapshot.get("open_receivable_amount")),
            "open_payable_count": _int(titles_snapshot.get("open_payable_count")),
            "open_payable_amount": _money(titles_snapshot.get("open_payable_amount")),
            "overdue_count": overdue_count,
            "overdue_amount": overdue_amount,
            "unreconciled_movements": unreconciled_movements,
            "unreconciled_amount": unreconciled_amount,
            "pending_statement_lines": pending_statement_lines,
            "divergent_items": divergent_count,
            "duplicate_balance_rows": duplicate_rows,
            "fiscal_preparatory_pending": fiscal_preparatory_pending,
            "fiscal_documents_pending": fiscal_documents_pending,
            "fiscal_documents_error": fiscal_documents_error,
        },
        "checklist": checklist,
        "blocking_issues": [
            item["label"] for item in checklist if item["blocking"] and item["status"] == "FAIL"
        ],
        "recommended_actions": _financial_close_recommended_actions(
            fiscal_documents_error=fiscal_documents_error,
            fiscal_attention_items=fiscal_attention_items,
            unreconciled_movements=unreconciled_movements,
            pending_statement_lines=pending_statement_lines,
            divergent_count=divergent_count,
            duplicate_rows=duplicate_rows,
            overdue_count=overdue_count,
        ),
        "notes": [
            "Fechamento financeiro e leitura de prontidao, nao lancamento contabil definitivo.",
            "READY exige ausencia de bloqueios e alertas no periodo.",
            "ATTENTION indica que nao ha bloqueio estrutural, mas ainda existem pendencias operacionais.",
            "BLOCKED indica inconsistencia que deve ser corrigida antes de confiar no fechamento.",
        ],
    }


def _financial_close_recommended_actions(
    *,
    fiscal_documents_error: int,
    fiscal_attention_items: int,
    unreconciled_movements: int,
    pending_statement_lines: int,
    divergent_count: int,
    duplicate_rows: int,
    overdue_count: int,
) -> list[str]:
    actions: list[str] = []
    if fiscal_documents_error:
        actions.append("Corrigir documentos fiscais com erro antes de considerar o fechamento confiavel.")
    if unreconciled_movements or pending_statement_lines or divergent_count:
        actions.append("Resolver pendencias de conciliacao e extrato antes do fechamento.")
    if duplicate_rows:
        actions.append("Remover duplicidades estruturais de saldo interno.")
    if fiscal_attention_items:
        actions.append("Sanear pendencias fiscais preparatorias ou registrar justificativa operacional.")
    if overdue_count:
        actions.append("Revisar titulos vencidos, registrar baixa, renegociacao ou justificativa.")
    if not actions:
        actions.append("Nenhuma acao operacional pendente para o periodo selecionado.")
    return actions


def get_accountant_pack(
    db: Session,
    company_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    *,
    include_details: bool = False,
    limit: int = 100,
    export_all: bool = False,
) -> dict[str, Any]:
    company = _get_company_or_raise(db, company_id)
    start, end = _default_period(start_date, end_date)
    today = today_in_brazil()
    page_limit = ACCOUNTANT_EXPORT_LIMIT if export_all else max(1, min(limit, 500))

    titles = _one(
        db,
        f"""
        SELECT
            COUNT(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS receivable_open_count,
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS receivable_open_amount,
            COUNT(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN 1 END) AS receivable_overdue_count,
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN open_amount ELSE 0 END), 0) AS receivable_overdue_amount,
            COUNT(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN 1 END) AS payable_open_count,
            COALESCE(SUM(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS payable_open_amount,
            COUNT(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN 1 END) AS payable_overdue_count,
            COALESCE(SUM(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} AND due_date < :today THEN open_amount ELSE 0 END), 0) AS payable_overdue_amount
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
        """,
        {"company_id": company_id, "today": today},
    ) or {}

    projected_flow = _one(
        db,
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN direction = 'receivable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS projected_inflow_amount,
            COALESCE(SUM(CASE WHEN direction = 'payable' AND status IN {ACTIVE_TITLE_STATUS_SQL} THEN open_amount ELSE 0 END), 0) AS projected_outflow_amount
        FROM financial_titles
        WHERE company_id = :company_id
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
          AND due_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    realized_flow = _one(
        db,
        """
        SELECT
            COALESCE(SUM(CASE WHEN direction = 'inflow' THEN movement_amount ELSE 0 END), 0) AS realized_inflow_amount,
            COALESCE(SUM(CASE WHEN direction = 'outflow' THEN movement_amount ELSE 0 END), 0) AS realized_outflow_amount
        FROM settlements
        WHERE company_id = :company_id
          AND reversed_at IS NULL
          AND status = 'active'
          AND settlement_date BETWEEN :start_date AND :end_date
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    balances = _rows(
        db,
        """
        SELECT
            fa.id AS financial_account_id,
            fa.name AS financial_account_name,
            fa.account_type,
            fa.currency,
            fab.current_balance_amount AS balance_amount
        FROM financial_account_balances fab
        JOIN financial_accounts fa ON fa.id = fab.financial_account_id
        WHERE fab.company_id = :company_id
          AND fa.deleted_at IS NULL
        ORDER BY fa.name
        """,
        {"company_id": company_id},
    )

    movements_by_period = _rows(
        db,
        f"""
        SELECT
            direction,
            COUNT(*) AS total_movements,
            COALESCE(SUM(amount), 0) AS amount,
            COALESCE(SUM(CASE WHEN reconciliation_status IN {RECONCILED_MOVEMENT_STATUS_SQL} THEN amount ELSE 0 END), 0) AS reconciled_amount,
            COALESCE(SUM(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN amount ELSE 0 END), 0) AS unreconciled_amount,
            COUNT(CASE WHEN reconciliation_status IN {RECONCILED_MOVEMENT_STATUS_SQL} THEN 1 END) AS reconciled_movements,
            COUNT(CASE WHEN reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL} THEN 1 END) AS unreconciled_movements
        FROM financial_movements
        WHERE company_id = :company_id
          AND reversal_of_movement_id IS NULL
          AND status = 'posted'
          AND reconciliation_status <> 'reversed'
          AND movement_date BETWEEN :start_date AND :end_date
        GROUP BY direction
        ORDER BY direction
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    sales_by_period = _rows(
        db,
        """
        SELECT
            sale_type,
            COUNT(*) AS total_sales,
            COALESCE(SUM(total_amount), 0) AS total_amount,
            COALESCE(SUM(receivable_total_amount), 0) AS receivable_total_amount,
            COALESCE(SUM(invoice_total_amount), 0) AS invoice_total_amount
        FROM sales
        WHERE company_id = :company_id
          AND status IN ('closed', 'paid')
          AND cancelled_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        GROUP BY sale_type
        ORDER BY sale_type
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    purchases_by_period = _rows(
        db,
        """
        SELECT
            purchase_type,
            COUNT(*) AS total_purchases,
            COALESCE(SUM(total_amount), 0) AS total_amount,
            COALESCE(SUM(payable_total_amount), 0) AS payable_total_amount,
            COALESCE(SUM(invoice_total_amount), 0) AS invoice_total_amount
        FROM purchases
        WHERE company_id = :company_id
          AND status = 'confirmed'
          AND cancelled_at IS NULL
          AND deleted_at IS NULL
          AND operation_date::date BETWEEN :start_date AND :end_date
        GROUP BY purchase_type
        ORDER BY purchase_type
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    )

    ignored_operational = _one(
        db,
        """
        SELECT
            (SELECT COUNT(*) FROM sales s
             WHERE s.company_id = :company_id
               AND s.status = 'quote'
               AND s.cancelled_at IS NULL
               AND s.operation_date::date BETWEEN :start_date AND :end_date) AS sale_quotes_ignored_count,
            (SELECT COALESCE(SUM(s.total_amount), 0) FROM sales s
             WHERE s.company_id = :company_id
               AND s.status = 'quote'
               AND s.cancelled_at IS NULL
               AND s.operation_date::date BETWEEN :start_date AND :end_date) AS sale_quotes_ignored_amount,
            (SELECT COUNT(*) FROM purchases p
             WHERE p.company_id = :company_id
               AND p.status = 'draft'
               AND p.cancelled_at IS NULL
               AND p.deleted_at IS NULL
               AND p.operation_date::date BETWEEN :start_date AND :end_date) AS purchase_drafts_ignored_count,
            (SELECT COALESCE(SUM(p.total_amount), 0) FROM purchases p
             WHERE p.company_id = :company_id
               AND p.status = 'draft'
               AND p.cancelled_at IS NULL
               AND p.deleted_at IS NULL
               AND p.operation_date::date BETWEEN :start_date AND :end_date) AS purchase_drafts_ignored_amount
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    settlement_consistency = _one(
        db,
        """
        WITH settlement_base AS (
            SELECT id, movement_amount
            FROM settlements
            WHERE company_id = :company_id
              AND status = 'active'
              AND reversed_at IS NULL
              AND settlement_date BETWEEN :start_date AND :end_date
        ), movement_base AS (
            SELECT settlement_id, COUNT(*) AS movement_count, COALESCE(SUM(amount), 0) AS movement_amount
            FROM financial_movements
            WHERE company_id = :company_id
              AND status = 'posted'
              AND reversal_of_movement_id IS NULL
              AND settlement_id IS NOT NULL
              AND movement_date BETWEEN :start_date AND :end_date
            GROUP BY settlement_id
        )
        SELECT
            COUNT(sb.id) AS active_settlements,
            COALESCE(SUM(sb.movement_amount), 0) AS settlement_movement_amount,
            COALESCE(SUM(COALESCE(mb.movement_amount, 0)), 0) AS posted_movement_amount,
            COUNT(CASE WHEN mb.settlement_id IS NULL THEN 1 END) AS settlements_without_movement_count,
            COALESCE(SUM(CASE WHEN mb.settlement_id IS NULL THEN sb.movement_amount ELSE 0 END), 0) AS settlements_without_movement_amount,
            COALESCE(SUM(CASE WHEN COALESCE(mb.movement_count, 0) > 1 THEN 1 ELSE 0 END), 0) AS settlements_with_multiple_movements
        FROM settlement_base sb
        LEFT JOIN movement_base mb ON mb.settlement_id = sb.id
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {}

    reconciliation_pendencies = _one(
        db,
        f"""
        SELECT
            (SELECT COUNT(*)
             FROM financial_movements fm
             WHERE fm.company_id = :company_id
               AND fm.reversal_of_movement_id IS NULL
               AND fm.status = 'posted'
               AND fm.reconciliation_status IN {PENDING_RECONCILIATION_STATUS_SQL}
               AND fm.movement_date BETWEEN :start_date AND :end_date) AS unreconciled_movements,
            (SELECT COUNT(*)
             FROM bank_statement_lines bsl
             WHERE bsl.company_id = :company_id
               AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
               AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date) AS unmatched_statement_lines
        """,
        {"company_id": company_id, "start_date": start, "end_date": end},
    ) or {"unreconciled_movements": 0, "unmatched_statement_lines": 0}

    fiscal_report = get_preparatory_fiscal_documents(
        db,
        company_id=company_id,
        start_date=start,
        end_date=end,
        limit=page_limit if include_details else 20,
        export_all=export_all if include_details else False,
    )
    fiscal_summary = fiscal_report.get("summary", {})

    detail_params = {
        "company_id": company_id,
        "start_date": start,
        "end_date": end,
        "today": today,
        "limit": page_limit,
    }
    open_title_details: list[dict[str, Any]] = []
    period_title_details: list[dict[str, Any]] = []
    settlement_details: list[dict[str, Any]] = []
    movement_details: list[dict[str, Any]] = []
    statement_line_details: list[dict[str, Any]] = []
    sales_details: list[dict[str, Any]] = []
    purchase_details: list[dict[str, Any]] = []
    ignored_sale_details: list[dict[str, Any]] = []
    ignored_purchase_details: list[dict[str, Any]] = []

    if include_details:
        open_title_details = _rows(
            db,
            f"""
            SELECT
                ft.id,
                ft.direction,
                ft.title_type,
                ft.status,
                ft.collection_status,
                ft.fiscal_status,
                ft.document_reference,
                ft.source_type,
                ft.source_id,
                ft.sale_id,
                s.sale_number_text,
                p.name AS participant_name,
                p.document AS participant_document,
                ft.payment_method_name,
                fa.name AS financial_account_name,
                ft.issue_date,
                ft.competency_date,
                ft.due_date,
                ft.expected_payment_date,
                ft.installment_number,
                ft.installment_total,
                ft.gross_amount,
                ft.net_amount,
                ft.paid_amount,
                ft.open_amount
            FROM financial_titles ft
            LEFT JOIN participants p ON p.id = ft.participant_id
            LEFT JOIN sales s ON s.id = ft.sale_id
            LEFT JOIN financial_accounts fa ON fa.id = ft.expected_financial_account_id
            WHERE ft.company_id = :company_id
              AND ft.status IN {ACTIVE_TITLE_STATUS_SQL}
              AND ft.cancelled_at IS NULL
              AND ft.deleted_at IS NULL
            ORDER BY ft.due_date ASC, ft.direction ASC, ft.open_amount DESC, ft.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        period_title_details = _rows(
            db,
            """
            SELECT
                ft.id,
                ft.direction,
                ft.title_type,
                ft.status,
                ft.collection_status,
                ft.fiscal_status,
                ft.document_reference,
                ft.source_type,
                ft.source_id,
                ft.sale_id,
                s.sale_number_text,
                p.name AS participant_name,
                p.document AS participant_document,
                ft.payment_method_name,
                fa.name AS financial_account_name,
                ft.issue_date,
                ft.competency_date,
                ft.due_date,
                ft.expected_payment_date,
                ft.installment_number,
                ft.installment_total,
                ft.gross_amount,
                ft.net_amount,
                ft.paid_amount,
                ft.open_amount
            FROM financial_titles ft
            LEFT JOIN participants p ON p.id = ft.participant_id
            LEFT JOIN sales s ON s.id = ft.sale_id
            LEFT JOIN financial_accounts fa ON fa.id = ft.expected_financial_account_id
            WHERE ft.company_id = :company_id
              AND ft.due_date BETWEEN :start_date AND :end_date
              AND ft.cancelled_at IS NULL
              AND ft.deleted_at IS NULL
            ORDER BY ft.due_date ASC, ft.direction ASC, ft.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        settlement_details = _rows(
            db,
            """
            WITH movement_by_settlement AS (
                SELECT settlement_id, COUNT(*) AS movement_count, COALESCE(SUM(amount), 0) AS movement_amount
                FROM financial_movements
                WHERE company_id = :company_id
                  AND status = 'posted'
                  AND reversal_of_movement_id IS NULL
                  AND settlement_id IS NOT NULL
                GROUP BY settlement_id
            )
            SELECT
                st.id,
                st.direction,
                st.settlement_type,
                st.status,
                st.settlement_date,
                st.competency_date,
                st.financial_title_id,
                ft.document_reference AS title_reference,
                p.name AS participant_name,
                fa.name AS financial_account_name,
                pm.name AS payment_method_name,
                st.received_amount,
                st.discount_amount,
                st.interest_amount,
                st.penalty_amount,
                st.fee_amount,
                st.title_settled_amount,
                st.movement_amount,
                COALESCE(mbs.movement_count, 0) AS linked_movement_count,
                COALESCE(mbs.movement_amount, 0) AS linked_movement_amount,
                st.evidence_reference,
                st.source_type,
                st.source_id
            FROM settlements st
            JOIN financial_titles ft ON ft.id = st.financial_title_id
            LEFT JOIN participants p ON p.id = st.participant_id
            LEFT JOIN financial_accounts fa ON fa.id = st.financial_account_id
            LEFT JOIN payment_methods pm ON pm.id = st.payment_method_id
            LEFT JOIN movement_by_settlement mbs ON mbs.settlement_id = st.id
            WHERE st.company_id = :company_id
              AND st.status = 'active'
              AND st.reversed_at IS NULL
              AND st.settlement_date BETWEEN :start_date AND :end_date
            ORDER BY st.settlement_date ASC, st.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        movement_details = _rows(
            db,
            """
            SELECT
                fm.id,
                fm.direction,
                fm.movement_type,
                fm.movement_date,
                fm.amount,
                fm.currency,
                fm.status,
                fm.reconciliation_status,
                fa.name AS financial_account_name,
                fm.settlement_id,
                fm.financial_title_id,
                ft.document_reference AS title_reference,
                p.name AS participant_name,
                fm.source_type,
                fm.source_id,
                fm.description
            FROM financial_movements fm
            JOIN financial_accounts fa ON fa.id = fm.financial_account_id
            LEFT JOIN financial_titles ft ON ft.id = fm.financial_title_id
            LEFT JOIN participants p ON p.id = fm.participant_id
            WHERE fm.company_id = :company_id
              AND fm.status = 'posted'
              AND fm.reversal_of_movement_id IS NULL
              AND fm.reconciliation_status <> 'reversed'
              AND fm.movement_date BETWEEN :start_date AND :end_date
            ORDER BY fm.movement_date ASC, fm.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        statement_line_details = _rows(
            db,
            f"""
            SELECT
                bsl.id,
                fa.name AS financial_account_name,
                bsl.statement_import_id,
                bsl.external_id,
                bsl.line_date,
                bsl.posted_at,
                bsl.direction,
                bsl.amount,
                bsl.description,
                bsl.document_number,
                bsl.counterparty_name,
                bsl.counterparty_document,
                bsl.bank_reference,
                bsl.status,
                bsl.match_confidence,
                bsl.matched_amount
            FROM bank_statement_lines bsl
            JOIN financial_accounts fa ON fa.id = bsl.financial_account_id
            WHERE bsl.company_id = :company_id
              AND bsl.status IN {PENDING_STATEMENT_STATUS_SQL}
              AND COALESCE(bsl.posted_at::date, bsl.line_date) BETWEEN :start_date AND :end_date
            ORDER BY COALESCE(bsl.posted_at::date, bsl.line_date) ASC, bsl.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        sales_details = _rows(
            db,
            """
            SELECT
                s.id,
                s.sale_number_text,
                s.status,
                s.sale_type,
                s.origin,
                s.operation_nature,
                s.fiscal_status,
                s.issue_date,
                s.operation_date,
                s.competency_date,
                p.name AS participant_name,
                p.document AS participant_document,
                s.subtotal_amount,
                s.discount_amount,
                s.freight_amount,
                s.tax_amount,
                s.total_amount,
                s.receivable_total_amount,
                s.invoice_total_amount
            FROM sales s
            LEFT JOIN participants p ON p.id = s.participant_id
            WHERE s.company_id = :company_id
              AND s.status IN ('closed', 'paid')
              AND s.cancelled_at IS NULL
              AND s.operation_date::date BETWEEN :start_date AND :end_date
            ORDER BY s.operation_date ASC, s.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        ignored_sale_details = _rows(
            db,
            """
            SELECT
                s.id,
                s.sale_number_text,
                s.status,
                s.sale_type,
                s.origin,
                s.operation_nature,
                s.fiscal_status,
                s.issue_date,
                s.operation_date,
                s.competency_date,
                p.name AS participant_name,
                p.document AS participant_document,
                s.subtotal_amount,
                s.discount_amount,
                s.freight_amount,
                s.tax_amount,
                s.total_amount,
                s.receivable_total_amount,
                s.invoice_total_amount
            FROM sales s
            LEFT JOIN participants p ON p.id = s.participant_id
            WHERE s.company_id = :company_id
              AND s.status = 'quote'
              AND s.cancelled_at IS NULL
              AND s.operation_date::date BETWEEN :start_date AND :end_date
            ORDER BY s.operation_date ASC, s.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        purchase_details = _rows(
            db,
            """
            SELECT
                pu.id,
                pu.status,
                pu.purchase_type,
                pu.origin,
                pu.fiscal_status,
                pu.issue_date,
                pu.operation_date,
                pu.competency_date,
                p.name AS participant_name,
                p.document AS participant_document,
                pu.document_type,
                pu.document_number,
                pu.document_series,
                pu.access_key,
                pu.subtotal_amount,
                pu.discount_amount,
                pu.freight_amount,
                pu.tax_amount,
                pu.total_amount,
                pu.payable_total_amount,
                pu.invoice_total_amount
            FROM purchases pu
            LEFT JOIN participants p ON p.id = pu.participant_id
            WHERE pu.company_id = :company_id
              AND pu.status = 'confirmed'
              AND pu.cancelled_at IS NULL
              AND pu.deleted_at IS NULL
              AND pu.operation_date::date BETWEEN :start_date AND :end_date
            ORDER BY pu.operation_date ASC, pu.id ASC
            LIMIT :limit
            """,
            detail_params,
        )
        ignored_purchase_details = _rows(
            db,
            """
            SELECT
                pu.id,
                pu.status,
                pu.purchase_type,
                pu.origin,
                pu.fiscal_status,
                pu.issue_date,
                pu.operation_date,
                pu.competency_date,
                p.name AS participant_name,
                p.document AS participant_document,
                pu.document_type,
                pu.document_number,
                pu.document_series,
                pu.access_key,
                pu.subtotal_amount,
                pu.discount_amount,
                pu.freight_amount,
                pu.tax_amount,
                pu.total_amount,
                pu.payable_total_amount,
                pu.invoice_total_amount
            FROM purchases pu
            LEFT JOIN participants p ON p.id = pu.participant_id
            WHERE pu.company_id = :company_id
              AND pu.status = 'draft'
              AND pu.cancelled_at IS NULL
              AND pu.deleted_at IS NULL
              AND pu.operation_date::date BETWEEN :start_date AND :end_date
            ORDER BY pu.operation_date ASC, pu.id ASC
            LIMIT :limit
            """,
            detail_params,
        )

    projected_inflow = Decimal(str(projected_flow.get("projected_inflow_amount") or 0))
    projected_outflow = Decimal(str(projected_flow.get("projected_outflow_amount") or 0))
    realized_inflow = Decimal(str(realized_flow.get("realized_inflow_amount") or 0))
    realized_outflow = Decimal(str(realized_flow.get("realized_outflow_amount") or 0))
    settlement_amount = _decimal(settlement_consistency.get("settlement_movement_amount"))
    posted_movement_amount = _decimal(settlement_consistency.get("posted_movement_amount"))

    snapshot_version = "v1.1.0"
    generated_at = datetime.now(timezone.utc).isoformat()
    detail_counts = {
        "open_title_details": len(open_title_details),
        "period_title_details": len(period_title_details),
        "settlement_details": len(settlement_details),
        "movement_details": len(movement_details),
        "statement_line_details": len(statement_line_details),
        "sales_details": len(sales_details),
        "purchase_details": len(purchase_details),
        "ignored_sale_details": len(ignored_sale_details),
        "ignored_purchase_details": len(ignored_purchase_details),
        "fiscal_sales_documents": len(fiscal_report.get("sales_documents") or []) if include_details else 0,
        "fiscal_purchase_documents": len(fiscal_report.get("purchase_documents") or []) if include_details else 0,
        "fiscal_title_documents": len(fiscal_report.get("title_documents") or []) if include_details else 0,
        "fiscal_documents": len(fiscal_report.get("fiscal_documents") or []) if include_details else 0,
    }

    return {
        "company_id": company_id,
        "company_display_name": company.get("display_name"),
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "snapshot": {
            "version": snapshot_version,
            "generated_at": generated_at,
            "snapshot_key": f"{company_id}:{start.isoformat()}:{end.isoformat()}:{snapshot_version}",
            "calculation_mode": "live_read_only",
        },
        "filters_used": {
            "company_id": company_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reference_date": today.isoformat(),
            "include_details": include_details,
            "export_all": export_all,
            "limit": page_limit,
        },
        "indicators": {
            "accounts_receivable_open": {
                "count": _int(titles.get("receivable_open_count")),
                "amount": _money(titles.get("receivable_open_amount")),
                "scope": "current_position",
            },
            "accounts_receivable_overdue": {
                "count": _int(titles.get("receivable_overdue_count")),
                "amount": _money(titles.get("receivable_overdue_amount")),
                "scope": "current_position",
            },
            "accounts_payable_open": {
                "count": _int(titles.get("payable_open_count")),
                "amount": _money(titles.get("payable_open_amount")),
                "scope": "current_position",
            },
            "accounts_payable_overdue": {
                "count": _int(titles.get("payable_overdue_count")),
                "amount": _money(titles.get("payable_overdue_amount")),
                "scope": "current_position",
            },
            "cash_flow_projected": {
                "inflow_amount": _money(projected_inflow),
                "outflow_amount": _money(projected_outflow),
                "net_amount": _money(projected_inflow - projected_outflow),
                "scope": "period_due_date",
            },
            "cash_flow_realized": {
                "inflow_amount": _money(realized_inflow),
                "outflow_amount": _money(realized_outflow),
                "net_amount": _money(realized_inflow - realized_outflow),
                "scope": "period_settlement_date",
            },
            "reconciliation_pendencies": {
                "unreconciled_movements": _int(reconciliation_pendencies.get("unreconciled_movements")),
                "unmatched_statement_lines": _int(reconciliation_pendencies.get("unmatched_statement_lines")),
            },
            "fiscal_document_pendencies": {
                "pending_sales_documents": _int(fiscal_summary.get("pending_sales_documents")),
                "pending_purchase_documents": _int(fiscal_summary.get("pending_purchase_documents")),
                "pending_fiscal_titles": _int(fiscal_summary.get("pending_fiscal_titles")),
                "pending_fiscal_open_amount": _money(fiscal_summary.get("pending_fiscal_open_amount")),
                "fiscal_documents_pending": _int(fiscal_summary.get("fiscal_documents_pending")),
                "fiscal_documents_error": _int(fiscal_summary.get("fiscal_documents_error")),
            },
        },
        "operational_ignored": {
            "sale_quotes_ignored_count": _int(ignored_operational.get("sale_quotes_ignored_count")),
            "sale_quotes_ignored_amount": _money(ignored_operational.get("sale_quotes_ignored_amount")),
            "purchase_drafts_ignored_count": _int(ignored_operational.get("purchase_drafts_ignored_count")),
            "purchase_drafts_ignored_amount": _money(ignored_operational.get("purchase_drafts_ignored_amount")),
        },
        "consistency_checks": {
            "active_settlements": _int(settlement_consistency.get("active_settlements")),
            "settlement_movement_amount": _money(settlement_amount),
            "posted_movement_amount": _money(posted_movement_amount),
            "difference_amount": _money(settlement_amount - posted_movement_amount),
            "settlements_without_movement_count": _int(settlement_consistency.get("settlements_without_movement_count")),
            "settlements_without_movement_amount": _money(settlement_consistency.get("settlements_without_movement_amount")),
            "settlements_with_multiple_movements": _int(settlement_consistency.get("settlements_with_multiple_movements")),
        },
        "detail_limits": {
            "include_details": include_details,
            "export_all": export_all,
            "limit": page_limit,
            "max_export_rows": ACCOUNTANT_EXPORT_LIMIT,
            "is_limited": include_details and not export_all and any(count >= page_limit for count in detail_counts.values()),
            "returned_rows": detail_counts,
        },
        "balances_by_account": [_normalize_money_fields(row, ["balance_amount"]) for row in balances],
        "movements_by_period": [_normalize_money_fields(row, ["amount", "reconciled_amount", "unreconciled_amount"]) for row in movements_by_period],
        "sales_by_period": [_normalize_money_fields(row, ["total_amount", "receivable_total_amount", "invoice_total_amount"]) for row in sales_by_period],
        "purchases_by_period": [_normalize_money_fields(row, ["total_amount", "payable_total_amount", "invoice_total_amount"]) for row in purchases_by_period],
        "open_title_details": [_normalize_money_fields(row, ["gross_amount", "net_amount", "paid_amount", "open_amount"]) for row in open_title_details],
        "period_title_details": [_normalize_money_fields(row, ["gross_amount", "net_amount", "paid_amount", "open_amount"]) for row in period_title_details],
        "settlement_details": [
            _normalize_money_fields(
                row,
                [
                    "received_amount",
                    "discount_amount",
                    "interest_amount",
                    "penalty_amount",
                    "fee_amount",
                    "title_settled_amount",
                    "movement_amount",
                    "linked_movement_amount",
                ],
            )
            for row in settlement_details
        ],
        "movement_details": [_normalize_money_fields(row, ["amount"]) for row in movement_details],
        "statement_line_details": [_normalize_money_fields(row, ["amount", "matched_amount"]) for row in statement_line_details],
        "sales_details": [_normalize_money_fields(row, ["subtotal_amount", "discount_amount", "freight_amount", "tax_amount", "total_amount", "receivable_total_amount", "invoice_total_amount"]) for row in sales_details],
        "purchase_details": [_normalize_money_fields(row, ["subtotal_amount", "discount_amount", "freight_amount", "tax_amount", "total_amount", "payable_total_amount", "invoice_total_amount"]) for row in purchase_details],
        "ignored_sale_details": [_normalize_money_fields(row, ["subtotal_amount", "discount_amount", "freight_amount", "tax_amount", "total_amount", "receivable_total_amount", "invoice_total_amount"]) for row in ignored_sale_details],
        "ignored_purchase_details": [_normalize_money_fields(row, ["subtotal_amount", "discount_amount", "freight_amount", "tax_amount", "total_amount", "payable_total_amount", "invoice_total_amount"]) for row in ignored_purchase_details],
        "fiscal_pending_details": {
            "sales_documents": fiscal_report.get("sales_documents") if include_details else [],
            "purchase_documents": fiscal_report.get("purchase_documents") if include_details else [],
            "title_documents": fiscal_report.get("title_documents") if include_details else [],
            "fiscal_documents": fiscal_report.get("fiscal_documents") if include_details else [],
        },
        "indicator_formulas": {
            "accounts_receivable_open": "Posicao atual: COUNT/SUM de financial_titles direction=receivable e status open|partially_paid|partially_received|overdue, excluindo cancelled/deleted.",
            "accounts_receivable_overdue": "Posicao atual: recebiveis ativos com due_date < reference_date em America/Sao_Paulo.",
            "accounts_payable_open": "Posicao atual: COUNT/SUM de financial_titles direction=payable e status open|partially_paid|partially_received|overdue, excluindo cancelled/deleted.",
            "accounts_payable_overdue": "Posicao atual: pagaveis ativos com due_date < reference_date em America/Sao_Paulo.",
            "cash_flow_projected": "Periodo: soma de open_amount dos titulos ativos com due_date dentro do periodo, receivable como entrada e payable como saida.",
            "cash_flow_realized": "Periodo: soma de movement_amount das baixas ativas em settlements por settlement_date, inflow como entrada e outflow como saida.",
            "balances_by_account": "Posicao atual: saldo interno materializado em financial_account_balances por conta financeira; nao e saldo final do periodo.",
            "movements_by_period": "Periodo: COUNT/SUM de financial_movements postados, sem estorno, separados por direcao e conciliacao.",
            "sales_by_period": "Periodo: COUNT/SUM de sales status closed|paid; orcamentos/quotes ficam fora e sao informados em operational_ignored.",
            "purchases_by_period": "Periodo: COUNT/SUM de purchases status confirmed; rascunhos ficam fora e sao informados em operational_ignored.",
            "reconciliation_pendencies": "Periodo: movimentos pending|divergent + linhas de extrato pending|divergent. Ignored nao entra.",
            "fiscal_document_pendencies": "Periodo: resumo de pendencias fiscais preparatorias de vendas, compras, titulos e documentos fiscais reais.",
            "settlement_consistency": "Periodo: compara settlements ativos com financial_movements postados vinculados ao settlement_id.",
        },
        "notes": [
            "Relatorio para contador e leitura consolidada: nao corrige dado, nao recria historico e nao substitui fechamento contabil oficial.",
            "Posicao atual e periodo sao separados: titulos em aberto e saldos sao posicao atual; baixas, movimentos, vendas e compras respeitam o periodo filtrado.",
            "Venda em quote e compra em draft nao entram como fato realizado; aparecem em operational_ignored para rastreabilidade.",
            "Caixa realizado vem de baixas ativas em settlements; conciliacao bancaria continua sendo conferencia posterior.",
            "Toda exportacao deve manter periodo, filtros, versao do snapshot e data de geracao para rastreabilidade.",
        ],
    }

