from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.modules.accounts_receivable.schemas import FinancialTitleCreate
from app.modules.accounts_receivable.service import create_manual_receivable
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}".upper()


def _create_cost_center(headers: dict[str, str], company_id: str, **overrides):
    payload = {
        "company_id": company_id,
        "code": _code("CC"),
        "name": "Centro regressao",
        "center_type": "other",
        "is_analytical": True,
        "status": "active",
    }
    payload.update(overrides)
    response = client.post("/financial/cost-centers", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _create_participant(headers: dict[str, str], company_id: str, *, participant_type: str = "customer") -> str:
    response = client.post(
        "/participants",
        json={
            "company_id": company_id,
            "participant_type": participant_type,
            "person_type": "individual",
            "name": f"Participante Centro {uuid4().hex[:8]}",
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_cost_center_rejects_child_under_analytical_parent():
    auth = get_auth_context(client)
    parent = _create_cost_center(auth.headers, auth.company_id, name="Pai analitico")

    response = client.post(
        "/financial/cost-centers",
        json={
            "company_id": auth.company_id,
            "code": _code("CC"),
            "name": "Filho invalido",
            "center_type": "project",
            "parent_id": parent["id"],
            "is_analytical": True,
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "pai deve ser sintetico" in response.json()["message"]


def test_cost_center_rejects_cycle_and_inactivation_with_active_children():
    auth = get_auth_context(client)
    parent = _create_cost_center(auth.headers, auth.company_id, name="Centro pai", is_analytical=False)
    child = _create_cost_center(auth.headers, auth.company_id, name="Centro filho", parent_id=parent["id"], is_analytical=False)

    cycle = client.patch(
        f"/financial/cost-centers/{parent['id']}",
        json={"parent_id": child["id"]},
        headers=auth.headers,
    )
    assert cycle.status_code == 400, cycle.text
    assert "ciclo" in cycle.json()["message"]

    parent_as_analytical = client.patch(
        f"/financial/cost-centers/{parent['id']}",
        json={"is_analytical": True},
        headers=auth.headers,
    )
    assert parent_as_analytical.status_code == 400, parent_as_analytical.text
    assert "centros filhos" in parent_as_analytical.json()["message"]

    inactive = client.patch(
        f"/financial/cost-centers/{parent['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )
    assert inactive.status_code == 400, inactive.text
    assert "centros filhos ativos" in inactive.json()["message"]


def test_cost_center_linked_to_active_title_cannot_be_inactivated():
    auth = get_auth_context(client)
    cost_center = _create_cost_center(auth.headers, auth.company_id, name="Centro com titulo")
    participant_id = _create_participant(auth.headers, auth.company_id)

    title = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": auth.company_id,
            "participant_id": participant_id,
            "title_type": "manual",
            "source_type": "manual",
            "cost_center_id": cost_center["id"],
            "due_date": "2030-01-15",
            "gross_amount": "100.00",
        },
        headers=auth.headers,
    )
    assert title.status_code == 200, title.text

    response = client.patch(
        f"/financial/cost-centers/{cost_center['id']}",
        json={"status": "inactive"},
        headers=auth.headers,
    )
    assert response.status_code == 400, response.text
    assert "titulo financeiro ativo" in response.json()["message"]


def test_receivable_rejects_synthetic_cost_center():
    auth = get_auth_context(client)
    synthetic = _create_cost_center(auth.headers, auth.company_id, name="Centro sintetico", is_analytical=False)
    participant_id = _create_participant(auth.headers, auth.company_id)

    with SessionLocal() as db:
        payload = FinancialTitleCreate(
            company_id=auth.company_id,
            participant_id=participant_id,
            title_type="manual",
            source_type="manual",
            cost_center_id=synthetic["id"],
            due_date=date(2030, 1, 15),
            gross_amount="100.00",
        )
        with pytest.raises(ValueError, match="analitico"):
            create_manual_receivable(db, payload, actor_id=auth.user_id)


def test_purchase_rejects_synthetic_cost_center():
    auth = get_auth_context(client)
    synthetic = _create_cost_center(auth.headers, auth.company_id, name="Centro sintetico compra", is_analytical=False)
    supplier_id = _create_participant(auth.headers, auth.company_id, participant_type="supplier")

    response = client.post(
        "/purchases-payables/purchases",
        json={
            "company_id": auth.company_id,
            "participant_id": supplier_id,
            "purchase_type": "expense",
            "origin": "manual",
            "fiscal_status": "not_required",
            "cost_center_id": synthetic["id"],
            "items": [
                {
                    "description": "Despesa regressao",
                    "quantity": "1",
                    "unit": "UN",
                    "unit_cost": "100.00",
                }
            ],
        },
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "analitico" in response.json()["message"]
