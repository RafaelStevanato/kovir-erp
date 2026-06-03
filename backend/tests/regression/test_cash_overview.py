from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.cash.db_models import FinancialMovementDB
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


def _money(value: object) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _summary(auth) -> dict:
    response = client.get(
        "/cash/summary",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _create_financial_account(auth, opening_balance: str = "0.00") -> str:
    response = client.post(
        "/financial/accounts",
        json={
            "company_id": auth.company_id,
            "name": f"Conta caixa overview {uuid4().hex[:8]}",
            "account_type": "bank_account",
            "institution_name": "Banco Regressao",
            "opening_balance_amount": opening_balance,
            "status": "active",
        },
        headers=auth.headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_receivable_title(auth, participant_id: str, amount: str = "100.00", due_date: str = "2099-03-10") -> str:
    response = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": auth.company_id,
            "participant_id": participant_id,
            "document_reference": f"AR-CASH-OVERVIEW-{uuid4().hex[:8]}",
            "due_date": due_date,
            "gross_amount": amount,
            "fiscal_status": "not_required",
            "notes": "Titulo para regressao da visao geral de caixa.",
        },
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_cash_overview_summary_uses_active_movements_balance_and_reversal() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)

    before = _summary(auth)
    account_id = _create_financial_account(auth, opening_balance="25.00")
    after_account = _summary(auth)

    assert _money(after_account["internal_balance_total"]) == _money(before["internal_balance_total"]) + Decimal("25.00")
    assert after_account["financial_account_count"] >= before["financial_account_count"] + 1

    title_id = _create_receivable_title(auth, fixtures["participant_id"])
    settlement_response = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "90.00",
            "discount_amount": "10.00",
            "interest_amount": "5.00",
            "fee_amount": "2.00",
            "source_type": "manual",
            "source_id": f"cash-overview-{uuid4().hex[:12]}",
            "notes": "Baixa para regressao da visao geral de caixa.",
        },
        headers=auth.headers,
    )
    assert settlement_response.status_code == 200, settlement_response.text
    settlement_id = settlement_response.json()["data"]["settlement"]["id"]

    after_settlement = _summary(auth)
    assert _money(after_settlement["received_amount"]) == _money(after_account["received_amount"]) + Decimal("90.00")
    assert _money(after_settlement["discount_amount"]) == _money(after_account["discount_amount"]) + Decimal("10.00")
    assert _money(after_settlement["inflow_amount"]) == _money(after_account["inflow_amount"]) + Decimal("93.00")
    assert _money(after_settlement["net_internal_balance_delta"]) == _money(after_account["net_internal_balance_delta"]) + Decimal("93.00")
    assert _money(after_settlement["internal_balance_total"]) == _money(after_account["internal_balance_total"]) + Decimal("93.00")
    assert after_settlement["pending_reconciliation_count"] == after_account["pending_reconciliation_count"] + 1

    reversal_response = client.post(
        f"/cash/settlements/{settlement_id}/reverse",
        json={"reason": "Estorno para regressao da visao geral de caixa."},
        headers=auth.headers,
    )
    assert reversal_response.status_code == 200, reversal_response.text

    after_reversal = _summary(auth)
    assert _money(after_reversal["received_amount"]) == _money(after_account["received_amount"])
    assert _money(after_reversal["discount_amount"]) == _money(after_account["discount_amount"])
    assert _money(after_reversal["inflow_amount"]) == _money(after_account["inflow_amount"])
    assert _money(after_reversal["net_internal_balance_delta"]) == _money(after_account["net_internal_balance_delta"])
    assert _money(after_reversal["internal_balance_total"]) == _money(after_account["internal_balance_total"])
    assert after_reversal["pending_reconciliation_count"] == after_account["pending_reconciliation_count"]


def test_cash_receive_accepts_overdue_and_partially_received_titles() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth)

    overdue_title_id = _create_receivable_title(
        auth,
        fixtures["participant_id"],
        amount="30.00",
        due_date=(date.today() - timedelta(days=1)).isoformat(),
    )
    overdue_settlement = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": overdue_title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "30.00",
            "source_type": "manual",
            "source_id": f"cash-overdue-{uuid4().hex[:12]}",
        },
        headers=auth.headers,
    )
    assert overdue_settlement.status_code == 200, overdue_settlement.text
    assert overdue_settlement.json()["data"]["title"]["status"] == "received"

    partial_title_id = _create_receivable_title(auth, fixtures["participant_id"], amount="100.00")
    first_settlement = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": partial_title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "40.00",
            "source_type": "manual",
            "source_id": f"cash-partial-1-{uuid4().hex[:12]}",
        },
        headers=auth.headers,
    )
    assert first_settlement.status_code == 200, first_settlement.text
    assert first_settlement.json()["data"]["title"]["status"] == "partially_received"
    assert _money(first_settlement.json()["data"]["title"]["open_amount"]) == Decimal("60.00")

    second_settlement = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": partial_title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "60.00",
            "source_type": "manual",
            "source_id": f"cash-partial-2-{uuid4().hex[:12]}",
        },
        headers=auth.headers,
    )
    assert second_settlement.status_code == 200, second_settlement.text
    assert second_settlement.json()["data"]["title"]["status"] == "received"
    assert _money(second_settlement.json()["data"]["title"]["open_amount"]) == Decimal("0.00")


