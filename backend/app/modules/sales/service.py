from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.modules.catalog.models import CatalogItemStatus, catalog_item_to_dict
from app.modules.catalog.repository import (
    catalog_item_db_to_domain,
    get_catalog_item as repository_get_catalog_item,
    list_catalog_items as repository_list_catalog_items,
)
from app.modules.company.repository import get_company as repository_get_company
from app.modules.fiscal_classification.models import FiscalRecordStatus, fiscal_classification_to_dict
from app.modules.fiscal_classification.repository import (
    fiscal_classification_db_to_domain,
    get_fiscal_classification as repository_get_fiscal_classification,
    list_fiscal_classifications,
)
from app.modules.participants.models import ParticipantStatus, ParticipantType, participant_to_dict
from app.modules.participants.repository import get_participant as repository_get_participant, participant_db_to_domain
from app.modules.sales.models import Sale, SaleDiscountType, SaleFiscalStatus, SaleItem, SalePaymentPlan, SalePaymentPlanStatus, SaleOperationNature, SaleOrigin, SaleStatus, SaleType, sale_to_dict
from app.modules.sales.repository import (
    catalog_item_fiscal_rule_db_to_dict,
    count_sales,
    count_sales_by_status,
    count_sales_filtered,
    create_payment_method,

    create_operation_nature,
    create_sale as repository_create_sale,
    create_sale_status_history,
    find_catalog_item_fiscal_rule,
    get_operation_nature,
    get_operation_nature_by_code,
    get_payment_method,
    get_payment_method_by_code,
    get_sale as repository_get_sale,
    get_sale_for_update as repository_get_sale_for_update,
    list_catalog_item_fiscal_rules as repository_list_fiscal_rules,
    list_operation_natures as repository_list_operation_natures,
    list_payment_methods as repository_list_payment_methods,
    list_sale_status_history,
    list_sales as repository_list_sales,
    next_sale_number,
    operation_nature_db_to_dict,
    payment_method_db_to_dict,
    sale_db_to_domain,
    sale_status_history_to_dict,
    update_sale as repository_update_sale,
    update_sale_header_only,
)
from app.modules.sales.schemas import SaleCreate, SaleStatusChange, SaleUpdate
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event, build_updated_event
from app.shared.audit_repository import audit_event_db_to_dict, count_audit_events_for_company, create_audit_event, list_audit_events_for_entity
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id


MONEY_QUANT = Decimal("0.01")
QUANTITY_QUANT = Decimal("0.0001")

DEFAULT_OPERATION_NATURES: list[dict[str, Any]] = [
    {
        "code": "normal_sale",
        "name": "Venda normal",
        "description": "Operação comercial padrão com cobrança integral e faturamento integral.",
        "requires_reason": False,
        "affects_revenue": True,
        "affects_accounts_receivable": True,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "full",
        "default_invoice_behavior": "full",
    },
    {
        "code": "bonus",
        "name": "Bonificação",
        "description": "Entrega sem cobrança comercial. Exige motivo e mantém rastro fiscal para documento futuro.",
        "requires_reason": True,
        "affects_revenue": False,
        "affects_accounts_receivable": False,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "zero",
        "default_invoice_behavior": "full",
    },
    {
        "code": "sample",
        "name": "Amostra grátis",
        "description": "Amostra enviada ao cliente, sem cobrança financeira por padrão.",
        "requires_reason": True,
        "affects_revenue": False,
        "affects_accounts_receivable": False,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "zero",
        "default_invoice_behavior": "full",
    },
    {
        "code": "exchange",
        "name": "Troca",
        "description": "Operação de troca comercial. Pode exigir análise fiscal/financeira posterior.",
        "requires_reason": True,
        "affects_revenue": False,
        "affects_accounts_receivable": False,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "zero",
        "default_invoice_behavior": "full",
    },
    {
        "code": "courtesy",
        "name": "Cortesia",
        "description": "Cortesia comercial ou relacionamento. Não gera contas a receber por padrão.",
        "requires_reason": True,
        "affects_revenue": False,
        "affects_accounts_receivable": False,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "zero",
        "default_invoice_behavior": "full",
    },
    {
        "code": "replacement",
        "name": "Reposição",
        "description": "Reposição por falha, avaria ou ajuste operacional.",
        "requires_reason": True,
        "affects_revenue": False,
        "affects_accounts_receivable": False,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "zero",
        "default_invoice_behavior": "full",
    },
    {
        "code": "other",
        "name": "Outra natureza",
        "description": "Natureza excepcional. Deve ser revisada no backoffice.",
        "requires_reason": True,
        "affects_revenue": True,
        "affects_accounts_receivable": True,
        "affects_stock": True,
        "requires_fiscal_document": True,
        "default_receivable_behavior": "full",
        "default_invoice_behavior": "full",
    },
]

