from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.cash.db_models import FinancialAccountBalanceDB, FinancialMovementDB, SettlementDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.participants.db_models import ParticipantDB
from app.modules.reconciliation.db_models import BankStatementLineDB, ReconciliationMatchDB
from app.shared.datetime import today_in_brazil

MONEY_QUANT = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_str(value: Any) -> str:
    return format(money(value), "f")


def iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def _period_filter(column: Any, start_date: date, end_date: date):
    return column >= start_date, column <= end_date


def _account_filter(model: Any, financial_account_id: str | None):
    if financial_account_id:
        return [model.financial_account_id == financial_account_id]
    return []


def get_financial_accounts(db: Session, *, company_id: str, financial_account_id: str | None = None, limit: int | None = None, offset: int = 0) -> list[FinancialAccountDB]:
    stmt = select(FinancialAccountDB).where(FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None))
    if financial_account_id:
        stmt = stmt.where(FinancialAccountDB.id == financial_account_id)
    stmt = stmt.order_by(FinancialAccountDB.name.asc(), FinancialAccountDB.id.asc())
    if limit is not None:
        stmt = stmt.limit(min(max(int(limit), 1), 200)).offset(max(int(offset or 0), 0))
    return list(db.scalars(stmt).all())


def get_account_balances_map(db: Session, *, company_id: str) -> dict[str, FinancialAccountBalanceDB]:
    rows = db.scalars(select(FinancialAccountBalanceDB).where(FinancialAccountBalanceDB.company_id == company_id)).all()
    return {row.financial_account_id: row for row in rows}


def sum_title_open_in_period(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> tuple[int, Decimal]:
    conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    if financial_account_id:
        conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    count_value, amount_value = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*conditions)).one()
    return int(count_value or 0), money(amount_value)


def sum_overdue_titles(db: Session, *, company_id: str, today: date, financial_account_id: str | None = None) -> tuple[int, Decimal]:
    conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
        FinancialTitleDB.due_date < today,
    ]
    if financial_account_id:
        conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    count_value, amount_value = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*conditions)).one()
    return int(count_value or 0), money(amount_value)




def sum_payable_open_in_period(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> tuple[int, Decimal]:
    conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    if financial_account_id:
        conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    count_value, amount_value = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*conditions)).one()
    return int(count_value or 0), money(amount_value)


def sum_overdue_payables(db: Session, *, company_id: str, today: date, financial_account_id: str | None = None) -> tuple[int, Decimal]:
    conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]),
        FinancialTitleDB.due_date < today,
    ]
    if financial_account_id:
        conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    count_value, amount_value = db.execute(select(func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*conditions)).one()
    return int(count_value or 0), money(amount_value)

def movement_totals_in_period(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Decimal]:
    conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
    ]
    conditions.extend(_account_filter(FinancialMovementDB, financial_account_id))
    rows = db.execute(select(FinancialMovementDB.direction, func.coalesce(func.sum(FinancialMovementDB.amount), 0)).where(*conditions).group_by(FinancialMovementDB.direction)).all()
    totals = {"inflow": Decimal("0.00"), "outflow": Decimal("0.00")}
    for direction, amount in rows:
        if direction in totals:
            totals[direction] = money(amount)
    return totals


def settlement_totals_in_period(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Decimal]:
    base_conditions = [
        SettlementDB.company_id == company_id,
        SettlementDB.status == "active",
        SettlementDB.settlement_date >= start_date,
        SettlementDB.settlement_date <= end_date,
    ]
    base_conditions.extend(_account_filter(SettlementDB, financial_account_id))
    inflow_conditions = [*base_conditions, SettlementDB.direction == "inflow"]
    outflow_conditions = [*base_conditions, SettlementDB.direction == "outflow"]
    inflow_row = db.execute(select(func.coalesce(func.sum(SettlementDB.received_amount), 0), func.coalesce(func.sum(SettlementDB.discount_amount), 0), func.coalesce(func.sum(SettlementDB.fee_amount), 0)).where(*inflow_conditions)).one()
    paid_value = db.scalar(select(func.coalesce(func.sum(SettlementDB.movement_amount), 0)).where(*outflow_conditions))
    return {"received": money(inflow_row[0]), "paid": money(paid_value), "discount": money(inflow_row[1]), "fee": money(inflow_row[2])}


