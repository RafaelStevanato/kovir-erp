"""Regressão — numeração de pedidos (sequência e unicidade básica)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import create_closeable_sale

client = TestClient(app)


def test_sale_number_assigned_on_close():
    """Pedido recebe sale_number_text ao ser fechado."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    before = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    assert before["sale_number"] is None
    assert before["sale_number_text"] is None

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    after = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    assert after["sale_number"] is not None
    assert after["sale_number_text"] is not None
    assert "PED" in after["sale_number_text"]


def test_two_closes_get_different_sale_numbers():
    """Dois pedidos fechados em sequência recebem números distintos."""
    auth = get_auth_context(client)

    id1 = create_closeable_sale(client, auth.company_id, auth.headers)
    id2 = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{id1}/confirm", json={}, headers=auth.headers)
    client.post(f"/sales/{id2}/confirm", json={}, headers=auth.headers)

    n1 = client.get(f"/sales/{id1}", headers=auth.headers).json()["data"]["sale_number"]
    n2 = client.get(f"/sales/{id2}", headers=auth.headers).json()["data"]["sale_number"]

    assert n1 != n2
    assert abs(n2 - n1) == 1, f"Números devem ser consecutivos: {n1}, {n2}"


def test_sale_number_text_format():
    """sale_number_text deve seguir o formato PED-XXXXXX."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    data = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    text = data["sale_number_text"]
    assert text is not None
    assert text.startswith("PED-"), f"Formato inesperado: {text}"
    number_part = text.replace("PED-", "")
    assert number_part.isdigit(), f"Parte numérica inválida: {number_part}"
    assert len(number_part) == 6, f"Esperado 6 dígitos, got: {number_part}"


def test_disabled_pay_does_not_assign_paid_number_text():
    """Pagamento direto desativado não deve gerar numeração de recibo legado."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    pay = client.post(f"/sales/{sale_id}/pay", json={}, headers=auth.headers)
    assert pay.status_code == 400

    data = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    assert data["status"] == "closed"
    assert data["paid_number_text"] is None
