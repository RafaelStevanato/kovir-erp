r"""
Kovir ERP — Bloco 7 — Stress/Regressão Cadastros Financeiros Base
===================================================================

Valida a fundação de cadastros financeiros antes de avançar para Contas a Receber:
- empresa persistente;
- plano de contas;
- categorias financeiras;
- centros de custo;
- contas financeiras;
- condições de pagamento;
- criação idempotente de padrões;
- auditoria básica;
- bloqueio de duplicidade por código/nome.

Uso PostgreSQL local migrado:
    cd backend
    python .\tools\stress_bloco_7_financial_masters.py --output bloco_7_financial_stress_report.json

Uso smoke isolado SQLite:
    python .\tools\stress_bloco_7_financial_masters.py --sqlite-smoke-db ..\bloco_7_financial_smoke.db
"""

from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class CaseResult:
    name: str
    expected: str
    status: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def _case(results: list[CaseResult], name: str, expected: str, func):
    try:
        evidence = func() or {}
        results.append(CaseResult(name=name, expected=expected, status="PASS", evidence=evidence))
        return evidence
    except Exception as exc:
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=f"{type(exc).__name__}: {exc}"))
        raise


def _safe_case(results: list[CaseResult], name: str, expected: str, func):
    try:
        evidence = func() or {}
        results.append(CaseResult(name=name, expected=expected, status="PASS", evidence=evidence))
        return evidence
    except Exception as exc:
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=f"{type(exc).__name__}: {exc}"))
        return None


def _configure_sqlite_if_requested(sqlite_path: str | None):
    if not sqlite_path:
        return False
    db_path = Path(sqlite_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_path.as_posix()}"

    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001, ARG001
        return "JSON"

    return True


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import (
        ChartAccountCreate,
        CostCenterCreate,
        FinancialAccountCreate,
        FinancialCategoryCreate,
        PaymentTermCreate,
    )
    from app.modules.financial.service import (
        create_chart_account,
        create_cost_center,
        create_default_financial_masters,
        create_financial_account,
        create_financial_category,
        create_payment_term,
        get_financial_audit_events,
        get_financial_diagnostics,
        list_chart_accounts,
        list_cost_centers,
        list_financial_accounts,
        list_financial_categories,
        list_payment_terms,
    )

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]
    ids: dict[str, str] = {}

    try:
        def create_company_case():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Finance Stress {suffix} LTDA",
                "trade_name": f"Kovir Finance {suffix}",
                "cnpj": f"221111{suffix[-8:]}",
                "email": f"finance.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Financeiro",
                "status": "active",
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            ids["company_id"] = company["id"]
            return {"company_id": company["id"]}

        _case(results, "create_company", "Empresa base deve existir para cadastros financeiros.", create_company_case)

        def create_masters_case():
            chart = create_chart_account(db, ChartAccountCreate(company_id=ids["company_id"], code="3.90", name="Receita teste", account_type="revenue"))
            category = create_financial_category(db, FinancialCategoryCreate(company_id=ids["company_id"], code="REC-TESTE", name="Receita teste", category_type="income", chart_account_id=chart["id"], cash_flow_group="operating_inflows"))
            center = create_cost_center(db, CostCenterCreate(company_id=ids["company_id"], code="TESTE", name="Centro teste", center_type="project"))
            account = create_financial_account(db, FinancialAccountCreate(company_id=ids["company_id"], name="Banco teste", account_type="bank_account", institution_name="Banco de Teste", opening_balance_amount="0"))
            term = create_payment_term(db, PaymentTermCreate(company_id=ids["company_id"], name="15 dias", term_type="installments", installments=1, first_due_days=15, interval_days=30))
            ids.update({"chart_id": chart["id"], "category_id": category["id"], "center_id": center["id"], "account_id": account["id"], "term_id": term["id"]})
            return ids.copy()

        _case(results, "create_financial_masters", "Todos os cadastros financeiros base devem ser criados com ID próprio.", create_masters_case)

        def list_masters_case():
            return {
                "chart_accounts": len(list_chart_accounts(db, company_id=ids["company_id"])),
                "financial_categories": len(list_financial_categories(db, company_id=ids["company_id"])),
                "cost_centers": len(list_cost_centers(db, company_id=ids["company_id"])),
                "financial_accounts": len(list_financial_accounts(db, company_id=ids["company_id"])),
                "payment_terms": len(list_payment_terms(db, company_id=ids["company_id"])),
            }

        _case(results, "list_financial_masters", "Listagens devem retornar dados por empresa.", list_masters_case)

        def defaults_case():
            output = create_default_financial_masters(db, ids["company_id"])
            diagnostics = get_financial_diagnostics(db, company_id=ids["company_id"])
            return {"created_keys": list(output["created"].keys()), "records_count": diagnostics.get("records_count")}

        _case(results, "create_defaults", "Padrões devem ser criados sem quebrar dados existentes.", defaults_case)

        def duplicate_block_case():
            try:
                create_chart_account(db, ChartAccountCreate(company_id=ids["company_id"], code="3.90", name="Duplicado", account_type="revenue"))
            except ValueError as error:
                return {"blocked": True, "message": str(error)}
            raise AssertionError("Duplicidade de código no plano de contas não foi bloqueada.")

        _case(results, "block_duplicate_chart_account_code", "Duplicidade por empresa deve ser bloqueada.", duplicate_block_case)

        def audit_case():
            events = get_financial_audit_events(db, "chart_account", ids["chart_id"])
            if not events:
                raise AssertionError("Auditoria de conta do plano de contas não encontrada.")
            return {"audit_events": len(events)}

        _case(results, "audit_financial_master", "Criação deve gerar audit_event persistente.", audit_case)

        failed = [result for result in results if result.status != "PASS"]
        return {
            "status": "PASS" if not failed else "FAIL",
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "sqlite_smoke_mode": sqlite_mode,
            "cases": [result.__dict__ for result in results],
        }
    except Exception:
        failed = [result for result in results if result.status != "PASS"]
        return {
            "status": "FAIL",
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "sqlite_smoke_mode": sqlite_mode,
            "cases": [result.__dict__ for result in results],
            "traceback": traceback.format_exc(),
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="bloco_7_financial_stress_report.json")
    args = parser.parse_args()
    report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