def reconciliation_movement_totals(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Any]:
    conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
    ]
    conditions.extend(_account_filter(FinancialMovementDB, financial_account_id))
    rows = db.execute(select(FinancialMovementDB.reconciliation_status, func.count(FinancialMovementDB.id), func.coalesce(func.sum(FinancialMovementDB.amount), 0)).where(*conditions).group_by(FinancialMovementDB.reconciliation_status)).all()
    by_status: dict[str, dict[str, Any]] = {}
    for status, count_value, amount in rows:
        by_status[status or "unknown"] = {"count": int(count_value or 0), "amount": money_str(amount)}
    return by_status


def statement_line_totals(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Any]:
    conditions = [
        BankStatementLineDB.company_id == company_id,
        BankStatementLineDB.status != "ignored",
        BankStatementLineDB.line_date >= start_date,
        BankStatementLineDB.line_date <= end_date,
    ]
    conditions.extend(_account_filter(BankStatementLineDB, financial_account_id))
    by_status_rows = db.execute(select(BankStatementLineDB.status, func.count(BankStatementLineDB.id), func.coalesce(func.sum(BankStatementLineDB.amount), 0)).where(*conditions).group_by(BankStatementLineDB.status)).all()
    by_direction_rows = db.execute(select(BankStatementLineDB.direction, func.coalesce(func.sum(BankStatementLineDB.amount), 0)).where(*conditions).group_by(BankStatementLineDB.direction)).all()
    by_status = {status or "unknown": {"count": int(count_value or 0), "amount": money_str(amount)} for status, count_value, amount in by_status_rows}
    by_direction = {"inflow": "0.00", "outflow": "0.00"}
    for direction, amount in by_direction_rows:
        if direction in by_direction:
            by_direction[direction] = money_str(amount)
    return {"by_status": by_status, "by_direction": by_direction}


def movement_totals_by_account(db: Session, *, company_id: str, start_date: date, end_date: date, account_ids: list[str]) -> dict[str, dict[str, Decimal]]:
    if not account_ids:
        return {}
    conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
        FinancialMovementDB.financial_account_id.in_(account_ids),
    ]
    rows = db.execute(
        select(
            FinancialMovementDB.financial_account_id,
            FinancialMovementDB.direction,
            func.coalesce(func.sum(FinancialMovementDB.amount), 0),
        )
        .where(*conditions)
        .group_by(FinancialMovementDB.financial_account_id, FinancialMovementDB.direction)
    ).all()
    totals: dict[str, dict[str, Decimal]] = {account_id: {"inflow": Decimal("0.00"), "outflow": Decimal("0.00")} for account_id in account_ids}
    for account_id, direction, amount in rows:
        if direction in {"inflow", "outflow"}:
            totals[str(account_id)][str(direction)] = money(amount)
    return totals


def reconciliation_movement_totals_by_account(db: Session, *, company_id: str, start_date: date, end_date: date, account_ids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    if not account_ids:
        return {}
    conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
        FinancialMovementDB.financial_account_id.in_(account_ids),
    ]
    rows = db.execute(
        select(
            FinancialMovementDB.financial_account_id,
            FinancialMovementDB.reconciliation_status,
            func.count(FinancialMovementDB.id),
            func.coalesce(func.sum(FinancialMovementDB.amount), 0),
        )
        .where(*conditions)
        .group_by(FinancialMovementDB.financial_account_id, FinancialMovementDB.reconciliation_status)
    ).all()
    output: dict[str, dict[str, dict[str, Any]]] = {account_id: {} for account_id in account_ids}
    for account_id, status, count_value, amount in rows:
        output[str(account_id)][status or "unknown"] = {"count": int(count_value or 0), "amount": money_str(amount)}
    return output


