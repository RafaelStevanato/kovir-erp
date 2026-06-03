r"""
Kovir ERP — Bloco 10 — Stress Conciliação Bancária / Extratos / Matches
=======================================================================

Valida:
- importação de extrato manual;
- sugestão de match por conta, data, direção e valor;
- confirmação de match com FOR UPDATE lógico no service;
- bloqueio de match duplicado;
- bloqueio de contas divergentes;
- estorno de match reabrindo linha e movimento;
- divergência de valor exige justificativa;
- linha ignorada não pode ser conciliada.

Uso PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_bloco_10_reconciliation.py --output bloco_10_reconciliation_stress_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_bloco_10_reconciliation.py --sqlite-smoke-db ..\bloco_10_reconciliation_smoke.db --output bloco_10_reconciliation_stress_report.json
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
    from app.modules.cash.schemas import ManualFinancialMovementCreate
    from app.modules.cash.service import create_manual_movement, list_movements
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import FinancialAccountCreate
    from app.modules.financial.service import create_financial_account
    from app.modules.reconciliation.schemas import BankStatementImportCreate, IgnoreStatementLine, OfxStatementImportText, ReconciliationMatchCreate, ReverseReconciliationMatch
    from app.modules.reconciliation.service import confirm_match, get_reconciliation_summary, ignore_statement_line, import_ofx_statement_text, import_statement, list_reconciliation_matches, list_statement_lines, reverse_match, suggest_matches

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, str] = {}
    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]

    try:
        def setup():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Recon Stress {suffix} LTDA",
                "trade_name": f"Kovir Recon {suffix}",
                "cnpj": f"887766{suffix[-8:]}",
                "email": f"recon.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Recon",
                "status": "active",
                "address": {"street": "Rua Recon", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            ids["company_id"] = company["id"]
            account_1 = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company["id"],
                "name": f"Banco Recon Principal {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir",
                "currency": "BRL",
                "opening_balance_amount": "0.00",
                "is_default_receivable": True,
                "status": "active",
            }))
            account_2 = create_financial_account(db, FinancialAccountCreate(**{
                "company_id": company["id"],
                "name": f"Banco Recon Secundario {suffix}",
                "account_type": "bank_account",
                "institution_name": "Banco Kovir 2",
                "currency": "BRL",
                "opening_balance_amount": "0.00",
                "status": "active",
            }))
            ids["account_1"] = account_1["id"]
            ids["account_2"] = account_2["id"]
            movement = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": company["id"],
                "financial_account_id": account_1["id"],
                "direction": "inflow",
                "movement_type": "manual_receipt_to_reconcile",
                "movement_date": date.today().isoformat(),
                "amount": "150.00",
                "description": "Movimento interno para conciliação exata",
            }))
            ids["movement_exact"] = movement["movement"]["id"]
            return {"company_id": company["id"], "account_1": account_1["id"], "movement_exact": ids["movement_exact"]}

        _case(results, "setup_base", "Cria empresa, duas contas financeiras e movimento interno pendente.", setup)

        def import_exact_statement():
            payload = BankStatementImportCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "source_type": "manual",
                "source_id": f"stmt-exact-{suffix}",
                "file_name": "extrato-exato.csv",
                "statement_start_date": date.today().isoformat(),
                "statement_end_date": date.today().isoformat(),
                "lines": [{
                    "external_id": f"ext-exact-{suffix}",
                    "line_date": date.today().isoformat(),
                    "direction": "inflow",
                    "amount": "150.00",
                    "description": "Entrada banco para conciliar",
                    "bank_reference": "PIX 123",
                }],
            })
            result = import_statement(db, payload)
            ids["line_exact"] = result["lines"][0]["id"]
            _assert(result["statement_import"]["line_count"] == 1, "deveria importar 1 linha")
            _assert(result["lines"][0]["status"] == "pending", "linha deveria iniciar pendente")
            return {"statement_import_id": result["statement_import"]["id"], "line_id": ids["line_exact"]}

        _case(results, "import_statement", "Importa extrato sem alterar saldo interno.", import_exact_statement)


        def import_ofx_statement_case():
            ofx = f'''OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:UTF-8
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE
<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL
<BANKACCTFROM><BANKID>001<ACCTID>12345<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>{date.today().strftime('%Y%m%d')}<DTEND>{date.today().strftime('%Y%m%d')}
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>{date.today().strftime('%Y%m%d')}120000<TRNAMT>150.00<FITID>OFX-{suffix}-001<NAME>PIX RECEBIDO<MEMO>Cliente OFX</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>{date.today().strftime('%Y%m%d')}130000<TRNAMT>-10.50<FITID>OFX-{suffix}-002<NAME>TARIFA<MEMO>Banco</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>139.50<DTASOF>{date.today().strftime('%Y%m%d')}</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>'''
            result = import_ofx_statement_text(db, OfxStatementImportText(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "file_name": f"stress-{suffix}.ofx",
                "ofx_content": ofx,
            }))
            _assert(result["statement_import"]["source_type"] == "ofx", "importação deveria ser source_type=ofx")
            _assert(result["statement_import"]["line_count"] == 2, "OFX deveria gerar 2 linhas")
            _assert(any(line["direction"] == "outflow" for line in result["lines"]), "OFX deveria interpretar saída negativa")
            return {"ofx_import_id": result["statement_import"]["id"], "lines": len(result["lines"])}

        _case(results, "import_ofx_statement", "Importa OFX e converte STMTTRN em linhas de extrato sem alterar saldo interno.", import_ofx_statement_case)
        def suggest_exact_match():
            result = suggest_matches(db, company_id=ids["company_id"], statement_line_id=ids["line_exact"])
            _assert(any(candidate["id"] == ids["movement_exact"] for candidate in result["candidates"]), "movimento exato deveria ser sugerido")
            return {"candidates": len(result["candidates"])}

        _case(results, "suggest_exact_match", "Sugere movimento por mesma conta, direção, data e valor.", suggest_exact_match)

        def confirm_exact_match():
            result = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["line_exact"],
                "financial_movement_id": ids["movement_exact"],
                "match_type": "suggested",
                "tolerance_amount": "0.00",
            }))
            ids["match_exact"] = result["match"]["id"]
            _assert(result["match"]["status"] == "confirmed", "match deveria ser confirmado")
            _assert(result["statement_line"]["status"] == "matched", "linha deveria ficar matched")
            _assert(result["financial_movement"]["reconciliation_status"] == "matched", "movimento deveria ficar matched")
            return {"match_id": ids["match_exact"]}

        _case(results, "confirm_exact_match", "Confirma match e atualiza linha/movimento.", confirm_exact_match)

        def block_duplicate_match():
            message = _expect_error(lambda: confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["line_exact"],
                "financial_movement_id": ids["movement_exact"],
            })), "disponível")
            return {"error": message}

        _case(results, "block_duplicate_match", "Bloqueia match duplicado em linha/movimento já conciliado.", block_duplicate_match)

        def reverse_exact_match():
            result = reverse_match(db, ids["match_exact"], ReverseReconciliationMatch(reason="Teste de estorno de match."))
            _assert(result["match"]["status"] == "reversed", "match deveria ser reversed")
            _assert(result["statement_line"]["status"] == "pending", "linha deveria voltar para pending")
            _assert(result["financial_movement"]["reconciliation_status"] == "pending", "movimento deveria voltar para pending")
            return {"match_status": result["match"]["status"]}

        _case(results, "reverse_match", "Estorna match e reabre linha/movimento.", reverse_exact_match)

        def block_cross_account_match():
            movement = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_2"],
                "direction": "inflow",
                "movement_type": "other_account_movement",
                "movement_date": date.today().isoformat(),
                "amount": "150.00",
                "description": "Movimento de outra conta",
            }))
            ids["movement_other_account"] = movement["movement"]["id"]
            message = _expect_error(lambda: confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["line_exact"],
                "financial_movement_id": ids["movement_other_account"],
            })), "contas")
            return {"error": message}

        _case(results, "block_cross_account_match", "Bloqueia conciliação entre contas financeiras diferentes.", block_cross_account_match)

        def divergence_requires_reason():
            movement = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "direction": "inflow",
                "movement_type": "divergent_movement",
                "movement_date": date.today().isoformat(),
                "amount": "200.00",
                "description": "Movimento divergente",
            }))
            import_result = import_statement(db, BankStatementImportCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "source_type": "manual",
                "source_id": f"stmt-divergent-{suffix}",
                "file_name": "extrato-divergente.csv",
                "lines": [{"external_id": f"ext-divergent-{suffix}", "line_date": date.today().isoformat(), "direction": "inflow", "amount": "199.00", "description": "Linha divergente"}],
            }))
            ids["line_divergent"] = import_result["lines"][0]["id"]
            ids["movement_divergent"] = movement["movement"]["id"]
            message = _expect_error(lambda: confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["line_divergent"],
                "financial_movement_id": ids["movement_divergent"],
                "tolerance_amount": "0.00",
            })), "tolerância")
            return {"error": message}

        _case(results, "divergence_requires_reason", "Diferença acima da tolerância sem permissão é bloqueada.", divergence_requires_reason)

        def force_divergent_match():
            result = confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": ids["line_divergent"],
                "financial_movement_id": ids["movement_divergent"],
                "match_type": "forced",
                "tolerance_amount": "0.00",
                "allow_difference": True,
                "confirmation_reason": "Diferença conhecida de tarifa externa ainda não detalhada.",
            }))
            _assert(result["match"]["status"] == "confirmed_with_difference", "deveria confirmar com diferença")
            _assert(result["statement_line"]["status"] == "divergent", "linha deveria ficar divergent")
            _assert(result["financial_movement"]["reconciliation_status"] == "divergent", "movimento deveria ficar divergent")
            return {"match_id": result["match"]["id"], "difference": result["match"]["difference_amount"]}

        _case(results, "force_divergent_match", "Permite conciliação divergente apenas com justificativa.", force_divergent_match)

        def ignored_line_cannot_match():
            movement = create_manual_movement(db, ManualFinancialMovementCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "direction": "outflow",
                "movement_type": "fee_to_ignore_test",
                "movement_date": date.today().isoformat(),
                "amount": "10.00",
                "description": "Tarifa para teste de linha ignorada",
            }))
            imported = import_statement(db, BankStatementImportCreate(**{
                "company_id": ids["company_id"],
                "financial_account_id": ids["account_1"],
                "source_type": "manual",
                "source_id": f"stmt-ignore-{suffix}",
                "file_name": "extrato-ignore.csv",
                "lines": [{"external_id": f"ext-ignore-{suffix}", "line_date": date.today().isoformat(), "direction": "outflow", "amount": "10.00", "description": "Linha a ignorar"}],
            }))
            line_id = imported["lines"][0]["id"]
            ignored = ignore_statement_line(db, line_id, IgnoreStatementLine(reason="Linha duplicada no extrato externo."))
            _assert(ignored["status"] == "ignored", "linha deveria ficar ignored")
            message = _expect_error(lambda: confirm_match(db, ReconciliationMatchCreate(**{
                "company_id": ids["company_id"],
                "statement_line_id": line_id,
                "financial_movement_id": movement["movement"]["id"],
            })), "disponível")
            return {"line_status": ignored["status"], "error": message}

        _case(results, "ignored_line_cannot_match", "Linha ignorada com justificativa não pode ser conciliada.", ignored_line_cannot_match)

        def summary_and_integrity():
            summary = get_reconciliation_summary(db, company_id=ids["company_id"])
            matches = list_reconciliation_matches(db, company_id=ids["company_id"])
            lines = list_statement_lines(db, company_id=ids["company_id"])
            pending_movements = list_movements(db, company_id=ids["company_id"], reconciliation_status="pending")
            _assert(summary["confirmed_matches"] >= 1, "deveria haver pelo menos um match ativo")
            _assert(len(matches) >= 2, "deveria listar matches")
            _assert(len(lines) >= 3, "deveria listar linhas")
            return {"summary": summary, "matches": len(matches), "lines": len(lines), "pending_movements": len(pending_movements)}

        _case(results, "summary_and_integrity", "Resumo e listagens refletem pendências, matches e divergências.", summary_and_integrity)

        failed = [result for result in results if result.status != "PASS"]
        return {
            "status": "FAIL" if failed else "PASS",
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "sqlite_smoke_db": sqlite_smoke_db,
            "cases": [result.__dict__ for result in results],
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="bloco_10_reconciliation_stress_report.json")
    args = parser.parse_args()
    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
