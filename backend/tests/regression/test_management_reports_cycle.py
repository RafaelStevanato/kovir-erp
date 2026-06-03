from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.modules.cash.db_models import FinancialMovementDB
from app.modules.financial.db_models import FinancialAccountDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context


client = TestClient(app)


def _direction_row(data: dict, direction: str) -> dict:
    for row in data["movements_by_direction"]:
        if row["direction"] == direction:
            return row
    return {
        "direction": direction,
        "total_movements": 0,
        "amount": "0.00",
        "reconciled_amount": "0.00",
        "unreconciled_amount": "0.00",
        "reconciled_movements": 0,
        "unreconciled_movements": 0,
    }


def _fetch_cycle(company_id: str, headers: dict) -> dict:
    response = client.get(
        "/management-reports/financial-cycle",
        params={"company_id": company_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _create_cycle_movements(company_id: str) -> None:
    now = utc_now()
    movement_date = today_in_brazil()
    account_id = generate_id("acc")

    with SessionLocal() as db:
        db.add(
            FinancialAccountDB(
                id=account_id,
                company_id=company_id,
                name=f"Conta ciclo financeiro {uuid4().hex[:8]}",
                account_type="cash",
                institution_name=None,
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
            FinancialMovementDB(
                id=generate_id("cash"),
                company_id=company_id,
                financial_account_id=account_id,
                direction="inflow",
                movement_type="manual",
                movement_date=movement_date,
                amount=Decimal("11.00"),
                currency="BRL",
                source_type="regression-cycle",
                source_id=f"matched-{uuid4().hex}",
                settlement_id=None,
                financial_title_id=None,
                participant_id=None,
                description="Regressao: movimento conciliado deve usar status matched.",
                status="posted",
                reconciliation_status="matched",
                reversal_of_movement_id=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            FinancialMovementDB(
                id=generate_id("cash"),
                company_id=company_id,
                financial_account_id=account_id,
                direction="inflow",
                movement_type="manual",
                movement_date=movement_date,
                amount=Decimal("7.00"),
                currency="BRL",
                source_type="regression-cycle",
                source_id=f"pending-{uuid4().hex}",
                settlement_id=None,
                financial_title_id=None,
                participant_id=None,
                description="Regressao: movimento pendente deve seguir como pendencia.",
                status="posted",
                reconciliation_status="pending",
                reversal_of_movement_id=None,
                metadata_json={},
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()


def test_financial_cycle_treats_matched_movement_as_reconciled() -> None:
    auth = get_auth_context(client)
    before = _direction_row(_fetch_cycle(auth.company_id, auth.headers), "inflow")

    _create_cycle_movements(auth.company_id)

    after = _direction_row(_fetch_cycle(auth.company_id, auth.headers), "inflow")

    assert Decimal(after["reconciled_amount"]) - Decimal(before["reconciled_amount"]) == Decimal("11.00")
    assert Decimal(after["unreconciled_amount"]) - Decimal(before["unreconciled_amount"]) == Decimal("7.00")
    assert int(after["reconciled_movements"]) - int(before["reconciled_movements"]) == 1
    assert int(after["unreconciled_movements"]) - int(before["unreconciled_movements"]) == 1
