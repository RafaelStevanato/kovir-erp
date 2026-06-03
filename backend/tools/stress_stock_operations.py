r"""
Kovir ERP — Stress Test do Bloco Estoque Operacional
=====================================================

Objetivo:
- Forçar cenários normais, extremos e atípicos do módulo de estoque.
- Validar saldo, movimentos, entrada por nota/documento de compra e XML de NF-e.
- Validar integração estoque <-> venda confirmada/cancelada.
- Encontrar fragilidades de domínio antes de avançar para Contas a Receber / Compras.

Uso esperado no Windows, com backend rodando em http://127.0.0.1:8000:

    cd C:\Users\Rafael Stevanato\Desktop\kovir-erp\backend
    .\.venv\Scripts\Activate.ps1
    python .\tools\stress_stock_operations.py

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
QTY = Decimal("0.0001")
DEFAULT_BASE_URL = os.getenv("KOVIR_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_COMPANY_ID = os.getenv("KOVIR_COMPANY_ID", "emp_93f95b63-8ed3-4d0c-b564-0c1c6de62887")
MISSING = object()


@dataclass
class CaseResult:
    name: str
    expected: str
    status: str
    detail: str = ""
    entity_id: str | None = None
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
            "X-Request-ID": f"stock-stress-{int(time.time() * 1000)}",
        }
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(self._url(path, query), data=data, headers=headers, method=method.upper())
        try:
            with request.urlopen(req, timeout=25) as resp:
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

    def post(self, path: str, body: dict[str, Any] | None = None, query: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, body=body, query=query)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PATCH", path, body=body)


def qmoney(value: Decimal | str | int | float | None) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY, rounding=ROUND_HALF_UP)


def qqty(value: Decimal | str | int | float | None) -> Decimal:
    return Decimal(str(value or "0")).quantize(QTY, rounding=ROUND_HALF_UP)


def money_str(value: Decimal | str | int | float) -> str:
    return format(qmoney(value), "f")


def qty_str(value: Decimal | str | int | float) -> str:
    return format(qqty(value), "f")


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


def response_blob(exc: KovirApiError) -> str:
    return json.dumps(exc.payload, ensure_ascii=False) if exc.payload is not None else exc.raw


class StressContext:
    def __init__(self, api: KovirClient, company_id: str | None):
        self.api = api
        self.company_id = company_id
        self.suffix = unique_suffix()
        self.customer_id: str | None = None
        self.supplier_id: str | None = None
        self.location_id: str | None = None
        self.alt_location_id: str | None = None
        self.inactive_location_id: str | None = None
        self.tracked_item_id: str | None = None
        self.tracked_sku: str | None = None
        self.tracked_negative_item_id: str | None = None
        self.untracked_item_id: str | None = None
        self.service_id: str | None = None
        self.fclass_id: str | None = None
        self.service_fclass_id: str | None = None
        self.tracked_price = Decimal("20.00")
        self.negative_price = Decimal("15.00")
        self.service_price = Decimal("80.00")

    def setup(self):
        self._health_check()
        self._ensure_company()
        self._ensure_sales_dependencies()
        self._create_participants()
        self._create_catalog_items()
        self._create_fiscal_classifications()
        self._ensure_locations()

    def _health_check(self):
        data = unwrap(self.api.get("/system/database-health"))
        if not data.get("online"):
            raise RuntimeError(f"Banco não está online: {data}")
        unwrap(self.api.get("/stock/diagnostics"))
        unwrap(self.api.get("/stock/rules"))

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
            "legal_name": f"STVN Stock Stress Test LTDA {self.suffix}",
            "trade_name": "STVN Stock Stress Test",
            "cnpj": f"99888777{self.suffix[-6:]}",
            "email": "stock.stress@example.com",
            "phone": "14999999999",
            "responsible_name": "Operador Stock Stress",
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

    def _ensure_sales_dependencies(self):
        # A integração venda -> estoque usa naturezas e formas de pagamento.
        try:
            unwrap(self.api.get("/sales/payment-methods", {"company_id": self.company_id}))
            unwrap(self.api.get("/sales/operation-natures", {"company_id": self.company_id}))
        except Exception as exc:
            raise RuntimeError(f"Não consegui preparar dependências de vendas: {exc}") from exc

    def _create_participants(self):
        doc_suffix = self.suffix[-6:]
        customer_payload = {
            "company_id": self.company_id,
            "participant_type": "customer",
            "person_type": "company",
            "name": f"Cliente Stock Stress {self.suffix} LTDA",
            "trade_name": f"Cliente Stock Stress {self.suffix}",
            "document": f"22334455{doc_suffix}",
            "email": f"cliente.stock.{self.suffix}@teste.com",
            "phone": "14988888888",
            "status": "active",
            "address": {
                "street": "Rua Cliente Stock",
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
                "pix_key": f"cliente.stock.{self.suffix}@teste.com",
                "credit_limit": "10000",
                "payment_priority": "normal",
            },
            "notes": "Cliente criado automaticamente pelo stress test de estoque.",
        }
        supplier_payload = dict(customer_payload)
        supplier_payload.update(
            {
                "participant_type": "supplier",
                "name": f"Fornecedor Stock Stress {self.suffix} LTDA",
                "trade_name": f"Fornecedor Stock Stress {self.suffix}",
                "document": f"66778899{doc_suffix}",
                "email": f"fornecedor.stock.{self.suffix}@teste.com",
                "notes": "Fornecedor criado automaticamente pelo stress test de estoque.",
            }
        )
        supplier_payload["financial_settings"] = dict(supplier_payload["financial_settings"])
        supplier_payload["financial_settings"]["pix_key"] = f"fornecedor.stock.{self.suffix}@teste.com"
        self.customer_id = unwrap(self.api.post("/participants", customer_payload))["id"]
        self.supplier_id = unwrap(self.api.post("/participants", supplier_payload))["id"]

    def _catalog_payload(
        self,
        *,
        item_type: str,
        name: str,
        sku: str,
        unit: str,
        sale_price: Decimal,
        track_stock: bool,
        allow_negative: bool,
        ncm: str | None = "21069090",
        nbs: str | None = None,
    ) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "item_type": item_type,
            "name": name,
            "description": f"Item criado automaticamente pelo stress test de estoque {self.suffix}.",
            "sku": sku,
            "barcode": None,
            "unit": unit,
            "status": "active",
            "origin": "manual",
            "financial_settings": {
                "default_sale_price": money_str(sale_price),
                "default_cost_price": "8.00",
                "allow_price_override": False,
            },
            "fiscal_settings": {
                "ncm": ncm,
                "nbs": nbs,
                "cfop_default": "5102" if item_type == "product" else None,
                "cst_ibs_cbs": "000",
                "cclass_trib": "000001",
                "subject_to_tax": True,
            },
            "inventory_settings": {
                "track_stock": track_stock,
                "stock_unit": unit if item_type == "product" else None,
                "minimum_stock": "2" if track_stock else None,
                "allow_negative_stock": allow_negative,
            },
            "notes": "Item do stress test de estoque.",
        }

    def _create_catalog_items(self):
        self.tracked_sku = f"STOCK-TRACK-{self.suffix}"
        tracked = self._catalog_payload(
            item_type="product",
            name=f"Produto Controla Estoque {self.suffix}",
            sku=self.tracked_sku,
            unit="UN",
            sale_price=self.tracked_price,
            track_stock=True,
            allow_negative=False,
        )
        negative = self._catalog_payload(
            item_type="product",
            name=f"Produto Estoque Negativo Permitido {self.suffix}",
            sku=f"STOCK-NEG-{self.suffix}",
            unit="UN",
            sale_price=self.negative_price,
            track_stock=True,
            allow_negative=True,
        )
        untracked = self._catalog_payload(
            item_type="product",
            name=f"Produto Sem Controle Estoque {self.suffix}",
            sku=f"STOCK-NOTRACK-{self.suffix}",
            unit="UN",
            sale_price=Decimal("25.00"),
            track_stock=False,
            allow_negative=False,
        )
        service = self._catalog_payload(
            item_type="service",
            name=f"Serviço Sem Estoque {self.suffix}",
            sku=f"STOCK-SERV-{self.suffix}",
            unit="SERV",
            sale_price=self.service_price,
            track_stock=False,
            allow_negative=False,
            ncm=None,
            nbs="123456789",
        )
        self.tracked_item_id = unwrap(self.api.post("/catalog/items", tracked))["id"]
        self.tracked_negative_item_id = unwrap(self.api.post("/catalog/items", negative))["id"]
        self.untracked_item_id = unwrap(self.api.post("/catalog/items", untracked))["id"]
        self.service_id = unwrap(self.api.post("/catalog/items", service))["id"]

    def _create_fiscal_classifications(self):
        product_payload = {
            "company_id": self.company_id,
            "name": f"Classificação Fiscal Stock Stress Produto {self.suffix}",
            "description": "Classificação criada pelo stress test de estoque.",
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
            "source_reference": "stock_stress_test",
            "notes": "Fiscal class do stress test de estoque.",
        }
        service_payload = {
            "company_id": self.company_id,
            "name": f"Classificação Fiscal Stock Stress Serviço {self.suffix}",
            "description": "Classificação criada pelo stress test de estoque.",
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
            "source_reference": "stock_stress_test",
            "notes": "Fiscal class serviço do stress test de estoque.",
        }
        self.fclass_id = unwrap(self.api.post("/fiscal/classifications", product_payload))["id"]
        self.service_fclass_id = unwrap(self.api.post("/fiscal/classifications", service_payload))["id"]

    def _ensure_locations(self):
        self.location_id = unwrap(self.api.post("/stock/locations/default", query={"company_id": self.company_id}))["id"]
        alt_payload = {
            "company_id": self.company_id,
            "code": f"stress_alt_{self.suffix}",
            "name": f"Estoque Alternativo Stress {self.suffix}",
            "location_type": "warehouse",
            "is_default": False,
            "status": "active",
            "settings": {"stress_test": True},
            "notes": "Local alternativo do stress test de estoque.",
        }
        inactive_payload = dict(alt_payload)
        inactive_payload["code"] = f"stress_inactive_{self.suffix}"
        inactive_payload["name"] = f"Estoque Inativo Stress {self.suffix}"
        self.alt_location_id = unwrap(self.api.post("/stock/locations", alt_payload))["id"]
        self.inactive_location_id = unwrap(self.api.post("/stock/locations", inactive_payload))["id"]
        unwrap(self.api.patch(f"/stock/locations/{self.inactive_location_id}", {"status": "inactive"}))

    def stock_movement_payload(
        self,
        *,
        item_id: str | None = None,
        location_id: str | None = None,
        movement_type: str = "initial_balance",
        quantity: str = "1",
        unit_cost: str | None = "10.00",
        unit: str = "UN",
        notes: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "company_id": self.company_id,
            "item_id": item_id or self.tracked_item_id,
            "location_id": location_id if location_id is not None else self.location_id,
            "movement_type": movement_type,
            "quantity": quantity,
            "unit": unit,
            "unit_cost": unit_cost,
            "notes": notes or f"Movimento criado por stress test {self.suffix}.",
            "metadata": {"stress_test": True, "suffix": self.suffix},
        }
        return {k: v for k, v in payload.items() if v is not None}

    def purchase_entry_payload(
        self,
        *,
        items: list[dict[str, Any]] | None = None,
        location_id: str | None = None,
        supplier_id: str | None | object = None,
        document_number: str | None | object = MISSING,
        document_series: str | None = "1",
        access_key: str | None | object = MISSING,
        issue_date: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        if supplier_id is None:
            supplier_id = self.supplier_id
        resolved_document_number = f"NF-STOCK-{self.suffix}" if document_number is MISSING else document_number
        resolved_access_key = None if access_key is MISSING else access_key
        payload = {
            "company_id": self.company_id,
            "supplier_participant_id": supplier_id,
            "location_id": location_id if location_id is not None else self.location_id,
            "document_type": "purchase_invoice",
            "document_number": resolved_document_number,
            "document_series": document_series,
            "access_key": resolved_access_key,
            "issue_date": issue_date or today(),
            "notes": notes or f"Entrada por nota criada por stress test {self.suffix}.",
            "metadata": {"stress_test": True, "suffix": self.suffix},
            "items": items or [
                {
                    "item_id": self.tracked_item_id,
                    "quantity": "3",
                    "unit_cost": "7.50",
                    "unit": "UN",
                    "description": "Linha padrão stress test",
                }
            ],
        }
        return {k: v for k, v in payload.items() if v is not None}

    def sale_payload(
        self,
        *,
        item_id: str | None = None,
        fclass_id: str | None = None,
        sale_type: str = "product",
        quantity: str = "1",
        unit_price: Decimal | None = None,
        payment_amount: Decimal | None = None,
    ) -> dict[str, Any]:
        if sale_type == "service":
            item_id = item_id or self.service_id
            fclass_id = fclass_id or self.service_fclass_id
            unit = "SERV"
            price = unit_price or self.service_price
        else:
            item_id = item_id or self.tracked_item_id
            fclass_id = fclass_id or self.fclass_id
            unit = "UN"
            price = unit_price or self.tracked_price
        amount = payment_amount if payment_amount is not None else (price * Decimal(str(quantity))).quantize(MONEY, rounding=ROUND_HALF_UP)
        return {
            "company_id": self.company_id,
            "participant_id": self.customer_id,
            "sale_type": sale_type,
            "origin": "manual",
            "operation_nature": "normal_sale",
            "issue_date": today(),
            "competency_date": today(),
            "discount_type": "amount",
            "discount_amount": "0",
            "freight_amount": "0",
            "tax_amount": "0",
            "notes": f"Venda criada por stress test de estoque {self.suffix}",
            "items": [
                {
                    "item_id": item_id,
                    "fiscal_classification_id": fclass_id,
                    "quantity": quantity,
                    "unit": unit,
                    "discount_amount": "0",
                    "freight_amount": "0",
                    "tax_amount": "0",
                }
            ],
            "payment_plans": [
                {
                    "payment_method_code": "pix",
                    "amount": money_str(amount),
                    "due_date": today(),
                    "installments": 1,
                }
            ],
        }


def get_balance(ctx: StressContext, *, item_id: str | None = None, location_id: str | None = None) -> Decimal:
    rows = unwrap(
        ctx.api.get(
            "/stock/balances",
            {
                "company_id": ctx.company_id,
                "item_id": item_id or ctx.tracked_item_id,
                "location_id": location_id if location_id is not None else ctx.location_id,
                "limit": 500,
                "offset": 0,
            },
        )
    )
    return sum((qqty(row.get("quantity")) for row in rows), Decimal("0.0000")).quantize(QTY, rounding=ROUND_HALF_UP)


def get_total_availability(ctx: StressContext, *, item_id: str | None = None) -> Decimal:
    data = unwrap(ctx.api.get(f"/stock/items/{item_id or ctx.tracked_item_id}/availability", {"company_id": ctx.company_id}))
    return qqty(data.get("total_quantity"))


def post_should_fail(api: KovirClient, path: str, payload: dict[str, Any], *, expected_text: str | None = None) -> str:
    try:
        resp = api.post(path, payload)
    except KovirApiError as exc:
        blob = response_blob(exc)
        if expected_text and expected_text.lower() not in blob.lower():
            raise AssertionError(f"Falhou, mas mensagem não contém {expected_text!r}. Resposta: {blob}")
        return blob
    if isinstance(resp, dict) and resp.get("success") is False:
        blob = json.dumps(resp, ensure_ascii=False)
        if expected_text and expected_text.lower() not in blob.lower():
            raise AssertionError(f"Falhou, mas mensagem não contém {expected_text!r}. Resposta: {blob}")
        return blob
    raise AssertionError(f"Payload inválido foi aceito: {resp}")


def assert_delta(before: Decimal, after: Decimal, expected_delta: Decimal, label: str):
    actual_delta = (after - before).quantize(QTY, rounding=ROUND_HALF_UP)
    expected_delta = expected_delta.quantize(QTY, rounding=ROUND_HALF_UP)
    if actual_delta != expected_delta:
        raise AssertionError(f"{label}: delta esperado {expected_delta}, delta real {actual_delta}. Antes={before}, Depois={after}")


def run_case(results: list[CaseResult], name: str, expected: str, fn):
    print(f"\n[TESTE] {name}")
    try:
        result = fn()
        entity_id = None
        if isinstance(result, dict):
            entity_id = result.get("id") or result.get("sale_id") or result.get("movement_id")
        print(f"  OK — {expected}" + (f" | id={entity_id}" if entity_id else ""))
        results.append(CaseResult(name=name, expected=expected, status="PASS", entity_id=entity_id))
    except Exception as exc:
        print(f"  FALHOU — {exc}")
        results.append(CaseResult(name=name, expected=expected, status="FAIL", detail=str(exc)))


def run_expected_risk_case(results: list[CaseResult], name: str, fn):
    """Se o cenário perigoso for aceito, vira WARNING. Se for bloqueado, vira PASS."""
    print(f"\n[RISCO] {name}")
    try:
        result = fn()
        entity_id = result.get("id") if isinstance(result, dict) else None
        detail = "A API aceitou um cenário que deveria ser avaliado/bloqueado por regra de domínio futura."
        print(f"  WARNING — {detail}" + (f" | id={entity_id}" if entity_id else ""))
        results.append(CaseResult(name=name, expected="deveria bloquear ou exigir aprovação", status="WARNING", detail=detail, entity_id=entity_id))
    except Exception as exc:
        print(f"  OK — cenário perigoso bloqueado: {exc}")
        results.append(CaseResult(name=name, expected="deveria bloquear", status="PASS", detail=str(exc)))


def create_sale_and_confirm(ctx: StressContext, payload: dict[str, Any]) -> dict[str, Any]:
    sale = unwrap(ctx.api.post("/sales", payload))
    confirmed = unwrap(ctx.api.post(f"/sales/{sale['id']}/confirm", {"reason": "Confirmação via stress test de estoque."}))
    if confirmed.get("status") != "confirmed":
        raise AssertionError(f"Venda deveria confirmar, veio status={confirmed.get('status')}")
    return confirmed


def confirm_sale_should_fail(ctx: StressContext, payload: dict[str, Any], *, expected_text: str | None = None):
    sale = unwrap(ctx.api.post("/sales", payload))
    try:
        ctx.api.post(f"/sales/{sale['id']}/confirm", {"reason": "Tentativa de confirmação via stress test de estoque."})
    except KovirApiError as exc:
        blob = response_blob(exc)
        if expected_text and expected_text.lower() not in blob.lower():
            raise AssertionError(f"Confirmou falha, mas mensagem não contém {expected_text!r}. Resposta: {blob}")
        return blob
    raise AssertionError(f"Venda sem estoque suficiente foi confirmada indevidamente: {sale['id']}")


def valid_nfe_xml(ctx: StressContext, *, sku: str | None = None, description: str | None = None, n_nf: str | None = None) -> str:
    sku = sku or ctx.tracked_sku
    description = description or f"Produto Controla Estoque {ctx.suffix}"
    n_nf = n_nf or f"{ctx.suffix[-6:]}"
    # Estrutura mínima suficiente para o parser do módulo, com namespace da NF-e.
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe3526041234567800019055001000{n_nf}10000000010" versao="4.00">
      <ide>
        <cUF>35</cUF>
        <cNF>00000001</cNF>
        <natOp>Venda de mercadoria</natOp>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>{n_nf}</nNF>
        <dhEmi>{today()}T10:00:00-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>66778899000100</CNPJ>
        <xNome>Fornecedor XML Stress</xNome>
        <xFant>Fornecedor XML</xFant>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>{sku}</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>{description}</xProd>
          <NCM>21069090</NCM>
          <CFOP>5102</CFOP>
          <uCom>UN</uCom>
          <qCom>4.0000</qCom>
          <vUnCom>11.50</vUnCom>
          <vProd>46.00</vProd>
          <cEANTrib>SEM GTIN</cEANTrib>
          <uTrib>UN</uTrib>
          <qTrib>4.0000</qTrib>
          <vUnTrib>11.50</vUnTrib>
        </prod>
      </det>
      <total>
        <ICMSTot>
          <vNF>46.00</vNF>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>'''


def run_tests(ctx: StressContext) -> list[CaseResult]:
    results: list[CaseResult] = []

    run_case(results, "Diagnóstico e regras de estoque", "endpoints básicos respondem", lambda: unwrap(ctx.api.get("/stock/diagnostics")))

    def case_default_location_idempotent():
        first = unwrap(ctx.api.post("/stock/locations/default", query={"company_id": ctx.company_id}))
        second = unwrap(ctx.api.post("/stock/locations/default", query={"company_id": ctx.company_id}))
        if first["id"] != second["id"]:
            raise AssertionError(f"Local padrão não foi idempotente: {first['id']} != {second['id']}")
        return first
    run_case(results, "Local padrão idempotente", "chamar duas vezes retorna o mesmo local", case_default_location_idempotent)

    def case_initial_balance():
        before = get_balance(ctx)
        movement = unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="initial_balance", quantity="10", unit_cost="8.50")))
        after = get_balance(ctx)
        assert_delta(before, after, Decimal("10"), "Saldo inicial")
        if movement.get("movement_type") != "initial_balance":
            raise AssertionError(f"movement_type inesperado: {movement.get('movement_type')}")
        return movement
    run_case(results, "Saldo inicial em produto controlado", "cria movimento e aumenta saldo", case_initial_balance)

    def case_adjustment_in():
        before = get_balance(ctx)
        movement = unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="adjustment_in", quantity="2.5", unit_cost="9.00")))
        after = get_balance(ctx)
        assert_delta(before, after, Decimal("2.5"), "Ajuste de entrada")
        return movement
    run_case(results, "Ajuste manual de entrada", "aumenta saldo com quantidade decimal", case_adjustment_in)

    def case_adjustment_out():
        before = get_balance(ctx)
        movement = unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="adjustment_out", quantity="3", unit_cost=None)))
        after = get_balance(ctx)
        assert_delta(before, after, Decimal("-3"), "Ajuste de saída")
        return movement
    run_case(results, "Ajuste manual de saída dentro do saldo", "reduz saldo sem negativar indevidamente", case_adjustment_out)

    def case_availability():
        balance = get_balance(ctx)
        availability = get_total_availability(ctx)
        if availability != balance:
            raise AssertionError(f"Disponibilidade {availability} não bate com saldo filtrado {balance}")
        return {"id": ctx.tracked_item_id, "availability": str(availability)}
    run_case(results, "Disponibilidade total do item", "availability bate com stock_balances", case_availability)

    run_case(
        results,
        "Bloqueio de saída maior que saldo",
        "produto sem allow_negative_stock bloqueia saldo negativo",
        lambda: post_should_fail(ctx.api, "/stock/movements", ctx.stock_movement_payload(movement_type="adjustment_out", quantity="999999"), expected_text="Saldo insuficiente"),
    )

    run_case(
        results,
        "Bloqueio de serviço no estoque",
        "serviço não pode movimentar estoque",
        lambda: post_should_fail(ctx.api, "/stock/movements", ctx.stock_movement_payload(item_id=ctx.service_id, movement_type="initial_balance", quantity="1", unit="SERV"), expected_text="apenas produtos"),
    )

    run_case(
        results,
        "Bloqueio de produto sem controle de estoque",
        "produto track_stock=false não pode receber movimento manual",
        lambda: post_should_fail(ctx.api, "/stock/movements", ctx.stock_movement_payload(item_id=ctx.untracked_item_id, movement_type="initial_balance", quantity="1"), expected_text="não está marcado"),
    )

    run_case(
        results,
        "Bloqueio de movement_type reservado via endpoint manual",
        "purchase_in/sale_out não entram pelo endpoint manual",
        lambda: post_should_fail(ctx.api, "/stock/movements", ctx.stock_movement_payload(movement_type="purchase_in", quantity="1"), expected_text="não permitido"),
    )

    run_case(
        results,
        "Bloqueio de movimento em local inativo",
        "local inactive não aceita nova movimentação",
        lambda: post_should_fail(ctx.api, "/stock/movements", ctx.stock_movement_payload(location_id=ctx.inactive_location_id, movement_type="adjustment_in", quantity="1"), expected_text="inativo"),
    )

    def case_negative_allowed_manual():
        before = get_balance(ctx, item_id=ctx.tracked_negative_item_id)
        movement = unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(item_id=ctx.tracked_negative_item_id, movement_type="adjustment_out", quantity="5", unit_cost=None)))
        after = get_balance(ctx, item_id=ctx.tracked_negative_item_id)
        assert_delta(before, after, Decimal("-5"), "Saída negativa permitida")
        return movement
    run_case(results, "Produto com estoque negativo permitido", "allow_negative_stock=true aceita saldo negativo", case_negative_allowed_manual)

    def case_purchase_entry_single():
        before = get_balance(ctx)
        entry = unwrap(ctx.api.post("/stock/purchase-entries", ctx.purchase_entry_payload(document_number=f"NF-SINGLE-{ctx.suffix}", access_key=f"35{ctx.suffix}0000000000000000000000000000000000000000"[:44])))
        after = get_balance(ctx)
        assert_delta(before, after, Decimal("3"), "Entrada por nota simples")
        if len(entry.get("items") or []) != 1:
            raise AssertionError("Entrada deveria retornar 1 item.")
        return entry
    run_case(results, "Entrada por nota/documento simples", "cria entrada, item, movimento purchase_in e saldo", case_purchase_entry_single)

    def case_purchase_entry_multiple_alt_location():
        before_main = get_balance(ctx, item_id=ctx.tracked_item_id, location_id=ctx.alt_location_id)
        before_neg = get_balance(ctx, item_id=ctx.tracked_negative_item_id, location_id=ctx.alt_location_id)
        entry = unwrap(
            ctx.api.post(
                "/stock/purchase-entries",
                ctx.purchase_entry_payload(
                    location_id=ctx.alt_location_id,
                    document_number=f"NF-MULTI-{ctx.suffix}",
                    access_key=f"36{ctx.suffix}0000000000000000000000000000000000000000"[:44],
                    items=[
                        {"item_id": ctx.tracked_item_id, "quantity": "4", "unit_cost": "7.25", "unit": "UN", "description": "Produto controlado multi"},
                        {"item_id": ctx.tracked_negative_item_id, "quantity": "6", "unit_cost": "5.10", "unit": "UN", "description": "Produto negativo multi"},
                    ],
                ),
            )
        )
        after_main = get_balance(ctx, item_id=ctx.tracked_item_id, location_id=ctx.alt_location_id)
        after_neg = get_balance(ctx, item_id=ctx.tracked_negative_item_id, location_id=ctx.alt_location_id)
        assert_delta(before_main, after_main, Decimal("4"), "Entrada multi item principal")
        assert_delta(before_neg, after_neg, Decimal("6"), "Entrada multi item negativo")
        if len(entry.get("items") or []) != 2:
            raise AssertionError("Entrada deveria retornar 2 itens.")
        return entry
    run_case(results, "Entrada por nota com múltiplos produtos em local alternativo", "atualiza saldos por item/local corretamente", case_purchase_entry_multiple_alt_location)

    run_case(
        results,
        "Bloqueio de serviço em entrada de compra",
        "entrada de compra só aceita produto com estoque controlado",
        lambda: post_should_fail(
            ctx.api,
            "/stock/purchase-entries",
            ctx.purchase_entry_payload(document_number=f"NF-SERV-{ctx.suffix}", items=[{"item_id": ctx.service_id, "quantity": "1", "unit_cost": "10", "unit": "SERV"}]),
            expected_text="apenas produtos",
        ),
    )

    run_case(
        results,
        "Bloqueio de produto sem controle em entrada de compra",
        "produto track_stock=false não entra por nota no estoque",
        lambda: post_should_fail(
            ctx.api,
            "/stock/purchase-entries",
            ctx.purchase_entry_payload(document_number=f"NF-NOTRACK-{ctx.suffix}", items=[{"item_id": ctx.untracked_item_id, "quantity": "1", "unit_cost": "10", "unit": "UN"}]),
            expected_text="não está marcado",
        ),
    )

    run_case(
        results,
        "Bloqueio de entrada sem documento/chave",
        "entrada exige número da nota/documento ou chave de acesso",
        lambda: post_should_fail(ctx.api, "/stock/purchase-entries", ctx.purchase_entry_payload(document_number=None, access_key=None), expected_text="número"),
    )

    run_case(
        results,
        "Bloqueio de quantidade zero na entrada",
        "quantidade precisa ser maior que zero",
        lambda: post_should_fail(
            ctx.api,
            "/stock/purchase-entries",
            ctx.purchase_entry_payload(document_number=f"NF-ZERO-{ctx.suffix}", items=[{"item_id": ctx.tracked_item_id, "quantity": "0", "unit_cost": "10", "unit": "UN"}]),
            expected_text="maior que zero",
        ),
    )

    run_case(
        results,
        "Bloqueio de custo unitário negativo",
        "unit_cost negativo não deve ser aceito",
        lambda: post_should_fail(
            ctx.api,
            "/stock/purchase-entries",
            ctx.purchase_entry_payload(document_number=f"NF-NEG-COST-{ctx.suffix}", items=[{"item_id": ctx.tracked_item_id, "quantity": "1", "unit_cost": "-1", "unit": "UN"}]),
            expected_text="não pode ser negativo",
        ),
    )

    def case_parse_xml_matched():
        parsed = unwrap(ctx.api.post("/stock/purchase-entries/parse-xml", {"company_id": ctx.company_id, "xml_text": valid_nfe_xml(ctx)}))
        summary = parsed.get("summary") or {}
        if int(summary.get("total_items") or 0) != 1:
            raise AssertionError(f"XML deveria ter 1 item: {summary}")
        if int(summary.get("matched_items") or 0) != 1:
            raise AssertionError(f"XML deveria casar por SKU: {parsed}")
        return {"id": parsed.get("document", {}).get("access_key") or "xml_matched"}
    run_case(results, "Leitura de XML NF-e com item casado por SKU", "parser preenche documento/fornecedor/item e sugere vínculo", case_parse_xml_matched)

    def case_parse_xml_unmatched():
        parsed = unwrap(ctx.api.post("/stock/purchase-entries/parse-xml", {"company_id": ctx.company_id, "xml_text": valid_nfe_xml(ctx, sku=f"SKU-SEM-CADASTRO-{ctx.suffix}", description="Produto inexistente no catálogo", n_nf=f"9{ctx.suffix[-5:]}")}))
        summary = parsed.get("summary") or {}
        if int(summary.get("unmatched_items") or 0) < 1:
            raise AssertionError(f"XML sem SKU cadastrado deveria gerar item sem correspondência: {parsed}")
        warnings = parsed.get("warnings") or []
        if not warnings:
            raise AssertionError("XML sem correspondência deveria gerar warnings.")
        return {"id": "xml_unmatched"}
    run_case(results, "Leitura de XML NF-e com item sem cadastro", "parser avisa que precisa vincular produto manualmente", case_parse_xml_unmatched)

    run_case(
        results,
        "Bloqueio de XML inválido",
        "parser não deve aceitar XML quebrado",
        lambda: post_should_fail(ctx.api, "/stock/purchase-entries/parse-xml", {"company_id": ctx.company_id, "xml_text": "<nfe><xml-quebrado>"}, expected_text="XML"),
    )

    def case_list_filters_export_readiness():
        balances = unwrap(ctx.api.get("/stock/balances", {"company_id": ctx.company_id, "item_id": ctx.tracked_item_id, "location_id": ctx.location_id, "limit": 50, "offset": 0}))
        movements = unwrap(ctx.api.get("/stock/movements", {"company_id": ctx.company_id, "movement_type": "purchase_in", "limit": 50, "offset": 0}))
        entries = unwrap(ctx.api.get("/stock/purchase-entries", {"company_id": ctx.company_id, "include_items": "true", "limit": 50, "offset": 0}))
        if not isinstance(balances, list) or not isinstance(movements, list) or not isinstance(entries, list):
            raise AssertionError("Listagens devem retornar listas para exportação.")
        required_balance_fields = {"company_id", "item_id", "location_id", "quantity"}
        if balances and not required_balance_fields.issubset(set(balances[0].keys())):
            raise AssertionError(f"Saldo sem campos mínimos para exportar: {balances[0].keys()}")
        return {"id": "export_readiness"}
    run_case(results, "Listagens e filtros para exportação", "saldos/movimentos/entradas retornam dados exportáveis", case_list_filters_export_readiness)

    def case_stock_audit():
        movement = unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="adjustment_in", quantity="1")))
        events = unwrap(ctx.api.get(f"/stock/stock_movement/{movement['id']}/audit"))
        if not events:
            raise AssertionError("Movimento de estoque não retornou auditoria.")
        return movement
    run_case(results, "Auditoria de movimento de estoque", "movimento crítico gera audit_event consultável", case_stock_audit)

    def case_sale_stock_decrease_and_cancel_reversal():
        before = get_balance(ctx)
        sale = create_sale_and_confirm(ctx, ctx.sale_payload(quantity="2"))
        after_confirm = get_balance(ctx)
        assert_delta(before, after_confirm, Decimal("-2"), "Confirmação de venda")
        links = unwrap(ctx.api.get("/stock/sale-links", {"sale_id": sale["id"]}))
        if not links:
            raise AssertionError("Venda confirmada deveria gerar sale_stock_links.")
        cancelled = unwrap(ctx.api.post(f"/sales/{sale['id']}/cancel", {"reason": "Cancelamento via stress test de estoque."}))
        if cancelled.get("status") != "cancelled":
            raise AssertionError(f"Venda deveria cancelar, veio {cancelled.get('status')}")
        after_cancel = get_balance(ctx)
        assert_delta(after_confirm, after_cancel, Decimal("2"), "Cancelamento de venda")
        return {"id": sale["id"]}
    run_case(results, "Venda confirmada reduz estoque e cancelamento reverte", "sale_out e sale_out_reversal preservam rastreabilidade", case_sale_stock_decrease_and_cancel_reversal)

    def case_sale_insufficient_stock_blocks_confirm():
        # Produto sem saldo e sem negative. Cria produto específico para não depender do saldo já carregado.
        sku = f"STOCK-ZERO-{ctx.suffix}"
        zero_item = unwrap(
            ctx.api.post(
                "/catalog/items",
                ctx._catalog_payload(
                    item_type="product",
                    name=f"Produto Sem Saldo {ctx.suffix}",
                    sku=sku,
                    unit="UN",
                    sale_price=ctx.tracked_price,
                    track_stock=True,
                    allow_negative=False,
                ),
            )
        )
        payload = ctx.sale_payload(item_id=zero_item["id"], quantity="5", payment_amount=ctx.tracked_price * Decimal("5"))
        return confirm_sale_should_fail(ctx, payload, expected_text="Saldo insuficiente")
    run_case(results, "Bloqueio de venda sem saldo suficiente", "confirmação da venda não pode furar saldo", case_sale_insufficient_stock_blocks_confirm)

    def case_sale_negative_allowed_confirm():
        before = get_balance(ctx, item_id=ctx.tracked_negative_item_id)
        sale = create_sale_and_confirm(ctx, ctx.sale_payload(item_id=ctx.tracked_negative_item_id, quantity="3", unit_price=ctx.negative_price, payment_amount=ctx.negative_price * Decimal("3")))
        after = get_balance(ctx, item_id=ctx.tracked_negative_item_id)
        assert_delta(before, after, Decimal("-3"), "Venda com negativo permitido")
        return sale
    run_case(results, "Venda com produto que permite estoque negativo", "allow_negative_stock=true permite confirmação mesmo sem saldo", case_sale_negative_allowed_confirm)

    def case_service_sale_no_stock_effect():
        before_movements = unwrap(ctx.api.get("/stock/movements", {"company_id": ctx.company_id, "source_type": "sale", "limit": 200, "offset": 0}))
        sale = create_sale_and_confirm(ctx, ctx.sale_payload(sale_type="service", quantity="1", payment_amount=ctx.service_price))
        after_movements = unwrap(ctx.api.get("/stock/movements", {"company_id": ctx.company_id, "source_type": "sale", "limit": 200, "offset": 0}))
        new_movements = [m for m in after_movements if m.get("source_id") == sale["id"]]
        if new_movements:
            raise AssertionError(f"Venda de serviço não deveria gerar movimento de estoque: {new_movements}")
        # before_movements só mantém a variável usada para evidenciar que a listagem está funcional.
        _ = before_movements
        return sale
    run_case(results, "Venda de serviço não movimenta estoque", "serviço confirmado não cria stock_movement", case_service_sale_no_stock_effect)

    # Casos de risco: indicam regras que talvez precisem endurecimento antes de operação real.
    run_expected_risk_case(
        results,
        "RISCO: entrada duplicada com mesma chave de acesso",
        lambda: unwrap(
            ctx.api.post(
                "/stock/purchase-entries",
                ctx.purchase_entry_payload(document_number=f"NF-DUP-A-{ctx.suffix}", access_key=f"37{ctx.suffix}0000000000000000000000000000000000000000"[:44]),
            )
        )
        and unwrap(
            ctx.api.post(
                "/stock/purchase-entries",
                ctx.purchase_entry_payload(document_number=f"NF-DUP-B-{ctx.suffix}", access_key=f"37{ctx.suffix}0000000000000000000000000000000000000000"[:44]),
            )
        ),
    )

    run_expected_risk_case(
        results,
        "RISCO: saldo inicial repetido no mesmo produto/local",
        lambda: unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="initial_balance", quantity="1", notes="Primeiro saldo inicial duplicado.")))
        and unwrap(ctx.api.post("/stock/movements", ctx.stock_movement_payload(movement_type="initial_balance", quantity="1", notes="Segundo saldo inicial duplicado."))),
    )

    run_expected_risk_case(
        results,
        "RISCO: entrada de compra com unidade diferente da unidade de estoque",
        lambda: unwrap(
            ctx.api.post(
                "/stock/purchase-entries",
                ctx.purchase_entry_payload(
                    document_number=f"NF-UNIT-MISMATCH-{ctx.suffix}",
                    items=[{"item_id": ctx.tracked_item_id, "quantity": "1", "unit_cost": "10", "unit": "CX", "description": "Unidade divergente"}],
                ),
            )
        ),
    )

    return results


def write_report(results: list[CaseResult], *, path: str, ctx: StressContext):
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": ctx.api.base_url,
        "company_id": ctx.company_id,
        "summary": {
            "pass": sum(1 for r in results if r.status == "PASS"),
            "fail": sum(1 for r in results if r.status == "FAIL"),
            "warning": sum(1 for r in results if r.status == "WARNING"),
            "total": len(results),
        },
        "context": {
            "suffix": ctx.suffix,
            "tracked_item_id": ctx.tracked_item_id,
            "tracked_negative_item_id": ctx.tracked_negative_item_id,
            "untracked_item_id": ctx.untracked_item_id,
            "service_id": ctx.service_id,
            "location_id": ctx.location_id,
            "alt_location_id": ctx.alt_location_id,
        },
        "results": [r.__dict__ for r in results],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stress test do módulo de estoque do Kovir ERP.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--company-id", default=DEFAULT_COMPANY_ID)
    parser.add_argument("--report", default="stock_stress_report.json")
    parser.add_argument("--traceback", action="store_true", help="Mostra traceback completo em falhas inesperadas.")
    args = parser.parse_args(argv)

    print("=" * 80)
    print("Kovir ERP - STRESS TEST DO BLOCO ESTOQUE")
    print("=" * 80)
    print(f"Backend: {args.base_url}")
    print(f"Empresa preferencial: {args.company_id}")
    print("Atenção: este teste cria dados no banco de desenvolvimento.")

    api = KovirClient(args.base_url)
    ctx = StressContext(api, args.company_id)

    try:
        print("\n[setup] Preparando empresa, participante, produtos, classificações e locais...")
        ctx.setup()
        print(f"[setup] Empresa usada: {ctx.company_id}")
        print(f"[setup] Produto controlado: {ctx.tracked_item_id}")
        print(f"[setup] Local padrão: {ctx.location_id}")
        results = run_tests(ctx)
    except Exception as exc:
        print(f"\n[ERRO FATAL] {exc}")
        if args.traceback:
            traceback.print_exc()
        return 2

    write_report(results, path=args.report, ctx=ctx)

    pass_count = sum(1 for r in results if r.status == "PASS")
    fail_count = sum(1 for r in results if r.status == "FAIL")
    warning_count = sum(1 for r in results if r.status == "WARNING")

    print("\n" + "=" * 30)
    print("RESUMO")
    print("=" * 30)
    print(f"PASS:    {pass_count}")
    print(f"FAIL:    {fail_count}")
    print(f"WARNING: {warning_count}")
    print(f"Relatório JSON: {args.report}")

    if fail_count:
        print("\nHá falhas reais. Não avance de bloco antes de corrigir.")
        return 1
    if warning_count:
        print("\nHá warnings de risco de domínio. Não são falhas técnicas imediatas, mas devem ser avaliados antes de uso real.")
        return 0
    print("\nBloco Estoque passou sem falhas nem warnings no stress test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
