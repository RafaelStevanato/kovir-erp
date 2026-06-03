from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.purchases_payables.db_models import PurchaseDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def _before_cursor_execute(self, *_args) -> None:
        self.count += 1

    def __enter__(self) -> "_QueryCounter":
        event.listen(engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(engine, "before_cursor_execute", self._before_cursor_execute)


def _create_payables_overview_fixture(company_id: str, participant_id: str) -> dict[str, str]:
    now = utc_now()
    today = today_in_brazil()
    suffix = uuid4().hex[:8]
    open_id = generate_id("ap")
    overdue_id = generate_id("ap")
    paid_id = generate_id("ap")
    draft_purchase_id = generate_id("buy")
    confirmed_purchase_id = generate_id("buy")

    with SessionLocal() as db:
        db.add_all(
            [
                FinancialTitleDB(
                    id=open_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="overview_test",
                    source_id=f"open-{suffix}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id, "name": f"Fornecedor Overview {suffix}"},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name=None,
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=None,
                    document_reference=f"OV-OPEN-{suffix}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=today + timedelta(days=7),
                    expected_payment_date=today + timedelta(days=7),
                    gross_amount=Decimal("100.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("100.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("100.00"),
                    status="open",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao overview AP aberto.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=overdue_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="overview_test",
                    source_id=f"overdue-{suffix}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id, "name": f"Fornecedor Vencido {suffix}"},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name=None,
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=None,
                    document_reference=f"OV-OVERDUE-{suffix}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=today - timedelta(days=1),
                    expected_payment_date=today - timedelta(days=1),
                    gross_amount=Decimal("50.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("50.00"),
                    paid_amount=Decimal("0.00"),
                    open_amount=Decimal("50.00"),
                    status="open",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao overview AP vencido.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=paid_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="overview_test",
                    source_id=f"paid-{suffix}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id, "name": f"Fornecedor Pago {suffix}"},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name=None,
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=None,
                    document_reference=f"OV-PAID-{suffix}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=today,
                    expected_payment_date=today,
                    gross_amount=Decimal("30.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("30.00"),
                    paid_amount=Decimal("30.00"),
                    open_amount=Decimal("0.00"),
                    status="paid",
                    collection_status="closed",
                    fiscal_status="not_required",
                    notes="Regressao overview AP pago.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                PurchaseDB(
                    id=draft_purchase_id,
                    company_id=company_id,
                    establishment_id=None,
                    participant_id=participant_id,
                    status="draft",
                    purchase_type="expense",
                    origin="manual",
                    operation_nature_id=None,
                    fiscal_status="not_required",
                    issue_date=today,
                    operation_date=now,
                    competency_date=today,
                    subtotal_amount=Decimal("12.00"),
                    discount_amount=Decimal("0.00"),
                    freight_amount=Decimal("0.00"),
                    tax_amount=Decimal("0.00"),
                    total_amount=Decimal("12.00"),
                    payable_total_amount=Decimal("12.00"),
                    invoice_total_amount=None,
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=None,
                    document_type="invoice",
                    document_number=f"OV-DRAFT-{suffix}",
                    document_series=None,
                    access_key=None,
                    participant_snapshot_json={"id": participant_id},
                    document_snapshot_json={},
                    metadata_json={},
                    notes="Regressao overview compra rascunho.",
                    created_at=now,
                    updated_at=now,
                    confirmed_at=None,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                PurchaseDB(
                    id=confirmed_purchase_id,
                    company_id=company_id,
                    establishment_id=None,
                    participant_id=participant_id,
                    status="confirmed",
                    purchase_type="expense",
                    origin="manual",
                    operation_nature_id=None,
                    fiscal_status="not_required",
                    issue_date=today,
                    operation_date=now,
                    competency_date=today,
                    subtotal_amount=Decimal("18.00"),
                    discount_amount=Decimal("0.00"),
                    freight_amount=Decimal("0.00"),
                    tax_amount=Decimal("0.00"),
                    total_amount=Decimal("18.00"),
                    payable_total_amount=Decimal("18.00"),
                    invoice_total_amount=None,
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=None,
                    document_type="invoice",
                    document_number=f"OV-CONF-{suffix}",
                    document_series=None,
                    access_key=None,
                    participant_snapshot_json={"id": participant_id},
                    document_snapshot_json={},
                    metadata_json={},
                    notes="Regressao overview compra confirmada.",
                    created_at=now,
                    updated_at=now,
                    confirmed_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
            ]
        )
        db.commit()

    return {
        "open_id": open_id,
        "overdue_id": overdue_id,
        "paid_id": paid_id,
        "draft_purchase_id": draft_purchase_id,
        "confirmed_purchase_id": confirmed_purchase_id,
    }


def _create_payment_fixture(company_id: str, participant_id: str) -> dict[str, str]:
    now = utc_now()
    today = today_in_brazil()
    suffix = uuid4().hex[:8]
    account_id = generate_id("bankacc")
    title_id = generate_id("ap")
    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta AP {suffix}",
                account_type="bank",
                institution_name="Banco Regressao",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("200.00"),
                is_default_receivable=False,
                is_default_payable=True,
                status="active",
                notes=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        db.flush()
        db.add(
            FinancialTitleDB(
                id=title_id,
                company_id=company_id,
                direction="payable",
                title_type="manual",
                source_type="payment_test",
                source_id=f"payment-{suffix}",
                source_snapshot_json={},
                sale_id=None,
                sale_payment_plan_id=None,
                participant_id=participant_id,
                participant_snapshot_json={"id": participant_id, "name": f"Fornecedor Pagamento {suffix}"},
                payment_method_id=None,
                payment_method_code=None,
                payment_method_name=None,
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=account_id,
                document_reference=f"PAY-{suffix}",
                installment_number=1,
                installment_total=1,
                issue_date=today,
                competency_date=today,
                due_date=today,
                expected_payment_date=today,
                gross_amount=Decimal("50.00"),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                net_amount=Decimal("50.00"),
                paid_amount=Decimal("0.00"),
                open_amount=Decimal("50.00"),
                status="open",
                collection_status="not_started",
                fiscal_status="not_required",
                notes="Regressao pagamento AP.",
                metadata_json={},
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                deleted_at=None,
            )
        )
        db.commit()
    return {"account_id": account_id, "title_id": title_id}


def _create_financial_account(company_id: str) -> str:
    now = utc_now()
    account_id = generate_id("bankacc")
    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta AP Compra {uuid4().hex[:8]}",
                account_type="bank",
                institution_name="Banco Regressao",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("500.00"),
                is_default_receivable=False,
                is_default_payable=True,
                status="active",
                notes=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        db.commit()
    return account_id


def test_purchases_payables_overview_evidence_is_scoped_and_query_bounded():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    ids = _create_payables_overview_fixture(auth.company_id, fixtures["participant_id"])

    with _QueryCounter() as counter:
        response = client.get(
            "/purchases-payables/overview-evidence",
            params={"company_id": auth.company_id, "limit": 5000},
            headers=auth.headers,
        )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert ids["open_id"] in {row["id"] for row in data["open_payables"]}
    assert ids["overdue_id"] in {row["id"] for row in data["open_payables"]}
    assert ids["overdue_id"] in {row["id"] for row in data["overdue_payables"]}
    assert ids["paid_id"] in {row["id"] for row in data["paid_payables"]}
    assert ids["draft_purchase_id"] in {row["id"] for row in data["draft_purchases"]}
    assert ids["confirmed_purchase_id"] in {row["id"] for row in data["confirmed_purchases"]}
    assert Decimal(data["summary"]["paid_payable_amount"]) >= Decimal("30.00")
    assert counter.count <= 20

    other_company = client.get(
        "/purchases-payables/overview-evidence",
        params={"company_id": "emp_outro_tenant"},
        headers=auth.headers,
    )
    assert other_company.status_code == 400 or other_company.status_code == 403


def test_purchases_payables_overview_evidence_can_return_single_block():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    ids = _create_payables_overview_fixture(auth.company_id, fixtures["participant_id"])

    response = client.get(
        "/purchases-payables/overview-evidence",
        params={"company_id": auth.company_id, "block": "overdue_payables", "limit": 5000},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert ids["overdue_id"] in {row["id"] for row in data["overdue_payables"]}
    assert data["open_payables"] == []
    assert data["paid_payables"] == []
    assert data["draft_purchases"] == []
    assert data["confirmed_purchases"] == []


def test_payable_payment_requires_evidence_and_allows_multiple_partial_payments():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    payment_fixture = _create_payment_fixture(auth.company_id, fixtures["participant_id"])
    today = today_in_brazil().isoformat()
    base_payload = {
        "company_id": auth.company_id,
        "financial_title_id": payment_fixture["title_id"],
        "financial_account_id": payment_fixture["account_id"],
        "payment_date": today,
        "competency_date": today,
        "paid_amount": "20.00",
        "discount_amount": "0.00",
        "interest_amount": "0.00",
        "penalty_amount": "0.00",
        "fee_amount": "0.00",
        "source_type": "manual",
        "source_id": None,
    }

    missing_evidence = client.post("/purchases-payables/payments", json=base_payload, headers=auth.headers)
    assert missing_evidence.status_code == 400, missing_evidence.text
    assert "comprovante" in missing_evidence.json()["message"].lower()

    discount_only = client.post(
        "/purchases-payables/payments",
        json={**base_payload, "paid_amount": "0.00", "discount_amount": "5.00", "evidence_reference": "DESCONTO-SEM-PAGAMENTO"},
        headers=auth.headers,
    )
    assert discount_only.status_code == 422, discount_only.text

    first_payment = client.post(
        "/purchases-payables/payments",
        json={**base_payload, "evidence_reference": "COMPROVANTE-1"},
        headers=auth.headers,
    )
    assert first_payment.status_code == 201, first_payment.text
    assert first_payment.json()["data"]["title"]["status"] == "partially_paid"
    assert first_payment.json()["data"]["title"]["open_amount"] == "30.00"
    assert "PAY-" in first_payment.json()["data"]["movement"]["description"]
    assert "Fornecedor Pagamento" in first_payment.json()["data"]["movement"]["description"]

    cancel_partial = client.post(
        f"/purchases-payables/payables/{payment_fixture['title_id']}/cancel",
        json={"reason": "Tentativa indevida de cancelar titulo parcialmente pago."},
        headers=auth.headers,
    )
    assert cancel_partial.status_code == 400, cancel_partial.text
    assert "estorno" in cancel_partial.json()["message"].lower()

    second_payment = client.post(
        "/purchases-payables/payments",
        json={**base_payload, "evidence_reference": "COMPROVANTE-2"},
        headers=auth.headers,
    )
    assert second_payment.status_code == 201, second_payment.text
    assert second_payment.json()["data"]["title"]["open_amount"] == "10.00"


def test_purchase_listing_is_light_and_export_uses_backend_filters():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    ids = _create_payables_overview_fixture(auth.company_id, fixtures["participant_id"])

    list_response = client.get(
        "/purchases-payables/purchases",
        params={"company_id": auth.company_id, "status": "draft", "q": ids["draft_purchase_id"], "limit": 1},
        headers=auth.headers,
    )
    assert list_response.status_code == 200, list_response.text
    list_rows = list_response.json()["data"]
    assert len(list_rows) == 1
    assert list_rows[0]["id"] == ids["draft_purchase_id"]
    assert "items" not in list_rows[0]

    export_response = client.get(
        "/purchases-payables/purchases/export",
        params={"company_id": auth.company_id, "status": "confirmed", "q": ids["confirmed_purchase_id"]},
        headers=auth.headers,
    )
    assert export_response.status_code == 200, export_response.text
    export_rows = export_response.json()["data"]
    assert [row["id"] for row in export_rows] == [ids["confirmed_purchase_id"]]
    assert "items" not in export_rows[0]


def test_payable_listing_and_export_use_backend_filters():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    payment_fixture = _create_payment_fixture(auth.company_id, fixtures["participant_id"])

    params = {
        "company_id": auth.company_id,
        "status": "open",
        "expected_financial_account_id": payment_fixture["account_id"],
        "open_amount_min": "50.00",
        "open_amount_max": "50.00",
        "q": payment_fixture["title_id"],
    }

    list_response = client.get(
        "/purchases-payables/payables",
        params={**params, "limit": 1},
        headers=auth.headers,
    )
    assert list_response.status_code == 200, list_response.text
    list_rows = list_response.json()["data"]
    assert [row["id"] for row in list_rows] == [payment_fixture["title_id"]]

    export_response = client.get(
        "/purchases-payables/payables/export",
        params=params,
        headers=auth.headers,
    )
    assert export_response.status_code == 200, export_response.text
    export_rows = export_response.json()["data"]
    assert [row["id"] for row in export_rows] == [payment_fixture["title_id"]]


def test_create_and_confirm_purchase_is_atomic_and_generates_payable():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id)
    today = today_in_brazil().isoformat()
    due_date = (today_in_brazil() + timedelta(days=10)).isoformat()
    document_number = f"AP-ATOMIC-{uuid4().hex[:8]}"

    response = client.post(
        "/purchases-payables/purchases/create-and-confirm",
        json={
            "purchase": {
                "company_id": auth.company_id,
                "participant_id": fixtures["participant_id"],
                "purchase_type": "expense",
                "origin": "manual",
                "fiscal_status": "pending_document",
                "issue_date": today,
                "competency_date": today,
                "expected_financial_account_id": account_id,
                "document_type": "invoice",
                "document_number": document_number,
                "invoice_total_amount": "75.00",
                "items": [{"description": "Obrigacao atomica regressao", "quantity": "1", "unit": "UN", "unit_cost": "75.00"}],
            },
            "confirmation": {
                "reason": "Confirmacao atomica de regressao.",
                "installments": [
                    {
                        "due_date": due_date,
                        "amount": "75.00",
                        "expected_financial_account_id": account_id,
                        "document_reference": document_number,
                    }
                ],
            },
        },
        headers=auth.headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["purchase"]["status"] == "confirmed"
    assert data["purchase"]["issue_date"] == today
    assert data["purchase"]["competency_date"] == today
    assert len(data["payables"]) == 1
    assert data["payables"][0]["document_reference"] == document_number
    assert data["payables"][0]["expected_financial_account_id"] == account_id
    assert data["payables"][0]["due_date"] == due_date
    assert data["payables"][0]["open_amount"] == "75.00"


def test_create_and_confirm_purchase_rolls_back_when_confirmation_fails():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id)
    today = today_in_brazil().isoformat()
    document_number = f"AP-ROLLBACK-{uuid4().hex[:8]}"

    response = client.post(
        "/purchases-payables/purchases/create-and-confirm",
        json={
            "purchase": {
                "company_id": auth.company_id,
                "participant_id": fixtures["participant_id"],
                "purchase_type": "expense",
                "origin": "manual",
                "fiscal_status": "not_required",
                "issue_date": today,
                "competency_date": today,
                "expected_financial_account_id": account_id,
                "document_type": "invoice",
                "document_number": document_number,
                "invoice_total_amount": "80.00",
                "items": [{"description": "Obrigacao rollback regressao", "quantity": "1", "unit": "UN", "unit_cost": "80.00"}],
            },
            "confirmation": {
                "reason": "Confirmacao deve falhar.",
                "installments": [{"due_date": today, "amount": "70.00", "expected_financial_account_id": account_id}],
            },
        },
        headers=auth.headers,
    )
    assert response.status_code == 400, response.text

    list_response = client.get(
        "/purchases-payables/purchases",
        params={"company_id": auth.company_id, "q": document_number, "limit": 10},
        headers=auth.headers,
    )
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["data"] == []


def test_paid_purchase_cannot_be_cancelled_without_reversal_flow():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    account_id = _create_financial_account(auth.company_id)
    today = today_in_brazil().isoformat()

    create_response = client.post(
        "/purchases-payables/purchases",
        json={
            "company_id": auth.company_id,
            "participant_id": fixtures["participant_id"],
            "purchase_type": "expense",
            "origin": "manual",
            "fiscal_status": "not_required",
            "issue_date": today,
            "competency_date": today,
            "expected_financial_account_id": account_id,
            "document_type": "invoice",
            "document_number": f"AP-CANCEL-{uuid4().hex[:8]}",
            "invoice_total_amount": "40.00",
            "items": [{"description": "Compra regressao paga", "quantity": "1", "unit": "UN", "unit_cost": "40.00"}],
        },
        headers=auth.headers,
    )
    assert create_response.status_code == 201, create_response.text
    purchase_id = create_response.json()["data"]["id"]

    confirm_response = client.post(
        f"/purchases-payables/purchases/{purchase_id}/confirm",
        json={
            "reason": "Confirmacao regressao cancelamento pago.",
            "installments": [
                {
                    "due_date": today,
                    "amount": "40.00",
                    "expected_financial_account_id": account_id,
                    "document_reference": f"AP-CANCEL-{uuid4().hex[:8]}",
                }
            ],
        },
        headers=auth.headers,
    )
    assert confirm_response.status_code == 200, confirm_response.text
    title_id = confirm_response.json()["data"]["payables"][0]["id"]

    pay_response = client.post(
        "/purchases-payables/payments",
        json={
            "company_id": auth.company_id,
            "financial_title_id": title_id,
            "financial_account_id": account_id,
            "payment_date": today,
            "competency_date": today,
            "paid_amount": "40.00",
            "discount_amount": "0.00",
            "interest_amount": "0.00",
            "penalty_amount": "0.00",
            "fee_amount": "0.00",
            "source_type": "manual",
            "source_id": None,
            "evidence_reference": "COMPROVANTE-CANCEL-BLOCK",
        },
        headers=auth.headers,
    )
    assert pay_response.status_code == 201, pay_response.text

    cancel_response = client.post(
        f"/purchases-payables/purchases/{purchase_id}/cancel",
        json={"reason": "Tentativa indevida de cancelar compra paga."},
        headers=auth.headers,
    )
    assert cancel_response.status_code == 400, cancel_response.text
    assert "títulos vinculados" in cancel_response.json()["message"]
