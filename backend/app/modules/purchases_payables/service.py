from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.cash.repository import balance_to_dict, create_balance, create_movement, create_settlement, get_balance_for_update, get_settlement_by_source, movement_to_dict, settlement_to_dict
from app.modules.company.db_models import CompanyDB
from app.modules.financial.db_models import CostCenterDB, FinancialAccountDB, FinancialCategoryDB
from app.modules.financial.period_service import assert_period_open
from app.modules.participants.db_models import ParticipantDB
from app.modules.purchases_payables.repository import (
    create_financial_title_history,
    create_payable_title,
    create_purchase,
    create_purchase_financial_link,
    create_purchase_item,
    create_purchase_status_history,
    get_payable,
    get_payable_for_update,
    get_purchase,
    get_purchase_for_update,
    iso,
    list_payables_for_overview,
    list_payables as repo_list_payables,
    list_purchase_history,
    list_purchase_payables,
    list_purchases_for_overview,
    list_purchases as repo_list_purchases,
    money,
    payable_to_dict,
    purchase_history_to_dict,
    purchase_to_dict,
    qty,
    summary_by_company,
    update_purchase_fields,
    update_title_fields,
)
from app.modules.purchases_payables.schemas import PayablePaymentCreate, PurchaseConfirmPayload, PurchaseCreate, PurchaseCreateAndConfirmPayload, PurchaseUpdate, StatusChangePayload
from app.modules.security.service import SecurityPrincipal, assert_payment_within_policy_or_approved, require_permission
from app.modules.sales.db_models import PaymentMethodDB
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event
from app.shared.audit_repository import audit_event_db_to_dict, create_audit_event, list_audit_events_for_entity
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import assert_valid_id, generate_id

MONEY_QUANT = Decimal("0.01")
QTY_QUANT = Decimal("0.0001")


def _audit_context(actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> AuditContext:
    if isinstance(source, str):
        source = AuditSource(source)
    return AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def _assert_company(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    exists = db.scalar(select(CompanyDB.id).where(CompanyDB.id == company_id, CompanyDB.deleted_at.is_(None)))
    if not exists:
        raise ValueError("Empresa não encontrada.")


def _get_participant(db: Session, participant_id: str, *, company_id: str) -> ParticipantDB:
    assert_valid_id(participant_id, "part")
    row = db.scalar(select(ParticipantDB).where(ParticipantDB.id == participant_id, ParticipantDB.company_id == company_id, ParticipantDB.deleted_at.is_(None)))
    if row is None:
        raise ValueError("Participante/fornecedor não encontrado para a empresa.")
    if row.status not in {"active", "draft"}:
        raise ValueError("Participante precisa estar ativo ou em rascunho para gerar compra/despesa.")
    return row


def _participant_snapshot(row: ParticipantDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "participant_type": row.participant_type,
        "person_type": row.person_type,
        "name": row.name,
        "trade_name": row.trade_name,
        "document": row.document,
        "email": row.email,
        "phone": row.phone,
        "status": row.status,
    }


def _assert_master_records(db: Session, *, company_id: str, financial_category_id: str | None = None, cost_center_id: str | None = None, expected_financial_account_id: str | None = None, payment_method_id: str | None = None) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    if financial_category_id:
        assert_valid_id(financial_category_id, "cat")
        row = db.scalar(select(FinancialCategoryDB).where(FinancialCategoryDB.id == financial_category_id, FinancialCategoryDB.company_id == company_id, FinancialCategoryDB.deleted_at.is_(None)))
        if row is None or row.status != "active":
            raise ValueError("Categoria financeira não encontrada ou inativa.")
        resolved["category"] = row
    if cost_center_id:
        assert_valid_id(cost_center_id, "cc")
        row = db.scalar(select(CostCenterDB).where(CostCenterDB.id == cost_center_id, CostCenterDB.company_id == company_id, CostCenterDB.deleted_at.is_(None)))
        if row is None or row.status != "active":
            raise ValueError("Centro de custo não encontrado ou inativo.")
        if not row.is_analytical:
            raise ValueError("Centro de custo deve ser analitico e ativo para lancamentos.")
        resolved["cost_center"] = row
    if expected_financial_account_id:
        assert_valid_id(expected_financial_account_id, "bankacc")
        row = db.scalar(select(FinancialAccountDB).where(FinancialAccountDB.id == expected_financial_account_id, FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None)))
        if row is None or row.status != "active":
            raise ValueError("Conta financeira prevista não encontrada ou inativa.")
        resolved["financial_account"] = row
    if payment_method_id:
        assert_valid_id(payment_method_id, "paym")
        row = db.scalar(select(PaymentMethodDB).where(PaymentMethodDB.id == payment_method_id, PaymentMethodDB.company_id == company_id, PaymentMethodDB.deleted_at.is_(None)))
        if row is None or row.status != "active":
            raise ValueError("Forma de pagamento não encontrada ou inativa.")
        resolved["payment_method"] = row
    return resolved


def _get_financial_account(db: Session, account_id: str, *, company_id: str) -> FinancialAccountDB:
    assert_valid_id(account_id, "bankacc")
    row = db.scalar(select(FinancialAccountDB).where(FinancialAccountDB.id == account_id, FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None)))
    if row is None:
        raise ValueError("Conta financeira não encontrada para a empresa.")
    if row.status != "active":
        raise ValueError("Conta financeira precisa estar ativa para registrar pagamento.")
    return row


