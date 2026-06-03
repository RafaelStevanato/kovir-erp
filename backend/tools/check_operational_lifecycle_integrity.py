r"""
Kovir ERP — Checagem estrutural do ciclo operacional/financeiro
=================================================================

Valida integridade relacional entre módulos já conectados:
Fiscal/Catálogo -> Vendas -> Estoque -> Contas a Receber -> Baixas ->
Movimentos Financeiros -> Extratos -> Conciliação -> Fluxo de Caixa.

Uso:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\check_operational_lifecycle_integrity.py --output operational_lifecycle_integrity_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _q4(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.0001"))


def _rows(db, sql: str) -> list[Any]:
    from sqlalchemy import text
    return list(db.execute(text(sql)).mappings().all())


def _count(db, sql: str) -> int:
    rows = _rows(db, sql)
    if not rows:
        return 0
    return int(next(iter(rows[0].values())) or 0)


def _check_zero(results: list[CheckResult], db, name: str, sql: str, detail: str) -> None:
    count = _count(db, sql)
    results.append(CheckResult(name=name, status="PASS" if count == 0 else "FAIL", detail=detail if count else "", evidence={"count": count}))


def run() -> dict[str, Any]:
    from app.core.database import SessionLocal

    db = SessionLocal()
    results: list[CheckResult] = []
    try:
        structural_checks = [
            ("sale_items_have_sales", """
                select count(*) as count
                from sale_items si
                left join sales s on s.id = si.sale_id and s.company_id = si.company_id
                where s.id is null
            """, "Existem itens de venda sem venda correspondente."),
            ("sale_items_have_catalog_items", """
                select count(*) as count
                from sale_items si
                left join catalog_items ci on ci.id = si.item_id and ci.company_id = si.company_id
                where ci.id is null
            """, "Existem itens de venda apontando para item de catálogo inexistente ou de outra empresa."),
            ("sale_payment_plans_have_sales", """
                select count(*) as count
                from sale_payment_plans spp
                left join sales s on s.id = spp.sale_id and s.company_id = spp.company_id
                where s.id is null
            """, "Existem planos de pagamento sem venda correspondente."),
            ("fiscal_rules_have_valid_dependencies", """
                select count(*) as count
                from catalog_item_fiscal_rules r
                left join catalog_items ci on ci.id = r.catalog_item_id and ci.company_id = r.company_id
                left join fiscal_classifications fc on fc.id = r.fiscal_classification_id and fc.company_id = r.company_id
                left join operation_natures op on op.id = r.operation_nature_id and op.company_id = r.company_id
                where ci.id is null or fc.id is null or op.id is null
            """, "Existem regras fiscais item+natureza+classificação com dependência inválida."),
            ("stock_movements_have_item_and_location", """
                select count(*) as count
                from stock_movements sm
                left join catalog_items ci on ci.id = sm.item_id and ci.company_id = sm.company_id
                left join stock_locations sl on sl.id = sm.location_id and sl.company_id = sm.company_id
                where ci.id is null or sl.id is null
            """, "Existem movimentos de estoque sem item ou local válido."),
            ("sale_stock_links_are_consistent", """
                select count(*) as count
                from sale_stock_links l
                left join sales s on s.id = l.sale_id and s.company_id = l.company_id
                left join sale_items si on si.id = l.sale_item_id and si.sale_id = l.sale_id and si.company_id = l.company_id
                left join stock_movements sm on sm.id = l.stock_movement_id and sm.company_id = l.company_id
                where s.id is null or si.id is null or sm.id is null
            """, "Existem vínculos venda-estoque sem venda, item ou movimento válido."),
            ("stock_balances_have_item_and_location", """
                select count(*) as count
                from stock_balances sb
                left join catalog_items ci on ci.id = sb.item_id and ci.company_id = sb.company_id
                left join stock_locations sl on sl.id = sb.location_id and sl.company_id = sb.company_id
                where ci.id is null or sl.id is null
            """, "Existem saldos de estoque sem item/local válido."),
            ("financial_titles_have_participants", """
                select count(*) as count
                from financial_titles ft
                left join participants p on p.id = ft.participant_id and p.company_id = ft.company_id
                where ft.deleted_at is null and p.id is null
            """, "Existem títulos financeiros sem participante válido."),
            ("financial_titles_sale_references_are_valid", """
                select count(*) as count
                from financial_titles ft
                left join sales s on s.id = ft.sale_id and s.company_id = ft.company_id
                where ft.sale_id is not null and s.id is null
            """, "Existem títulos financeiros apontando para venda inválida."),
            ("sale_financial_links_are_consistent", """
                select count(*) as count
                from sale_financial_links l
                left join sales s on s.id = l.sale_id and s.company_id = l.company_id
                left join financial_titles ft on ft.id = l.financial_title_id and ft.company_id = l.company_id
                left join sale_payment_plans spp on spp.id = l.sale_payment_plan_id and spp.company_id = l.company_id
                where s.id is null or ft.id is null or (l.sale_payment_plan_id is not null and spp.id is null)
            """, "Existem vínculos venda-financeiro com venda, título ou plano inválido."),
            ("settlements_have_title_and_account", """
                select count(*) as count
                from settlements st
                left join financial_titles ft on ft.id = st.financial_title_id and ft.company_id = st.company_id
                left join financial_accounts fa on fa.id = st.financial_account_id and fa.company_id = st.company_id
                where ft.id is null or fa.id is null
            """, "Existem baixas sem título ou conta financeira válida."),
            ("financial_movements_have_account", """
                select count(*) as count
                from financial_movements fm
                left join financial_accounts fa on fa.id = fm.financial_account_id and fa.company_id = fm.company_id
                where fa.id is null
            """, "Existem movimentos financeiros sem conta financeira válida."),
            ("financial_movements_have_valid_settlement_when_informed", """
                select count(*) as count
                from financial_movements fm
                left join settlements st on st.id = fm.settlement_id and st.company_id = fm.company_id
                where fm.settlement_id is not null and st.id is null
            """, "Existem movimentos financeiros apontando para baixa inválida."),
            ("account_balances_have_account", """
                select count(*) as count
                from financial_account_balances b
                left join financial_accounts fa on fa.id = b.financial_account_id and fa.company_id = b.company_id
                where fa.id is null
            """, "Existem saldos financeiros sem conta financeira válida."),
            ("statement_lines_have_account_and_import", """
                select count(*) as count
                from bank_statement_lines bl
                left join financial_accounts fa on fa.id = bl.financial_account_id and fa.company_id = bl.company_id
                left join bank_statement_imports bi on bi.id = bl.statement_import_id and bi.company_id = bl.company_id
                where fa.id is null or (bl.statement_import_id is not null and bi.id is null)
            """, "Existem linhas de extrato sem conta/importação válida."),
            ("reconciliation_matches_are_consistent", """
                select count(*) as count
                from reconciliation_matches rm
                left join bank_statement_lines bl on bl.id = rm.statement_line_id and bl.company_id = rm.company_id
                left join financial_movements fm on fm.id = rm.financial_movement_id and fm.company_id = rm.company_id
                where bl.id is null or fm.id is null or bl.financial_account_id <> rm.financial_account_id or fm.financial_account_id <> rm.financial_account_id
            """, "Existem matches sem linha/movimento válido ou com conta financeira divergente."),
            ("received_titles_have_zero_open_amount", """
                select count(*) as count
                from financial_titles
                where deleted_at is null and status = 'received' and open_amount <> 0
            """, "Existem títulos recebidos com saldo aberto diferente de zero."),
            ("open_titles_have_positive_open_amount", """
                select count(*) as count
                from financial_titles
                where deleted_at is null and status in ('open','overdue','partially_received') and open_amount <= 0
            """, "Existem títulos em aberto/parcial/vencidos sem saldo positivo."),
            ("matched_movements_have_confirmed_match", """
                select count(*) as count
                from financial_movements fm
                where fm.reconciliation_status in ('matched','divergent')
                  and not exists (
                    select 1 from reconciliation_matches rm
                    where rm.financial_movement_id = fm.id
                      and rm.company_id = fm.company_id
                      and rm.status in ('confirmed','confirmed_with_difference')
                  )
            """, "Existem movimentos marcados como conciliados/divergentes sem match confirmado."),
            ("matched_statement_lines_have_confirmed_match", """
                select count(*) as count
                from bank_statement_lines bl
                where bl.status in ('matched','divergent')
                  and not exists (
                    select 1 from reconciliation_matches rm
                    where rm.statement_line_id = bl.id
                      and rm.company_id = bl.company_id
                      and rm.status in ('confirmed','confirmed_with_difference')
                  )
            """, "Existem linhas de extrato marcadas como conciliadas/divergentes sem match confirmado."),
        ]

        for name, sql, detail in structural_checks:
            _check_zero(results, db, name, sql, detail)

        # Recalcula saldo financeiro materializado por conta: abertura + movimentos postados.
        balance_rows = _rows(db, """
            select
              fa.company_id,
              fa.id as financial_account_id,
              coalesce(fa.opening_balance_amount, 0) + coalesce(sum(case when fm.status = 'posted' and fm.direction = 'inflow' then fm.amount when fm.status = 'posted' and fm.direction = 'outflow' then -fm.amount else 0 end), 0) as expected_balance,
              coalesce(b.current_balance_amount, fa.opening_balance_amount, 0) as actual_balance
            from financial_accounts fa
            left join financial_movements fm on fm.financial_account_id = fa.id and fm.company_id = fa.company_id
            left join financial_account_balances b on b.financial_account_id = fa.id and b.company_id = fa.company_id
            where fa.deleted_at is null
            group by fa.company_id, fa.id, fa.opening_balance_amount, b.current_balance_amount
        """)
        mismatches = [dict(row) for row in balance_rows if _money(row["expected_balance"]) != _money(row["actual_balance"])]
        results.append(CheckResult(
            name="financial_account_balances_match_movements",
            status="PASS" if not mismatches else "FAIL",
            detail="Saldo materializado da conta financeira difere de abertura + movimentos postados." if mismatches else "",
            evidence={"mismatch_count": len(mismatches), "sample": mismatches[:10]},
        ))

        # Recalcula saldo de estoque materializado por item/local: entradas - saídas de movimentos postados.
        stock_rows = _rows(db, """
            select
              sb.company_id,
              sb.item_id,
              sb.location_id,
              coalesce(sum(case when sm.status = 'posted' and sm.direction = 'in' then sm.quantity when sm.status = 'posted' and sm.direction = 'out' then -sm.quantity else 0 end), 0) as expected_quantity,
              sb.quantity as actual_quantity
            from stock_balances sb
            left join stock_movements sm on sm.company_id = sb.company_id and sm.item_id = sb.item_id and sm.location_id = sb.location_id
            group by sb.company_id, sb.item_id, sb.location_id, sb.quantity
        """)
        stock_mismatches = [dict(row) for row in stock_rows if _q4(row["expected_quantity"]) != _q4(row["actual_quantity"])]
        results.append(CheckResult(
            name="stock_balances_match_movements",
            status="PASS" if not stock_mismatches else "FAIL",
            detail="Saldo materializado de estoque difere de entradas - saídas postadas." if stock_mismatches else "",
            evidence={"mismatch_count": len(stock_mismatches), "sample": stock_mismatches[:10]},
        ))

        failed = [result for result in results if result.status != "PASS"]
        return {
            "status": "PASS" if not failed else "FAIL",
            "summary": {"total": len(results), "passed": len(results) - len(failed), "failed": len(failed)},
            "checks": [result.__dict__ for result in results],
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="operational_lifecycle_integrity_report.json")
    args = parser.parse_args()
    try:
        report = run()
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
