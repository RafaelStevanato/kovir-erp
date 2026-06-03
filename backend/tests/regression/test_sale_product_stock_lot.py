from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context


client = TestClient(app)


def _suffix() -> str:
    return uuid4().hex[:10]


def _ncm() -> str:
    return str(70000000 + (uuid4().int % 9999999)).zfill(8)[:8]


def _decimal(value: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _ensure_customer(company_id: str, headers: dict[str, str]) -> str:
    suffix = _suffix()
    response = client.post(
        "/participants",
        json={
            "company_id": company_id,
            "participant_type": "customer",
            "person_type": "individual",
            "name": f"Cliente Produto Lote {suffix}",
            "document": f"55{suffix.upper()}CC",
            "status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_product_with_fiscal(company_id: str, headers: dict[str, str]) -> dict[str, str]:
    suffix = _suffix()
    ncm = _ncm()
    fiscal_response = client.post(
        "/fiscal/classifications",
        json={
            "company_id": company_id,
            "name": f"NCM Produto Lote {suffix}",
            "item_type": "product",
            "tax_regime": "simples_nacional",
            "ncm": ncm,
            "cfop_default": "5102",
            "origem_mercadoria": "0",
            "subject_to_icms": True,
            "subject_to_ibs_cbs": True,
            "status": "active",
        },
        headers=headers,
    )
    assert fiscal_response.status_code == 201, fiscal_response.text
    fiscal_id = fiscal_response.json()["data"]["id"]

    product_response = client.post(
        "/catalog/items",
        json={
            "company_id": company_id,
            "item_type": "product",
            "name": f"Produto com Lote {suffix}",
            "sku": f"LOT-{suffix}",
            "unit": "UN",
            "status": "active",
            "financial_settings": {
                "default_sale_price": "50.00",
                "default_cost_price": "20.00",
                "allow_price_override": False,
            },
            "fiscal_settings": {
                "ncm": ncm,
                "fiscal_classification_id": fiscal_id,
            },
            "inventory_settings": {
                "track_stock": True,
                "stock_unit": "UN",
                "minimum_stock": "0",
                "allow_negative_stock": False,
            },
        },
        headers=headers,
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["data"]["id"]
    return {"product_id": product_id, "fiscal_id": fiscal_id}


def _ensure_default_location(company_id: str, headers: dict[str, str]) -> str:
    response = client.post(
        "/stock/locations/default",
        params={"company_id": company_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def _create_location(company_id: str, headers: dict[str, str]) -> str:
    suffix = _suffix().upper()
    response = client.post(
        "/stock/locations",
        json={
            "company_id": company_id,
            "code": f"LOC-{suffix}",
            "name": f"Estoque filial {suffix}",
            "location_type": "warehouse",
            "is_default": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_stock_lot(
    company_id: str,
    item_id: str,
    location_id: str,
    headers: dict[str, str],
    *,
    expiration_date: str | None = "2030-12-31",
) -> dict:
    suffix = _suffix().upper()
    response = client.post(
        "/stock/purchase-entries",
        json={
            "company_id": company_id,
            "location_id": location_id,
            "document_type": "purchase_invoice",
            "document_number": f"NF-{suffix}",
            "items": [
                {
                    "item_id": item_id,
                    "quantity": "5",
                    "unit_cost": "20.00",
                    "unit": "UN",
                    "lot_code": f"LOTE-{suffix}",
                    "expiration_date": expiration_date,
                }
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text

    lots_response = client.get(
        "/stock/lots",
        params={
            "company_id": company_id,
            "item_id": item_id,
            "location_id": location_id,
            "only_positive": True,
        },
        headers=headers,
    )
    assert lots_response.status_code == 200, lots_response.text
    lots = lots_response.json()["data"]
    assert lots
    return lots[0]


def test_product_sale_with_stock_lot_consumes_lot_balance_and_creates_links():
    auth = get_auth_context(client)
    participant_id = _ensure_customer(auth.company_id, auth.headers)
    product = _create_product_with_fiscal(auth.company_id, auth.headers)
    location_id = _ensure_default_location(auth.company_id, auth.headers)
    lot = _create_stock_lot(auth.company_id, product["product_id"], location_id, auth.headers)

    sale_response = client.post(
        "/sales",
        json={
            "company_id": auth.company_id,
            "sale_type": "product",
            "origin": "manual",
            "participant_id": participant_id,
            "payment_plans": [
                {
                    "amount": "100.00",
                    "payment_method_code": "pix",
                }
            ],
            "items": [
                {
                    "item_id": product["product_id"],
                    "stock_lot_id": lot["id"],
                    "quantity": "2",
                }
            ],
        },
        headers=auth.headers,
    )
    assert sale_response.status_code == 201, sale_response.text
    sale = sale_response.json()["data"]
    assert sale["items"][0]["stock_lot_id"] == lot["id"]
    assert sale["items"][0]["stock_lot_code"] == lot["lot_code"]
    assert sale["items"][0]["stock_lot_expiration_date"] == lot["expiration_date"]

    close_response = client.post(
        f"/sales/{sale['id']}/confirm",
        json={"reason": "regressao produto com lote"},
        headers=auth.headers,
    )
    assert close_response.status_code == 200, close_response.text
    closed_sale = close_response.json()["data"]
    assert closed_sale["status"] == "closed"

    lots_after = client.get(
        "/stock/lots",
        params={
            "company_id": auth.company_id,
            "item_id": product["product_id"],
            "location_id": location_id,
            "only_positive": False,
        },
        headers=auth.headers,
    )
    assert lots_after.status_code == 200, lots_after.text
    updated_lot = next(row for row in lots_after.json()["data"] if row["id"] == lot["id"])
    assert _decimal(updated_lot["quantity"]) == Decimal("3.0000")

    balances = client.get(
        "/stock/balances",
        params={
            "company_id": auth.company_id,
            "item_id": product["product_id"],
            "location_id": location_id,
        },
        headers=auth.headers,
    )
    assert balances.status_code == 200, balances.text
    assert _decimal(balances.json()["data"][0]["quantity"]) == Decimal("3.0000")

    movements = client.get(
        "/stock/movements",
        params={
            "company_id": auth.company_id,
            "item_id": product["product_id"],
            "source_type": "sale",
        },
        headers=auth.headers,
    )
    assert movements.status_code == 200, movements.text
    sale_movements = [row for row in movements.json()["data"] if row["source_id"] == sale["id"]]
    assert len(sale_movements) == 1
    assert sale_movements[0]["lot_id"] == lot["id"]
    assert sale_movements[0]["sale_item_id"] == sale["items"][0]["id"]

    links = client.get(
        "/stock/sale-links",
        params={"sale_id": sale["id"]},
        headers=auth.headers,
    )
    assert links.status_code == 200, links.text
    assert len(links.json()["data"]) == 1
    assert links.json()["data"][0]["sale_item_id"] == sale["items"][0]["id"]

    receivables = client.get(
        "/accounts-receivable/titles",
        params={"company_id": auth.company_id, "sale_id": sale["id"]},
        headers=auth.headers,
    )
    assert receivables.status_code == 200, receivables.text
    assert receivables.json()["data"]


def test_product_sale_tracking_stock_requires_lot():
    auth = get_auth_context(client)
    participant_id = _ensure_customer(auth.company_id, auth.headers)
    product = _create_product_with_fiscal(auth.company_id, auth.headers)

    sale_response = client.post(
        "/sales",
        json={
            "company_id": auth.company_id,
            "sale_type": "product",
            "origin": "manual",
            "participant_id": participant_id,
            "payment_plans": [
                {
                    "amount": "50.00",
                    "payment_method_code": "pix",
                }
            ],
            "items": [
                {
                    "item_id": product["product_id"],
                    "quantity": "1",
                }
            ],
        },
        headers=auth.headers,
    )
    assert sale_response.status_code == 400
    assert "lote" in sale_response.text.lower()


def test_product_sale_consumes_lot_from_selected_non_default_location():
    auth = get_auth_context(client)
    participant_id = _ensure_customer(auth.company_id, auth.headers)
    product = _create_product_with_fiscal(auth.company_id, auth.headers)
    default_location_id = _ensure_default_location(auth.company_id, auth.headers)
    branch_location_id = _create_location(auth.company_id, auth.headers)
    lot = _create_stock_lot(auth.company_id, product["product_id"], branch_location_id, auth.headers)

    availability = client.get(
        f"/stock/items/{product['product_id']}/availability",
        params={"company_id": auth.company_id, "location_id": branch_location_id},
        headers=auth.headers,
    )
    assert availability.status_code == 200, availability.text
    assert availability.json()["data"]["location_id"] == branch_location_id
    assert any(row["id"] == lot["id"] for row in availability.json()["data"]["lots"])

    sale_response = client.post(
        "/sales",
        json={
            "company_id": auth.company_id,
            "sale_type": "product",
            "origin": "manual",
            "participant_id": participant_id,
            "payment_plans": [{"amount": "50.00", "payment_method_code": "pix"}],
            "items": [{"item_id": product["product_id"], "stock_lot_id": lot["id"], "quantity": "1"}],
        },
        headers=auth.headers,
    )
    assert sale_response.status_code == 201, sale_response.text
    sale = sale_response.json()["data"]

    close_response = client.post(
        f"/sales/{sale['id']}/confirm",
        json={"reason": "regressao lote em estoque nao padrao"},
        headers=auth.headers,
    )
    assert close_response.status_code == 200, close_response.text

    branch_lots = client.get(
        "/stock/lots",
        params={"company_id": auth.company_id, "item_id": product["product_id"], "location_id": branch_location_id, "only_positive": False},
        headers=auth.headers,
    )
    assert branch_lots.status_code == 200, branch_lots.text
    updated_lot = next(row for row in branch_lots.json()["data"] if row["id"] == lot["id"])
    assert _decimal(updated_lot["quantity"]) == Decimal("4.0000")

    default_balances = client.get(
        "/stock/balances",
        params={"company_id": auth.company_id, "item_id": product["product_id"], "location_id": default_location_id},
        headers=auth.headers,
    )
    assert default_balances.status_code == 200, default_balances.text
    assert default_balances.json()["data"] == []


def test_stock_purchase_entry_rejects_incomplete_line_without_partial_posting():
    auth = get_auth_context(client)
    product = _create_product_with_fiscal(auth.company_id, auth.headers)
    location_id = _ensure_default_location(auth.company_id, auth.headers)
    document_number = f"NF-PARCIAL-{_suffix().upper()}"

    response = client.post(
        "/stock/purchase-entries",
        json={
            "company_id": auth.company_id,
            "location_id": location_id,
            "document_type": "purchase_invoice",
            "document_number": document_number,
            "items": [
                {
                    "item_id": product["product_id"],
                    "quantity": "5",
                    "unit_cost": "20.00",
                    "unit": "UN",
                    "lot_code": f"LOTE-OK-{_suffix().upper()}",
                    "expiration_date": "2030-12-31",
                },
                {
                    "item_id": product["product_id"],
                    "quantity": "1",
                    "unit_cost": "20.00",
                    "unit": "UN",
                    "lot_code": "",
                    "expiration_date": "2030-12-31",
                },
            ],
        },
        headers=auth.headers,
    )
    assert response.status_code == 422, response.text

    movements = client.get(
        "/stock/movements",
        params={
            "company_id": auth.company_id,
            "item_id": product["product_id"],
            "source_type": "purchase_entry",
        },
        headers=auth.headers,
    )
    assert movements.status_code == 200, movements.text
    assert movements.json()["data"] == []


def test_product_sale_with_no_expiration_lot_uses_sv_lot():
    auth = get_auth_context(client)
    participant_id = _ensure_customer(auth.company_id, auth.headers)
    product = _create_product_with_fiscal(auth.company_id, auth.headers)
    location_id = _ensure_default_location(auth.company_id, auth.headers)
    lot = _create_stock_lot(
        auth.company_id,
        product["product_id"],
        location_id,
        auth.headers,
        expiration_date=None,
    )

    assert lot["expiration_date"] == "9999-12-31"

    availability = client.get(
        f"/stock/items/{product['product_id']}/availability",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert availability.status_code == 200, availability.text
    availability_lots = availability.json()["data"]["lots"]
    assert any(row["id"] == lot["id"] and row["expiration_date"] == "9999-12-31" for row in availability_lots)

    sale_response = client.post(
        "/sales",
        json={
            "company_id": auth.company_id,
            "sale_type": "product",
            "origin": "manual",
            "participant_id": participant_id,
            "payment_plans": [
                {
                    "amount": "50.00",
                    "payment_method_code": "pix",
                }
            ],
            "items": [
                {
                    "item_id": product["product_id"],
                    "stock_lot_id": lot["id"],
                    "quantity": "1",
                }
            ],
        },
        headers=auth.headers,
    )
    assert sale_response.status_code == 201, sale_response.text
    sale = sale_response.json()["data"]
    assert sale["items"][0]["stock_lot_expiration_date"] == "9999-12-31"

    close_response = client.post(
        f"/sales/{sale['id']}/confirm",
        json={"reason": "regressao produto sem vencimento"},
        headers=auth.headers,
    )
    assert close_response.status_code == 200, close_response.text

    lots_after = client.get(
        "/stock/lots",
        params={
            "company_id": auth.company_id,
            "item_id": product["product_id"],
            "location_id": location_id,
            "only_positive": False,
        },
        headers=auth.headers,
    )
    assert lots_after.status_code == 200, lots_after.text
    updated_lot = next(row for row in lots_after.json()["data"] if row["id"] == lot["id"])
    assert updated_lot["expiration_date"] == "9999-12-31"
    assert _decimal(updated_lot["quantity"]) == Decimal("4.0000")