def _payable_status_for_due(due_date: Any, *, open_amount: Decimal) -> str:
    if open_amount <= Decimal("0.00"):
        return "paid"
    return "overdue" if due_date and due_date < today_in_brazil() else "open"


def _purchase_reference_date(*, issue_date: Any, competency_date: Any, operation_date: Any) -> Any:
    return competency_date or issue_date or operation_date


def _calculate_item_total(quantity: Decimal, unit_cost: Decimal, discount: Decimal, freight: Decimal, tax: Decimal) -> Decimal:
    total = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) - discount + freight + tax
    if total < Decimal("0.00"):
        raise ValueError("Total do item de compra não pode ficar negativo.")
    return total.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _ensure_balance(db: Session, *, company_id: str, financial_account: FinancialAccountDB, now: Any):
    balance = get_balance_for_update(db, company_id=company_id, financial_account_id=financial_account.id)
    if balance is not None:
        return balance
    return create_balance(db, id=generate_id("cashbal"), company_id=company_id, financial_account_id=financial_account.id, current_balance_amount=money(financial_account.opening_balance_amount), last_movement_id=None, updated_at=now)


def _apply_account_delta(db: Session, *, company_id: str, financial_account: FinancialAccountDB, delta: Decimal, movement_id: str, now: Any) -> dict[str, Any]:
    balance = _ensure_balance(db, company_id=company_id, financial_account=financial_account, now=now)
    balance.current_balance_amount = money(balance.current_balance_amount) + money(delta)
    balance.last_movement_id = movement_id
    balance.updated_at = now
    db.flush()
    return balance_to_dict(balance)


def _payable_payment_description(title: FinancialTitleDB) -> str:
    snapshot = title.participant_snapshot_json or {}
    participant_name = next(
        (
            value.strip()
            for value in (
                snapshot.get("trade_name"),
                snapshot.get("name"),
                snapshot.get("legal_name"),
                snapshot.get("display_name"),
            )
            if isinstance(value, str) and value.strip()
        ),
        title.participant_id,
    )
    document = title.document_reference or title.id
    return f"Pagamento do titulo {document} - {participant_name}"


