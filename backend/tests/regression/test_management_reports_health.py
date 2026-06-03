from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.cash.db_models import FinancialAccountBalanceDB, FinancialMovementDB, SettlementDB
from app.modules.company.schemas import CompanyCreate
from app.modules.company.service import create_company
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.fiscal_documents.db_models import FiscalDocumentDB
from app.modules.reconciliation.db_models import BankStatementLineDB
from app.modules.purchases_payables.db_models import PurchaseDB
from app.modules.sales.db_models import SaleDB
from app.shared.audit import AuditSource
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

client = TestClient(app)


def _create_other_company() -> str:
    with SessionLocal() as db:
        created = create_company(
            db,
            CompanyCreate(
                legal_name=f"Empresa Isolada {uuid4().hex[:8]}",
                trade_name="Empresa Isolada",
                cnpj=None,
                email=None,
                phone=None,
                responsible_name="Regressao",
            ),
            source=AuditSource.TEST,
        )
        db.commit()
        return str(created["id"])


def _create_partially_received_overdue_title(company_id: str, participant_id: str) -> str:
    now = utc_now()
    due_date = today_in_brazil() - timedelta(days=1)
    title_id = generate_id("ar")
    with SessionLocal() as db:
        db.add(
            FinancialTitleDB(
                id=title_id,
                company_id=company_id,
                direction="receivable",
                title_type="manual",
                source_type="manual",
                source_id=f"health-partial-{uuid4().hex}",
                source_snapshot_json={},
                sale_id=None,
                sale_payment_plan_id=None,
                participant_id=participant_id,
                participant_snapshot_json={"id": participant_id},
                payment_method_id=None,
                payment_method_code=None,
                payment_method_name=None,
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=None,
                document_reference=f"HEALTH-{uuid4().hex[:8]}",
                installment_number=1,
                installment_total=1,
                issue_date=due_date,
                competency_date=due_date,
                due_date=due_date,
                expected_payment_date=None,
                gross_amount=Decimal("20.00"),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                net_amount=Decimal("20.00"),
                paid_amount=Decimal("5.00"),
                open_amount=Decimal("15.00"),
                status="partially_received",
                collection_status="in_collection",
                fiscal_status="not_required",
                notes="Regressao: titulo parcialmente recebido vencido deve entrar na saude do Kovir.",
                metadata_json={},
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                deleted_at=None,
            )
        )
        db.commit()
    return title_id


def _create_manual_receivable_title(
    company_id: str,
    participant_id: str,
    *,
    document_reference: str,
    due_days: int = 3,
    amount: str = "31.00",
) -> str:
    now = utc_now()
    due_date = today_in_brazil() + timedelta(days=due_days)
    title_id = generate_id("ar")
    with SessionLocal() as db:
        db.add(
            FinancialTitleDB(
                id=title_id,
                company_id=company_id,
                direction="receivable",
                title_type="manual",
                source_type="manual",
                source_id=f"title-route-{uuid4().hex}",
                source_snapshot_json={},
                sale_id=None,
                sale_payment_plan_id=None,
                participant_id=participant_id,
                participant_snapshot_json={"id": participant_id},
                payment_method_id=None,
                payment_method_code=None,
                payment_method_name="PIX",
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=None,
                document_reference=document_reference,
                installment_number=1,
                installment_total=1,
                issue_date=due_date,
                competency_date=due_date,
                due_date=due_date,
                expected_payment_date=due_date,
                gross_amount=Decimal(amount),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                net_amount=Decimal(amount),
                paid_amount=Decimal("0.00"),
                open_amount=Decimal(amount),
                status="open",
                collection_status="not_started",
                fiscal_status="not_required",
                notes="Regressao: titulo manual para rota de titulos gerenciais.",
                metadata_json={},
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                deleted_at=None,
            )
        )
        db.commit()
    return title_id


