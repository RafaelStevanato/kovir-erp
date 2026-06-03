from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cash_flow.repository import (
    account_cash_flow,
    daily_cash_flow,
    get_account_balances_map,
    get_financial_accounts,
    money,
    money_str,
    movement_totals_in_period,
    overview_evidence,
    pending_items,
    reconciliation_movement_totals,
    reconciliation_status_summary,
    settlement_totals_in_period,
    statement_line_totals,
    sum_overdue_titles,
    sum_overdue_payables,
    sum_payable_open_in_period,
    sum_title_open_in_period,
)
from app.modules.company.db_models import CompanyDB
from app.modules.financial.db_models import FinancialAccountDB
from app.shared.datetime import today_in_brazil
from app.shared.ids import assert_valid_id


def _assert_company(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    exists = db.scalar(select(CompanyDB.id).where(CompanyDB.id == company_id, CompanyDB.deleted_at.is_(None)))
    if not exists:
        raise ValueError("Empresa não encontrada.")


def _assert_account(db: Session, *, company_id: str, financial_account_id: str | None) -> None:
    if not financial_account_id:
        return
    assert_valid_id(financial_account_id)
    exists = db.scalar(select(FinancialAccountDB.id).where(FinancialAccountDB.id == financial_account_id, FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None)))
    if not exists:
        raise ValueError("Conta financeira não encontrada para a empresa.")