def _create_purchase_draft_model(db: Session, payload: PurchaseCreate, *, context: AuditContext) -> Any:
    _assert_company(db, payload.company_id)
    assert_period_open(
        db,
        company_id=payload.company_id,
        event_date=_purchase_reference_date(
            issue_date=payload.issue_date,
            competency_date=payload.competency_date,
            operation_date=payload.operation_date,
        ),
        operation_label="criação de compra/despesa",
    )
    participant = _get_participant(db, payload.participant_id, company_id=payload.company_id)
    _assert_master_records(db, company_id=payload.company_id, financial_category_id=payload.financial_category_id, cost_center_id=payload.cost_center_id, expected_financial_account_id=payload.expected_financial_account_id)

    now = utc_now()
    subtotal = Decimal("0.00")
    total_discount = Decimal("0.00")
    total_freight = Decimal("0.00")
    total_tax = Decimal("0.00")
    item_payloads: list[dict[str, Any]] = []
    for item in payload.items:
        item_id = item.item_id
        if item_id:
            assert_valid_id(item_id, "item")
        if item.fiscal_classification_id:
            assert_valid_id(item.fiscal_classification_id, "fclass")
        quantity = qty(item.quantity)
        unit_cost = qty(item.unit_cost)
        discount = money(item.discount_amount)
        freight = money(item.freight_amount)
        tax = money(item.tax_amount)
        line_subtotal = (quantity * unit_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        line_total = _calculate_item_total(quantity, unit_cost, discount, freight, tax)
        subtotal += line_subtotal
        total_discount += discount
        total_freight += freight
        total_tax += tax
        item_payloads.append({
            "item_id": item_id,
            "fiscal_classification_id": item.fiscal_classification_id,
            "description": item.description,
            "quantity": quantity,
            "unit": item.unit.upper(),
            "unit_cost": unit_cost,
            "discount_amount": discount,
            "freight_amount": freight,
            "tax_amount": tax,
            "total_amount": line_total,
            "metadata_json": item.metadata or {},
        })
    total = subtotal - total_discount + total_freight + total_tax
    if total <= Decimal("0.00"):
        raise ValueError("Compra/despesa precisa ter total maior que zero.")
    invoice_total = money(payload.invoice_total_amount) if payload.invoice_total_amount is not None else None
    if invoice_total is not None and invoice_total != money(total):
        raise ValueError("Valor informado da nota/documento diverge do total calculado da compra.")

    purchase = create_purchase(
        db,
        id=generate_id("buy"),
        company_id=payload.company_id,
        establishment_id=payload.establishment_id,
        participant_id=participant.id,
        status="draft",
        purchase_type=payload.purchase_type,
        origin=payload.origin,
        operation_nature_id=payload.operation_nature_id,
        fiscal_status=payload.fiscal_status,
        issue_date=payload.issue_date,
        operation_date=payload.operation_date or now,
        competency_date=payload.competency_date,
        subtotal_amount=money(subtotal),
        discount_amount=money(total_discount),
        freight_amount=money(total_freight),
        tax_amount=money(total_tax),
        total_amount=money(total),
        payable_total_amount=money(total),
        invoice_total_amount=invoice_total,
        financial_category_id=payload.financial_category_id,
        cost_center_id=payload.cost_center_id,
        expected_financial_account_id=payload.expected_financial_account_id,
        document_type=payload.document_type,
        document_number=payload.document_number,
        document_series=payload.document_series,
        access_key=payload.access_key,
        participant_snapshot_json=_participant_snapshot(participant),
        document_snapshot_json={"document_type": payload.document_type, "document_number": payload.document_number, "document_series": payload.document_series, "access_key": payload.access_key},
        metadata_json=payload.metadata or {},
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )
    for item_data in item_payloads:
        create_purchase_item(db, id=generate_id("buyitem"), company_id=payload.company_id, purchase_id=purchase.id, item_snapshot_json={"item_id": item_data["item_id"], "description": item_data["description"]}, fiscal_snapshot_json={"fiscal_classification_id": item_data["fiscal_classification_id"]}, created_at=now, updated_at=now, **item_data)
    create_purchase_status_history(db, id=generate_id("buyhist"), company_id=payload.company_id, purchase_id=purchase.id, previous_status=None, new_status="draft", reason="Criação da compra/despesa.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
    db.flush()
    purchase_dict = purchase_to_dict(purchase)
    create_audit_event(db, build_created_event(entity_type=AuditEntityType.PURCHASE, entity_id=purchase.id, context=context, after=purchase_dict), company_id=payload.company_id)
    return purchase


def create_purchase_draft(db: Session, payload: PurchaseCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    try:
        purchase = _create_purchase_draft_model(db, payload, context=context)
        result = purchase_to_dict(purchase)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def _build_purchase_source_snapshot(purchase: Any, *, installment_number: int, installment_total: int) -> dict[str, Any]:
    return {
        "purchase_id": purchase.id,
        "purchase_status": purchase.status,
        "purchase_type": purchase.purchase_type,
        "origin": purchase.origin,
        "document_type": purchase.document_type,
        "document_number": purchase.document_number,
        "payable_total_amount": str(money(purchase.payable_total_amount)),
        "installment_number": installment_number,
        "installment_total": installment_total,
    }


def _confirm_purchase_model(db: Session, purchase: Any, payload: PurchaseConfirmPayload, *, context: AuditContext) -> dict[str, Any]:
    if purchase.status != "draft":
        raise ValueError("Apenas compra/despesa em rascunho pode ser confirmada.")
    _assert_company(db, purchase.company_id)
    assert_period_open(
        db,
        company_id=purchase.company_id,
        event_date=_purchase_reference_date(
            issue_date=purchase.issue_date,
            competency_date=purchase.competency_date,
            operation_date=purchase.operation_date,
        ),
        operation_label="confirmação de compra/despesa",
    )
    _assert_master_records(
        db,
        company_id=purchase.company_id,
        financial_category_id=purchase.financial_category_id,
        cost_center_id=purchase.cost_center_id,
        expected_financial_account_id=purchase.expected_financial_account_id,
    )
    total_installments = len(payload.installments)
    expected_sum = sum((money(installment.amount) for installment in payload.installments), Decimal("0.00"))
    if money(expected_sum) != money(purchase.payable_total_amount):
        raise ValueError("Soma das parcelas a pagar não confere com o total da compra/despesa.")

    now = utc_now()
    before = purchase_to_dict(purchase)
    created_titles: list[dict[str, Any]] = []
    purchase.status = "confirmed"
    purchase.confirmed_at = now
    purchase.updated_at = now
    create_purchase_status_history(db, id=generate_id("buyhist"), company_id=purchase.company_id, purchase_id=purchase.id, previous_status="draft", new_status="confirmed", reason=payload.reason, source=context.source.value, actor_id=context.actor_id, occurred_at=now)

    for index, installment in enumerate(payload.installments, start=1):
        _assert_master_records(db, company_id=purchase.company_id, expected_financial_account_id=installment.expected_financial_account_id or purchase.expected_financial_account_id, payment_method_id=installment.payment_method_id)
        source_id = f"{purchase.id}:{index}"
        assert_period_open(
            db,
            company_id=purchase.company_id,
            event_date=installment.due_date,
            operation_label="geração de título a pagar (vencimento da parcela)",
        )
        status = _payable_status_for_due(installment.due_date, open_amount=money(installment.amount))
        payment_method = None
        if installment.payment_method_id:
            payment_method = db.scalar(select(PaymentMethodDB).where(PaymentMethodDB.id == installment.payment_method_id, PaymentMethodDB.company_id == purchase.company_id, PaymentMethodDB.deleted_at.is_(None)))
        title = create_payable_title(
            db,
            id=generate_id("ap"),
            company_id=purchase.company_id,
            direction="payable",
            title_type=purchase.purchase_type,
            source_type="purchase_payment_plan",
            source_id=source_id,
            source_snapshot_json=_build_purchase_source_snapshot(purchase, installment_number=index, installment_total=total_installments),
            sale_id=None,
            sale_payment_plan_id=None,
            participant_id=purchase.participant_id,
            participant_snapshot_json=purchase.participant_snapshot_json,
            payment_method_id=installment.payment_method_id,
            payment_method_code=payment_method.code if payment_method is not None else installment.payment_method_code,
            payment_method_name=payment_method.name if payment_method is not None else installment.payment_method_code,
            financial_category_id=purchase.financial_category_id,
            cost_center_id=purchase.cost_center_id,
            expected_financial_account_id=installment.expected_financial_account_id or purchase.expected_financial_account_id,
            document_reference=installment.document_reference or purchase.document_number or purchase.id,
            installment_number=index,
            installment_total=total_installments,
            issue_date=purchase.issue_date,
            competency_date=purchase.competency_date,
            due_date=installment.due_date,
            expected_payment_date=installment.expected_payment_date,
            gross_amount=money(installment.amount),
            discount_amount=Decimal("0.00"),
            interest_amount=Decimal("0.00"),
            penalty_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            net_amount=money(installment.amount),
            paid_amount=Decimal("0.00"),
            open_amount=money(installment.amount),
            status=status,
            collection_status="not_started" if status != "paid" else "closed",
            fiscal_status=purchase.fiscal_status,
            notes=installment.notes,
            metadata_json=installment.metadata or {},
            created_at=now,
            updated_at=now,
        )
        create_purchase_financial_link(db, id=generate_id("aplink"), company_id=purchase.company_id, purchase_id=purchase.id, financial_title_id=title.id, installment_number=index, installment_total=total_installments, link_type="generated_from_purchase", amount=money(installment.amount), status="active", metadata_json={"source_id": source_id}, created_at=now)
        create_financial_title_history(db, id=generate_id("aphist"), company_id=purchase.company_id, financial_title_id=title.id, previous_status=None, new_status=status, previous_collection_status=None, new_collection_status="not_started" if status != "paid" else "closed", reason="Título a pagar gerado pela confirmação da compra/despesa.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        title_dict = payable_to_dict(title)
        created_titles.append(title_dict)
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.ACCOUNT_PAYABLE, entity_id=title.id, context=context, after=title_dict), company_id=purchase.company_id)

    db.flush()
    after = purchase_to_dict(purchase)
    create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.PURCHASE, entity_id=purchase.id, context=context, before=before, after=after), company_id=purchase.company_id)
    return {"purchase": after, "payables": created_titles}


