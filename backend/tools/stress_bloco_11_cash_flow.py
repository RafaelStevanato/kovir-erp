r"""
Kovir ERP — Bloco 11 — Stress Fluxo de Caixa / Dashboard Financeiro Integrado
================================================================================

Valida que o dashboard de fluxo de caixa lê fatos reais sem gravar ou corrigir origem:
- título a receber previsto;
- baixa/recebimento;
- movimento financeiro interno;
- saldo interno por conta;
- extrato importado;
- match de conciliação;
- pendências e indicadores diários.

Uso PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_bloco_11_cash_flow.py --output bloco_11_cash_flow_stress_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_bloco_11_cash_flow.py --sqlite-smoke-db ..\bloco_11_cash_flow_smoke.db --output bloco_11_cash_flow_stress_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


@dataclass
class CaseResult:
    name: str
    expected: str
    status: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def _configure_sqlite_if_requested(sqlite_path: str | None) -> bool:
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


def _case(results: list[CaseResult], name: str, expected: str, func: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
    try:
        evidence = func() or {}
        results.append(CaseResult(name=name, expected=expected, status="PASS", evidence=evidence))
        return evidence
    except Exception as exc:  # noqa: BLE001
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=f"{type(exc).__name__}: {exc}"))
        raise


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate
    from app.modules.accounts_receivable.service import create_manual_receivable
    from app.modules.cash.schemas import ManualFinancialMovementCreate, SettlementCreate
    from app.modules.cash.service import create_manual_movement, receive_title
    from app.modules.cash_flow.service import get_cash_flow_accounts, get_cash_flow_daily, get_cash_flow_pending, get_cash_flow_reconciliation_status, get_cash_flow_summary
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import FinancialAccountCreate
    from app.modules.financial.service import create_financial_account
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.reconciliation.schemas import BankStatementImportCreate, ReconciliationMatchCreate
    from app.modules.reconciliation.service import confirm_match, import_statement

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, str] = {}
    today = date.today()
    suffix = str(abs(hash((today.isoformat(), os.getpid()))))[-8:]

    try:
        def setup_base():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Cash Flow Stress {suffix} LTDA",
                "trade_name": f"Kovir CF {suffix}",
                "cnpj": f"55{suffix[-8:]}0001",
                "email": f"cashflow.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Fluxo",
                "status": "active",
                "address": {"street": "Rua Fluxo", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            ids["company_id"] = company["id"]
            participant = create_participant(db, ParticipantCreate(**{
                "company_id": company["id"],
                "participant_type": "customer",
                "person_type": "company",
                "name": f"Cliente Fluxo {suffix}",
                "trade_name": f"Cliente CF {suffix}",
                "document": f"12{suffix[-8:]}0001",
                "email": f"cliente.cf.{suffix}@example.com",
                "phone": "14988887777",
                "status": "active",
                "address": {"street": "Rua Cliente", "number": "50", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "À vista", "credit_limit": "5000.00"},
            }))
            ids["participant_id"] = participant["id"]
            account = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company["id"],
                "name": f"Banco Fluxo {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir",
                "currency": "BRL",
                "opening_balance_amount": "1000.00",
                "is_default_receivable": True,
                "status": "active",
            }))
            ids["account_id"] = account["id"]
            return {"company_id": company["id"], "participant_id": participant["id"], "account_id": account["id"]}

        _case(results, "setup_base", "Cria empresa, cliente e conta financeira ativa.", setup_base)

        def create_titles():
            overdue = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": ids["company_id"],
                "participant_id": ids["participant_id"],
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"cf-overdue-{suffix}",
                "expected_financial_account_id": ids["account_id"],
                "document_reference": f"AR-VENCIDO-{suffix}",
                "due_date": (today - timedelta(days=5)).isoformat(),
                "gross_amount": "120.00",
                "fiscal_status": "not_required",
                "notes": "Título vencido para dashboard",
            }))
            open_title = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": ids["company_id"],
                "participant_id": ids["participant_id"],
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"cf-open-{suffix}",
                "expected_financial_account_id": ids["account_id"],
                "document_reference": f"AR-ABERTO-{suffix}",
                "due_date": (today + timedelta(days=2)).isoformat(),
                "gross_amount": "300.00",
                "fiscal_status": "not_required",
                "notes": "Título aberto para dashboard",
            }))
            ids["title_overdue"] = overdue["id"]
            ids["title_open"] = open_title["id"]
            return {"overdue_id": overdue["id"], "open_id": open_title["id"]}

        _case(results, "create_receivables", "Cria título vencido e título futuro para previsão de caixa.", create_titles)

        def receive_partial_title():
            result = receive_title(db, SettlementCreate(**{
                "company_id": ids["company_id"],
                "financial_title_id": ids["title_open"],
                "financial_account_id": ids["account_id"],
                "settlement_date": today.isoformat(),
                "received_amount": "100.00",
                "fee_amount": "2.50",
                "source_type": "manual",
                "source_id": f"cf-settlement-{suffix}",
                "evidence_reference": f"PIX-CF-{suffix}",
            }))
            ids["settlement_id"] = result["settlement"]["id"]
            ids["movement_receipt"] = result["movement"]["id"]
            _assert(_money(result["balance"]["current_balance_amount"]) == Decimal("1097.50"), "saldo interno deveria considerar abertura + movimento líquido")
            return {"settlement_id": ids["settlement_id"], "movement_id": ids["movement_receipt"], "balance": result["balance"]["current_balance_amount"]}

        _case(results, "receive_title", "Baixa parcial gera movimento e saldo interno.", receive_partial_title)

        def create_outflow_movement():
            result = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_id"],
                "direction": "outflow",
                "movement_type": "bank_fee",
                "movement_date": today.isoformat(),
                "amount": "30.00",
                "description": "Saída manual para validar fluxo líquido",
                "source_type": "manual",
                "source_id": f"cf-outflow-{suffix}",
            }))
            ids["movement_outflow"] = result["movement"]["id"]
            _assert(_money(result["balance"]["current_balance_amount"]) == Decimal("1067.50"), "saldo interno deveria reduzir saída manual")
            return {"movement_id": ids["movement_outflow"], "balance": result["balance"]["current_balance_amount"]}

        _case(results, "create_outflow", "Movimento manual de saída reduz saldo interno.", create_outflow_movement)

        def import_and_match_statement():
            imported = import_statement(db, BankStatementImportCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_id"],
                "source_type": "manual",
                "source_id": f"cf-statement-{suffix}",
                "file_name": "extrato-cash-flow.csv",
                "statement_start_date": today.isoformat(),
                "statement_end_date": today.isoformat(),
                "lines": [{
                    "external_id": f"cf-line-{suffix}",
                    "line_date": today.isoformat(),
                    "direction": "inflow",
                    "amount": "97.50",
                    "description": "PIX líquido recebido",
                    "bank_reference": f"PIX-CF-{suffix}",
                }],
            }))
            ids["statement_line"] = imported["lines"][0]["id"]
            matched = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["statement_line"],
                "financial_movement_id": ids["movement_receipt"],
                "match_type": "manual",
            }))
            _assert(matched["match"]["status"] == "confirmed", "match deveria ser confirmado")
            return {"line_id": ids["statement_line"], "match_id": matched["match"]["id"]}

        _case(results, "statement_match", "Importa extrato e concilia movimento de recebimento.", import_and_match_statement)

        def validate_summary():
            summary = get_cash_flow_summary(db, company_id=ids["company_id"], start_date=today - timedelta(days=7), end_date=today + timedelta(days=7))
            _assert(_money(summary["internal_balance_total"]) == Decimal("1067.50"), "saldo interno total incorreto")
            _assert(_money(summary["realized_inflow_amount"]) == Decimal("97.50"), "entrada realizada deveria considerar movimento líquido")
            _assert(_money(summary["realized_outflow_amount"]) == Decimal("30.00"), "saída realizada deveria aparecer")
            _assert(summary["overdue_receivable_count"] >= 1, "deveria apontar título vencido")
            _assert(summary["matched_movement_count"] >= 1, "deveria apontar movimento conciliado")
            return summary

        _case(results, "summary", "Resumo consolida previsto, realizado, saldo e conciliação.", validate_summary)

        def validate_daily_accounts_pending():
            daily = get_cash_flow_daily(db, company_id=ids["company_id"], start_date=today - timedelta(days=7), end_date=today + timedelta(days=7))
            accounts = get_cash_flow_accounts(db, company_id=ids["company_id"], start_date=today - timedelta(days=7), end_date=today + timedelta(days=7))
            pending = get_cash_flow_pending(db, company_id=ids["company_id"], start_date=today - timedelta(days=7), end_date=today + timedelta(days=7))
            recon = get_cash_flow_reconciliation_status(db, company_id=ids["company_id"], start_date=today - timedelta(days=7), end_date=today + timedelta(days=7))
            today_row = next(row for row in daily if row["date"] == today.isoformat())
            _assert(_money(today_row["movement_inflow_amount"]) == Decimal("97.50"), "dia deveria mostrar entrada líquida")
            _assert(accounts and _money(accounts[0]["current_balance_amount"]) == Decimal("1067.50"), "conta deveria mostrar saldo atual")
            _assert(pending["overdue_titles"], "pendências deveriam incluir título vencido")
            _assert("matched" in recon["financial_movements"], "status de conciliação deveria incluir matched")
            return {"daily_rows": len(daily), "accounts": len(accounts), "overdue_titles": len(pending["overdue_titles"]), "reconciliation_keys": list(recon["financial_movements"].keys())}

        _case(results, "daily_accounts_pending", "Detalhes por dia, conta, pendência e conciliação permanecem coerentes.", validate_daily_accounts_pending)

        failed = [result for result in results if result.status != "PASS"]
        return {
            "status": "PASS" if not failed else "FAIL",
            "summary": {"total": len(results), "passed": len(results) - len(failed), "failed": len(failed)},
            "cases": [result.__dict__ for result in results],
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="bloco_11_cash_flow_stress_report.json")
    args = parser.parse_args()
    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
