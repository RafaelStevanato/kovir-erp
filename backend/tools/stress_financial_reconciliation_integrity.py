r"""
Kovir ERP — Stress financeiro consolidado pós-conciliação
==========================================================

Valida a cadeia crítica:
- Company -> Participants -> Financial Masters -> Accounts Receivable;
- Recebimento/Baixa -> Financial Movement -> Account Balance;
- Importação de extrato -> Match de conciliação;
- Bloqueio de estorno de baixa já conciliada;
- Estorno de match antes do estorno de baixa;
- Integridade de saldo interno, título e status de conciliação.

Uso PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_financial_reconciliation_integrity.py --output financial_reconciliation_integrity_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_financial_reconciliation_integrity.py --sqlite-smoke-db ..\financial_reconciliation_integrity.db --output financial_reconciliation_integrity_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass, field
from datetime import date
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


def _expect_error(func: Callable[[], Any], contains: str | None = None) -> str:
    try:
        func()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if contains and contains.lower() not in message.lower():
            raise AssertionError(f"Erro esperado deveria conter {contains!r}, mas foi: {message}") from exc
        return message
    raise AssertionError("Operação deveria falhar, mas foi concluída.")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from sqlalchemy import text

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate
    from app.modules.accounts_receivable.service import create_manual_receivable, get_receivable_history
    from app.modules.cash.schemas import SettlementCreate, SettlementReverse
    from app.modules.cash.service import get_cash_summary, list_account_balances, receive_title, reverse_settlement
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import FinancialAccountCreate
    from app.modules.financial.service import create_financial_account
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.reconciliation.schemas import BankStatementImportCreate, ReconciliationMatchCreate, ReverseReconciliationMatch
    from app.modules.reconciliation.service import confirm_match, get_reconciliation_summary, import_statement, reverse_match, suggest_matches

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, str] = {}
    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]

    try:
        def setup_base():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Integridade Financeira {suffix} LTDA",
                "trade_name": f"Kovir Fin {suffix}",
                "cnpj": f"550011{suffix}",
                "email": f"fin.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Financeiro",
                "status": "active",
                "address": {"street": "Rua Financeira", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            customer = create_participant(db, ParticipantCreate(**{
                "company_id": company["id"],
                "participant_type": "customer",
                "person_type": "company",
                "name": f"Cliente Integridade {suffix}",
                "document": f"449988{suffix}",
                "email": f"cliente.{suffix}@teste.com",
                "phone": "14988888888",
                "status": "active",
                "address": {"street": "Rua Cliente", "number": "10", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"credit_limit": "1000", "default_payment_method": "pix", "default_payment_terms": "a_vista"},
            }))
            account = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company["id"],
                "name": f"Banco Integridade {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir",
                "currency": "BRL",
                "opening_balance_amount": "10.00",
                "is_default_receivable": True,
                "status": "active",
            }))
            title = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": company["id"],
                "participant_id": customer["id"],
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"FULL-FIN-{suffix}",
                "due_date": date.today().isoformat(),
                "gross_amount": "100.00",
                "document_reference": f"DOC-FIN-{suffix}",
                "notes": "Título para teste completo de baixa e conciliação.",
            }))
            ids.update(company_id=company["id"], customer_id=customer["id"], account_id=account["id"], title_id=title["id"])
            return ids.copy()

        _case(results, "01_setup_base", "Cria empresa, cliente, conta financeira e título a receber.", setup_base)

        def receive_and_move():
            result = receive_title(db, SettlementCreate(**{
                "company_id": ids["company_id"],
                "financial_title_id": ids["title_id"],
                "financial_account_id": ids["account_id"],
                "settlement_date": date.today().isoformat(),
                "received_amount": "100.00",
                "discount_amount": "0.00",
                "interest_amount": "0.00",
                "penalty_amount": "0.00",
                "fee_amount": "2.00",
                "evidence_reference": f"PIX-FIN-{suffix}",
            }))
            ids["settlement_id"] = result["settlement"]["id"]
            ids["movement_id"] = result["movement"]["id"]
            _assert(result["title"]["status"] == "received", "Título deveria ficar recebido.")
            _assert(result["movement"]["reconciliation_status"] == "pending", "Movimento deve nascer pendente de conciliação.")
            _assert(_money(result["movement"]["amount"]) == Decimal("98.00"), "Taxa deve reduzir o movimento financeiro.")
            return {"settlement_id": ids["settlement_id"], "movement_id": ids["movement_id"], "balance": result["balance"]}

        _case(results, "02_receive_title", "Baixa título, cria movimento financeiro líquido e atualiza saldo interno.", receive_and_move)

        def import_and_match():
            statement = import_statement(db, BankStatementImportCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_id"],
                "source_type": "manual",
                "source_id": f"FULL-STMT-{suffix}",
                "file_name": "extrato-financeiro.csv",
                "statement_start_date": date.today().isoformat(),
                "statement_end_date": date.today().isoformat(),
                "lines": [{
                    "external_id": f"FULL-LINE-{suffix}",
                    "line_date": date.today().isoformat(),
                    "direction": "inflow",
                    "amount": "98.00",
                    "description": "Entrada líquida bancária do recebimento",
                    "bank_reference": f"PIX-FIN-{suffix}",
                }],
            }))
            ids["statement_line_id"] = statement["lines"][0]["id"]
            suggestions = suggest_matches(db, company_id=ids["company_id"], statement_line_id=ids["statement_line_id"])
            _assert(any(candidate["id"] == ids["movement_id"] for candidate in suggestions["candidates"]), "Movimento da baixa deveria ser sugerido.")
            match = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["statement_line_id"],
                "financial_movement_id": ids["movement_id"],
                "match_type": "suggested",
                "tolerance_amount": "0.00",
            }))
            ids["match_id"] = match["match"]["id"]
            _assert(match["statement_line"]["status"] == "matched", "Linha deve ficar matched.")
            _assert(match["financial_movement"]["reconciliation_status"] == "matched", "Movimento deve ficar matched.")
            return {"match_id": ids["match_id"], "suggestions": len(suggestions["candidates"])}

        _case(results, "03_reconcile_receipt", "Importa extrato e concilia com movimento gerado pela baixa.", import_and_match)

        def block_reversal_before_unmatch():
            error = _expect_error(
                lambda: reverse_settlement(db, ids["settlement_id"], SettlementReverse(reason="Não deve estornar baixa conciliada.")),
                "Estorne o match",
            )
            return {"blocked_error": error}

        _case(results, "04_block_settlement_reversal_when_reconciled", "Baixa conciliada não pode ser estornada antes do estorno do match.", block_reversal_before_unmatch)

        def reverse_match_then_settlement():
            reversed_match = reverse_match(db, ids["match_id"], ReverseReconciliationMatch(reason="Reabrir conciliação para estornar baixa."))
            _assert(reversed_match["financial_movement"]["reconciliation_status"] == "pending", "Movimento deve voltar para pendente após estorno do match.")
            reversed_settlement = reverse_settlement(db, ids["settlement_id"], SettlementReverse(reason="Estorno autorizado após desfazer match."))
            _assert(reversed_settlement["settlement"]["status"] == "reversed", "Baixa deve ficar estornada.")
            _assert(reversed_settlement["title"]["status"] == "open", "Título recebido integralmente deve voltar para aberto após estorno.")
            _assert(_money(reversed_settlement["title"]["open_amount"]) == Decimal("100.00"), "Título deve reabrir integralmente.")
            return {"match_status": reversed_match["match"]["status"], "settlement_status": reversed_settlement["settlement"]["status"], "title_open": reversed_settlement["title"]["open_amount"]}

        _case(results, "05_reverse_match_then_settlement", "Após estornar match, baixa pode ser estornada e título reabre.", reverse_match_then_settlement)

        def final_integrity():
            cash_summary = get_cash_summary(db, company_id=ids["company_id"])
            recon_summary = get_reconciliation_summary(db, company_id=ids["company_id"])
            balances = list_account_balances(db, company_id=ids["company_id"])
            history = get_receivable_history(db, ids["title_id"])
            checks = {
                "orphan_movements_without_account": "select count(*) from financial_movements fm left join financial_accounts fa on fa.id = fm.financial_account_id where fa.id is null",
                "orphan_matches_without_line": "select count(*) from reconciliation_matches rm left join bank_statement_lines bsl on bsl.id = rm.statement_line_id where bsl.id is null",
                "orphan_matches_without_movement": "select count(*) from reconciliation_matches rm left join financial_movements fm on fm.id = rm.financial_movement_id where fm.id is null",
            }
            evidence = {name: db.execute(text(sql)).scalar_one() for name, sql in checks.items()}
            for name, count in evidence.items():
                _assert(count == 0, f"Integridade falhou: {name}={count}")
            return {"cash_summary": cash_summary, "reconciliation_summary": recon_summary, "balances": balances, "title_history_count": len(history), "orphan_checks": evidence}

        _case(results, "06_final_integrity", "Confere saldos, resumos, histórico e ausência de órfãos nos vínculos financeiros.", final_integrity)

    finally:
        failed = sum(1 for result in results if result.status == "FAIL")
        passed = sum(1 for result in results if result.status == "PASS")
        report = {
            "status": "PASS" if failed == 0 else "FAIL",
            "sqlite_smoke_mode": sqlite_mode,
            "summary": {"passed": passed, "failed": failed, "total": len(results)},
            "ids": ids,
            "cases": [result.__dict__ for result in results],
        }
        db.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="financial_reconciliation_integrity_report.json")
    args = parser.parse_args()
    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