def statement_line_totals_by_account(db: Session, *, company_id: str, start_date: date, end_date: date, account_ids: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    if not account_ids:
        return {}
    conditions = [
        BankStatementLineDB.company_id == company_id,
        BankStatementLineDB.status != "ignored",
        BankStatementLineDB.line_date >= start_date,
        BankStatementLineDB.line_date <= end_date,
        BankStatementLineDB.financial_account_id.in_(account_ids),
    ]
    status_rows = db.execute(
        select(
            BankStatementLineDB.financial_account_id,
            BankStatementLineDB.status,
            func.count(BankStatementLineDB.id),
            func.coalesce(func.sum(BankStatementLineDB.amount), 0),
        )
        .where(*conditions)
        .group_by(BankStatementLineDB.financial_account_id, BankStatementLineDB.status)
    ).all()
    direction_rows = db.execute(
        select(
            BankStatementLineDB.financial_account_id,
            BankStatementLineDB.direction,
            func.coalesce(func.sum(BankStatementLineDB.amount), 0),
        )
        .where(*conditions)
        .group_by(BankStatementLineDB.financial_account_id, BankStatementLineDB.direction)
    ).all()
    output: dict[str, dict[str, dict[str, Any]]] = {
        account_id: {"by_status": {}, "by_direction": {"inflow": "0.00", "outflow": "0.00"}}
        for account_id in account_ids
    }
    for account_id, status, count_value, amount in status_rows:
        output[str(account_id)]["by_status"][status or "unknown"] = {"count": int(count_value or 0), "amount": money_str(amount)}
    for account_id, direction, amount in direction_rows:
        if direction in {"inflow", "outflow"}:
            output[str(account_id)]["by_direction"][str(direction)] = money_str(amount)
    return output


def match_totals(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Any]:
    conditions = [ReconciliationMatchDB.company_id == company_id, ReconciliationMatchDB.created_at >= start_date, ReconciliationMatchDB.created_at < (end_date + timedelta(days=1))]
    if financial_account_id:
        conditions.append(ReconciliationMatchDB.financial_account_id == financial_account_id)
    rows = db.execute(select(ReconciliationMatchDB.status, func.count(ReconciliationMatchDB.id), func.coalesce(func.sum(ReconciliationMatchDB.difference_amount), 0)).where(*conditions).group_by(ReconciliationMatchDB.status)).all()
    return {status or "unknown": {"count": int(count_value or 0), "difference_amount": money_str(amount)} for status, count_value, amount in rows}


def daily_cash_flow(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> list[dict[str, Any]]:
    days: dict[date, dict[str, Any]] = defaultdict(lambda: {
        "expected_inflow_amount": Decimal("0.00"),
        "expected_inflow_count": 0,
        "expected_outflow_amount": Decimal("0.00"),
        "expected_outflow_count": 0,
        "received_amount": Decimal("0.00"),
        "paid_amount": Decimal("0.00"),
        "movement_inflow_amount": Decimal("0.00"),
        "movement_outflow_amount": Decimal("0.00"),
        "statement_inflow_amount": Decimal("0.00"),
        "statement_outflow_amount": Decimal("0.00"),
        "pending_statement_lines": 0,
        "unreconciled_movements": 0,
    })

    title_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    if financial_account_id:
        title_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    for due_date, count_value, amount in db.execute(select(FinancialTitleDB.due_date, func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*title_conditions).group_by(FinancialTitleDB.due_date)).all():
        days[due_date]["expected_inflow_amount"] += money(amount)
        days[due_date]["expected_inflow_count"] += int(count_value or 0)


    payable_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    if financial_account_id:
        payable_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
    for due_date, count_value, amount in db.execute(select(FinancialTitleDB.due_date, func.count(FinancialTitleDB.id), func.coalesce(func.sum(FinancialTitleDB.open_amount), 0)).where(*payable_conditions).group_by(FinancialTitleDB.due_date)).all():
        days[due_date]["expected_outflow_amount"] += money(amount)
        days[due_date]["expected_outflow_count"] += int(count_value or 0)

    settlement_conditions = [SettlementDB.company_id == company_id, SettlementDB.status == "active", SettlementDB.settlement_date >= start_date, SettlementDB.settlement_date <= end_date]
    settlement_conditions.extend(_account_filter(SettlementDB, financial_account_id))
    for settlement_date, direction, received_amount, movement_amount in db.execute(
        select(
            SettlementDB.settlement_date,
            SettlementDB.direction,
            func.coalesce(func.sum(SettlementDB.received_amount), 0),
            func.coalesce(func.sum(SettlementDB.movement_amount), 0),
        ).where(*settlement_conditions).group_by(SettlementDB.settlement_date, SettlementDB.direction)
    ).all():
        if direction == "outflow":
            # Em pagamento, received_amount representa o principal pago ao título.
            # Para fluxo de caixa diário, a saída realizada deve usar movement_amount:
            # principal + juros + multa + tarifa.
            days[settlement_date]["paid_amount"] += money(movement_amount)
        else:
            days[settlement_date]["received_amount"] += money(received_amount)

    movement_conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
    ]
    movement_conditions.extend(_account_filter(FinancialMovementDB, financial_account_id))
    for movement_date, direction, amount, pending_count in db.execute(
        select(
            FinancialMovementDB.movement_date,
            FinancialMovementDB.direction,
            func.coalesce(func.sum(FinancialMovementDB.amount), 0),
            func.count(FinancialMovementDB.id).filter(FinancialMovementDB.reconciliation_status.in_(["pending", "divergent"])),
        ).where(*movement_conditions).group_by(FinancialMovementDB.movement_date, FinancialMovementDB.direction)
    ).all():
        key = "movement_inflow_amount" if direction == "inflow" else "movement_outflow_amount"
        days[movement_date][key] += money(amount)
        days[movement_date]["unreconciled_movements"] += int(pending_count or 0)

    statement_conditions = [
        BankStatementLineDB.company_id == company_id,
        BankStatementLineDB.status != "ignored",
        BankStatementLineDB.line_date >= start_date,
        BankStatementLineDB.line_date <= end_date,
    ]
    statement_conditions.extend(_account_filter(BankStatementLineDB, financial_account_id))
    for line_date, direction, amount, pending_count in db.execute(
        select(
            BankStatementLineDB.line_date,
            BankStatementLineDB.direction,
            func.coalesce(func.sum(BankStatementLineDB.amount), 0),
            func.count(BankStatementLineDB.id).filter(BankStatementLineDB.status.in_(["pending", "divergent"])),
        ).where(*statement_conditions).group_by(BankStatementLineDB.line_date, BankStatementLineDB.direction)
    ).all():
        key = "statement_inflow_amount" if direction == "inflow" else "statement_outflow_amount"
        days[line_date][key] += money(amount)
        days[line_date]["pending_statement_lines"] += int(pending_count or 0)

    output: list[dict[str, Any]] = []
    current = start_date
    while current <= end_date:
        row = days[current]
        realized_net = money(row["movement_inflow_amount"]) - money(row["movement_outflow_amount"])
        projected_net = money(row["expected_inflow_amount"]) - money(row["expected_outflow_amount"]) + realized_net
        output.append({
            "date": current.isoformat(),
            "expected_inflow_amount": money_str(row["expected_inflow_amount"]),
            "expected_inflow_count": row["expected_inflow_count"],
            "expected_outflow_amount": money_str(row["expected_outflow_amount"]),
            "expected_outflow_count": row["expected_outflow_count"],
            "received_amount": money_str(row["received_amount"]),
            "paid_amount": money_str(row["paid_amount"]),
            "movement_inflow_amount": money_str(row["movement_inflow_amount"]),
            "movement_outflow_amount": money_str(row["movement_outflow_amount"]),
            "realized_net_amount": money_str(realized_net),
            "projected_net_amount": money_str(projected_net),
            "statement_inflow_amount": money_str(row["statement_inflow_amount"]),
            "statement_outflow_amount": money_str(row["statement_outflow_amount"]),
            "pending_statement_lines": row["pending_statement_lines"],
            "unreconciled_movements": row["unreconciled_movements"],
        })
        current = date.fromordinal(current.toordinal() + 1)
    return output


def account_cash_flow(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    accounts = get_financial_accounts(db, company_id=company_id, financial_account_id=financial_account_id, limit=limit, offset=offset)
    balances = get_account_balances_map(db, company_id=company_id)
    account_ids = [account.id for account in accounts]
    movement_totals_by_id = movement_totals_by_account(db, company_id=company_id, start_date=start_date, end_date=end_date, account_ids=account_ids)
    reconciliation_by_id = reconciliation_movement_totals_by_account(db, company_id=company_id, start_date=start_date, end_date=end_date, account_ids=account_ids)
    statement_by_id = statement_line_totals_by_account(db, company_id=company_id, start_date=start_date, end_date=end_date, account_ids=account_ids)
    rows: list[dict[str, Any]] = []
    for account in accounts:
        movement_totals = movement_totals_by_id.get(account.id, {"inflow": Decimal("0.00"), "outflow": Decimal("0.00")})
        reconciliation = reconciliation_by_id.get(account.id, {})
        statement = statement_by_id.get(account.id, {"by_status": {}, "by_direction": {"inflow": "0.00", "outflow": "0.00"}})
        balance = balances.get(account.id)
        current_balance = money(balance.current_balance_amount if balance else account.opening_balance_amount)
        rows.append({
            "financial_account_id": account.id,
            "financial_account_name": account.name,
            "account_type": account.account_type,
            "institution_name": account.institution_name,
            "currency": account.currency,
            "opening_balance_amount": money_str(account.opening_balance_amount),
            "current_balance_amount": money_str(current_balance),
            "period_inflow_amount": money_str(movement_totals["inflow"]),
            "period_outflow_amount": money_str(movement_totals["outflow"]),
            "period_net_amount": money_str(movement_totals["inflow"] - movement_totals["outflow"]),
            "reconciliation_by_status": reconciliation,
            "statement_by_status": statement["by_status"],
            "statement_by_direction": statement["by_direction"],
            "last_balance_update": iso(balance.updated_at) if balance else None,
            "status": account.status,
        })
    return rows


def pending_items(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    today = today_in_brazil()
    overdue_titles_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
        FinancialTitleDB.due_date < today,
    ]
    open_titles_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "receivable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_received"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    overdue_payables_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]),
        FinancialTitleDB.due_date < today,
    ]
    upcoming_payables_conditions = [
        FinancialTitleDB.company_id == company_id,
        FinancialTitleDB.direction == "payable",
        FinancialTitleDB.deleted_at.is_(None),
        FinancialTitleDB.status.in_(["open", "overdue", "partially_paid"]),
        FinancialTitleDB.due_date >= start_date,
        FinancialTitleDB.due_date <= end_date,
    ]
    if financial_account_id:
        overdue_titles_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
        open_titles_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
        overdue_payables_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
        upcoming_payables_conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)

    def title_row(title: FinancialTitleDB) -> dict[str, Any]:
        return {
            "id": title.id,
            "direction": title.direction,
            "participant_id": title.participant_id,
            "document_reference": title.document_reference,
            "due_date": iso(title.due_date),
            "open_amount": money_str(title.open_amount),
            "status": title.status,
            "collection_status": title.collection_status,
            "source_type": title.source_type,
            "source_id": title.source_id,
        }

    overdue_titles = [title_row(row) for row in db.scalars(select(FinancialTitleDB).where(*overdue_titles_conditions).order_by(FinancialTitleDB.due_date.asc()).limit(limit)).all()]
    upcoming_titles = [title_row(row) for row in db.scalars(select(FinancialTitleDB).where(*open_titles_conditions).order_by(FinancialTitleDB.due_date.asc()).limit(limit)).all()]
    overdue_payables = [title_row(row) for row in db.scalars(select(FinancialTitleDB).where(*overdue_payables_conditions).order_by(FinancialTitleDB.due_date.asc()).limit(limit)).all()]
    upcoming_payables = [title_row(row) for row in db.scalars(select(FinancialTitleDB).where(*upcoming_payables_conditions).order_by(FinancialTitleDB.due_date.asc()).limit(limit)).all()]

    movement_conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.reconciliation_status.in_(["pending", "divergent"]),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
    ]
    movement_conditions.extend(_account_filter(FinancialMovementDB, financial_account_id))
    unreconciled_movements = [
        {
            "id": row.id,
            "financial_account_id": row.financial_account_id,
            "direction": row.direction,
            "movement_type": row.movement_type,
            "movement_date": iso(row.movement_date),
            "amount": money_str(row.amount),
            "source_type": row.source_type,
            "source_id": row.source_id,
            "description": row.description,
            "reconciliation_status": row.reconciliation_status,
        }
        for row in db.scalars(select(FinancialMovementDB).where(*movement_conditions).order_by(FinancialMovementDB.movement_date.asc()).limit(limit)).all()
    ]

    statement_conditions = [
        BankStatementLineDB.company_id == company_id,
        BankStatementLineDB.status.in_(["pending", "divergent"]),
        BankStatementLineDB.line_date >= start_date,
        BankStatementLineDB.line_date <= end_date,
    ]
    statement_conditions.extend(_account_filter(BankStatementLineDB, financial_account_id))
    unmatched_statement_lines = [
        {
            "id": row.id,
            "financial_account_id": row.financial_account_id,
            "line_date": iso(row.line_date),
            "direction": row.direction,
            "amount": money_str(row.amount),
            "description": row.description,
            "status": row.status,
            "bank_reference": row.bank_reference,
        }
        for row in db.scalars(select(BankStatementLineDB).where(*statement_conditions).order_by(BankStatementLineDB.line_date.asc()).limit(limit)).all()
    ]

    divergent_matches_conditions = [
        ReconciliationMatchDB.company_id == company_id,
        ReconciliationMatchDB.status == "confirmed_with_difference",
        ReconciliationMatchDB.created_at >= start_date,
        ReconciliationMatchDB.created_at < (end_date + timedelta(days=1)),
    ]
    if financial_account_id:
        divergent_matches_conditions.append(ReconciliationMatchDB.financial_account_id == financial_account_id)
    divergent_matches = [
        {
            "id": row.id,
            "financial_account_id": row.financial_account_id,
            "statement_line_id": row.statement_line_id,
            "financial_movement_id": row.financial_movement_id,
            "difference_amount": money_str(row.difference_amount),
            "confirmation_reason": row.confirmation_reason,
            "created_at": iso(row.created_at),
        }
        for row in db.scalars(select(ReconciliationMatchDB).where(*divergent_matches_conditions).order_by(ReconciliationMatchDB.created_at.desc()).limit(limit)).all()
    ]

    return {
        "overdue_titles": overdue_titles,
        "upcoming_titles": upcoming_titles,
        "overdue_payables": overdue_payables,
        "upcoming_payables": upcoming_payables,
        "unreconciled_movements": unreconciled_movements,
        "unmatched_statement_lines": unmatched_statement_lines,
        "divergent_matches": divergent_matches,
    }


