from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.cash.db_models import FinancialAccountBalanceDB, FinancialMovementDB, SettlementDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.reconciliation.db_models import BankStatementLineDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def _before_cursor_execute(self, *_args) -> None:
        self.count += 1

    def __enter__(self) -> "_QueryCounter":
        event.listen(engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(engine, "before_cursor_execute", self._before_cursor_execute)


def _money(value: str) -> Decimal:
    return Decimal(str(value))


def _create_cash_flow_overview_fixture(company_id: str, participant_id: str) -> dict[str, str]:
    now = utc_now()
    today = today_in_brazil()
    account_id = generate_id("acc")
    legacy_account_id = generate_id("bankacc")
    receivable_id = generate_id("ar")
    payable_id = generate_id("ap")
    overdue_receivable_id = generate_id("ar")
    overdue_payable_id = generate_id("ap")
    inflow_settlement_id = generate_id("sett")
    outflow_settlement_id = generate_id("sett")
    inflow_movement_id = generate_id("cash")
    reversal_movement_id = generate_id("cash")
    pending_statement_id = generate_id("stmtln")
    ignored_statement_id = generate_id("stmtln")

    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta fluxo {uuid4().hex[:8]}",
                account_type="bank",
                institution_name="Banco Regressao",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("10.00"),
                is_default_receivable=False,
                is_default_payable=False,
                status="active",
                notes=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        db.add(
            FinancialAccountDB(
                id=legacy_account_id,
                company_id=company_id,
                name=f"Conta legado fluxo {uuid4().hex[:8]}",
                account_type="cash",
                institution_name=None,
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("20.00"),
                is_default_receivable=False,
                is_default_payable=False,
                status="active",
                notes=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        db.flush()
        db.add(
            FinancialAccountBalanceDB(
                id=generate_id("cashbal"),
                company_id=company_id,
                financial_account_id=account_id,
                current_balance_amount=Decimal("150.00"),
                last_movement_id=None,
                updated_at=now,
            )
        )
        db.add_all(
            [
                FinancialTitleDB(
                    id=receivable_id,
                    company_id=company_id,
                    direction="receivable",
                    title_type="manual",
                    source_type="cash_flow_test",
                    source_id=f"rec-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"CF-REC-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=today,
                    expected_payment_date=today,
                    gross_amount=Decimal("100.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("100.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("100.00"),
                    status="open",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao fluxo de caixa: entrada prevista.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=payable_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="cash_flow_test",
                    source_id=f"pay-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"CF-PAY-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=today,
                    expected_payment_date=today,
                    gross_amount=Decimal("60.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("60.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("60.00"),
                    status="open",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao fluxo de caixa: saida prevista.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=overdue_receivable_id,
                    company_id=company_id,
                    direction="receivable",
                    title_type="manual",
                    source_type="cash_flow_test",
                    source_id=f"over-rec-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"CF-OVR-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today - timedelta(days=2),
                    competency_date=today - timedelta(days=2),
                    due_date=today - timedelta(days=1),
                    expected_payment_date=None,
                    gross_amount=Decimal("25.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("25.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("25.00"),
                    status="overdue",
                    collection_status="in_collection",
                    fiscal_status="not_required",
                    notes="Regressao fluxo de caixa: recebido vencido.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=overdue_payable_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="cash_flow_test",
                    source_id=f"over-pay-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"CF-OVP-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today - timedelta(days=2),
                    competency_date=today - timedelta(days=2),
                    due_date=today - timedelta(days=1),
                    expected_payment_date=None,
                    gross_amount=Decimal("35.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("35.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("35.00"),
                    status="overdue",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao fluxo de caixa: pagar vencido.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                SettlementDB(
                    id=inflow_settlement_id,
                    company_id=company_id,
                    direction="inflow",
                    settlement_type="receipt",
                    financial_title_id=receivable_id,
                    participant_id=participant_id,
                    financial_account_id=account_id,
                    payment_method_id=None,
                    settlement_date=today,
                    competency_date=today,
                    received_amount=Decimal("40.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    title_settled_amount=Decimal("40.00"),
                    movement_amount=Decimal("40.00"),
                    source_type="cash_flow_test",
                    source_id=f"sett-in-{uuid4().hex}",
                    evidence_reference="CF-IN-001",
                    notes=None,
                    status="active",
                    reversal_of_settlement_id=None,
                    reversed_at=None,
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                ),
                SettlementDB(
                    id=outflow_settlement_id,
                    company_id=company_id,
                    direction="outflow",
                    settlement_type="payment",
                    financial_title_id=payable_id,
                    participant_id=participant_id,
                    financial_account_id=account_id,
                    payment_method_id=None,
                    settlement_date=today,
                    competency_date=today,
                    received_amount=Decimal("30.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    title_settled_amount=Decimal("30.00"),
                    movement_amount=Decimal("30.00"),
                    source_type="cash_flow_test",
                    source_id=f"sett-out-{uuid4().hex}",
                    evidence_reference="CF-OUT-001",
                    notes=None,
                    status="active",
                    reversal_of_settlement_id=None,
                    reversed_at=None,
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                FinancialMovementDB(
                    id=inflow_movement_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    direction="inflow",
                    movement_type="receipt",
                    movement_date=today,
                    amount=Decimal("40.00"),
                    currency="BRL",
                    source_type="settlement",
                    source_id=inflow_settlement_id,
                    settlement_id=inflow_settlement_id,
                    financial_title_id=receivable_id,
                    participant_id=participant_id,
                    description="Regressao fluxo de caixa: movimento valido.",
                    status="posted",
                    reconciliation_status="pending",
                    reversal_of_movement_id=None,
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                ),
                FinancialMovementDB(
                    id=reversal_movement_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    direction="inflow",
                    movement_type="receipt_reversal",
                    movement_date=today,
                    amount=Decimal("999.00"),
                    currency="BRL",
                    source_type="settlement_reversal",
                    source_id=f"reversal-{uuid4().hex}",
                    settlement_id=inflow_settlement_id,
                    financial_title_id=receivable_id,
                    participant_id=participant_id,
                    description="Regressao fluxo de caixa: estorno nao deve somar.",
                    status="posted",
                    reconciliation_status="pending",
                    reversal_of_movement_id=inflow_movement_id,
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.add_all(
            [
                BankStatementLineDB(
                    id=pending_statement_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    statement_import_id=None,
                    external_id=f"stmt-pending-{uuid4().hex}",
                    line_date=today,
                    posted_at=None,
                    direction="inflow",
                    amount=Decimal("12.00"),
                    description="Regressao fluxo de caixa: extrato pendente.",
                    document_number=None,
                    counterparty_name="Cliente Teste",
                    counterparty_document=None,
                    bank_reference="BANK-OK",
                    status="pending",
                    match_confidence=None,
                    matched_amount=Decimal("0.00"),
                    ignored_reason=None,
                    raw_payload_json={},
                    created_at=now,
                    updated_at=now,
                ),
                BankStatementLineDB(
                    id=ignored_statement_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    statement_import_id=None,
                    external_id=f"stmt-ignored-{uuid4().hex}",
                    line_date=today,
                    posted_at=None,
                    direction="inflow",
                    amount=Decimal("999.00"),
                    description="Regressao fluxo de caixa: extrato ignorado nao deve somar.",
                    document_number=None,
                    counterparty_name="Cliente Ignorado",
                    counterparty_document=None,
                    bank_reference="BANK-IGN",
                    status="ignored",
                    match_confidence=None,
                    matched_amount=Decimal("0.00"),
                    ignored_reason="Ignorado na conciliacao.",
                    raw_payload_json={},
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.commit()

    return {
        "account_id": account_id,
        "legacy_account_id": legacy_account_id,
        "receivable_id": receivable_id,
        "payable_id": payable_id,
        "overdue_receivable_id": overdue_receivable_id,
        "overdue_payable_id": overdue_payable_id,
        "inflow_settlement_id": inflow_settlement_id,
        "outflow_settlement_id": outflow_settlement_id,
        "inflow_movement_id": inflow_movement_id,
        "reversal_movement_id": reversal_movement_id,
        "pending_statement_id": pending_statement_id,
        "ignored_statement_id": ignored_statement_id,
    }


def test_cash_flow_overview_uses_clean_totals_and_export_evidence() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    today = today_in_brazil().isoformat()

    before = client.get(
        "/cash-flow/summary",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_data = before.json()["data"]

    before_daily = client.get(
        "/cash-flow/daily",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert before_daily.status_code == 200, before_daily.text
    before_day = next(row for row in before_daily.json()["data"] if row["date"] == today)

    created = _create_cash_flow_overview_fixture(auth.company_id, fixtures["participant_id"])

    after = client.get(
        "/cash-flow/summary",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    data = after.json()["data"]

    assert data["reference_date"] == today
    assert _money(data["expected_inflow_amount"]) >= _money(before_data["expected_inflow_amount"]) + Decimal("100.00")
    assert _money(data["expected_outflow_amount"]) >= _money(before_data["expected_outflow_amount"]) + Decimal("60.00")
    assert _money(data["overdue_receivable_amount"]) >= _money(before_data["overdue_receivable_amount"]) + Decimal("25.00")
    assert _money(data["overdue_payable_amount"]) >= _money(before_data["overdue_payable_amount"]) + Decimal("35.00")
    assert _money(data["received_amount"]) >= _money(before_data["received_amount"]) + Decimal("40.00")
    assert _money(data["paid_amount"]) >= _money(before_data.get("paid_amount", "0.00")) + Decimal("30.00")
    assert _money(data["realized_inflow_amount"]) == _money(before_data["realized_inflow_amount"]) + Decimal("40.00")
    assert _money(data["statement_inflow_amount"]) == _money(before_data["statement_inflow_amount"]) + Decimal("12.00")

    daily = client.get(
        "/cash-flow/daily",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert daily.status_code == 200, daily.text
    day = next(row for row in daily.json()["data"] if row["date"] == today)
    assert _money(day["expected_inflow_amount"]) >= _money(before_day["expected_inflow_amount"]) + Decimal("100.00")
    assert _money(day["expected_outflow_amount"]) >= _money(before_day["expected_outflow_amount"]) + Decimal("60.00")
    assert _money(day["received_amount"]) >= _money(before_day["received_amount"]) + Decimal("40.00")
    assert _money(day["paid_amount"]) >= _money(before_day.get("paid_amount", "0.00")) + Decimal("30.00")
    assert _money(day["movement_inflow_amount"]) == _money(before_day["movement_inflow_amount"]) + Decimal("40.00")
    assert _money(day["statement_inflow_amount"]) == _money(before_day["statement_inflow_amount"]) + Decimal("12.00")
    assert day["unreconciled_movements"] == before_day["unreconciled_movements"] + 1
    assert day["pending_statement_lines"] == before_day["pending_statement_lines"] + 1

    accounts = client.get(
        "/cash-flow/accounts",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "financial_account_id": created["account_id"],
        },
        headers=auth.headers,
    )
    assert accounts.status_code == 200, accounts.text
    account_rows = accounts.json()["data"]
    assert len(account_rows) == 1
    account = account_rows[0]
    assert account["financial_account_id"] == created["account_id"]
    assert _money(account["current_balance_amount"]) == Decimal("150.00")
    assert _money(account["period_inflow_amount"]) == Decimal("40.00")
    assert _money(account["period_outflow_amount"]) == Decimal("0.00")
    assert _money(account["period_net_amount"]) == Decimal("40.00")
    assert account["reconciliation_by_status"]["pending"]["count"] == 1
    assert _money(account["reconciliation_by_status"]["pending"]["amount"]) == Decimal("40.00")
    assert account["statement_by_status"]["pending"]["count"] == 1
    assert _money(account["statement_by_status"]["pending"]["amount"]) == Decimal("12.00")
    assert _money(account["statement_by_direction"]["inflow"]) == Decimal("12.00")

    legacy_accounts = client.get(
        "/cash-flow/accounts",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "financial_account_id": created["legacy_account_id"],
        },
        headers=auth.headers,
    )
    assert legacy_accounts.status_code == 200, legacy_accounts.text
    legacy_account_rows = legacy_accounts.json()["data"]
    assert len(legacy_account_rows) == 1
    assert legacy_account_rows[0]["financial_account_id"] == created["legacy_account_id"]
    assert _money(legacy_account_rows[0]["current_balance_amount"]) == Decimal("20.00")

    legacy_evidence = client.get(
        "/cash-flow/overview-evidence",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "financial_account_id": created["legacy_account_id"],
        },
        headers=auth.headers,
    )
    assert legacy_evidence.status_code == 200, legacy_evidence.text
    assert created["legacy_account_id"] in {row["financial_account_id"] for row in legacy_evidence.json()["data"]["account_balances"]}

    pending = client.get(
        "/cash-flow/pending",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "financial_account_id": created["account_id"],
            "limit": 100,
        },
        headers=auth.headers,
    )
    assert pending.status_code == 200, pending.text
    pending_data = pending.json()["data"]
    assert created["overdue_receivable_id"] in {row["id"] for row in pending_data["overdue_titles"]}
    assert created["receivable_id"] in {row["id"] for row in pending_data["upcoming_titles"]}
    assert created["overdue_payable_id"] in {row["id"] for row in pending_data["overdue_payables"]}
    assert created["payable_id"] in {row["id"] for row in pending_data["upcoming_payables"]}
    assert created["inflow_movement_id"] in {row["id"] for row in pending_data["unreconciled_movements"]}
    assert created["reversal_movement_id"] not in {row["id"] for row in pending_data["unreconciled_movements"]}
    assert created["pending_statement_id"] in {row["id"] for row in pending_data["unmatched_statement_lines"]}
    assert created["ignored_statement_id"] not in {row["id"] for row in pending_data["unmatched_statement_lines"]}

    reconciliation = client.get(
        "/cash-flow/reconciliation-status",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "financial_account_id": created["account_id"],
        },
        headers=auth.headers,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    reconciliation_data = reconciliation.json()["data"]
    assert reconciliation_data["financial_movements"]["pending"]["count"] == 1
    assert _money(reconciliation_data["financial_movements"]["pending"]["amount"]) == Decimal("40.00")
    assert reconciliation_data["statement_lines"]["pending"]["count"] == 1
    assert _money(reconciliation_data["statement_lines"]["pending"]["amount"]) == Decimal("12.00")
    assert "ignored" not in reconciliation_data["statement_lines"]

    evidence = client.get(
        "/cash-flow/overview-evidence",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert evidence.status_code == 200, evidence.text
    evidence_data = evidence.json()["data"]

    assert "matches" in evidence_data
    assert created["account_id"] in {row["financial_account_id"] for row in evidence_data["account_balances"]}
    assert created["receivable_id"] in {row["id"] for row in evidence_data["expected_receivable_titles"]}
    assert created["payable_id"] in {row["id"] for row in evidence_data["expected_payable_titles"]}
    assert created["overdue_receivable_id"] in {row["id"] for row in evidence_data["overdue_receivable_titles"]}
    assert created["overdue_payable_id"] in {row["id"] for row in evidence_data["overdue_payable_titles"]}
    assert created["inflow_settlement_id"] in {row["id"] for row in evidence_data["settlements"]}
    assert created["outflow_settlement_id"] in {row["id"] for row in evidence_data["settlements"]}
    assert created["inflow_movement_id"] in {row["id"] for row in evidence_data["movements"]}
    assert created["reversal_movement_id"] not in {row["id"] for row in evidence_data["movements"]}
    assert created["pending_statement_id"] in {row["id"] for row in evidence_data["statement_lines"]}
    assert created["ignored_statement_id"] not in {row["id"] for row in evidence_data["statement_lines"]}


def test_cash_flow_accounts_is_paginated_and_uses_constant_query_budget() -> None:
    auth = get_auth_context(client)
    now = utc_now()
    today = today_in_brazil().isoformat()

    with SessionLocal() as db:
        account_ids: list[str] = []
        for index in range(8):
            account_id = generate_id("bankacc")
            account_ids.append(account_id)
            db.add(
                FinancialAccountDB(
                    id=account_id,
                    company_id=auth.company_id,
                    name=f"Conta fluxo performance {index:02d} {uuid4().hex[:6]}",
                    account_type="cash",
                    institution_name=None,
                    branch_number=None,
                    account_number=None,
                    account_digit=None,
                    pix_key=None,
                    pix_key_type=None,
                    currency="BRL",
                    opening_balance_amount=Decimal("10.00"),
                    is_default_receivable=False,
                    is_default_payable=False,
                    status="active",
                    notes=None,
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                )
            )
        db.commit()

    with _QueryCounter() as counter:
        first_page = client.get(
            "/cash-flow/accounts",
            params={"company_id": auth.company_id, "start_date": today, "end_date": today, "limit": 3, "offset": 0},
            headers=auth.headers,
        )
    assert first_page.status_code == 200, first_page.text
    first_rows = first_page.json()["data"]
    assert len(first_rows) == 3
    assert counter.count <= 16

    second_page = client.get(
        "/cash-flow/accounts",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today, "limit": 3, "offset": 3},
        headers=auth.headers,
    )
    assert second_page.status_code == 200, second_page.text
    assert len(second_page.json()["data"]) == 3
    assert {row["financial_account_id"] for row in first_rows}.isdisjoint({row["financial_account_id"] for row in second_page.json()["data"]})
