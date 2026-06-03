from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.imports.schemas import MAX_IMPORT_CELL_LENGTH, MAX_IMPORT_COLUMNS, MAX_IMPORT_ROWS
from tests.regression.auth_helpers import get_auth_context


client = TestClient(app)


def _suffix() -> str:
    return uuid4().hex[:10]


def _ncm() -> str:
    return str(80000000 + (uuid4().int % 9999999)).zfill(8)[:8]


def _post_preview(auth, target: str, rows: list[dict]):
    return client.post(
        f"/imports/{target}/preview",
        json={"company_id": auth.company_id, "rows": rows},
        headers=auth.headers,
    )


def _post_commit(auth, target: str, rows: list[dict]):
    return client.post(
        f"/imports/{target}/commit",
        json={"company_id": auth.company_id, "rows": rows},
        headers=auth.headers,
    )


def _valid_participant_row(suffix: str) -> dict:
    return {
        "participant_type": "customer",
        "person_type": "company",
        "name": f"Cliente Importacao {suffix}",
        "document": f"88{suffix[:10].upper()}AA",
        "email": f"cliente.{suffix}@kovirerp.com.br",
        "phone": "11999999999",
        "status": "active",
        "origin": "import",
        "tags": "legado; cliente",
    }


def _valid_fiscal_row(suffix: str, ncm: str) -> dict:
    return {
        "name": f"NCM Importacao {suffix}",
        "item_type": "product",
        "tax_regime": "simples_nacional",
        "ncm": ncm,
        "cfop_default": "5102",
        "origem_mercadoria": "0",
        "subject_to_icms": "sim",
        "subject_to_ibs_cbs": "sim",
        "status": "active",
        "source_reference": f"legacy-{suffix}",
    }


def _valid_product_row(suffix: str, ncm: str) -> dict:
    return {
        "name": f"Produto Importacao {suffix}",
        "sku": f"IMP-{suffix}",
        "barcode": f"789{uuid4().int % 10**10:010d}",
        "unit": "UN",
        "brand": "Kovir Test",
        "category": "Importacao",
        "ncm": ncm,
        "sale_price": "129,90",
        "cost_price": "80,00",
        "track_stock": "sim",
        "stock_unit": "UN",
        "minimum_stock": "5",
        "status": "active",
    }


