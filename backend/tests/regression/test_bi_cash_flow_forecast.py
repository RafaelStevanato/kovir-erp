from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.cash.db_models import FinancialAccountBalanceDB
from app.modules.financial.db_models import FinancialAccountDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


@pytest.fixture(autouse=True)
def _enable_internal_bi_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enable_internal_modules", True)


def _money(value: str) -> Decimal:
    return Decimal(str(value))


def _add_title(*, company_id: str, participant_id: str, account_id: str, direction: str, due_date, amount: str) -> str:
    now = utc_now()
    title_id = generate_id("ar" if direction == "receivable" else "ap")
    with SessionLocal() as db:
        db.add(
            FinancialTitleDB(
                id=title_id,
                company_id=company_id,
                direction=direction,
                title_type="manual",
                source_type="bi_forecast_test",
                source_id=f"forecast-{uuid4().hex}",
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
                document_reference=f"BI13-{uuid4().hex[:8]}",
                installment_number=1,
                installment_total=1,
                issue_date=due_date,
                competency_date=due_date,
                due_date=due_date,
                expected_payment_date=due_date,
                gross_amount=Decimal(amount),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                net_amount=Decimal(amount),
                paid_amount=Decimal("0.00"),
                open_amount=Decimal(amount),
                status="open",
                collection_status="not_started",
                fiscal_status="not_required",
                notes="Regressao BI: previsao 13 semanas.",
                metadata_json={},
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                deleted_at=None,
            )
        )
        db.commit()
    return title_id


def _create_account(company_id: str, *, balance: str) -> str:
    now = utc_now()
    account_id = generate_id("acc")
    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta forecast {uuid4().hex[:8]}",
                account_type="bank",
                institution_name="Banco Regressao",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal(balance),
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
                current_balance_amount=Decimal(balance),
                last_movement_id=None,
                updated_at=now,
            )
        )
        db.commit()
    return account_id


def test_bi_cash_flow_13w_uses_account_filter_overdue_counts_and_aligned_export() -> None:
    auth = get_auth_context(client)
    participant_id = ensure_service_fixtures(client, auth.company_id, auth.headers)["participant_id"]
    monday = today_in_brazil() - timedelta(days=today_in_brazil().weekday())
    account_id = _create_account(auth.company_id, balance="200.00")
    other_account_id = _create_account(auth.company_id, balance="999.00")

    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=account_id, direction="receivable", due_date=monday - timedelta(days=1), amount="50.00")
    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=account_id, direction="payable", due_date=monday - timedelta(days=1), amount="20.00")
    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=account_id, direction="receivable", due_date=monday + timedelta(days=1), amount="100.00")
    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=account_id, direction="payable", due_date=monday + timedelta(days=2), amount="30.00")
    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=account_id, direction="receivable", due_date=monday + timedelta(days=8), amount="70.00")
    _add_title(company_id=auth.company_id, participant_id=participant_id, account_id=other_account_id, direction="receivable", due_date=monday + timedelta(days=1), amount="999.00")

    response = client.get(
        "/bi/cash-flow-13w",
        params={
            "company_id": auth.company_id,
            "weeks": 2,
            "start_date": monday.isoformat(),
            "financial_account_id": account_id,
        },
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["financial_account_id"] == account_id
    assert data["starting_week"] == monday.isoformat()
    assert data["opening_balance_amount"] == "200.00"
    assert data["overdue_inflow_amount"] == "50.00"
    assert data["overdue_outflow_amount"] == "20.00"
    assert data["overdue_inflow_count"] == 1
    assert data["overdue_outflow_count"] == 1

    week_1 = data["weekly"][0]
    assert week_1["week_index"] == 1
    assert _money(week_1["expected_inflow_amount"]) == Decimal("150.00")
    assert week_1["expected_inflow_count"] == 2
    assert _money(week_1["expected_outflow_amount"]) == Decimal("50.00")
    assert week_1["expected_outflow_count"] == 2
    assert _money(week_1["projected_balance_amount"]) == Decimal("300.00")

    week_2 = data["weekly"][1]
    assert week_2["week_index"] == 2
    assert _money(week_2["expected_inflow_amount"]) == Decimal("70.00")
    assert week_2["expected_inflow_count"] == 1
    assert _money(week_2["projected_balance_amount"]) == Decimal("370.00")

    csv_response = client.get(
        "/bi/exports/cash-flow-13w.csv",
        params={
            "company_id": auth.company_id,
            "weeks": 2,
            "start_date": monday.isoformat(),
            "financial_account_id": account_id,
        },
        headers=auth.headers,
    )
    assert csv_response.status_code == 200, csv_response.text
    csv_text = csv_response.content.decode("utf-8-sig")
    assert "week_index" in csv_text
    assert "150.00" in csv_text
    assert "999.00" not in csv_text

    category_response = client.get(
        "/bi/cash-flow-by-category",
        params={
            "company_id": auth.company_id,
            "start_date": monday.isoformat(),
            "end_date": (monday + timedelta(days=6)).isoformat(),
            "financial_account_id": account_id,
        },
        headers=auth.headers,
    )
    assert category_response.status_code == 200, category_response.text
    assert category_response.json()["data"]["financial_account_id"] == account_id

    category_csv = client.get(
        "/bi/exports/cash-flow-by-category.csv",
        params={
            "company_id": auth.company_id,
            "start_date": monday.isoformat(),
            "end_date": (monday + timedelta(days=6)).isoformat(),
            "financial_account_id": account_id,
        },
        headers=auth.headers,
    )
    assert category_csv.status_code == 200, category_csv.text
