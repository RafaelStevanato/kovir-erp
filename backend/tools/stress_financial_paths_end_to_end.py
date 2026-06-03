r"""
Kovir ERP — Stress End-to-End dos caminhos financeiros
=======================================================

Cobre, em uma bateria única e rastreável:
- Empresa -> Participantes -> Cadastros Financeiros Base;
- Contas a Receber manual -> baixa parcial -> movimento de entrada -> saldo interno;
- Compras/Despesas -> Contas a Pagar -> pagamento parcial -> movimento de saída -> saldo interno;
- Extrato bancário -> match de conciliação de entrada e saída;
- Fluxo de caixa consolidando entradas previstas, saídas previstas, realizado, pendências e conciliação;
- guardrails de multiempresa, duplicidade, overpayment, locks e órfãos relacionais.

Uso PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_financial_paths_end_to_end.py --output stress_financial_paths_end_to_end_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_financial_paths_end_to_end.py --sqlite-smoke-db ..\stress_financial_paths_end_to_end_smoke.db --output stress_financial_paths_end_to_end_report.json
"""
from __future__ import annotations

import argparse
import inspect
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


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_error(func: Callable[[], Any], contains: str | None = None) -> str:
    try:
        func()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if contains and contains.lower() not in message.lower():
            raise AssertionError(f"Erro esperado deveria conter {contains!r}, mas retornou: {message}") from exc
        return message
    raise AssertionError("Operação deveria falhar, mas foi concluída com sucesso.")


