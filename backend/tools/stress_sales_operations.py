r"""
Kovir ERP — Stress Test de Operações de Venda
================================================

Objetivo:
- Forçar cenários complexos de vendas no backend real do Kovir ERP.
- Validar desconto em valor e percentual.
- Validar múltiplas formas de pagamento.
- Validar natureza de operação com/sem valor a receber.
- Validar bloqueios esperados para payloads inválidos.
- Detectar riscos de integridade antes de avançar para Estoque / Contas a Receber.

Uso esperado no Windows, com backend rodando em http://127.0.0.1:8000:

    cd C:\Users\Rafael Stevanato\Desktop\kovir-erp\backend
    .\.venv\Scripts\Activate.ps1
    python .\tools\stress_sales_operations.py

Variáveis opcionais:
    $env:KOVIR_BASE_URL="http://127.0.0.1:8000"
    $env:KOVIR_COMPANY_ID="emp_..."

Observação:
Este script CRIA dados de teste no banco de desenvolvimento.
Não rode em base real/produção.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib import error, parse, request

MONEY = Decimal("0.01")
DEFAULT_BASE_URL = os.getenv("KOVIR_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_COMPANY_ID = os.getenv("KOVIR_COMPANY_ID", "emp_93f95b63-8ed3-4d0c-b564-0c1c6de62887")


@dataclass
class CaseResult:
    name: str
    expected: str
    status: str
    detail: str = ""
    sale_id: str | None = None
    warnings: list[str] = field(default_factory=list)


class KovirApiError(Exception):
    def __init__(self, status: int, payload: Any, raw: str = ""):
        self.status = status
        self.payload = payload
        self.raw = raw
        super().__init__(f"HTTP {status}: {payload or raw}")


class KovirClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str, query: dict[str, Any] | None = None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url += "?" + parse.urlencode(clean)
        return url

    def request(self, method: str, path: str, body: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": f"stress-{int(time.time() * 1000)}",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(self._url(path, query), data=data, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else None
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw else None
            except Exception:
                payload = None
            raise KovirApiError(exc.code, payload, raw) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Não foi possível conectar ao backend em {self.base_url}: {exc}") from exc

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, query=query)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("POST", path, body=body)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PATCH", path, body=body)


def qmoney(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def money_str(value: Decimal | str | int | float) -> str:
    return format(qmoney(value), "f")


def unwrap(resp: Any) -> Any:
    if not isinstance(resp, dict):
        raise AssertionError(f"Resposta inválida: {resp!r}")
    if resp.get("success") is not True:
        raise AssertionError(f"API retornou success != true: {resp}")
    return resp.get("data")


def today(offset_days: int = 0) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def unique_suffix() -> str:
    return str(int(time.time() * 1000))[-10:]


class StressContext:
    def __init__(self, api: KovirClient, company_id: str | None):
        self.api = api
        self.company_id = company_id
        self.customer_id: str | None = None
        self.product_id: str | None = None
        self.service_id: str | None = None
        self.product_fclass_id: str | None = None
        self.service_fclass_id: str | None = None
        self.product_price = Decimal("99.90")
        self.service_price = Decimal("150.00")
        self.created_sales: list[str] = []
        self.suffix = unique_suffix()

    def setup(self):
        self._health_check()
        self._ensure_company()
        self._ensure_payment_methods_and_natures()
        self._create_customer()
        self._create_catalog_items()
        self._create_fiscal_classifications()

    def _health_check(self):
        data = unwrap(self.api.get("/system/database-health"))
        if not data.get("online"):
            raise RuntimeError(f"Banco não está online: {data}")

    def _ensure_company(self):
        if self.company_id:
            try:
                unwrap(self.api.get(f"/companies/{self.company_id}"))
                return
            except Exception:
                print(f"[setup] Empresa {self.company_id} não encontrada. Vou tentar usar/criar outra empresa.")
        companies = unwrap(self.api.get("/companies", {"limit": 1, "offset": 0}))
        if companies:
            self.company_id = companies[0]["id"]
            return
        payload = {
            "legal_name": f"STVN Stress Test LTDA {self.suffix}",
            "trade_name": "STVN Stress Test",
            "cnpj": f"11222333{self.suffix[-6:]}",
            "email": "stress@example.com",
            "phone": "14999999999",
            "responsible_name": "Operador Stress Test",
            "status": "active",
            "address": {
                "street": "Rua Teste",
                "number": "1",
                "district": "Centro",
                "city": "Bauru",
                "state": "SP",
                "zip_code": "17000000",
            },
            "fiscal_settings": {
                "tax_regime": "simples_nacional",
                "main_cnae": "6201500",
                "fiscal_environment": "none",
                "uses_fiscal_control": True,
                "prepared_for_tax_reform": True,
            },
            "financial_settings": {
                "currency": "BRL",
                "monthly_closing_day": 31,
                "uses_accounts_receivable": True,
                "uses_accounts_payable": True,
                "uses_cash_control": True,
            },
            "operational_settings": {
                "timezone": "America/Sao_Paulo",
                "date_format": "YYYY-MM-DD",
                "money_format": "BRL",
                "allow_manual_entries": True,
                "allow_imports": True,
            },
        }
        self.company_id = unwrap(self.api.post("/companies", payload))["id"]

    def _ensure_payment_methods_and_natures(self):
        unwrap(self.api.get("/sales/payment-methods", {"company_id": self.company_id}))
        unwrap(self.api.get("/sales/operation-natures", {"company_id": self.company_id}))

    def _create_customer(self):
        doc_suffix = self.suffix[-6:]
        payload = {
            "company_id": self.company_id,
            "participant_type": "customer",
            "person_type": "company",
            "name": f"Cliente Stress Test {self.suffix} LTDA",
            "trade_name": f"Cliente Stress {self.suffix}",
            "document": f"12345678{doc_suffix}",
            "email": f"cliente.stress.{self.suffix}@teste.com",
            "phone": "14988888888",
            "status": "active",
            "address": {
                "street": "Rua Cliente Stress",
                "number": "200",
                "complement": None,
                "district": "Centro",
                "city": "Bauru",
                "state": "SP",
                "zip_code": "17000000",
                "country": "BR",
                "ibge_municipality_code": None,
            },
            "fiscal_settings": {
                "taxpayer_type": "taxpayer",
                "tax_regime": "simples_nacional",
                "main_cnae": None,
                "state_registration": None,
                "municipal_registration": None,
                "suframa_registration": None,
                "is_foreign": False,
                "fiscal_notes": None,
            },
            "financial_settings": {
                "default_payment_method": "pix",
                "default_payment_terms": "a_vista",
                "bank_name": None,
                "bank_branch": None,
                "bank_account": None,
                "pix_key": f"cliente.stress.{self.suffix}@teste.com",
                "credit_limit": "10000",
                "payment_priority": "normal",
            },
            "notes": "Cliente criado automaticamente pelo stress test de vendas.",
        }
        self.customer_id = unwrap(self.api.post("/participants", payload))["id"]

    def _create_catalog_items(self):
        product_payload = {
            "company_id": self.company_id,
            "item_type": "product",
            "name": f"Produto Stress Test {self.suffix}",
            "description": "Produto criado automaticamente pelo stress test.",
            "sku": f"STRESS-PROD-{self.suffix}",
            "barcode": None,
            "unit": "UN",
            "status": "active",
            "origin": "manual",
            "financial_settings": {
                "default_sale_price": money_str(self.product_price),
                "default_cost_price": "55.25",
                "allow_price_override": False,
            },
            "fiscal_settings": {
                "ncm": "21069090",
                "nbs": None,
                "cfop_default": "5102",
                "cst_ibs_cbs": "000",
                "cclass_trib": "000001",
                "subject_to_tax": True,
            },
            "inventory_settings": {
                "track_stock": False,
                "stock_unit": "UN",
                "minimum_stock": "0",
                "allow_negative_stock": False,
            },
            "notes": "Produto do stress test.",
        }
        service_payload = {
            "company_id": self.company_id,
            "item_type": "service",
            "name": f"Serviço Stress Test {self.suffix}",
            "description": "Serviço criado automaticamente pelo stress test.",
            "sku": f"STRESS-SERV-{self.suffix}",
            "barcode": None,
            "unit": "SERV",
            "status": "active",
            "origin": "manual",
            "financial_settings": {
                "default_sale_price": money_str(self.service_price),
                "default_cost_price": "30.00",
                "allow_price_override": False,
            },
            "fiscal_settings": {
                "ncm": None,
                "nbs": "123456789",
                "cfop_default": None,
                "cst_ibs_cbs": "000",
                "cclass_trib": "000001",
                "subject_to_tax": True,
            },
            "inventory_settings": {
                "track_stock": False,
                "stock_unit": None,
                "minimum_stock": None,
                "allow_negative_stock": False,
            },
            "notes": "Serviço do stress test.",
        }
        self.product_id = unwrap(self.api.post("/catalog/items", product_payload))["id"]
        self.service_id = unwrap(self.api.post("/catalog/items", service_payload))["id"]

    def _create_fiscal_classifications(self):
        product_payload = {
            "company_id": self.company_id,
            "name": f"Classificação Fiscal Produto Stress {self.suffix}",
            "description": "Classificação fiscal criada pelo stress test.",
            "item_type": "product",
            "tax_regime": "simples_nacional",
            "ncm": "21069090",
            "cfop_default": "5102",
            "cst_ibs_cbs": "000",
            "cclass_trib": "000001",
            "subject_to_icms": True,
            "subject_to_iss": False,
            "subject_to_pis_cofins": True,
            "subject_to_ibs_cbs": True,
            "subject_to_is": False,
            "valid_from": today(-1),
            "status": "active",
            "source": "manual",
            "source_reference": "stress_test",
            "notes": "Fiscal class do stress test.",
        }
        service_payload = {
            "company_id": self.company_id,
            "name": f"Classificação Fiscal Serviço Stress {self.suffix}",
            "description": "Classificação fiscal de serviço criada pelo stress test.",
            "item_type": "service",
            "tax_regime": "simples_nacional",
            "nbs": "123456789",
            "cst_ibs_cbs": "000",
            "cclass_trib": "000001",
            "subject_to_icms": False,
            "subject_to_iss": True,
            "subject_to_pis_cofins": True,
            "subject_to_ibs_cbs": True,
            "subject_to_is": False,
            "valid_from": today(-1),
            "status": "active",
            "source": "manual",
            "source_reference": "stress_test",
            "notes": "Fiscal class de serviço do stress test.",
        }
        self.product_fclass_id = unwrap(self.api.post("/fiscal/classifications", product_payload))["id"]
        self.service_fclass_id = unwrap(self.api.post("/fiscal/classifications", service_payload))["id"]

    def base_sale_payload(
        self,
        *,
        sale_type: str = "product",
        operation_nature: str = "normal_sale",
        operation_nature_reason: str | None = None,
        quantity: str = "2",
        item_discount_amount: str = "0",
        discount_type: str = "amount",
        discount_amount: str = "0",
        discount_percentage: str | None = None,
        discount_category: str | None = None,
        discount_reason: str | None = None,
        payment_plans: list[dict[str, Any]] | None = None,
        unit_price_override: str | None = None,
    ) -> dict[str, Any]:
        item_id = self.product_id if sale_type == "product" else self.service_id
        fclass_id = self.product_fclass_id if sale_type == "product" else self.service_fclass_id
        unit = "UN" if sale_type == "product" else "SERV"
        item = {
            "item_id": item_id,
            "fiscal_classification_id": fclass_id,
            "quantity": quantity,
            "unit": unit,
            "discount_amount": item_discount_amount,
            "freight_amount": "0",
            "tax_amount": "0",
        }
        if unit_price_override is not None:
            item["unit_price"] = unit_price_override
        payload = {
            "company_id": self.company_id,
            "participant_id": self.customer_id,
            "sale_type": sale_type,
            "origin": "manual",
            "operation_nature": operation_nature,
            "operation_nature_reason": operation_nature_reason,
            "issue_date": today(),
            "competency_date": today(),
            "discount_type": discount_type,
            "discount_amount": discount_amount,
            "discount_percentage": discount_percentage,
            "discount_category": discount_category,
            "discount_reason": discount_reason,
            "freight_amount": "0",
            "tax_amount": "0",
            "notes": f"Venda criada por stress test {self.suffix}",
            "items": [item],
            "payment_plans": payment_plans or [],
        }
        # Remove None to simulate frontend payloads cleaner.
        return {k: v for k, v in payload.items() if v is not None}


def sale_expectations(ctx: StressContext, payload: dict[str, Any]) -> dict[str, Decimal]:
    # Calcula expectativa considerando os produtos/serviços padrão criados pelo script.
    item = payload["items"][0]
    sale_type = payload["sale_type"]
    default_price = ctx.product_price if sale_type == "product" else ctx.service_price
    unit_price = Decimal(str(item.get("unit_price", default_price)))
    quantity = Decimal(str(item.get("quantity", "1")))
    gross = (unit_price * quantity).quantize(MONEY, rounding=ROUND_HALF_UP)
    item_discount = qmoney(item.get("discount_amount", "0"))
    item_total = gross - item_discount
    discount_type = payload.get("discount_type", "amount")
    if discount_type == "percentage":
        pct = Decimal(str(payload.get("discount_percentage") or "0"))
        header_discount = (gross * pct / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    else:
        header_discount = qmoney(payload.get("discount_amount", "0"))
    total = (item_total - header_discount).quantize(MONEY, rounding=ROUND_HALF_UP)
    operation = payload.get("operation_nature", "normal_sale")
    receivable = Decimal("0.00") if operation in {"bonus", "sample", "courtesy", "replacement"} else total
    invoice = total
    return {
        "subtotal_amount": gross,
        "discount_amount": (item_discount + header_discount).quantize(MONEY, rounding=ROUND_HALF_UP),
        "total_amount": total,
        "receivable_total_amount": receivable.quantize(MONEY, rounding=ROUND_HALF_UP),
        "invoice_total_amount": invoice.quantize(MONEY, rounding=ROUND_HALF_UP),
    }


def assert_sale_amounts(sale: dict[str, Any], expected: dict[str, Decimal]):
    for key, expected_value in expected.items():
        actual = qmoney(sale.get(key, "0"))
        if actual != expected_value:
            raise AssertionError(f"{key}: esperado {expected_value}, recebido {actual}")


def create_sale_success(ctx: StressContext, payload: dict[str, Any], *, confirm: bool = True) -> dict[str, Any]:
    sale = unwrap(ctx.api.post("/sales", payload))
    ctx.created_sales.append(sale["id"])
    assert sale["status"] == "draft", f"Venda deveria nascer draft, veio {sale['status']}"
    expected = sale_expectations(ctx, payload)
    assert_sale_amounts(sale, expected)
    expected_payment_total = expected["receivable_total_amount"]
    actual_plan_total = sum(qmoney(plan["amount"]) for plan in sale.get("payment_plans", []))
    if actual_plan_total != expected_payment_total:
        raise AssertionError(f"Plano de pagamento soma {actual_plan_total}, mas total a receber é {expected_payment_total}")
    if confirm:
        sale = unwrap(ctx.api.post(f"/sales/{sale['id']}/confirm", {"reason": "Confirmação via stress test."}))
        assert sale["status"] == "confirmed", f"Venda deveria estar confirmed, veio {sale['status']}"
    return sale


def create_sale_should_fail(ctx: StressContext, payload: dict[str, Any], *, expected_text: str | None = None):
    try:
        resp = ctx.api.post("/sales", payload)
    except KovirApiError as exc:
        blob = json.dumps(exc.payload, ensure_ascii=False) if exc.payload is not None else exc.raw
        if expected_text and expected_text.lower() not in blob.lower():
            raise AssertionError(f"Falhou, mas mensagem não contém {expected_text!r}. Resposta: {blob}")
        return
    if isinstance(resp, dict) and resp.get("success") is False:
        blob = json.dumps(resp, ensure_ascii=False)
        if expected_text and expected_text.lower() not in blob.lower():
            raise AssertionError(f"Falhou, mas mensagem não contém {expected_text!r}. Resposta: {blob}")
        return
    raise AssertionError(f"Venda inválida foi aceita: {resp}")


def run_case(results: list[CaseResult], name: str, expected: str, fn):
    print(f"\n[TESTE] {name}")
    try:
        result = fn()
        sale_id = result.get("id") if isinstance(result, dict) else None
        print(f"  OK — {expected}" + (f" | sale_id={sale_id}" if sale_id else ""))
        results.append(CaseResult(name=name, expected=expected, status="PASS", sale_id=sale_id))
    except Exception as exc:
        print(f"  FALHOU — {exc}")
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=str(exc)))


def run_expected_risk_case(results: list[CaseResult], name: str, fn):
    """Caso usado para detectar fragilidade de regra: se passar indevidamente, vira WARNING."""
    print(f"\n[RISCO] {name}")
    try:
        sale = fn()
        sale_id = sale.get("id") if isinstance(sale, dict) else None
        detail = "A API aceitou um cenário que deveria ser bloqueado por regra futura/segurança de domínio."
        print(f"  WARNING — {detail}" + (f" | sale_id={sale_id}" if sale_id else ""))
        results.append(CaseResult(name=name, expected="deveria bloquear", status="WARNING", detail=detail, sale_id=sale_id))
    except Exception as exc:
        print(f"  OK — bloqueado/recusado: {exc}")
        results.append(CaseResult(name=name, expected="deveria bloquear", status="PASS", detail="Bloqueado corretamente."))


def build_cases(ctx: StressContext):
    def normal_pix():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="2",
            payment_plans=[{"payment_method_code": "pix", "amount": "199.80", "due_date": today(), "installments": 1}],
        )
        return create_sale_success(ctx, payload)

    def amount_discount_split_pix_credit():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="2",
            discount_type="amount",
            discount_amount="19.80",
            discount_category="promotion",
            discount_reason="Promoção stress test valor fixo.",
            payment_plans=[
                {"payment_method_code": "pix", "amount": "80.00", "due_date": today(), "installments": 1},
                {"payment_method_code": "credit_card", "amount": "100.00", "due_date": today(30), "installments": 1},
            ],
        )
        return create_sale_success(ctx, payload)

    def percentage_discount_split_cash_debit():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="3",
            discount_type="percentage",
            discount_percentage="10",
            discount_category="coupon",
            discount_reason="Cupom percentual stress test.",
            payment_plans=[
                {"payment_method_code": "cash", "amount": "100.00", "due_date": today(), "installments": 1},
                {"payment_method_code": "debit_card", "amount": "169.73", "due_date": today(), "installments": 1},
            ],
        )
        return create_sale_success(ctx, payload)

    def service_percentage_boleto_transfer():
        payload = ctx.base_sale_payload(
            sale_type="service",
            quantity="2",
            discount_type="percentage",
            discount_percentage="12.5",
            discount_category="commercial_negotiation",
            discount_reason="Negociação comercial sobre serviço.",
            payment_plans=[
                {"payment_method_code": "boleto", "amount": "150.00", "due_date": today(7), "installments": 1},
                {"payment_method_code": "bank_transfer", "amount": "112.50", "due_date": today(), "installments": 1},
            ],
        )
        return create_sale_success(ctx, payload)

    def item_discount_plus_header_percentage():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="2",
            item_discount_amount="9.80",
            discount_type="percentage",
            discount_percentage="10",
            discount_category="manager_authorization",
            discount_reason="Desconto no item + desconto percentual autorizado.",
            payment_plans=[{"payment_method_code": "pix", "amount": "170.02", "due_date": today(), "installments": 1}],
        )
        return create_sale_success(ctx, payload)

    def bonus_without_payment():
        payload = ctx.base_sale_payload(
            sale_type="product",
            operation_nature="bonus",
            operation_nature_reason="Bonificação operacional stress test.",
            quantity="2",
            payment_plans=[],
        )
        sale = create_sale_success(ctx, payload)
        if qmoney(sale["receivable_total_amount"]) != Decimal("0.00"):
            raise AssertionError("Bonificação deveria ter receivable_total_amount = 0.00")
        return sale

    def default_payment_plan_compatibility():
        payload = ctx.base_sale_payload(sale_type="product", quantity="1", payment_plans=[])
        sale = create_sale_success(ctx, payload)
        if len(sale.get("payment_plans", [])) != 1:
            raise AssertionError("Sem payment_plans, backend deveria gerar plano padrão de compatibilidade.")
        if sale["payment_plans"][0]["payment_method_code"] != "pix":
            raise AssertionError("Plano padrão esperado era Pix.")
        return sale

    def failure_payment_sum_less():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="2",
            payment_plans=[{"payment_method_code": "pix", "amount": "100.00", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Soma das formas de pagamento")

    def failure_payment_sum_more():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="2",
            payment_plans=[{"payment_method_code": "pix", "amount": "250.00", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Soma das formas de pagamento")

    def failure_zero_payment():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            payment_plans=[{"payment_method_code": "pix", "amount": "0", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="maior que zero")

    def failure_percentage_over_100():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            discount_type="percentage",
            discount_percentage="150",
            discount_category="coupon",
            discount_reason="Percentual inválido.",
            payment_plans=[{"payment_method_code": "pix", "amount": "99.90", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Percentual")

    def failure_percentage_without_reason():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            discount_type="percentage",
            discount_percentage="10",
            discount_category="coupon",
            payment_plans=[{"payment_method_code": "pix", "amount": "89.91", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Motivo do desconto")

    def failure_amount_discount_without_category():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            discount_type="amount",
            discount_amount="10",
            discount_reason="Sem categoria.",
            payment_plans=[{"payment_method_code": "pix", "amount": "89.90", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Categoria")

    def failure_discount_bigger_than_total():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            discount_type="amount",
            discount_amount="9999",
            discount_category="promotion",
            discount_reason="Desconto maior que venda.",
            payment_plans=[{"payment_method_code": "pix", "amount": "0.01", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Total da venda não pode ser negativo")

    def failure_bonus_with_payment():
        payload = ctx.base_sale_payload(
            sale_type="product",
            operation_nature="bonus",
            operation_nature_reason="Bonificação não deve receber pagamento.",
            quantity="1",
            payment_plans=[{"payment_method_code": "pix", "amount": "99.90", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Venda sem valor a receber")

    def failure_product_sale_with_service_item():
        payload = ctx.base_sale_payload(sale_type="product", quantity="1", payment_plans=[{"payment_method_code": "pix", "amount": "150.00", "due_date": today(), "installments": 1}])
        payload["items"][0]["item_id"] = ctx.service_id
        payload["items"][0]["fiscal_classification_id"] = ctx.service_fclass_id
        payload["items"][0]["unit"] = "SERV"
        create_sale_should_fail(ctx, payload, expected_text="não aceita item de outro tipo")

    def failure_invalid_payment_code():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            payment_plans=[{"payment_method_code": "bitcoin", "amount": "99.90", "due_date": today(), "installments": 1}],
        )
        create_sale_should_fail(ctx, payload, expected_text="Forma de pagamento inválida")

    def failure_confirm_twice():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            payment_plans=[{"payment_method_code": "pix", "amount": "99.90", "due_date": today(), "installments": 1}],
        )
        sale = create_sale_success(ctx, payload, confirm=True)
        try:
            ctx.api.post(f"/sales/{sale['id']}/confirm", {"reason": "Confirmar novamente."})
        except KovirApiError as exc:
            blob = json.dumps(exc.payload, ensure_ascii=False)
            if "Apenas vendas em rascunho" not in blob:
                raise AssertionError(f"Falha inesperada ao confirmar duas vezes: {blob}")
            return sale
        raise AssertionError("Confirmação dupla foi aceita indevidamente.")

    def failure_update_confirmed_sale():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            payment_plans=[{"payment_method_code": "pix", "amount": "99.90", "due_date": today(), "installments": 1}],
        )
        sale = create_sale_success(ctx, payload, confirm=True)
        try:
            ctx.api.patch(f"/sales/{sale['id']}", {"notes": "Tentativa de alterar confirmada."})
        except KovirApiError as exc:
            blob = json.dumps(exc.payload, ensure_ascii=False)
            if "Apenas vendas em rascunho" not in blob:
                raise AssertionError(f"Falha inesperada ao alterar confirmada: {blob}")
            return sale
        raise AssertionError("Alteração de venda confirmada foi aceita indevidamente.")

    def risk_unit_price_override():
        payload = ctx.base_sale_payload(
            sale_type="product",
            quantity="1",
            unit_price_override="1.00",
            payment_plans=[{"payment_method_code": "pix", "amount": "1.00", "due_date": today(), "installments": 1}],
        )
        return create_sale_success(ctx, payload)

    return [
        ("Venda produto normal com Pix", "criar e confirmar venda simples", normal_pix),
        ("Venda produto com desconto em valor e Pix + Crédito", "total e soma dos pagamentos devem bater", amount_discount_split_pix_credit),
        ("Venda produto com 10% de desconto e Dinheiro + Débito", "backend recalcula desconto percentual", percentage_discount_split_cash_debit),
        ("Venda serviço com 12,5% e Boleto + Transferência", "serviço usa fluxo próprio e múltiplas formas", service_percentage_boleto_transfer),
        ("Desconto no item + desconto percentual no cabeçalho", "desconto total composto deve bater", item_discount_plus_header_percentage),
        ("Bonificação sem pagamento", "receivable_total_amount deve ser zero e sem plano positivo", bonus_without_payment),
        ("Compatibilidade: venda sem payment_plans", "backend gera Pix automático", default_payment_plan_compatibility),
        ("ERRO esperado: pagamento menor que total", "deve bloquear soma divergente", failure_payment_sum_less),
        ("ERRO esperado: pagamento maior que total", "deve bloquear soma divergente", failure_payment_sum_more),
        ("ERRO esperado: pagamento zero", "deve bloquear valor zero", failure_zero_payment),
        ("ERRO esperado: desconto percentual > 100", "deve bloquear percentual inválido", failure_percentage_over_100),
        ("ERRO esperado: desconto percentual sem motivo", "deve exigir motivo", failure_percentage_without_reason),
        ("ERRO esperado: desconto valor sem categoria", "deve exigir categoria", failure_amount_discount_without_category),
        ("ERRO esperado: desconto maior que total", "deve bloquear total negativo", failure_discount_bigger_than_total),
        ("ERRO esperado: bonificação com pagamento", "deve bloquear pagamento positivo", failure_bonus_with_payment),
        ("ERRO esperado: venda produto com serviço", "deve bloquear item incompatível", failure_product_sale_with_service_item),
        ("ERRO esperado: forma de pagamento inexistente", "deve bloquear código inválido", failure_invalid_payment_code),
        ("ERRO esperado: confirmar venda duas vezes", "deve bloquear segunda confirmação", failure_confirm_twice),
        ("ERRO esperado: alterar venda confirmada", "deve bloquear atualização após confirmação", failure_update_confirmed_sale),
        ("RISCO: override de preço unitário via API", "deveria ser bloqueado pelo backend, não só pela tela", risk_unit_price_override),
    ]


def write_report(path: str, ctx: StressContext, results: list[CaseResult]):
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warnings = sum(1 for r in results if r.status == "WARNING")
    payload = {
        "generated_at_epoch": int(time.time()),
        "base_url": ctx.api.base_url,
        "company_id": ctx.company_id,
        "customer_id": ctx.customer_id,
        "product_id": ctx.product_id,
        "service_id": ctx.service_id,
        "product_fiscal_classification_id": ctx.product_fclass_id,
        "service_fiscal_classification_id": ctx.service_fclass_id,
        "created_sales": ctx.created_sales,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        },
        "results": [r.__dict__ for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stress test das operações de venda do Kovir ERP.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--company-id", default=DEFAULT_COMPANY_ID)
    parser.add_argument("--report", default="sales_stress_report.json")
    parser.add_argument("--stop-on-fail", action="store_true")
    args = parser.parse_args(argv)

    api = KovirClient(args.base_url)
    ctx = StressContext(api, args.company_id)
    results: list[CaseResult] = []

    print("Kovir ERP — Stress Test de Vendas")
    print(f"Backend: {args.base_url}")
    print("Aviso: este teste cria dados de desenvolvimento no banco.")

    try:
        ctx.setup()
        print("\n[SETUP OK]")
        print(f"  company_id={ctx.company_id}")
        print(f"  customer_id={ctx.customer_id}")
        print(f"  product_id={ctx.product_id}")
        print(f"  service_id={ctx.service_id}")
    except Exception as exc:
        print("\n[SETUP FALHOU]")
        print(exc)
        traceback.print_exc()
        return 2

    for name, expected, fn in build_cases(ctx):
        if name.startswith("RISCO:"):
            run_expected_risk_case(results, name, fn)
        else:
            run_case(results, name, expected, fn)
        if args.stop_on_fail and results[-1].status == "FAIL":
            break

    write_report(args.report, ctx, results)

    print("\n==============================")
    print("RESUMO")
    print("==============================")
    print(f"PASS:    {sum(1 for r in results if r.status == 'PASS')}")
    print(f"FAIL:    {sum(1 for r in results if r.status == 'FAIL')}")
    print(f"WARNING: {sum(1 for r in results if r.status == 'WARNING')}")
    print(f"Relatório JSON: {args.report}")

    if any(r.status == "WARNING" for r in results):
        print("\nPONTO DE ATENÇÃO:")
        print("- WARNING não significa que o backend caiu. Significa que uma regra de domínio crítica pode estar permissiva demais.")
        print("- O caso principal esperado é override de preço unitário via API. Se aparecer WARNING, recomendo corrigir antes de seguir para Estoque/Contas a Receber.")

    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
