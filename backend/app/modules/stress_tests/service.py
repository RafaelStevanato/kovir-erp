from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.schemas import FinancialTitleCreate
from app.modules.accounts_receivable.service import create_manual_receivable
from app.modules.catalog.schemas import CatalogItemCreate
from app.modules.catalog.service import create_catalog_item, list_catalog_items
from app.modules.fiscal_classification.schemas import FiscalClassificationCreate
from app.modules.fiscal_classification.service import (
    create_fiscal_classification,
    list_fiscal_classifications,
)
from app.modules.participants.schemas import ParticipantCreate
from app.modules.participants.service import create_participant, list_participants
from app.modules.purchases_payables.schemas import PurchaseConfirmPayload, PurchaseCreate
from app.modules.purchases_payables.service import (
    confirm_purchase,
    create_purchase_draft,
)
from app.modules.sales.schemas import SaleCreate, SaleStatusChange
from app.modules.sales.service import confirm_sale, create_sale
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.ids import assert_valid_id

MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class StressRequestContext:
    actor_id: str
    source: AuditSource
    request_id: str | None
    correlation_id: str | None


def _money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money_text(value: Decimal | str | int | float) -> str:
    return format(_money(value), "f")


def _today_plus(days: int) -> date:
    return date.today() + timedelta(days=days)


def _seed(company_id: str) -> random.Random:
    return random.Random(abs(hash((company_id, time.time_ns(), uuid4().hex))))