def test_cash_settlement_list_is_enriched_and_reversal_blocks_reconciled_movement() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth)
    title_id = _create_receivable_title(auth, fixtures["participant_id"], amount="55.00")

    settlement_response = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "55.00",
            "source_type": "manual",
            "source_id": f"cash-enriched-{uuid4().hex[:12]}",
            "evidence_reference": "REC-TEST-001",
        },
        headers=auth.headers,
    )
    assert settlement_response.status_code == 200, settlement_response.text
    settlement_data = settlement_response.json()["data"]
    settlement_id = settlement_data["settlement"]["id"]
    movement_id = settlement_data["movement"]["id"]

    list_response = client.get(
        "/cash/settlements",
        params={"company_id": auth.company_id, "financial_title_id": title_id},
        headers=auth.headers,
    )
    assert list_response.status_code == 200, list_response.text
    rows = list_response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["financial_title_reference"].startswith("AR-CASH-OVERVIEW-")
    assert rows[0]["participant_name"]
    assert rows[0]["financial_title_installment_number"] == 1
    assert rows[0]["financial_title_installment_total"] == 1

    movements_response = client.get(
        "/cash/movements",
        params={"company_id": auth.company_id, "financial_account_id": account_id},
        headers=auth.headers,
    )
    assert movements_response.status_code == 200, movements_response.text
    movement_rows = movements_response.json()["data"]
    movement_row = next(row for row in movement_rows if row["id"] == movement_id)
    assert movement_row["financial_account_name"]
    assert movement_row["financial_title_reference"].startswith("AR-CASH-OVERVIEW-")
    assert movement_row["participant_name"]
    assert movement_row["settlement_status"] == "active"
    assert movement_row["settlement_date"] == date.today().isoformat()

    with SessionLocal() as db:
        movement = db.scalar(select(FinancialMovementDB).where(FinancialMovementDB.id == movement_id))
        assert movement is not None
        movement.reconciliation_status = "matched"
        db.commit()

    matched_movements_response = client.get(
        "/cash/movements",
        params={"company_id": auth.company_id, "financial_account_id": account_id, "reconciliation_status": "matched"},
        headers=auth.headers,
    )
    assert matched_movements_response.status_code == 200, matched_movements_response.text
    assert movement_id in {row["id"] for row in matched_movements_response.json()["data"]}

    reversal_response = client.post(
        f"/cash/settlements/{settlement_id}/reverse",
        json={"reason": "Tentativa de estorno de baixa conciliada."},
        headers=auth.headers,
    )
    assert reversal_response.status_code == 400, reversal_response.text
    assert "conciliada" in reversal_response.text.lower()


def test_cash_lists_apply_server_filters_pagination_and_constant_query_budget() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth)
    source_ids: list[str] = []

    for index in range(4):
        title_id = _create_receivable_title(auth, fixtures["participant_id"], amount=f"{40 + index}.00")
        source_id = f"cash-filter-{uuid4().hex[:12]}"
        source_ids.append(source_id)
        response = client.post(
            "/cash/settlements",
            json={
                "company_id": auth.company_id,
                "financial_title_id": title_id,
                "financial_account_id": account_id,
                "settlement_date": date.today().isoformat(),
                "competency_date": date.today().isoformat(),
                "received_amount": f"{40 + index}.00",
                "source_type": "manual",
                "source_id": source_id,
                "evidence_reference": f"PERF-{index}",
            },
            headers=auth.headers,
        )
        assert response.status_code == 200, response.text

    manual_response = client.post(
        "/cash/movements",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "direction": "outflow",
            "movement_type": "fee",
            "movement_date": date.today().isoformat(),
            "amount": "7.00",
            "description": "Tarifa para regressao de filtros e paginacao.",
        },
        headers=auth.headers,
    )
    assert manual_response.status_code == 200, manual_response.text
    manual_movement_id = manual_response.json()["data"]["movement"]["id"]

    with _QueryCounter() as counter:
        settlements_response = client.get(
            "/cash/settlements",
            params={"company_id": auth.company_id, "financial_account_id": account_id, "payment_method_id": "__none__", "limit": 2, "offset": 0},
            headers=auth.headers,
        )
    assert settlements_response.status_code == 200, settlements_response.text
    settlements_page = settlements_response.json()["data"]
    assert len(settlements_page) == 2
    assert all(row["financial_account_id"] == account_id for row in settlements_page)
    assert all(row["payment_method_id"] is None for row in settlements_page)
    assert counter.count <= 16

    second_page = client.get(
        "/cash/settlements",
        params={"company_id": auth.company_id, "financial_account_id": account_id, "limit": 2, "offset": 2},
        headers=auth.headers,
    )
    assert second_page.status_code == 200, second_page.text
    assert {row["id"] for row in settlements_page}.isdisjoint({row["id"] for row in second_page.json()["data"]})

    q_response = client.get(
        "/cash/settlements",
        params={"company_id": auth.company_id, "financial_account_id": account_id, "q": source_ids[0], "limit": 10},
        headers=auth.headers,
    )
    assert q_response.status_code == 200, q_response.text
    assert len(q_response.json()["data"]) == 1
    assert q_response.json()["data"][0]["source_id"] == source_ids[0]

    with _QueryCounter() as movement_counter:
        movement_response = client.get(
            "/cash/movements",
            params={"company_id": auth.company_id, "financial_account_id": account_id, "direction": "outflow", "movement_type": "fee", "limit": 2},
            headers=auth.headers,
        )
    assert movement_response.status_code == 200, movement_response.text
    movement_rows = movement_response.json()["data"]
    assert manual_movement_id in {row["id"] for row in movement_rows}
    assert all(row["direction"] == "outflow" for row in movement_rows)
    assert all(row["movement_type"] == "fee" for row in movement_rows)
    assert movement_counter.count <= 16