def _create_fiscal_pending_title(company_id: str, participant_id: str, amount: str = "77.00") -> str:
    now = utc_now()
    title_id = generate_id("ar")
    with SessionLocal() as db:
        db.add(
            FinancialTitleDB(
                id=title_id,
                company_id=company_id,
                direction="receivable",
                title_type="manual",
                source_type="manual",
                source_id=f"fiscal-title-{uuid4().hex}",
                source_snapshot_json={},
                sale_id=None,
                sale_payment_plan_id=None,
                participant_id=participant_id,
                participant_snapshot_json={"id": participant_id},
                payment_method_id=None,
                payment_method_code=None,
                payment_method_name=None,
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=None,
                document_reference=f"FISCAL-TITLE-{uuid4().hex[:8]}",
                installment_number=1,
                installment_total=1,
                issue_date=today_in_brazil(),
                competency_date=today_in_brazil(),
                due_date=today_in_brazil(),
                expected_payment_date=None,
                gross_amount=Decimal(amount),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                net_amount=Decimal(amount),
                paid_amount=Decimal("0.00"),
                open_amount=Decimal(amount),
                status="open",
                collection_status="not_started",
                fiscal_status="pending_document",
                notes="Regressao: titulo com pendencia fiscal.",
                metadata_json={},
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                deleted_at=None,
            )
        )
        db.commit()
    return title_id


def _create_sale_for_fiscal_report(
    company_id: str,
    participant_id: str,
    *,
    status: str = "closed",
    fiscal_status: str = "pending_document",
    amount: str = "42.00",
) -> str:
    now = utc_now()
    sale_id = generate_id("sale")
    with SessionLocal() as db:
        db.add(
            SaleDB(
                id=sale_id,
                company_id=company_id,
                establishment_id=None,
                participant_id=participant_id,
                status=status,
                sale_type="service",
                origin="manual",
                operation_nature="normal_sale",
                operation_nature_id=None,
                operation_nature_reason=None,
                operation_nature_snapshot_json={"requires_fiscal_document": True},
                fiscal_status=fiscal_status,
                issue_date=None,
                operation_date=now,
                competency_date=today_in_brazil(),
                subtotal_amount=Decimal(amount),
                discount_amount=Decimal("0.00"),
                discount_type="amount",
                discount_percentage=None,
                discount_category=None,
                discount_reason=None,
                freight_amount=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                total_amount=Decimal(amount),
                receivable_total_amount=Decimal(amount),
                invoice_total_amount=Decimal(amount),
                participant_snapshot_json={"id": participant_id, "name": "Cliente Regressao"},
                notes="Regressao: venda para relatorio fiscal.",
                created_at=now,
                updated_at=now,
                cancelled_at=None,
                sale_number=None,
                sale_number_text=f"PED-FISCAL-{uuid4().hex[:6]}",
                paid_number_text=None,
                closed_at=now if status in {"closed", "paid"} else None,
                paid_at=now if status == "paid" else None,
                closed_by=None,
                paid_by=None,
                unlocked_by=None,
                unlocked_at=None,
            )
        )
        db.commit()
    return sale_id


def _create_purchase_for_fiscal_report(
    company_id: str,
    participant_id: str,
    *,
    status: str = "confirmed",
    fiscal_status: str = "pending_document",
    deleted: bool = False,
    amount: str = "55.00",
) -> str:
    now = utc_now()
    purchase_id = generate_id("buy")
    with SessionLocal() as db:
        db.add(
            PurchaseDB(
                id=purchase_id,
                company_id=company_id,
                establishment_id=None,
                participant_id=participant_id,
                status=status,
                purchase_type="expense",
                origin="manual",
                operation_nature_id=None,
                fiscal_status=fiscal_status,
                issue_date=None,
                operation_date=now,
                competency_date=today_in_brazil(),
                subtotal_amount=Decimal(amount),
                discount_amount=Decimal("0.00"),
                freight_amount=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                total_amount=Decimal(amount),
                payable_total_amount=Decimal(amount),
                invoice_total_amount=Decimal(amount),
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=None,
                document_type="nfe",
                document_number=None,
                document_series=None,
                access_key=None,
                participant_snapshot_json={"id": participant_id, "name": "Fornecedor Regressao"},
                document_snapshot_json={},
                metadata_json={},
                notes="Regressao: compra para relatorio fiscal.",
                created_at=now,
                updated_at=now,
                confirmed_at=now if status == "confirmed" else None,
                cancelled_at=None,
                deleted_at=now if deleted else None,
            )
        )
        db.commit()
    return purchase_id


