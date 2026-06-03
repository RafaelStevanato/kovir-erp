from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.modules.cash.db_models import FinancialAccountBalanceDB
from app.shared.datetime import utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


def _name(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def _create_account(headers: dict[str, str], company_id: str, **overrides):
    payload = {
        "company_id": company_id,
        "name": _name("Conta regressao"),
        "account_type": "cash",
        "opening_balance_amount": "0",
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/accounts", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_participant(headers: dict[str, str], company_id: str) -> str:
    response = client.post(
        "/participants",
        json={
            "company_id": company_id,
            "participant_type": "customer",
            "person_type": "individual",
            "name": _name("Cliente conta"),
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_financial_account_defaults_are_unique():
    auth = get_auth_context(client)
    first = _create_account(
        auth.headers,
        auth.company_id,
        name=_name("Conta padrao 1"),
        is_default_receivable=True,
        is_default_payable=True,
    )
    second = _create_account(
        auth.headers,
        auth.company_id,
        name=_name("Conta padrao 2"),
        is_default_receivable=True,
        is_default_payable=True,
    )

    response = client.get(
        f"/financial/accounts?company_id={auth.company_id}&limit=200",
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    first_row = next(row for row in rows if row["id"] == first["id"])
    second_row = next(row for row in rows if row["id"] == second["id"])

    assert first_row["is_default_receivable"] is False
    assert first_row["is_default_payable"] is False
    assert second_row["is_default_receivable"] is True
    assert second_row["is_default_payable"] is True


def test_financial_account_default_must_be_active():
    auth = get_auth_context(client)

    response = client.post(
        "/financial/accounts",
        json={
            "company_id": auth.company_id,
            "name": _name("Conta inativa padrao"),
            "account_type": "cash",
            "status": "inactive",
            "is_default_receivable": True,
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "padrao precisa estar ativa" in response.json()["message"]


def test_financial_account_opening_balance_cannot_change_after_balance_exists():
    auth = get_auth_context(client)
    account = _create_account(auth.headers, auth.company_id, opening_balance_amount="100.00")

    with SessionLocal() as db:
        db.add(
            FinancialAccountBalanceDB(
                id=generate_id("cashbal"),
                company_id=auth.company_id,
                financial_account_id=account["id"],
                current_balance_amount=Decimal("100.00"),
                last_movement_id=None,
                updated_at=utc_now(),
            )
        )
        db.commit()

    response = client.patch(
        f"/financial/accounts/{account['id']}",
        json={"opening_balance_amount": "200.00"},
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "Saldo inicial nao pode ser alterado" in response.json()["message"]


def test_financial_account_in_use_cannot_be_inactivated():
    auth = get_auth_context(client)
    account = _create_account(auth.headers, auth.company_id, name=_name("Conta com titulo"))
    participant_id = _create_participant(auth.headers, auth.company_id)

    title = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": auth.company_id,
            "participant_id": participant_id,
            "title_type": "manual",
            "source_type": "manual",
            "expected_financial_account_id": account["id"],
            "due_date": "2030-01-15",
            "gross_amount": "100.00",
        },
        headers=auth.headers,
    )
    assert title.status_code == 200, title.text

    response = client.patch(
        f"/financial/accounts/{account['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "Conta financeira em uso" in response.json()["message"]


def test_financial_account_full_update_keeps_operational_fields():
    auth = get_auth_context(client)
    account = _create_account(auth.headers, auth.company_id, name=_name("Conta editar"))

    response = client.patch(
        f"/financial/accounts/{account['id']}",
        json={
            "name": _name("Banco editado"),
            "account_type": "bank_account",
            "institution_name": "Banco Regressao",
            "branch_number": "0001",
            "account_number": "12345",
            "account_digit": "6",
            "pix_key": "financeiro@kovir.local",
            "pix_key_type": "email",
            "currency": "brl",
            "is_default_receivable": True,
            "notes": "Conta validada por regressao.",
        },
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["account_type"] == "bank_account"
    assert data["institution_name"] == "Banco Regressao"
    assert data["branch_number"] == "0001"
    assert data["account_number"] == "12345"
    assert data["account_digit"] == "6"
    assert data["pix_key_type"] == "email"
    assert data["currency"] == "BRL"
    assert data["is_default_receivable"] is True
