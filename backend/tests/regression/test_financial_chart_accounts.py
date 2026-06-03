from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}".upper()


def _create_chart_account(headers: dict[str, str], company_id: str, **overrides):
    payload = {
        "company_id": company_id,
        "code": _code("ACC"),
        "name": "Conta regressao",
        "account_type": "expense",
        "is_analytical": True,
        "accepts_entries": True,
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/chart-accounts", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_chart_account_rejects_child_under_analytical_parent():
    auth = get_auth_context(client)
    parent = _create_chart_account(auth.headers, auth.company_id, name="Pai analitico")

    response = client.post(
        "/financial/chart-accounts",
        json={
            "company_id": auth.company_id,
            "code": _code("CHILD"),
            "name": "Filha invalida",
            "account_type": "expense",
            "parent_id": parent["id"],
            "is_analytical": True,
            "accepts_entries": True,
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "sintética" in response.json()["message"]


def test_chart_account_rejects_invalid_hierarchy_and_synthetic_entry_state():
    auth = get_auth_context(client)
    parent = _create_chart_account(
        auth.headers,
        auth.company_id,
        name="Pai sintetico",
        is_analytical=False,
        accepts_entries=False,
    )
    child = _create_chart_account(
        auth.headers,
        auth.company_id,
        name="Filha analitica",
        parent_id=parent["id"],
    )

    synthetic_accepting_entries = client.patch(
        f"/financial/chart-accounts/{child['id']}",
        json={"is_analytical": False},
        headers=auth.headers,
    )
    assert synthetic_accepting_entries.status_code == 400, synthetic_accepting_entries.text
    assert "sintética" in synthetic_accepting_entries.json()["message"]

    self_parent = client.patch(
        f"/financial/chart-accounts/{child['id']}",
        json={"parent_id": child["id"]},
        headers=auth.headers,
    )
    assert self_parent.status_code == 400, self_parent.text

    parent_with_child_as_entry = client.patch(
        f"/financial/chart-accounts/{parent['id']}",
        json={"is_analytical": True, "accepts_entries": True},
        headers=auth.headers,
    )
    assert parent_with_child_as_entry.status_code == 400, parent_with_child_as_entry.text
    assert "contas filhas" in parent_with_child_as_entry.json()["message"]


def test_chart_account_linked_to_active_category_cannot_be_inactivated():
    auth = get_auth_context(client)
    account = _create_chart_account(auth.headers, auth.company_id, name="Conta vinculada")

    category = client.post(
        "/financial/categories",
        json={
            "company_id": auth.company_id,
            "code": _code("CAT"),
            "name": "Categoria vinculada",
            "category_type": "income",
            "chart_account_id": account["id"],
            "cash_flow_group": "operating_inflows",
            "affects_cash_flow": True,
            "status": "active",
        },
        headers=auth.headers,
    )
    assert category.status_code == 201, category.text

    response = client.patch(
        f"/financial/chart-accounts/{account['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "categoria financeira ativa" in response.json()["message"]
