from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.financial.db_models import (
    ChartAccountDB,
    CostCenterDB,
    FinancialAccountDB,
    FinancialCategoryDB,
    PaymentTermDB,
)
from app.shared.datetime import utc_now
from app.shared.ids import generate_id
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


def _seed_financial_master_rows(company_id: str, suffix: str, total: int = 25) -> None:
    now = utc_now()
    with SessionLocal() as db:
        for index in range(total):
            db.add(
                ChartAccountDB(
                    id=generate_id("acc"),
                    company_id=company_id,
                    code=f"PERF-ACC-{suffix}-{index:03d}",
                    name=f"Perf {suffix} plano {index:03d}",
                    account_type="expense",
                    is_analytical=True,
                    accepts_entries=True,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.add(
                FinancialCategoryDB(
                    id=generate_id("cat"),
                    company_id=company_id,
                    code=f"PERF-CAT-{suffix}-{index:03d}",
                    name=f"Perf {suffix} categoria {index:03d}",
                    category_type="expense",
                    cash_flow_group="operating_outflows",
                    affects_cash_flow=True,
                    requires_cost_center=False,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.add(
                CostCenterDB(
                    id=generate_id("cc"),
                    company_id=company_id,
                    code=f"PERF-CC-{suffix}-{index:03d}",
                    name=f"Perf {suffix} centro {index:03d}",
                    center_type="administrative",
                    is_analytical=True,
                    monthly_budget_amount=Decimal("0.00"),
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.add(
                FinancialAccountDB(
                    id=generate_id("bankacc"),
                    company_id=company_id,
                    name=f"Perf {suffix} conta {index:03d}",
                    account_type="cash",
                    opening_balance_amount=Decimal("0.00"),
                    currency="BRL",
                    is_default_receivable=False,
                    is_default_payable=False,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.add(
                PaymentTermDB(
                    id=generate_id("term"),
                    company_id=company_id,
                    name=f"Perf {suffix} condicao {index:03d}",
                    term_type="cash",
                    installments=1,
                    first_due_days=0,
                    interval_days=0,
                    generate_on_sale=True,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()


def test_financial_master_list_endpoints_keep_constant_query_budget():
    auth = get_auth_context(client)
    suffix = uuid4().hex[:8]
    _seed_financial_master_rows(auth.company_id, suffix)

    endpoints = [
        "/financial/chart-accounts",
        "/financial/categories",
        "/financial/cost-centers",
        "/financial/accounts",
        "/financial/payment-terms",
    ]

    for path in endpoints:
        with QueryCounter() as counter:
            response = client.get(
                path,
                params={
                    "company_id": auth.company_id,
                    "search": f"Perf {suffix}",
                    "limit": 51,
                    "offset": 0,
                },
                headers=auth.headers,
            )

        assert response.status_code == 200, response.text
        assert len(response.json()["data"]) == 25
        assert counter.count <= 8, f"{path} executou {counter.count} queries"
