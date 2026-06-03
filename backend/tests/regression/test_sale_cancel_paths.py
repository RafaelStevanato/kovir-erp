"""Regressão — caminhos de cancelamento a partir de cada estado válido."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import create_closeable_sale

client = TestClient(app)


def _get_sale_title(auth, sale_id: str) -> dict:
    resp = client.get(
        "/accounts-receivable/titles",
        params={"company_id": auth.company_id, "sale_id": sale_id},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    titles = resp.json()["data"]
    assert len(titles) == 1
    return titles[0]


def _create_financial_account(auth) -> str:
    resp = client.post(
        "/financial/accounts",
        json={
            "company_id": auth.company_id,
            "name": f"Conta cancelamento {uuid4().hex[:8]}",
            "account_type": "bank_account",
            "institution_name": "Banco Regressao",
            "opening_balance_amount": "0.00",
            "status": "active",
        },
        headers=auth.headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _create_discount_settlement(auth, title_id: str, account_id: str) -> str:
    resp = client.post(
        "/cash/settlements",
        json={
            "company_id": auth.company_id,
            "financial_title_id": title_id,
            "financial_account_id": account_id,
            "settlement_date": date.today().isoformat(),
            "competency_date": date.today().isoformat(),
            "received_amount": "0.00",
            "discount_amount": "100.00",
            "source_type": "manual",
            "source_id": f"cancel-{uuid4().hex[:12]}",
            "notes": "Baixa por desconto para regressao de cancelamento.",
        },
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["settlement"]["id"]


def test_cancel_quote_sale():
    """Cancelar orçamento (QUOTE → CANCELLED)."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    resp = client.post(
        f"/sales/{sale_id}/cancel",
        json={"reason": "Teste — cancelamento de orçamento"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None

    history = client.get(f"/sales/{sale_id}/status-history", headers=auth.headers)
    assert history.status_code == 200, history.text
    cancel_event = next(item for item in history.json()["data"] if item["new_status"] == "cancelled")
    assert cancel_event["actor_id"] == auth.user_id


def test_cancel_closed_sale_requires_reason():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    close = client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    assert close.status_code == 200, close.text

    resp = client.post(f"/sales/{sale_id}/cancel", json={}, headers=auth.headers)
    assert resp.status_code == 400
    assert "Motivo de cancelamento" in resp.json()["message"]


def test_cancel_closed_sale_with_active_settlement_fails():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    close = client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    assert close.status_code == 200, close.text
    title = _get_sale_title(auth, sale_id)
    account_id = _create_financial_account(auth)
    _create_discount_settlement(auth, title["id"], account_id)

    resp = client.post(
        f"/sales/{sale_id}/cancel",
        json={"reason": "Tentativa com baixa ativa"},
        headers=auth.headers,
    )
    assert resp.status_code == 400
    assert "baixa ativa" in resp.json()["message"]

    current = client.get(f"/sales/{sale_id}", headers=auth.headers)
    assert current.status_code == 200, current.text
    assert current.json()["data"]["status"] == "closed"


def test_cancel_closed_sale_after_settlement_reversal_succeeds():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    close = client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    assert close.status_code == 200, close.text
    title = _get_sale_title(auth, sale_id)
    account_id = _create_financial_account(auth)
    settlement_id = _create_discount_settlement(auth, title["id"], account_id)

    reversal = client.post(
        f"/cash/settlements/{settlement_id}/reverse",
        json={"reason": "Estorno antes do cancelamento do pedido"},
        headers=auth.headers,
    )
    assert reversal.status_code == 200, reversal.text

    resp = client.post(
        f"/sales/{sale_id}/cancel",
        json={"reason": "Cancelamento apos estorno financeiro"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"


def test_cancel_closed_sale():
    """Cancelar pedido fechado (CLOSED → CANCELLED), deve estornar estoque e AR."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    # fechar
    close = client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    assert close.status_code == 200, close.text

    # cancelar
    resp = client.post(
        f"/sales/{sale_id}/cancel",
        json={"reason": "Teste — cancelamento de pedido fechado"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "cancelled"


def test_disabled_pay_does_not_block_closed_sale_cancel():
    """Pagamento direto desativado mantém pedido CLOSED e cancelamento segue controlado."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    pay = client.post(f"/sales/{sale_id}/pay", json={}, headers=auth.headers)
    assert pay.status_code == 400

    current = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    assert current["status"] == "closed"

    resp = client.post(
        f"/sales/{sale_id}/cancel",
        json={"reason": "Teste — cancelamento após tentativa de pagamento direto"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "cancelled"


def test_cancel_already_cancelled_fails():
    """Cancelar venda já cancelada deve retornar erro 400."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/cancel", json={"reason": "Primeiro cancelamento"}, headers=auth.headers)

    second = client.post(f"/sales/{sale_id}/cancel", json={}, headers=auth.headers)
    assert second.status_code == 400
    assert second.json()["success"] is False
