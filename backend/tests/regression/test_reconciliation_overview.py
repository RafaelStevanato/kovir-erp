from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.cash.db_models import FinancialMovementDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.reconciliation.db_models import BankStatementLineDB, ReconciliationMatchDB
from app.shared.datetime import utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


class _QueryCounter:
    def __init__(self) -> None:
        self.count = 0

    def before_cursor_execute(self, *args, **kwargs) -> None:
        self.count += 1


def _money(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _create_account(company_id: str, *, name: str) -> str:
    account_id = generate_id("bankacc")
    now = utc_now()
    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=name,
                account_type="bank",
                institution_name="Banco Regressão",
                currency="BRL",
                opening_balance_amount=_money("0.00"),
                is_default_receivable=False,
                is_default_payable=False,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    return account_id


def _statement_line(
    *,
    company_id: str,
    account_id: str,
    status: str,
    amount: str,
    description: str,
    matched_amount: str = "0.00",
) -> BankStatementLineDB:
    now = utc_now()
    return BankStatementLineDB(
        id=generate_id("stmtln"),
        company_id=company_id,
        financial_account_id=account_id,
        statement_import_id=None,
        external_id=generate_id("stmtln"),
        line_date=date(2026, 5, 8),
        posted_at=None,
        direction="inflow",
        amount=_money(amount),
        description=description,
        document_number=None,
        counterparty_name="Cliente Regressão",
        counterparty_document=None,
        bank_reference=generate_id("stmtln"),
        status=status,
        match_confidence="forced_difference" if status == "divergent" else None,
        matched_amount=_money(matched_amount),
        ignored_reason="Duplicidade operacional" if status == "ignored" else None,
        raw_payload_json={},
        created_at=now,
        updated_at=now,
    )


def _movement(
    *,
    company_id: str,
    account_id: str,
    reconciliation_status: str,
    amount: str,
    description: str,
) -> FinancialMovementDB:
    now = utc_now()
    movement_id = generate_id("cash")
    return FinancialMovementDB(
        id=movement_id,
        company_id=company_id,
        financial_account_id=account_id,
        direction="inflow",
        movement_type="receipt",
        movement_date=date(2026, 5, 8),
        amount=_money(amount),
        currency="BRL",
        source_type="regression",
        source_id=movement_id,
        settlement_id=None,
        financial_title_id=None,
        participant_id=None,
        description=description,
        status="posted",
        reconciliation_status=reconciliation_status,
        reversal_of_movement_id=None,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )


def _create_fixture(company_id: str, account_id: str, other_account_id: str) -> dict[str, str]:
    pending_line = _statement_line(
        company_id=company_id,
        account_id=account_id,
        status="pending",
        amount="100.00",
        description="Extrato pendente conta filtrada",
    )
    ignored_line = _statement_line(
        company_id=company_id,
        account_id=account_id,
        status="ignored",
        amount="10.00",
        description="Extrato ignorado conta filtrada",
    )
    divergent_line = _statement_line(
        company_id=company_id,
        account_id=account_id,
        status="divergent",
        amount="70.00",
        matched_amount="65.00",
        description="Extrato divergente conta filtrada",
    )
    other_line = _statement_line(
        company_id=company_id,
        account_id=other_account_id,
        status="pending",
        amount="999.00",
        description="Extrato de outra conta",
    )
    pending_movement = _movement(
        company_id=company_id,
        account_id=account_id,
        reconciliation_status="pending",
        amount="80.00",
        description="Movimento pendente conta filtrada",
    )
    divergent_movement = _movement(
        company_id=company_id,
        account_id=account_id,
        reconciliation_status="divergent",
        amount="65.00",
        description="Movimento divergente conta filtrada",
    )
    other_movement = _movement(
        company_id=company_id,
        account_id=other_account_id,
        reconciliation_status="pending",
        amount="999.00",
        description="Movimento de outra conta",
    )
    now = utc_now()
    match = ReconciliationMatchDB(
        id=generate_id("recmatch"),
        company_id=company_id,
        financial_account_id=account_id,
        statement_line_id=divergent_line.id,
        financial_movement_id=divergent_movement.id,
        match_type="manual",
        matched_amount=_money("65.00"),
        line_amount=_money("70.00"),
        movement_amount=_money("65.00"),
        difference_amount=_money("5.00"),
        tolerance_amount=_money("0.00"),
        status="confirmed_with_difference",
        confirmation_reason="Diferença operacional identificada",
        reversed_reason=None,
        confirmed_at=now,
        reversed_at=None,
        metadata_json={},
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add_all(
            [
                pending_line,
                ignored_line,
                divergent_line,
                other_line,
                pending_movement,
                divergent_movement,
                other_movement,
                match,
            ]
        )
        db.commit()
    return {
        "pending_line_id": pending_line.id,
        "ignored_line_id": ignored_line.id,
        "divergent_line_id": divergent_line.id,
        "pending_movement_id": pending_movement.id,
        "divergent_movement_id": divergent_movement.id,
        "match_id": match.id,
        "other_line_id": other_line.id,
        "other_movement_id": other_movement.id,
    }


def test_reconciliation_overview_is_account_scoped_and_exportable() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta Conciliação Regressão")
    other_account_id = _create_account(auth.company_id, name="Outra Conta Conciliação Regressão")
    created = _create_fixture(auth.company_id, account_id, other_account_id)

    summary_response = client.get(
        "/reconciliation/summary",
        params={"company_id": auth.company_id, "financial_account_id": account_id},
        headers=auth.headers,
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()["data"]
    assert summary["financial_account_id"] == account_id
    assert summary["pending_statement_lines"] == 1
    assert _money(summary["pending_statement_lines_amount"]) == _money("100.00")
    assert summary["ignored_statement_lines"] == 1
    assert _money(summary["ignored_statement_lines_amount"]) == _money("10.00")
    assert summary["divergent_statement_lines"] == 1
    assert _money(summary["divergent_statement_lines_amount"]) == _money("70.00")
    assert summary["pending_financial_movements"] == 1
    assert _money(summary["pending_financial_movements_amount"]) == _money("80.00")
    assert summary["divergent_financial_movements"] == 1
    assert _money(summary["divergent_financial_movements_amount"]) == _money("65.00")
    assert summary["confirmed_matches"] == 1
    assert _money(summary["confirmed_matches_amount"]) == _money("65.00")
    assert _money(summary["confirmed_matches_difference_amount"]) == _money("5.00")

    evidence_response = client.get(
        "/reconciliation/overview-evidence",
        params={"company_id": auth.company_id, "financial_account_id": account_id, "limit": 5000},
        headers=auth.headers,
    )
    assert evidence_response.status_code == 200, evidence_response.text
    evidence = evidence_response.json()["data"]
    assert {row["id"] for row in evidence["pending_statement_lines"]} == {created["pending_line_id"]}
    assert {row["id"] for row in evidence["ignored_statement_lines"]} == {created["ignored_line_id"]}
    assert {row["id"] for row in evidence["divergent_statement_lines"]} == {created["divergent_line_id"]}
    assert {row["id"] for row in evidence["pending_financial_movements"]} == {created["pending_movement_id"]}
    assert {row["id"] for row in evidence["divergent_financial_movements"]} == {created["divergent_movement_id"]}
    assert {row["id"] for row in evidence["confirmed_matches"]} == {created["match_id"]}
    assert created["other_line_id"] not in {row["id"] for row in evidence["pending_statement_lines"]}
    assert created["other_movement_id"] not in {row["id"] for row in evidence["pending_financial_movements"]}

    block_response = client.get(
        "/reconciliation/overview-evidence",
        params={"company_id": auth.company_id, "financial_account_id": account_id, "block": "pending_statement_lines"},
        headers=auth.headers,
    )
    assert block_response.status_code == 200, block_response.text
    block_evidence = block_response.json()["data"]
    assert {row["id"] for row in block_evidence["pending_statement_lines"]} == {created["pending_line_id"]}
    assert block_evidence["divergent_statement_lines"] == []
    assert block_evidence["pending_financial_movements"] == []
    assert block_evidence["confirmed_matches"] == []


def test_reconciliation_summary_uses_constant_query_budget() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta Budget Conciliação Regressão")
    other_account_id = _create_account(auth.company_id, name="Outra Conta Budget Conciliação Regressão")
    _create_fixture(auth.company_id, account_id, other_account_id)

    counter = _QueryCounter()
    event.listen(engine, "before_cursor_execute", counter.before_cursor_execute)
    try:
        response = client.get(
            "/reconciliation/summary",
            params={"company_id": auth.company_id, "financial_account_id": account_id},
            headers=auth.headers,
        )
    finally:
        event.remove(engine, "before_cursor_execute", counter.before_cursor_execute)

    assert response.status_code == 200, response.text
    assert counter.count <= 12


def test_reconciliation_overview_rejects_cross_company_context() -> None:
    auth = get_auth_context(client)
    response = client.get(
        "/reconciliation/summary",
        params={"company_id": generate_id("emp")},
        headers=auth.headers,
    )
    assert response.status_code == 403, response.text


def test_reconciliation_statement_lines_filters_are_explicit_and_exportable() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta Linhas Regressão")
    other_account_id = _create_account(auth.company_id, name="Outra Conta Linhas Regressão")
    created = _create_fixture(auth.company_id, account_id, other_account_id)

    response = client.get(
        "/reconciliation/statement-lines",
        params={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "status": "pending",
            "line_from": "2026-05-08",
            "line_to": "2026-05-08",
            "q": "pendente conta filtrada",
            "limit": 5000,
        },
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert [row["id"] for row in data] == [created["pending_line_id"]]
    assert created["other_line_id"] not in {row["id"] for row in data}

    multi_status = client.get(
        "/reconciliation/statement-lines",
        params={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "statuses": "pending,divergent",
            "limit": 5000,
        },
        headers=auth.headers,
    )
    assert multi_status.status_code == 200, multi_status.text
    assert {row["id"] for row in multi_status.json()["data"]} == {
        created["pending_line_id"],
        created["divergent_line_id"],
    }

    invalid_period = client.get(
        "/reconciliation/statement-lines",
        params={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "line_from": "2026-05-09",
            "line_to": "2026-05-08",
        },
        headers=auth.headers,
    )
    assert invalid_period.status_code == 400, invalid_period.text


def test_reconciliation_matches_history_is_account_scoped_and_exportable() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta Histórico Regressão")
    other_account_id = _create_account(auth.company_id, name="Outra Conta Histórico Regressão")
    created = _create_fixture(auth.company_id, account_id, other_account_id)

    response = client.get(
        "/reconciliation/matches",
        params={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "status": "confirmed_with_difference",
            "limit": 5000,
        },
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert [row["id"] for row in data] == [created["match_id"]]
    assert data[0]["statement_line_id"] == created["divergent_line_id"]
    assert data[0]["financial_movement_id"] == created["divergent_movement_id"]
    assert data[0]["status"] == "confirmed_with_difference"
    assert data[0]["confirmation_reason"] == "Diferença operacional identificada"


def test_reconciliation_import_accepts_sgml_ofx_without_creating_financial_fact() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta OFX SGML Regressão")
    ofx_content = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>001
<BRANCHID>0001
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260501000000[-3:BRT]
<DTEND>20260508000000[-3:BRT]
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260508000000[-3:BRT]
<TRNAMT>123.45
<FITID>FITID-REGRESSION-001
<NAME>Cliente OFX
<MEMO>Pix recebido
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>123.45
<DTASOF>20260508000000[-3:BRT]
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    response = client.post(
        "/reconciliation/statement-imports/ofx-text",
        json={
            "company_id": auth.company_id,
            "financial_account_id": account_id,
            "file_name": "regressao-sgml.ofx",
            "ofx_content": ofx_content,
        },
        headers=auth.headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["statement_import"]["line_count"] == 1
    assert data["statement_import"]["total_inflow_amount"] == "123.45"
    assert data["statement_import"]["closing_balance_amount"] == "123.45"
    assert data["lines"][0]["direction"] == "inflow"
    assert data["lines"][0]["amount"] == "123.45"
    assert data["lines"][0]["status"] == "pending"

    summary_response = client.get(
        "/reconciliation/summary",
        params={"company_id": auth.company_id, "financial_account_id": account_id},
        headers=auth.headers,
    )
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()["data"]
    assert summary["pending_statement_lines"] == 1
    assert summary["pending_financial_movements"] == 0


def test_reconciliation_manual_import_duplicate_returns_400_not_500() -> None:
    auth = get_auth_context(client)
    account_id = _create_account(auth.company_id, name="Conta Duplicidade Manual Regressão")
    payload = {
        "company_id": auth.company_id,
        "financial_account_id": account_id,
        "source_type": "manual",
        "source_id": generate_id("stmtimp"),
        "file_name": "extrato-manual-regressao.csv",
        "statement_start_date": "2026-05-08",
        "statement_end_date": "2026-05-08",
        "closing_balance_amount": "25.00",
        "lines": [
            {
                "external_id": generate_id("stmtln"),
                "line_date": "2026-05-08",
                "direction": "inflow",
                "amount": "25.00",
                "description": "Linha manual regressão",
                "bank_reference": "MANUAL-REGRESSION",
            }
        ],
    }
    first = client.post("/reconciliation/statement-imports", json=payload, headers=auth.headers)
    assert first.status_code == 200, first.text

    duplicate = client.post("/reconciliation/statement-imports", json=payload, headers=auth.headers)
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["success"] is False
