from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.modules.company.db_models import CompanyDB
from app.modules.security.db_models import CompanyUserDB, RoleDB, UserDB, UserRoleDB
from app.modules.security.service import _hash_password, ensure_security_catalog
from app.shared.datetime import utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


@dataclass(frozen=True)
class LimitedAuth:
    company_id: str
    user_id: str
    headers: dict[str, str]


def _limited_user_auth(company_id: str, *, role_code: str = "viewer") -> LimitedAuth:
    email = f"limited.{uuid4().hex}@kovir.local"
    password = "Limited@123"
    now = utc_now()

    with SessionLocal() as db:
        ensure_security_catalog(db)
        role = db.scalar(select(RoleDB).where(RoleDB.code == role_code))
        assert role is not None

        password_hash, password_salt = _hash_password(password)
        user = UserDB(
            id=generate_id("user"),
            full_name="Usuario Limitado Regressao",
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.flush()
        db.add(
            CompanyUserDB(
                id=generate_id("cmpusr"),
                company_id=company_id,
                user_id=user.id,
                status="active",
                joined_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            UserRoleDB(
                id=generate_id("urole"),
                user_id=user.id,
                role_id=role.id,
                company_id=company_id,
                created_at=now,
            )
        )
        db.commit()
        user_id = user.id

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "company_id": company_id},
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]
    return LimitedAuth(company_id=company_id, user_id=user_id, headers={"Authorization": f"Bearer {token}"})


def _assert_forbidden(response, permission_code: str) -> None:
    assert response.status_code == 403, response.text
    assert permission_code in response.json()["detail"]


def test_company_routes_are_session_scoped_and_write_protected():
    admin = get_auth_context(client)
    viewer = _limited_user_auth(admin.company_id)

    read_response = client.get(f"/companies/{admin.company_id}", headers=viewer.headers)
    assert read_response.status_code == 200, read_response.text

    rules_response = client.get("/system/company-rules", headers=viewer.headers)
    assert rules_response.status_code == 200, rules_response.text

    diagnostics_response = client.get("/system/company-diagnostics", headers=viewer.headers)
    assert diagnostics_response.status_code == 200, diagnostics_response.text
    assert diagnostics_response.json()["data"]["total_companies"] == 1

    write_response = client.patch(
        f"/companies/{admin.company_id}",
        json={"trade_name": "Empresa sem permissao"},
        headers=viewer.headers,
    )
    _assert_forbidden(write_response, "company.write")

    cross_tenant_write = client.patch(
        "/companies/emp_outro_tenant",
        json={"trade_name": "Outro tenant"},
        headers=admin.headers,
    )
    assert cross_tenant_write.status_code == 403, cross_tenant_write.text


def test_company_fiscal_fields_are_persisted_without_leaking_focus_token():
    admin = get_auth_context(client)

    response = client.patch(
        f"/companies/{admin.company_id}",
        json={
            "fiscal_settings": {
                "crt": "1",
                "nfe_serie": "2",
                "nfce_serie": "3",
                "focus_nfe_token": "token-secreto-regressao",
            }
        },
        headers=admin.headers,
    )
    assert response.status_code == 200, response.text
    fiscal_settings = response.json()["data"]["fiscal_settings"]
    assert fiscal_settings["crt"] == "1"
    assert fiscal_settings["nfe_serie"] == "2"
    assert fiscal_settings["nfce_serie"] == "3"
    assert fiscal_settings["focus_nfe_token"] is None
    assert fiscal_settings["focus_nfe_token_configured"] is True


def test_inactive_company_blocks_authenticated_session():
    admin = get_auth_context(client)

    with SessionLocal() as db:
        company = db.get(CompanyDB, admin.company_id)
        assert company is not None
        original_status = company.status
        company.status = "blocked"
        db.commit()

    try:
        response = client.get(f"/companies/{admin.company_id}", headers=admin.headers)
        assert response.status_code == 403, response.text
        assert "Empresa inativa ou bloqueada" in response.json()["detail"]
    finally:
        with SessionLocal() as db:
            company = db.get(CompanyDB, admin.company_id)
            assert company is not None
            company.status = original_status
            db.commit()


