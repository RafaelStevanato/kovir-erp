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
        "name": "Conta categoria regressao",
        "account_type": "expense",
        "is_analytical": True,
        "accepts_entries": True,
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/chart-accounts", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_category(headers: dict[str, str], company_id: str, **overrides):
    payload = {
        "company_id": company_id,
        "code": _code("CAT"),
        "name": "Categoria regressao",
        "category_type": "expense",
        "cash_flow_group": "operating_outflows",
        "affects_cash_flow": True,
        "requires_cost_center": False,
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/categories", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_participant(headers: dict[str, str], company_id: str) -> str:
    response = client.post(
        "/participants",
        json={
            "company_id": company_id,
            "participant_type": "customer",
            "person_type": "individual",
            "name": f"Cliente Categoria {uuid4().hex[:8]}",
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_financial_category_cash_flow_rules_are_enforced():
    auth = get_auth_context(client)

    missing_group = client.post(
        "/financial/categories",
        json={
            "company_id": auth.company_id,
            "code": _code("CAT"),
            "name": "Sem grupo",
            "category_type": "income",
            "affects_cash_flow": True,
        },
        headers=auth.headers,
    )
    assert missing_group.status_code == 400, missing_group.text
    assert "grupo de fluxo" in missing_group.json()["message"]

    invalid_group = client.post(
        "/financial/categories",
        json={
            "company_id": auth.company_id,
            "code": _code("CAT"),
            "name": "Grupo invalido",
            "category_type": "income",
            "cash_flow_group": "grupo_solto",
            "affects_cash_flow": True,
        },
        headers=auth.headers,
    )
    assert invalid_group.status_code == 422, invalid_group.text

    group_without_cash_flow = client.post(
        "/financial/categories",
        json={
            "company_id": auth.company_id,
            "code": _code("CAT"),
            "name": "Grupo sem fluxo",
            "category_type": "other",
            "cash_flow_group": "operating_outflows",
            "affects_cash_flow": False,
        },
        headers=auth.headers,
    )
    assert group_without_cash_flow.status_code == 400, group_without_cash_flow.text
    assert "não afeta fluxo" in group_without_cash_flow.json()["message"]


def test_financial_category_requires_analytical_chart_account_that_accepts_entries():
    auth = get_auth_context(client)
    synthetic = _create_chart_account(
        auth.headers,
        auth.company_id,
        name="Conta sintetica",
        is_analytical=False,
        accepts_entries=False,
    )

    response = client.post(
        "/financial/categories",
        json={
            "company_id": auth.company_id,
            "code": _code("CAT"),
            "name": "Categoria com conta sintetica",
            "category_type": "expense",
            "cash_flow_group": "operating_outflows",
            "affects_cash_flow": True,
            "chart_account_id": synthetic["id"],
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "conta analítica ativa" in response.json()["message"]


def test_financial_category_rejects_cycle_and_inactivation_with_active_children():
    auth = get_auth_context(client)
    parent = _create_category(auth.headers, auth.company_id, name="Categoria pai")
    child = _create_category(auth.headers, auth.company_id, name="Categoria filha", parent_id=parent["id"])

    cycle = client.patch(
        f"/financial/categories/{parent['id']}",
        json={"parent_id": child["id"]},
        headers=auth.headers,
    )
    assert cycle.status_code == 400, cycle.text
    assert "ciclo" in cycle.json()["message"]

    inactive = client.patch(
        f"/financial/categories/{parent['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )
    assert inactive.status_code == 400, inactive.text
    assert "subcategorias ativas" in inactive.json()["message"]


def test_financial_category_linked_to_active_title_cannot_be_inactivated():
    auth = get_auth_context(client)
    category = _create_category(auth.headers, auth.company_id, name="Categoria vinculada a titulo")
    participant_id = _create_participant(auth.headers, auth.company_id)

    title = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": auth.company_id,
            "participant_id": participant_id,
            "title_type": "manual",
            "source_type": "manual",
            "financial_category_id": category["id"],
            "due_date": "2030-01-15",
            "gross_amount": "100.00",
        },
        headers=auth.headers,
    )
    assert title.status_code == 200, title.text

    response = client.patch(
        f"/financial/categories/{category['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )
    assert response.status_code == 400, response.text
    assert "título financeiro ativo" in response.json()["message"]

