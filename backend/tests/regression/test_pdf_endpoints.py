"""Regressão — endpoints de PDF (orçamento e nota comercial)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import create_closeable_sale

client = TestClient(app)


def test_quote_pdf_for_quote_sale():
    """GET /sales/{id}/quote.pdf para venda QUOTE retorna PDF."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)

    resp = client.get(f"/sales/{sale_id}/quote.pdf", headers=auth.headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 100  # arquivo não vazio


def test_quote_pdf_for_closed_sale():
    """GET /sales/{id}/quote.pdf para venda CLOSED também retorna PDF."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    resp = client.get(f"/sales/{sale_id}/quote.pdf", headers=auth.headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_quote_pdf_for_cancelled_sale_fails():
    """GET /sales/{id}/quote.pdf para venda CANCELLED retorna 409."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/cancel", json={"reason": "Cancelamento para teste de PDF"}, headers=auth.headers)

    resp = client.get(f"/sales/{sale_id}/quote.pdf", headers=auth.headers)
    assert resp.status_code == 409


def test_commercial_invoice_pdf_for_closed_sale():
    """GET /sales/{id}/commercial-invoice.pdf para venda CLOSED retorna PDF."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    resp = client.get(
        f"/sales/{sale_id}/commercial-invoice.pdf",
        params={"mode": "closed"},
        headers=auth.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 100


def test_commercial_invoice_pdf_paid_mode_requires_paid_status():
    """mode=paid em venda CLOSED deve retornar 409."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)

    resp = client.get(
        f"/sales/{sale_id}/commercial-invoice.pdf",
        params={"mode": "paid"},
        headers=auth.headers,
    )
    assert resp.status_code == 409


def test_disabled_pay_keeps_paid_pdf_blocked():
    """Pagamento direto desativado não libera mode=paid."""
    auth = get_auth_context(client)
    sale_id = create_closeable_sale(client, auth.company_id, auth.headers)
    client.post(f"/sales/{sale_id}/confirm", json={}, headers=auth.headers)
    pay = client.post(f"/sales/{sale_id}/pay", json={}, headers=auth.headers)
    assert pay.status_code == 400

    resp = client.get(
        f"/sales/{sale_id}/commercial-invoice.pdf",
        params={"mode": "paid"},
        headers=auth.headers,
    )
    assert resp.status_code == 409


def test_pdf_endpoints_require_auth():
    """Endpoints de PDF exigem token Bearer."""
    fake_id = "sale_00000000-0000-4000-8000-000000000000"
    resp = client.get(f"/sales/{fake_id}/quote.pdf")
    assert resp.status_code in (401, 403, 422)
