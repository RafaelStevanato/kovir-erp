from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import engine
from app.main import app
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


class QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def __enter__(self) -> "QueryCounter":
        event.listen(engine, "before_cursor_execute", self._count_query)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        event.remove(engine, "before_cursor_execute", self._count_query)

    def _count_query(self, *args) -> None:
        self.count += 1


def _suffix() -> str:
    return uuid4().hex[:10]


def _ncm() -> str:
    return str(71000000 + (uuid4().int % 9999999)).zfill(8)[:8]


def _create_stock_product(company_id: str, headers: dict[str, str]) -> str:
    suffix = _suffix()
    ncm = _ncm()
    fiscal_response = client.post(
        "/fiscal/classifications",
        json={
            "company_id": company_id,
            "name": f"NCM Estoque Perf {suffix}",
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

    product_response = client.post(
        "/catalog/items",
        json={
            "company_id": company_id,
            "item_type": "product",
            "name": f"Produto Estoque Perf {suffix}",
            "sku": f"STPERF-{suffix}",
            "unit": "UN",
            "status": "active",
            "financial_settings": {
                "default_sale_price": "50.00",
                "default_cost_price": "20.00",
                "allow_price_override": False,
            },
            "fiscal_settings": {
                "ncm": ncm,
                "fiscal_classification_id": fiscal_response.json()["data"]["id"],
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
    return str(product_response.json()["data"]["id"])


def _ensure_default_location(company_id: str, headers: dict[str, str]) -> str:
    response = client.post("/stock/locations/default", params={"company_id": company_id}, headers=headers)
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["id"])


def _seed_purchase_entries(company_id: str, product_id: str, location_id: str, headers: dict[str, str], *, prefix: str, total: int = 10) -> None:
    for index in range(total):
        response = client.post(
            "/stock/purchase-entries",
            json={
                "company_id": company_id,
                "location_id": location_id,
                "document_type": "purchase_invoice",
                "document_number": f"{prefix}-{index:03d}",
                "items": [
                    {
                        "item_id": product_id,
                        "quantity": "1",
                        "unit_cost": "10.00",
                        "unit": "UN",
                        "lot_code": f"{prefix}-LOTE-{index:03d}",
                        "expiration_date": "2031-12-31",
                    }
                ],
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text


def test_stock_lists_keep_constant_query_budget_with_purchase_items():
    auth = get_auth_context(client)
    product_id = _create_stock_product(auth.company_id, auth.headers)
    location_id = _ensure_default_location(auth.company_id, auth.headers)
    prefix = f"STPERF-{_suffix().upper()}"
    _seed_purchase_entries(auth.company_id, product_id, location_id, auth.headers, prefix=prefix)

    with QueryCounter() as purchase_counter:
        purchase_response = client.get(
            "/stock/purchase-entries",
            params={
                "company_id": auth.company_id,
                "document_number": prefix,
                "location_id": location_id,
                "include_items": True,
                "limit": 10,
                "offset": 0,
            },
            headers=auth.headers,
        )

    assert purchase_response.status_code == 200, purchase_response.text
    purchase_rows = purchase_response.json()["data"]
    assert len(purchase_rows) == 10
    assert all(row["items"] and len(row["items"]) == 1 for row in purchase_rows)
    assert purchase_counter.count <= 12, f"entradas com itens executaram {purchase_counter.count} queries"

    with QueryCounter() as balances_counter:
        balances_response = client.get(
            "/stock/balances",
            params={"company_id": auth.company_id, "item_id": product_id, "limit": 10, "offset": 0},
            headers=auth.headers,
        )

    assert balances_response.status_code == 200, balances_response.text
    assert balances_response.json()["data"]
    assert balances_counter.count <= 8, f"saldos executaram {balances_counter.count} queries"

    with QueryCounter() as movements_counter:
        movements_response = client.get(
            "/stock/movements",
            params={
                "company_id": auth.company_id,
                "item_id": product_id,
                "source_type": "purchase_entry",
                "limit": 10,
                "offset": 0,
            },
            headers=auth.headers,
        )

    assert movements_response.status_code == 200, movements_response.text
    assert len(movements_response.json()["data"]) >= 10
    assert movements_counter.count <= 8, f"movimentos executaram {movements_counter.count} queries"
