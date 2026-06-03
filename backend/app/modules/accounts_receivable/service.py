from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.repository import (
    create_sale_financial_link,
    create_title,
    create_title_history,
    get_title,
    get_title_by_source,
    get_title_for_update,
    history_to_dict,
    list_history,
    list_titles as repository_list_titles,
    list_titles_by_sale,
    summary_by_company,
    title_to_dict,
    update_title_fields,
)
from app.modules.accounts_receivable.schemas import FinancialTitleCreate, FinancialTitleStatusChange, FinancialTitleUpdate
from app.modules.cash.db_models import FinancialMovementDB, SettlementDB
from app.modules.company.db_models import CompanyDB
from app.modules.financial.db_models import CostCenterDB, FinancialAccountDB, FinancialCategoryDB
from app.modules.financial.period_service import assert_period_open
from app.modules.participants.db_models import ParticipantDB
from app.modules.sales.db_models import PaymentMethodDB, SaleDB
from app.modules.sales.repository import sale_db_to_domain
from app.modules.sales.models import sale_to_dict
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event, build_updated_event
from app.shared.audit_repository import audit_event_db_to_dict, create_audit_event, list_audit_events_for_entity
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import assert_valid_id, generate_id

MONEY_QUANT = Decimal("0.01")


def _title_has_active_settlement_or_movement(db: Session, *, company_id: str, title_id: str) -> bool:
    active_settlement = db.scalar(
        select(SettlementDB.id)
        .where(
            SettlementDB.company_id == company_id,
            SettlementDB.financial_title_id == title_id,
            SettlementDB.status == "active",
        )
        .limit(1)
    )
    if active_settlement is not None:
        return True

    active_movement = db.scalar(
        select(FinancialMovementDB.id)
        .where(
            FinancialMovementDB.company_id == company_id,
            FinancialMovementDB.financial_title_id == title_id,
            FinancialMovementDB.status == "posted",
            FinancialMovementDB.movement_type != "reversal",
            FinancialMovementDB.reconciliation_status != "reversed",
        )
        .limit(1)
    )
    return active_movement is not None


def assert_sale_receivables_can_be_cancelled(db: Session, sale_id: str, *, company_id: str) -> None:
    titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale_id)
    for title in titles:
        if title.status == "cancelled":
            continue
        if _title_has_active_settlement_or_movement(db, company_id=company_id, title_id=title.id):
            raise ValueError("Não é possível cancelar pedido com baixa ativa. Estorne a baixa em Caixa e Baixas antes de cancelar o pedido.")
        if _money(title.paid_amount) > Decimal("0.00") or title.status in {"received", "partially_received"}:
            raise ValueError("Não é possível cancelar pedido com título já recebido. Regularize ou estorne o financeiro antes de cancelar o pedido.")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money_text(value: Any) -> str:
    return format(_money(value), "f")