def _validate_period(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("Data final não pode ser anterior à data inicial.")
    if (end_date - start_date).days > 370:
        raise ValueError("O período máximo do dashboard é de 370 dias.")


def _default_period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    today = today_in_brazil()
    end = end_date or today
    start = start_date or (end - timedelta(days=30))
    return start, end


def get_cash_flow_summary(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None) -> dict[str, Any]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)

    title_count, expected_inflow = sum_title_open_in_period(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    payable_count, expected_outflow = sum_payable_open_in_period(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    reference_date = today_in_brazil()
    overdue_count, overdue_amount = sum_overdue_titles(db, company_id=company_id, today=reference_date, financial_account_id=financial_account_id)
    overdue_payable_count, overdue_payable_amount = sum_overdue_payables(db, company_id=company_id, today=reference_date, financial_account_id=financial_account_id)
    movement_totals = movement_totals_in_period(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    settlement_totals = settlement_totals_in_period(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    reconciliation = reconciliation_movement_totals(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    statements = statement_line_totals(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)
    accounts = get_financial_accounts(db, company_id=company_id, financial_account_id=financial_account_id)
    balances = get_account_balances_map(db, company_id=company_id)

    internal_balance_total = Decimal("0.00")
    for account in accounts:
        balance = balances.get(account.id)
        internal_balance_total += money(balance.current_balance_amount if balance else account.opening_balance_amount)

    realized_net = movement_totals["inflow"] - movement_totals["outflow"]
    projected_net = expected_inflow - expected_outflow + realized_net
    pending_recon = reconciliation.get("pending", {"count": 0, "amount": "0.00"})
    divergent_recon = reconciliation.get("divergent", {"count": 0, "amount": "0.00"})
    matched_recon = reconciliation.get("matched", {"count": 0, "amount": "0.00"})

    return {
        "company_id": company_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "reference_date": reference_date.isoformat(),
        "financial_account_id": financial_account_id,
        "basis": "mixed",
        "internal_balance_total": money_str(internal_balance_total),
        "financial_account_count": len(accounts),
        "expected_inflow_amount": money_str(expected_inflow),
        "expected_inflow_count": title_count,
        "expected_outflow_amount": money_str(expected_outflow),
        "expected_outflow_count": payable_count,
        "overdue_receivable_amount": money_str(overdue_amount),
        "overdue_receivable_count": overdue_count,
        "overdue_payable_amount": money_str(overdue_payable_amount),
        "overdue_payable_count": overdue_payable_count,
        "received_amount": money_str(settlement_totals["received"]),
        "paid_amount": money_str(settlement_totals["paid"]),
        "settlement_discount_amount": money_str(settlement_totals["discount"]),
        "settlement_fee_amount": money_str(settlement_totals["fee"]),
        "realized_inflow_amount": money_str(movement_totals["inflow"]),
        "realized_outflow_amount": money_str(movement_totals["outflow"]),
        "realized_net_amount": money_str(realized_net),
        "projected_net_amount": money_str(projected_net),
        "matched_movement_count": int(matched_recon.get("count", 0)),
        "matched_movement_amount": matched_recon.get("amount", "0.00"),
        "pending_reconciliation_count": int(pending_recon.get("count", 0)),
        "pending_reconciliation_amount": pending_recon.get("amount", "0.00"),
        "divergent_reconciliation_count": int(divergent_recon.get("count", 0)),
        "divergent_reconciliation_amount": divergent_recon.get("amount", "0.00"),
        "statement_inflow_amount": statements["by_direction"]["inflow"],
        "statement_outflow_amount": statements["by_direction"]["outflow"],
        "pending_statement_lines": int(statements["by_status"].get("pending", {}).get("count", 0)),
        "matched_statement_lines": int(statements["by_status"].get("matched", {}).get("count", 0)),
        "divergent_statement_lines": int(statements["by_status"].get("divergent", {}).get("count", 0)),
        "health_flags": _build_health_flags(title_count=title_count, overdue_count=overdue_count, overdue_payable_count=overdue_payable_count, pending_reconciliation_count=int(pending_recon.get("count", 0)), pending_statement_lines=int(statements["by_status"].get("pending", {}).get("count", 0)), divergent_count=int(divergent_recon.get("count", 0)) + int(statements["by_status"].get("divergent", {}).get("count", 0))),
    }


def _build_health_flags(*, title_count: int, overdue_count: int, overdue_payable_count: int, pending_reconciliation_count: int, pending_statement_lines: int, divergent_count: int) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if overdue_count > 0:
        flags.append({"level": "warning", "code": "overdue_receivables", "message": "Existem títulos a receber vencidos em aberto."})
    if overdue_payable_count > 0:
        flags.append({"level": "warning", "code": "overdue_payables", "message": "Existem títulos a pagar vencidos em aberto."})
    if pending_reconciliation_count > 0 or pending_statement_lines > 0:
        flags.append({"level": "info", "code": "pending_reconciliation", "message": "Existem movimentos ou linhas de extrato pendentes de conciliação."})
    if divergent_count > 0:
        flags.append({"level": "risk", "code": "reconciliation_divergence", "message": "Existem divergências de conciliação que precisam de revisão."})
    if title_count == 0 and pending_reconciliation_count == 0 and pending_statement_lines == 0:
        flags.append({"level": "ok", "code": "no_pending_items", "message": "Nenhuma pendência financeira relevante no período consultado."})
    return flags


def get_cash_flow_daily(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None) -> list[dict[str, Any]]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)
    return daily_cash_flow(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)


def get_cash_flow_accounts(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)
    return account_cash_flow(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id, limit=max(1, min(limit, 200)), offset=max(offset, 0))


def get_cash_flow_pending(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)
    return pending_items(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id, limit=max(1, min(limit, 100)))


def get_cash_flow_overview_evidence(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None, limit: int = 5000) -> dict[str, Any]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)
    return {
        "company_id": company_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "reference_date": today_in_brazil().isoformat(),
        "financial_account_id": financial_account_id,
        **overview_evidence(
            db,
            company_id=company_id,
            start_date=start,
            end_date=end,
            financial_account_id=financial_account_id,
            limit=max(1, min(limit, 5000)),
        ),
    }


def get_cash_flow_reconciliation_status(db: Session, *, company_id: str, start_date: date | None = None, end_date: date | None = None, financial_account_id: str | None = None) -> dict[str, Any]:
    start, end = _default_period(start_date, end_date)
    _validate_period(start, end)
    _assert_company(db, company_id)
    _assert_account(db, company_id=company_id, financial_account_id=financial_account_id)
    return reconciliation_status_summary(db, company_id=company_id, start_date=start, end_date=end, financial_account_id=financial_account_id)


def get_cash_flow_diagnostics() -> dict[str, Any]:
    return {
        "module": "cash_flow",
        "status": "ready",
        "storage": "derived",
        "persistence": "postgresql",
        "tables_consumed": [
            "financial_titles",
            "settlements",
            "financial_movements",
            "financial_account_balances",
            "financial_accounts",
            "purchases",
            "purchase_financial_links",
            "bank_statement_lines",
            "reconciliation_matches",
        ],
        "tables_created": [],
        "integrations": ["accounts_receivable", "cash", "reconciliation", "financial", "sales"],
        "safety": [
            "Dashboard não grava fato financeiro.",
            "Fluxo de caixa lê títulos, baixas, movimentos e conciliação sem corrigir origem.",
            "Período máximo de consulta limitado para evitar consultas pesadas.",
            "Empresa e conta financeira são validadas no backend.",
        ],
    }


def get_cash_flow_rules() -> dict[str, Any]:
    return {
        "principles": [
            "Fluxo de caixa não é DRE.",
            "Saldo interno vem de financial_movements e financial_account_balances.",
            "Entrada prevista vem de financial_titles receivable em aberto.",
            "Saída prevista vem de financial_titles payable em aberto.",
            "Entrada realizada vem de settlements e financial_movements postados.",
            "Saldo conciliado depende de reconciliation_matches e status de conciliação.",
            "Extrato/OFX é evidência externa; não altera saldo interno sozinho.",
            "Relatório não corrige dado ruim; ele aponta a origem da divergência.",
        ],
        "indicators": [
            "saldo interno total",
            "entradas previstas",
            "recebimentos realizados",
            "entradas e saídas realizadas",
            "títulos vencidos",
            "movimentos pendentes de conciliação",
            "linhas de extrato pendentes",
            "divergências de conciliação",
            "saldo por conta financeira",
        ],
        "flows": {
            "expected": "financial_titles receivable/payable em aberto por due_date",
            "realized": "settlements + financial_movements postados",
            "reconciled": "financial_movements com reconciliation_status matched/divergent + reconciliation_matches",
            "external_evidence": "bank_statement_lines importadas por manual/OFX/API futura",
        },
        "correction_policy": {
            "título errado": "corrigir em Contas a Receber",
            "baixa errada": "estornar/corrigir em Recebimentos e Baixas",
            "movimento errado": "corrigir via movimento/estorno, não no dashboard",
            "extrato errado": "corrigir em Conciliação/Extratos",
            "match errado": "estornar match em Conciliação",
        },
    }
