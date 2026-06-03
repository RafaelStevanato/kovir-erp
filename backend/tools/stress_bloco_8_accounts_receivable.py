r"""
Kovir ERP — Bloco 8 — Stress/Regressão Contas a Receber
===========================================================

Valida:
- criação manual de título a receber;
- geração automática por venda confirmada;
- idempotência da geração por sale_payment_plan;
- cancelamento da venda cancelando títulos abertos;
- resumo por empresa;
- histórico e auditoria básica.

Uso PostgreSQL local migrado:
    cd backend
    python .\tools\stress_bloco_8_accounts_receivable.py --output bloco_8_accounts_receivable_stress_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_bloco_8_accounts_receivable.py --sqlite-smoke-db ..\bloco_8_ar_smoke.db
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
    from app.shared.datetime import utc_now
    from app.shared.ids import generate_id
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.catalog.schemas import CatalogItemCreate
    from app.modules.catalog.service import create_catalog_item
    from app.modules.fiscal_classification.schemas import FiscalClassificationCreate
    from app.modules.fiscal_classification.service import create_fiscal_classification
    from app.modules.sales.repository import create_catalog_item_fiscal_rule
    from app.modules.sales.schemas import SaleCreate, SaleStatusChange
    from app.modules.sales.service import cancel_sale, confirm_sale, create_sale, list_operation_natures, list_payment_methods
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate
    from app.modules.accounts_receivable.service import create_manual_receivable, generate_receivables_from_sale_id, get_receivable_audit_events, get_receivable_history, get_receivables_summary, list_receivables

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, str] = {}
    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]

    try:
        def create_base():
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir AR Stress {suffix} LTDA",
                "trade_name": f"Kovir AR {suffix}",
                "cnpj": f"778899{suffix[-8:]}",
                "email": f"ar.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador AR",
                "status": "active",
                "address": {"street": "Rua AR", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            ids["company_id"] = company["id"]
            customer = create_participant(db, ParticipantCreate(**{
                "company_id": company["id"],
                "participant_type": "customer",
                "person_type": "company",
                "name": f"Cliente AR {suffix} LTDA",
                "document": f"998877{suffix[-8:]}",
                "email": f"cliente.ar.{suffix}@teste.com",
                "phone": "14988888888",
                "status": "active",
                "address": {"street": "Rua Cliente", "number": "200", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "a_vista", "credit_limit": "10000"},
            }))
            ids["customer_id"] = customer["id"]
            return ids.copy()

        _case(results, "create_company_and_customer", "Empresa e cliente ativos devem existir para título a receber.", create_base)

        def manual_receivable():
            title = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": ids["company_id"],
                "participant_id": ids["customer_id"],
                "title_type": "manual",
                "source_type": "manual",
                "due_date": date.today().isoformat(),
                "gross_amount": "150.00",
                "document_reference": f"MAN-{suffix}",
                "notes": "Título manual de stress AR",
            }))
            if title["status"] not in {"open", "overdue"}:
                raise AssertionError(f"Status inesperado: {title['status']}")
            ids["manual_title_id"] = title["id"]
            return {"title_id": title["id"], "open_amount": title["open_amount"], "status": title["status"]}

        _case(results, "manual_receivable", "Título manual deve nascer aberto e com saldo em aberto.", manual_receivable)

        def create_sale_dependencies():
            service = create_catalog_item(db, CatalogItemCreate(**{
                "company_id": ids["company_id"],
                "item_type": "service",
                "name": f"Serviço AR {suffix}",
                "sku": f"SAR-{suffix}",
                "unit": "SERV",
                "status": "active",
                "origin": "manual",
                "financial_settings": {"default_sale_price": "220.00", "default_cost_price": "40.00", "allow_price_override": False},
                "fiscal_settings": {"nbs": "123456789", "cfop_default": "5933", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000002", "subject_to_tax": True},
                "inventory_settings": {"track_stock": False, "stock_unit": None, "minimum_stock": None, "allow_negative_stock": False},
            }))
            fclass = create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": ids["company_id"],
                "name": f"Fiscal Serviço AR {suffix}",
                "item_type": "service",
                "tax_regime": "simples_nacional",
                "nbs": "123456789",
                "cfop_default": "5933",
                "cst_pis": "99",
                "cst_cofins": "99",
                "cst_ibs_cbs": "000",
                "cclass_trib": "000002",
                "subject_to_iss": True,
                "subject_to_pis_cofins": True,
                "subject_to_ibs_cbs": True,
                "status": "active",
                "source": "manual",
            }))
            opnats = list_operation_natures(db, company_id=ids["company_id"])
            list_payment_methods(db, company_id=ids["company_id"])
            opnat = next(row for row in opnats if row["code"] == "normal_sale")
            now = utc_now()
            rule = create_catalog_item_fiscal_rule(db, id=generate_id("fiscalrule"), company_id=ids["company_id"], catalog_item_id=service["id"], fiscal_classification_id=fclass["id"], operation_nature_id=opnat["id"], sale_type="service", valid_from=None, valid_to=None, priority=100, status="active", notes="Stress AR", created_at=now, updated_at=now, deleted_at=None)
            db.commit()
            ids.update({"service_id": service["id"], "fclass_id": fclass["id"], "operation_nature_id": opnat["id"], "fiscal_rule_id": rule.id})
            return {"service_id": service["id"], "operation_nature_id": opnat["id"], "fiscal_rule_id": rule.id}

        _case(results, "sale_dependencies", "Venda precisa de serviço, fiscal, natureza e forma de pagamento.", create_sale_dependencies)

        def sale_generates_receivable():
            sale = create_sale(db, SaleCreate(**{
                "company_id": ids["company_id"],
                "participant_id": ids["customer_id"],
                "sale_type": "service",
                "operation_nature_id": ids["operation_nature_id"],
                "items": [{"item_id": ids["service_id"], "fiscal_classification_id": ids["fclass_id"], "quantity": "1", "unit": "SERV", "unit_price": "220.00"}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "220.00", "due_date": date.today().isoformat()}],
            }))
            ids["sale_id"] = sale["id"]
            confirm_sale(db, sale["id"], SaleStatusChange(reason="Stress AR confirma venda"))
            titles = list_receivables(db, company_id=ids["company_id"], sale_id=sale["id"])
            if len(titles) != 1:
                raise AssertionError(f"Esperado 1 título da venda, recebido {len(titles)}")
            ids["sale_title_id"] = titles[0]["id"]
            if Decimal(titles[0]["open_amount"]) != Decimal("220.00"):
                raise AssertionError(f"Valor aberto inesperado: {titles[0]['open_amount']}")
            return {"sale_id": sale["id"], "title_id": titles[0]["id"], "open_amount": titles[0]["open_amount"]}

        _case(results, "sale_generates_receivable", "Venda confirmada deve gerar título a receber por plano de pagamento.", sale_generates_receivable)

        def idempotent_generation():
            titles = generate_receivables_from_sale_id(db, ids["sale_id"], reason="Idempotência stress AR")
            count = len(list_receivables(db, company_id=ids["company_id"], sale_id=ids["sale_id"]))
            if count != 1:
                raise AssertionError(f"Geração duplicou título: {count}")
            return {"returned": len(titles), "persisted_count": count}

        _case(results, "idempotent_generation", "Gerar novamente por venda não deve duplicar título.", idempotent_generation)

        def cancel_sale_cancels_receivable():
            cancel_sale(db, ids["sale_id"], SaleStatusChange(reason="Stress AR cancela venda"))
            titles = list_receivables(db, company_id=ids["company_id"], sale_id=ids["sale_id"])
            if titles[0]["status"] != "cancelled" or titles[0]["open_amount"] != "0.00":
                raise AssertionError(f"Título não cancelado corretamente: {titles[0]}")
            return {"title_id": titles[0]["id"], "status": titles[0]["status"], "open_amount": titles[0]["open_amount"]}

        _case(results, "cancel_sale_cancels_receivable", "Cancelamento da venda deve cancelar título aberto e zerar saldo em aberto.", cancel_sale_cancels_receivable)

        def summary_history_audit():
            summary = get_receivables_summary(db, company_id=ids["company_id"])
            history = get_receivable_history(db, ids["manual_title_id"])
            audit = get_receivable_audit_events(db, ids["manual_title_id"])
            if not history or not audit:
                raise AssertionError("Histórico/auditoria do título manual não encontrados.")
            return {"open_amount": summary["open_amount"], "history_count": len(history), "audit_count": len(audit)}

        _case(results, "summary_history_audit", "Resumo, histórico e auditoria devem existir.", summary_history_audit)

        passed = sum(1 for result in results if result.status == "PASS")
        failed = sum(1 for result in results if result.status == "FAIL")
        return {"status": "PASS" if failed == 0 else "FAIL", "database_url": str(engine.url), "sqlite_smoke_mode": sqlite_mode, "summary": {"passed": passed, "failed": failed, "total": len(results)}, "ids": ids, "cases": [result.__dict__ for result in results]}
    except Exception as exc:
        return {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(), "summary": {"passed": sum(1 for r in results if r.status == "PASS"), "failed": sum(1 for r in results if r.status == "FAIL"), "total": len(results)}, "cases": [result.__dict__ for result in results]}
    finally:
        db.close()
        try:
            engine.dispose()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None)
    parser.add_argument("--output", default="bloco_8_accounts_receivable_stress_report.json")
    args = parser.parse_args()
    report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    output = Path(args.output)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