def _audit_context(actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> AuditContext:
    if isinstance(source, str):
        source = AuditSource(source)
    return AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def _assert_company(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    exists = db.scalar(select(CompanyDB.id).where(CompanyDB.id == company_id, CompanyDB.deleted_at.is_(None)))
    if not exists:
        raise ValueError("Empresa não encontrada.")


def _assert_title_company_scope(title: Any, expected_company_id: str | None) -> None:
    if expected_company_id is not None and title.company_id != expected_company_id:
        raise ValueError("Sessão autenticada não pertence à empresa do título.")


def _get_participant(db: Session, participant_id: str, *, company_id: str) -> ParticipantDB:
    assert_valid_id(participant_id, "part")
    participant = db.scalar(select(ParticipantDB).where(ParticipantDB.id == participant_id, ParticipantDB.company_id == company_id, ParticipantDB.deleted_at.is_(None)))
    if participant is None:
        raise ValueError("Participante não encontrado para a empresa.")
    if participant.status not in {"active"}:
        raise ValueError("Participante precisa estar ativo para gerar conta a receber.")
    return participant


def _participant_snapshot(participant: ParticipantDB) -> dict[str, Any]:
    return {
        "id": participant.id,
        "name": participant.name,
        "trade_name": participant.trade_name,
        "participant_type": participant.participant_type,
        "person_type": participant.person_type,
        "document": participant.document,
        "email": participant.email,
        "phone": participant.phone,
        "status": participant.status,
    }


def _assert_optional_master_records(db: Session, *, company_id: str, financial_category_id: str | None = None, cost_center_id: str | None = None, expected_financial_account_id: str | None = None, payment_method_id: str | None = None) -> dict[str, Any]:
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


def _status_for_due(due_date: date, *, open_amount: Decimal) -> str:
    if open_amount <= Decimal("0.00"):
        return "received"
    return "overdue" if due_date < today_in_brazil() else "open"


def _collection_for_due(due_date: date, status: str) -> str:
    if status == "overdue":
        return "in_collection"
    if status in {"received", "cancelled", "written_off"}:
        return "closed"
    return "not_started"


def _reference_date(
    *,
    issue_date: date | None,
    competency_date: date | None,
    due_date: date | None,
) -> date | None:
    return competency_date or issue_date or due_date


def _calculate_net_amount(*, gross_amount: Decimal, discount_amount: Decimal, interest_amount: Decimal, penalty_amount: Decimal, fee_amount: Decimal) -> Decimal:
    net = gross_amount - discount_amount + interest_amount + penalty_amount - fee_amount
    if net < Decimal("0.00"):
        raise ValueError("Valor líquido do título não pode ficar negativo.")
    return net.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def create_manual_receivable(db: Session, payload: FinancialTitleCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, payload.company_id)
    assert_period_open(
        db,
        company_id=payload.company_id,
        event_date=_reference_date(
            issue_date=payload.issue_date,
            competency_date=payload.competency_date,
            due_date=payload.due_date,
        ),
        operation_label="criação manual de título a receber",
    )
    participant = _get_participant(db, payload.participant_id, company_id=payload.company_id)
    resolved = _assert_optional_master_records(db, company_id=payload.company_id, financial_category_id=payload.financial_category_id, cost_center_id=payload.cost_center_id, expected_financial_account_id=payload.expected_financial_account_id, payment_method_id=payload.payment_method_id)
    gross = _money(payload.gross_amount)
    discount = _money(payload.discount_amount)
    interest = _money(payload.interest_amount)
    penalty = _money(payload.penalty_amount)
    fee = _money(payload.fee_amount)
    if gross <= Decimal("0.00"):
        raise ValueError("Título a receber precisa ter valor bruto maior que zero.")
    net = _calculate_net_amount(gross_amount=gross, discount_amount=discount, interest_amount=interest, penalty_amount=penalty, fee_amount=fee)
    status = _status_for_due(payload.due_date, open_amount=net)
    collection_status = _collection_for_due(payload.due_date, status)
    now = utc_now()
    source_id = payload.source_id or generate_id("ar")
    if get_title_by_source(db, company_id=payload.company_id, source_type=payload.source_type, source_id=source_id):
        raise ValueError("Já existe título financeiro para esta origem.")

    payment_method = resolved.get("payment_method")
    title = create_title(
        db,
        id=generate_id("ar"),
        company_id=payload.company_id,
        direction="receivable",
        title_type=payload.title_type,
        source_type=payload.source_type,
        source_id=source_id,
        source_snapshot_json={"source_type": payload.source_type, "source_id": source_id, "origin": "manual_receivable"},
        sale_id=None,
        sale_payment_plan_id=None,
        participant_id=participant.id,
        participant_snapshot_json=_participant_snapshot(participant),
        payment_method_id=payment_method.id if payment_method is not None else payload.payment_method_id,
        payment_method_code=payment_method.code if payment_method is not None else payload.payment_method_code,
        payment_method_name=payment_method.name if payment_method is not None else payload.payment_method_code,
        financial_category_id=payload.financial_category_id,
        cost_center_id=payload.cost_center_id,
        expected_financial_account_id=payload.expected_financial_account_id,
        document_reference=payload.document_reference,
        installment_number=payload.installment_number,
        installment_total=payload.installment_total,
        issue_date=payload.issue_date,
        competency_date=payload.competency_date,
        due_date=payload.due_date,
        expected_payment_date=payload.expected_payment_date,
        gross_amount=gross,
        discount_amount=discount,
        interest_amount=interest,
        penalty_amount=penalty,
        fee_amount=fee,
        net_amount=net,
        paid_amount=Decimal("0.00"),
        open_amount=net,
        status=status,
        collection_status=collection_status,
        fiscal_status=payload.fiscal_status,
        notes=payload.notes,
        metadata_json=payload.metadata,
        created_at=now,
        updated_at=now,
    )
    after = title_to_dict(title)
    try:
        context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        create_title_history(db, id=generate_id("arhist"), company_id=payload.company_id, financial_title_id=title.id, previous_status=None, new_status=status, previous_collection_status=None, new_collection_status=collection_status, reason="Criação manual de título a receber.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        event = build_created_event(entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, after=after)
        create_audit_event(db, event, company_id=payload.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return after


def _build_sale_source_snapshot(sale: Any, plan: Any) -> dict[str, Any]:
    return {
        "sale_id": sale.id,
        "sale_number": sale.sale_number,
        "sale_number_text": sale.sale_number_text,
        "sale_status": sale.status.value if hasattr(sale.status, "value") else str(sale.status),
        "sale_type": sale.sale_type.value if hasattr(sale.sale_type, "value") else str(sale.sale_type),
        "operation_nature_id": sale.operation_nature_id,
        "operation_nature": sale.operation_nature.value if hasattr(sale.operation_nature, "value") else str(sale.operation_nature),
        "receivable_total_amount": sale.receivable_total_amount,
        "payment_plan_id": plan.id,
        "payment_method_id": plan.payment_method_id,
        "payment_method_code": plan.payment_method_code,
        "payment_method_name": plan.payment_method_name,
        "payment_plan_amount": plan.amount,
        "payment_plan_due_date": plan.due_date.isoformat() if plan.due_date else None,
    }


def _sale_receivable_document_reference(sale: Any, *, installment_number: int, installment_total: int) -> str:
    sale_number_text = getattr(sale, "sale_number_text", None)
    base = f"RECEBER-{sale_number_text}" if sale_number_text else f"RECEBER-{sale.id}"
    if installment_total > 1:
        return f"{base}-{installment_number:02d}/{installment_total:02d}"
    return base


def generate_receivables_from_sale(db: Session, sale: Any, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, reason: str | None = None) -> list[dict[str, Any]]:
    """Gera títulos a receber a partir de sale_payment_plans.

    Usado dentro da mesma transação de confirmação da venda. É idempotente por
    company_id + source_type + source_id; se chamado novamente, retorna os títulos existentes.
    """
    company_id = sale.company_id
    _assert_company(db, company_id)
    assert_period_open(
        db,
        company_id=company_id,
        event_date=_reference_date(
            issue_date=sale.issue_date,
            competency_date=sale.competency_date,
            due_date=None,
        ),
        operation_label="geração de títulos a receber da venda",
    )
    if _money(sale.receivable_total_amount) <= Decimal("0.00"):
        return []
    if not sale.payment_plans:
        raise ValueError("Venda com valor a receber precisa ter plano de pagamento para gerar Contas a Receber.")

    created_or_existing: list[dict[str, Any]] = []
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source)
    expected_sum = Decimal("0.00")
    for plan in sale.payment_plans:
        expected_sum += _money(plan.amount)
    if expected_sum != _money(sale.receivable_total_amount):
        raise ValueError("Soma dos planos de pagamento não confere com total a receber da venda.")

    for index, plan in enumerate(sale.payment_plans, start=1):
        existing = get_title_by_source(db, company_id=company_id, source_type="sale_payment_plan", source_id=plan.id)
        if existing is not None:
            created_or_existing.append(title_to_dict(existing))
            continue
        amount = _money(plan.amount)
        due_date = plan.due_date or sale.issue_date or sale.competency_date or today_in_brazil()
        status = _status_for_due(due_date, open_amount=amount)
        collection_status = _collection_for_due(due_date, status)
        document_reference = _sale_receivable_document_reference(
            sale,
            installment_number=index,
            installment_total=len(sale.payment_plans),
        )
        title = create_title(
            db,
            id=generate_id("ar"),
            company_id=company_id,
            direction="receivable",
            title_type="sale",
            source_type="sale_payment_plan",
            source_id=plan.id,
            source_snapshot_json=_build_sale_source_snapshot(sale, plan),
            sale_id=sale.id,
            sale_payment_plan_id=plan.id,
            participant_id=sale.participant_id,
            participant_snapshot_json=sale.participant_snapshot,
            payment_method_id=plan.payment_method_id,
            payment_method_code=plan.payment_method_code,
            payment_method_name=plan.payment_method_name,
            financial_category_id=None,
            cost_center_id=None,
            expected_financial_account_id=None,
            document_reference=document_reference,
            installment_number=index,
            installment_total=len(sale.payment_plans),
            issue_date=sale.issue_date,
            competency_date=sale.competency_date,
            due_date=due_date,
            expected_payment_date=due_date,
            gross_amount=amount,
            discount_amount=Decimal("0.00"),
            interest_amount=Decimal("0.00"),
            penalty_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            net_amount=amount,
            paid_amount=Decimal("0.00"),
            open_amount=amount,
            status=status,
            collection_status=collection_status,
            fiscal_status="not_required" if (sale.fiscal_status.value if hasattr(sale.fiscal_status, "value") else str(sale.fiscal_status)) == "not_required" else "pending_document",
            notes=plan.notes or "Título gerado automaticamente a partir do pedido fechado.",
            metadata_json={"generated_by": "sales.confirm", "reason": reason},
            created_at=now,
            updated_at=now,
        )
        create_sale_financial_link(db, id=generate_id("arlink"), company_id=company_id, sale_id=sale.id, sale_payment_plan_id=plan.id, financial_title_id=title.id, link_type="generated_from_sale", amount=amount, status="active", metadata_json={"generated_by": "sales.confirm"}, created_at=now)
        create_title_history(db, id=generate_id("arhist"), company_id=company_id, financial_title_id=title.id, previous_status=None, new_status=status, previous_collection_status=None, new_collection_status=collection_status, reason="Título gerado a partir do fechamento do pedido.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after = title_to_dict(title)
        event = build_created_event(entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, after=after)
        create_audit_event(db, event, company_id=company_id)
        created_or_existing.append(after)
    return created_or_existing


def generate_receivables_from_sale_id(db: Session, sale_id: str, *, expected_company_id: str | None = None, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, reason: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(sale_id, "sale")
    sale_db = db.scalar(select(SaleDB).where(SaleDB.id == sale_id))
    if sale_db is None:
        raise ValueError("Venda não encontrada.")
    if expected_company_id is not None and sale_db.company_id != expected_company_id:
        raise ValueError("Sessão autenticada não pertence à empresa da venda.")
    sale = sale_db_to_domain(sale_db)
    status = sale.status.value if hasattr(sale.status, "value") else str(sale.status)
    if status not in {"closed", "confirmed"}:
        raise ValueError("Apenas pedido fechado pode gerar Contas a Receber.")
    try:
        titles = generate_receivables_from_sale(db, sale, actor_id=actor_id, source=source, reason=reason)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return titles


def cancel_receivables_for_sale(db: Session, sale_id: str, *, company_id: str, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, reason: str | None = None) -> list[dict[str, Any]]:
    titles = list_titles_by_sale(db, company_id=company_id, sale_id=sale_id)
    if not titles:
        return []
    assert_sale_receivables_can_be_cancelled(db, sale_id, company_id=company_id)
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source)
    cancelled: list[dict[str, Any]] = []
    for title in titles:
        if title.status == "cancelled":
            cancelled.append(title_to_dict(title))
            continue
        assert_period_open(
            db,
            company_id=company_id,
            event_date=today_in_brazil(),
            operation_label="cancelamento de titulo a receber vinculado a venda",
        )
        assert_period_open(
            db,
            company_id=company_id,
            event_date=_reference_date(
                issue_date=title.issue_date,
                competency_date=title.competency_date,
                due_date=title.due_date,
            ),
            operation_label="cancelamento de titulo a receber em periodo fechado",
        )
        if _money(title.paid_amount) > Decimal("0.00"):
            raise ValueError("Não é possível cancelar venda com título já recebido. Será necessário estorno/baixa em etapa financeira futura.")
        before = title_to_dict(title)
        previous_status = title.status
        previous_collection = title.collection_status
        update_title_fields(title, status="cancelled", collection_status="closed", open_amount=Decimal("0.00"), cancelled_at=now, updated_at=now, metadata_json={**(title.metadata_json or {}), "cancel_reason": reason})
        create_title_history(db, id=generate_id("arhist"), company_id=company_id, financial_title_id=title.id, previous_status=previous_status, new_status="cancelled", previous_collection_status=previous_collection, new_collection_status="closed", reason=reason or "Cancelamento da venda de origem.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after = title_to_dict(title)
        event = build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, before=before, after=after, metadata={"sale_id": sale_id, "reason": reason})
        create_audit_event(db, event, company_id=company_id)
        cancelled.append(after)
    return cancelled


def list_receivables(db: Session, *, company_id: str, participant_id: str | None = None, status: str | None = None, collection_status: str | None = None, fiscal_status: str | None = None, sale_id: str | None = None, source_type: str | None = None, due_from: date | None = None, due_to: date | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if participant_id:
        assert_valid_id(participant_id, "part")
    if sale_id:
        assert_valid_id(sale_id, "sale")
    return [title_to_dict(row) for row in repository_list_titles(db, company_id=company_id, participant_id=participant_id, status=status, collection_status=collection_status, fiscal_status=fiscal_status, sale_id=sale_id, source_type=source_type, due_from=due_from, due_to=due_to, q=q, limit=limit, offset=offset)]


def get_receivable(db: Session, title_id: str, *, expected_company_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(title_id, "ar")
    title = get_title(db, title_id)
    if title is None:
        raise ValueError("Título a receber não encontrado.")
    _assert_title_company_scope(title, expected_company_id)
    return title_to_dict(title)


def update_receivable(db: Session, title_id: str, payload: FinancialTitleUpdate, *, expected_company_id: str | None = None, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(title_id, "ar")
    title = get_title_for_update(db, title_id)
    if title is None:
        raise ValueError("Título a receber não encontrado.")
    _assert_title_company_scope(title, expected_company_id)
    if title.status in {"cancelled", "received", "written_off"}:
        raise ValueError("Título encerrado não pode ser alterado nesta etapa.")
    assert_period_open(
        db,
        company_id=title.company_id,
        event_date=today_in_brazil(),
        operation_label="alteracao de titulo a receber",
    )
    assert_period_open(
        db,
        company_id=title.company_id,
        event_date=_reference_date(issue_date=title.issue_date, competency_date=title.competency_date, due_date=title.due_date),
        operation_label="alteracao de titulo a receber em periodo fechado",
    )
    _assert_optional_master_records(db, company_id=title.company_id, financial_category_id=payload.financial_category_id, cost_center_id=payload.cost_center_id, expected_financial_account_id=payload.expected_financial_account_id)
    before = title_to_dict(title)
    updates: dict[str, Any] = {"updated_at": utc_now()}
    for field in ["due_date", "expected_payment_date", "financial_category_id", "cost_center_id", "expected_financial_account_id", "document_reference", "collection_status", "fiscal_status", "notes"]:
        value = getattr(payload, field)
        if value is not None:
            updates[field] = value
    if payload.metadata is not None:
        updates["metadata_json"] = payload.metadata
    if "due_date" in updates:
        updates["status"] = _status_for_due(updates["due_date"], open_amount=_money(title.open_amount))
        if payload.collection_status is None:
            updates["collection_status"] = _collection_for_due(updates["due_date"], updates["status"])
    try:
        update_title_fields(title, **updates)
        after = title_to_dict(title)
        context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        if before != after:
            create_title_history(db, id=generate_id("arhist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before["status"], new_status=after["status"], previous_collection_status=before["collection_status"], new_collection_status=after["collection_status"], reason="Atualização cadastral do título a receber.", source=context.source.value, actor_id=context.actor_id, occurred_at=updates["updated_at"])
            event = build_updated_event(entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, before=before, after=after)
            create_audit_event(db, event, company_id=title.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return title_to_dict(title)


def cancel_receivable(db: Session, title_id: str, payload: FinancialTitleStatusChange, *, expected_company_id: str | None = None, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(title_id, "ar")
    title = get_title_for_update(db, title_id)
    if title is None:
        raise ValueError("Título a receber não encontrado.")
    _assert_title_company_scope(title, expected_company_id)
    if title.status == "cancelled":
        raise ValueError("Título já está cancelado.")
    if _money(title.paid_amount) > Decimal("0.00"):
        raise ValueError("Título com recebimento registrado não pode ser cancelado sem estorno.")
    if _title_has_active_settlement_or_movement(db, company_id=title.company_id, title_id=title.id):
        raise ValueError("Título com baixa ou movimento financeiro ativo não pode ser cancelado sem estorno.")
    assert_period_open(
        db,
        company_id=title.company_id,
        event_date=today_in_brazil(),
        operation_label="cancelamento de titulo a receber",
    )
    assert_period_open(
        db,
        company_id=title.company_id,
        event_date=_reference_date(issue_date=title.issue_date, competency_date=title.competency_date, due_date=title.due_date),
        operation_label="cancelamento de titulo a receber em periodo fechado",
    )
    before = title_to_dict(title)
    now = utc_now()
    try:
        context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
        update_title_fields(title, status="cancelled", collection_status="closed", open_amount=Decimal("0.00"), cancelled_at=now, updated_at=now)
        create_title_history(db, id=generate_id("arhist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before["status"], new_status="cancelled", previous_collection_status=before["collection_status"], new_collection_status="closed", reason=payload.reason, source=context.source.value, actor_id=context.actor_id, occurred_at=now)
        after = title_to_dict(title)
        event = build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, before=before, after=after, metadata={"reason": payload.reason})
        create_audit_event(db, event, company_id=title.company_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return title_to_dict(title)


def get_receivables_summary(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company(db, company_id)
    return summary_by_company(db, company_id=company_id, today=today_in_brazil())


def get_receivable_history(db: Session, title_id: str, *, expected_company_id: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(title_id, "ar")
    title = get_title(db, title_id)
    if title is None:
        raise ValueError("Título a receber não encontrado.")
    _assert_title_company_scope(title, expected_company_id)
    return [history_to_dict(row) for row in list_history(db, title_id)]


def get_receivable_audit_events(db: Session, title_id: str, *, expected_company_id: str | None = None) -> list[dict[str, Any]]:
    assert_valid_id(title_id, "ar")
    title = get_title(db, title_id)
    if title is None:
        raise ValueError("Título a receber não encontrado.")
    _assert_title_company_scope(title, expected_company_id)
    events = list_audit_events_for_entity(db, entity_type=AuditEntityType.ACCOUNT_RECEIVABLE.value, entity_id=title_id, limit=100, offset=0)
    return [audit_event_db_to_dict(event) for event in events]


def get_accounts_receivable_diagnostics() -> dict[str, Any]:
    return {
        "module": "accounts_receivable",
        "status": "ready",
        "storage": "database",
        "persistence": "postgresql",
        "id_prefix": "ar",
        "tables": ["financial_titles", "sale_financial_links", "financial_title_history"],
        "integrations": ["sales", "sale_payment_plans", "participants", "financial master data", "cash/settlements", "future reconciliation"],
        "rules": [
            "Pedido fechado pode gerar títulos a receber, mas não é recebimento.",
            "sale_payment_plans é plano previsto; financial_titles é direito financeiro.",
            "Baixa e movimento financeiro ficam no módulo cash; conciliação permanece em bloco posterior.",
            "Título possui vínculo + snapshot da origem e do participante.",
        ],
    }


def get_accounts_receivable_rules() -> dict[str, Any]:
    return {
        "statuses": ["draft", "open", "overdue", "partially_received", "received", "cancelled", "written_off", "renegotiated"],
        "collection_statuses": ["not_started", "scheduled", "reminder_sent", "in_collection", "promised", "disputed", "paused", "closed"],
        "fiscal_statuses": ["pending_document", "linked", "not_required", "divergent"],
        "source_flow": "sales -> sale_payment_plans -> financial_titles -> settlements -> financial_movements -> reconciliation_matches",
        "mvp_scope": ["criação manual", "geração a partir de pedido fechado", "listagem/filtros", "cancelamento", "histórico", "resumo"],
        "out_of_scope_now": ["conciliação bancária", "renegociação completa", "chargeback operacional", "importação automática de extrato"],
    }