def test_limited_user_cannot_write_participants_or_catalog():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)

    participant = client.post(
        "/participants",
        json={
            "company_id": limited.company_id,
            "participant_type": "customer",
            "person_type": "individual",
            "name": "Cliente Bloqueado",
            "status": "active",
        },
        headers=limited.headers,
    )
    _assert_forbidden(participant, "participants.write")

    catalog = client.post(
        "/catalog/items",
        json={
            "company_id": limited.company_id,
            "item_type": "service",
            "name": "Servico Bloqueado",
            "financial_settings": {"default_sale_price": "10.00"},
        },
        headers=limited.headers,
    )
    _assert_forbidden(catalog, "catalog.write")

    fiscal_profile = client.post(
        "/fiscal/profiles",
        json={"company_id": limited.company_id, "name": "Perfil Fiscal Bloqueado"},
        headers=limited.headers,
    )
    _assert_forbidden(fiscal_profile, "fiscal.write")


def test_catalog_requires_view_permission_and_returns_real_total():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)
    prefix = f"Catalogo Paginado {uuid4().hex[:8]}"

    created_ids: list[str] = []
    for index in range(3):
        response = client.post(
            "/catalog/items",
            json={
                "company_id": admin.company_id,
                "item_type": "service",
                "name": f"{prefix} {index}",
                "unit": "HORA",
                "status": "active",
                "financial_settings": {"default_sale_price": "10.00"},
            },
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["data"]["id"])

    read_response = client.get(
        "/catalog/items",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(read_response, "view.catalog")

    detail_response = client.get(f"/catalog/items/{created_ids[0]}", headers=limited.headers)
    _assert_forbidden(detail_response, "view.catalog")

    audit_response = client.get(f"/catalog/items/{created_ids[0]}/audit", headers=limited.headers)
    _assert_forbidden(audit_response, "view.catalog")

    rules_response = client.get("/catalog/rules", headers=limited.headers)
    _assert_forbidden(rules_response, "view.catalog")

    diagnostics_response = client.get("/catalog/diagnostics", headers=limited.headers)
    _assert_forbidden(diagnostics_response, "view.catalog")

    paginated_response = client.get(
        "/catalog/items",
        params={
            "company_id": admin.company_id,
            "search": prefix,
            "search_scope": "name",
            "limit": 1,
            "offset": 0,
        },
        headers=admin.headers,
    )
    assert paginated_response.status_code == 200, paginated_response.text
    data = paginated_response.json()["data"]
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 0


def test_participants_requires_view_permission_and_returns_real_total():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)
    prefix = f"Participante Paginado {uuid4().hex[:8]}"

    created_ids: list[str] = []
    for index in range(3):
        response = client.post(
            "/participants",
            json={
                "company_id": admin.company_id,
                "participant_type": "customer",
                "person_type": "individual",
                "name": f"{prefix} {index}",
                "document": f"{uuid4().hex[:10]}{index}",
                "status": "active",
            },
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["data"]["id"])

    read_response = client.get(
        "/participants",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(read_response, "view.participants")

    detail_response = client.get(f"/participants/{created_ids[0]}", headers=limited.headers)
    _assert_forbidden(detail_response, "view.participants")

    audit_response = client.get(f"/participants/{created_ids[0]}/audit", headers=limited.headers)
    _assert_forbidden(audit_response, "view.participants")

    rules_response = client.get("/system/participant-rules", headers=limited.headers)
    _assert_forbidden(rules_response, "view.participants")

    summary_response = client.get(
        "/participants/summary",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(summary_response, "view.participants")

    diagnostics_response = client.get("/system/participant-diagnostics", headers=limited.headers)
    _assert_forbidden(diagnostics_response, "view.participants")

    paginated_response = client.get(
        "/participants",
        params={"company_id": admin.company_id, "search": prefix, "limit": 1, "offset": 0},
        headers=admin.headers,
    )
    assert paginated_response.status_code == 200, paginated_response.text
    data = paginated_response.json()["data"]
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 0

    cross_tenant_create = client.post(
        "/participants",
        json={
            "company_id": "emp_outro_tenant",
            "participant_type": "customer",
            "person_type": "individual",
            "name": "Participante outro tenant",
        },
        headers=admin.headers,
    )
    assert cross_tenant_create.status_code == 403, cross_tenant_create.text


def test_limited_user_cannot_execute_stock_mutations():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)

    movement = client.post(
        "/stock/movements",
        json={
            "company_id": limited.company_id,
            "item_id": "item_fake",
            "movement_type": "manual_entry",
            "quantity": "1",
            "lot_code": "LOTE-SEM-PERMISSAO",
        },
        headers=limited.headers,
    )
    _assert_forbidden(movement, "stock.move")

    purchase_parse = client.post(
        "/stock/purchase-entries/parse-xml",
        json={"company_id": limited.company_id, "xml_text": "<nfe>12345678901234567890</nfe>"},
        headers=limited.headers,
    )
    _assert_forbidden(purchase_parse, "stock.purchase_entry")


def test_limited_user_cannot_read_stock_without_view_permission():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)

    balances = client.get(
        "/stock/balances",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(balances, "view.stock")

    diagnostics = client.get(
        "/stock/diagnostics",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(diagnostics, "view.stock")


def test_limited_user_cannot_execute_sales_cash_or_fiscal_actions():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)

    sales_list = client.get("/sales", params={"company_id": limited.company_id}, headers=limited.headers)
    _assert_forbidden(sales_list, "sales.view")

    sales_summary = client.get("/sales/summary", params={"company_id": limited.company_id}, headers=limited.headers)
    _assert_forbidden(sales_summary, "sales.view")

    sales_detail = client.get("/sales/sale_fake", headers=limited.headers)
    _assert_forbidden(sales_detail, "sales.view")

    sale = client.post(
        "/sales",
        json={
            "company_id": limited.company_id,
            "sale_type": "service",
            "origin": "manual",
            "participant_id": "part_fake",
            "items": [{"item_id": "item_fake", "quantity": "1"}],
            "payment_plans": [{"amount": "10.00", "payment_method_code": "pix"}],
        },
        headers=limited.headers,
    )
    _assert_forbidden(sale, "sales.create")

    close = client.post("/sales/sale_fake/confirm", json={}, headers=limited.headers)
    _assert_forbidden(close, "sales.close")

    cancel = client.post("/sales/sale_fake/cancel", json={"reason": "Sem permissao"}, headers=limited.headers)
    _assert_forbidden(cancel, "sales.cancel")

    pay = client.post("/sales/sale_fake/pay", json={}, headers=limited.headers)
    _assert_forbidden(pay, "sales.pay")

    settlement = client.post(
        "/cash/settlements",
        json={
            "company_id": limited.company_id,
            "financial_title_id": "ar_fake",
            "financial_account_id": "bankacc_fake",
            "settlement_date": "2026-05-08",
            "competency_date": "2026-05-08",
            "received_amount": "10.00",
        },
        headers=limited.headers,
    )
    _assert_forbidden(settlement, "cash.receive")

    manual_movement = client.post(
        "/cash/movements",
        json={
            "company_id": limited.company_id,
            "financial_account_id": "bankacc_fake",
            "direction": "inflow",
            "movement_type": "adjustment",
            "movement_date": "2026-05-08",
            "amount": "10.00",
            "description": "Movimento sem permissao.",
        },
        headers=limited.headers,
    )
    _assert_forbidden(manual_movement, "cash.receive")

    reversal = client.post(
        "/cash/settlements/sett_fake/reverse",
        json={"reason": "Sem permissao"},
        headers=limited.headers,
    )
    _assert_forbidden(reversal, "cash.reverse")

    movement_reversal = client.post(
        "/cash/movements/cash_fake/reverse",
        json={"reason": "Sem permissao"},
        headers=limited.headers,
    )
    _assert_forbidden(movement_reversal, "cash.reverse")

    invoice = client.post("/sales/sale_fake/invoice", headers=limited.headers)
    _assert_forbidden(invoice, "fiscal.issue")

    fiscal_docs = client.get("/fiscal-documents/sale/sale_fake", headers=limited.headers)
    _assert_forbidden(fiscal_docs, "fiscal.issue")


def test_fiscal_classification_requires_view_permission_and_returns_real_total():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)
    prefix = f"Fiscal Paginado {uuid4().hex[:8]}"

    created_ids: list[str] = []
    for index in range(3):
        response = client.post(
            "/fiscal/classifications",
            json={
                "company_id": admin.company_id,
                "name": f"{prefix} {index}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": f"1234567{index}",
                "status": "active",
            },
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["data"]["id"])

    read_response = client.get(
        "/fiscal/classifications",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(read_response, "view.fiscalClassification")

    detail_response = client.get(f"/fiscal/classifications/{created_ids[0]}", headers=limited.headers)
    _assert_forbidden(detail_response, "view.fiscalClassification")

    audit_response = client.get(f"/fiscal/classifications/{created_ids[0]}/audit", headers=limited.headers)
    _assert_forbidden(audit_response, "view.fiscalClassification")

    rules_response = client.get("/fiscal/rules", headers=limited.headers)
    _assert_forbidden(rules_response, "view.fiscalClassification")

    diagnostics_response = client.get("/fiscal/diagnostics", headers=limited.headers)
    _assert_forbidden(diagnostics_response, "view.fiscalClassification")

    paginated_response = client.get(
        "/fiscal/classifications",
        params={"company_id": admin.company_id, "search": prefix, "limit": 1, "offset": 0},
        headers=admin.headers,
    )
    assert paginated_response.status_code == 200, paginated_response.text
    data = paginated_response.json()["data"]
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["limit"] == 1
    assert data["offset"] == 0


def test_limited_user_cannot_read_cash_overview_without_view_permission():
    admin = get_auth_context(client)
    limited = _limited_user_auth(admin.company_id)

    summary = client.get(
        "/cash/summary",
        params={"company_id": limited.company_id},
        headers=limited.headers,
    )
    _assert_forbidden(summary, "view.cash")


def test_financial_base_requires_read_and_write_permissions():
    admin = get_auth_context(client)
    viewer = _limited_user_auth(admin.company_id)
    finance_operator = _limited_user_auth(admin.company_id, role_code="finance_operator")

    read_response = client.get(
        "/financial/accounts",
        params={"company_id": viewer.company_id},
        headers=viewer.headers,
    )
    _assert_forbidden(read_response, "finance.read")

    write_response = client.post(
        "/financial/defaults",
        params={"company_id": finance_operator.company_id},
        headers=finance_operator.headers,
    )
    _assert_forbidden(write_response, "finance.write")


def test_accounts_receivable_requires_view_read_and_write_permissions():
    admin = get_auth_context(client)
    viewer = _limited_user_auth(admin.company_id)
    finance_operator = _limited_user_auth(admin.company_id, role_code="finance_operator")

    read_response = client.get(
        "/accounts-receivable/summary",
        params={"company_id": viewer.company_id},
        headers=viewer.headers,
    )
    _assert_forbidden(read_response, "view.accountsReceivable")

    write_response = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": finance_operator.company_id,
            "participant_id": "part_fake",
            "due_date": "2099-05-08",
            "gross_amount": "10.00",
            "fiscal_status": "not_required",
        },
        headers=finance_operator.headers,
    )
    _assert_forbidden(write_response, "finance.write")


