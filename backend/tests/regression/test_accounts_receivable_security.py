from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB, FinancialTitleHistoryDB
from app.modules.cash.db_models import FinancialMovementDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


def _create_financial_account(company_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/financial/accounts",
        json={
            "company_id": company_id,
            "name": f"Conta AR Seguranca {uuid4().hex[:8]}",
            "account_type": "bank_account",
            "institution_name": "Banco Regressao",
            "opening_balance_amount": "0.00",
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_manual_receivable(company_id: str, participant_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": company_id,
            "participant_id": participant_id,
            "document_reference": f"AR-SEC-{uuid4().hex[:8]}",
            "due_date": "2099-05-08",
            "gross_amount": "100.00",
            "fiscal_status": "not_required",
            "notes": "Titulo para regressao de seguranca.",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def _create_income_category(company_id: str, headers: dict[str, str], *, requires_cost_center: bool = False) -> str:
    response = client.post(
        "/financial/categories",
        json={
            "company_id": company_id,
            "code": f"ARINC{uuid4().hex[:6]}",
            "name": f"Receita Manual AR {uuid4().hex[:8]}",
            "category_type": "income",
            "cash_flow_group": "operating_inflows",
            "affects_cash_flow": True,
            "requires_cost_center": requires_cost_center,
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_cost_center(company_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/financial/cost-centers",
        json={
            "company_id": company_id,
            "code": f"ARCC{uuid4().hex[:6]}",
            "name": f"Centro AR {uuid4().hex[:8]}",
            "center_type": "other",
            "is_analytical": True,
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _get_payment_method(company_id: str, headers: dict[str, str]) -> dict:
    response = client.get("/sales/payment-methods", params={"company_id": company_id}, headers=headers)
    assert response.status_code == 200, response.text
    methods = response.json()["data"]
    assert methods
    return methods[0]


def _create_unique_customer(company_id: str, headers: dict[str, str], name: str) -> str:
    response = client.post(
        "/participants",
        json={
            "company_id": company_id,
            "participant_type": "customer",
            "person_type": "individual",
            "name": name,
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_receivable_cancel_rejects_active_financial_movement_even_without_paid_amount():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id, auth.headers)
    title_id = _create_manual_receivable(auth.company_id, fixtures["participant_id"], auth.headers)
    now = utc_now()

    with SessionLocal() as db:
        movement = FinancialMovementDB(
            id=generate_id("cash"),
            company_id=auth.company_id,
            financial_account_id=account_id,
            direction="inflow",
            movement_type="receipt",
            movement_date=date.today(),
            amount=Decimal("25.00"),
            currency="BRL",
            source_type="regression_receivable_cancel",
            source_id=f"mov-{uuid4().hex}",
            settlement_id=None,
            financial_title_id=title_id,
            participant_id=fixtures["participant_id"],
            description="Movimento ativo sem baixa para testar bloqueio de cancelamento.",
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=None,
            metadata_json={"test": "accounts_receivable_cancel_guard"},
            created_at=now,
            updated_at=now,
        )
        db.add(movement)
        db.commit()

    response = client.post(
        f"/accounts-receivable/titles/{title_id}/cancel",
        json={"reason": "Bloqueio com movimento ativo."},
        headers=auth.headers,
    )
    assert response.status_code == 400, response.text
    assert "movimento financeiro ativo" in response.json()["message"]


def test_receivable_overdue_filter_uses_due_date_not_only_persisted_status():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    title_id = _create_manual_receivable(auth.company_id, fixtures["participant_id"], auth.headers)
    reference = f"OVERDUE-AR-{uuid4().hex[:8]}"

    with SessionLocal() as db:
        title = db.get(FinancialTitleDB, title_id)
        assert title is not None
        title.status = "open"
        title.due_date = today_in_brazil() - timedelta(days=1)
        title.document_reference = reference
        title.updated_at = utc_now()
        db.commit()

    response = client.get(
        "/accounts-receivable/titles",
        params={"company_id": auth.company_id, "status": "overdue", "q": reference, "limit": 200},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    returned_ids = {row["id"] for row in response.json()["data"]}
    assert title_id in returned_ids


def test_receivable_search_matches_participant_snapshot_name():
    auth = get_auth_context(client)
    name = f"Cliente Busca Receber {uuid4().hex[:8]}"
    participant_id = _create_unique_customer(auth.company_id, auth.headers, name)
    title_id = _create_manual_receivable(auth.company_id, participant_id, auth.headers)

    response = client.get(
        "/accounts-receivable/titles",
        params={"company_id": auth.company_id, "q": name, "limit": 200},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    returned_ids = {row["id"] for row in response.json()["data"]}
    assert title_id in returned_ids


def test_receivable_manual_create_accepts_brazilian_money_and_optional_master_records():
    auth = get_auth_context(client)
    participant_id = _create_unique_customer(auth.company_id, auth.headers, f"Cliente Manual AR {uuid4().hex[:8]}")
    category_id = _create_income_category(auth.company_id, auth.headers, requires_cost_center=True)
    cost_center_id = _create_cost_center(auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id, auth.headers)
    payment_method = _get_payment_method(auth.company_id, auth.headers)
    today = today_in_brazil()

    response = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": auth.company_id,
            "participant_id": participant_id,
            "title_type": "manual",
            "source_type": "manual",
            "document_reference": f"MAN-AR-{uuid4().hex[:8]}",
            "issue_date": today.isoformat(),
            "competency_date": today.isoformat(),
            "due_date": (today + timedelta(days=5)).isoformat(),
            "expected_payment_date": (today + timedelta(days=7)).isoformat(),
            "gross_amount": "R$ 1.000,00",
            "discount_amount": "50,00",
            "interest_amount": "10,00",
            "penalty_amount": "5,50",
            "fee_amount": "2,00",
            "payment_method_id": payment_method["id"],
            "financial_category_id": category_id,
            "cost_center_id": cost_center_id,
            "expected_financial_account_id": account_id,
            "fiscal_status": "not_required",
            "notes": "Criacao manual completa de regressao.",
        },
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["gross_amount"] == "1000.00"
    assert data["discount_amount"] == "50.00"
    assert data["interest_amount"] == "10.00"
    assert data["penalty_amount"] == "5.50"
    assert data["fee_amount"] == "2.00"
    assert data["net_amount"] == "963.50"
    assert data["open_amount"] == "963.50"
    assert data["payment_method_id"] == payment_method["id"]
    assert data["payment_method_name"] == payment_method["name"]
    assert data["financial_category_id"] == category_id
    assert data["cost_center_id"] == cost_center_id
    assert data["expected_financial_account_id"] == account_id
    assert data["fiscal_status"] == "not_required"

    with SessionLocal() as db:
        history = db.scalar(
            select(FinancialTitleHistoryDB)
            .where(FinancialTitleHistoryDB.financial_title_id == data["id"])
            .order_by(FinancialTitleHistoryDB.occurred_at.desc())
            .limit(1)
        )
        assert history is not None
        assert history.actor_id == auth.user_id

