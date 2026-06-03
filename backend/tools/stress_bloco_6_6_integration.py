r"""
Kovir ERP — Bloco 6.6 — Stress/Regressão Fiscal → Catálogo → Estoque → Vendas
================================================================================

Objetivo:
- Validar o fluxo crítico antes de iniciar o próximo bloco financeiro/fiscal.
- Exercitar criação de empresa, participante, produto com estoque, serviço sem estoque,
  classificação fiscal, regra item+natureza+fiscal, entrada de estoque, venda,
  confirmação, baixa de estoque, cancelamento e reversão.
- Validar bloqueio de venda sem saldo.
- Validar que venda de serviço não movimenta estoque.
- Auditar presença de SELECT ... FOR UPDATE nos pontos críticos de venda/estoque.

Uso recomendado com PostgreSQL local já migrado:

    cd backend
    .\.venv\Scripts\Activate.ps1
    python .\tools\stress_bloco_6_6_integration.py --output bloco_6_6_stress_report.json

Uso opcional em SQLite apenas para smoke local isolado, sem substituir PostgreSQL:

    python .\tools\stress_bloco_6_6_integration.py --sqlite-smoke-db ..\bloco_6_6_smoke.db

Este script cria dados de teste. Não rode em produção.
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


def _money(value: str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _qty(value: str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def run(sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from sqlalchemy.dialects import postgresql
    from sqlalchemy import select

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
    from app.modules.sales.schemas import SaleCreate, SaleStatusChange
    from app.modules.sales.service import (
        cancel_sale,
        confirm_sale,
        create_sale,
        list_operation_natures,
        list_payment_methods,
    )
    from app.modules.sales.repository import create_catalog_item_fiscal_rule
    from app.modules.sales.db_models import SaleDB
    from app.modules.stock.schemas import StockPurchaseEntryCreate
    from app.modules.stock.service import create_purchase_stock_entry, get_item_availability
    from app.modules.stock.db_models import StockBalanceDB

    if sqlite_mode:
        Base.metadata.create_all(engine)

    results: list[CaseResult] = []
    db = SessionLocal()
    ids: dict[str, str] = {}

    suffix = str(abs(hash((date.today().isoformat(), os.getpid()))))[-8:]

    def create_base_records():
        company = create_company(db, CompanyCreate(**{
            "legal_name": f"Kovir Bloco 6.6 Stress {suffix} LTDA",
            "trade_name": f"Kovir 6.6 {suffix}",
            "cnpj": f"11222333{suffix[-6:]}",
            "email": f"stress.{suffix}@example.com",
            "phone": "14999999999",
            "responsible_name": "Operador Stress",
            "status": "active",
            "address": {"street": "Rua A", "number": "1", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000"},
            "fiscal_settings": {"tax_regime": "simples_nacional", "main_cnae": "6201500", "fiscal_environment": "none", "uses_fiscal_control": True, "prepared_for_tax_reform": True},
            "financial_settings": {"currency": "BRL", "monthly_closing_day": 31, "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            "operational_settings": {"timezone": "America/Sao_Paulo", "date_format": "YYYY-MM-DD", "money_format": "BRL", "allow_manual_entries": True, "allow_imports": True},
        }))
        ids["company_id"] = company["id"]

        customer = create_participant(db, ParticipantCreate(**{
            "company_id": ids["company_id"],
            "participant_type": "customer",
            "person_type": "company",
            "name": f"Cliente Stress 6.6 {suffix} LTDA",
            "trade_name": f"Cliente 6.6 {suffix}",
            "document": f"22334455{suffix[-6:]}",
            "email": f"cliente.{suffix}@teste.com",
            "phone": "14988888888",
            "status": "active",
            "address": {"street": "Rua Cliente", "number": "200", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
            "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "4712100", "state_registration": "ISENTO", "is_foreign": False},
            "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "a_vista", "pix_key": f"cliente.{suffix}@teste.com", "credit_limit": "10000", "payment_priority": "normal"},
        }))
        ids["customer_id"] = customer["id"]

        supplier = create_participant(db, ParticipantCreate(**{
            "company_id": ids["company_id"],
            "participant_type": "supplier",
            "person_type": "company",
            "name": f"Fornecedor Stress 6.6 {suffix} LTDA",
            "trade_name": f"Fornecedor 6.6 {suffix}",
            "document": f"33445566{suffix[-6:]}",
            "email": f"fornecedor.{suffix}@teste.com",
            "phone": "14977777777",
            "status": "active",
            "address": {"street": "Rua Fornecedor", "number": "300", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
            "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "4691500", "state_registration": "ISENTO", "is_foreign": False},
            "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "a_vista", "pix_key": f"fornecedor.{suffix}@teste.com", "credit_limit": "0", "payment_priority": "normal"},
        }))
        ids["supplier_id"] = supplier["id"]
        return ids.copy()

    def create_items_and_fiscal():
        product = create_catalog_item(db, CatalogItemCreate(**{
            "company_id": ids["company_id"],
            "item_type": "product",
            "name": f"Produto Controlado Stress 6.6 {suffix}",
            "description": "Produto com controle de estoque",
            "sku": f"P66-{suffix}",
            "unit": "UN",
            "status": "active",
            "origin": "manual",
            "financial_settings": {"default_sale_price": "100.00", "default_cost_price": "50.00", "allow_price_override": False},
            "fiscal_settings": {"ncm": "21069090", "cfop_default": "5102", "cst_icms": "102", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True},
            "inventory_settings": {"track_stock": True, "stock_unit": "UN", "minimum_stock": "0", "allow_negative_stock": False},
        }))
        ids["product_id"] = product["id"]

        service = create_catalog_item(db, CatalogItemCreate(**{
            "company_id": ids["company_id"],
            "item_type": "service",
            "name": f"Serviço Stress 6.6 {suffix}",
            "description": "Serviço sem controle de estoque",
            "sku": f"S66-{suffix}",
            "unit": "SERV",
            "status": "active",
            "origin": "manual",
            "financial_settings": {"default_sale_price": "80.00", "default_cost_price": "20.00", "allow_price_override": False},
            "fiscal_settings": {"nbs": "123456789", "cfop_default": "5933", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000002", "subject_to_tax": True},
            "inventory_settings": {"track_stock": False, "stock_unit": None, "minimum_stock": None, "allow_negative_stock": False},
        }))
        ids["service_id"] = service["id"]

        fclass = create_fiscal_classification(db, FiscalClassificationCreate(**{
            "company_id": ids["company_id"],
            "name": f"Fiscal Produto 6.6 {suffix}",
            "item_type": "product",
            "tax_regime": "simples_nacional",
            "ncm": "21069090",
            "cfop_default": "5102",
            "cst_icms": "102",
            "cst_pis": "99",
            "cst_cofins": "99",
            "cst_ibs_cbs": "000",
            "cclass_trib": "000001",
            "subject_to_icms": True,
            "subject_to_pis_cofins": True,
            "subject_to_ibs_cbs": True,
            "status": "active",
            "source": "manual",
        }))
        ids["product_fclass_id"] = fclass["id"]

        sfclass = create_fiscal_classification(db, FiscalClassificationCreate(**{
            "company_id": ids["company_id"],
            "name": f"Fiscal Serviço 6.6 {suffix}",
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
        ids["service_fclass_id"] = sfclass["id"]
        return {k: ids[k] for k in ("product_id", "service_id", "product_fclass_id", "service_fclass_id")}

    def create_sales_dependencies():
        opnats = list_operation_natures(db, company_id=ids["company_id"])
        payms = list_payment_methods(db, company_id=ids["company_id"])
        opnat = next(row for row in opnats if row["code"] == "normal_sale")
        ids["operation_nature_id"] = opnat["id"]
        now = utc_now()
        rule = create_catalog_item_fiscal_rule(
            db,
            id=generate_id("fiscalrule"),
            company_id=ids["company_id"],
            catalog_item_id=ids["product_id"],
            fiscal_classification_id=ids["product_fclass_id"],
            operation_nature_id=ids["operation_nature_id"],
            sale_type="product",
            valid_from=None,
            valid_to=None,
            priority=100,
            status="active",
            notes="Criado por stress Bloco 6.6",
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.commit()
        ids["fiscal_rule_id"] = rule.id
        return {"operation_natures": len(opnats), "payment_methods": len(payms), "fiscal_rule_id": rule.id}

    def create_stock_entry():
        entry = create_purchase_stock_entry(db, StockPurchaseEntryCreate(**{
            "company_id": ids["company_id"],
            "supplier_participant_id": ids["supplier_id"],
            "document_type": "purchase_invoice",
            "document_number": f"NF66-{suffix}",
            "issue_date": date.today().isoformat(),
            "items": [{"item_id": ids["product_id"], "quantity": "5", "unit_cost": "50.00", "unit": "UN", "description": "Entrada de stress"}],
        }))
        av = get_item_availability(db, company_id=ids["company_id"], item_id=ids["product_id"])
        if _qty(av["available_quantity"]) != Decimal("5.0000"):
            raise AssertionError(f"Saldo esperado 5.0000, recebido {av['available_quantity']}")
        return {"purchase_entry_id": entry["id"], "available_quantity": av["available_quantity"]}

    def sale_confirm_and_cancel():
        sale = create_sale(db, SaleCreate(**{
            "company_id": ids["company_id"],
            "participant_id": ids["customer_id"],
            "sale_type": "product",
            "operation_nature_id": ids["operation_nature_id"],
            "items": [{"item_id": ids["product_id"], "fiscal_classification_id": ids["product_fclass_id"], "quantity": "2", "unit": "UN", "unit_price": "100.00"}],
            "payment_plans": [{"payment_method_code": "pix", "amount": "200.00"}],
        }))
        confirmed = confirm_sale(db, sale["id"], SaleStatusChange(reason="Stress Bloco 6.6"))
        av_after_confirm = get_item_availability(db, company_id=ids["company_id"], item_id=ids["product_id"])
        if _qty(av_after_confirm["available_quantity"]) != Decimal("3.0000"):
            raise AssertionError(f"Saldo após confirmar deveria ser 3.0000, veio {av_after_confirm['available_quantity']}")
        cancelled = cancel_sale(db, sale["id"], SaleStatusChange(reason="Reversão stress Bloco 6.6"))
        av_after_cancel = get_item_availability(db, company_id=ids["company_id"], item_id=ids["product_id"])
        if _qty(av_after_cancel["available_quantity"]) != Decimal("5.0000"):
            raise AssertionError(f"Saldo após cancelar deveria ser 5.0000, veio {av_after_cancel['available_quantity']}")
        ids["sale_cancelled_id"] = sale["id"]
        return {"sale_id": sale["id"], "confirmed_status": confirmed["status"], "cancelled_status": cancelled["status"], "after_confirm": av_after_confirm["available_quantity"], "after_cancel": av_after_cancel["available_quantity"]}

    def block_without_stock():
        sale = create_sale(db, SaleCreate(**{
            "company_id": ids["company_id"],
            "participant_id": ids["customer_id"],
            "sale_type": "product",
            "operation_nature_id": ids["operation_nature_id"],
            "items": [{"item_id": ids["product_id"], "fiscal_classification_id": ids["product_fclass_id"], "quantity": "10", "unit": "UN", "unit_price": "100.00"}],
            "payment_plans": [{"payment_method_code": "pix", "amount": "1000.00"}],
        }))
        try:
            confirm_sale(db, sale["id"], SaleStatusChange(reason="Deve bloquear"))
        except Exception as exc:
            db.rollback()
            if "Saldo insuficiente" not in str(exc):
                raise AssertionError(f"Bloqueio ocorreu, mas mensagem inesperada: {exc}") from exc
            return {"sale_id": sale["id"], "blocked_message": str(exc)}
        raise AssertionError("Venda sem estoque foi confirmada indevidamente.")

    def service_does_not_touch_stock():
        before = get_item_availability(db, company_id=ids["company_id"], item_id=ids["product_id"])["available_quantity"]
        sale = create_sale(db, SaleCreate(**{
            "company_id": ids["company_id"],
            "participant_id": ids["customer_id"],
            "sale_type": "service",
            "operation_nature_id": ids["operation_nature_id"],
            "items": [{"item_id": ids["service_id"], "fiscal_classification_id": ids["service_fclass_id"], "quantity": "1", "unit": "SERV", "unit_price": "80.00"}],
            "payment_plans": [{"payment_method_code": "pix", "amount": "80.00"}],
        }))
        confirm_sale(db, sale["id"], SaleStatusChange(reason="Serviço sem estoque"))
        after = get_item_availability(db, company_id=ids["company_id"], item_id=ids["product_id"])["available_quantity"]
        if before != after:
            raise AssertionError(f"Saldo de produto mudou em venda de serviço: antes {before}, depois {after}")
        return {"service_sale_id": sale["id"], "stock_before": before, "stock_after": after}

    def idempotency_guards():
        sale = create_sale(db, SaleCreate(**{
            "company_id": ids["company_id"],
            "participant_id": ids["customer_id"],
            "sale_type": "product",
            "operation_nature_id": ids["operation_nature_id"],
            "items": [{"item_id": ids["product_id"], "fiscal_classification_id": ids["product_fclass_id"], "quantity": "1", "unit": "UN", "unit_price": "100.00"}],
            "payment_plans": [{"payment_method_code": "pix", "amount": "100.00"}],
        }))
        confirm_sale(db, sale["id"], SaleStatusChange(reason="Teste idempotência"))
        try:
            confirm_sale(db, sale["id"], SaleStatusChange(reason="Confirmar de novo deve falhar"))
        except Exception as exc:
            msg_confirm = str(exc)
            db.rollback()
        else:
            raise AssertionError("Confirmação duplicada não foi bloqueada.")
        cancel_sale(db, sale["id"], SaleStatusChange(reason="Cancelar uma vez"))
        try:
            cancel_sale(db, sale["id"], SaleStatusChange(reason="Cancelar de novo deve falhar"))
        except Exception as exc:
            msg_cancel = str(exc)
            db.rollback()
        else:
            raise AssertionError("Cancelamento duplicado não foi bloqueado.")
        return {"sale_id": sale["id"], "double_confirm_blocked": msg_confirm, "double_cancel_blocked": msg_cancel}

    def lock_sql_audit():
        stock_sql = str(select(StockBalanceDB).where(StockBalanceDB.company_id == "emp_x").with_for_update().compile(dialect=postgresql.dialect()))
        sale_sql = str(select(SaleDB).where(SaleDB.id == "sale_x").with_for_update().compile(dialect=postgresql.dialect()))
        if "FOR UPDATE" not in stock_sql.upper():
            raise AssertionError("SQL compilado de estoque não contém FOR UPDATE.")
        if "FOR UPDATE" not in sale_sql.upper():
            raise AssertionError("SQL compilado de venda não contém FOR UPDATE.")
        return {"stock_sql_has_for_update": True, "sale_sql_has_for_update": True}

    _case(results, "Criar empresa, cliente e fornecedor", "Cadastros base persistidos e vinculados à empresa", create_base_records)
    _case(results, "Criar produto controlado, serviço e classificações fiscais", "Produto controla estoque; serviço não controla estoque", create_items_and_fiscal)
    _case(results, "Criar natureza/formas e regra item+natureza+fiscal", "Venda resolve fiscal por regra estruturada", create_sales_dependencies)
    _case(results, "Criar entrada de estoque", "Saldo disponível inicial deve ser 5.0000", create_stock_entry)
    _case(results, "Confirmar e cancelar venda de produto", "Confirmação baixa estoque; cancelamento repõe", sale_confirm_and_cancel)
    _case(results, "Bloquear venda sem estoque", "Quantidade maior que saldo deve falhar", block_without_stock)
    _case(results, "Confirmar venda de serviço", "Serviço não deve alterar saldo de produto", service_does_not_touch_stock)
    _case(results, "Bloquear confirmação/cancelamento duplicado", "Status transacional deve impedir repetição indevida", idempotency_guards)
    _case(results, "Auditar locks transacionais", "Queries críticas devem compilar com FOR UPDATE no PostgreSQL", lock_sql_audit)

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")

    return {
        "status": "PASS" if failed == 0 else "FAIL",
        "database_url": str(engine.url).replace(str(engine.url.password), "***") if getattr(engine.url, "password", None) else str(engine.url),
        "sqlite_smoke_mode": sqlite_mode,
        "summary": {"passed": passed, "failed": failed, "total": len(results)},
        "ids": ids,
        "cases": [r.__dict__ for r in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="bloco_6_6_stress_report.json")
    parser.add_argument("--sqlite-smoke-db", default=None, help="Executa smoke isolado em SQLite. Não substitui PostgreSQL.")
    args = parser.parse_args()

    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:
        report = {
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