def test_import_templates_require_auth_and_list_three_targets():
    unauthenticated = client.get("/imports/templates")
    assert unauthenticated.status_code == 401

    auth = get_auth_context(client)
    response = client.get("/imports/templates", headers=auth.headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    targets = {item["target"] for item in payload["data"]}
    assert {"participants", "products", "fiscal-classifications"}.issubset(targets)


def test_import_participants_preview_commit_and_duplicate_validation():
    auth = get_auth_context(client)
    suffix = _suffix()
    row = _valid_participant_row(suffix)

    preview = _post_preview(auth, "participants", [row])
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()["data"]
    assert preview_data["total_rows"] == 1
    assert preview_data["valid_rows"] == 1
    assert preview_data["invalid_rows"] == 0
    assert preview_data["rows"][0]["payload"]["name"] == row["name"]

    commit = _post_commit(auth, "participants", [row])
    assert commit.status_code == 200, commit.text
    commit_data = commit.json()["data"]
    assert commit_data["created_rows"] == 1
    assert commit_data["failed_rows"] == 0
    assert commit_data["created"][0]["id"]

    duplicate_preview = _post_preview(auth, "participants", [row])
    assert duplicate_preview.status_code == 200, duplicate_preview.text
    duplicate_data = duplicate_preview.json()["data"]
    assert duplicate_data["invalid_rows"] == 1
    assert "participante cadastrado" in " ".join(duplicate_data["rows"][0]["errors"]).lower()

    sheet_duplicate_document = f"77{_suffix().upper()}BB"
    duplicate_inside_sheet = _post_preview(
        auth,
        "participants",
        [
            {**_valid_participant_row(_suffix()), "document": sheet_duplicate_document},
            {**_valid_participant_row(_suffix()), "document": sheet_duplicate_document},
        ],
    )
    assert duplicate_inside_sheet.status_code == 200, duplicate_inside_sheet.text
    duplicate_sheet_data = duplicate_inside_sheet.json()["data"]
    assert duplicate_sheet_data["valid_rows"] == 1
    assert duplicate_sheet_data["invalid_rows"] == 1
    assert "documento duplicado" in " ".join(duplicate_sheet_data["rows"][1]["errors"]).lower()


def test_import_participants_commit_rejects_invalid_rows_without_creating():
    auth = get_auth_context(client)
    response = _post_commit(
        auth,
        "participants",
        [
            {
                "participant_type": "customer",
                "person_type": "company",
                "name": "",
            }
        ],
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["created_rows"] == 0
    assert data["failed_rows"] == 1
    assert data["failures"][0]["errors"]


def test_import_fiscal_classifications_preview_commit_and_warnings():
    auth = get_auth_context(client)
    suffix = _suffix()
    ncm = _ncm()
    row = _valid_fiscal_row(suffix, ncm)

    preview = _post_preview(auth, "fiscal-classifications", [row, row])
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()["data"]
    assert preview_data["valid_rows"] == 2
    assert preview_data["invalid_rows"] == 0
    assert preview_data["rows"][1]["warnings"]

    commit = _post_commit(auth, "fiscal-classifications", [row])
    assert commit.status_code == 200, commit.text
    commit_data = commit.json()["data"]
    assert commit_data["created_rows"] == 1
    assert commit_data["failed_rows"] == 0
    assert commit_data["created"][0]["id"]

    invalid = _post_preview(
        auth,
        "fiscal-classifications",
        [{"name": f"Fiscal Sem NCM {suffix}", "item_type": "product"}],
    )
    assert invalid.status_code == 200, invalid.text
    invalid_data = invalid.json()["data"]
    assert invalid_data["invalid_rows"] == 1
    assert "ncm" in " ".join(invalid_data["rows"][0]["errors"]).lower()


def test_import_fiscal_classification_accepts_excel_serial_date():
    auth = get_auth_context(client)
    suffix = _suffix()
    ncm = _ncm()

    preview = _post_preview(
        auth,
        "fiscal-classifications",
        [
            {
                **_valid_fiscal_row(suffix, ncm),
                "valid_from": "46143",
            }
        ],
    )

    assert preview.status_code == 200, preview.text
    row = preview.json()["data"]["rows"][0]
    assert row["status"] == "valid"
    assert row["payload"]["valid_from"] == "2026-05-01"


def test_import_products_requires_existing_fiscal_classification_and_commits():
    auth = get_auth_context(client)
    suffix = _suffix()
    ncm = _ncm()
    product_row = _valid_product_row(suffix, ncm)

    missing_fiscal_preview = _post_preview(auth, "products", [product_row])
    assert missing_fiscal_preview.status_code == 200, missing_fiscal_preview.text
    missing_data = missing_fiscal_preview.json()["data"]
    assert missing_data["invalid_rows"] == 1
    assert "ncm nao encontrado" in " ".join(missing_data["rows"][0]["errors"]).lower()

    fiscal_commit = _post_commit(auth, "fiscal-classifications", [_valid_fiscal_row(suffix, ncm)])
    assert fiscal_commit.status_code == 200, fiscal_commit.text
    assert fiscal_commit.json()["data"]["created_rows"] == 1

    preview = _post_preview(auth, "products", [product_row])
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()["data"]
    assert preview_data["valid_rows"] == 1
    assert preview_data["invalid_rows"] == 0
    assert preview_data["rows"][0]["payload"]["sku"] == product_row["sku"]

    commit = _post_commit(auth, "products", [product_row])
    assert commit.status_code == 200, commit.text
    commit_data = commit.json()["data"]
    assert commit_data["created_rows"] == 1
    assert commit_data["failed_rows"] == 0
    assert commit_data["created"][0]["id"]

    duplicate_sku_preview = _post_preview(auth, "products", [{**_valid_product_row(_suffix(), ncm), "sku": product_row["sku"]}])
    assert duplicate_sku_preview.status_code == 200, duplicate_sku_preview.text
    duplicate_data = duplicate_sku_preview.json()["data"]
    assert duplicate_data["invalid_rows"] == 1
    assert "sku" in " ".join(duplicate_data["rows"][0]["errors"]).lower()


def test_import_products_rejects_duplicate_sku_inside_sheet():
    auth = get_auth_context(client)
    suffix = _suffix()
    ncm = _ncm()
    fiscal_commit = _post_commit(auth, "fiscal-classifications", [_valid_fiscal_row(suffix, ncm)])
    assert fiscal_commit.status_code == 200, fiscal_commit.text

    sku = f"IMP-DUP-{suffix}"
    rows = [
        {**_valid_product_row(_suffix(), ncm), "sku": sku},
        {**_valid_product_row(_suffix(), ncm), "sku": sku},
    ]

    preview = _post_preview(auth, "products", rows)
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["valid_rows"] == 1
    assert data["invalid_rows"] == 1
    assert "sku duplicado" in " ".join(data["rows"][1]["errors"]).lower()


def test_import_invalid_target_returns_validation_error():
    auth = get_auth_context(client)
    response = _post_preview(auth, "unknown-target", [])
    assert response.status_code == 422


def test_import_payload_rejects_row_count_above_limit():
    auth = get_auth_context(client)
    rows = [{"name": f"Cliente {index}"} for index in range(MAX_IMPORT_ROWS + 1)]

    response = _post_preview(auth, "participants", rows)

    assert response.status_code == 422


def test_import_payload_rejects_excessive_columns_and_cell_size():
    auth = get_auth_context(client)
    too_many_columns = {f"coluna_{index}": "valor" for index in range(MAX_IMPORT_COLUMNS + 1)}
    columns_response = _post_preview(auth, "participants", [too_many_columns])

    assert columns_response.status_code == 422
    assert "colunas" in columns_response.text.lower()

    long_value_response = _post_preview(
        auth,
        "participants",
        [{"name": "A" * (MAX_IMPORT_CELL_LENGTH + 1)}],
    )

    assert long_value_response.status_code == 422
    assert "caracteres" in long_value_response.text.lower()


def test_import_payload_rejects_nested_cell_values():
    auth = get_auth_context(client)
    response = _post_preview(auth, "participants", [{"name": {"nested": "Cliente"}}])

    assert response.status_code == 422
