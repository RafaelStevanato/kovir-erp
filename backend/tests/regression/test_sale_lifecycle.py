"""Regressão — ciclo de vida principal: QUOTE → CLOSED, com recebimento via Caixa/Baixas."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import build_sale_payload, create_closeable_sale, ensure_service_fixtures

client = TestClient(app)


def test_sale_create_returns_quote_status():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    resp = client.get(f"/sales/{sale_id}", headers=auth.headers)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["status"] == "quote"
    assert data["sale_number"] is None
    assert data["closed_at"] is None


def test_sale_close_moves_to_closed():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    close_resp = client.post(
        f"/sales/{sale_id}/confirm",
        json={"reason": "Teste de regressão — fechamento"},
        headers=auth.headers,
    )
    assert close_resp.status_code == 200, close_resp.text
    data = close_resp.json()["data"]
    assert data["status"] == "closed"
    assert data["sale_number"] is not None
    assert data["sale_number_text"] is not None
    assert data["closed_at"] is not None


def test_sales_list_uses_server_filters_pagination_and_summary():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    close_resp = client.post(
        f"/sales/{sale_id}/confirm",
        json={"reason": "Fechamento para filtro de pedidos"},
        headers=auth.headers,
    )
    assert close_resp.status_code == 200, close_resp.text
    sale_number_text = close_resp.json()["data"]["sale_number_text"]

    list_resp = client.get(
        "/sales",
        params={"company_id": auth.company_id, "status": "closed", "q": sale_number_text, "limit": 1, "offset": 0},
        headers=auth.headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == sale_id

    summary_resp = client.get(
        "/sales/summary",
        params={"company_id": auth.company_id, "status": "closed", "q": sale_number_text},
        headers=auth.headers,
    )
    assert summary_resp.status_code == 200, summary_resp.text
    summary = summary_resp.json()["data"]
    assert summary["total"] == 1
    assert summary["counts_by_status"]["closed"] >= 1


def test_generate_receivables_from_closed_sale_is_idempotent():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    close_resp = client.post(
        f"/sales/{sale_id}/confirm",
        json={"reason": "Fechamento para gerar títulos"},
        headers=auth.headers,
    )
    assert close_resp.status_code == 200, close_resp.text
    sale_number_text = close_resp.json()["data"]["sale_number_text"]
    assert sale_number_text is not None

    resp = client.post(
        f"/accounts-receivable/from-sale/{sale_id}",
        json={"reason": "Regressão endpoint manual"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert len(payload["data"]) >= 1
    assert {title["sale_id"] for title in payload["data"]} == {sale_id}
    title = payload["data"][0]
    assert title["document_reference"] == f"RECEBER-{sale_number_text}"
    assert title["source_snapshot"]["sale_number_text"] == sale_number_text


def test_generate_receivables_for_installments_uses_distinct_order_references():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    payload = build_sale_payload(
        auth.company_id,
        fixtures["item_id"],
        fixtures["fiscal_classification_id"],
        fixtures["participant_id"],
    )
    payload["payment_plans"] = [
        {"amount": "40.00", "payment_method_code": "pix", "due_date": "2099-01-15"},
        {"amount": "60.00", "payment_method_code": "boleto", "due_date": "2099-02-15"},
    ]

    create_resp = client.post("/sales", json=payload, headers=auth.headers)
    assert create_resp.status_code == 201, create_resp.text
    sale_id = create_resp.json()["data"]["id"]

    close_resp = client.post(
        f"/sales/{sale_id}/confirm",
        json={"reason": "Fechamento com duas parcelas"},
        headers=auth.headers,
    )
    assert close_resp.status_code == 200, close_resp.text
    sale_number_text = close_resp.json()["data"]["sale_number_text"]
    assert sale_number_text is not None

    first_resp = client.post(
        f"/accounts-receivable/from-sale/{sale_id}",
        json={"reason": "Validação de parcelas"},
        headers=auth.headers,
    )
    second_resp = client.post(
        f"/accounts-receivable/from-sale/{sale_id}",
        json={"reason": "Validação de idempotência"},
        headers=auth.headers,
    )
    assert first_resp.status_code == 200, first_resp.text
    assert second_resp.status_code == 200, second_resp.text

    first_titles = sorted(first_resp.json()["data"], key=lambda title: title["installment_number"])
    second_titles = sorted(second_resp.json()["data"], key=lambda title: title["installment_number"])
    assert len(first_titles) == 2
    assert [title["id"] for title in second_titles] == [title["id"] for title in first_titles]
    assert [title["document_reference"] for title in first_titles] == [
        f"RECEBER-{sale_number_text}-01/02",
        f"RECEBER-{sale_number_text}-02/02",
    ]
    assert [title["installment_number"] for title in first_titles] == [1, 2]
    assert {title["installment_total"] for title in first_titles} == {2}
    assert [title["open_amount"] for title in first_titles] == ["40.00", "60.00"]
    assert [title["due_date"] for title in first_titles] == ["2099-01-15", "2099-02-15"]
    assert {title["source_snapshot"]["sale_number_text"] for title in first_titles} == {sale_number_text}

    search_resp = client.get(
        "/accounts-receivable/titles",
        params={"company_id": auth.company_id, "q": sale_number_text, "limit": 10, "offset": 0},
        headers=auth.headers,
    )
    assert search_resp.status_code == 200, search_resp.text
    found_refs = {title["document_reference"] for title in search_resp.json()["data"]}
    assert {title["document_reference"] for title in first_titles}.issubset(found_refs)


def test_sale_pay_endpoint_is_disabled_for_closed_sale():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    # fechar primeiro
    close_resp = client.post(
        f"/sales/{sale_id}/confirm",
        json={"reason": "Fechamento para teste de pagamento"},
        headers=auth.headers,
    )
    assert close_resp.status_code == 200, close_resp.text

    pay_resp = client.post(
        f"/sales/{sale_id}/pay",
        json={"reason": "Tentativa de pagamento direto"},
        headers=auth.headers,
    )
    assert pay_resp.status_code == 400
    payload = pay_resp.json()
    assert payload["success"] is False
    assert "Caixa e Baixas" in payload["message"]

    data = client.get(f"/sales/{sale_id}", headers=auth.headers).json()["data"]
    assert data["status"] == "closed"
    assert data["paid_at"] is None
    assert data["paid_number_text"] is None


def test_pay_quote_sale_fails():
    """Não é possível receber um orçamento diretamente."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    pay_resp = client.post(
        f"/sales/{sale_id}/pay",
        json={},
        headers=auth.headers,
    )
    assert pay_resp.status_code == 400
    assert pay_resp.json()["success"] is False
    assert "fechado" in pay_resp.json()["message"]


def test_close_already_closed_sale_fails():
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    second_close = client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    assert second_close.status_code == 400
    assert second_close.json()["success"] is False