def test_cash_manual_movement_requires_safe_payload_and_can_be_reversed() -> None:
    auth = get_auth_context(client)
    account_id = _create_financial_account(auth, opening_balance="10.00")

    missing_reason = client.post(
        "/cash/movements",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "direction": "inflow",
            "movement_type": "adjustment",
            "movement_date": date.today().isoformat(),
            "amount": "15.00",
            "description": " ",
        },
        headers=auth.headers,
    )
    assert missing_reason.status_code == 422, missing_reason.text

    unsafe_type = client.post(
        "/cash/movements",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "direction": "inflow",
            "movement_type": "transfer",
            "movement_date": date.today().isoformat(),
            "amount": "15.00",
            "description": "Tentativa de tipo inseguro para regressao.",
        },
        headers=auth.headers,
    )
    assert unsafe_type.status_code == 422, unsafe_type.text

    movement_response = client.post(
        "/cash/movements",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "direction": "inflow",
            "movement_type": "adjustment",
            "movement_date": date.today().isoformat(),
            "amount": "15.00",
            "description": "Ajuste manual operacional para regressao.",
        },
        headers=auth.headers,
    )
    assert movement_response.status_code == 200, movement_response.text
    movement_data = movement_response.json()["data"]
    movement_id = movement_data["movement"]["id"]
    assert movement_data["movement"]["source_type"] == "manual"
    assert _money(movement_data["balance"]["current_balance_amount"]) == Decimal("25.00")

    reverse_response = client.post(
        f"/cash/movements/{movement_id}/reverse",
        json={"reason": "Estorno de ajuste manual para regressao."},
        headers=auth.headers,
    )
    assert reverse_response.status_code == 200, reverse_response.text
    reverse_data = reverse_response.json()["data"]
    assert reverse_data["movement"]["status"] == "reversed"
    assert reverse_data["movement"]["reconciliation_status"] == "reversed"
    assert reverse_data["reversal_movement"]["direction"] == "outflow"
    assert reverse_data["reversal_movement"]["reversal_of_movement_id"] == movement_id
    assert _money(reverse_data["balance"]["current_balance_amount"]) == Decimal("10.00")


def test_cash_manual_movement_reversal_blocks_reconciled_movement() -> None:
    auth = get_auth_context(client)
    account_id = _create_financial_account(auth)

    movement_response = client.post(
        "/cash/movements",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "direction": "outflow",
            "movement_type": "fee",
            "movement_date": date.today().isoformat(),
            "amount": "8.00",
            "description": "Tarifa bancaria manual para regressao.",
        },
        headers=auth.headers,
    )
    assert movement_response.status_code == 200, movement_response.text
    movement_id = movement_response.json()["data"]["movement"]["id"]

    with SessionLocal() as db:
        movement = db.scalar(select(FinancialMovementDB).where(FinancialMovementDB.id == movement_id))
        assert movement is not None
        movement.reconciliation_status = "matched"
        db.commit()

    reverse_response = client.post(
        f"/cash/movements/{movement_id}/reverse",
        json={"reason": "Tentativa de estorno de movimento conciliado."},
        headers=auth.headers,
    )
    assert reverse_response.status_code == 400, reverse_response.text
    assert "conciliado" in reverse_response.text.lower()