def overview_evidence(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None, limit: int = 5000) -> dict[str, Any]:
    today = today_in_brazil()
    accounts = get_financial_accounts(db, company_id=company_id, financial_account_id=financial_account_id)
    balances = get_account_balances_map(db, company_id=company_id)

    def title_rows(*, direction: str, overdue_only: bool = False, in_period: bool = False) -> list[dict[str, Any]]:
        statuses = ["open", "overdue", "partially_received"] if direction == "receivable" else ["open", "overdue", "partially_paid"]
        conditions = [
            FinancialTitleDB.company_id == company_id,
            FinancialTitleDB.direction == direction,
            FinancialTitleDB.deleted_at.is_(None),
            FinancialTitleDB.status.in_(statuses),
        ]
        if overdue_only:
            conditions.append(FinancialTitleDB.due_date < today)
        if in_period:
            conditions.extend([FinancialTitleDB.due_date >= start_date, FinancialTitleDB.due_date <= end_date])
        if financial_account_id:
            conditions.append(FinancialTitleDB.expected_financial_account_id == financial_account_id)
        rows = db.execute(
            select(FinancialTitleDB, ParticipantDB.name, ParticipantDB.document, FinancialAccountDB.name)
            .outerjoin(ParticipantDB, ParticipantDB.id == FinancialTitleDB.participant_id)
            .outerjoin(FinancialAccountDB, FinancialAccountDB.id == FinancialTitleDB.expected_financial_account_id)
            .where(*conditions)
            .order_by(FinancialTitleDB.due_date.asc(), FinancialTitleDB.open_amount.desc(), FinancialTitleDB.id.asc())
            .limit(limit)
        ).all()
        return [
            {
                "id": title.id,
                "direction": title.direction,
                "participant_id": title.participant_id,
                "participant_name": participant_name,
                "participant_document": participant_document,
                "financial_account_name": account_name,
                "document_reference": title.document_reference,
                "issue_date": iso(title.issue_date),
                "competency_date": iso(title.competency_date),
                "due_date": iso(title.due_date),
                "expected_payment_date": iso(title.expected_payment_date),
                "installment_number": title.installment_number,
                "installment_total": title.installment_total,
                "gross_amount": money_str(title.gross_amount),
                "net_amount": money_str(title.net_amount),
                "paid_amount": money_str(title.paid_amount),
                "open_amount": money_str(title.open_amount),
                "status": title.status,
                "collection_status": title.collection_status,
                "source_type": title.source_type,
                "source_id": title.source_id,
            }
            for title, participant_name, participant_document, account_name in rows
        ]

    account_rows = []
    for account in accounts:
        balance = balances.get(account.id)
        account_rows.append({
            "financial_account_id": account.id,
            "financial_account_name": account.name,
            "account_type": account.account_type,
            "institution_name": account.institution_name,
            "currency": account.currency,
            "opening_balance_amount": money_str(account.opening_balance_amount),
            "current_balance_amount": money_str(balance.current_balance_amount if balance else account.opening_balance_amount),
            "last_balance_update": iso(balance.updated_at) if balance else None,
            "status": account.status,
        })

    settlement_conditions = [
        SettlementDB.company_id == company_id,
        SettlementDB.status == "active",
        SettlementDB.settlement_date >= start_date,
        SettlementDB.settlement_date <= end_date,
    ]
    settlement_conditions.extend(_account_filter(SettlementDB, financial_account_id))
    settlement_rows = db.execute(
        select(SettlementDB, FinancialTitleDB.document_reference, ParticipantDB.name, FinancialAccountDB.name)
        .join(FinancialTitleDB, FinancialTitleDB.id == SettlementDB.financial_title_id)
        .outerjoin(ParticipantDB, ParticipantDB.id == SettlementDB.participant_id)
        .outerjoin(FinancialAccountDB, FinancialAccountDB.id == SettlementDB.financial_account_id)
        .where(*settlement_conditions)
        .order_by(SettlementDB.settlement_date.asc(), SettlementDB.id.asc())
        .limit(limit)
    ).all()
    settlements = [
        {
            "id": settlement.id,
            "direction": settlement.direction,
            "settlement_type": settlement.settlement_type,
            "status": settlement.status,
            "settlement_date": iso(settlement.settlement_date),
            "competency_date": iso(settlement.competency_date),
            "financial_title_id": settlement.financial_title_id,
            "title_reference": title_reference,
            "participant_name": participant_name,
            "financial_account_name": account_name,
            "received_amount": money_str(settlement.received_amount),
            "discount_amount": money_str(settlement.discount_amount),
            "interest_amount": money_str(settlement.interest_amount),
            "penalty_amount": money_str(settlement.penalty_amount),
            "fee_amount": money_str(settlement.fee_amount),
            "title_settled_amount": money_str(settlement.title_settled_amount),
            "movement_amount": money_str(settlement.movement_amount),
            "evidence_reference": settlement.evidence_reference,
            "source_type": settlement.source_type,
            "source_id": settlement.source_id,
        }
        for settlement, title_reference, participant_name, account_name in settlement_rows
    ]

    movement_conditions = [
        FinancialMovementDB.company_id == company_id,
        FinancialMovementDB.status == "posted",
        FinancialMovementDB.reversal_of_movement_id.is_(None),
        FinancialMovementDB.movement_date >= start_date,
        FinancialMovementDB.movement_date <= end_date,
    ]
    movement_conditions.extend(_account_filter(FinancialMovementDB, financial_account_id))
    movement_rows = db.execute(
        select(FinancialMovementDB, FinancialAccountDB.name, ParticipantDB.name, FinancialTitleDB.document_reference)
        .join(FinancialAccountDB, FinancialAccountDB.id == FinancialMovementDB.financial_account_id)
        .outerjoin(ParticipantDB, ParticipantDB.id == FinancialMovementDB.participant_id)
        .outerjoin(FinancialTitleDB, FinancialTitleDB.id == FinancialMovementDB.financial_title_id)
        .where(*movement_conditions)
        .order_by(FinancialMovementDB.movement_date.asc(), FinancialMovementDB.id.asc())
        .limit(limit)
    ).all()
    movements = [
        {
            "id": movement.id,
            "financial_account_id": movement.financial_account_id,
            "financial_account_name": account_name,
            "direction": movement.direction,
            "movement_type": movement.movement_type,
            "movement_date": iso(movement.movement_date),
            "amount": money_str(movement.amount),
            "currency": movement.currency,
            "status": movement.status,
            "reconciliation_status": movement.reconciliation_status,
            "settlement_id": movement.settlement_id,
            "financial_title_id": movement.financial_title_id,
            "title_reference": title_reference,
            "participant_name": participant_name,
            "source_type": movement.source_type,
            "source_id": movement.source_id,
            "description": movement.description,
        }
        for movement, account_name, participant_name, title_reference in movement_rows
    ]

    statement_conditions = [
        BankStatementLineDB.company_id == company_id,
        BankStatementLineDB.status != "ignored",
        BankStatementLineDB.line_date >= start_date,
        BankStatementLineDB.line_date <= end_date,
    ]
    statement_conditions.extend(_account_filter(BankStatementLineDB, financial_account_id))
    statement_rows = db.execute(
        select(BankStatementLineDB, FinancialAccountDB.name)
        .join(FinancialAccountDB, FinancialAccountDB.id == BankStatementLineDB.financial_account_id)
        .where(*statement_conditions)
        .order_by(BankStatementLineDB.line_date.asc(), BankStatementLineDB.id.asc())
        .limit(limit)
    ).all()
    statement_lines = [
        {
            "id": line.id,
            "financial_account_id": line.financial_account_id,
            "financial_account_name": account_name,
            "statement_import_id": line.statement_import_id,
            "external_id": line.external_id,
            "line_date": iso(line.line_date),
            "posted_at": iso(line.posted_at),
            "direction": line.direction,
            "amount": money_str(line.amount),
            "description": line.description,
            "document_number": line.document_number,
            "counterparty_name": line.counterparty_name,
            "counterparty_document": line.counterparty_document,
            "bank_reference": line.bank_reference,
            "status": line.status,
            "match_confidence": line.match_confidence,
            "matched_amount": money_str(line.matched_amount),
        }
        for line, account_name in statement_rows
    ]

    match_conditions = [
        ReconciliationMatchDB.company_id == company_id,
        ReconciliationMatchDB.created_at >= start_date,
        ReconciliationMatchDB.created_at < (end_date + timedelta(days=1)),
    ]
    match_conditions.extend(_account_filter(ReconciliationMatchDB, financial_account_id))
    matches = [
        {
            "id": row.id,
            "financial_account_id": row.financial_account_id,
            "statement_line_id": row.statement_line_id,
            "financial_movement_id": row.financial_movement_id,
            "matched_amount": money_str(row.matched_amount),
            "line_amount": money_str(row.line_amount),
            "movement_amount": money_str(row.movement_amount),
            "difference_amount": money_str(row.difference_amount),
            "tolerance_amount": money_str(row.tolerance_amount),
            "status": row.status,
            "confirmation_reason": row.confirmation_reason,
            "created_at": iso(row.created_at),
        }
        for row in db.scalars(select(ReconciliationMatchDB).where(*match_conditions).order_by(ReconciliationMatchDB.created_at.desc()).limit(limit)).all()
    ]

    divergent_conditions = [
        ReconciliationMatchDB.company_id == company_id,
        ReconciliationMatchDB.status == "confirmed_with_difference",
        ReconciliationMatchDB.created_at >= start_date,
        ReconciliationMatchDB.created_at < (end_date + timedelta(days=1)),
    ]
    if financial_account_id:
        divergent_conditions.append(ReconciliationMatchDB.financial_account_id == financial_account_id)
    divergent_matches = [
        {
            "id": row.id,
            "financial_account_id": row.financial_account_id,
            "statement_line_id": row.statement_line_id,
            "financial_movement_id": row.financial_movement_id,
            "matched_amount": money_str(row.matched_amount),
            "line_amount": money_str(row.line_amount),
            "movement_amount": money_str(row.movement_amount),
            "difference_amount": money_str(row.difference_amount),
            "tolerance_amount": money_str(row.tolerance_amount),
            "status": row.status,
            "confirmation_reason": row.confirmation_reason,
            "created_at": iso(row.created_at),
        }
        for row in db.scalars(select(ReconciliationMatchDB).where(*divergent_conditions).order_by(ReconciliationMatchDB.created_at.desc()).limit(limit)).all()
    ]

    return {
        "account_balances": account_rows,
        "expected_receivable_titles": title_rows(direction="receivable", in_period=True),
        "expected_payable_titles": title_rows(direction="payable", in_period=True),
        "overdue_receivable_titles": title_rows(direction="receivable", overdue_only=True),
        "overdue_payable_titles": title_rows(direction="payable", overdue_only=True),
        "settlements": settlements,
        "movements": movements,
        "statement_lines": statement_lines,
        "matches": matches,
        "divergent_matches": divergent_matches,
    }


def reconciliation_status_summary(db: Session, *, company_id: str, start_date: date, end_date: date, financial_account_id: str | None = None) -> dict[str, Any]:
    return {
        "financial_movements": reconciliation_movement_totals(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id),
        "statement_lines": statement_line_totals(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id)["by_status"],
        "matches": match_totals(db, company_id=company_id, start_date=start_date, end_date=end_date, financial_account_id=financial_account_id),
    }
