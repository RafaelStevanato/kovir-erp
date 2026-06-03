r"""
Kovir ERP — Super Stress Test de Integração
============================================

Cobre, em uma bateria única:
- Company -> Participants -> Catalog -> Fiscal -> Stock -> Sales -> Financial Masters -> Accounts Receivable;
- casos atípicos de empresa cruzada, cliente bloqueado, preço adulterado, plano de pagamento divergente;
- baixa/reversão de estoque, bloqueio por saldo insuficiente, venda de serviço sem estoque;
- geração idempotente de Contas a Receber a partir de sale_payment_plans;
- rollback transacional quando cancelamento de venda encontra título já recebido;
- integridade estrutural básica contra órfãos nas tabelas conectadas.

Uso com PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_super_integration.py --output super_stress_integration_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_super_integration.py --sqlite-smoke-db ..\super_stress_smoke.db --output super_stress_integration_report.json
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
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _q(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_error(func: Callable[[], Any], contains: str | None = None) -> str:
    try:
        func()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if contains and contains.lower() not in message.lower():
            raise AssertionError(f"Erro esperado deveria conter {contains!r}, mas foi: {message}") from exc
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
    from app.shared.datetime import utc_now
    from app.shared.ids import generate_id
    from app.shared.audit_repository import list_audit_events_for_entity

    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant
    from app.modules.catalog.schemas import CatalogItemCreate
    from app.modules.catalog.service import create_catalog_item
    from app.modules.fiscal_classification.schemas import FiscalClassificationCreate
    from app.modules.fiscal_classification.service import create_fiscal_classification
    from app.modules.sales.repository import create_catalog_item_fiscal_rule, get_payment_method_by_code
    from app.modules.sales.schemas import SaleCreate, SaleItemCreate, SalePaymentPlanCreate, SaleStatusChange
    from app.modules.sales.service import (
        cancel_sale,
        confirm_sale,
        create_sale,
        get_sales_diagnostics,
        list_operation_natures,
        list_payment_methods,
        list_sale_item_readiness,
    )
    from app.modules.stock.schemas import StockPurchaseEntryCreate
    from app.modules.stock.service import create_purchase_stock_entry, get_item_availability, list_stock_lots, list_stock_movements
    from app.modules.financial.service import create_default_financial_masters, get_financial_diagnostics
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate, FinancialTitleStatusChange, FinancialTitleUpdate
    from app.modules.accounts_receivable.service import (
        cancel_receivable,
        create_manual_receivable,
        generate_receivables_from_sale_id,
        get_accounts_receivable_diagnostics,
        get_receivable_history,
        get_receivables_summary,
        list_receivables,
        update_receivable,
    )
    from app.modules.accounts_receivable.repository import get_title, list_titles_by_sale, update_title_fields
    from app.modules.stock import repository as stock_repository
    from app.modules.sales import repository as sales_repository

    if sqlite_mode:
        Base.metadata.create_all(engine)

    db = SessionLocal()
    results: list[CaseResult] = []
    ctx: dict[str, Any] = {"ids": {}}
    suffix = str(abs(hash((date.today().isoformat(), os.getpid(), id(db)))))[-8:]

    def remember(key: str, value: Any) -> Any:
        ctx["ids"][key] = value
        return value

    try:
        def foundational_setup() -> dict[str, Any]:
            company_a = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Super Stress A {suffix} LTDA",
                "trade_name": f"Kovir Stress A {suffix}",
                "cnpj": f"111222{suffix}",
                "email": f"stress.a.{suffix}@example.com",
                "phone": "14999999999",
                "responsible_name": "Operador Stress",
                "status": "active",
                "address": {"street": "Rua A", "number": "100", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            company_b = create_company(db, CompanyCreate(**{
                "legal_name": f"Kovir Super Stress B {suffix} LTDA",
                "trade_name": f"Kovir Stress B {suffix}",
                "cnpj": f"333444{suffix}",
                "email": f"stress.b.{suffix}@example.com",
                "phone": "14999999998",
                "responsible_name": "Operador Stress B",
                "status": "active",
                "address": {"street": "Rua B", "number": "200", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            company_id = remember("company_id", company_a["id"])
            other_company_id = remember("other_company_id", company_b["id"])

            def participant_payload(company: str, name: str, ptype: str, status: str, doc: str) -> dict[str, Any]:
                return {
                    "company_id": company,
                    "participant_type": ptype,
                    "person_type": "company",
                    "name": name,
                    "document": doc,
                    "email": f"{doc}@example.com",
                    "phone": "14988888888",
                    "status": status,
                    "address": {"street": "Rua Participante", "number": "1", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                    "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                    "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "a_vista", "credit_limit": "10000"},
                }

            customer = create_participant(db, ParticipantCreate(**participant_payload(company_id, f"Cliente Ativo {suffix}", "customer", "active", f"100000{suffix}")))
            supplier = create_participant(db, ParticipantCreate(**participant_payload(company_id, f"Fornecedor Ativo {suffix}", "supplier", "active", f"200000{suffix}")))
            blocked = create_participant(db, ParticipantCreate(**participant_payload(company_id, f"Cliente Bloqueado {suffix}", "customer", "blocked", f"300000{suffix}")))
            other_customer = create_participant(db, ParticipantCreate(**participant_payload(other_company_id, f"Cliente Outra Empresa {suffix}", "customer", "active", f"400000{suffix}")))
            remember("customer_id", customer["id"])
            remember("supplier_id", supplier["id"])
            remember("blocked_customer_id", blocked["id"])
            remember("other_customer_id", other_customer["id"])
            return {"company_id": company_id, "other_company_id": other_company_id, "customer_id": customer["id"], "supplier_id": supplier["id"]}

        _case(results, "01_foundation_company_participants", "Empresas, cliente, fornecedor e cliente bloqueado devem ser criados com vínculo multiempresa.", foundational_setup)

        def catalog_fiscal_setup() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            other_company_id = ctx["ids"]["other_company_id"]
            create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Produto Prévia {suffix}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": "12345678",
                "cfop_default": "5102",
                "cst_icms": "00",
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
            create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Produto Zero Prévia {suffix}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": "87654321",
                "cfop_default": "5102",
                "cst_icms": "00",
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
            create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": other_company_id,
                "name": f"Fiscal Produto Outra Prévia {suffix}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": "12345678",
                "cfop_default": "5102",
                "cst_icms": "00",
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
            create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Serviço Prévia {suffix}",
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
            product = create_catalog_item(db, CatalogItemCreate(**{
                "company_id": company_id,
                "item_type": "product",
                "name": f"Produto Controlado {suffix}",
                "sku": f"PROD-{suffix}",
                "unit": "UN",
                "status": "active",
                "origin": "manual",
                "financial_settings": {"default_sale_price": "100.00", "default_cost_price": "55.00", "allow_price_override": False},
                "fiscal_settings": {"ncm": "12345678", "cfop_default": "5102", "cst_icms": "00", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True},
                "inventory_settings": {"track_stock": True, "stock_unit": "UN", "minimum_stock": "1", "allow_negative_stock": False},
            }))
            product_no_stock = create_catalog_item(db, CatalogItemCreate(**{
                "company_id": company_id,
                "item_type": "product",
                "name": f"Produto Sem Saldo {suffix}",
                "sku": f"ZERO-{suffix}",
                "unit": "UN",
                "status": "active",
                "origin": "manual",
                "financial_settings": {"default_sale_price": "45.00", "default_cost_price": "20.00", "allow_price_override": False},
                "fiscal_settings": {"ncm": "87654321", "cfop_default": "5102", "cst_icms": "00", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True},
                "inventory_settings": {"track_stock": True, "stock_unit": "UN", "minimum_stock": "1", "allow_negative_stock": False},
            }))
            service = create_catalog_item(db, CatalogItemCreate(**{
                "company_id": company_id,
                "item_type": "service",
                "name": f"Serviço Consultivo {suffix}",
                "sku": f"SERV-{suffix}",
                "unit": "SERV",
                "status": "active",
                "origin": "manual",
                "financial_settings": {"default_sale_price": "220.00", "default_cost_price": "40.00", "allow_price_override": False},
                "fiscal_settings": {"nbs": "123456789", "cfop_default": "5933", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000002", "subject_to_tax": True},
                "inventory_settings": {"track_stock": False, "allow_negative_stock": False},
            }))
            other_product = create_catalog_item(db, CatalogItemCreate(**{
                "company_id": other_company_id,
                "item_type": "product",
                "name": f"Produto Outra Empresa {suffix}",
                "sku": f"OTHER-{suffix}",
                "unit": "UN",
                "status": "active",
                "origin": "manual",
                "financial_settings": {"default_sale_price": "50.00", "default_cost_price": "20.00", "allow_price_override": False},
                "fiscal_settings": {"ncm": "12345678", "cfop_default": "5102", "cst_icms": "00", "cst_pis": "99", "cst_cofins": "99", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True},
                "inventory_settings": {"track_stock": True, "stock_unit": "UN", "minimum_stock": "1", "allow_negative_stock": False},
            }))
            fclass_product = create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Produto {suffix}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": "12345678",
                "cfop_default": "5102",
                "cst_icms": "00",
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
            fclass_product_zero = create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Produto Zero {suffix}",
                "item_type": "product",
                "tax_regime": "simples_nacional",
                "ncm": "87654321",
                "cfop_default": "5102",
                "cst_icms": "00",
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
            fclass_service = create_fiscal_classification(db, FiscalClassificationCreate(**{
                "company_id": company_id,
                "name": f"Fiscal Serviço {suffix}",
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
            remember("product_id", product["id"])
            remember("product_zero_id", product_no_stock["id"])
            remember("service_id", service["id"])
            remember("other_product_id", other_product["id"])
            remember("fclass_product_id", fclass_product["id"])
            remember("fclass_product_zero_id", fclass_product_zero["id"])
            remember("fclass_service_id", fclass_service["id"])
            return {"product_id": product["id"], "service_id": service["id"], "fclass_product_id": fclass_product["id"]}

        _case(results, "02_catalog_and_fiscal_foundation", "Produtos/serviços e classificações fiscais devem existir e respeitar empresa/tipo.", catalog_fiscal_setup)

        def sales_rules_and_financial_defaults() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            natures = list_operation_natures(db, company_id=company_id)
            methods = list_payment_methods(db, company_id=company_id)
            normal = next(item for item in natures if item["code"] == "normal_sale")
            bonus = next(item for item in natures if item["code"] == "bonus")
            now = utc_now()
            for key, fclass_key in [("product_id", "fclass_product_id"), ("product_zero_id", "fclass_product_zero_id"), ("service_id", "fclass_service_id")]:
                create_catalog_item_fiscal_rule(
                    db,
                    id=generate_id("fiscalrule"),
                    company_id=company_id,
                    catalog_item_id=ctx["ids"][key],
                    fiscal_classification_id=ctx["ids"][fclass_key],
                    operation_nature_id=normal["id"],
                    sale_type="both" if key != "service_id" else "service",
                    valid_from=None,
                    valid_to=None,
                    priority=10,
                    status="active",
                    notes="Regra criada pelo super stress.",
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                )
            create_catalog_item_fiscal_rule(
                db,
                id=generate_id("fiscalrule"),
                company_id=company_id,
                catalog_item_id=ctx["ids"]["product_id"],
                fiscal_classification_id=ctx["ids"]["fclass_product_id"],
                operation_nature_id=bonus["id"],
                sale_type="product",
                valid_from=None,
                valid_to=None,
                priority=10,
                status="active",
                notes="Regra bonificação criada pelo super stress.",
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
            db.commit()
            financial_defaults = create_default_financial_masters(db, company_id)
            remember("normal_operation_id", normal["id"])
            remember("bonus_operation_id", bonus["id"])
            pix = get_payment_method_by_code(db, company_id=company_id, code="pix")
            remember("pix_payment_method_id", pix.id)
            return {"natures": len(natures), "methods": len(methods), "financial_defaults_created_keys": list(financial_defaults["created"].keys())}

        _case(results, "03_sales_rules_and_financial_defaults", "Naturezas, formas de pagamento, regras fiscais por item e cadastros financeiros base devem estar prontos.", sales_rules_and_financial_defaults)

        def stock_entry_and_readiness() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            entry = create_purchase_stock_entry(db, StockPurchaseEntryCreate(**{
                "company_id": company_id,
                "supplier_participant_id": ctx["ids"]["supplier_id"],
                "document_type": "purchase_invoice",
                "document_number": f"NF-STRESS-{suffix}",
                "issue_date": date.today().isoformat(),
                "notes": "Entrada de estoque para super stress.",
                "items": [{
                    "item_id": ctx["ids"]["product_id"],
                    "quantity": "5",
                    "unit_cost": "55.00",
                    "unit": "UN",
                    "lot_code": f"LOT-{suffix}",
                    "expiration_date": (date.today() + timedelta(days=365)).isoformat(),
                }],
            }))
            avail = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            lots = list_stock_lots(db, company_id=company_id, item_id=ctx["ids"]["product_id"], limit=20, offset=0)
            readiness = list_sale_item_readiness(db, company_id=company_id, sale_type="product", operation_nature_id=ctx["ids"]["normal_operation_id"])
            product_readiness = next(row for row in readiness if row["item_id"] == ctx["ids"]["product_id"])
            zero_readiness = next(row for row in readiness if row["item_id"] == ctx["ids"]["product_zero_id"])
            _assert(len(lots) >= 1, "Entrada deve gerar ao menos um lote para o produto.")
            remember("product_lot_id", lots[0]["id"])
            remember("product_lot_code", lots[0]["lot_code"])
            remember("product_lot_expiration_date", str(lots[0]["expiration_date"]))
            _assert(_q(avail["total_quantity"]) == Decimal("5.0000"), "Saldo inicial esperado de 5 unidades.")
            _assert(product_readiness["can_select"] is True, "Produto com saldo deveria estar selecionável.")
            _assert(zero_readiness["can_select"] is False, "Produto sem saldo não deveria estar selecionável.")
            return {"purchase_entry_id": entry["id"], "product_total_quantity": avail["total_quantity"], "zero_can_select": zero_readiness["can_select"], "lot_id": lots[0]["id"]}

        _case(results, "04_stock_entry_and_readiness", "Entrada de estoque deve aumentar saldo e readiness deve bloquear produto sem saldo.", stock_entry_and_readiness)

        def cross_company_and_blocked_guards() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            err_cross_customer = _expect_error(lambda: create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["other_customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "100.00"}],
            })), "Participante não pertence")
            err_blocked = _expect_error(lambda: create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["blocked_customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "100.00"}],
            })), "ativo")
            err_cross_item = _expect_error(lambda: create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["other_product_id"], "quantity": "1"}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "50.00"}],
            })), "Item não pertence")
            return {"cross_customer_blocked": err_cross_customer, "blocked_customer_blocked": err_blocked, "cross_item_blocked": err_cross_item}

        _case(results, "05_multiempresa_and_status_guards", "Venda deve bloquear cliente de outra empresa, cliente bloqueado e item de outra empresa.", cross_company_and_blocked_guards)

        def sale_validation_guards() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            price_error = _expect_error(lambda: create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"], "unit_price": "90.00"}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "90.00"}],
            })), "Preço unitário")
            plan_error = _expect_error(lambda: create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "99.00"}],
            })), "Soma das formas")
            return {"price_tamper_blocked": price_error, "payment_sum_blocked": plan_error}

        _case(results, "06_price_and_payment_plan_guards", "Backend deve bloquear preço adulterado e plano de pagamento divergente.", sale_validation_guards)

        def normal_product_sale_full_cycle() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale = create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "2", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [
                    {"payment_method_code": "pix", "amount": "120.00", "due_date": date.today().isoformat(), "notes": "Parcela 1"},
                    {"payment_method_code": "boleto", "amount": "80.00", "due_date": (date.today() + timedelta(days=30)).isoformat(), "notes": "Parcela 2"},
                ],
            }))
            sale_id = remember("normal_sale_id", sale["id"])
            confirmed = confirm_sale(db, sale_id, SaleStatusChange(reason="Super stress: confirmação venda normal."))
            avail_after_confirm = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale_id)
            _assert(confirmed["status"] == "confirmed", "Venda deveria estar confirmada.")
            _assert(_q(avail_after_confirm["total_quantity"]) == Decimal("3.0000"), "Saldo deveria cair de 5 para 3.")
            _assert(len(titles) == 2, "Venda com duas formas deve gerar dois títulos a receber.")
            _assert(sum(_money(title.net_amount) for title in titles) == Decimal("200.00"), "Soma dos títulos deveria ser 200,00.")
            remember("normal_sale_title_ids", [title.id for title in titles])
            existing = generate_receivables_from_sale_id(db, sale_id, reason="Idempotência super stress")
            _assert(len(existing) == 2, "Geração idempotente deveria retornar os dois títulos existentes.")
            movement_count = len(list_stock_movements(db, company_id=company_id, item_id=ctx["ids"]["product_id"], source_type="sale", source_id=sale_id, limit=20, offset=0))
            return {"sale_id": sale_id, "status": confirmed["status"], "stock_after_confirm": avail_after_confirm["total_quantity"], "titles": len(titles), "stock_movements_for_sale": movement_count}

        _case(results, "07_product_sale_confirms_stock_and_receivables", "Venda de produto deve baixar estoque e gerar títulos a receber por plano de pagamento.", normal_product_sale_full_cycle)

        def cancel_normal_sale_reverses() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale_id = ctx["ids"]["normal_sale_id"]
            cancelled = cancel_sale(db, sale_id, SaleStatusChange(reason="Super stress: cancelamento venda normal."))
            avail = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale_id)
            movements = list_stock_movements(db, company_id=company_id, item_id=ctx["ids"]["product_id"], source_type="sale", source_id=sale_id, limit=20, offset=0)
            _assert(cancelled["status"] == "cancelled", "Venda deveria estar cancelada.")
            _assert(_q(avail["total_quantity"]) == Decimal("5.0000"), "Cancelamento deveria repor saldo para 5.")
            _assert(all(title.status == "cancelled" and _money(title.open_amount) == Decimal("0.00") for title in titles), "Títulos vinculados deveriam ser cancelados e zerados.")
            _assert(any(m.get("movement_type") == "sale_out_reversal" for m in movements), "Deve existir movimento reverso de estoque.")
            return {"sale_id": sale_id, "stock_after_cancel": avail["total_quantity"], "titles_cancelled": len(titles), "movements": [m.get("movement_type") for m in movements]}

        _case(results, "08_cancel_sale_reverses_stock_and_receivables", "Cancelamento deve repor estoque, cancelar títulos abertos e manter movimentos reversos.", cancel_normal_sale_reverses)

        def insufficient_stock_rollback() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale = create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "999", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "99900.00"}],
            }))
            before_titles = len(list_receivables(db, company_id=company_id, sale_id=sale["id"], limit=20, offset=0))
            before_movements = len(list_stock_movements(db, company_id=company_id, item_id=ctx["ids"]["product_id"], source_type="sale", source_id=sale["id"], limit=20, offset=0))
            error = _expect_error(lambda: confirm_sale(db, sale["id"], SaleStatusChange(reason="Deve falhar por estoque")), "Saldo insuficiente")
            after_titles = len(list_receivables(db, company_id=company_id, sale_id=sale["id"], limit=20, offset=0))
            after_movements = len(list_stock_movements(db, company_id=company_id, item_id=ctx["ids"]["product_id"], source_type="sale", source_id=sale["id"], limit=20, offset=0))
            _assert(before_titles == after_titles == 0, "Falha de estoque não pode gerar título a receber.")
            _assert(before_movements == after_movements == 0, "Falha de estoque não pode gerar movimento.")
            return {"sale_id": sale["id"], "blocked_error": error, "titles_after_fail": after_titles, "movements_after_fail": after_movements}

        _case(results, "09_insufficient_stock_blocks_and_rolls_back", "Venda sem estoque deve falhar sem gerar título nem movimento.", insufficient_stock_rollback)

        def service_sale_no_stock_effects() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale = create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "service",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "discount_type": "amount",
                "discount_amount": "20.00",
                "discount_category": "commercial_negotiation",
                "discount_reason": "Desconto comercial de validação",
                "items": [{"item_id": ctx["ids"]["service_id"], "quantity": "1"}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "200.00"}],
            }))
            confirmed = confirm_sale(db, sale["id"], SaleStatusChange(reason="Super stress: venda de serviço."))
            titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale["id"])
            service_movements = list_stock_movements(db, company_id=company_id, item_id=ctx["ids"]["service_id"], source_type="sale", source_id=sale["id"], limit=20, offset=0)
            _assert(confirmed["status"] == "confirmed", "Venda de serviço deveria confirmar.")
            _assert(len(titles) == 1 and _money(titles[0].net_amount) == Decimal("200.00"), "Serviço com desconto deveria gerar 1 título líquido de 200,00.")
            _assert(len(service_movements) == 0, "Serviço não deve gerar movimento de estoque.")
            return {"sale_id": sale["id"], "titles": len(titles), "stock_movements": len(service_movements)}

        _case(results, "10_service_sale_generates_receivable_no_stock", "Venda de serviço deve gerar Contas a Receber sem mexer no estoque.", service_sale_no_stock_effects)

        def bonus_sale_stock_without_receivable() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale = create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature": "bonus",
                "operation_nature_id": ctx["ids"]["bonus_operation_id"],
                "operation_nature_reason": "Amostra/bonificação controlada no stress.",
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [],
            }))
            confirmed = confirm_sale(db, sale["id"], SaleStatusChange(reason="Super stress: bonificação."))
            titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale["id"])
            avail = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            _assert(confirmed["receivable_total_amount"] == "0.00", "Bonificação deve ter total a receber zero.")
            _assert(len(titles) == 0, "Bonificação não deve gerar título a receber.")
            _assert(_q(avail["total_quantity"]) == Decimal("4.0000"), "Bonificação deve baixar 1 unidade do estoque.")
            return {"sale_id": sale["id"], "receivable_total": confirmed["receivable_total_amount"], "titles": len(titles), "stock_after_bonus": avail["total_quantity"]}

        _case(results, "11_bonus_sale_affects_stock_not_receivable", "Bonificação deve baixar estoque, mas não gerar título financeiro.", bonus_sale_stock_without_receivable)

        def manual_ar_edge_cases() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            manual = create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"MANUAL-SRC-{suffix}",
                "due_date": date.today().isoformat(),
                "gross_amount": "150.00",
                "document_reference": f"MAN-{suffix}",
                "payment_method_id": ctx["ids"]["pix_payment_method_id"],
                "notes": "Título manual super stress.",
            }))
            duplicate_error = _expect_error(lambda: create_manual_receivable(db, FinancialTitleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "title_type": "manual",
                "source_type": "manual",
                "source_id": f"MANUAL-SRC-{suffix}",
                "due_date": date.today().isoformat(),
                "gross_amount": "150.00",
            })), "Já existe")
            updated = update_receivable(db, manual["id"], FinancialTitleUpdate(due_date=(date.today() - timedelta(days=5)).isoformat(), notes="Atualizado para vencido no super stress."))
            _assert(updated["status"] == "overdue", "Título com vencimento passado deveria ficar vencido.")
            cancelled = cancel_receivable(db, manual["id"], FinancialTitleStatusChange(reason="Cancelamento manual no stress."))
            update_closed_error = _expect_error(lambda: update_receivable(db, manual["id"], FinancialTitleUpdate(notes="Não pode alterar encerrado")), "encerrado")
            history = get_receivable_history(db, manual["id"])
            return {"manual_title_id": manual["id"], "duplicate_blocked": duplicate_error, "status_after_due_update": updated["status"], "cancelled_status": cancelled["status"], "update_closed_blocked": update_closed_error, "history_count": len(history)}

        _case(results, "12_manual_receivable_edge_cases", "Contas a Receber manual deve bloquear duplicidade, virar vencido por data passada e bloquear alteração encerrada.", manual_ar_edge_cases)

        def cancel_sale_with_paid_title_rolls_back() -> dict[str, Any]:
            company_id = ctx["ids"]["company_id"]
            sale = create_sale(db, SaleCreate(**{
                "company_id": company_id,
                "participant_id": ctx["ids"]["customer_id"],
                "sale_type": "product",
                "operation_nature_id": ctx["ids"]["normal_operation_id"],
                "items": [{"item_id": ctx["ids"]["product_id"], "quantity": "1", "stock_lot_id": ctx["ids"]["product_lot_id"], "stock_lot_code": ctx["ids"]["product_lot_code"]}],
                "payment_plans": [{"payment_method_code": "pix", "amount": "100.00"}],
            }))
            confirm_sale(db, sale["id"], SaleStatusChange(reason="Confirmar venda para teste de rollback de cancelamento."))
            before_avail = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale["id"])
            _assert(len(titles) == 1, "Venda deveria ter 1 título.")
            title = get_title(db, titles[0].id)
            update_title_fields(title, paid_amount=Decimal("10.00"), open_amount=Decimal("90.00"), status="partially_received", updated_at=utc_now())
            db.commit()
            error = _expect_error(lambda: cancel_sale(db, sale["id"], SaleStatusChange(reason="Deve falhar: título parcialmente recebido.")), "título já recebido")
            after_avail = get_item_availability(db, company_id=company_id, item_id=ctx["ids"]["product_id"])
            after_titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale["id"])
            _assert(_q(before_avail["total_quantity"]) == _q(after_avail["total_quantity"]), "Rollback deve preservar saldo após falha no cancelamento.")
            _assert(after_titles[0].status == "partially_received", "Título não deve ser cancelado quando cancelamento falha.")
            return {"sale_id": sale["id"], "blocked_error": error, "stock_before": before_avail["total_quantity"], "stock_after": after_avail["total_quantity"], "title_status_after_fail": after_titles[0].status}

        _case(results, "13_cancel_paid_sale_rolls_back_stock_reversal", "Se cancelar venda com título recebido falhar, reversão de estoque deve ser revertida pela transação.", cancel_sale_with_paid_title_rolls_back)

        def locks_and_integrity() -> dict[str, Any]:
            source_stock = inspect.getsource(stock_repository.get_stock_balance_for_update)
            source_sale_repo = inspect.getsource(sales_repository.get_sale_for_update)
            _assert("with_for_update" in source_stock, "Saldo de estoque deve usar with_for_update.")
            _assert("with_for_update" in source_sale_repo, "Venda deve ser buscada com with_for_update na confirmação/cancelamento.")
            company_id = ctx["ids"]["company_id"]
            summary = get_receivables_summary(db, company_id=company_id)
            sales_diag = get_sales_diagnostics(db)
            financial_diag = get_financial_diagnostics(db, company_id=company_id)
            ar_diag = get_accounts_receivable_diagnostics()
            audit_sale_events = list_audit_events_for_entity(db, entity_type="sale", entity_id=ctx["ids"].get("normal_sale_id", ""), limit=100, offset=0)
            return {
                "stock_lock_source_has_with_for_update": True,
                "sale_lock_source_has_with_for_update": True,
                "receivables_summary": summary,
                "sales_status": sales_diag.get("status"),
                "financial_counts": financial_diag.get("records_count"),
                "ar_tables": ar_diag.get("tables"),
                "normal_sale_audit_events": len(audit_sale_events),
            }

        _case(results, "14_locks_diagnostics_and_audit", "Pontos críticos devem usar FOR UPDATE, diagnósticos devem responder e auditoria deve existir.", locks_and_integrity)

        def relational_orphan_check() -> dict[str, Any]:
            checks_sql = {
                "sale_items_without_sale": "select count(*) from sale_items si left join sales s on s.id = si.sale_id where s.id is null",
                "sale_payment_plans_without_sale": "select count(*) from sale_payment_plans sp left join sales s on s.id = sp.sale_id where s.id is null",
                "sale_stock_links_without_sale": "select count(*) from sale_stock_links ssl left join sales s on s.id = ssl.sale_id where s.id is null",
                "stock_movements_without_item": "select count(*) from stock_movements sm left join catalog_items ci on ci.id = sm.item_id where ci.id is null",
                "financial_titles_without_participant": "select count(*) from financial_titles ft left join participants p on p.id = ft.participant_id where p.id is null",
                "sale_financial_links_without_title": "select count(*) from sale_financial_links sfl left join financial_titles ft on ft.id = sfl.financial_title_id where ft.id is null",
            }
            evidence: dict[str, Any] = {}
            for name, sql in checks_sql.items():
                count = db.execute(text(sql)).scalar_one()
                evidence[name] = count
                _assert(count == 0, f"Integridade falhou: {name}={count}")
            counts_sql = {
                "companies": "select count(*) from companies",
                "participants": "select count(*) from participants",
                "catalog_items": "select count(*) from catalog_items",
                "fiscal_classifications": "select count(*) from fiscal_classifications",
                "sales": "select count(*) from sales",
                "stock_movements": "select count(*) from stock_movements",
                "financial_titles": "select count(*) from financial_titles",
                "audit_events": "select count(*) from audit_events",
            }
            evidence["table_counts"] = {name: db.execute(text(sql)).scalar_one() for name, sql in counts_sql.items()}
            return evidence

        _case(results, "15_relational_orphan_check", "Tabelas conectadas não devem apresentar registros órfãos nos vínculos principais.", relational_orphan_check)

    finally:
        failed = sum(1 for result in results if result.status == "FAIL")
        passed = sum(1 for result in results if result.status == "PASS")
        report = {
            "status": "PASS" if failed == 0 else "FAIL",
            "database_url": os.environ.get("DATABASE_URL", "configured_by_app_settings"),
            "sqlite_smoke_mode": sqlite_mode,
            "summary": {"passed": passed, "failed": failed, "total": len(results)},
            "ids": ctx.get("ids", {}),
            "cases": [result.__dict__ for result in results],
        }
        db.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-smoke-db", default=None, help="Caminho opcional para banco SQLite isolado de smoke test.")
    parser.add_argument("--output", default="super_stress_integration_report.json", help="Arquivo JSON de saída.")
    args = parser.parse_args()
    try:
        report = run(sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
