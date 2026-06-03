from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.modules.participants.db_models import ParticipantDB
from app.modules.sales.db_models import (
    CatalogItemFiscalRuleDB,
    OperationNatureDB,
    PaymentMethodDB,
    SaleDB,
    SaleItemDB,
    SalePaymentPlanDB,
    SaleSequenceDB,
    SaleStatusHistoryDB,
)
from app.shared.datetime import utc_now
from app.shared.ids import generate_id
from app.modules.sales.models import (
    CatalogItemFiscalRule,
    OperationNature,
    PaymentMethod,
    Sale,
    SaleDiscountType,
    SaleFiscalStatus,
    SaleItem,
    SalePaymentPlan,
    SalePaymentPlanStatus,
    SaleOperationNature,
    SaleOrigin,
    SaleStatus,
    SaleType,
)


def _decimal_to_text(value: Any) -> str:
    if value is None:
        return "0"
    return format(Decimal(str(value)), "f")


def _to_decimal(value: str | Decimal | int | float | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def payment_method_db_to_domain(method: PaymentMethodDB) -> PaymentMethod:
    return PaymentMethod(
        id=method.id,
        company_id=method.company_id,
        code=method.code,
        name=method.name,
        method_type=method.method_type,
        description=method.description,
        requires_reference=method.requires_reference,
        default_due_behavior=method.default_due_behavior,
        status=method.status,
        settings=method.settings_json,
        created_at=method.created_at,
        updated_at=method.updated_at,
        deleted_at=method.deleted_at,
    )


def payment_method_db_to_dict(method: PaymentMethodDB) -> dict[str, Any]:
    domain = payment_method_db_to_domain(method)
    return {
        "id": domain.id,
        "company_id": domain.company_id,
        "code": domain.code,
        "name": domain.name,
        "method_type": domain.method_type,
        "description": domain.description,
        "requires_reference": domain.requires_reference,
        "default_due_behavior": domain.default_due_behavior,
        "status": domain.status,
        "settings": domain.settings,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }


def create_payment_method(db: Session, **data: Any) -> PaymentMethodDB:
    method = PaymentMethodDB(**data)
    db.add(method)
    db.flush()
    return method


def list_payment_methods(db: Session, *, company_id: str, status: str | None = "active") -> list[PaymentMethodDB]:
    statement = select(PaymentMethodDB).where(
        PaymentMethodDB.company_id == company_id,
        PaymentMethodDB.deleted_at.is_(None),
    )
    if status is not None:
        statement = statement.where(PaymentMethodDB.status == status)
    statement = statement.order_by(PaymentMethodDB.name.asc(), PaymentMethodDB.id.asc())
    return list(db.scalars(statement).all())


def get_payment_method(db: Session, method_id: str) -> PaymentMethodDB | None:
    return db.scalar(select(PaymentMethodDB).where(PaymentMethodDB.id == method_id, PaymentMethodDB.deleted_at.is_(None)))


def get_payment_method_by_code(db: Session, *, company_id: str, code: str) -> PaymentMethodDB | None:
    return db.scalar(
        select(PaymentMethodDB).where(
            PaymentMethodDB.company_id == company_id,
            PaymentMethodDB.code == code,
            PaymentMethodDB.status == "active",
            PaymentMethodDB.deleted_at.is_(None),
        )
    )

def operation_nature_db_to_domain(nature: OperationNatureDB) -> OperationNature:
    return OperationNature(
        id=nature.id,
        company_id=nature.company_id,
        code=nature.code,
        name=nature.name,
        sale_type=nature.sale_type,
        description=nature.description,
        requires_reason=nature.requires_reason,
        affects_revenue=nature.affects_revenue,
        affects_accounts_receivable=nature.affects_accounts_receivable,
        affects_stock=nature.affects_stock,
        requires_fiscal_document=nature.requires_fiscal_document,
        default_receivable_behavior=nature.default_receivable_behavior,
        default_invoice_behavior=nature.default_invoice_behavior,
        status=nature.status,
        created_at=nature.created_at,
        updated_at=nature.updated_at,
        deleted_at=nature.deleted_at,
    )


def operation_nature_db_to_dict(nature: OperationNatureDB) -> dict[str, Any]:
    domain = operation_nature_db_to_domain(nature)
    return {
        "id": domain.id,
        "company_id": domain.company_id,
        "code": domain.code,
        "name": domain.name,
        "sale_type": domain.sale_type,
        "description": domain.description,
        "requires_reason": domain.requires_reason,
        "affects_revenue": domain.affects_revenue,
        "affects_accounts_receivable": domain.affects_accounts_receivable,
        "affects_stock": domain.affects_stock,
        "requires_fiscal_document": domain.requires_fiscal_document,
        "default_receivable_behavior": domain.default_receivable_behavior,
        "default_invoice_behavior": domain.default_invoice_behavior,
        "status": domain.status,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }


def catalog_item_fiscal_rule_db_to_domain(rule: CatalogItemFiscalRuleDB) -> CatalogItemFiscalRule:
    return CatalogItemFiscalRule(
        id=rule.id,
        company_id=rule.company_id,
        catalog_item_id=rule.catalog_item_id,
        fiscal_classification_id=rule.fiscal_classification_id,
        operation_nature_id=rule.operation_nature_id,
        sale_type=rule.sale_type,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        priority=rule.priority,
        status=rule.status,
        notes=rule.notes,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        deleted_at=rule.deleted_at,
    )


def catalog_item_fiscal_rule_db_to_dict(rule: CatalogItemFiscalRuleDB) -> dict[str, Any]:
    domain = catalog_item_fiscal_rule_db_to_domain(rule)
    return {
        "id": domain.id,
        "company_id": domain.company_id,
        "catalog_item_id": domain.catalog_item_id,
        "fiscal_classification_id": domain.fiscal_classification_id,
        "operation_nature_id": domain.operation_nature_id,
        "sale_type": domain.sale_type,
        "valid_from": domain.valid_from.isoformat() if domain.valid_from else None,
        "valid_to": domain.valid_to.isoformat() if domain.valid_to else None,
        "priority": domain.priority,
        "status": domain.status,
        "notes": domain.notes,
        "created_at": domain.created_at.isoformat() if domain.created_at else None,
        "updated_at": domain.updated_at.isoformat() if domain.updated_at else None,
    }


def create_operation_nature(db: Session, **data: Any) -> OperationNatureDB:
    nature = OperationNatureDB(**data)
    db.add(nature)
    db.flush()
    return nature


def list_operation_natures(
    db: Session,
    *,
    company_id: str,
    sale_type: str | None = None,
    status: str | None = "active",
) -> list[OperationNatureDB]:
    statement: Select[tuple[OperationNatureDB]] = select(OperationNatureDB).where(
        OperationNatureDB.company_id == company_id,
        OperationNatureDB.deleted_at.is_(None),
    )
    if sale_type is not None:
        statement = statement.where(or_(OperationNatureDB.sale_type == sale_type, OperationNatureDB.sale_type == "both"))
    if status is not None:
        statement = statement.where(OperationNatureDB.status == status)
    statement = statement.order_by(OperationNatureDB.code.asc(), OperationNatureDB.id.asc())
    return list(db.scalars(statement).all())


def get_operation_nature(db: Session, nature_id: str) -> OperationNatureDB | None:
    return db.scalar(select(OperationNatureDB).where(OperationNatureDB.id == nature_id, OperationNatureDB.deleted_at.is_(None)))


def get_operation_nature_by_code(
    db: Session,
    *,
    company_id: str,
    code: str,
    sale_type: str | None = None,
) -> OperationNatureDB | None:
    statement = select(OperationNatureDB).where(
        OperationNatureDB.company_id == company_id,
        OperationNatureDB.code == code,
        OperationNatureDB.status == "active",
        OperationNatureDB.deleted_at.is_(None),
    )
    if sale_type is not None:
        statement = statement.where(or_(OperationNatureDB.sale_type == sale_type, OperationNatureDB.sale_type == "both"))
    statement = statement.order_by(OperationNatureDB.sale_type.desc(), OperationNatureDB.id.asc())
    return db.scalar(statement)


def create_catalog_item_fiscal_rule(db: Session, **data: Any) -> CatalogItemFiscalRuleDB:
    rule = CatalogItemFiscalRuleDB(**data)
    db.add(rule)
    db.flush()
    return rule


def find_catalog_item_fiscal_rule(
    db: Session,
    *,
    company_id: str,
    catalog_item_id: str,
    operation_nature_id: str,
    sale_type: str,
    valid_on: date | None = None,
) -> CatalogItemFiscalRuleDB | None:
    statement = select(CatalogItemFiscalRuleDB).where(
        CatalogItemFiscalRuleDB.company_id == company_id,
        CatalogItemFiscalRuleDB.catalog_item_id == catalog_item_id,
        CatalogItemFiscalRuleDB.operation_nature_id == operation_nature_id,
        CatalogItemFiscalRuleDB.status == "active",
        CatalogItemFiscalRuleDB.deleted_at.is_(None),
        or_(CatalogItemFiscalRuleDB.sale_type == sale_type, CatalogItemFiscalRuleDB.sale_type == "both"),
    )
    if valid_on is not None:
        statement = statement.where(
            or_(CatalogItemFiscalRuleDB.valid_from.is_(None), CatalogItemFiscalRuleDB.valid_from <= valid_on),
            or_(CatalogItemFiscalRuleDB.valid_to.is_(None), CatalogItemFiscalRuleDB.valid_to >= valid_on),
        )
    statement = statement.order_by(CatalogItemFiscalRuleDB.priority.asc(), CatalogItemFiscalRuleDB.created_at.desc(), CatalogItemFiscalRuleDB.id.desc())
    return db.scalar(statement)


def list_catalog_item_fiscal_rules(
    db: Session,
    *,
    company_id: str,
    catalog_item_id: str | None = None,
    operation_nature_id: str | None = None,
    status: str | None = "active",
    limit: int = 50,
    offset: int = 0,
) -> list[CatalogItemFiscalRuleDB]:
    statement = select(CatalogItemFiscalRuleDB).where(
        CatalogItemFiscalRuleDB.company_id == company_id,
        CatalogItemFiscalRuleDB.deleted_at.is_(None),
    )
    if catalog_item_id is not None:
        statement = statement.where(CatalogItemFiscalRuleDB.catalog_item_id == catalog_item_id)
    if operation_nature_id is not None:
        statement = statement.where(CatalogItemFiscalRuleDB.operation_nature_id == operation_nature_id)
    if status is not None:
        statement = statement.where(CatalogItemFiscalRuleDB.status == status)
    statement = statement.order_by(CatalogItemFiscalRuleDB.priority.asc(), CatalogItemFiscalRuleDB.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def sale_item_db_to_domain(item: SaleItemDB) -> SaleItem:
    return SaleItem(
        id=item.id,
        company_id=item.company_id,
        sale_id=item.sale_id,
        item_id=item.item_id,
        stock_lot_id=getattr(item, "stock_lot_id", None),
        stock_lot_code=getattr(item, "stock_lot_code", None),
        stock_lot_expiration_date=getattr(item, "stock_lot_expiration_date", None),
        fiscal_classification_id=item.fiscal_classification_id,
        description=item.description,
        quantity=_decimal_to_text(item.quantity),
        unit=item.unit,
        unit_price=_decimal_to_text(item.unit_price),
        discount_amount=_decimal_to_text(item.discount_amount),
        freight_amount=_decimal_to_text(item.freight_amount),
        tax_amount=_decimal_to_text(item.tax_amount),
        total_amount=_decimal_to_text(item.total_amount),
        item_snapshot=item.item_snapshot_json or {},
        fiscal_snapshot=item.fiscal_snapshot_json,
        operation_nature_snapshot=item.operation_nature_snapshot_json,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def sale_payment_plan_db_to_domain(plan: SalePaymentPlanDB) -> SalePaymentPlan:
    return SalePaymentPlan(
        id=plan.id,
        company_id=plan.company_id,
        sale_id=plan.sale_id,
        payment_method_id=plan.payment_method_id,
        payment_method_code=plan.payment_method_code,
        payment_method_name=plan.payment_method_name,
        amount=_decimal_to_text(plan.amount),
        due_date=plan.due_date,
        installments=plan.installments,
        status=SalePaymentPlanStatus(plan.status),
        notes=plan.notes,
        metadata=plan.metadata_json,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _sale_payment_plan_to_db(plan: SalePaymentPlan) -> SalePaymentPlanDB:
    return SalePaymentPlanDB(
        id=plan.id,
        company_id=plan.company_id,
        sale_id=plan.sale_id,
        payment_method_id=plan.payment_method_id,
        payment_method_code=plan.payment_method_code,
        payment_method_name=plan.payment_method_name,
        amount=_to_decimal(plan.amount),
        due_date=plan.due_date,
        installments=plan.installments,
        status=plan.status.value,
        notes=plan.notes,
        metadata_json=plan.metadata,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )

def sale_db_to_domain(sale: SaleDB) -> Sale:
    return Sale(
        id=sale.id,
        company_id=sale.company_id,
        establishment_id=sale.establishment_id,
        participant_id=sale.participant_id,
        status=SaleStatus(sale.status),
        sale_type=SaleType(getattr(sale, "sale_type", "product")),
        origin=SaleOrigin(sale.origin),
        operation_nature=SaleOperationNature(getattr(sale, "operation_nature", "normal_sale")),
        operation_nature_id=getattr(sale, "operation_nature_id", None),
        operation_nature_reason=getattr(sale, "operation_nature_reason", None),
        operation_nature_snapshot=getattr(sale, "operation_nature_snapshot_json", None),
        fiscal_status=SaleFiscalStatus(getattr(sale, "fiscal_status", "pending_classification")),
        issue_date=sale.issue_date,
        operation_date=sale.operation_date,
        competency_date=sale.competency_date,
        subtotal_amount=_decimal_to_text(sale.subtotal_amount),
        discount_amount=_decimal_to_text(sale.discount_amount),
        discount_type=SaleDiscountType(getattr(sale, "discount_type", "amount")),
        discount_percentage=_decimal_to_text(getattr(sale, "discount_percentage", None)) if getattr(sale, "discount_percentage", None) is not None else None,
        discount_category=getattr(sale, "discount_category", None),
        discount_reason=getattr(sale, "discount_reason", None),
        freight_amount=_decimal_to_text(sale.freight_amount),
        tax_amount=_decimal_to_text(sale.tax_amount),
        total_amount=_decimal_to_text(sale.total_amount),
        receivable_total_amount=_decimal_to_text(getattr(sale, "receivable_total_amount", sale.total_amount)),
        invoice_total_amount=_decimal_to_text(getattr(sale, "invoice_total_amount", sale.total_amount)),
        participant_snapshot=sale.participant_snapshot_json or {},
        notes=sale.notes,
        created_at=sale.created_at,
        updated_at=sale.updated_at,
        cancelled_at=sale.cancelled_at,
        sale_number=getattr(sale, "sale_number", None),
        sale_number_text=getattr(sale, "sale_number_text", None),
        paid_number_text=getattr(sale, "paid_number_text", None),
        closed_at=getattr(sale, "closed_at", None),
        paid_at=getattr(sale, "paid_at", None),
        closed_by=getattr(sale, "closed_by", None),
        paid_by=getattr(sale, "paid_by", None),
        unlocked_by=getattr(sale, "unlocked_by", None),
        unlocked_at=getattr(sale, "unlocked_at", None),
        items=[sale_item_db_to_domain(item) for item in sorted(sale.items, key=lambda item: item.created_at)],
        payment_plans=[sale_payment_plan_db_to_domain(plan) for plan in sorted(sale.payment_plans, key=lambda plan: plan.created_at)],
    )


def _apply_sale_to_db(sale_db: SaleDB, sale: Sale) -> None:
    sale_db.company_id = sale.company_id
    sale_db.establishment_id = sale.establishment_id
    sale_db.participant_id = sale.participant_id
    sale_db.status = sale.status.value
    sale_db.sale_type = sale.sale_type.value
    sale_db.origin = sale.origin.value
    sale_db.operation_nature = sale.operation_nature.value
    sale_db.operation_nature_id = sale.operation_nature_id
    sale_db.operation_nature_reason = sale.operation_nature_reason
    sale_db.operation_nature_snapshot_json = sale.operation_nature_snapshot
    sale_db.fiscal_status = sale.fiscal_status.value
    sale_db.issue_date = sale.issue_date
    sale_db.operation_date = sale.operation_date
    sale_db.competency_date = sale.competency_date
    sale_db.subtotal_amount = _to_decimal(sale.subtotal_amount)
    sale_db.discount_amount = _to_decimal(sale.discount_amount)
    sale_db.discount_type = sale.discount_type.value
    sale_db.discount_percentage = _to_decimal(sale.discount_percentage) if sale.discount_percentage is not None else None
    sale_db.discount_category = sale.discount_category
    sale_db.discount_reason = sale.discount_reason
    sale_db.freight_amount = _to_decimal(sale.freight_amount)
    sale_db.tax_amount = _to_decimal(sale.tax_amount)
    sale_db.total_amount = _to_decimal(sale.total_amount)
    sale_db.receivable_total_amount = _to_decimal(sale.receivable_total_amount)
    sale_db.invoice_total_amount = _to_decimal(sale.invoice_total_amount)
    sale_db.participant_snapshot_json = sale.participant_snapshot
    sale_db.notes = sale.notes
    sale_db.created_at = sale.created_at
    sale_db.updated_at = sale.updated_at
    sale_db.cancelled_at = sale.cancelled_at
    sale_db.sale_number = sale.sale_number
    sale_db.sale_number_text = sale.sale_number_text
    sale_db.paid_number_text = sale.paid_number_text
    sale_db.closed_at = sale.closed_at
    sale_db.paid_at = sale.paid_at
    sale_db.closed_by = sale.closed_by
    sale_db.paid_by = sale.paid_by
    sale_db.unlocked_by = sale.unlocked_by
    sale_db.unlocked_at = sale.unlocked_at


def _sale_item_to_db(item: SaleItem) -> SaleItemDB:
    return SaleItemDB(
        id=item.id,
        company_id=item.company_id,
        sale_id=item.sale_id,
        item_id=item.item_id,
        stock_lot_id=item.stock_lot_id,
        stock_lot_code=item.stock_lot_code,
        stock_lot_expiration_date=item.stock_lot_expiration_date,
        fiscal_classification_id=item.fiscal_classification_id,
        description=item.description,
        quantity=_to_decimal(item.quantity),
        unit=item.unit,
        unit_price=_to_decimal(item.unit_price),
        discount_amount=_to_decimal(item.discount_amount),
        freight_amount=_to_decimal(item.freight_amount),
        tax_amount=_to_decimal(item.tax_amount),
        total_amount=_to_decimal(item.total_amount),
        item_snapshot_json=item.item_snapshot,
        fiscal_snapshot_json=item.fiscal_snapshot,
        operation_nature_snapshot_json=item.operation_nature_snapshot,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_sale(db: Session, sale: Sale) -> SaleDB:
    sale_db = SaleDB(id=sale.id)
    _apply_sale_to_db(sale_db, sale)
    for item in sale.items:
        sale_db.items.append(_sale_item_to_db(item))
    for plan in sale.payment_plans:
        sale_db.payment_plans.append(_sale_payment_plan_to_db(plan))
    db.add(sale_db)
    db.flush()
    return sale_db


def replace_sale_items(db: Session, sale_db: SaleDB, sale: Sale) -> None:
    sale_db.items.clear()
    db.flush()
    for item in sale.items:
        sale_db.items.append(_sale_item_to_db(item))
    db.flush()


def replace_sale_payment_plans(db: Session, sale_db: SaleDB, sale: Sale) -> None:
    sale_db.payment_plans.clear()
    db.flush()
    for plan in sale.payment_plans:
        sale_db.payment_plans.append(_sale_payment_plan_to_db(plan))
    db.flush()

def update_sale(db: Session, sale_db: SaleDB, sale: Sale) -> SaleDB:
    _apply_sale_to_db(sale_db, sale)
    replace_sale_items(db, sale_db, sale)
    replace_sale_payment_plans(db, sale_db, sale)
    db.add(sale_db)
    db.flush()
    return sale_db


def update_sale_header_only(db: Session, sale_db: SaleDB, sale: Sale) -> SaleDB:
    _apply_sale_to_db(sale_db, sale)
    db.add(sale_db)
    db.flush()
    return sale_db


def get_sale(db: Session, sale_id: str) -> SaleDB | None:
    return db.scalar(select(SaleDB).options(selectinload(SaleDB.items), selectinload(SaleDB.payment_plans)).where(SaleDB.id == sale_id))


def get_sale_for_update(db: Session, sale_id: str) -> SaleDB | None:
    """Busca a venda com lock transacional para confirmação/cancelamento.

    O lock evita duas requisições simultâneas confirmarem a mesma venda antes de
    uma delas criar os vínculos de estoque. As relações são carregadas depois do
    lock da linha principal.
    """
    sale = db.scalar(select(SaleDB).where(SaleDB.id == sale_id).with_for_update())
    if sale is not None:
        _ = sale.items
        _ = sale.payment_plans
    return sale


def list_sales(
    db: Session,
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: str | None = None,
    status_filter: str | None = None,
    fiscal_status: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SaleDB]:
    statement: Select[tuple[SaleDB]] = _sales_filtered_statement(
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type,
        status_filter=status_filter,
        fiscal_status=fiscal_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
    ).options(selectinload(SaleDB.items), selectinload(SaleDB.payment_plans))
    statement = statement.order_by(SaleDB.created_at.desc(), SaleDB.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def _sales_filtered_statement(
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: str | None = None,
    status_filter: str | None = None,
    fiscal_status: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select[tuple[SaleDB]]:
    statement: Select[tuple[SaleDB]] = select(SaleDB)
    if company_id is not None:
        statement = statement.where(SaleDB.company_id == company_id)
    if participant_id is not None:
        statement = statement.where(SaleDB.participant_id == participant_id)
    if sale_type is not None:
        statement = statement.where(SaleDB.sale_type == sale_type)
    if status_filter is not None:
        statement = statement.where(SaleDB.status == status_filter)
    if fiscal_status is not None:
        statement = statement.where(SaleDB.fiscal_status == fiscal_status)
    if date_from is not None:
        statement = statement.where(SaleDB.operation_date >= date_from)
    if date_to is not None:
        statement = statement.where(SaleDB.operation_date <= date_to)
    if q:
        like = f"%{q.strip()}%"
        statement = statement.outerjoin(ParticipantDB, ParticipantDB.id == SaleDB.participant_id).where(
            or_(
                SaleDB.sale_number_text.ilike(like),
                SaleDB.id.ilike(like),
                ParticipantDB.name.ilike(like),
                ParticipantDB.trade_name.ilike(like),
                ParticipantDB.document.ilike(like),
            )
        )
    return statement


def count_sales_filtered(
    db: Session,
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: str | None = None,
    status_filter: str | None = None,
    fiscal_status: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    base = _sales_filtered_statement(
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type,
        status_filter=status_filter,
        fiscal_status=fiscal_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
    ).subquery()
    return int(db.scalar(select(func.count()).select_from(base)) or 0)


def count_sales_by_status(
    db: Session,
    *,
    company_id: str | None = None,
    participant_id: str | None = None,
    sale_type: str | None = None,
    fiscal_status: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, int]:
    statement = _sales_filtered_statement(
        company_id=company_id,
        participant_id=participant_id,
        sale_type=sale_type,
        status_filter=None,
        fiscal_status=fiscal_status,
        q=q,
        date_from=date_from,
        date_to=date_to,
    ).with_only_columns(SaleDB.status, func.count()).group_by(SaleDB.status)
    return {str(status): int(count or 0) for status, count in db.execute(statement).all()}


def count_sales(db: Session, company_id: str | None = None) -> int:
    statement = select(func.count()).select_from(SaleDB)
    if company_id is not None:
        statement = statement.where(SaleDB.company_id == company_id)
    return int(db.scalar(statement) or 0)


def create_sale_status_history(
    db: Session,
    *,
    history_id: str,
    company_id: str,
    sale_id: str,
    previous_status: str | None,
    new_status: str,
    reason: str | None,
    source: str | None,
    actor_id: str | None,
    occurred_at,
) -> SaleStatusHistoryDB:
    history = SaleStatusHistoryDB(id=history_id, company_id=company_id, sale_id=sale_id, previous_status=previous_status, new_status=new_status, reason=reason, source=source, actor_id=actor_id, occurred_at=occurred_at)
    db.add(history)
    db.flush()
    return history


def list_sale_status_history(db: Session, sale_id: str, *, limit: int = 100, offset: int = 0) -> list[SaleStatusHistoryDB]:
    statement = select(SaleStatusHistoryDB).where(SaleStatusHistoryDB.sale_id == sale_id).order_by(SaleStatusHistoryDB.occurred_at.desc(), SaleStatusHistoryDB.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def sale_status_history_to_dict(history: SaleStatusHistoryDB) -> dict:
    return {
        "id": history.id,
        "company_id": history.company_id,
        "sale_id": history.sale_id,
        "previous_status": history.previous_status,
        "new_status": history.new_status,
        "reason": history.reason,
        "source": history.source,
        "actor_id": history.actor_id,
        "occurred_at": history.occurred_at.isoformat() if history.occurred_at else None,
    }


def next_sale_number(db: Session, company_id: str) -> tuple[int, str]:
    """Gera o próximo número sequencial de pedido para a empresa com lock pessimista.

    Garante números únicos mesmo sob concorrência. Não faz commit — o chamador
    deve commitar a transação externa para persistir o incremento.
    """
    stmt = pg_insert(SaleSequenceDB).values(
        id=generate_id("sseq"),
        company_id=company_id,
        current_value=0,
        updated_at=utc_now(),
    ).on_conflict_do_nothing(index_elements=["company_id"])
    db.execute(stmt)
    db.flush()

    seq = db.scalar(
        select(SaleSequenceDB)
        .where(SaleSequenceDB.company_id == company_id)
        .with_for_update()
    )
    seq.current_value += 1
    seq.updated_at = utc_now()
    db.flush()
    return seq.current_value, f"PED-{seq.current_value:06d}"