def confirm_purchase(db: Session, purchase_id: str, payload: PurchaseConfirmPayload, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(purchase_id, "buy")
    purchase = get_purchase_for_update(db, purchase_id)
    if purchase is None:
        raise ValueError("Compra/despesa não encontrada.")
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    try:
        result = _confirm_purchase_model(db, purchase, payload, context=context)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def create_and_confirm_purchase(db: Session, payload: PurchaseCreateAndConfirmPayload, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    try:
        purchase = _create_purchase_draft_model(db, payload.purchase, context=context)
        result = _confirm_purchase_model(db, purchase, payload.confirmation, context=context)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def list_purchases(
    db: Session,
    *,
    company_id: str,
    participant_id: str | None = None,
    status: str | None = None,
    purchase_type: str | None = None,
    date_from: Any | None = None,
    date_to: Any | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_items: bool = True,
    max_limit: int = 200,
) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    rows = repo_list_purchases(
        db,
        company_id=company_id,
        participant_id=participant_id,
        status=status,
        purchase_type=purchase_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
        include_items=include_items,
        max_limit=max_limit,
    )
    return [purchase_to_dict(row, include_items=include_items) for row in rows]


def get_purchase_detail(db: Session, purchase_id: str, *, expected_company_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(purchase_id, "buy")
    purchase = get_purchase(db, purchase_id)
    if purchase is None:
        raise ValueError("Compra/despesa não encontrada.")
    if expected_company_id is not None and purchase.company_id != expected_company_id:
        raise ValueError("Compra/despesa não pertence à empresa da sessão.")
    data = purchase_to_dict(purchase)
    data["payables"] = [payable_to_dict(row) for row in list_purchase_payables(db, company_id=purchase.company_id, purchase_id=purchase.id)]
    return data


def update_purchase(db: Session, purchase_id: str, payload: PurchaseUpdate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(purchase_id, "buy")
    purchase = get_purchase_for_update(db, purchase_id)
    if purchase is None:
        raise ValueError("Compra/despesa não encontrada.")
    if purchase.status != "draft":
        raise ValueError("Apenas compra/despesa em rascunho pode ser editada neste MVP.")
    _assert_master_records(db, company_id=purchase.company_id, financial_category_id=payload.financial_category_id, cost_center_id=payload.cost_center_id, expected_financial_account_id=payload.expected_financial_account_id)
    before = purchase_to_dict(purchase)
    updates = payload.model_dump(exclude_unset=True)
    now = utc_now()
    updates["updated_at"] = now
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    try:
        update_purchase_fields(purchase, **updates)
        after = purchase_to_dict(purchase)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.UPDATED, entity_type=AuditEntityType.PURCHASE, entity_id=purchase.id, context=context, before=before, after=after), company_id=purchase.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def cancel_purchase(db: Session, purchase_id: str, payload: StatusChangePayload, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(purchase_id, "buy")
    purchase = get_purchase_for_update(db, purchase_id)
    if purchase is None:
        raise ValueError("Compra/despesa não encontrada.")
    if purchase.status == "cancelled":
        raise ValueError("Compra/despesa já está cancelada.")
    blocking_payables = [row for row in list_purchase_payables(db, company_id=purchase.company_id, purchase_id=purchase.id) if row.status not in {"cancelled", "written_off"}]
    if blocking_payables:
        raise ValueError("Não cancele compra/despesa com títulos vinculados ativos, vencidos, parciais ou pagos. Cancele/estorne os títulos antes.")
    assert_period_open(db, company_id=purchase.company_id, event_date=today_in_brazil(), operation_label="cancelamento de compra/despesa")
    assert_period_open(
        db,
        company_id=purchase.company_id,
        event_date=_purchase_reference_date(
            issue_date=purchase.issue_date,
            competency_date=purchase.competency_date,
            operation_date=purchase.operation_date,
        ),
        operation_label="cancelamento de compra/despesa em período fechado",
    )
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before = purchase_to_dict(purchase)
    try:
        previous = purchase.status
        purchase.status = "cancelled"
        purchase.cancelled_at = now
        purchase.updated_at = now
        create_purchase_status_history(db, id=generate_id("buyhist"), company_id=purchase.company_id, purchase_id=purchase.id, previous_status=previous, new_status="cancelled", reason=payload.reason, source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after = purchase_to_dict(purchase)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.PURCHASE, entity_id=purchase.id, context=context, before=before, after=after), company_id=purchase.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def list_payables(
    db: Session,
    *,
    company_id: str,
    participant_id: str | None = None,
    status: str | None = None,
    purchase_id: str | None = None,
    financial_category_id: str | None = None,
    cost_center_id: str | None = None,
    expected_financial_account_id: str | None = None,
    due_from: Any | None = None,
    due_to: Any | None = None,
    open_amount_min: Decimal | None = None,
    open_amount_max: Decimal | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    max_limit: int = 200,
) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    return [
        payable_to_dict(row)
        for row in repo_list_payables(
            db,
            company_id=company_id,
            participant_id=participant_id,
            status=status,
            purchase_id=purchase_id,
            financial_category_id=financial_category_id,
            cost_center_id=cost_center_id,
            expected_financial_account_id=expected_financial_account_id,
            due_from=due_from,
            due_to=due_to,
            open_amount_min=open_amount_min,
            open_amount_max=open_amount_max,
            q=q,
            limit=limit,
            offset=offset,
            max_limit=max_limit,
        )
    ]


def get_payable_detail(db: Session, title_id: str, *, expected_company_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(title_id, "ap")
    row = get_payable(db, title_id)
    if row is None:
        raise ValueError("Título a pagar não encontrado.")
    if expected_company_id is not None and row.company_id != expected_company_id:
        raise ValueError("Título a pagar não pertence à empresa da sessão.")
    return payable_to_dict(row)


def pay_payable(db: Session, payload: PayablePaymentCreate, *, principal: SecurityPrincipal, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    require_permission(principal, "payables.pay")
    _assert_company(db, payload.company_id)
    if principal.company_id != payload.company_id:
        raise ValueError("Sessão autenticada não pertence à empresa informada para o pagamento.")
    if not (payload.evidence_reference or "").strip():
        raise ValueError("Pagamento de título a pagar exige comprovante, extrato ou justificativa.")
    assert_valid_id(payload.financial_title_id, "ap")
    account = _get_financial_account(db, payload.financial_account_id, company_id=payload.company_id)
    _assert_master_records(db, company_id=payload.company_id, payment_method_id=payload.payment_method_id)
    if payload.source_id and get_settlement_by_source(db, company_id=payload.company_id, source_type=payload.source_type, source_id=payload.source_id):
        raise ValueError("Já existe pagamento/baixa para esta origem.")
    title = get_payable_for_update(db, payload.financial_title_id)
    if title is None or title.company_id != payload.company_id or title.direction != "payable":
        raise ValueError("Título a pagar não encontrado para a empresa.")
    if title.status in {"cancelled", "paid", "written_off"}:
        raise ValueError("Título encerrado não pode receber novo pagamento.")

    assert_period_open(db, company_id=payload.company_id, event_date=payload.payment_date, operation_label="baixa/pagamento de título a pagar")
    assert_period_open(db, company_id=payload.company_id, event_date=payload.competency_date, operation_label="competência do pagamento de título a pagar")
    paid = money(payload.paid_amount)
    discount = money(payload.discount_amount)
    interest = money(payload.interest_amount)
    penalty = money(payload.penalty_amount)
    fee = money(payload.fee_amount)
    title_effect = paid + discount
    movement_amount = paid + interest + penalty + fee
    if title_effect <= Decimal("0.00"):
        raise ValueError("Pagamento precisa reduzir o saldo do título.")
    if title_effect > money(title.open_amount):
        raise ValueError("Valor do pagamento excede o saldo em aberto do título.")
    if movement_amount <= Decimal("0.00"):
        raise ValueError("Movimento financeiro de pagamento precisa ser maior que zero.")
    assert_payment_within_policy_or_approved(
        db,
        actor=principal,
        financial_title_id=payload.financial_title_id,
        payment_amount=movement_amount,
        approval_request_id=payload.approval_request_id,
    )

    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_title = payable_to_dict(title)
    try:
        settlement = create_settlement(
            db,
            id=generate_id("sett"),
            company_id=payload.company_id,
            direction="outflow",
            settlement_type="payment",
            financial_title_id=title.id,
            participant_id=title.participant_id,
            financial_account_id=account.id,
            payment_method_id=payload.payment_method_id,
            settlement_date=payload.payment_date,
            competency_date=payload.competency_date,
            received_amount=paid,
            discount_amount=discount,
            interest_amount=interest,
            penalty_amount=penalty,
            fee_amount=fee,
            title_settled_amount=title_effect,
            movement_amount=movement_amount,
            source_type=payload.source_type,
            source_id=payload.source_id or generate_id("sett"),
            evidence_reference=payload.evidence_reference,
            notes=payload.notes,
            status="active",
            reversal_of_settlement_id=None,
            reversed_at=None,
            metadata_json=payload.metadata or {},
            created_at=now,
            updated_at=now,
        )
        movement = create_movement(
            db,
            id=generate_id("cash"),
            company_id=payload.company_id,
            financial_account_id=account.id,
            direction="outflow",
            movement_type="payment",
            movement_date=payload.payment_date,
            amount=movement_amount,
            currency=account.currency or "BRL",
            source_type="settlement",
            source_id=settlement.id,
            settlement_id=settlement.id,
            financial_title_id=title.id,
            participant_id=title.participant_id,
            description=_payable_payment_description(title),
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=None,
            metadata_json={"settlement_id": settlement.id, "title_id": title.id, "direction": "payable"},
            created_at=now,
            updated_at=now,
        )
        balance = _apply_account_delta(db, company_id=payload.company_id, financial_account=account, delta=-movement_amount, movement_id=movement.id, now=now)
        new_paid = money(title.paid_amount) + paid
        new_open = money(title.open_amount) - title_effect
        new_status = "paid" if new_open <= Decimal("0.00") else ("overdue" if title.due_date and title.due_date < today_in_brazil() else "partially_paid")
        collection_status = "closed" if new_status == "paid" else "not_started"
        update_title_fields(title, paid_amount=new_paid, open_amount=new_open, status=new_status, collection_status=collection_status, updated_at=now)
        create_financial_title_history(db, id=generate_id("aphist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before_title["status"], new_status=new_status, previous_collection_status=before_title["collection_status"], new_collection_status=collection_status, reason="Pagamento/baixa de título a pagar registrado.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after_title = payable_to_dict(title)
        event = build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.ACCOUNT_PAYABLE, entity_id=title.id, context=context, before=before_title, after=after_title)
        create_audit_event(db, event, company_id=payload.company_id)
        db.commit()
        return {"settlement": settlement_to_dict(settlement), "movement": movement_to_dict(movement), "title": after_title, "balance": balance}
    except Exception:
        db.rollback()
        raise


def cancel_payable(db: Session, title_id: str, payload: StatusChangePayload, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(title_id, "ap")
    title = get_payable_for_update(db, title_id)
    if title is None:
        raise ValueError("Título a pagar não encontrado.")
    if title.status in {"paid", "partially_paid", "written_off"}:
        raise ValueError("Título com pagamento não deve ser cancelado sem estorno controlado.")
    if title.status == "cancelled":
        raise ValueError("Título a pagar já está cancelado.")
    assert_period_open(db, company_id=title.company_id, event_date=today_in_brazil(), operation_label="cancelamento de título a pagar")
    assert_period_open(
        db,
        company_id=title.company_id,
        event_date=_purchase_reference_date(issue_date=title.issue_date, competency_date=title.competency_date, operation_date=title.due_date),
        operation_label="cancelamento de título a pagar em período fechado",
    )
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before = payable_to_dict(title)
    try:
        title.status = "cancelled"
        title.collection_status = "closed"
        title.cancelled_at = now
        title.updated_at = now
        create_financial_title_history(db, id=generate_id("aphist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before["status"], new_status="cancelled", previous_collection_status=before["collection_status"], new_collection_status="closed", reason=payload.reason, source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after = payable_to_dict(title)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.ACCOUNT_PAYABLE, entity_id=title.id, context=context, before=before, after=after), company_id=title.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def get_purchases_payables_summary(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company(db, company_id)
    return summary_by_company(db, company_id=company_id, today=today_in_brazil())


def get_purchases_payables_overview_evidence(db: Session, *, company_id: str, block: str | None = None, limit: int = 500) -> dict[str, Any]:
    _assert_company(db, company_id)
    allowed_blocks = {"open_payables", "overdue_payables", "paid_payables", "draft_purchases", "confirmed_purchases"}
    if block is not None and block not in allowed_blocks:
        raise ValueError("Bloco de evidência de Compras e Contas a Pagar inválido.")

    today = today_in_brazil()
    summary = summary_by_company(db, company_id=company_id, today=today)

    def include(name: str) -> bool:
        return block is None or block == name

    open_payables = [payable_to_dict(row) for row in list_payables_for_overview(db, company_id=company_id, block="open_payables", today=today, limit=limit)] if include("open_payables") else []
    overdue_payables = [payable_to_dict(row) for row in list_payables_for_overview(db, company_id=company_id, block="overdue_payables", today=today, limit=limit)] if include("overdue_payables") else []
    paid_payables = [payable_to_dict(row) for row in list_payables_for_overview(db, company_id=company_id, block="paid_payables", today=today, limit=limit)] if include("paid_payables") else []
    draft_purchases = [purchase_to_dict(row, include_items=False) for row in list_purchases_for_overview(db, company_id=company_id, status="draft", limit=limit)] if include("draft_purchases") else []
    confirmed_purchases = [purchase_to_dict(row, include_items=False) for row in list_purchases_for_overview(db, company_id=company_id, status="confirmed", limit=limit)] if include("confirmed_purchases") else []

    return {
        "company_id": company_id,
        "summary": summary,
        "open_payables": open_payables,
        "overdue_payables": overdue_payables,
        "paid_payables": paid_payables,
        "draft_purchases": draft_purchases,
        "confirmed_purchases": confirmed_purchases,
    }


def get_purchase_history(db: Session, purchase_id: str, *, expected_company_id: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(purchase_id, "buy")
    purchase = get_purchase(db, purchase_id)
    if purchase is None:
        raise ValueError("Compra/despesa não encontrada.")
    if expected_company_id is not None and purchase.company_id != expected_company_id:
        raise ValueError("Compra/despesa não pertence à empresa da sessão.")
    return [purchase_history_to_dict(row) for row in list_purchase_history(db, purchase_id)]


def get_purchase_audit_events(db: Session, purchase_id: str, *, expected_company_id: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(purchase_id, "buy")
    if expected_company_id is not None:
        purchase = get_purchase(db, purchase_id)
        if purchase is None:
            raise ValueError("Compra/despesa não encontrada.")
        if purchase.company_id != expected_company_id:
            raise ValueError("Compra/despesa não pertence à empresa da sessão.")
    return [audit_event_db_to_dict(event) for event in list_audit_events_for_entity(db, AuditEntityType.PURCHASE.value, purchase_id)]


def get_payable_audit_events(db: Session, title_id: str, *, expected_company_id: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(title_id, "ap")
    if expected_company_id is not None:
        payable = get_payable(db, title_id)
        if payable is None:
            raise ValueError("Título a pagar não encontrado.")
        if payable.company_id != expected_company_id:
            raise ValueError("Título a pagar não pertence à empresa da sessão.")
    return [audit_event_db_to_dict(event) for event in list_audit_events_for_entity(db, AuditEntityType.ACCOUNT_PAYABLE.value, title_id)]


def get_purchases_payables_diagnostics() -> dict[str, Any]:
    return {
        "module": "purchases_payables",
        "status": "ready",
        "storage": "postgresql",
        "tables_created": ["purchases", "purchase_items", "purchase_financial_links", "purchase_status_history"],
        "tables_consumed": ["companies", "participants", "catalog_items", "financial_titles", "settlements", "financial_movements", "financial_account_balances", "financial_accounts", "payment_methods", "financial_categories", "cost_centers", "audit_events"],
        "integrations": ["company", "participants", "catalog", "financial", "cash", "cash_flow", "reconciliation"],
        "safety": [
            "Compra/despesa não é pagamento.",
            "Título a pagar não é saída de caixa até existir baixa/pagamento.",
            "Pagamento gera movement outflow e deixa conciliação pendente.",
            "Documento fiscal de entrada é preparado por referência; importação XML real fica para bloco fiscal.",
            "Cancelamento não apaga histórico e exige justificativa.",
        ],
    }


def get_purchases_payables_rules() -> dict[str, Any]:
    return {
        "principles": [
            "Fornecedor, compra, título, pagamento e conciliação são fatos diferentes.",
            "Toda obrigação deve ter empresa, participante, vencimento, valor, status e trilha.",
            "Contas a Pagar usa financial_titles com direction=payable.",
            "Baixa de título a pagar gera settlement outflow e financial_movement outflow.",
            "Extrato importado não cria compra nem pagamento; ele apenas serve como evidência de conciliação.",
        ],
        "status_flow": {
            "purchase": "draft -> confirmed -> cancelled",
            "payable": "open/overdue -> partially_paid -> paid ou cancelled",
            "settlement": "active; reversão futura deve gerar movimento reverso",
        },
        "anti_patterns": [
            "Cadastrar fornecedor como texto solto na despesa.",
            "Marcar compra como paga sem movimento financeiro.",
            "Confundir nota/documento fiscal com pagamento.",
            "Baixar título diretamente pela conciliação sem evento financeiro interno.",
        ],
    }
