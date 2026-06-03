from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


def _name(prefix: str) -> str:
    return f"{prefix} {uuid4().hex[:8]}"


def _create_payment_term(headers: dict[str, str], company_id: str, **overrides):
    payload = {
        "company_id": company_id,
        "name": _name("Condicao regressao"),
        "term_type": "installments",
        "installments": 2,
        "first_due_days": 30,
        "interval_days": 30,
        "generate_on_sale": True,
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/payment-terms", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_payment_term_cash_requires_d0_single_installment_and_zero_interval():
    auth = get_auth_context(client)

    response = client.post(
        "/financial/payment-terms",
        json={
            "company_id": auth.company_id,
            "name": _name("Vista invalida"),
            "term_type": "cash",
            "installments": 1,
            "first_due_days": 5,
            "interval_days": 0,
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "D+0" in response.json()["message"]


def test_payment_term_installments_require_positive_interval_when_multiple():
    auth = get_auth_context(client)

    response = client.post(
        "/financial/payment-terms",
        json={
            "company_id": auth.company_id,
            "name": _name("Parcelado invalido"),
            "term_type": "installments",
            "installments": 3,
            "first_due_days": 30,
            "interval_days": 0,
        },
        headers=auth.headers,
    )

    assert response.status_code in {400, 422}, response.text
    assert "intervalo maior que zero" in response.text


def test_payment_term_update_validates_effective_combination():
    auth = get_auth_context(client)
    term = _create_payment_term(auth.headers, auth.company_id, name=_name("Parcelado editar"))

    invalid = client.patch(
        f"/financial/payment-terms/{term['id']}",
        json={"term_type": "cash"},
        headers=auth.headers,
    )
    assert invalid.status_code == 400, invalid.text
    assert "uma parcela" in invalid.json()["message"]

    valid = client.patch(
        f"/financial/payment-terms/{term['id']}",
        json={
            "term_type": "cash",
            "installments": 1,
            "first_due_days": 0,
            "interval_days": 0,
            "generate_on_sale": True,
            "notes": "Convertida para a vista.",
        },
        headers=auth.headers,
    )
    assert valid.status_code == 200, valid.text
    data = valid.json()["data"]
    assert data["term_type"] == "cash"
    assert data["installments"] == 1
    assert data["first_due_days"] == 0
    assert data["interval_days"] == 0


def test_payment_term_list_supports_filters():
    auth = get_auth_context(client)
    target_name = _name("Busca condicao")
    _create_payment_term(auth.headers, auth.company_id, name=target_name, term_type="custom", installments=1, first_due_days=15, interval_days=0)

    response = client.get(
        f"/financial/payment-terms?company_id={auth.company_id}&term_type=custom&status=active&search={target_name}",
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    rows = response.json()["data"]
    assert any(row["name"] == target_name and row["term_type"] == "custom" for row in rows)
