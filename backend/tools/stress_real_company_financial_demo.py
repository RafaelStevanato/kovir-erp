r"""
Kovir ERP — Super stress test com empresa demo e fluxo financeiro real
========================================================================

Objetivo
--------
Cria uma empresa demo com volume operacional suficiente para abrir o ERP e enxergar
um fluxo real, não telas vazias:

- empresa demo;
- clientes;
- fornecedores;
- produtos;
- serviços;
- contas financeiras;
- categorias;
- centros de custo;
- vendas;
- contas a receber;
- compras;
- contas a pagar;
- baixas;
- movimentos financeiros;
- extratos;
- conciliações;
- divergências controladas;
- varreduras de integridade relacional.

Uso no PostgreSQL local migrado:
    cd backend
    $env:PYTHONPATH = (Get-Location).Path
    python .\tools\stress_real_company_financial_demo.py --output stress_real_company_financial_demo_report.json

Uso com volume maior:
    python .\tools\stress_real_company_financial_demo.py --sales 40 --purchases 25 --output stress_real_company_financial_demo_report.json

Uso smoke SQLite isolado:
    python .\tools\stress_real_company_financial_demo.py --sqlite-smoke-db ..\stress_real_company_financial_demo_smoke.db --output stress_real_company_financial_demo_report.json

Observação
----------
Este script grava dados reais de demonstração no banco configurado. Ele usa nomes,
documentos e referências sintéticas com prefixo "DEMO" e sufixo único por execução.
Não apaga dados existentes.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable

MONEY_QUANT = Decimal("0.01")
QTY_QUANT = Decimal("0.0001")


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
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _qty(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def _money_str(value: Any) -> str:
    return format(_money(value), "f")


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


def _slice_amount(total: Decimal, parts: int) -> list[Decimal]:
    if parts <= 1:
        return [total]
    base = (total / Decimal(parts)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    values = [base for _ in range(parts)]
    values[-1] = total - sum(values[:-1], Decimal("0.00"))
    return [item.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) for item in values]


def run(*, sales_count: int = 24, purchases_count: int = 16, sqlite_smoke_db: str | None = None) -> dict[str, Any]:
    sqlite_mode = _configure_sqlite_if_requested(sqlite_smoke_db)

    from sqlalchemy import text

    from app.core.database import SessionLocal, engine
    from app.db.base import Base
    from app.modules.accounts_receivable.schemas import FinancialTitleCreate
    from app.modules.accounts_receivable.service import create_manual_receivable, list_receivables
    from app.modules.cash.schemas import ManualFinancialMovementCreate, SettlementCreate
    from app.modules.cash.service import create_manual_movement, list_account_balances, list_movements, receive_title
    from app.modules.catalog.schemas import CatalogItemCreate
    from app.modules.catalog.service import create_catalog_item
    from app.modules.company.schemas import CompanyCreate
    from app.modules.company.service import create_company
    from app.modules.financial.schemas import CostCenterCreate, FinancialAccountCreate, FinancialCategoryCreate
    from app.modules.financial.service import (
        create_cost_center,
        create_default_financial_masters,
        create_financial_account,
        create_financial_category,
        list_cost_centers,
        list_financial_accounts,
        list_financial_categories,
    )
    from app.modules.fiscal_classification.schemas import FiscalClassificationCreate, FiscalProfileCreate
    from app.modules.fiscal_classification.service import create_fiscal_classification, create_fiscal_profile
    from app.modules.participants.schemas import ParticipantCreate
    from app.modules.participants.service import create_participant, list_participants
    from app.modules.purchases_payables.schemas import PayablePaymentCreate, PurchaseConfirmPayload, PurchaseCreate
    from app.modules.purchases_payables.service import create_purchase_draft, confirm_purchase, get_purchases_payables_summary, list_payables, pay_payable
    from app.modules.reconciliation.schemas import BankStatementImportCreate, ReconciliationMatchCreate
    from app.modules.reconciliation.service import confirm_match, import_statement, list_reconciliation_matches, list_statement_lines
    from app.modules.sales.schemas import SaleCreate, SaleStatusChange
    from app.modules.sales.service import confirm_sale, create_sale, ensure_default_operation_natures, ensure_default_payment_methods, list_sales
    from app.modules.stock.schemas import StockPurchaseEntryCreate
    from app.modules.stock.service import create_purchase_stock_entry, list_purchase_stock_entries, list_stock_balances, list_stock_movements

    if sqlite_mode:
        Base.metadata.create_all(engine)

    rng_seed = abs(hash((date.today().isoformat(), os.getpid(), sales_count, purchases_count)))
    rng = random.Random(rng_seed)
    suffix = str(rng_seed).zfill(10)[-10:]
    today = date.today()

    db = SessionLocal()
    results: list[CaseResult] = []
    ids: dict[str, Any] = {
        "run_suffix": suffix,
        "rng_seed": rng_seed,
        "requested_sales": sales_count,
        "requested_purchases": purchases_count,
    }
    collections: dict[str, list[Any]] = defaultdict(list)
    inconsistencies: list[dict[str, Any]] = []

    def remember(key: str, value: Any) -> Any:
        ids[key] = value
        return value

    def collect(key: str, value: Any) -> Any:
        collections[key].append(value)
        return value

    def need(key: str) -> Any:
        if key not in ids:
            raise AssertionError(f"Pré-requisito não criado: {key}. Verifique o caso anterior no relatório.")
        return ids[key]

    def participant_document(prefix: str, index: int) -> str:
        raw = f"{prefix[:3].upper()}{suffix[-8:]}{index:03d}"
        return "".join(ch for ch in raw if ch.isalnum())[:14].ljust(14, "0")

    def participant_payload(*, company_id: str, name: str, ptype: str, index: int, doc_prefix: str, email_prefix: str) -> dict[str, Any]:
        return {
            "company_id": company_id,
            "participant_type": ptype,
            "person_type": "company",
            "name": name,
            "trade_name": name.split(" LTDA")[0],
            "document": participant_document(doc_prefix, index),
            "email": f"{email_prefix}.{suffix}.{index}@kovirdemo.com",  # domínio público sintético; EmailStr rejeita .local/.test
            "phone": f"1499{index:07d}"[:11],
            "status": "active",
            "address": {"street": "Rua Demo Kovir", "number": str(100 + index), "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
            "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
            "financial_settings": {"default_payment_method": "pix", "default_payment_terms": "30 dias", "credit_limit": "50000.00"},
        }

    def pick(seq: list[Any], index: int) -> Any:
        if not seq:
            raise AssertionError("Coleção vazia para seleção.")
        return seq[index % len(seq)]

    try:
        def case_01_company_participants() -> dict[str, Any]:
            company = create_company(db, CompanyCreate(**{
                "legal_name": f"DEMO Kovir Comércio Integrado {suffix} LTDA",
                "trade_name": f"DEMO Kovir {suffix}",
                "cnpj": f"91{suffix[-8:]}0001",
                "email": f"financeiro.{suffix}@kovirdemo.com",
                "phone": "14999999999",
                "responsible_name": "Gestor Demo Kovir",
                "status": "active",
                "address": {"street": "Avenida Demo Kovir", "number": "1000", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "4789099", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
                "operational_settings": {"business_segment": "commerce_services", "default_language": "pt-BR"},
            }))
            company_id = remember("company_id", company["id"])

            other_company = create_company(db, CompanyCreate(**{
                "legal_name": f"DEMO Outra Empresa Isolamento {suffix} LTDA",
                "trade_name": f"DEMO Outra {suffix}",
                "cnpj": f"92{suffix[-8:]}0001",
                "email": f"outra.{suffix}@kovirdemo.com",
                "phone": "14999999998",
                "responsible_name": "Gestor Outra Empresa",
                "status": "active",
                "address": {"street": "Rua Isolamento", "number": "2000", "district": "Centro", "city": "Bauru", "state": "SP", "zip_code": "17000000", "country": "BR"},
                "fiscal_settings": {"taxpayer_type": "taxpayer", "tax_regime": "simples_nacional", "main_cnae": "6201500", "state_registration": "ISENTO", "is_foreign": False},
                "financial_settings": {"currency": "BRL", "uses_accounts_receivable": True, "uses_accounts_payable": True, "uses_cash_control": True},
            }))
            remember("other_company_id", other_company["id"])

            customer_names = [
                "Mercado Vila Nova LTDA", "Clínica Boa Saúde LTDA", "Loja Central Bauru LTDA", "Restaurante São Bento LTDA",
                "Distribuidora Alpha LTDA", "E-commerce Cliente Beta LTDA", "Padaria Aurora LTDA", "Escritório Prisma LTDA",
            ]
            supplier_names = [
                "Atacado Brasil Alimentos LTDA", "Serviços CloudPro LTDA", "Aluguel Galpão Bauru LTDA", "Transportes Rápidos SP LTDA",
                "Energia Comercial S.A.", "Contabilidade Parceira LTDA", "Marketing Local LTDA", "Fornecedor Embalagens Premium LTDA",
            ]
            for i, name in enumerate(customer_names, start=1):
                customer = create_participant(db, ParticipantCreate(**participant_payload(company_id=company_id, name=name, ptype="customer", index=i, doc_prefix="CLI", email_prefix="cliente")))
                collect("customers", customer)
            for i, name in enumerate(supplier_names, start=1):
                supplier = create_participant(db, ParticipantCreate(**participant_payload(company_id=company_id, name=name, ptype="supplier", index=i, doc_prefix="SUP", email_prefix="fornecedor")))
                collect("suppliers", supplier)
            other_supplier = create_participant(db, ParticipantCreate(**participant_payload(company_id=other_company["id"], name="Fornecedor Bloqueio Cross Company LTDA", ptype="supplier", index=99, doc_prefix="OUT", email_prefix="bloqueio")))
            remember("other_supplier_id", other_supplier["id"])
            remember("customer_id", collections["customers"][0]["id"])
            remember("supplier_id", collections["suppliers"][0]["id"])
            return {"company_id": company_id, "customers": len(collections["customers"]), "suppliers": len(collections["suppliers"]), "other_company_id": other_company["id"]}

        _case(results, "01_demo_company_customers_suppliers", "Cria empresa demo, clientes, fornecedores e empresa de isolamento multiempresa.", case_01_company_participants)

        def case_02_financial_masters() -> dict[str, Any]:
            company_id = need("company_id")
            create_default_financial_masters(db, company_id)

            revenue_cat = create_financial_category(db, FinancialCategoryCreate(**{"company_id": company_id, "code": f"DEMO-REC-{suffix[-4:]}", "name": "Receita operacional demo", "category_type": "income", "cash_flow_group": "operational_inflow", "status": "active"}))
            inventory_cat = create_financial_category(db, FinancialCategoryCreate(**{"company_id": company_id, "code": f"DEMO-CMV-{suffix[-4:]}", "name": "Compra de mercadorias demo", "category_type": "cost", "cash_flow_group": "operational_outflow", "requires_cost_center": True, "status": "active"}))
            expense_cat = create_financial_category(db, FinancialCategoryCreate(**{"company_id": company_id, "code": f"DEMO-DESP-{suffix[-4:]}", "name": "Despesas administrativas demo", "category_type": "expense", "cash_flow_group": "operational_outflow", "requires_cost_center": True, "status": "active"}))
            services_cat = create_financial_category(db, FinancialCategoryCreate(**{"company_id": company_id, "code": f"DEMO-SERV-{suffix[-4:]}", "name": "Serviços de terceiros demo", "category_type": "expense", "cash_flow_group": "operational_outflow", "requires_cost_center": True, "status": "active"}))
            cc_admin = create_cost_center(db, CostCenterCreate(**{"company_id": company_id, "code": f"DEMO-ADM-{suffix[-4:]}", "name": "Administrativo Demo", "center_type": "administrative", "responsible_name": "Gestor Administrativo", "monthly_budget_amount": "15000.00", "status": "active"}))
            cc_sales = create_cost_center(db, CostCenterCreate(**{"company_id": company_id, "code": f"DEMO-COM-{suffix[-4:]}", "name": "Comercial Demo", "center_type": "commercial", "responsible_name": "Gestor Comercial", "monthly_budget_amount": "25000.00", "status": "active"}))
            cc_marketplace = create_cost_center(db, CostCenterCreate(**{"company_id": company_id, "code": f"DEMO-MKT-{suffix[-4:]}", "name": "Marketplace Demo", "center_type": "marketplace", "responsible_name": "Gestor Marketplace", "monthly_budget_amount": "18000.00", "status": "active"}))

            main_bank = create_financial_account(db, FinancialAccountCreate(**{"company_id": company_id, "name": f"Banco Principal Demo {suffix}", "account_type": "bank_account", "institution_name": "Banco Kovir", "branch_number": "0001", "account_number": suffix[-6:], "account_digit": "0", "currency": "BRL", "opening_balance_amount": "25000.00", "is_default_receivable": True, "is_default_payable": True, "status": "active"}))
            cash_register = create_financial_account(db, FinancialAccountCreate(**{"company_id": company_id, "name": f"Caixa Loja Demo {suffix}", "account_type": "cash", "institution_name": "Caixa Interno", "currency": "BRL", "opening_balance_amount": "1500.00", "is_default_receivable": False, "is_default_payable": False, "status": "active"}))
            gateway = create_financial_account(db, FinancialAccountCreate(**{"company_id": company_id, "name": f"Gateway Cartões Demo {suffix}", "account_type": "gateway", "institution_name": "Gateway DemoPay", "currency": "BRL", "opening_balance_amount": "0.00", "is_default_receivable": False, "is_default_payable": False, "status": "active"}))

            remember("main_bank_id", main_bank["id"])
            remember("cash_register_id", cash_register["id"])
            remember("gateway_account_id", gateway["id"])
            remember("revenue_category_id", revenue_cat["id"])
            remember("inventory_category_id", inventory_cat["id"])
            remember("expense_category_id", expense_cat["id"])
            remember("services_category_id", services_cat["id"])
            remember("cc_admin_id", cc_admin["id"])
            remember("cc_sales_id", cc_sales["id"])
            remember("cc_marketplace_id", cc_marketplace["id"])
            return {"accounts": 3, "categories": 4, "cost_centers": 3, "main_bank_id": main_bank["id"]}

        _case(results, "02_financial_accounts_categories_cost_centers", "Cria contas financeiras, categorias e centros de custo operacionais para a demo.", case_02_financial_masters)

        def case_03_catalog_fiscal_stock() -> dict[str, Any]:
            company_id = need("company_id")
            profile = create_fiscal_profile(db, FiscalProfileCreate(**{"company_id": company_id, "name": f"Perfil Fiscal Demo {suffix}", "description": "Perfil fiscal sintético para stress demo.", "profile_type": "mixed", "applies_to": "both", "tax_regime": "simples_nacional", "status": "active", "valid_from": today - timedelta(days=30), "source": "manual", "source_reference": "stress_real_company_financial_demo.py"}))
            remember("fiscal_profile_id", profile["id"])

            product_specs = [
                ("Café Especial 500g", "789100000001", "09012100", "28.90", "16.40", "UN"),
                ("Suplemento Proteico 900g", "789100000002", "21069030", "119.90", "72.10", "UN"),
                ("Snack Integral Caixa", "789100000003", "19059090", "42.50", "24.70", "CX"),
                ("Garrafa Térmica 1L", "789100000004", "96170010", "89.00", "51.20", "UN"),
                ("Kit Escritório Premium", "789100000005", "48201000", "64.90", "37.80", "UN"),
            ]
            service_specs = [
                ("Implantação Kovir Básica", "DMSERV001", "118011000", "450.00", "0.00", "SERV"),
                ("Treinamento Financeiro Operacional", "DMSERV002", "118011000", "320.00", "0.00", "HORA"),
                ("Suporte Mensal ERP", "DMSERV003", "118011000", "690.00", "0.00", "MES"),
            ]

            for i, (name, barcode, ncm, sale_price, cost_price, unit) in enumerate(product_specs, start=1):
                classification = create_fiscal_classification(db, FiscalClassificationCreate(**{"company_id": company_id, "fiscal_profile_id": profile["id"], "name": f"Classificação {name}", "item_type": "product", "tax_regime": "simples_nacional", "ncm": ncm, "cfop_default": "5102", "cst_icms": "102", "cst_pis": "49", "cst_cofins": "49", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_icms": True, "subject_to_pis_cofins": True, "subject_to_ibs_cbs": True, "status": "active", "valid_from": today - timedelta(days=30), "source": "manual", "source_reference": "stress demo"}))
                item = create_catalog_item(db, CatalogItemCreate(**{"company_id": company_id, "item_type": "product", "name": name, "description": f"Produto demo {name}", "sku": f"DEMO-PROD-{suffix[-4:]}-{i:02d}", "barcode": f"{barcode}{suffix[-2:]}", "unit": unit, "status": "active", "origin": "manual", "financial_settings": {"default_sale_price": sale_price, "default_cost_price": cost_price, "default_revenue_account_id": need("revenue_category_id"), "default_expense_account_id": need("inventory_category_id"), "default_cost_center_id": need("cc_sales_id")}, "fiscal_settings": {"ncm": ncm, "cfop_default": "5102", "cst_icms": "102", "cst_pis": "49", "cst_cofins": "49", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True}, "inventory_settings": {"track_stock": True, "stock_unit": unit, "minimum_stock": "10", "allow_negative_stock": False}, "notes": "Produto demo com estoque controlado."}))
                collect("products", item)
                collect("product_classifications", classification)

            for i, (name, sku, nbs, sale_price, cost_price, unit) in enumerate(service_specs, start=1):
                classification = create_fiscal_classification(db, FiscalClassificationCreate(**{"company_id": company_id, "fiscal_profile_id": profile["id"], "name": f"Classificação {name}", "item_type": "service", "tax_regime": "simples_nacional", "nbs": nbs, "cfop_default": None, "cst_pis": "49", "cst_cofins": "49", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_iss": True, "subject_to_pis_cofins": True, "subject_to_ibs_cbs": True, "status": "active", "valid_from": today - timedelta(days=30), "source": "manual", "source_reference": "stress demo"}))
                item = create_catalog_item(db, CatalogItemCreate(**{"company_id": company_id, "item_type": "service", "name": name, "description": f"Serviço demo {name}", "sku": f"{sku}-{suffix[-4:]}", "unit": unit, "status": "active", "origin": "manual", "financial_settings": {"default_sale_price": sale_price, "default_cost_price": cost_price, "default_revenue_account_id": need("revenue_category_id"), "default_expense_account_id": need("services_category_id"), "default_cost_center_id": need("cc_admin_id")}, "fiscal_settings": {"nbs": nbs, "cst_pis": "49", "cst_cofins": "49", "cst_ibs_cbs": "000", "cclass_trib": "000001", "subject_to_tax": True}, "inventory_settings": {"track_stock": False, "stock_unit": unit, "minimum_stock": None, "allow_negative_stock": False}, "notes": "Serviço demo sem controle de estoque."}))
                collect("services", item)
                collect("service_classifications", classification)

            purchase_entry = create_purchase_stock_entry(db, StockPurchaseEntryCreate(**{"company_id": company_id, "supplier_participant_id": need("supplier_id"), "document_type": "purchase_invoice", "document_number": f"NF-STOCK-{suffix}", "document_series": "1", "issue_date": today - timedelta(days=6), "notes": "Entrada inicial de estoque demo para vendas.", "items": [{"item_id": product["id"], "quantity": "160", "unit_cost": product["financial_settings"]["default_cost_price"], "unit": product["unit"], "description": product["name"]} for product in collections["products"]]}))
            remember("stock_entry_id", purchase_entry["id"])
            balances = list_stock_balances(db, company_id=company_id, limit=200)
            _assert(len(collections["products"]) >= 5, "Produtos demo não foram criados em quantidade mínima.")
            _assert(len(collections["services"]) >= 3, "Serviços demo não foram criados em quantidade mínima.")
            _assert(len(balances) >= len(collections["products"]), "Saldos de estoque não foram criados para os produtos.")
            return {"products": len(collections["products"]), "services": len(collections["services"]), "fiscal_classifications": len(collections["product_classifications"]) + len(collections["service_classifications"]), "stock_entry_id": purchase_entry["id"], "stock_balances": len(balances)}

        _case(results, "03_catalog_fiscal_stock_foundation", "Cria catálogo, classificações fiscais e entrada de estoque para suportar vendas reais.", case_03_catalog_fiscal_stock)

        def case_04_sales_generate_receivables() -> dict[str, Any]:
            company_id = need("company_id")
            ensure_default_operation_natures(db, company_id)
            ensure_default_payment_methods(db, company_id)
            products = collections["products"]
            services = collections["services"]
            customers = collections["customers"]
            created_sales = []
            confirmed_sales = []
            for i in range(max(1, sales_count)):
                is_service = i % 4 == 3
                item = pick(services if is_service else products, i)
                customer = pick(customers, i)
                sale_type = "service" if is_service else "product"
                qty = Decimal(str(1 + (i % 3))) if not is_service else Decimal("1")
                price = _money((item.get("financial_settings") or {}).get("default_sale_price"))
                total = (qty * price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                installments = 2 if i % 5 in {1, 2} else 1
                amounts = _slice_amount(total, installments)
                payment_plans = []
                for n, amount in enumerate(amounts, start=1):
                    payment_plans.append({"payment_method_code": "pix" if i % 3 else "boleto", "amount": _money_str(amount), "due_date": (today + timedelta(days=7 * n - (10 if i % 7 == 0 else 0))).isoformat(), "installments": installments, "notes": f"Parcela {n}/{installments} venda demo"})
                sale = create_sale(db, SaleCreate(**{"company_id": company_id, "participant_id": customer["id"], "sale_type": sale_type, "origin": "manual", "operation_nature": "normal_sale", "issue_date": (today - timedelta(days=i % 9)).isoformat(), "competency_date": (today - timedelta(days=i % 9)).isoformat(), "notes": f"Venda demo stress #{i+1}", "payment_plans": payment_plans, "items": [{"item_id": item["id"], "description": item["name"], "quantity": _money_str(qty).rstrip("0").rstrip("."), "unit": item["unit"], "unit_price": _money_str(price), "discount_amount": "0", "freight_amount": "0", "tax_amount": "0"}]}))
                created_sales.append(sale)
                confirmed = confirm_sale(db, sale["id"], SaleStatusChange(reason="Confirmação automática pelo super stress demo."))
                confirmed_sales.append(confirmed)
                collect("sales", confirmed)
                titles = list_receivables(db, company_id=company_id, sale_id=sale["id"], limit=50)
                for title in titles:
                    collect("receivables", title)
            _assert(len(created_sales) == sales_count, "Quantidade de vendas criadas diverge do solicitado.")
            _assert(len(collections["receivables"]) >= sales_count, "Vendas confirmadas deveriam gerar contas a receber.")
            return {"created_sales": len(created_sales), "confirmed_sales": len(confirmed_sales), "receivable_titles": len(collections["receivables"]), "sales_total_amount": _money_str(sum((_money(row["total_amount"]) for row in confirmed_sales), Decimal("0.00")))}

        _case(results, "04_sales_products_services_generate_accounts_receivable", "Cria vendas de produtos/serviços, confirma, baixa estoque e gera contas a receber.", case_04_sales_generate_receivables)

        def case_05_receive_receivables_and_extra_cash_movements() -> dict[str, Any]:
            receivables = list_receivables(db, company_id=need("company_id"), limit=500)
            received_count = 0
            partial_count = 0
            movement_ids = []
            for i, title in enumerate(receivables):
                if title["direction"] != "receivable" or title["status"] in {"received", "cancelled", "written_off"}:
                    continue
                if i % 5 == 4:
                    continue
                open_amount = _money(title["open_amount"])
                if open_amount <= 0:
                    continue
                partial = i % 4 == 1 and open_amount > Decimal("20.00")
                received = (open_amount / Decimal("2")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if partial else open_amount
                fee = Decimal("1.90") if i % 3 == 0 and received > Decimal("5.00") else Decimal("0.00")
                settlement = receive_title(db, SettlementCreate(**{"company_id": need("company_id"), "financial_title_id": title["id"], "financial_account_id": need("main_bank_id") if i % 3 else need("gateway_account_id"), "settlement_date": (today - timedelta(days=i % 5)).isoformat(), "received_amount": _money_str(received), "discount_amount": "0.00", "interest_amount": "0.00", "penalty_amount": "0.00", "fee_amount": _money_str(fee), "source_type": "manual", "source_id": f"DEMO-AR-SETT-{suffix}-{i}", "evidence_reference": f"PIX-DEMO-AR-{suffix}-{i}", "notes": "Baixa automática criada pelo super stress demo."}))
                movement_ids.append(settlement["movement"]["id"])
                received_count += 1
                if partial:
                    partial_count += 1
            manual_fee = create_manual_movement(db, ManualFinancialMovementCreate(**{"company_id": need("company_id"), "financial_account_id": need("main_bank_id"), "direction": "outflow", "movement_type": "bank_fee", "movement_date": today.isoformat(), "amount": "18.90", "description": "Tarifa bancária mensal demo", "source_type": "manual", "source_id": f"DEMO-BANK-FEE-{suffix}", "metadata": {"demo": True}}))
            collect("manual_movements", manual_fee["movement"])
            movements = list_movements(db, company_id=need("company_id"), limit=500)
            _assert(received_count > 0, "Nenhum recebível foi baixado.")
            _assert(len(movements) >= received_count, "Movimentos financeiros deveriam existir após baixas.")
            return {"received_titles": received_count, "partial_receipts": partial_count, "movement_count": len(movements), "manual_fee_movement_id": manual_fee["movement"]["id"]}

        _case(results, "05_receipts_settlements_financial_movements", "Baixa parte dos recebíveis, cria movimentos financeiros e deixa títulos em aberto para fluxo previsto.", case_05_receive_receivables_and_extra_cash_movements)

        def case_06_purchases_generate_payables() -> dict[str, Any]:
            suppliers = collections["suppliers"]
            products = collections["products"]
            purchases = []
            payables_generated = []
            for i in range(max(1, purchases_count)):
                supplier = pick(suppliers, i)
                ptype = ["inventory_purchase", "expense", "service", "tax", "other"][i % 5]
                category_id = need("inventory_category_id") if ptype == "inventory_purchase" else (need("services_category_id") if ptype == "service" else need("expense_category_id"))
                cc_id = [need("cc_admin_id"), need("cc_sales_id"), need("cc_marketplace_id")][i % 3]
                if ptype == "inventory_purchase":
                    product = pick(products, i)
                    quantity = Decimal(str(3 + (i % 5)))
                    unit_cost = _money((product.get("financial_settings") or {}).get("default_cost_price"))
                    total = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                    item_payload = {"item_id": product["id"], "description": f"Compra de {product['name']}", "quantity": str(quantity), "unit": product["unit"], "unit_cost": _money_str(unit_cost)}
                else:
                    total = Decimal(str(180 + (i * 37) % 900)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                    item_payload = {"description": f"Despesa demo {ptype} #{i+1}", "quantity": "1", "unit": "UN", "unit_cost": _money_str(total)}
                purchase = create_purchase_draft(db, PurchaseCreate(**{"company_id": need("company_id"), "participant_id": supplier["id"], "purchase_type": ptype, "origin": "manual", "fiscal_status": "pending_document" if i % 4 else "not_required", "issue_date": (today - timedelta(days=i % 12)).isoformat(), "competency_date": (today - timedelta(days=i % 12)).isoformat(), "financial_category_id": category_id, "cost_center_id": cc_id, "expected_financial_account_id": need("main_bank_id"), "document_type": "invoice", "document_number": f"NF-AP-DEMO-{suffix}-{i:03d}", "invoice_total_amount": _money_str(total), "notes": f"Compra/despesa demo stress #{i+1}", "items": [item_payload]}))
                parts = 3 if i % 6 == 0 else (2 if i % 4 in {1, 2} else 1)
                amounts = _slice_amount(total, parts)
                installments = []
                for n, amount in enumerate(amounts, start=1):
                    due = today + timedelta(days=7 * n - (12 if i % 5 == 0 else 0))
                    installments.append({"due_date": due.isoformat(), "amount": _money_str(amount), "expected_financial_account_id": need("main_bank_id"), "document_reference": f"NF-AP-DEMO-{suffix}-{i:03d}-{n}", "notes": f"Parcela AP {n}/{parts}"})
                confirmed = confirm_purchase(db, purchase["id"], PurchaseConfirmPayload(**{"reason": "Confirmação automática pelo super stress demo.", "installments": installments}))
                purchases.append(confirmed["purchase"])
                for payable in confirmed["payables"]:
                    payables_generated.append(payable)
                    collect("payables", payable)
            _assert(len(purchases) == purchases_count, "Quantidade de compras confirmadas diverge do solicitado.")
            _assert(len(payables_generated) >= purchases_count, "Compras deveriam gerar títulos a pagar.")
            return {"confirmed_purchases": len(purchases), "payable_titles": len(payables_generated), "payables_total_amount": _money_str(sum((_money(row["net_amount"]) for row in payables_generated), Decimal("0.00")))}

        _case(results, "06_purchases_expenses_generate_accounts_payable", "Cria compras/despesas de vários tipos e gera contas a pagar por parcelas.", case_06_purchases_generate_payables)

        def case_07_pay_payables() -> dict[str, Any]:
            payables = list_payables(db, company_id=need("company_id"), limit=500)
            paid_count = 0
            partial_count = 0
            for i, title in enumerate(payables):
                if title["status"] in {"paid", "cancelled", "written_off"}:
                    continue
                if i % 4 == 3:
                    continue
                open_amount = _money(title["open_amount"])
                if open_amount <= Decimal("0.00"):
                    continue
                partial = i % 5 == 2 and open_amount > Decimal("50.00")
                paid = (open_amount / Decimal("2")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) if partial else open_amount
                discount = Decimal("5.00") if partial and paid + Decimal("5.00") <= open_amount else Decimal("0.00")
                interest = Decimal("2.25") if i % 6 == 0 else Decimal("0.00")
                fee = Decimal("1.10") if i % 3 == 0 else Decimal("0.00")
                pay_payable(db, PayablePaymentCreate(**{"company_id": need("company_id"), "financial_title_id": title["id"], "financial_account_id": need("main_bank_id"), "payment_date": (today - timedelta(days=i % 4)).isoformat(), "paid_amount": _money_str(paid), "discount_amount": _money_str(discount), "interest_amount": _money_str(interest), "penalty_amount": "0.00", "fee_amount": _money_str(fee), "source_type": "manual", "source_id": f"DEMO-AP-PAY-{suffix}-{i}", "evidence_reference": f"COMPROVANTE-AP-DEMO-{suffix}-{i}", "notes": "Pagamento automático criado pelo super stress demo."}))
                paid_count += 1
                if partial:
                    partial_count += 1
            balances = list_account_balances(db, company_id=need("company_id"))
            _assert(paid_count > 0, "Nenhum título a pagar foi pago.")
            return {"paid_payables": paid_count, "partial_payables": partial_count, "account_balances": balances}

        _case(results, "07_payables_payments_cash_outflows", "Paga parte das contas a pagar, gerando baixas, movimentos de saída e saldo interno atualizado.", case_07_pay_payables)

        def case_08_reconciliation_with_exact_divergent_unmatched_lines() -> dict[str, Any]:
            movements = list_movements(db, company_id=need("company_id"), reconciliation_status="pending", limit=500)
            candidate_movements = [row for row in movements if row["financial_account_id"] == need("main_bank_id")]
            exact_targets = candidate_movements[: min(18, len(candidate_movements))]
            if len(exact_targets) < 2:
                raise AssertionError("Movimentos pendentes insuficientes para conciliação.")
            lines_payload = []
            for i, movement in enumerate(exact_targets):
                lines_payload.append({"external_id": f"DEMO-STMT-EXACT-{suffix}-{i}", "line_date": movement["movement_date"], "direction": movement["direction"], "amount": movement["amount"], "description": f"Extrato demo para {movement['description'] or movement['id']}", "bank_reference": f"BANK-DEMO-{suffix}-{i}"})
            divergent_movement = exact_targets[-1]
            divergent_amount = _money(divergent_movement["amount"]) + Decimal("0.37")
            lines_payload.append({"external_id": f"DEMO-STMT-DIV-{suffix}", "line_date": divergent_movement["movement_date"], "direction": divergent_movement["direction"], "amount": _money_str(divergent_amount), "description": "Linha divergente controlada para testar tolerância", "bank_reference": f"BANK-DIV-{suffix}"})
            lines_payload.append({"external_id": f"DEMO-STMT-UNMATCHED-IN-{suffix}", "line_date": today.isoformat(), "direction": "inflow", "amount": "77.77", "description": "Depósito externo sem movimento interno", "bank_reference": f"UNMATCHED-IN-{suffix}"})
            lines_payload.append({"external_id": f"DEMO-STMT-UNMATCHED-OUT-{suffix}", "line_date": today.isoformat(), "direction": "outflow", "amount": "33.33", "description": "Tarifa externa ainda sem lançamento interno", "bank_reference": f"UNMATCHED-OUT-{suffix}"})
            imported = import_statement(db, BankStatementImportCreate(**{"company_id": need("company_id"), "financial_account_id": need("main_bank_id"), "source_type": "manual", "source_id": f"DEMO-STMT-IMPORT-{suffix}", "file_name": f"extrato-demo-{suffix}.csv", "statement_start_date": (today - timedelta(days=10)).isoformat(), "statement_end_date": (today + timedelta(days=10)).isoformat(), "opening_balance_amount": "25000.00", "closing_balance_amount": None, "notes": "Extrato sintético com linhas exatas, divergentes e pendentes.", "lines": lines_payload}))
            line_by_external = {line["external_id"]: line for line in imported["lines"]}
            exact_matches = 0
            for i, movement in enumerate(exact_targets[:-1]):
                line = line_by_external[f"DEMO-STMT-EXACT-{suffix}-{i}"]
                confirm_match(db, ReconciliationMatchCreate(**{"company_id": need("company_id"), "statement_line_id": line["id"], "financial_movement_id": movement["id"], "match_type": "manual"}))
                exact_matches += 1
            div_line = line_by_external[f"DEMO-STMT-DIV-{suffix}"]
            div_match = confirm_match(db, ReconciliationMatchCreate(**{"company_id": need("company_id"), "statement_line_id": div_line["id"], "financial_movement_id": divergent_movement["id"], "match_type": "forced", "tolerance_amount": "1.00", "allow_difference": True, "confirmation_reason": "Divergência controlada de centavos para stress demo."}))
            matches = list_reconciliation_matches(db, company_id=need("company_id"), limit=500)
            lines = list_statement_lines(db, company_id=need("company_id"), limit=500)
            return {"statement_import_id": imported["statement_import"]["id"], "imported_lines": len(imported["lines"]), "exact_matches": exact_matches, "divergent_match_id": div_match["match"]["id"], "matches_total": len(matches), "statement_lines_total": len(lines)}

        _case(results, "08_bank_statement_reconciliation_exact_divergent_unmatched", "Importa extrato, concilia movimentos exatos, força uma divergência justificada e deixa pendências controladas.", case_08_reconciliation_with_exact_divergent_unmatched_lines)

        def case_09_cash_flow_dashboard_views() -> dict[str, Any]:
            from app.modules.cash_flow.service import get_cash_flow_accounts, get_cash_flow_daily, get_cash_flow_pending, get_cash_flow_reconciliation_status, get_cash_flow_summary
            start = today - timedelta(days=20)
            end = today + timedelta(days=45)
            summary = get_cash_flow_summary(db, company_id=need("company_id"), start_date=start, end_date=end)
            daily = get_cash_flow_daily(db, company_id=need("company_id"), start_date=start, end_date=end)
            accounts = get_cash_flow_accounts(db, company_id=need("company_id"), start_date=start, end_date=end)
            pending = get_cash_flow_pending(db, company_id=need("company_id"), start_date=start, end_date=end, limit=50)
            recon = get_cash_flow_reconciliation_status(db, company_id=need("company_id"), start_date=start, end_date=end)
            realized_outflow_from_daily = sum((_money(row["paid_amount"]) for row in daily), Decimal("0.00"))
            _assert(_money(summary["realized_inflow_amount"]) > Decimal("0.00"), "Fluxo deve ter entradas realizadas.")
            _assert(_money(summary["realized_outflow_amount"]) > Decimal("0.00"), "Fluxo deve ter saídas realizadas.")
            _assert(realized_outflow_from_daily > Decimal("0.00"), "Linha diária deve separar pagamentos realizados.")
            _assert(summary["financial_account_count"] >= 3, "Resumo deve enxergar múltiplas contas financeiras.")
            return {"summary": summary, "daily_rows": len(daily), "accounts": len(accounts), "pending_counts": {key: len(value) for key, value in pending.items() if isinstance(value, list)}, "reconciliation_status": recon}

        _case(results, "09_cash_flow_reads_real_demo_flow", "Fluxo de caixa lê AR, AP, baixas, movimentos, contas, extratos e conciliações sem criar fatos artificiais.", case_09_cash_flow_dashboard_views)

        def case_10_negative_safety_guards() -> dict[str, Any]:
            if not collections["products"]:
                raise AssertionError("Pré-requisito não criado: products. Verifique os casos de catálogo/estoque.")
            if not collections["customers"]:
                raise AssertionError("Pré-requisito não criado: customers. Verifique o caso de participantes.")
            product = collections["products"][0]
            customer = collections["customers"][0]
            too_large_sale = create_sale(db, SaleCreate(**{"company_id": need("company_id"), "participant_id": customer["id"], "sale_type": "product", "origin": "manual", "operation_nature": "normal_sale", "issue_date": today.isoformat(), "competency_date": today.isoformat(), "notes": "Venda inválida para testar estoque negativo bloqueado.", "payment_plans": [{"payment_method_code": "pix", "amount": _money_str(_money(product["financial_settings"]["default_sale_price"]) * Decimal("99999")), "due_date": today.isoformat(), "installments": 1}], "items": [{"item_id": product["id"], "description": product["name"], "quantity": "99999", "unit": product["unit"], "unit_price": product["financial_settings"]["default_sale_price"]}]}))
            oversell_blocked = _expect_error(lambda: confirm_sale(db, too_large_sale["id"], SaleStatusChange(reason="Deve falhar por estoque insuficiente.")), "estoque")
            payables = list_payables(db, company_id=need("company_id"), limit=500)
            open_payable = next((row for row in payables if row["status"] not in {"paid", "cancelled", "written_off"} and _money(row["open_amount"]) > 0), None)
            if open_payable is None:
                raise AssertionError("Nenhum AP aberto para teste de overpayment.")
            overpay_blocked = _expect_error(lambda: pay_payable(db, PayablePaymentCreate(**{"company_id": need("company_id"), "financial_title_id": open_payable["id"], "financial_account_id": need("main_bank_id"), "payment_date": today.isoformat(), "paid_amount": _money_str(_money(open_payable["open_amount"]) + Decimal("999.99")), "source_type": "manual", "source_id": f"DEMO-OVERPAY-{suffix}"})), "excede")
            cross_company_supplier_blocked = _expect_error(lambda: create_purchase_draft(db, PurchaseCreate(**{"company_id": need("company_id"), "participant_id": need("other_supplier_id"), "purchase_type": "expense", "origin": "manual", "issue_date": today.isoformat(), "invoice_total_amount": "10.00", "items": [{"description": "Fornecedor de outra empresa", "quantity": "1", "unit": "UN", "unit_cost": "10.00"}]})), "não encontrado")
            return {"oversell_blocked": oversell_blocked, "overpay_blocked": overpay_blocked, "cross_company_supplier_blocked": cross_company_supplier_blocked}

        _case(results, "10_safety_guards_overstock_overpayment_cross_company", "Força erros controlados para validar estoque, overpayment e isolamento multiempresa.", case_10_negative_safety_guards)

        def case_11_consistency_scans() -> dict[str, Any]:
            company_id = need("company_id")
            scans: dict[str, Any] = {}
            count_sql = {
                "orphan_sale_items": "select count(*) from sale_items si left join sales s on s.id = si.sale_id where si.company_id = :company_id and s.id is null",
                "orphan_sale_financial_links": "select count(*) from sale_financial_links sfl left join financial_titles ft on ft.id = sfl.financial_title_id where sfl.company_id = :company_id and ft.id is null",
                "orphan_purchase_items": "select count(*) from purchase_items pi left join purchases p on p.id = pi.purchase_id where pi.company_id = :company_id and p.id is null",
                "orphan_purchase_financial_links": "select count(*) from purchase_financial_links pfl left join financial_titles ft on ft.id = pfl.financial_title_id where pfl.company_id = :company_id and ft.id is null",
                "orphan_settlements": "select count(*) from settlements s left join financial_titles ft on ft.id = s.financial_title_id where s.company_id = :company_id and ft.id is null",
                "orphan_movements": "select count(*) from financial_movements fm left join financial_accounts fa on fa.id = fm.financial_account_id where fm.company_id = :company_id and fa.id is null",
                "orphan_reconciliation_matches": "select count(*) from reconciliation_matches rm left join bank_statement_lines bsl on bsl.id = rm.statement_line_id left join financial_movements fm on fm.id = rm.financial_movement_id where rm.company_id = :company_id and (bsl.id is null or fm.id is null)",
                "negative_financial_titles": "select count(*) from financial_titles where company_id = :company_id and (net_amount < 0 or paid_amount < 0 or open_amount < 0)",
                "settlement_movement_amount_mismatch": "select count(*) from settlements s join financial_movements fm on fm.settlement_id = s.id where s.company_id = :company_id and abs(cast(s.movement_amount as numeric) - cast(fm.amount as numeric)) > 0.01",
            }
            for name, sql in count_sql.items():
                count = int(db.execute(text(sql), {"company_id": company_id}).scalar_one() or 0)
                scans[name] = count
                if count != 0:
                    inconsistencies.append({"code": name, "severity": "high", "count": count})

            balance_rows = db.execute(text("""
                select fa.id, fa.name, fa.opening_balance_amount,
                       coalesce(b.current_balance_amount, fa.opening_balance_amount) as stored_balance,
                       fa.opening_balance_amount
                       + coalesce(sum(case when fm.direction = 'inflow' and fm.status = 'posted' then fm.amount when fm.direction = 'outflow' and fm.status = 'posted' then -fm.amount else 0 end), 0) as calculated_balance
                from financial_accounts fa
                left join financial_account_balances b on b.financial_account_id = fa.id and b.company_id = fa.company_id
                left join financial_movements fm on fm.financial_account_id = fa.id and fm.company_id = fa.company_id
                where fa.company_id = :company_id and fa.deleted_at is null
                group by fa.id, fa.name, fa.opening_balance_amount, b.current_balance_amount
                order by fa.name
            """), {"company_id": company_id}).mappings().all()
            balance_mismatches = []
            for row in balance_rows:
                stored = _money(row["stored_balance"])
                calculated = _money(row["calculated_balance"])
                if abs(stored - calculated) > Decimal("0.01"):
                    balance_mismatches.append({"financial_account_id": row["id"], "name": row["name"], "stored": _money_str(stored), "calculated": _money_str(calculated), "difference": _money_str(stored - calculated)})
            scans["balance_mismatches"] = balance_mismatches
            if balance_mismatches:
                inconsistencies.append({"code": "balance_mismatches", "severity": "critical", "items": balance_mismatches})

            sales_mismatch = db.execute(text("""
                select count(*) from (
                    select s.id, s.receivable_total_amount, coalesce(sum(ft.net_amount), 0) as titles_total
                    from sales s
                    left join financial_titles ft on ft.sale_id = s.id and ft.direction = 'receivable' and ft.deleted_at is null
                    where s.company_id = :company_id and s.status = 'confirmed'
                    group by s.id, s.receivable_total_amount
                    having abs(cast(s.receivable_total_amount as numeric) - coalesce(sum(ft.net_amount), 0)) > 0.01
                ) z
            """), {"company_id": company_id}).scalar_one()
            purchases_mismatch = db.execute(text("""
                select count(*) from (
                    select p.id, p.payable_total_amount, coalesce(sum(ft.net_amount), 0) as titles_total
                    from purchases p
                    left join purchase_financial_links pfl on pfl.purchase_id = p.id and pfl.company_id = p.company_id
                    left join financial_titles ft on ft.id = pfl.financial_title_id and ft.direction = 'payable' and ft.deleted_at is null
                    where p.company_id = :company_id and p.status = 'confirmed'
                    group by p.id, p.payable_total_amount
                    having abs(cast(p.payable_total_amount as numeric) - coalesce(sum(ft.net_amount), 0)) > 0.01
                ) z
            """), {"company_id": company_id}).scalar_one()
            scans["confirmed_sales_receivable_total_mismatches"] = int(sales_mismatch or 0)
            scans["confirmed_purchases_payable_total_mismatches"] = int(purchases_mismatch or 0)
            if sales_mismatch:
                inconsistencies.append({"code": "confirmed_sales_receivable_total_mismatches", "severity": "high", "count": int(sales_mismatch)})
            if purchases_mismatch:
                inconsistencies.append({"code": "confirmed_purchases_payable_total_mismatches", "severity": "high", "count": int(purchases_mismatch)})

            counts = db.execute(text("""
                select
                  (select count(*) from participants where company_id = :company_id and deleted_at is null) as participants,
                  (select count(*) from catalog_items where company_id = :company_id and deleted_at is null) as catalog_items,
                  (select count(*) from sales where company_id = :company_id) as sales,
                  (select count(*) from purchases where company_id = :company_id) as purchases,
                  (select count(*) from financial_titles where company_id = :company_id and deleted_at is null and direction = 'receivable') as receivables,
                  (select count(*) from financial_titles where company_id = :company_id and deleted_at is null and direction = 'payable') as payables,
                  (select count(*) from settlements where company_id = :company_id and status = 'active') as settlements,
                  (select count(*) from financial_movements where company_id = :company_id and status = 'posted') as movements,
                  (select count(*) from bank_statement_lines where company_id = :company_id) as statement_lines,
                  (select count(*) from reconciliation_matches where company_id = :company_id and status in ('confirmed', 'confirmed_with_difference')) as matches
            """), {"company_id": company_id}).mappings().one()
            scans["entity_counts"] = dict(counts)
            _assert(scans["entity_counts"]["sales"] >= sales_count, "Contagem de vendas abaixo do volume solicitado.")
            _assert(scans["entity_counts"]["purchases"] >= purchases_count, "Contagem de compras abaixo do volume solicitado.")
            _assert(scans["entity_counts"]["movements"] > 0, "Stress deveria criar movimentos financeiros.")
            return scans

        _case(results, "11_relational_integrity_and_inconsistency_scan", "Varre órfãos, saldos, links venda/AR, compra/AP e divergências estruturais.", case_11_consistency_scans)

        def case_12_demo_opening_summary() -> dict[str, Any]:
            company_id = need("company_id")
            balances = list_account_balances(db, company_id=company_id)
            payables_summary = get_purchases_payables_summary(db, company_id=company_id)
            receivables = list_receivables(db, company_id=company_id, limit=500)
            payables = list_payables(db, company_id=company_id, limit=500)
            sales = list_sales(db, company_id=company_id, limit=500)
            purchases = payables_summary
            stock_balances = list_stock_balances(db, company_id=company_id, limit=500)
            return {
                "demo_company_id": company_id,
                "demo_company_name_hint": f"DEMO Kovir {suffix}",
                "open_this_company_in_frontend": "Selecione a empresa demo pelo nome/ID no seletor de empresa ativa.",
                "balances": balances,
                "receivable_status_counts": dict(sorted({status: sum(1 for row in receivables if row["status"] == status) for status in {row["status"] for row in receivables}}.items())),
                "payable_status_counts": dict(sorted({status: sum(1 for row in payables if row["status"] == status) for status in {row["status"] for row in payables}}.items())),
                "sales_count": len(sales),
                "payables_summary": purchases,
                "stock_balance_count": len(stock_balances),
                "inconsistency_count": len(inconsistencies),
            }

        _case(results, "12_demo_data_ready_for_frontend", "Consolida IDs e resumo para abrir a empresa demo no frontend com dados reais.", case_12_demo_opening_summary)

    finally:
        failed = sum(1 for result in results if result.status == "FAIL")
        passed = sum(1 for result in results if result.status == "PASS")
        report = {
            "status": "PASS" if failed == 0 and not inconsistencies else "FAIL",
            "database_url": os.environ.get("DATABASE_URL", "configured_by_app_settings"),
            "sqlite_smoke_mode": sqlite_mode,
            "summary": {"passed": passed, "failed": failed, "total": len(results), "inconsistencies": len(inconsistencies)},
            "ids": ids,
            "collections_summary": {key: len(value) for key, value in collections.items()},
            "inconsistencies": inconsistencies,
            "cases": [result.__dict__ for result in results],
        }
        db.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sales", type=int, default=24, help="Quantidade de vendas demo a criar.")
    parser.add_argument("--purchases", type=int, default=16, help="Quantidade de compras/despesas demo a criar.")
    parser.add_argument("--sqlite-smoke-db", default=None, help="Caminho opcional para banco SQLite isolado de smoke test.")
    parser.add_argument("--output", default="stress_real_company_financial_demo_report.json", help="Arquivo JSON de saída.")
    args = parser.parse_args()
    try:
        report = run(sales_count=max(1, args.sales), purchases_count=max(1, args.purchases), sqlite_smoke_db=args.sqlite_smoke_db)
    except Exception as exc:  # noqa: BLE001
        report = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
