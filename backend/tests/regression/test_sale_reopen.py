"""Regressão — reabertura de pedido fechado com senha mestre."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import create_closeable_sale

client = TestClient(app)

_MASTER_PASSWORD = "MasterTest@123"


def _set_master_password(client: TestClient, headers: dict) -> None:
    resp = client.post(
        "/security/master-password",
        json={"password": _MASTER_PASSWORD},
        headers=headers,
    )
    assert resp.status_code == 200, f"Falha ao configurar senha mestre: {resp.text}"


def test_set_master_password():
    """Configurar senha mestre via API deve retornar sucesso."""
    auth = get_auth_context(client)
    resp = client.post(
        "/security/master-password",
        json={"password": _MASTER_PASSWORD},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert resp.json()["data"]["configured"] is True


def test_master_password_status_after_set():
    auth = get_auth_context(client)
    _set_master_password(client, auth.headers)

    resp = client.get("/security/master-password/status", headers=auth.headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["configured"] is True


def test_reopen_closed_sale_with_correct_password():
    """Reabrir pedido fechado com senha correta → volta para QUOTE."""
    auth = get_auth_context(client)
    _set_master_password(client, auth.headers)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    reopen = client.post(
        f"/sales/{sale_id}/reopen",
        json={"master_password": _MASTER_PASSWORD, "reason": "Teste de regressão — reabertura"},
        headers=auth.headers,
    )
    assert reopen.status_code == 200, reopen.text
    data = reopen.json()["data"]
    assert data["status"] == "quote"
    assert data["unlocked_at"] is not None
    assert data["unlocked_by"] is not None


def test_reopen_with_wrong_password_fails():
    """Reabertura com senha errada deve retornar 403."""
    auth = get_auth_context(client)
    _set_master_password(client, auth.headers)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    resp = client.post(
        f"/sales/{sale_id}/reopen",
        json={"master_password": "SenhaErrada@999"},
        headers=auth.headers,
    )
    assert resp.status_code == 403
    assert resp.json()["success"] is False


def test_reopen_after_disabled_pay_still_reopens_closed_sale():
    """Tentativa de pagamento direto não altera CLOSED; reabertura controlada continua válida."""
    auth = get_auth_context(client)
    _set_master_password(client, auth.headers)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    pay = client.post(f"/sales/{sale_id}/pay", json={}, headers=auth.headers)
    assert pay.status_code == 400

    resp = client.post(
        f"/sales/{sale_id}/reopen",
        json={"master_password": _MASTER_PASSWORD},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "quote"


def test_reopen_quote_sale_fails():
    """Reabrir orçamento (QUOTE) deve falhar — só CLOSED pode ser reaberto."""
    auth = get_auth_context(client)
    _set_master_password(client, auth.headers)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    resp = client.post(
        f"/sales/{sale_id}/reopen",
        json={"master_password": _MASTER_PASSWORD},
        headers=auth.headers,
    )
    assert resp.status_code == 400
    assert resp.json()["success"] is False