def test_purchases_payables_requires_view_permission():
    admin = get_auth_context(client)
    viewer = _limited_user_auth(admin.company_id)

    read_response = client.get(
        "/purchases-payables/summary",
        params={"company_id": viewer.company_id},
        headers=viewer.headers,
    )
    _assert_forbidden(read_response, "view.purchasesPayables")


def test_accounts_receivable_rejects_cross_tenant_company_scope():
    admin = get_auth_context(client)

    summary_response = client.get(
        "/accounts-receivable/summary",
        params={"company_id": "emp_outro_tenant"},
        headers=admin.headers,
    )
    assert summary_response.status_code == 403, summary_response.text

    create_response = client.post(
        "/accounts-receivable/titles",
        json={
            "company_id": "emp_outro_tenant",
            "participant_id": "part_fake",
            "due_date": "2099-05-08",
            "gross_amount": "10.00",
            "fiscal_status": "not_required",
        },
        headers=admin.headers,
    )
    assert create_response.status_code == 403, create_response.text


def test_financial_diagnostics_are_tenant_scoped_and_count_active_records():
    admin = get_auth_context(client)

    defaults = client.post(
        "/financial/defaults",
        params={"company_id": admin.company_id},
        headers=admin.headers,
    )
    assert defaults.status_code == 201, defaults.text

    diagnostics = client.get(
        "/financial/diagnostics",
        params={"company_id": admin.company_id},
        headers=admin.headers,
    )
    assert diagnostics.status_code == 200, diagnostics.text
    data = diagnostics.json()["data"]
    assert data["records_count"]["financial_accounts"] >= 0
    assert data["active_records_count"]["chart_accounts"] >= 1
    assert data["active_records_count"]["financial_categories"] >= 1
    assert data["active_records_count"]["payment_terms"] >= 1

    other_company = client.get(
        "/financial/diagnostics",
        params={"company_id": "emp_outro_tenant"},
        headers=admin.headers,
    )
    assert other_company.status_code == 403, other_company.text


def test_stock_diagnostics_are_tenant_scoped():
    admin = get_auth_context(client)

    diagnostics = client.get(
        "/stock/diagnostics",
        params={"company_id": admin.company_id},
        headers=admin.headers,
    )
    assert diagnostics.status_code == 200, diagnostics.text
    data = diagnostics.json()["data"]
    assert data["company_id"] == admin.company_id
    assert data["total_locations"] >= 0
    assert data["total_movements"] >= 0
    assert data["total_purchase_entries"] >= 0

    other_company = client.get(
        "/stock/diagnostics",
        params={"company_id": "emp_outro_tenant"},
        headers=admin.headers,
    )
    assert other_company.status_code == 403, other_company.text
