r"""
Kovir ERP — Bloco 9 — Stress Recebimentos, Baixas e Movimentos Financeiros
===========================================================================

Valida:
- título a receber em aberto;
- baixa parcial com movimento financeiro interno;
- bloqueio de baixa acima do saldo em aberto;
- baixa final com taxa;
- cancelamento de título recebido bloqueado;
- estorno de baixa criando movimento reverso e reabrindo saldo;
- movimento manual alterando saldo interno;
- saldos internos com atualização protegida por FOR UPDATE no service.

Uso PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_bloco_9_cash.py --output bloco_9_cash_stress_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_bloco_9_cash.py --sqlite-smoke-db ..\bloco_9_cash_smoke.db --output bloco_9_cash_stress_report.json
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
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.financial.schemas import FinancialAccountCreate
    from app.modules.financial.service import create_financial_account
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate, FinancialTitleStatusChange
    from app.modules.accounts_receivable.service import cancel_receivable, create_manual_receivable, get_receivable, get_receivables_summary
    from app.modules.cash.schemas import ManualFinancialMovementCreate, SettlementCreate, SettlementReverse
    from app.modules.cash.service import create_manual_movement, get_cash_summary, list_account_balances, list_movements, list_settlements, receive_title, reverse_settlement

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, str] = {}
    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]

    try:
        def setup():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Cash Stress {suffix} LTDA",
                "trade_name": f"Kovir Cash {suffix}",
                "cnpj": f"112233{suffix[-8:]}",
                "email": f"cash.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Cash",
                "status": "active",
                "address": {"street": "Rua Cash", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            ids["company_id"] = company["id"]
            customer = create_participant(db, ParticipantCreate(**{
                "company_id": company["id"],
                "participant_type": "customer",
                "person_type": "company",
                "name": f"Cliente Cash {suffix} LTDA",
                "document": f"445566{suffix[-8:]}",
                "email": f"cliente.cash.{suffix}@teste.com",
                "phone": "14988888888",
                "status": "active",
                "address": {"street": "Rua Cliente", "number": "200", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "is_foreign": False},
                "financial_settings": {"credit_limit": "10000", "default_payment_method": "pix", "default_payment_terms": "À vista"},
            }))
            ids["customer_id"] = customer["id"]
            account = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company["id"],
                "name": f"Banco Stress Cash {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir",
                "currency": "BRL",
                "opening_balance_amount": "100.00",
                "is_default_receivable": True,
                "status": "active",
            }))
            ids["financial_account_id"] = account["id"]
            title = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": company["id"],
                "participant_id": customer["id"],
                "title_type": "manual",
                "source_type": "manual",
                "document_reference": f"STRESS-CASH-{suffix}",
                "due_date": date.today().isoformat(),
                "gross_amount": "100.00",
                "expected_financial_account_id": account["id"],
                "notes": "Título para stress de recebimentos.",
            }))
            ids["title_id"] = title["id"]
            return {"company_id": company["id"], "title_id": title["id"], "account_id": account["id"], "open_amount": title["open_amount"]}

        _case(results, "setup_base", "Cria empresa, cliente, conta financeira e título AR.", setup)

        def partial_receipt():
            result = receive_title(db, SettlementCreate(**{
                "company_id": ids["company_id"],
                "financial_title_id": ids["title_id"],
                "financial_account_id": ids["financial_account_id"],
                "settlement_date": date.today().isoformat(),
                "received_amount": "40.00",
                "evidence_reference": f"PIX-PARCIAL-{suffix}",
            }))
            ids["settlement_1"] = result["settlement"]["id"]
            title = result["title"]
            balance = result["balance"]
            _assert(_money(title["paid_amount"]) == Decimal("40.00"), "paid_amount deveria ser 40")
            _assert(_money(title["open_amount"]) == Decimal("60.00"), "open_amount deveria ser 60")
            _assert(title["status"] == "partially_received", "status deveria ser partially_received")
            _assert(_money(balance["current_balance_amount"]) == Decimal("140.00"), "saldo interno deveria ser 140")
            return {"settlement_id": ids["settlement_1"], "title_status": title["status"], "balance": balance["current_balance_amount"]}

        _case(results, "partial_receipt", "Baixa parcial reduz título e aumenta saldo interno.", partial_receipt)

        def block_over_receipt():
            message = _expect_error(lambda: receive_title(db, SettlementCreate(**{
                "company_id": ids["company_id"],
                "financial_title_id": ids["title_id"],
                "financial_account_id": ids["financial_account_id"],
                "settlement_date": date.today().isoformat(),
                "received_amount": "70.00",
            })), "excede")
            return {"error": message}

        _case(results, "block_over_receipt", "Bloqueia baixa acima do saldo em aberto.", block_over_receipt)

        def final_receipt_with_fee():
            result = receive_title(db, SettlementCreate(**{
                "company_id": ids["company_id"],
                "financial_title_id": ids["title_id"],
                "financial_account_id": ids["financial_account_id"],
                "settlement_date": date.today().isoformat(),
                "received_amount": "60.00",
                "fee_amount": "2.00",
                "evidence_reference": f"PIX-FINAL-{suffix}",
            }))
            ids["settlement_2"] = result["settlement"]["id"]
            title = result["title"]
            balance = result["balance"]
            _assert(title["status"] == "received", "status deveria ser received")
            _assert(_money(title["open_amount"]) == Decimal("0.00"), "open_amount deveria ser zero")
            _assert(_money(balance["current_balance_amount"]) == Decimal("198.00"), "saldo interno deveria considerar taxa e ficar 198")
            return {"settlement_id": ids["settlement_2"], "movement_amount": result["movement"]["amount"], "balance": balance["current_balance_amount"]}

        _case(results, "final_receipt_with_fee", "Baixa final encerra título e movimento considera taxa.", final_receipt_with_fee)

        def block_cancel_received_title():
            message = _expect_error(lambda: cancel_receivable(db, ids["title_id"], FinancialTitleStatusChange(reason="Tentativa indevida após recebimento.")), "recebimento")
            return {"error": message}

        _case(results, "block_cancel_received_title", "Título recebido não pode ser cancelado sem estorno.", block_cancel_received_title)

        def reverse_partial_settlement():
            result = reverse_settlement(db, ids["settlement_1"], SettlementReverse(reason="Estorno de teste da primeira baixa."))
            title = result["title"]
            balance = result["balance"]
            _assert(title["status"] == "partially_received", "título deveria voltar para partially_received")
            _assert(_money(title["paid_amount"]) == Decimal("60.00"), "paid_amount deveria voltar para 60")
            _assert(_money(title["open_amount"]) == Decimal("40.00"), "open_amount deveria voltar para 40")
            _assert(_money(balance["current_balance_amount"]) == Decimal("158.00"), "saldo interno deveria reduzir para 158")
            return {"title_status": title["status"], "open_amount": title["open_amount"], "balance": balance["current_balance_amount"]}

        _case(results, "reverse_partial_settlement", "Estorno cria movimento reverso e reabre saldo do título.", reverse_partial_settlement)

        def manual_outflow():
            result = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["financial_account_id"],
                "direction": "outflow",
                "movement_type": "bank_fee_adjustment",
                "movement_date": date.today().isoformat(),
                "amount": "8.00",
                "description": "Tarifa bancária manual de teste.",
            }))
            balance = result["balance"]
            _assert(_money(balance["current_balance_amount"]) == Decimal("150.00"), "saldo interno deveria ir para 150")
            return {"movement_id": result["movement"]["id"], "balance": balance["current_balance_amount"]}

        _case(results, "manual_outflow", "Movimento manual de saída reduz saldo interno.", manual_outflow)

        def final_integrity():
            title = get_receivable(db, ids["title_id"])
            settlements = list_settlements(db, company_id=ids["company_id"])
            movements = list_movements(db, company_id=ids["company_id"])
            balances = list_account_balances(db, company_id=ids["company_id"])
            cash_summary = get_cash_summary(db, company_id=ids["company_id"])
            ar_summary = get_receivables_summary(db, company_id=ids["company_id"])
            _assert(len(settlements) == 2, "deveria haver 2 baixas")
            _assert(len(movements) == 4, "deveria haver 4 movimentos: 2 recebimentos, 1 estorno, 1 manual")
            _assert(len(balances) == 1, "deveria haver saldo materializado")
            pending_count = sum(1 for movement in movements if movement.get("reconciliation_status") == "pending")
            _assert(cash_summary["pending_reconciliation_count"] == pending_count, "resumo de conciliação pendente deve bater com os movimentos pendentes")
            _assert(pending_count >= 3, "deveria haver ao menos 3 movimentos pendentes de conciliação")
            return {"title": {"status": title["status"], "open_amount": title["open_amount"]}, "cash_summary": cash_summary, "ar_summary": ar_summary}

        _case(results, "final_integrity", "Confere baixa, movimentos, saldo, pendência de conciliação e resumo AR.", final_integrity)

        failed = [case for case in results if case.status != "PASS"]
        return {
            "status": "PASS" if not failed else "FAIL",
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "sqlite_mode": sqlite_mode,
            "cases": [case.__dict__ for case in results],
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="bloco_9_cash_stress_report.json")
    args = parser.parse_args()
    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