DEFAULT_PAYMENT_METHODS: list[dict[str, Any]] = [
    {
        "code": "pix",
        "name": "Pix",
        "method_type": "instant_transfer",
        "description": "Recebimento por Pix. Baixa e conciliação serão tratadas no financeiro futuramente.",
        "requires_reference": False,
        "default_due_behavior": "immediate",
        "settings_json": {"supports_split": True, "ar_hint": "generate_receivable_or_settlement"},
    },
    {
        "code": "credit_card",
        "name": "Cartão de crédito",
        "method_type": "card",
        "description": "Recebimento por cartão de crédito. Pode gerar taxa, agenda de recebíveis e conciliação futura.",
        "requires_reference": False,
        "default_due_behavior": "scheduled",
        "settings_json": {"supports_installments": True, "ar_hint": "generate_card_receivable"},
    },
    {
        "code": "debit_card",
        "name": "Cartão de débito",
        "method_type": "card",
        "description": "Recebimento por cartão de débito.",
        "requires_reference": False,
        "default_due_behavior": "scheduled",
        "settings_json": {"supports_installments": False, "ar_hint": "generate_card_receivable"},
    },
    {
        "code": "cash",
        "name": "Dinheiro",
        "method_type": "cash",
        "description": "Recebimento em caixa físico.",
        "requires_reference": False,
        "default_due_behavior": "immediate",
        "settings_json": {"supports_split": True, "ar_hint": "generate_cash_settlement"},
    },
    {
        "code": "boleto",
        "name": "Boleto",
        "method_type": "bank_slip",
        "description": "Recebimento por boleto. Prepara título a receber com vencimento.",
        "requires_reference": False,
        "default_due_behavior": "due_date",
        "settings_json": {"supports_installments": True, "ar_hint": "generate_open_receivable"},
    },
    {
        "code": "bank_transfer",
        "name": "Transferência bancária",
        "method_type": "bank_transfer",
        "description": "TED/DOC/transferência ou depósito identificado.",
        "requires_reference": False,
        "default_due_behavior": "immediate",
        "settings_json": {"supports_split": True, "ar_hint": "generate_receivable_or_settlement"},
    },
    {
        "code": "store_credit",
        "name": "Crédito/vale do cliente",
        "method_type": "credit",
        "description": "Uso de crédito, vale, compensação ou saldo do cliente.",
        "requires_reference": True,
        "default_due_behavior": "immediate",
        "settings_json": {"requires_backoffice_review": True, "ar_hint": "generate_compensation_link"},
    },
    {
        "code": "other",
        "name": "Outra forma",
        "method_type": "other",
        "description": "Forma excepcional. Deve ser revisada no financeiro.",
        "requires_reference": True,
        "default_due_behavior": "manual",
        "settings_json": {"requires_backoffice_review": True},
    },
]


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _decimal(value: str | Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _money(value: str | Decimal | int | float | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _quantity(value: str | Decimal | int | float | None) -> Decimal:
    return _decimal(value).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _normalize_discount_metadata(*, discount_amount: Decimal, discount_category: str | None, discount_reason: str | None) -> tuple[str | None, str | None]:
    category = discount_category.strip().lower() if discount_category else None
    reason = discount_reason.strip() if discount_reason else None
    if discount_amount > Decimal("0"):
        if not category:
            raise ValueError("Categoria do desconto é obrigatória quando há desconto.")
        if not reason:
            raise ValueError("Motivo do desconto é obrigatório quando há desconto.")
        return category, reason
    return None, None




def _calculate_header_discount(
    *,
    subtotal: Decimal,
    discount_type: str,
    discount_amount: str | Decimal | None,
    discount_percentage: str | Decimal | None,
) -> tuple[Decimal, SaleDiscountType, Decimal | None]:
    normalized_type = SaleDiscountType.PERCENTAGE if discount_type == SaleDiscountType.PERCENTAGE.value else SaleDiscountType.AMOUNT

    if normalized_type == SaleDiscountType.PERCENTAGE:
        percentage = _decimal(discount_percentage).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        if percentage <= Decimal("0") or percentage > Decimal("100"):
            raise ValueError("Percentual de desconto deve ser maior que zero e menor ou igual a 100.")
        amount = (subtotal * percentage / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        return amount, normalized_type, percentage

    amount = _money(discount_amount)
    return amount, normalized_type, None

def _assert_company_id(company_id: str) -> None:
    assert_valid_id(company_id, "emp")


def _assert_participant_id(participant_id: str) -> None:
    assert_valid_id(participant_id, "part")


def _assert_item_id(item_id: str) -> None:
    assert_valid_id(item_id, "item")


def _assert_fiscal_classification_id(fiscal_classification_id: str | None) -> None:
    if fiscal_classification_id is not None:
        assert_valid_id(fiscal_classification_id, "fclass")


def _assert_sale_id(sale_id: str) -> None:
    assert_valid_id(sale_id, "sale")


def _assert_actor_id(actor_id: str | None) -> None:
    if actor_id is not None:
        assert_valid_id(actor_id, "user")


def _assert_company_exists(db: Session, company_id: str) -> None:
    _assert_company_id(company_id)
    if repository_get_company(db, company_id) is None:
        raise ValueError("Empresa vinculada à venda não encontrada.")


def _create_audit_context(actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> AuditContext:
    _assert_actor_id(actor_id)
    if not isinstance(source, AuditSource):
        source = AuditSource(source)
    return AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def _get_sale_db_or_raise(db: Session, sale_id: str):
    _assert_sale_id(sale_id)
    sale_db = repository_get_sale(db, sale_id)
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    return sale_db


def _get_customer_or_raise(db: Session, company_id: str, participant_id: str) -> dict[str, Any]:
    _assert_participant_id(participant_id)
    participant_db = repository_get_participant(db, participant_id)
    if participant_db is None:
        raise ValueError("Participante da venda não encontrado.")
    participant = participant_db_to_domain(participant_db)
    if participant.company_id != company_id:
        raise ValueError("Participante não pertence à empresa da venda.")
    if participant.participant_type != ParticipantType.CUSTOMER:
        raise ValueError("Venda exige participante do tipo cliente.")
    if participant.status != ParticipantStatus.ACTIVE:
        raise ValueError("Cliente precisa estar ativo para gerar venda.")
    return participant_to_dict(participant)


def _get_item_snapshot_or_raise(db: Session, company_id: str, item_id: str) -> dict[str, Any]:
    _assert_item_id(item_id)
    item_db = repository_get_catalog_item(db, item_id)
    if item_db is None:
        raise ValueError("Item da venda não encontrado.")
    item = catalog_item_db_to_domain(item_db)
    if item.company_id != company_id:
        raise ValueError("Item não pertence à empresa da venda.")
    if item.status != CatalogItemStatus.ACTIVE:
        raise ValueError("Item precisa estar ativo para venda.")
    return catalog_item_to_dict(item)


def ensure_default_operation_natures(db: Session, company_id: str) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    existing = repository_list_operation_natures(db, company_id=company_id, status=None)
    existing_keys = {(row.code, row.sale_type) for row in existing}
    now = utc_now()
    created = False
    for sale_type in ("both",):
        for template in DEFAULT_OPERATION_NATURES:
            key = (template["code"], sale_type)
            if key in existing_keys:
                continue
            create_operation_nature(
                db,
                id=generate_id("opnat"),
                company_id=company_id,
                sale_type=sale_type,
                status="active",
                created_at=now,
                updated_at=now,
                deleted_at=None,
                **template,
            )
            created = True
    if created:
        db.commit()
    return [operation_nature_db_to_dict(row) for row in repository_list_operation_natures(db, company_id=company_id, status="active")]


def ensure_default_payment_methods(db: Session, company_id: str) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    existing = repository_list_payment_methods(db, company_id=company_id, status=None)
    existing_codes = {row.code for row in existing}
    now = utc_now()
    created = False
    for template in DEFAULT_PAYMENT_METHODS:
        if template["code"] in existing_codes:
            continue
        create_payment_method(
            db,
            id=generate_id("paym"),
            company_id=company_id,
            status="active",
            created_at=now,
            updated_at=now,
            deleted_at=None,
            **template,
        )
        created = True
    if created:
        db.commit()
    return [payment_method_db_to_dict(row) for row in repository_list_payment_methods(db, company_id=company_id, status="active")]


def list_payment_methods(db: Session, *, company_id: str) -> list[dict[str, Any]]:
    return ensure_default_payment_methods(db, company_id)

def list_operation_natures(db: Session, *, company_id: str, sale_type: SaleType | str | None = None) -> list[dict[str, Any]]:
    ensure_default_operation_natures(db, company_id)
    sale_type_value = sale_type.value if isinstance(sale_type, SaleType) else sale_type
    rows = repository_list_operation_natures(db, company_id=company_id, sale_type=sale_type_value, status="active")
    return [operation_nature_db_to_dict(row) for row in rows]


def list_catalog_item_fiscal_rules(db: Session, *, company_id: str, catalog_item_id: str | None = None, operation_nature_id: str | None = None) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    rows = repository_list_fiscal_rules(db, company_id=company_id, catalog_item_id=catalog_item_id, operation_nature_id=operation_nature_id)
    return [catalog_item_fiscal_rule_db_to_dict(row) for row in rows]


def _price_readiness_from_item_snapshot(item_snapshot: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    financial_settings = item_snapshot.get("financial_settings") or {}
    default_sale_price = financial_settings.get("default_sale_price")

    if default_sale_price is None:
        return False, None, "Item sem preço padrão de venda no catálogo."

    try:
        price = _money(default_sale_price)
    except Exception:
        return False, str(default_sale_price), "Preço padrão de venda inválido no catálogo."

    if price < Decimal("0.00"):
        return False, _decimal_text(price), "Preço padrão de venda não pode ser negativo."

    return True, _decimal_text(price), None


def _build_sale_item_readiness_payload(
    db: Session,
    *,
    company_id: str,
    item_db: Any,
    sale_type: SaleType,
    operation_nature_snapshot: dict[str, Any],
    valid_on: date | None,
    location_id: str | None,
) -> dict[str, Any]:
    item = catalog_item_db_to_domain(item_db)
    item_snapshot = catalog_item_to_dict(item)
    blocking_reasons: list[str] = []

    is_active = item.status == CatalogItemStatus.ACTIVE
    if not is_active:
        blocking_reasons.append("Item não está ativo no catálogo.")

    item_type_matches = item.item_type.value == sale_type.value
    if not item_type_matches:
        blocking_reasons.append("Item incompatível com o tipo da venda.")

    price_ready, default_sale_price, price_block_reason = _price_readiness_from_item_snapshot(item_snapshot)
    if price_block_reason is not None:
        blocking_reasons.append(price_block_reason)

    fiscal_required = bool(operation_nature_snapshot.get("requires_fiscal_document", True))
    fiscal_classification_id: str | None = None
    fiscal_snapshot: dict[str, Any] | None = None
    fiscal_resolution_source = "not_required" if not fiscal_required else "not_resolved"
    fiscal_block_reason: str | None = None

    if fiscal_required:
        try:
            fiscal_classification_id, fiscal_snapshot, fiscal_resolution_source = _resolve_fiscal_snapshot(
                db,
                company_id=company_id,
                item_id=item.id,
                sale_type=sale_type,
                operation_nature_id=operation_nature_snapshot.get("id"),
                payload_fiscal_classification_id=None,
                item_snapshot=item_snapshot,
                valid_on=valid_on,
            )
        except Exception as error:
            fiscal_block_reason = str(error)

        if fiscal_snapshot is None:
            fiscal_block_reason = fiscal_block_reason or "Item sem classificação fiscal ativa compatível com a operação."
            blocking_reasons.append(fiscal_block_reason)

    fiscal_ready = not fiscal_required or fiscal_snapshot is not None

    stock_payload: dict[str, Any] | None = None
    stock_ready = True
    stock_required = sale_type == SaleType.PRODUCT

    if stock_required:
        try:
            from app.modules.stock.service import get_item_availability

            stock_payload = get_item_availability(
                db,
                company_id=company_id,
                item_id=item.id,
                location_id=location_id,
            )
            if item_snapshot.get("inventory_settings", {}).get("track_stock") and not stock_payload.get("can_sell_now"):
                stock_ready = False
                blocking_reasons.append(stock_payload.get("block_reason") or "Produto sem estoque efetivo para venda.")
        except Exception as error:
            stock_ready = False
            blocking_reasons.append(f"Disponibilidade de estoque indisponível: {error}")

    can_select = is_active and item_type_matches and price_ready and fiscal_ready and stock_ready

    return {
        "company_id": company_id,
        "item_id": item.id,
        "item_name": item.name,
        "item_type": item.item_type.value,
        "sale_type": sale_type.value,
        "can_select": can_select,
        "blocking_reasons": blocking_reasons,
        "price_ready": price_ready,
        "default_sale_price": default_sale_price,
        "fiscal_required": fiscal_required,
        "fiscal_ready": fiscal_ready,
        "fiscal_classification_id": fiscal_classification_id,
        "fiscal_resolution_source": fiscal_resolution_source,
        "fiscal_block_reason": fiscal_block_reason,
        "stock_required": stock_required,
        "stock_ready": stock_ready,
        "stock": stock_payload,
    }


def list_sale_item_readiness(
    db: Session,
    *,
    company_id: str,
    sale_type: SaleType | str,
    operation_nature: SaleOperationNature | str = SaleOperationNature.NORMAL_SALE,
    operation_nature_id: str | None = None,
    valid_on: date | None = None,
    location_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    sale_type_value = sale_type if isinstance(sale_type, SaleType) else SaleType(sale_type)
    operation_nature_value = operation_nature if isinstance(operation_nature, SaleOperationNature) else SaleOperationNature(operation_nature)
    operation_nature_snapshot = _resolve_operation_nature(
        db,
        company_id=company_id,
        sale_type=sale_type_value,
        operation_nature_code=operation_nature_value,
        operation_nature_id=operation_nature_id,
        reason="readiness_check",
    )
    item_rows = repository_list_catalog_items(
        db,
        company_id=company_id,
        item_type=sale_type_value.value,
        status="active",
        limit=limit,
        offset=offset,
    )

    return [
        _build_sale_item_readiness_payload(
            db,
            company_id=company_id,
            item_db=item_db,
            sale_type=sale_type_value,
            operation_nature_snapshot=operation_nature_snapshot,
            valid_on=valid_on,
            location_id=location_id,
        )
        for item_db in item_rows
    ]


def _resolve_operation_nature(db: Session, *, company_id: str, sale_type: SaleType, operation_nature_code: SaleOperationNature, operation_nature_id: str | None, reason: str | None) -> dict[str, Any]:
    ensure_default_operation_natures(db, company_id)
    row = None
    if operation_nature_id:
        assert_valid_id(operation_nature_id, "opnat")
        row = get_operation_nature(db, operation_nature_id)
        if row is None or row.company_id != company_id or row.status != "active" or row.deleted_at is not None:
            raise ValueError("Natureza da operação não encontrada ou inativa.")
        if row.sale_type not in {sale_type.value, "both"}:
            raise ValueError("Natureza da operação incompatível com o tipo da venda.")
    if row is None:
        row = get_operation_nature_by_code(db, company_id=company_id, code=operation_nature_code.value, sale_type=sale_type.value)
    if row is None:
        raise ValueError("Natureza da operação não configurada para a empresa.")
    if row.requires_reason and not (reason or "").strip():
        raise ValueError("Motivo da natureza da operação é obrigatório para esta natureza.")
    return operation_nature_db_to_dict(row)


def _operation_total(behavior: str, total_amount: Decimal) -> Decimal:
    if behavior == "zero":
        return Decimal("0.00")
    return total_amount


def _get_fiscal_snapshot_or_raise(db: Session, *, company_id: str, fiscal_classification_id: str | None, item_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    _assert_fiscal_classification_id(fiscal_classification_id)
    if fiscal_classification_id is None:
        return None
    classification_db = repository_get_fiscal_classification(db, fiscal_classification_id)
    if classification_db is None:
        raise ValueError("Classificação fiscal da venda não encontrada.")
    classification = fiscal_classification_db_to_domain(classification_db)
    if classification.company_id != company_id:
        raise ValueError("Classificação fiscal não pertence à empresa da venda.")
    if classification.status != FiscalRecordStatus.ACTIVE:
        raise ValueError("Classificação fiscal precisa estar ativa para venda.")
    item_type = item_snapshot.get("item_type")
    if classification.item_type.value not in {item_type, "both", "operation"}:
        raise ValueError("Classificação fiscal incompatível com o tipo do item.")
    return fiscal_classification_to_dict(classification)


def _fallback_fiscal_classification_id(db: Session, *, company_id: str, item_snapshot: dict[str, Any], sale_type: SaleType, valid_on: date | None) -> str | None:
    fiscal_settings = item_snapshot.get("fiscal_settings") or {}
    ncm = fiscal_settings.get("ncm")
    nbs = fiscal_settings.get("nbs")
    rows = list_fiscal_classifications(
        db,
        company_id=company_id,
        status_filter="active",
        item_type=sale_type.value,
        ncm=ncm if ncm else None,
        nbs=nbs if nbs else None,
        valid_on=valid_on,
        limit=1,
        offset=0,
    )
    if rows:
        return rows[0].id
    return None


def _resolve_fiscal_snapshot(
    db: Session,
    *,
    company_id: str,
    item_id: str,
    sale_type: SaleType,
    operation_nature_id: str | None,
    payload_fiscal_classification_id: str | None,
    item_snapshot: dict[str, Any],
    valid_on: date | None,
) -> tuple[str | None, dict[str, Any] | None, str]:
    fiscal_classification_id = payload_fiscal_classification_id
    source = "payload"
    if fiscal_classification_id is None and operation_nature_id:
        rule = find_catalog_item_fiscal_rule(db, company_id=company_id, catalog_item_id=item_id, operation_nature_id=operation_nature_id, sale_type=sale_type.value, valid_on=valid_on)
        if rule is not None:
            fiscal_classification_id = rule.fiscal_classification_id
            source = "catalog_item_fiscal_rule"
    if fiscal_classification_id is None:
        fiscal_classification_id = _fallback_fiscal_classification_id(db, company_id=company_id, item_snapshot=item_snapshot, sale_type=sale_type, valid_on=valid_on)
        source = "fallback_by_item_ncm_nbs" if fiscal_classification_id else "not_resolved"
    snapshot = _get_fiscal_snapshot_or_raise(db, company_id=company_id, fiscal_classification_id=fiscal_classification_id, item_snapshot=item_snapshot)
    if snapshot is not None:
        snapshot = {**snapshot, "resolution_source": source}
    return fiscal_classification_id, snapshot, source


def _unit_price_from_payload_or_item(payload_unit_price: str | None, item_snapshot: dict[str, Any]) -> Decimal:
    """Resolve o preço unitário oficial do item na venda.

    Regra de domínio do Bloco 5D:
    - A tela operacional mostra o preço, mas não decide o preço oficial.
    - O backend deve usar o preço vigente do cadastro do item.
    - Se alguém tentar enviar unit_price diferente via API, a venda deve ser bloqueada.

    A liberação futura de preço manual deve ser outro fluxo: permissão, motivo,
    política comercial, alçada e auditoria. Não deve ser aceita silenciosamente aqui.
    """
    financial_settings = item_snapshot.get("financial_settings") or {}
    default_sale_price = financial_settings.get("default_sale_price")
    if default_sale_price is None:
        raise ValueError("Item não possui preço padrão de venda configurado.")

    official_price = _money(default_sale_price)

    if payload_unit_price is not None:
        informed_price = _money(payload_unit_price)
        if informed_price != official_price:
            raise ValueError(
                "Preço unitário não pode ser alterado na operação de venda. "
                "O preço oficial vem do cadastro do produto/serviço."
            )

    return official_price


def _item_tracks_stock_for_sale(item_snapshot: dict[str, Any]) -> bool:
    return bool((item_snapshot.get("inventory_settings") or {}).get("track_stock"))


def _item_allows_negative_stock_for_sale(item_snapshot: dict[str, Any]) -> bool:
    return bool((item_snapshot.get("inventory_settings") or {}).get("allow_negative_stock"))


def _stock_lot_expiration_to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _resolve_sale_item_stock_lot(
    db: Session,
    *,
    company_id: str,
    item_snapshot: dict[str, Any],
    item_id: str,
    quantity: Decimal,
    stock_lot_id: str | None,
    stock_lot_code: str | None,
    stock_lot_expiration_date: date | None,
) -> tuple[str | None, str | None, date | None]:
    if not _item_tracks_stock_for_sale(item_snapshot):
        return None, None, None

    from app.modules.stock.service import get_stock_lot_payload_for_sale, list_stock_lots

    lot_payload: dict[str, Any] | None = None

    if stock_lot_id:
        lot_payload = get_stock_lot_payload_for_sale(
            db,
            company_id=company_id,
            item_id=item_id,
            lot_id=stock_lot_id,
        )
    elif stock_lot_code and stock_lot_expiration_date:
        normalized_lot_code = stock_lot_code.strip().upper()
        expected_expiration = stock_lot_expiration_date.isoformat()
        for lot in list_stock_lots(
            db,
            company_id=company_id,
            item_id=item_id,
            only_positive=False,
            limit=500,
            offset=0,
        ):
            if (
                str(lot.get("lot_code") or "").upper() == normalized_lot_code
                and str(lot.get("expiration_date") or "")[:10] == expected_expiration
            ):
                lot_payload = lot
                break

    if lot_payload is None:
        item_label = item_snapshot.get("name") or item_id
        raise ValueError(f"Produto {item_label} exige selecao de lote para venda.")

    lot_quantity = Decimal(str(lot_payload.get("quantity") or "0")).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)
    if not _item_allows_negative_stock_for_sale(item_snapshot) and lot_quantity < quantity:
        lot_label = lot_payload.get("lot_code") or lot_payload.get("id")
        raise ValueError(
            f"Saldo insuficiente no lote {lot_label}. "
            f"Disponivel: {_decimal_text(lot_quantity)}; solicitado: {_decimal_text(quantity)}."
        )

    resolved_expiration = _stock_lot_expiration_to_date(lot_payload.get("expiration_date"))
    return str(lot_payload["id"]), str(lot_payload["lot_code"]), resolved_expiration


def _build_sale_items(db: Session, *, company_id: str, sale_id: str, sale_type: SaleType, operation_nature_snapshot: dict[str, Any], valid_on: date | None, payload_items) -> tuple[list[SaleItem], dict[str, Decimal], bool]:
    if not payload_items:
        raise ValueError("Venda precisa ter pelo menos um item.")
    now = utc_now()
    items: list[SaleItem] = []
    subtotal = Decimal("0.00")
    item_discount_total = Decimal("0.00")
    item_freight_total = Decimal("0.00")
    item_tax_total = Decimal("0.00")
    item_total = Decimal("0.00")
    all_items_fiscal_ready = True

    for payload_item in payload_items:
        item_snapshot = _get_item_snapshot_or_raise(db, company_id=company_id, item_id=payload_item.item_id)
        if item_snapshot.get("item_type") != sale_type.value:
            expected = "produto" if sale_type == SaleType.PRODUCT else "serviço"
            raise ValueError(f"Venda de {expected} não aceita item de outro tipo.")
        fiscal_classification_id, fiscal_snapshot, _source = _resolve_fiscal_snapshot(
            db,
            company_id=company_id,
            item_id=payload_item.item_id,
            sale_type=sale_type,
            operation_nature_id=operation_nature_snapshot.get("id"),
            payload_fiscal_classification_id=payload_item.fiscal_classification_id,
            item_snapshot=item_snapshot,
            valid_on=valid_on,
        )
        if fiscal_snapshot is None:
            all_items_fiscal_ready = False

        quantity = _quantity(payload_item.quantity)
        stock_lot_id, stock_lot_code, stock_lot_expiration_date = _resolve_sale_item_stock_lot(
            db,
            company_id=company_id,
            item_snapshot=item_snapshot,
            item_id=payload_item.item_id,
            quantity=quantity,
            stock_lot_id=payload_item.stock_lot_id,
            stock_lot_code=payload_item.stock_lot_code,
            stock_lot_expiration_date=payload_item.stock_lot_expiration_date,
        )
        unit_price = _unit_price_from_payload_or_item(payload_item.unit_price, item_snapshot)
        discount_amount = _money(payload_item.discount_amount)
        freight_amount = _money(payload_item.freight_amount)
        tax_amount = _money(payload_item.tax_amount)
        gross_amount = (quantity * unit_price).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        total_amount = (gross_amount - discount_amount + freight_amount + tax_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if total_amount < Decimal("0"):
            raise ValueError("Total do item não pode ser negativo.")
        subtotal += gross_amount
        item_discount_total += discount_amount
        item_freight_total += freight_amount
        item_tax_total += tax_amount
        item_total += total_amount
        items.append(SaleItem(
            id=generate_id("saleitem"),
            company_id=company_id,
            sale_id=sale_id,
            item_id=payload_item.item_id,
            stock_lot_id=stock_lot_id,
            stock_lot_code=stock_lot_code,
            stock_lot_expiration_date=stock_lot_expiration_date,
            fiscal_classification_id=fiscal_classification_id,
            description=payload_item.description or item_snapshot.get("name") or "Item da venda",
            quantity=_decimal_text(quantity),
            unit=payload_item.unit or item_snapshot.get("unit") or "UN",
            unit_price=_decimal_text(unit_price),
            discount_amount=_decimal_text(discount_amount),
            freight_amount=_decimal_text(freight_amount),
            tax_amount=_decimal_text(tax_amount),
            total_amount=_decimal_text(total_amount),
            item_snapshot=item_snapshot,
            fiscal_snapshot=fiscal_snapshot,
            operation_nature_snapshot=operation_nature_snapshot,
            created_at=now,
            updated_at=now,
        ))
    return items, {
        "subtotal": subtotal.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        "item_discount_total": item_discount_total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        "item_freight_total": item_freight_total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        "item_tax_total": item_tax_total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
        "item_total": item_total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP),
    }, all_items_fiscal_ready


def _assert_payment_method_id(payment_method_id: str | None) -> None:
    if payment_method_id is not None:
        assert_valid_id(payment_method_id, "paym")


def _resolve_payment_method(db: Session, *, company_id: str, payment_method_id: str | None, payment_method_code: str | None):
    ensure_default_payment_methods(db, company_id)
    method = None
    if payment_method_id:
        _assert_payment_method_id(payment_method_id)
        method = get_payment_method(db, payment_method_id)
        if method is None or method.company_id != company_id or method.status != "active" or method.deleted_at is not None:
            raise ValueError("Forma de pagamento não encontrada ou inativa.")
    if method is None:
        code = (payment_method_code or "pix").strip().lower()
        method = get_payment_method_by_code(db, company_id=company_id, code=code)
    if method is None:
        raise ValueError("Forma de pagamento não configurada para a empresa.")
    return method


def _build_sale_payment_plans(db: Session, *, company_id: str, sale_id: str, receivable_total: Decimal, payload_payment_plans, default_due_date: date | None) -> list[SalePaymentPlan]:
    now = utc_now()
    if receivable_total <= Decimal("0.00"):
        if payload_payment_plans:
            total_informed = sum(_money(plan.amount) for plan in payload_payment_plans)
            if total_informed > Decimal("0.00"):
                raise ValueError("Venda sem valor a receber não deve ter forma de pagamento com valor.")
        return []

    plans_payload = payload_payment_plans or []
    if not plans_payload:
        # Compatibilidade para chamadas antigas da API; a tela operacional exige escolha explícita.
        from app.modules.sales.schemas import SalePaymentPlanCreate
        plans_payload = [SalePaymentPlanCreate(payment_method_code="pix", amount=_decimal_text(receivable_total), due_date=default_due_date, installments=1, notes="Plano de pagamento padrão gerado automaticamente.")]

    plans: list[SalePaymentPlan] = []
    total = Decimal("0.00")
    for payload_plan in plans_payload:
        amount = _money(payload_plan.amount)
        if amount <= Decimal("0.00"):
            raise ValueError("Valor da forma de pagamento deve ser maior que zero.")
        method = _resolve_payment_method(
            db,
            company_id=company_id,
            payment_method_id=payload_plan.payment_method_id,
            payment_method_code=payload_plan.payment_method_code,
        )
        total += amount
        plans.append(SalePaymentPlan(
            id=generate_id("salepay"),
            company_id=company_id,
            sale_id=sale_id,
            payment_method_id=method.id,
            payment_method_code=method.code,
            payment_method_name=method.name,
            amount=_decimal_text(amount),
            due_date=payload_plan.due_date or default_due_date,
            installments=payload_plan.installments,
            status=SalePaymentPlanStatus.PLANNED,
            notes=payload_plan.notes,
            metadata=payload_plan.metadata,
            created_at=now,
            updated_at=now,
        ))
    total = total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    if total != receivable_total:
        raise ValueError(f"Soma das formas de pagamento ({_decimal_text(total)}) deve ser igual ao total a receber ({_decimal_text(receivable_total)}).")
    return plans

def _build_sale_from_create(db: Session, payload: SaleCreate) -> Sale:
    _assert_company_exists(db, payload.company_id)
    participant_snapshot = _get_customer_or_raise(db, company_id=payload.company_id, participant_id=payload.participant_id)
    now = utc_now()
    sale_id = generate_id("sale")
    operation_nature_snapshot = _resolve_operation_nature(db, company_id=payload.company_id, sale_type=payload.sale_type, operation_nature_code=payload.operation_nature, operation_nature_id=payload.operation_nature_id, reason=payload.operation_nature_reason)
    valid_on = payload.issue_date or payload.competency_date
    items, totals, all_items_fiscal_ready = _build_sale_items(db, company_id=payload.company_id, sale_id=sale_id, sale_type=payload.sale_type, operation_nature_snapshot=operation_nature_snapshot, valid_on=valid_on, payload_items=payload.items)

    header_discount, discount_type, discount_percentage = _calculate_header_discount(
        subtotal=totals["subtotal"],
        discount_type=payload.discount_type,
        discount_amount=payload.discount_amount,
        discount_percentage=payload.discount_percentage,
    )
    header_freight = _money(payload.freight_amount)
    header_tax = _money(payload.tax_amount)
    discount_amount = totals["item_discount_total"] + header_discount
    freight_amount = totals["item_freight_total"] + header_freight
    tax_amount = totals["item_tax_total"] + header_tax
    total_amount = (totals["item_total"] - header_discount + header_freight + header_tax).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    if total_amount < Decimal("0"):
        raise ValueError("Total da venda não pode ser negativo.")
    discount_category, discount_reason = _normalize_discount_metadata(discount_amount=discount_amount, discount_category=payload.discount_category, discount_reason=payload.discount_reason)
    receivable_total = _operation_total(operation_nature_snapshot["default_receivable_behavior"], total_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    invoice_total = _operation_total(operation_nature_snapshot["default_invoice_behavior"], total_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    fiscal_status = SaleFiscalStatus.FISCAL_READY if all_items_fiscal_ready else SaleFiscalStatus.PENDING_CLASSIFICATION
    if not operation_nature_snapshot.get("requires_fiscal_document", True):
        fiscal_status = SaleFiscalStatus.NOT_REQUIRED

    payment_plans = _build_sale_payment_plans(
        db,
        company_id=payload.company_id,
        sale_id=sale_id,
        receivable_total=receivable_total,
        payload_payment_plans=payload.payment_plans,
        default_due_date=payload.issue_date or payload.competency_date,
    )

    return Sale(
        id=sale_id,
        company_id=payload.company_id,
        establishment_id=payload.establishment_id,
        participant_id=payload.participant_id,
        status=SaleStatus.QUOTE,
        sale_type=payload.sale_type,
        origin=payload.origin,
        operation_nature=payload.operation_nature,
        operation_nature_id=operation_nature_snapshot.get("id"),
        operation_nature_reason=payload.operation_nature_reason,
        operation_nature_snapshot=operation_nature_snapshot,
        fiscal_status=fiscal_status,
        issue_date=payload.issue_date,
        operation_date=payload.operation_date or now,
        competency_date=payload.competency_date,
        subtotal_amount=_decimal_text(totals["subtotal"]),
        discount_amount=_decimal_text(discount_amount),
        discount_type=discount_type,
        discount_percentage=_decimal_text(discount_percentage) if discount_percentage is not None else None,
        discount_category=discount_category,
        discount_reason=discount_reason,
        freight_amount=_decimal_text(freight_amount),
        tax_amount=_decimal_text(tax_amount),
        total_amount=_decimal_text(total_amount),
        receivable_total_amount=_decimal_text(receivable_total),
        invoice_total_amount=_decimal_text(invoice_total),
        participant_snapshot=participant_snapshot,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
        cancelled_at=None,
        sale_number=None,
        sale_number_text=None,
        paid_number_text=None,
        closed_at=None,
        paid_at=None,
        closed_by=None,
        paid_by=None,
        unlocked_by=None,
        unlocked_at=None,
        items=items,
        payment_plans=payment_plans,
    )


def create_sale(db: Session, payload: SaleCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    sale = _build_sale_from_create(db, payload)
    after = sale_to_dict(sale)
    try:
        repository_create_sale(db, sale)
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        create_sale_status_history(db, history_id=generate_id("salehist"), company_id=sale.company_id, sale_id=sale.id, previous_status=None, new_status=sale.status.value, reason="Criação da venda em rascunho.", source=context.source.value, actor_id=context.actor_id, occurred_at=sale.created_at)
        event = build_created_event(entity_type=AuditEntityType.SALE, entity_id=sale.id, context=context, after=after)
        create_audit_event(db, event, company_id=sale.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return after


def _date_start(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _date_end(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def list_sales(
    db: Session,
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: SaleType | str | None = None,
    status: SaleStatus | str | None = None,
    fiscal_status: SaleFiscalStatus | str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    status_value = None
    sale_type_value = None
    fiscal_status_value = None
    if company_id is not None:
        _assert_company_exists(db, company_id)
    if participant_id is not None:
        _assert_participant_id(participant_id)
    if status is not None:
        status_value = status.value if isinstance(status, SaleStatus) else SaleStatus(status).value
    if sale_type is not None:
        sale_type_value = sale_type.value if isinstance(sale_type, SaleType) else SaleType(sale_type).value
    if fiscal_status is not None:
        fiscal_status_value = fiscal_status.value if isinstance(fiscal_status, SaleFiscalStatus) else SaleFiscalStatus(fiscal_status).value
    sales = repository_list_sales(
        db,
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type_value,
        status_filter=status_value,
        fiscal_status=fiscal_status_value,
        q=(q or "").strip() or None,
        date_from=_date_start(date_from),
        date_to=_date_end(date_to),
        limit=limit,
        offset=offset,
    )
    return [sale_to_dict(sale_db_to_domain(sale)) for sale in sales]


def get_sales_summary(
    db: Session,
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: SaleType | str | None = None,
    status: SaleStatus | str | None = None,
    fiscal_status: SaleFiscalStatus | str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    status_value = None
    sale_type_value = None
    fiscal_status_value = None
    if company_id is not None:
        _assert_company_exists(db, company_id)
    if participant_id is not None:
        _assert_participant_id(participant_id)
    if status is not None:
        status_value = status.value if isinstance(status, SaleStatus) else SaleStatus(status).value
    if sale_type is not None:
        sale_type_value = sale_type.value if isinstance(sale_type, SaleType) else SaleType(sale_type).value
    if fiscal_status is not None:
        fiscal_status_value = fiscal_status.value if isinstance(fiscal_status, SaleFiscalStatus) else SaleFiscalStatus(fiscal_status).value

    normalized_q = (q or "").strip() or None
    start = _date_start(date_from)
    end = _date_end(date_to)
    total = count_sales_filtered(
        db,
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type_value,
        status_filter=status_value,
        fiscal_status=fiscal_status_value,
        q=normalized_q,
        date_from=start,
        date_to=end,
    )
    counts = {"quote": 0, "closed": 0, "paid": 0, "cancelled": 0}
    counts.update(count_sales_by_status(
        db,
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type_value,
        fiscal_status=fiscal_status_value,
        q=normalized_q,
        date_from=start,
        date_to=end,
    ))
    return {"total": total, "counts_by_status": counts}


def get_sale(db: Session, sale_id: str) -> dict[str, Any]:
    return sale_to_dict(sale_db_to_domain(_get_sale_db_or_raise(db, sale_id)))


def update_sale(db: Session, sale_id: str, payload: SaleUpdate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    sale_db = _get_sale_db_or_raise(db, sale_id)
    sale = sale_db_to_domain(sale_db)
    if sale.status != SaleStatus.QUOTE:
        raise ValueError("Apenas orçamentos podem ser alterados.")
    before = sale_to_dict(sale)
    from app.modules.sales.schemas import SaleItemCreate, SalePaymentPlanCreate
    items_for_update = payload.items if payload.items is not None else [
        SaleItemCreate(item_id=item.item_id, stock_lot_id=item.stock_lot_id, stock_lot_code=item.stock_lot_code, stock_lot_expiration_date=item.stock_lot_expiration_date, fiscal_classification_id=item.fiscal_classification_id, description=item.description, quantity=item.quantity, unit=item.unit, unit_price=item.unit_price, discount_amount=item.discount_amount, freight_amount=item.freight_amount, tax_amount=item.tax_amount)
        for item in sale.items
    ]
    merged = SaleCreate(
        company_id=sale.company_id,
        establishment_id=payload.establishment_id if payload.establishment_id is not None else sale.establishment_id,
        participant_id=payload.participant_id if payload.participant_id is not None else sale.participant_id,
        sale_type=payload.sale_type if payload.sale_type is not None else sale.sale_type,
        origin=payload.origin if payload.origin is not None else sale.origin,
        operation_nature=payload.operation_nature if payload.operation_nature is not None else sale.operation_nature,
        operation_nature_id=payload.operation_nature_id if payload.operation_nature_id is not None else sale.operation_nature_id,
        operation_nature_reason=payload.operation_nature_reason if payload.operation_nature_reason is not None else sale.operation_nature_reason,
        issue_date=payload.issue_date if payload.issue_date is not None else sale.issue_date,
        operation_date=payload.operation_date if payload.operation_date is not None else sale.operation_date,
        competency_date=payload.competency_date if payload.competency_date is not None else sale.competency_date,
        discount_amount=payload.discount_amount if payload.discount_amount is not None else sale.discount_amount,
        discount_type=payload.discount_type if payload.discount_type is not None else sale.discount_type.value,
        discount_percentage=payload.discount_percentage if payload.discount_percentage is not None else sale.discount_percentage,
        discount_category=payload.discount_category if payload.discount_category is not None else sale.discount_category,
        discount_reason=payload.discount_reason if payload.discount_reason is not None else sale.discount_reason,
        freight_amount=payload.freight_amount if payload.freight_amount is not None else sale.freight_amount,
        tax_amount=payload.tax_amount if payload.tax_amount is not None else sale.tax_amount,
        notes=payload.notes if payload.notes is not None else sale.notes,
        payment_plans=payload.payment_plans if payload.payment_plans is not None else [
            SalePaymentPlanCreate(
                payment_method_id=plan.payment_method_id,
                payment_method_code=plan.payment_method_code,
                amount=plan.amount,
                due_date=plan.due_date,
                installments=plan.installments,
                notes=plan.notes,
                metadata=plan.metadata,
            )
            for plan in sale.payment_plans
        ],
        items=items_for_update,
    )
    updated = _build_sale_from_create(db, merged)
    updated.id = sale.id
    updated.status = sale.status
    updated.created_at = sale.created_at
    updated.updated_at = utc_now()
    updated.cancelled_at = sale.cancelled_at
    updated.sale_number = sale.sale_number
    updated.sale_number_text = sale.sale_number_text
    updated.paid_number_text = sale.paid_number_text
    updated.closed_at = sale.closed_at
    updated.paid_at = sale.paid_at
    updated.closed_by = sale.closed_by
    updated.paid_by = sale.paid_by
    updated.unlocked_by = sale.unlocked_by
    updated.unlocked_at = sale.unlocked_at
    after = sale_to_dict(updated)
    try:
        repository_update_sale(db, sale_db, updated)
        if before != after:
            context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
            event = build_updated_event(entity_type=AuditEntityType.SALE, entity_id=sale.id, context=context, before=before, after=after)
            create_audit_event(db, event, company_id=sale.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return after


def _assert_sale_ready_for_confirmation(sale: Sale) -> None:
    operation_snapshot = sale.operation_nature_snapshot or {}

    if operation_snapshot.get("requires_fiscal_document", True) and sale.fiscal_status != SaleFiscalStatus.FISCAL_READY:
        pending_items = [
            item.description
            for item in sale.items
            if item.fiscal_classification_id is None or item.fiscal_snapshot is None
        ]
        suffix = f" Itens pendentes: {', '.join(pending_items)}." if pending_items else ""
        raise ValueError(
            "Venda não pode ser confirmada porque possui item sem classificação fiscal ativa compatível."
            + suffix
        )


def _change_sale_status_internal(db: Session, sale_id: str, *, new_status: SaleStatus, payload: SaleStatusChange, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    """Legado: use close_sale, cancel_sale ou reopen_sale."""
    if new_status == SaleStatus.CLOSED:
        return close_sale(db, sale_id, payload, actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    if new_status == SaleStatus.CANCELLED:
        return cancel_sale(db, sale_id, payload, actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    raise ValueError("Mudança de status não suportada via _change_sale_status_internal.")


def close_sale(
    db: Session,
    sale_id: str,
    payload: SaleStatusChange,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_sale_id(sale_id)
    sale_db = repository_get_sale_for_update(db, sale_id)
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    sale = sale_db_to_domain(sale_db)
    if sale.status != SaleStatus.QUOTE:
        raise ValueError("Apenas orçamentos podem ser fechados.")
    if not sale.items:
        raise ValueError("Venda precisa ter itens para ser fechada.")
    _assert_sale_ready_for_confirmation(sale)

    now = utc_now()
    before = sale_to_dict(sale)
    previous_status = sale.status

    try:
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        from app.modules.stock.service import apply_sale_stock_effects
        from app.modules.accounts_receivable.service import generate_receivables_from_sale
        # Marcar como fechado antes dos efeitos de estoque/recebíveis — before/previous_status já foram capturados acima.
        sale_number, sale_number_text = next_sale_number(db, sale.company_id)
        sale.status = SaleStatus.CLOSED
        sale.sale_number = sale_number
        sale.sale_number_text = sale_number_text
        sale.closed_at = now
        sale.closed_by = actor_id
        sale.updated_at = now
        stock_effects = apply_sale_stock_effects(db, sale, actor_id=context.actor_id)
        receivable_effects = generate_receivables_from_sale(db, sale, actor_id=context.actor_id, source=context.source, reason=payload.reason)
        after = sale_to_dict(sale)

        update_sale_header_only(db, sale_db, sale)
        create_sale_status_history(
            db,
            history_id=generate_id("salehist"),
            company_id=sale.company_id,
            sale_id=sale.id,
            previous_status=previous_status.value,
            new_status=sale.status.value,
            reason=payload.reason,
            source=context.source.value,
            actor_id=context.actor_id,
            occurred_at=now,
        )
        event = build_audit_event(
            event_type=AuditEventType.STATUS_CHANGED,
            entity_type=AuditEntityType.SALE,
            entity_id=sale.id,
            context=context,
            before=before,
            after=after,
            metadata={
                "previous_status": previous_status.value,
                "new_status": sale.status.value,
                "reason": payload.reason,
                "sale_number_text": sale_number_text,
                "stock_effects": stock_effects,
                "receivable_effects": receivable_effects,
            },
        )
        create_audit_event(db, event, company_id=sale.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return after


def pay_sale(
    db: Session,
    sale_id: str,
    payload: SaleStatusChange,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_sale_id(sale_id)
    sale_db = repository_get_sale_for_update(db, sale_id)
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    sale = sale_db_to_domain(sale_db)
    if sale.status == SaleStatus.QUOTE:
        raise ValueError("Pedido em orçamento precisa ser fechado antes de gerar título a receber.")
    if sale.status == SaleStatus.CANCELLED:
        raise ValueError("Pedido cancelado não pode ser recebido.")
    if sale.status == SaleStatus.PAID:
        raise ValueError("Pedido já possui status pago legado. Novos recebimentos devem ser feitos por Caixa e Baixas.")
    raise ValueError(
        "Recebimento direto pelo pedido foi desativado na v1.0. "
        "Feche o pedido para gerar o título a receber e registre a baixa em Caixa e Baixas."
    )


def cancel_sale(
    db: Session,
    sale_id: str,
    payload: SaleStatusChange,
    *,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_sale_id(sale_id)
    sale_db = repository_get_sale_for_update(db, sale_id)
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    sale = sale_db_to_domain(sale_db)
    if sale.status == SaleStatus.CANCELLED:
        raise ValueError("Venda já está cancelada.")

    if not payload.reason:
        raise ValueError("Motivo de cancelamento e obrigatorio.")

    now = utc_now()
    before = sale_to_dict(sale)
    previous_status = sale.status
    stock_effects: list[dict[str, Any]] = []
    receivable_effects: list[dict[str, Any]] = []

    sale.status = SaleStatus.CANCELLED
    sale.cancelled_at = now
    sale.updated_at = now
    after = sale_to_dict(sale)

    try:
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        if previous_status in (SaleStatus.CLOSED, SaleStatus.PAID):
            from app.modules.stock.service import reverse_sale_stock_effects
            from app.modules.accounts_receivable.service import assert_sale_receivables_can_be_cancelled, cancel_receivables_for_sale
            assert_sale_receivables_can_be_cancelled(db, sale.id, company_id=sale.company_id)
            stock_effects = reverse_sale_stock_effects(db, sale, actor_id=context.actor_id)
            receivable_effects = cancel_receivables_for_sale(db, sale.id, company_id=sale.company_id, actor_id=context.actor_id, source=context.source, reason=payload.reason)
        update_sale_header_only(db, sale_db, sale)
        create_sale_status_history(
            db,
            history_id=generate_id("salehist"),
            company_id=sale.company_id,
            sale_id=sale.id,
            previous_status=previous_status.value,
            new_status=sale.status.value,
            reason=payload.reason,
            source=context.source.value,
            actor_id=context.actor_id,
            occurred_at=now,
        )
        event = build_audit_event(
            event_type=AuditEventType.STATUS_CHANGED,
            entity_type=AuditEntityType.SALE,
            entity_id=sale.id,
            context=context,
            before=before,
            after=after,
            metadata={
                "previous_status": previous_status.value,
                "new_status": sale.status.value,
                "reason": payload.reason,
                "stock_effects": stock_effects,
                "receivable_effects": receivable_effects,
            },
        )
        create_audit_event(db, event, company_id=sale.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return after


def reopen_sale(
    db: Session,
    sale_id: str,
    *,
    master_password: str,
    reason: str | None = None,
    actor_id: str | None = None,
    source: AuditSource | str = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    _assert_sale_id(sale_id)
    sale_db = repository_get_sale_for_update(db, sale_id)
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    sale = sale_db_to_domain(sale_db)
    if sale.status != SaleStatus.CLOSED:
        raise ValueError("Apenas pedidos fechados podem ser reabertos.")

    now = utc_now()
    before = sale_to_dict(sale)
    previous_status = sale.status

    from app.modules.security.service import verify_master_password, _audit_security_event
    password_valid = verify_master_password(db, sale.company_id, master_password)
    if not password_valid:
        _audit_security_event(
            db,
            event_type="reopen_sale_failed",
            severity="warning",
            message="Tentativa de reabertura de pedido com senha mestre inválida.",
            company_id=sale.company_id,
            user_id=actor_id,
            metadata={"sale_id": sale_id, "sale_number_text": sale.sale_number_text},
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.flush()
        raise PermissionError("Senha mestre inválida.")

    stock_effects: list[dict[str, Any]] = []
    receivable_effects: list[dict[str, Any]] = []

    try:
        context = _create_audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        from app.modules.stock.service import reverse_sale_stock_effects
        from app.modules.accounts_receivable.service import cancel_receivables_for_sale
        stock_effects = reverse_sale_stock_effects(db, sale, actor_id=context.actor_id)
        receivable_effects = cancel_receivables_for_sale(
            db, sale.id, company_id=sale.company_id,
            actor_id=context.actor_id, source=context.source,
            reason=reason or "Reabertura de pedido.",
        )

        sale.status = SaleStatus.QUOTE
        sale.unlocked_by = actor_id
        sale.unlocked_at = now
        sale.updated_at = now
        after = sale_to_dict(sale)

        update_sale_header_only(db, sale_db, sale)
        create_sale_status_history(
            db,
            history_id=generate_id("salehist"),
            company_id=sale.company_id,
            sale_id=sale.id,
            previous_status=previous_status.value,
            new_status=sale.status.value,
            reason=reason,
            source=context.source.value,
            actor_id=context.actor_id,
            occurred_at=now,
        )
        _audit_security_event(
            db,
            event_type="reopen_sale_success",
            severity="warning",
            message="Pedido reaberto com senha mestre.",
            company_id=sale.company_id,
            user_id=actor_id,
            metadata={"sale_id": sale_id, "sale_number_text": sale.sale_number_text, "reason": reason},
            request_id=request_id,
            correlation_id=correlation_id,
        )
        event = build_audit_event(
            event_type=AuditEventType.STATUS_CHANGED,
            entity_type=AuditEntityType.SALE,
            entity_id=sale.id,
            context=context,
            before=before,
            after=after,
            metadata={
                "previous_status": previous_status.value,
                "new_status": sale.status.value,
                "reason": reason,
                "stock_effects": stock_effects,
                "receivable_effects": receivable_effects,
                "unlocked_by": actor_id,
            },
        )
        create_audit_event(db, event, company_id=sale.company_id)
        db.commit()
    except PermissionError:
        raise
    except Exception:
        db.rollback()
        raise
    return after


def confirm_sale(db: Session, sale_id: str, payload: SaleStatusChange, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    # alias de compatibilidade — delega para close_sale
    return close_sale(db, sale_id, payload, actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def get_sale_audit_events(db: Session, sale_id: str) -> list[dict[str, Any]]:
    _get_sale_db_or_raise(db, sale_id)
    events = list_audit_events_for_entity(db, entity_type=AuditEntityType.SALE.value, entity_id=sale_id, limit=100, offset=0)
    return [audit_event_db_to_dict(event) for event in events]


def get_sale_status_history(db: Session, sale_id: str) -> list[dict[str, Any]]:
    _get_sale_db_or_raise(db, sale_id)
    history = list_sale_status_history(db, sale_id, limit=100, offset=0)
    return [sale_status_history_to_dict(item) for item in history]


def get_sales_rules() -> dict[str, Any]:
    return {
        "module": "sales",
        "entity": "sale",
        "id_prefix": "sale",
        "item_id_prefix": "saleitem",
        "operation_nature_prefix": "opnat",
        "fiscal_rule_prefix": "fiscalrule",
        "status_history_prefix": "salehist",
        "tables": ["sales", "sale_items", "sale_payment_plans", "sale_status_history", "sale_sequences", "operation_natures", "catalog_item_fiscal_rules", "payment_methods"],
        "relationships": {
            "sales.company_id": "companies.id",
            "sales.participant_id": "participants.id",
            "sales.operation_nature_id": "operation_natures.id",
            "sale_items.sale_id": "sales.id",
            "sale_items.item_id": "catalog_items.id",
            "sale_items.fiscal_classification_id": "fiscal_classifications.id",
            "catalog_item_fiscal_rules.catalog_item_id": "catalog_items.id",
            "catalog_item_fiscal_rules.fiscal_classification_id": "fiscal_classifications.id",
            "sale_sequences.company_id": "companies.id",
        },
        "statuses": [status.value for status in SaleStatus],
        "fiscal_statuses": [status.value for status in SaleFiscalStatus],
        "sale_types": [sale_type.value for sale_type in SaleType],
        "operation_natures": [operation_nature.value for operation_nature in SaleOperationNature],
        "discount_types": ["amount", "percentage"],
        "discount_categories": ["coupon", "promotion", "commercial_negotiation", "customer_loyalty", "manager_authorization", "damaged_goods", "other"],
        "payment_methods": [method["code"] for method in DEFAULT_PAYMENT_METHODS],
        "origins": [origin.value for origin in SaleOrigin],
        "rules": [
            "Operador escolhe natureza comercial; tributação pesada não é preenchida no caixa.",
            "Natureza de operação é cadastro parametrizável em operation_natures, não texto solto.",
            "O backend resolve classificação fiscal por regra item+natureza e grava snapshot fiscal por item.",
            "Vendas separam total comercial, total a receber e total previsto para documento fiscal.",
            "Desconto pode ser informado como valor fixo ou percentual; o backend calcula e persiste o valor monetário oficial.",
            "Venda pode ter múltiplas formas de pagamento; a soma do plano precisa bater com sales.receivable_total_amount.",
            "Preço unitário informado via API é validado contra o preço oficial do cadastro; override manual fica bloqueado no Bloco 5D.",
            "Fechamento do pedido gera título a receber quando há valor financeiro a receber.",
            "Pedido fechado não é recebimento; baixa financeira real deve ocorrer em Caixa e Baixas.",
            "POST /sales/{id}/pay permanece apenas como compatibilidade técnica e retorna erro controlado na v1.0.",
            "Baixa financeira cria settlement, movimento financeiro e atualiza saldo interno fora do módulo Sales.",
            "Bonificação, amostra, cortesia, troca e reposição exigem motivo e podem zerar contas a receber por padrão.",
            "Venda sem classificação fiscal aplicável fica com fiscal_status pending_classification.",
            "Documento fiscal, título financeiro, baixa e conciliação bancária são fatos separados.",
        ],
    }


def get_sales_diagnostics(db: Session) -> dict[str, Any]:
    return {
        "module": "sales",
        "status": "active",
        "storage": "postgresql",
        "persistence": "sqlalchemy_repository",
        "tables": ["sales", "sale_items", "sale_payment_plans", "sale_status_history", "operation_natures", "catalog_item_fiscal_rules", "payment_methods"],
        "id_prefix": "sale",
        "item_id_prefix": "saleitem",
        "operation_nature_prefix": "opnat",
        "fiscal_rule_prefix": "fiscalrule",
        "status_history_prefix": "salehist",
        "audit_enabled": True,
        "audit_persistence": "audit_events",
        "total_sales": count_sales(db),
        "total_audit_events": count_audit_events_for_company(db),
        "available_operations": ["create_sale", "list_sales", "get_sale", "update_sale", "confirm_sale", "cancel_sale", "list_operation_natures", "list_payment_methods", "list_catalog_item_fiscal_rules", "list_sale_item_readiness"],
        "technical_notes": [
            "Bloco 5C adiciona naturezas de operação e preparação fiscal da venda.",
            "sales.receivable_total_amount separa valor financeiro esperado do total comercial.",
            "sales.invoice_total_amount separa valor previsto para documento fiscal futuro.",
            "sales.fiscal_status indica se a venda está pronta fiscalmente ou pendente de classificação.",
            "operation_natures parametriza venda normal, bonificação, amostra, troca, cortesia e reposição.",
            "catalog_item_fiscal_rules prepara vínculo item+natureza+classificação fiscal.",
            "sales/item-readiness cruza catálogo, fiscal e estoque antes da seleção operacional.",
            "Desconto percentual mantém percentagem original em sales.discount_percentage para rastreabilidade.",
            "sale_payment_plans registra Pix, cartão, dinheiro, boleto, transferência ou combinações para preparar Contas a Receber.",
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Prontidão Fiscal e Emissão NF-e
# ──────────────────────────────────────────────────────────────────────────────

def get_sale_invoice_readiness(db: Session, sale_id: str) -> dict[str, Any]:
    """Executa a validação de prontidão fiscal e persiste o fiscal_status na venda."""
    sale = repository_get_sale_for_update(db, sale_id)
    if not sale:
        raise ValueError(f"Venda {sale_id} não encontrada.")

    from app.modules.sales.invoice_readiness import build_invoice_readiness

    result = build_invoice_readiness(db, sale)

    # Persiste o fiscal_status resolvido
    if sale.fiscal_status != result.fiscal_status:
        sale.fiscal_status = result.fiscal_status
        db.flush()
        db.commit()

    return result.to_dict()


def emit_sale_invoice(db: Session, sale_id: str) -> dict[str, Any]:
    """Emite NF-e para a venda via Focus NFe.

    A venda precisa estar confirmada e com fiscal_status='fiscal_ready'.
    """
    sale = repository_get_sale_for_update(db, sale_id)
    if not sale:
        raise ValueError(f"Venda {sale_id} não encontrada.")

    if sale.status not in ("closed", "paid"):
        raise ValueError("Apenas vendas fechadas ou pagas podem ser faturadas.")

    # Valida prontidão antes de emitir
    from app.modules.sales.invoice_readiness import build_invoice_readiness

    readiness = build_invoice_readiness(db, sale)
    if readiness.blocking_count > 0:
        issues_text = "; ".join(
            f"[{i.scope}] {i.message}"
            for i in readiness.issues
            if i.severity == "blocking"
        )
        raise ValueError(f"Venda não está pronta para faturamento. Bloqueios: {issues_text}")

    from app.modules.fiscal_documents.service import emit_invoice_for_sale

    result = emit_invoice_for_sale(db, sale)
    return result
