from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.main import app
from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import generate_id
from tests.regression.auth_helpers import get_auth_context
from tests.regression.sale_test_helpers import ensure_service_fixtures

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


def _seed_receivable_titles(company_id: str, participant_id: str, suffix: str, total: int = 25) -> None:
    now = utc_now()
    today = today_in_brazil()
    with SessionLocal() as db:
        for index in range(total):
            due_date = today if index % 2 == 0 else today.replace(year=today.year + 1)
            amount = Decimal("100.00") + Decimal(index)
            db.add(
                FinancialTitleDB(
                    id=generate_id("ar"),
                    company_id=company_id,
                    direction="receivable",
                    title_type="manual",
                    source_type="manual",
                    source_id=f"perf-ar-{suffix}-{index:03d}",
                    source_snapshot_json={"origin": "performance_test"},
                    participant_id=participant_id,
                    participant_snapshot_json={"id": participant_id, "name": f"Cliente Perf {suffix}"},
                    document_reference=f"PERF-AR-{suffix}-{index:03d}",
                    installment_number=1,
                    installment_total=1,
                    issue_date=today,
                    competency_date=today,
                    due_date=due_date,
                    expected_payment_date=due_date,
                    gross_amount=amount,
                    discount_amount=Decimal("0.00"),
                    interest_amount=Decimal("0.00"),
                    penalty_amount=Decimal("0.00"),
                    fee_amount=Decimal("0.00"),
                    net_amount=amount,
                    paid_amount=Decimal("0.00"),
                    open_amount=amount,
                    status="open",
                    collection_status="not_started",
                    fiscal_status="not_required",
                    notes=f"Perf {suffix} titulo {index:03d}",
                    metadata_json={"test": "accounts_receivable_performance"},
                    created_at=now,
                    updated_at=now,
                )
            )
        db.commit()


def test_accounts_receivable_list_and_summary_keep_constant_query_budget():
    auth = get_auth_context(client)
    fixtures = ensure_service_fixtures(client, auth.company_id, auth.headers)
    suffix = uuid4().hex[:8]
    _seed_receivable_titles(auth.company_id, fixtures["participant_id"], suffix)

    with QueryCounter() as list_counter:
        list_response = client.get(
            "/accounts-receivable/titles",
            params={
                "company_id": auth.company_id,
                "q": f"PERF-AR-{suffix}",
                "limit": 21,
                "offset": 0,
            },
            headers=auth.headers,
        )

    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()["data"]) == 21
    assert list_counter.count <= 8, f"listagem executou {list_counter.count} queries"

    with QueryCounter() as summary_counter:
        summary_response = client.get(
            "/accounts-receivable/summary",
            params={"company_id": auth.company_id},
            headers=auth.headers,
        )

    assert summary_response.status_code == 200, summary_response.text
    assert summary_response.json()["data"]["total_count"] >= 25
    assert summary_counter.count <= 10, f"resumo executou {summary_counter.count} queries"