def _digits(rng: random.Random, length: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


def _participant_payload(
    *,
    company_id: str,
    participant_type: str,
    suffix: str,
    rng: random.Random,
) -> ParticipantCreate:
    legal_name = (
        f"Stress Cliente {suffix} LTDA"
        if participant_type == "customer"
        else f"Stress Fornecedor {suffix} LTDA"
    )
    document = _digits(rng, 14)
    email_prefix = "cliente" if participant_type == "customer" else "fornecedor"

    return ParticipantCreate(
        company_id=company_id,
        participant_type=participant_type,
        person_type="company",
        name=legal_name,
        trade_name=legal_name.replace(" LTDA", ""),
        document=document,
        email=f"{email_prefix}.{suffix}@stress.kovirerp.com.br",
        phone=f"119{_digits(rng, 8)}",
        status="active",
        address={
            "street": "Rua Stress Kovir",
            "number": str(rng.randint(1, 5000)),
            "complement": None,
            "district": "Centro",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01001000",
            "country": "BR",
            "ibge_municipality_code": None,
        },
        fiscal_settings={
            "taxpayer_type": "taxpayer",
            "tax_regime": "simples_nacional",
            "main_cnae": "6201500",
            "state_registration": "ISENTO",
            "municipal_registration": None,
            "suframa_registration": None,
            "is_foreign": False,
            "fiscal_notes": "Gerado pelo módulo Stress e Testes.",
        },
        financial_settings={
            "default_payment_method": "pix",
            "default_payment_terms": "30 dias",
            "bank_name": None,
            "bank_branch": None,
            "bank_account": None,
            "pix_key": None,
            "credit_limit": "20000.00",
            "payment_priority": "normal",
        },
        notes="Participante gerado automaticamente para stress.",
    )


def _classification_payload(
    *,
    company_id: str,
    item_type: str,
    suffix: str,
    rng: random.Random,
) -> FiscalClassificationCreate:
    if item_type == "service":
        return FiscalClassificationCreate(
            company_id=company_id,
            name=f"Classificação Fiscal Serviço {suffix}",
            description="Classificação fiscal gerada no módulo Stress e Testes.",
            item_type="service",
            tax_regime="simples_nacional",
            nbs=f"{_digits(rng, 9)}",
            cst_ibs_cbs="900",
            cclass_trib="A1",
            subject_to_icms=False,
            subject_to_iss=True,
            subject_to_pis_cofins=True,
            subject_to_ibs_cbs=True,
            subject_to_is=False,
            status="active",
            source="manual",
        )

    return FiscalClassificationCreate(
        company_id=company_id,
        name=f"Classificação Fiscal Produto {suffix}",
        description="Classificação fiscal gerada no módulo Stress e Testes.",
        item_type="product",
        tax_regime="simples_nacional",
        ncm=f"{_digits(rng, 8)}",
        cfop_default="5102",
        cst_icms="102",
        cst_pis="49",
        cst_cofins="49",
        cst_ibs_cbs="900",
        cclass_trib="A1",
        subject_to_icms=True,
        subject_to_iss=False,
        subject_to_pis_cofins=True,
        subject_to_ibs_cbs=True,
        subject_to_is=False,
        status="active",
        source="manual",
    )


def _catalog_payload(
    *,
    company_id: str,
    item_type: str,
    suffix: str,
    classification: dict[str, Any] | None,
    rng: random.Random,
) -> CatalogItemCreate:
    sale_price = _money_text(rng.randint(30, 350))
    cost_price = _money_text(Decimal(sale_price) * Decimal("0.55"))

    if item_type == "service":
        nbs = (
            str(classification.get("nbs"))
            if classification and classification.get("nbs")
            else f"{_digits(rng, 9)}"
        )
        return CatalogItemCreate(
            company_id=company_id,
            item_type="service",
            name=f"Serviço Stress {suffix}",
            description="Serviço gerado para validação de stress.",
            sku=f"STRESS-SERV-{suffix}-{uuid4().hex[:6].upper()}",
            barcode=None,
            unit="SERV",
            status="active",
            origin="manual",
            financial_settings={
                "default_sale_price": sale_price,
                "default_cost_price": cost_price,
                "allow_price_override": True,
            },
            fiscal_settings={
                "ncm": None,
                "nbs": nbs,
                "cest": None,
                "cfop_default": None,
                "cst_icms": None,
                "cst_pis": None,
                "cst_cofins": None,
                "cst_ibs_cbs": None,
                "cclass_trib": None,
                "fiscal_classification_id": classification.get("id") if classification else None,
                "fiscal_classification_name": classification.get("name") if classification else None,
                "subject_to_tax": True,
            },
            inventory_settings={
                "track_stock": False,
                "stock_unit": "UN",
                "minimum_stock": None,
                "allow_negative_stock": True,
                "requires_lot": False,
                "requires_expiration_date": False,
            },
            notes="Serviço gerado no módulo Stress e Testes.",
        )

    ncm = (
        str(classification.get("ncm"))
        if classification and classification.get("ncm")
        else f"{_digits(rng, 8)}"
    )
    return CatalogItemCreate(
        company_id=company_id,
        item_type="product",
        name=f"Produto Stress {suffix}",
        description="Produto gerado para validação de stress.",
        sku=f"STRESS-PROD-{suffix}-{uuid4().hex[:6].upper()}",
        barcode=None,
        unit="UN",
        status="active",
        origin="manual",
        financial_settings={
            "default_sale_price": sale_price,
            "default_cost_price": cost_price,
            "allow_price_override": True,
        },
        fiscal_settings={
            "ncm": ncm,
            "nbs": None,
            "cest": None,
            "cfop_default": None,
            "cst_icms": None,
            "cst_pis": None,
            "cst_cofins": None,
            "cst_ibs_cbs": None,
            "cclass_trib": None,
            "fiscal_classification_id": classification.get("id") if classification else None,
            "fiscal_classification_name": classification.get("name") if classification else None,
            "subject_to_tax": True,
        },
        inventory_settings={
        "track_stock": False,
        "stock_unit": "UN",
        "minimum_stock": None,
        "allow_negative_stock": True,
        "requires_lot": False,
        "requires_expiration_date": False,
        },
        notes="Produto gerado no módulo Stress e Testes.",
    )


def _request_kwargs(context: StressRequestContext) -> dict[str, Any]:
    return {
        "actor_id": context.actor_id,
        "source": context.source,
        "request_id": context.request_id,
        "correlation_id": context.correlation_id,
    }


def _company_counts(db: Session, company_id: str) -> dict[str, int]:
    row = db.execute(
        text(
            """
            SELECT
              (SELECT COUNT(*) FROM participants WHERE company_id = :company_id AND deleted_at IS NULL) AS participants,
              (SELECT COUNT(*) FROM fiscal_classifications WHERE company_id = :company_id) AS fiscal_classifications,
              (SELECT COUNT(*) FROM catalog_items WHERE company_id = :company_id AND deleted_at IS NULL) AS catalog_items,
              (SELECT COUNT(*) FROM sales WHERE company_id = :company_id) AS sales,
              (SELECT COUNT(*) FROM financial_titles WHERE company_id = :company_id AND direction = 'receivable' AND deleted_at IS NULL) AS receivables,
              (SELECT COUNT(*) FROM purchases WHERE company_id = :company_id) AS purchases,
              (SELECT COUNT(*) FROM financial_titles WHERE company_id = :company_id AND direction = 'payable' AND deleted_at IS NULL) AS payables
            """
        ),
        {"company_id": company_id},
    ).mappings().one()
    return {key: int(value or 0) for key, value in dict(row).items()}


def _find_participant_by_type(db: Session, *, company_id: str, participant_type: str) -> dict[str, Any] | None:
    rows = list_participants(
        db,
        company_id=company_id,
        participant_type=participant_type,
        status="active",
        limit=1,
        offset=0,
    )
    return rows[0] if rows else None


def _ensure_participant(
    db: Session,
    *,
    company_id: str,
    participant_type: str,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    existing = _find_participant_by_type(
        db,
        company_id=company_id,
        participant_type=participant_type,
    )
    if existing is not None:
        return existing

    suffix = f"{int(time.time() * 1000)}-{uuid4().hex[:6]}"
    payload = _participant_payload(
        company_id=company_id,
        participant_type=participant_type,
        suffix=suffix,
        rng=rng,
    )
    return create_participant(db, payload, **_request_kwargs(context))


def _find_classification(
    db: Session,
    *,
    company_id: str,
    item_type: str,
) -> dict[str, Any] | None:
    rows = list_fiscal_classifications(
        db,
        company_id=company_id,
        status_filter="active",
        item_type=item_type,
        limit=1,
        offset=0,
    )
    return rows[0] if rows else None


def _ensure_classification(
    db: Session,
    *,
    company_id: str,
    item_type: str,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    existing = _find_classification(db, company_id=company_id, item_type=item_type)
    if existing is not None:
        return existing

    suffix = f"{int(time.time() * 1000)}-{uuid4().hex[:6]}"
    payload = _classification_payload(
        company_id=company_id,
        item_type=item_type,
        suffix=suffix,
        rng=rng,
    )
    return create_fiscal_classification(db, payload, **_request_kwargs(context))


def _find_catalog_item(db: Session, *, company_id: str, item_type: str) -> dict[str, Any] | None:
    rows = list_catalog_items(
        db,
        company_id=company_id,
        item_type=item_type,
        status="active",
        limit=1,
        offset=0,
    )
    return rows[0] if rows else None


def _ensure_catalog_item(
    db: Session,
    *,
    company_id: str,
    item_type: str,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    existing = _find_catalog_item(db, company_id=company_id, item_type=item_type)
    if existing is not None:
        return existing

    classification = _ensure_classification(
        db,
        company_id=company_id,
        item_type="service" if item_type == "service" else "product",
        context=context,
        rng=rng,
    )
    suffix = f"{int(time.time() * 1000)}-{uuid4().hex[:6]}"
    payload = _catalog_payload(
        company_id=company_id,
        item_type=item_type,
        suffix=suffix,
        classification=classification,
        rng=rng,
    )
    return create_catalog_item(db, payload, **_request_kwargs(context))


def _generate_participants(
    db: Session,
    *,
    company_id: str,
    count: int,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    customers = 0
    suppliers = 0
    for index in range(count):
        participant_type = "customer" if index % 2 == 0 else "supplier"
        suffix = f"{int(time.time() * 1000)}-{index}-{uuid4().hex[:6]}"
        payload = _participant_payload(
            company_id=company_id,
            participant_type=participant_type,
            suffix=suffix,
            rng=rng,
        )
        row = create_participant(db, payload, **_request_kwargs(context))
        created_ids.append(row["id"])
        if participant_type == "customer":
            customers += 1
        else:
            suppliers += 1

    return {
        "count": count,
        "created_ids": created_ids,
        "customers": customers,
        "suppliers": suppliers,
    }


def _generate_fiscal_classifications(
    db: Session,
    *,
    company_id: str,
    count: int,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    product_count = 0
    service_count = 0
    for index in range(count):
        item_type = "product" if index % 2 == 0 else "service"
        suffix = f"{int(time.time() * 1000)}-{index}-{uuid4().hex[:6]}"
        payload = _classification_payload(
            company_id=company_id,
            item_type=item_type,
            suffix=suffix,
            rng=rng,
        )
        row = create_fiscal_classification(db, payload, **_request_kwargs(context))
        created_ids.append(row["id"])
        if item_type == "product":
            product_count += 1
        else:
            service_count += 1

    return {
        "count": count,
        "created_ids": created_ids,
        "product_classifications": product_count,
        "service_classifications": service_count,
    }


def _generate_catalog_items(
    db: Session,
    *,
    company_id: str,
    count: int,
    item_type: str,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    for index in range(count):
        classification = _ensure_classification(
            db,
            company_id=company_id,
            item_type="service" if item_type == "service" else "product",
            context=context,
            rng=rng,
        )
        suffix = f"{int(time.time() * 1000)}-{index}-{uuid4().hex[:6]}"
        payload = _catalog_payload(
            company_id=company_id,
            item_type=item_type,
            suffix=suffix,
            classification=classification,
            rng=rng,
        )
        row = create_catalog_item(db, payload, **_request_kwargs(context))
        created_ids.append(row["id"])

    return {"count": count, "created_ids": created_ids}


def _generate_sales(
    db: Session,
    *,
    company_id: str,
    count: int,
    confirm: bool,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    confirmed_ids: list[str] = []
    customer = _ensure_participant(
        db,
        company_id=company_id,
        participant_type="customer",
        context=context,
        rng=rng,
    )
    product_item = _ensure_catalog_item(
        db,
        company_id=company_id,
        item_type="product",
        context=context,
        rng=rng,
    )
    service_item = _ensure_catalog_item(
        db,
        company_id=company_id,
        item_type="service",
        context=context,
        rng=rng,
    )

    for index in range(count):
        item = product_item if index % 2 == 0 else service_item
        item_type = "product" if index % 2 == 0 else "service"
        qty_value = str(rng.randint(1, 5))
        unit_price = (
            ((item.get("financial_settings") or {}).get("default_sale_price"))
            or _money_text(rng.randint(50, 200))
        )
        sale = create_sale(
            db,
            SaleCreate(
                company_id=company_id,
                participant_id=customer["id"],
                sale_type=item_type,
                origin="manual",
                operation_nature="normal_sale",
                issue_date=_today_plus(0),
                competency_date=_today_plus(0),
                notes="Venda gerada pelo módulo Stress e Testes.",
                items=[
                    {
                        "item_id": item["id"],
                        "fiscal_classification_id": ((item.get("fiscal_settings") or {}).get("fiscal_classification_id")),
                        "description": item["name"],
                        "quantity": qty_value,
                        "unit": item.get("unit") or ("UN" if item_type == "product" else "SERV"),
                        "unit_price": unit_price,
                        "discount_amount": "0",
                        "freight_amount": "0",
                        "tax_amount": "0",
                    }
                ],
                payment_plans=[],
            ),
            **_request_kwargs(context),
        )
        created_ids.append(sale["id"])
        if confirm:
            confirmed = confirm_sale(
                db,
                sale["id"],
                SaleStatusChange(reason="Confirmação automática do módulo Stress e Testes."),
                **_request_kwargs(context),
            )
            confirmed_ids.append(confirmed["id"])

    return {
        "count": count,
        "created_ids": created_ids,
        "confirmed_ids": confirmed_ids,
        "confirmed": confirm,
    }


def _generate_receivables(
    db: Session,
    *,
    company_id: str,
    count: int,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    customer = _ensure_participant(
        db,
        company_id=company_id,
        participant_type="customer",
        context=context,
        rng=rng,
    )
    for index in range(count):
        amount = _money_text(rng.randint(80, 1800))
        due_date = _today_plus(rng.randint(3, 45))
        title = create_manual_receivable(
            db,
            FinancialTitleCreate(
                company_id=company_id,
                participant_id=customer["id"],
                title_type="manual",
                source_type="manual",
                source_id=f"stress-receivable-{int(time.time() * 1000)}-{index}",
                payment_method_id=None,
                payment_method_code="pix",
                financial_category_id=None,
                cost_center_id=None,
                expected_financial_account_id=None,
                document_reference=f"STRESS-REC-{uuid4().hex[:8].upper()}",
                installment_number=1,
                installment_total=1,
                issue_date=_today_plus(0),
                competency_date=_today_plus(0),
                due_date=due_date,
                expected_payment_date=due_date,
                gross_amount=amount,
                discount_amount="0",
                interest_amount="0",
                penalty_amount="0",
                fee_amount="0",
                fiscal_status="pending_document",
                notes="Título manual gerado pelo módulo Stress e Testes.",
                metadata={"generated_by": "stress-tests"},
            ),
            **_request_kwargs(context),
        )
        created_ids.append(title["id"])
    return {"count": count, "created_ids": created_ids}


def _generate_purchases(
    db: Session,
    *,
    company_id: str,
    count: int,
    confirm: bool,
    context: StressRequestContext,
    rng: random.Random,
) -> dict[str, Any]:
    created_ids: list[str] = []
    confirmed_ids: list[str] = []
    generated_payables: list[str] = []
    supplier = _ensure_participant(
        db,
        company_id=company_id,
        participant_type="supplier",
        context=context,
        rng=rng,
    )

    for index in range(count):
        quantity = Decimal(str(rng.randint(1, 5)))
        unit_cost = _money(rng.randint(50, 900))
        total_amount = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        draft = create_purchase_draft(
            db,
            PurchaseCreate(
                company_id=company_id,
                participant_id=supplier["id"],
                purchase_type="expense",
                origin="manual",
                issue_date=_today_plus(0),
                competency_date=_today_plus(0),
                document_type="invoice",
                document_number=f"STRESS-BUY-{uuid4().hex[:8].upper()}",
                invoice_total_amount=_money_text(total_amount),
                notes="Compra/despesa gerada pelo módulo Stress e Testes.",
                items=[
                    {
                        "item_id": None,
                        "fiscal_classification_id": None,
                        "description": f"Despesa stress {index + 1}",
                        "quantity": str(quantity),
                        "unit": "UN",
                        "unit_cost": _money_text(unit_cost),
                        "discount_amount": "0",
                        "freight_amount": "0",
                        "tax_amount": "0",
                        "metadata": {},
                    }
                ],
            ),
            **_request_kwargs(context),
        )
        created_ids.append(draft["id"])
        if confirm:
            confirmed = confirm_purchase(
                db,
                draft["id"],
                PurchaseConfirmPayload(
                    reason="Confirmação automática do módulo Stress e Testes.",
                    installments=[
                        {
                            "due_date": _today_plus(rng.randint(3, 40)),
                            "amount": draft["payable_total_amount"],
                            "expected_payment_date": None,
                            "expected_financial_account_id": None,
                            "payment_method_id": None,
                            "payment_method_code": "pix",
                            "document_reference": draft.get("document_number") or draft["id"],
                            "notes": "Parcela automática do stress.",
                            "metadata": {"generated_by": "stress-tests"},
                        }
                    ],
                ),
                **_request_kwargs(context),
            )
            confirmed_ids.append(confirmed["purchase"]["id"])
            generated_payables.extend([payable["id"] for payable in confirmed["payables"]])

    return {
        "count": count,
        "created_ids": created_ids,
        "confirmed_ids": confirmed_ids,
        "generated_payable_ids": generated_payables,
        "confirmed": confirm,
    }


def get_stress_rules() -> dict[str, Any]:
    return {
        "module": "stress_tests",
        "purpose": (
            "Gerar massa sintética controlada para validar banco de dados e lógica operacional "
            "na empresa logada."
        ),
        "security": {
            "requires_auth": True,
            "requires_permission": "users.manage",
            "company_scope": "session_company_only",
        },
        "generators": [
            "participants",
            "fiscal_classifications",
            "products",
            "services",
            "sales",
            "receivables",
            "purchases",
        ],
        "limits": {
            "max_per_generator": 200,
        },
    }


def get_stress_summary(db: Session, *, principal: SecurityPrincipal) -> dict[str, Any]:
    return {
        "company_id": principal.company_id,
        "counts": _company_counts(db, principal.company_id),
        "notes": [
            "Resumo limitado à empresa da sessão autenticada.",
            "Use o endpoint de geração para criar massa sintética de teste.",
        ],
    }


def run_stress_generation(
    db: Session,
    *,
    principal: SecurityPrincipal,
    payload: Any,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    company_id = principal.company_id
    assert_valid_id(company_id, "emp")
    context = StressRequestContext(
        actor_id=principal.user_id,
        source=AuditSource.API,
        request_id=request_id,
        correlation_id=correlation_id,
    )
    rng = _seed(company_id)
    before = _company_counts(db, company_id)

    created: dict[str, Any] = {}

    if payload.participants > 0:
        created["participants"] = _generate_participants(
            db,
            company_id=company_id,
            count=payload.participants,
            context=context,
            rng=rng,
        )

    if payload.fiscal_classifications > 0:
        created["fiscal_classifications"] = _generate_fiscal_classifications(
            db,
            company_id=company_id,
            count=payload.fiscal_classifications,
            context=context,
            rng=rng,
        )

    if payload.products > 0:
        created["products"] = _generate_catalog_items(
            db,
            company_id=company_id,
            count=payload.products,
            item_type="product",
            context=context,
            rng=rng,
        )

    if payload.services > 0:
        created["services"] = _generate_catalog_items(
            db,
            company_id=company_id,
            count=payload.services,
            item_type="service",
            context=context,
            rng=rng,
        )

    if payload.sales > 0:
        created["sales"] = _generate_sales(
            db,
            company_id=company_id,
            count=payload.sales,
            confirm=payload.confirm_sales,
            context=context,
            rng=rng,
        )

    if payload.receivables > 0:
        created["receivables"] = _generate_receivables(
            db,
            company_id=company_id,
            count=payload.receivables,
            context=context,
            rng=rng,
        )

    if payload.purchases > 0:
        created["purchases"] = _generate_purchases(
            db,
            company_id=company_id,
            count=payload.purchases,
            confirm=payload.confirm_purchases,
            context=context,
            rng=rng,
        )

    after = _company_counts(db, company_id)
    deltas = {key: after[key] - before.get(key, 0) for key in after}

    return {
        "company_id": company_id,
        "requested": {
            "participants": payload.participants,
            "fiscal_classifications": payload.fiscal_classifications,
            "products": payload.products,
            "services": payload.services,
            "sales": payload.sales,
            "receivables": payload.receivables,
            "purchases": payload.purchases,
            "confirm_sales": payload.confirm_sales,
            "confirm_purchases": payload.confirm_purchases,
        },
        "before": before,
        "after": after,
        "delta": deltas,
        "created": created,
        "notes": [
            "Todos os registros foram gerados somente na empresa da sessão autenticada.",
            "Dados gerados são sintéticos e destinados a stress/validação de lógica.",
        ],
    }

