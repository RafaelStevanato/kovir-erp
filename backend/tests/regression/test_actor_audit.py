from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


def _create_financial_account(company_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/financial/accounts",
        json={
            "company_id": company_id,
            "name": f"Conta auditoria {uuid4().hex[:8]}",
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
            "document_reference": f"AR-AUD-{uuid4().hex[:8]}",
            "due_date": "2099-03-10",
            "gross_amount": "100.00",
            "fiscal_status": "not_required",
            "notes": "Titulo para regressao de auditoria.",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_financial_master_mutations_record_authenticated_actor():
    auth = get_auth_context(client)
    account_id = _create_financial_account(auth.company_id, auth.headers)

    audit_response = client.get(f"/financial/audit/financial_account/{account_id}", headers=auth.headers)
    assert audit_response.status_code == 200, audit_response.text
    created_events = audit_response.json()["data"]
    assert any(event["event_type"] == "created" and event["actor_id"] == auth.user_id for event in created_events)

    update_response = client.patch(
        f"/financial/accounts/{account_id}",
        json={"notes": "Atualizacao auditada com usuario real."},
        headers=auth.headers,
    )
    assert update_response.status_code == 200, update_response.text

    audit_response = client.get(f"/financial/audit/financial_account/{account_id}", headers=auth.headers)
    assert audit_response.status_code == 200, audit_response.text
    updated_events = audit_response.json()["data"]
    assert any(event["event_type"] == "updated" and event["actor_id"] == auth.user_id for event in updated_events)


def test_receivable_and_cash_mutations_record_authenticated_actor():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id, auth.headers)
    title_id = _create_manual_receivable(auth.company_id, fixtures["participant_id"], auth.headers)

    history_response = client.get(f"/accounts-receivable/titles/{title_id}/history", headers=auth.headers)
    assert history_response.status_code == 200, history_response.text
    assert any(event["actor_id"] == auth.user_id for event in history_response.json()["data"])

    update_response = client.patch(
        f"/accounts-receivable/titles/{title_id}",
        json={"notes": "Atualizacao auditada do titulo."},
        headers=auth.headers,
    )
    assert update_response.status_code == 200, update_response.text

    settlement_response = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "100.00",
            "source_type": "manual",
            "source_id": f"audit-{uuid4().hex[:12]}",
            "notes": "Baixa para regressao de auditoria.",
        },
        headers=auth.headers,
    )
    assert settlement_response.status_code == 200, settlement_response.text
    settlement_id = settlement_response.json()["data"]["settlement"]["id"]

    reverse_response = client.post(
        f"/cash/settlements/{settlement_id}/reverse",
        json={"reason": "Estorno para validar ator real."},
        headers=auth.headers,
    )
    assert reverse_response.status_code == 200, reverse_response.text

    history_response = client.get(f"/accounts-receivable/titles/{title_id}/history", headers=auth.headers)
    assert history_response.status_code == 200, history_response.text
    title_history = history_response.json()["data"]
    assert len([event for event in title_history if event["actor_id"] == auth.user_id]) >= 4