def _create_fiscal_document_for_report(company_id: str, sale_id: str, *, status: str) -> str:
    now = utc_now()
    doc_id = generate_id("fdoc")
    with SessionLocal() as db:
        db.add(
            FiscalDocumentDB(
                id=doc_id,
                company_id=company_id,
                sale_id=sale_id,
                document_type="nfe",
                model="55",
                serie="1",
                number=f"{uuid4().int % 999999}",
                reference=f"fiscal-report-{uuid4().hex}",
                status=status,
                focus_status=status,
                focus_response_json=None,
                access_key=f"352605{uuid4().hex[:38]}",
                protocol=f"PROTO-{uuid4().hex[:8]}",
                error_code="E001" if status == "error" else None,
                error_message="Erro fiscal de regressao." if status == "error" else None,
                danfe_url=None,
                xml_url=None,
                issued_at=now if status in {"authorized", "issued"} else None,
                authorized_at=now if status == "authorized" else None,
                cancelled_at=now if status == "cancelled" else None,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    return doc_id


def _create_statement_lines_for_backlog(company_id: str) -> tuple[str, str]:
    now = utc_now()
    line_date = today_in_brazil()
    account_id = generate_id("acc")
    pending_id = generate_id("stmtln")
    ignored_id = generate_id("stmtln")

    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta pendencias {uuid4().hex[:8]}",
                account_type="bank",
                institution_name="Banco Teste",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("0.00"),
                is_default_receivable=False,
                is_default_payable=False,
                status="active",
                notes=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        db.flush()

        db.add_all(
            [
                BankStatementLineDB(
                    id=pending_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    statement_import_id=None,
                    external_id=f"pending-{uuid4().hex}",
                    line_date=line_date,
                    posted_at=None,
                    direction="inflow",
                    amount=Decimal("123.45"),
                    description="Regressao: extrato pendente deve entrar no backlog.",
                    document_number=None,
                    counterparty_name="Cliente Teste",
                    counterparty_document=None,
                    bank_reference=None,
                    status="pending",
                    match_confidence=None,
                    matched_amount=Decimal("0.00"),
                    ignored_reason=None,
                    raw_payload_json={},
                    created_at=now,
                    updated_at=now,
                ),
                BankStatementLineDB(
                    id=ignored_id,
                    company_id=company_id,
                    financial_account_id=account_id,
                    statement_import_id=None,
                    external_id=f"ignored-{uuid4().hex}",
                    line_date=line_date,
                    posted_at=None,
                    direction="inflow",
                    amount=Decimal("987.65"),
                    description="Regressao: extrato ignorado nao deve entrar no backlog.",
                    document_number=None,
                    counterparty_name="Cliente Ignorado",
                    counterparty_document=None,
                    bank_reference=None,
                    status="ignored",
                    match_confidence=None,
                    matched_amount=Decimal("0.00"),
                    ignored_reason="Linha ignorada na conciliacao.",
                    raw_payload_json={},
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.commit()

    return pending_id, ignored_id


def _create_accountant_financial_fixture(company_id: str, participant_id: str) -> dict[str, str]:
    now = utc_now()
    reference_date = today_in_brazil()
    account_id = generate_id("acc")
    receivable_id = generate_id("ar")
    payable_id = generate_id("ap")
    settlement_id = generate_id("sett")
    movement_id = generate_id("cash")

    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta contador {uuid4().hex[:8]}",
                account_type="bank",
                institution_name="Banco Teste",
                branch_number=None,
                account_number=None,
                account_digit=None,
                pix_key=None,
                pix_key_type=None,
                currency="BRL",
                opening_balance_amount=Decimal("0.00"),
                is_default_receivable=False,
                is_default_payable=False,
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
            FinancialAccountBalanceDB(
                id=generate_id("cashbal"),
                company_id=company_id,
                financial_account_id=account_id,
                current_balance_amount=Decimal("100.00"),
                last_movement_id=None,
                updated_at=now,
            )
        )
        db.add_all(
            [
                FinancialTitleDB(
                    id=receivable_id,
                    company_id=company_id,
                    direction="receivable",
                    title_type="manual",
                    source_type="accountant_test",
                    source_id=f"receivable-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"ACC-REC-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=reference_date,
                    competency_date=reference_date,
                    due_date=reference_date - timedelta(days=1),
                    expected_payment_date=reference_date,
                    gross_amount=Decimal("100.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("100.00"),
                    paid_amount=Decimal("40.00"),
                    open_amount=Decimal("60.00"),
                    status="partially_received",
                    collection_status="in_collection",
                    fiscal_status="not_required",
                    notes="Regressao: contador deve incluir partially_received.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
                FinancialTitleDB(
                    id=payable_id,
                    company_id=company_id,
                    direction="payable",
                    title_type="manual",
                    source_type="accountant_test",
                    source_id=f"payable-{uuid4().hex}",
                    source_snapshot_json={},
                    sale_id=None,
                    sale_payment_plan_id=None,
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id},
                    payment_method_id=None,
                    payment_method_code=None,
                    payment_method_name="PIX",
                    financial_category_id=None,
                    cost_center_id=None,
                    expected_financial_account_id=account_id,
                    document_reference=f"ACC-PAY-{uuid4().hex[:8]}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=reference_date,
                    competency_date=reference_date,
                    due_date=reference_date - timedelta(days=1),
                    expected_payment_date=reference_date,
                    gross_amount=Decimal("80.00"),
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=Decimal("80.00"),
                    paid_amount=Decimal("30.00"),
                    open_amount=Decimal("50.00"),
                    status="partially_paid",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes="Regressao: contador deve incluir partially_paid.",
                    metadata_json={},
                    created_at=now,
                    updated_at=now,
                    cancelled_at=None,
                    deleted_at=None,
                ),
            ]
        )
        db.flush()
        db.add(
            SettlementDB(
                id=settlement_id,
                company_id=company_id,
                direction="inflow",
                settlement_type="receipt",
                financial_title_id=receivable_id,
                participant_id=participant_id,
                financial_account_id=account_id,
                payment_method_id=None,
                settlement_date=reference_date,
                competency_date=reference_date,
                received_amount=Decimal("40.00"),
                discount_amount=Decimal("0.00"),
                interest_amount=Decimal("0.00"),
                penalty_amount=Decimal("0.00"),
                fee_amount=Decimal("0.00"),
                title_settled_amount=Decimal("40.00"),
                movement_amount=Decimal("40.00"),
                source_type="accountant_test",
                source_id=f"settlement-{uuid4().hex}",
                evidence_reference="REG-ACC-001",
                notes="Regressao: baixa com movimento para contador.",
                status="active",
                reversal_of_settlement_id=None,
                reversed_at=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
            )
        )
        db.flush()
        db.add(
            FinancialMovementDB(
                id=movement_id,
                company_id=company_id,
                financial_account_id=account_id,
                direction="inflow",
                movement_type="receipt",
                movement_date=reference_date,
                amount=Decimal("40.00"),
                currency="BRL",
                source_type="settlement",
                source_id=settlement_id,
                settlement_id=settlement_id,
                financial_title_id=receivable_id,
                participant_id=participant_id,
                description="Regressao: movimento de baixa para contador.",
                status="posted",
                reconciliation_status="pending",
                reversal_of_movement_id=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()

    return {
        "account_id": account_id,
        "receivable_id": receivable_id,
        "payable_id": payable_id,
        "settlement_id": settlement_id,
        "movement_id": movement_id,
    }


def test_management_health_blocks_cross_tenant_company_query() -> None:
    auth = get_auth_context(client)
    other_company_id = _create_other_company()

    response = client.get(
        "/management-reports/mvp-health",
        params={"company_id": other_company_id},
        headers=auth.headers,
    )

    assert response.status_code == 403, response.text
    assert "Acesso bloqueado" in response.json()["detail"]


def test_management_health_indicator_details_blocks_cross_tenant_company_query() -> None:
    auth = get_auth_context(client)
    other_company_id = _create_other_company()

    response = client.get(
        "/management-reports/health-indicator-details",
        params={"company_id": other_company_id, "indicator": "overdue_titles"},
        headers=auth.headers,
    )

    assert response.status_code == 403, response.text
    assert "Acesso bloqueado" in response.json()["detail"]


def test_management_health_counts_partially_received_overdue_titles() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)

    before = client.get(
        "/management-reports/mvp-health",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_data = before.json()["data"]
    before_count = int(before_data["pendencies"].get("overdue_titles") or 0)
    before_amount = Decimal(str(before_data["pendencies"].get("overdue_amount") or "0"))

    _create_partially_received_overdue_title(auth.company_id, fixtures["participant_id"])

    after = client.get(
        "/management-reports/mvp-health",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    after_data = after.json()["data"]
    after_count = int(after_data["pendencies"].get("overdue_titles") or 0)
    after_amount = Decimal(str(after_data["pendencies"].get("overdue_amount") or "0"))

    assert after_count >= before_count + 1
    assert after_amount >= before_amount + Decimal("15.00")
    assert "overdue_titles" in after_data["score_components"]
    assert "calculation_notes" in after_data


def test_management_health_indicator_details_exports_all_overdue_titles() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    title_id = _create_partially_received_overdue_title(auth.company_id, fixtures["participant_id"])

    response = client.get(
        "/management-reports/health-indicator-details",
        params={"company_id": auth.company_id, "indicator": "overdue_titles"},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    rows = data["rows"]

    assert data["indicator"] == "overdue_titles"
    assert data["total"] == len(rows)
    assert title_id in {row["id"] for row in rows}
    assert "open_amount" in data["columns"]


def test_management_health_indicator_details_all_supported_indicators_respond() -> None:
    auth = get_auth_context(client)
    indicators = [
        "participants",
        "titles",
        "movements",
        "sales",
        "purchases",
        "reconciliation_matches",
        "overdue_titles",
        "titles_without_clear_origin",
        "titles_without_participant",
        "unreconciled_movements",
        "unmatched_bank_statement_lines",
    ]

    for indicator in indicators:
        response = client.get(
            "/management-reports/health-indicator-details",
            params={"company_id": auth.company_id, "indicator": indicator},
            headers=auth.headers,
        )

        assert response.status_code == 200, f"{indicator}: {response.text}"
        data = response.json()["data"]
        assert data["indicator"] == indicator
        assert data["total"] == len(data["rows"])
        assert data["columns"]


def test_management_health_indicator_details_rejects_unknown_indicator() -> None:
    auth = get_auth_context(client)

    response = client.get(
        "/management-reports/health-indicator-details",
        params={"company_id": auth.company_id, "indicator": "not-real"},
        headers=auth.headers,
    )

    assert response.status_code == 400, response.text
    assert "Indicador de saúde do Kovir" in response.json()["message"]


def test_management_title_references_filters_and_summarizes_titles() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    title_id = _create_partially_received_overdue_title(auth.company_id, fixtures["participant_id"])
    due_from = (today_in_brazil() - timedelta(days=2)).isoformat()
    due_to = today_in_brazil().isoformat()

    response = client.get(
        "/management-reports/title-references",
        params={
            "company_id": auth.company_id,
            "direction": "receivable",
            "status": "partially_received",
            "due_from": due_from,
            "due_to": due_to,
            "search": title_id,
            "limit": 1,
        },
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    ids = {row["id"] for row in data["items"]}

    assert title_id in ids
    assert data["summary"]["total_count"] >= 1
    assert Decimal(str(data["summary"]["total_open_amount"])) >= Decimal("15.00")
    assert data["summary"]["page_count"] == len(data["items"])
    assert data["items"][0]["collection_status"]
    assert data["items"][0]["fiscal_status"]


def test_management_title_references_export_all_uses_complete_filtered_base() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    marker = f"TITLE-EXPORT-{uuid4().hex[:8]}"
    first_id = _create_manual_receivable_title(auth.company_id, fixtures["participant_id"], document_reference=f"{marker}-1")
    second_id = _create_manual_receivable_title(auth.company_id, fixtures["participant_id"], document_reference=f"{marker}-2")

    limited = client.get(
        "/management-reports/title-references",
        params={"company_id": auth.company_id, "search": marker, "limit": 1},
        headers=auth.headers,
    )
    assert limited.status_code == 200, limited.text
    limited_data = limited.json()["data"]
    assert limited_data["summary"]["total_count"] >= 2
    assert len(limited_data["items"]) == 1

    exported = client.get(
        "/management-reports/title-references",
        params={"company_id": auth.company_id, "search": marker, "export_all": True},
        headers=auth.headers,
    )
    assert exported.status_code == 200, exported.text
    exported_data = exported.json()["data"]
    exported_ids = {row["id"] for row in exported_data["items"]}

    assert exported_data["filters"]["export_all"] is True
    assert {first_id, second_id}.issubset(exported_ids)
    assert len(exported_data["items"]) >= 2


def test_management_backlog_returns_total_pendencies_not_only_limited_rows() -> None:
    auth = get_auth_context(client)

    response = client.get(
        "/management-reports/backlog",
        params={"company_id": auth.company_id, "limit": 1},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    visible_total = (
        len(data["overdue_titles"])
        + len(data["titles_without_clear_origin"])
        + len(data["unreconciled_movements"])
        + len(data["unmatched_bank_statement_lines"])
    )

    assert data["totals"]["total_pendencies"] >= visible_total
    assert isinstance(data["totals"]["is_limited"], bool)
    assert "overdue_titles_amount" in data["totals"]
    assert "unmatched_bank_statement_amount" in data["totals"]


def test_management_backlog_ignores_ignored_statement_lines() -> None:
    auth = get_auth_context(client)

    before = client.get(
        "/management-reports/backlog",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_totals = before.json()["data"]["totals"]
    before_count = int(before_totals["unmatched_bank_statement_lines"])
    before_amount = Decimal(str(before_totals["unmatched_bank_statement_amount"]))

    pending_id, ignored_id = _create_statement_lines_for_backlog(auth.company_id)

    after = client.get(
        "/management-reports/backlog",
        params={"company_id": auth.company_id},
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    after_totals = after.json()["data"]["totals"]

    assert int(after_totals["unmatched_bank_statement_lines"]) == before_count + 1
    assert Decimal(str(after_totals["unmatched_bank_statement_amount"])) == before_amount + Decimal("123.45")

    details = client.get(
        "/management-reports/health-indicator-details",
        params={"company_id": auth.company_id, "indicator": "unmatched_bank_statement_lines"},
        headers=auth.headers,
    )
    assert details.status_code == 200, details.text
    ids = {row["id"] for row in details.json()["data"]["rows"]}
    assert pending_id in ids
    assert ignored_id not in ids


def test_management_fiscal_documents_report_counts_real_totals_and_documents() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    today = today_in_brazil().isoformat()

    before = client.get(
        "/management-reports/preparatory-fiscal-documents",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today, "limit": 1},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_summary = before.json()["data"]["summary"]

    sale_one = _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"])
    sale_two = _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"], fiscal_status="blocked")
    _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"], status="quote")

    purchase_id = _create_purchase_for_fiscal_report(auth.company_id, fixtures["participant_id"], fiscal_status="divergent")
    _create_purchase_for_fiscal_report(auth.company_id, fixtures["participant_id"], deleted=True)
    title_id = _create_fiscal_pending_title(auth.company_id, fixtures["participant_id"])
    authorized_doc = _create_fiscal_document_for_report(auth.company_id, sale_one, status="authorized")
    error_doc = _create_fiscal_document_for_report(auth.company_id, sale_two, status="error")

    after = client.get(
        "/management-reports/preparatory-fiscal-documents",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today, "limit": 1},
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    data = after.json()["data"]
    summary = data["summary"]

    assert summary["pending_sales_documents"] >= before_summary["pending_sales_documents"] + 2
    assert summary["pending_purchase_documents"] >= before_summary["pending_purchase_documents"] + 1
    assert summary["pending_fiscal_titles"] >= before_summary["pending_fiscal_titles"] + 1
    assert summary["fiscal_documents_total"] >= before_summary["fiscal_documents_total"] + 2
    assert summary["fiscal_documents_authorized"] >= before_summary["fiscal_documents_authorized"] + 1
    assert summary["fiscal_documents_error"] >= before_summary["fiscal_documents_error"] + 1
    assert len(data["sales_documents"]) == 1
    assert data["returned_rows"]["sales_documents"] == 1
    assert data["summary"]["status"] == "BLOCKED"

    exported = client.get(
        "/management-reports/preparatory-fiscal-documents",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "limit": 1,
            "export_all": True,
        },
        headers=auth.headers,
    )
    assert exported.status_code == 200, exported.text
    exported_data = exported.json()["data"]

    assert exported_data["export_all"] is True
    assert {sale_one, sale_two}.issubset({row["sale_id"] for row in exported_data["sales_documents"]})
    assert purchase_id in {row["purchase_id"] for row in exported_data["purchase_documents"]}
    assert title_id in {row["id"] for row in exported_data["title_documents"]}
    assert {authorized_doc, error_doc}.issubset({row["id"] for row in exported_data["fiscal_documents"]})


def test_management_financial_close_counts_partially_received_titles() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    start = (today_in_brazil() - timedelta(days=2)).isoformat()
    end = today_in_brazil().isoformat()

    before = client.get(
        "/management-reports/financial-close-mvp",
        params={"company_id": auth.company_id, "start_date": start, "end_date": end},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_snapshot = before.json()["data"]["snapshot"]

    _create_partially_received_overdue_title(auth.company_id, fixtures["participant_id"])

    after = client.get(
        "/management-reports/financial-close-mvp",
        params={"company_id": auth.company_id, "start_date": start, "end_date": end},
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    data = after.json()["data"]
    snapshot = data["snapshot"]

    assert snapshot["open_receivable_count"] >= before_snapshot["open_receivable_count"] + 1
    assert Decimal(str(snapshot["open_receivable_amount"])) >= Decimal(str(before_snapshot["open_receivable_amount"])) + Decimal("15.00")
    assert snapshot["overdue_count"] >= before_snapshot["overdue_count"] + 1
    assert "generated_at" in data
    assert "reference_date" in data
    assert "can_close_with_warnings" in data


def test_management_financial_close_blocks_fiscal_document_errors() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    today = today_in_brazil().isoformat()
    sale_id = _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"])
    _create_fiscal_document_for_report(auth.company_id, sale_id, status="error")

    response = client.get(
        "/management-reports/financial-close-mvp",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    checklist = {item["code"]: item for item in data["checklist"]}

    assert data["close_status"] == "BLOCKED"
    assert data["can_close_with_warnings"] is False
    assert checklist["fiscal_errors"]["status"] == "FAIL"
    assert checklist["fiscal_errors"]["blocking"] is True
    assert checklist["fiscal_errors"]["evidence"]["fiscal_documents_error"] >= 1
    assert data["snapshot"]["fiscal_documents_error"] >= 1


def test_management_accountant_pack_uses_reliable_scopes_and_details() -> None:
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    today = today_in_brazil().isoformat()

    before = client.get(
        "/management-reports/accountant-pack",
        params={"company_id": auth.company_id, "start_date": today, "end_date": today},
        headers=auth.headers,
    )
    assert before.status_code == 200, before.text
    before_data = before.json()["data"]

    created = _create_accountant_financial_fixture(auth.company_id, fixtures["participant_id"])
    closed_sale = _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"], status="closed", amount="42.00")
    quote_sale = _create_sale_for_fiscal_report(auth.company_id, fixtures["participant_id"], status="quote", amount="99.00")
    confirmed_purchase = _create_purchase_for_fiscal_report(auth.company_id, fixtures["participant_id"], status="confirmed", amount="55.00")
    draft_purchase = _create_purchase_for_fiscal_report(auth.company_id, fixtures["participant_id"], status="draft", amount="88.00")
    pending_statement_id, ignored_statement_id = _create_statement_lines_for_backlog(auth.company_id)

    after = client.get(
        "/management-reports/accountant-pack",
        params={
            "company_id": auth.company_id,
            "start_date": today,
            "end_date": today,
            "include_details": True,
            "export_all": True,
        },
        headers=auth.headers,
    )
    assert after.status_code == 200, after.text
    data = after.json()["data"]
    indicators = data["indicators"]

    assert data["filters_used"]["reference_date"] == today
    assert data["detail_limits"]["include_details"] is True
    assert data["detail_limits"]["export_all"] is True
    assert indicators["accounts_receivable_open"]["scope"] == "current_position"
    assert indicators["accounts_receivable_open"]["count"] >= before_data["indicators"]["accounts_receivable_open"]["count"] + 1
    assert Decimal(str(indicators["accounts_receivable_open"]["amount"])) >= Decimal(str(before_data["indicators"]["accounts_receivable_open"]["amount"])) + Decimal("60.00")
    assert indicators["accounts_receivable_overdue"]["count"] >= before_data["indicators"]["accounts_receivable_overdue"]["count"] + 1
    assert indicators["accounts_payable_open"]["count"] >= before_data["indicators"]["accounts_payable_open"]["count"] + 1
    assert indicators["accounts_payable_overdue"]["count"] >= before_data["indicators"]["accounts_payable_overdue"]["count"] + 1
    assert Decimal(str(indicators["cash_flow_realized"]["inflow_amount"])) >= Decimal(str(before_data["indicators"]["cash_flow_realized"]["inflow_amount"])) + Decimal("40.00")

    assert data["operational_ignored"]["sale_quotes_ignored_count"] >= before_data["operational_ignored"]["sale_quotes_ignored_count"] + 1
    assert data["operational_ignored"]["purchase_drafts_ignored_count"] >= before_data["operational_ignored"]["purchase_drafts_ignored_count"] + 1
    assert data["consistency_checks"]["settlements_without_movement_count"] == before_data["consistency_checks"]["settlements_without_movement_count"]
    assert Decimal(str(data["consistency_checks"]["difference_amount"])) == Decimal(str(before_data["consistency_checks"]["difference_amount"]))
    assert created["receivable_id"] in {row["id"] for row in data["open_title_details"]}
    assert created["payable_id"] in {row["id"] for row in data["open_title_details"]}
    assert created["settlement_id"] in {row["id"] for row in data["settlement_details"]}
    assert created["movement_id"] in {row["id"] for row in data["movement_details"]}
    assert pending_statement_id in {row["id"] for row in data["statement_line_details"]}
    assert ignored_statement_id not in {row["id"] for row in data["statement_line_details"]}
    assert closed_sale in {row["id"] for row in data["sales_details"]}
    assert quote_sale not in {row["id"] for row in data["sales_details"]}
    assert quote_sale in {row["id"] for row in data["ignored_sale_details"]}
    assert confirmed_purchase in {row["id"] for row in data["purchase_details"]}
    assert draft_purchase not in {row["id"] for row in data["purchase_details"]}
    assert draft_purchase in {row["id"] for row in data["ignored_purchase_details"]}
    assert "partially_received" in data["indicator_formulas"]["accounts_receivable_open"]