def _case(results: list[CaseResult], name: str, expected: str, func: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
    try:
        evidence = func() or {}
        results.append(CaseResult(name=name, expected=expected, status="PASS", evidence=evidence))
        return evidence
    except Exception as exc:  # noqa: BLE001
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=f"{type(exc).__name__}: {exc}"))
        return {}


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from sqlalchemy import text

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate
    from app.modules.accounts_receivable.service import create_manual_receivable, list_receivables
    from app.modules.cash.schemas import SettlementCreate
    from app.modules.cash.service import receive_title
    from app.modules.cash import repository as cash_repository
    from app.modules.cash_flow.service import get_cash_flow_daily, get_cash_flow_pending, get_cash_flow_reconciliation_status, get_cash_flow_summary
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import FinancialAccountCreate
    from app.modules.financial.service import create_default_financial_masters, create_financial_account, list_cost_centers, list_financial_accounts, list_financial_categories
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.purchases_payables.schemas import PayablePaymentCreate, PurchaseConfirmPayload, PurchaseCreate
    from app.modules.purchases_payables.service import confirm_purchase, create_purchase_draft, get_purchases_payables_summary, list_payables, pay_payable
    from app.modules.purchases_payables import repository as purchases_repository
    from app.modules.reconciliation.schemas import BankStatementImportCreate, ReconciliationMatchCreate
    from app.modules.reconciliation.service import confirm_match, import_statement

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, Any] = {}
    today = date.today()
    suffix = str(abs(hash((today.isoformat(), os.getpid(), id(db))))).zfill(8)[-8:]

    def remember(key: str, value: Any) -> Any:
        ids[key] = value
        return value

    def _participant_document(doc_prefix: str) -> str:
        # ParticipantCreate valida documento com exatamente 11 ou 14 caracteres
        # alfanuméricos. O stress usa PJ sintética, então gera CNPJ alfanumérico
        # estável de 14 posições para evitar falha artificial na fundação.
        raw = f"{doc_prefix}{suffix}0001".upper()
        only_alnum = "".join(ch for ch in raw if ch.isalnum())
        return only_alnum[:14].ljust(14, "0")

    def _need(key: str) -> Any:
        if key not in ids:
            raise AssertionError(f"Pré-requisito não criado: {key}. Verifique o caso anterior no relatório.")
        return ids[key]

    def participant_payload(company_id: str, *, name: str, ptype: str, status: str, doc_prefix: str) -> dict[str, Any]:
        return {
            "company_id": company_id,
            "participant_type": ptype,
            "person_type": "company",
            "name": name,
            "trade_name": name,
            "document": _participant_document(doc_prefix),
            "email": f"{doc_prefix.lower()}.{suffix}@example.com",
            "phone": "14999999999",
            "status": status,
            "address": {"street": "Rua Stress", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
            "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
            "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "À vista", "credit_limit": "10000.00"},
        }

    try:
        def setup_foundation() -> dict[str, Any]:
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Stress Financeiro {suffix} LTDA",
                "trade_name": f"Kovir Stress {suffix}",
                "cnpj": f"55{suffix}0001",
                "email": f"financeiro.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Stress Financeiro",
                "status": "active",
                "address": {"street": "Rua Kovir", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            other_company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Stress Outra {suffix} LTDA",
                "trade_name": f"Outra Stress {suffix}",
                "cnpj": f"66{suffix}0001",
                "email": f"outra.{suffix}@example.com",
                "phone": "14999999998",
                "responsible_name": "Operador Outra Empresa",
                "status": "active",
                "address": {"street": "Rua Outra", "number": "200", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            company_id = remember("company_id", company["id"])
            other_company_id = remember("other_company_id", other_company["id"])
            customer = create_participant(db, ParticipantCreate(**participant_payload(company_id, name=f"Cliente Stress {suffix}", ptype="customer", status="active", doc_prefix="CLI")))
            supplier = create_participant(db, ParticipantCreate(**participant_payload(company_id, name=f"Fornecedor Stress {suffix}", ptype="supplier", status="active", doc_prefix="SUP")))
            other_supplier = create_participant(db, ParticipantCreate(**participant_payload(other_company_id, name=f"Fornecedor Outra Empresa {suffix}", ptype="supplier", status="active", doc_prefix="OUT")))
            remember("customer_id", customer["id"])
            remember("supplier_id", supplier["id"])
            remember("other_supplier_id", other_supplier["id"])
            create_default_financial_masters(db, company_id)
            account = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company_id,
                "name": f"Banco Stress {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir",
                "currency": "BRL",
                "opening_balance_amount": "1000.00",
                "is_default_receivable": True,
                "is_default_payable": True,
                "status": "active",
            }))
            categories = list_financial_categories(db, company_id=company_id, limit=200)
            cost_centers = list_cost_centers(db, company_id=company_id, limit=200)
            accounts = list_financial_accounts(db, company_id=company_id, limit=200)
            category = next((row for row in categories if row.get("code") == "DESP-ADMIN"), categories[0])
            cost_center = next((row for row in cost_centers if row.get("code") == "ADMIN"), cost_centers[0])
            remember("account_id", account["id"])
            remember("category_id", category["id"])
            remember("cost_center_id", cost_center["id"])
            _assert(any(row["id"] == account["id"] for row in accounts), "Conta financeira criada deve estar listável.")
            return {"company_id": company_id, "customer_id": customer["id"], "supplier_id": supplier["id"], "account_id": account["id"], "category_id": category["id"], "cost_center_id": cost_center["id"]}

        _case(results, "01_foundation_company_participants_financial_masters", "Cria empresa, cliente, fornecedor, cadastros financeiros e conta bancária sem texto solto.", setup_foundation)

        def receivable_to_cash_path() -> dict[str, Any]:
            title = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": _need("company_id"),
                "participant_id": _need("customer_id"),
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"e2e-ar-{suffix}",
                "expected_financial_account_id": _need("account_id"),
                "financial_category_id": None,
                "cost_center_id": _need("cost_center_id"),
                "document_reference": f"AR-E2E-{suffix}",
                "due_date": (today + timedelta(days=2)).isoformat(),
                "gross_amount": "500.00",
                "fiscal_status": "not_required",
                "notes": "Recebível manual para stress financeiro end-to-end.",
            }))
            result = receive_title(db, SettlementCreate(**{
                "company_id": _need("company_id"),
                "financial_title_id": title["id"],
                "financial_account_id": _need("account_id"),
                "settlement_date": today.isoformat(),
                "received_amount": "200.00",
                "fee_amount": "5.00",
                "source_type": "manual",
                "source_id": f"e2e-receipt-{suffix}",
                "evidence_reference": f"PIX-AR-{suffix}",
            }))
            remember("receivable_title_id", title["id"])
            remember("receipt_settlement_id", result["settlement"]["id"])
            remember("receipt_movement_id", result["movement"]["id"])
            _assert(_money(result["movement"]["amount"]) == Decimal("195.00"), "Recebimento de 200 com tarifa 5 deve gerar entrada líquida 195.")
            _assert(_money(result["title"]["open_amount"]) == Decimal("300.00"), "Título deve permanecer parcialmente aberto em 300.")
            _assert(_money(result["balance"]["current_balance_amount"]) == Decimal("1195.00"), "Saldo interno deveria ser 1000 + 195.")
            return {"title_id": title["id"], "movement_id": result["movement"]["id"], "balance": result["balance"]["current_balance_amount"]}

        _case(results, "02_receivable_settlement_cash_inflow", "Contas a Receber baixa parcial, gera movimento de entrada e atualiza saldo interno.", receivable_to_cash_path)

        def purchase_to_payable_path() -> dict[str, Any]:
            purchase = create_purchase_draft(db, PurchaseCreate(**{
                "company_id": _need("company_id"),
                "participant_id": _need("supplier_id"),
                "purchase_type": "expense",
                "origin": "manual",
                "fiscal_status": "pending_document",
                "issue_date": today.isoformat(),
                "competency_date": today.isoformat(),
                "financial_category_id": _need("category_id"),
                "cost_center_id": _need("cost_center_id"),
                "expected_financial_account_id": _need("account_id"),
                "document_type": "invoice",
                "document_number": f"AP-E2E-{suffix}",
                "invoice_total_amount": "360.00",
                "notes": "Despesa operacional para stress financeiro end-to-end.",
                "items": [{"description": "Despesa operacional", "quantity": "1", "unit": "UN", "unit_cost": "360.00"}],
            }))
            confirmed = confirm_purchase(db, purchase["id"], PurchaseConfirmPayload(**{
                "reason": "Confirmação end-to-end: compra vira título a pagar.",
                "installments": [
                    {"due_date": (today - timedelta(days=1)).isoformat(), "amount": "160.00", "expected_financial_account_id": _need("account_id"), "document_reference": f"AP-E2E-{suffix}-1"},
                    {"due_date": (today + timedelta(days=8)).isoformat(), "amount": "200.00", "expected_financial_account_id": _need("account_id"), "document_reference": f"AP-E2E-{suffix}-2"},
                ],
            }))
            payables = confirmed["payables"]
            overdue = next(row for row in payables if row["status"] == "overdue")
            remember("purchase_id", purchase["id"])
            remember("first_payable_id", overdue["id"])
            _assert(len(payables) == 2, "Compra confirmada deveria gerar duas parcelas/títulos a pagar.")
            _assert(sum(_money(row["open_amount"]) for row in payables) == Decimal("360.00"), "Soma dos títulos a pagar deve fechar com a compra.")
            return {"purchase_id": purchase["id"], "payables": [row["id"] for row in payables], "overdue_title_id": overdue["id"]}

        _case(results, "03_purchase_generates_payables", "Compra/despesa confirmada gera títulos a pagar separados da saída de caixa.", purchase_to_payable_path)

        def payable_to_cash_path() -> dict[str, Any]:
            result = pay_payable(db, PayablePaymentCreate(**{
                "company_id": _need("company_id"),
                "financial_title_id": _need("first_payable_id"),
                "financial_account_id": _need("account_id"),
                "payment_date": today.isoformat(),
                "paid_amount": "100.00",
                "discount_amount": "10.00",
                "interest_amount": "2.00",
                "penalty_amount": "0.00",
                "fee_amount": "3.00",
                "source_type": "manual",
                "source_id": f"e2e-payment-{suffix}",
                "evidence_reference": f"COMPROVANTE-AP-{suffix}",
                "notes": "Pagamento parcial de AP com desconto, juros e tarifa.",
            }))
            remember("payable_settlement_id", result["settlement"]["id"])
            remember("payable_movement_id", result["movement"]["id"])
            _assert(_money(result["movement"]["amount"]) == Decimal("105.00"), "Pagamento deve gerar saída de 100 + 2 + 3 = 105.")
            _assert(_money(result["title"]["open_amount"]) == Decimal("50.00"), "Título AP deveria ficar com saldo aberto 50 após efeito 100 + desconto 10.")
            _assert(_money(result["balance"]["current_balance_amount"]) == Decimal("1090.00"), "Saldo interno deveria ser 1195 - 105.")
            return {"movement_id": result["movement"]["id"], "title_status": result["title"]["status"], "balance": result["balance"]["current_balance_amount"]}

        _case(results, "04_payable_payment_cash_outflow", "Pagamento de título a pagar gera baixa, movimento de saída, saldo e pendência de conciliação.", payable_to_cash_path)

        def safety_guards() -> dict[str, Any]:
            duplicate_payment = _expect_error(lambda: pay_payable(db, PayablePaymentCreate(**{
                "company_id": _need("company_id"),
                "financial_title_id": _need("first_payable_id"),
                "financial_account_id": _need("account_id"),
                "payment_date": today.isoformat(),
                "paid_amount": "1.00",
                "source_type": "manual",
                "source_id": f"e2e-payment-{suffix}",
            })), "Já existe")
            overpayment = _expect_error(lambda: pay_payable(db, PayablePaymentCreate(**{
                "company_id": _need("company_id"),
                "financial_title_id": _need("first_payable_id"),
                "financial_account_id": _need("account_id"),
                "payment_date": today.isoformat(),
                "paid_amount": "500.00",
                "source_type": "manual",
                "source_id": f"e2e-overpay-{suffix}",
            })), "excede")
            cross_company_supplier = _expect_error(lambda: create_purchase_draft(db, PurchaseCreate(**{
                "company_id": _need("company_id"),
                "participant_id": _need("other_supplier_id"),
                "purchase_type": "expense",
                "origin": "manual",
                "issue_date": today.isoformat(),
                "invoice_total_amount": "10.00",
                "items": [{"description": "Fornecedor de outra empresa", "quantity": "1", "unit": "UN", "unit_cost": "10.00"}],
            })), "não encontrado")
            return {"duplicate_payment_blocked": duplicate_payment, "overpayment_blocked": overpayment, "cross_company_supplier_blocked": cross_company_supplier}

        _case(results, "05_financial_safety_guards", "Bloqueia baixa duplicada, pagamento acima do saldo e fornecedor de outra empresa.", safety_guards)

        def statement_reconciliation() -> dict[str, Any]:
            imported = import_statement(db, BankStatementImportCreate(**{
                "company_id": _need("company_id"),
                "financial_account_id": _need("account_id"),
                "source_type": "manual",
                "source_id": f"e2e-statement-{suffix}",
                "file_name": "stress-financeiro.csv",
                "statement_start_date": today.isoformat(),
                "statement_end_date": today.isoformat(),
                "opening_balance_amount": "1000.00",
                "closing_balance_amount": "1090.00",
                "lines": [
                    {"external_id": f"e2e-in-{suffix}", "line_date": today.isoformat(), "direction": "inflow", "amount": "195.00", "description": "PIX recebido", "bank_reference": f"PIX-AR-{suffix}"},
                    {"external_id": f"e2e-out-{suffix}", "line_date": today.isoformat(), "direction": "outflow", "amount": "105.00", "description": "Pagamento fornecedor", "bank_reference": f"COMPROVANTE-AP-{suffix}"},
                ],
            }))
            line_in = next(row for row in imported["lines"] if row["direction"] == "inflow")
            line_out = next(row for row in imported["lines"] if row["direction"] == "outflow")
            match_in = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": _need("company_id"),
                "statement_line_id": line_in["id"],
                "financial_movement_id": _need("receipt_movement_id"),
                "match_type": "manual",
            }))
            match_out = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": _need("company_id"),
                "statement_line_id": line_out["id"],
                "financial_movement_id": _need("payable_movement_id"),
                "match_type": "manual",
            }))
            _assert(match_in["match"]["status"] == "confirmed", "Entrada deveria conciliar sem diferença.")
            _assert(match_out["match"]["status"] == "confirmed", "Saída deveria conciliar sem diferença.")
            return {"statement_import_id": imported["statement_import"]["id"], "match_in": match_in["match"]["id"], "match_out": match_out["match"]["id"]}

        _case(results, "06_bank_statement_reconciliation_inflow_outflow", "Extrato externo concilia entrada e saída sem alterar a origem financeira.", statement_reconciliation)

        def cash_flow_views() -> dict[str, Any]:
            start = today - timedelta(days=3)
            end = today + timedelta(days=15)
            summary = get_cash_flow_summary(db, company_id=_need("company_id"), start_date=start, end_date=end)
            daily = get_cash_flow_daily(db, company_id=_need("company_id"), start_date=start, end_date=end)
            pending = get_cash_flow_pending(db, company_id=_need("company_id"), start_date=start, end_date=end)
            recon = get_cash_flow_reconciliation_status(db, company_id=_need("company_id"), start_date=start, end_date=end)
            today_row = next(row for row in daily if row["date"] == today.isoformat())
            _assert(_money(summary["internal_balance_total"]) == Decimal("1090.00"), "Fluxo de caixa deve ler saldo interno pós AR/AP.")
            _assert(_money(summary["realized_inflow_amount"]) == Decimal("195.00"), "Resumo deveria mostrar entrada realizada líquida.")
            _assert(_money(summary["realized_outflow_amount"]) == Decimal("105.00"), "Resumo deveria mostrar saída realizada.")
            _assert(_money(summary["expected_inflow_amount"]) == Decimal("300.00"), "Resumo deveria considerar AR aberto restante.")
            _assert(_money(summary["expected_outflow_amount"]) == Decimal("250.00"), "Resumo deveria considerar AP aberto restante.")
            _assert(pending["overdue_payables"], "Pendências devem incluir conta a pagar vencida/parcial.")
            _assert(_money(today_row["paid_amount"]) == Decimal("105.00"), "Linha diária deveria separar pagamentos realizados.")
            _assert(recon["financial_movements"].get("matched", {}).get("count", 0) >= 2, "Conciliação deveria marcar dois movimentos como matched.")
            return {"summary": summary, "today_row": today_row, "overdue_payables": len(pending["overdue_payables"]), "reconciliation_keys": list(recon["financial_movements"].keys())}

        _case(results, "07_cash_flow_integrates_ar_ap_cash_reconciliation", "Fluxo de caixa consolida AR, AP, caixa, extrato e matches sem corrigir fatos de origem.", cash_flow_views)

        def locks_and_orphans() -> dict[str, Any]:
            source_payable_lock = inspect.getsource(purchases_repository.get_payable_for_update)
            source_balance_lock = inspect.getsource(cash_repository.get_balance_for_update)
            _assert("with_for_update" in source_payable_lock, "Título a pagar deve ser carregado com lock para pagamento.")
            _assert("with_for_update" in source_balance_lock, "Saldo financeiro deve usar lock para alteração.")
            checks_sql = {
                "purchase_items_without_purchase": "select count(*) from purchase_items pi left join purchases p on p.id = pi.purchase_id where p.id is null",
                "purchase_financial_links_without_purchase": "select count(*) from purchase_financial_links pfl left join purchases p on p.id = pfl.purchase_id where p.id is null",
                "purchase_financial_links_without_title": "select count(*) from purchase_financial_links pfl left join financial_titles ft on ft.id = pfl.financial_title_id where ft.id is null",
                "payable_titles_without_participant": "select count(*) from financial_titles ft left join participants p on p.id = ft.participant_id where ft.direction = 'payable' and p.id is null",
                "settlements_without_title": "select count(*) from settlements s left join financial_titles ft on ft.id = s.financial_title_id where ft.id is null",
                "movements_without_account": "select count(*) from financial_movements fm left join financial_accounts fa on fa.id = fm.financial_account_id where fa.id is null",
                "reconciliation_matches_without_line": "select count(*) from reconciliation_matches rm left join bank_statement_lines bsl on bsl.id = rm.statement_line_id where bsl.id is null",
                "reconciliation_matches_without_movement": "select count(*) from reconciliation_matches rm left join financial_movements fm on fm.id = rm.financial_movement_id where fm.id is null",
            }
            evidence: dict[str, Any] = {"locks": {"payable_for_update": True, "balance_for_update": True}, "orphans": {}}
            for name, sql in checks_sql.items():
                count = db.execute(text(sql)).scalar_one()
                evidence["orphans"][name] = count
                _assert(count == 0, f"Integridade relacional falhou: {name}={count}")
            evidence["counts"] = {
                "receivables": len(list_receivables(db, company_id=_need("company_id"))),
                "payables": len(list_payables(db, company_id=_need("company_id"))),
                "financial_accounts": len(list_financial_accounts(db, company_id=_need("company_id"))),
                "purchases_summary": get_purchases_payables_summary(db, company_id=_need("company_id")),
            }
            return evidence

        _case(results, "08_locks_and_relational_integrity", "Locks críticos existem e vínculos financeiros principais não têm órfãos.", locks_and_orphans)

    finally:
        failed = sum(1 for result in results if result.status == "FAIL")
        passed = sum(1 for result in results if result.status == "PASS")
        report = {
            "status": "PASS" if failed == 0 else "FAIL",
            "database_url": os.environ.get("DATABASE_URL", "configured_by_app_settings"),
            "sqlite_smoke_mode": sqlite_mode,
            "summary": {"passed": passed, "failed": failed, "total": len(results)},
            "ids": ids,
            "cases": [result.__dict__ for result in results],
        }
        db.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None, help="Caminho opcional para banco SQLite isolado de smoke test.")
    parser.add_argument("--output", default="stress_financial_paths_end_to_end_report.json", help="Arquivo JSON de saída.")
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
