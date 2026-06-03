from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.accounts_receivable.db_models import FinancialTitleDB
from app.modules.accounts_receivable.repository import create_title_history, get_title_for_update, title_to_dict, update_title_fields
from app.modules.cash.db_models import SettlementDB
from app.modules.cash.repository import (
    balance_to_dict,
    create_balance,
    create_movement,
    create_settlement,
    get_balance_for_update,
    get_movement_for_update,
    get_movement_by_source,
    get_posted_movement_by_settlement_for_update,
    get_reversal_movement_by_original_for_update,
    get_settlement,
    get_settlement_by_source,
    get_settlement_for_update,
    list_balances as repository_list_balances,
    list_movements as repository_list_movements,
    list_settlements as repository_list_settlements,
    movement_to_dict,
    settlement_to_dict,
    summary_by_company,
)
from app.modules.cash.schemas import ManualFinancialMovementCreate, ManualFinancialMovementReverse, SettlementCreate, SettlementReverse
from app.modules.company.db_models import CompanyDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.financial.period_service import assert_period_open
from app.modules.participants.db_models import ParticipantDB
from app.modules.sales.db_models import PaymentMethodDB
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event
from app.shared.audit_repository import create_audit_event
from app.shared.datetime import today_in_brazil, utc_now
from app.shared.ids import assert_valid_id, generate_id

MONEY_QUANT = Decimal("0.01")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _audit_context(actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> AuditContext:
    if isinstance(source, str):
        source = AuditSource(source)
    return AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def _assert_company(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    exists = db.scalar(select(CompanyDB.id).where(CompanyDB.id == company_id, CompanyDB.deleted_at.is_(None)))
    if not exists:
        raise ValueError("Empresa não encontrada.")


def _get_financial_account(db: Session, account_id: str, *, company_id: str) -> FinancialAccountDB:
    assert_valid_id(account_id, "bankacc")
    account = db.scalar(select(FinancialAccountDB).where(FinancialAccountDB.id == account_id, FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None)))
    if account is None:
        raise ValueError("Conta financeira não encontrada para a empresa.")
    if account.status != "active":
        raise ValueError("Conta financeira precisa estar ativa para registrar movimento.")
    return account


def _get_payment_method(db: Session, payment_method_id: str | None, *, company_id: str) -> PaymentMethodDB | None:
    if not payment_method_id:
        return None
    assert_valid_id(payment_method_id, "paym")
    row = db.scalar(select(PaymentMethodDB).where(PaymentMethodDB.id == payment_method_id, PaymentMethodDB.company_id == company_id, PaymentMethodDB.deleted_at.is_(None)))
    if row is None:
        raise ValueError("Forma de pagamento não encontrada para a empresa.")
    if row.status != "active":
        raise ValueError("Forma de pagamento precisa estar ativa para registrar recebimento.")
    return row


def _status_after_settlement(*, due_date: Any, open_amount: Decimal) -> tuple[str, str]:
    if open_amount <= Decimal("0.00"):
        return "received", "closed"
    status = "overdue" if due_date and due_date < today_in_brazil() else "partially_received"
    collection = "in_collection" if status == "overdue" else "not_started"
    return status, collection


def _title_reference_from_row(row: Any) -> str:
    snapshot = row.get("source_snapshot_json") if hasattr(row, "get") else None
    sale_number = snapshot.get("sale_number_text") if isinstance(snapshot, dict) else None
    return str(row.get("document_reference") or sale_number or row.get("sale_id") or row.get("source_id") or row.get("id"))


def _enrich_settlement_rows(db: Session, rows: list[Any]) -> list[dict[str, Any]]:
    if not rows:
        return []

    title_ids = {row.financial_title_id for row in rows if row.financial_title_id}
    titles_by_id: dict[str, Any] = {}
    if title_ids:
        title_rows = db.execute(
            select(
                FinancialTitleDB.id,
                FinancialTitleDB.participant_id,
                FinancialTitleDB.document_reference,
                FinancialTitleDB.sale_id,
                FinancialTitleDB.source_id,
                FinancialTitleDB.source_snapshot_json,
                FinancialTitleDB.installment_number,
                FinancialTitleDB.installment_total,
                FinancialTitleDB.status,
                FinancialTitleDB.open_amount,
                FinancialTitleDB.paid_amount,
            )
            .where(FinancialTitleDB.id.in_(title_ids))
        ).mappings().all()
        titles_by_id = {str(row["id"]): row for row in title_rows}

    participant_ids = {row.participant_id for row in rows if row.participant_id}
    participant_ids.update(str(title["participant_id"]) for title in titles_by_id.values() if title.get("participant_id"))
    participants_by_id: dict[str, Any] = {}
    if participant_ids:
        participant_rows = db.execute(
            select(ParticipantDB.id, ParticipantDB.name, ParticipantDB.document).where(ParticipantDB.id.in_(participant_ids))
        ).mappings().all()
        participants_by_id = {str(row["id"]): row for row in participant_rows}

    enriched: list[dict[str, Any]] = []
    for row in rows:
        data = settlement_to_dict(row)
        title = titles_by_id.get(row.financial_title_id)
        participant_id = row.participant_id
        if title is not None:
            participant_id = participant_id or title.get("participant_id")
            data.update(
                {
                    "financial_title_reference": _title_reference_from_row(title),
                    "financial_title_status": title.get("status"),
                    "financial_title_installment_number": title.get("installment_number"),
                    "financial_title_installment_total": title.get("installment_total"),
                    "financial_title_open_amount": format(_money(title.get("open_amount")), "f"),
                    "financial_title_paid_amount": format(_money(title.get("paid_amount")), "f"),
                }
            )
        participant = participants_by_id.get(str(participant_id)) if participant_id else None
        if participant is not None:
            data["participant_name"] = participant.get("name")
            data["participant_document"] = participant.get("document")
        enriched.append(data)
    return enriched


def _enrich_movement_rows(db: Session, rows: list[Any]) -> list[dict[str, Any]]:
    if not rows:
        return []

    account_ids = {row.financial_account_id for row in rows if row.financial_account_id}
    title_ids = {row.financial_title_id for row in rows if row.financial_title_id}
    participant_ids = {row.participant_id for row in rows if row.participant_id}
    settlement_ids = {row.settlement_id for row in rows if row.settlement_id}

    accounts_by_id: dict[str, Any] = {}
    if account_ids:
        account_rows = db.execute(
            select(
                FinancialAccountDB.id,
                FinancialAccountDB.name,
                FinancialAccountDB.account_type,
                FinancialAccountDB.institution_name,
            )
            .where(FinancialAccountDB.id.in_(account_ids))
        ).mappings().all()
        accounts_by_id = {str(row["id"]): row for row in account_rows}

    titles_by_id: dict[str, Any] = {}
    if title_ids:
        title_rows = db.execute(
            select(
                FinancialTitleDB.id,
                FinancialTitleDB.direction,
                FinancialTitleDB.participant_id,
                FinancialTitleDB.document_reference,
                FinancialTitleDB.sale_id,
                FinancialTitleDB.source_id,
                FinancialTitleDB.source_snapshot_json,
                FinancialTitleDB.installment_number,
                FinancialTitleDB.installment_total,
                FinancialTitleDB.status,
                FinancialTitleDB.open_amount,
                FinancialTitleDB.paid_amount,
            )
            .where(FinancialTitleDB.id.in_(title_ids))
        ).mappings().all()
        titles_by_id = {str(row["id"]): row for row in title_rows}
        participant_ids.update(str(title["participant_id"]) for title in titles_by_id.values() if title.get("participant_id"))

    settlements_by_id: dict[str, Any] = {}
    payment_method_ids: set[str] = set()
    if settlement_ids:
        settlement_rows = db.execute(
            select(
                SettlementDB.id,
                SettlementDB.status,
                SettlementDB.settlement_type,
                SettlementDB.settlement_date,
                SettlementDB.evidence_reference,
                SettlementDB.payment_method_id,
            )
            .where(SettlementDB.id.in_(settlement_ids))
        ).mappings().all()
        settlements_by_id = {str(row["id"]): row for row in settlement_rows}
        payment_method_ids.update(str(row["payment_method_id"]) for row in settlement_rows if row.get("payment_method_id"))

    payment_methods_by_id: dict[str, Any] = {}
    if payment_method_ids:
        payment_method_rows = db.execute(
            select(PaymentMethodDB.id, PaymentMethodDB.name, PaymentMethodDB.code).where(PaymentMethodDB.id.in_(payment_method_ids))
        ).mappings().all()
        payment_methods_by_id = {str(row["id"]): row for row in payment_method_rows}

    participants_by_id: dict[str, Any] = {}
    if participant_ids:
        participant_rows = db.execute(
            select(ParticipantDB.id, ParticipantDB.name, ParticipantDB.document).where(ParticipantDB.id.in_(participant_ids))
        ).mappings().all()
        participants_by_id = {str(row["id"]): row for row in participant_rows}

    enriched: list[dict[str, Any]] = []
    for row in rows:
        data = movement_to_dict(row)
        account = accounts_by_id.get(row.financial_account_id)
        if account is not None:
            data["financial_account_name"] = account.get("name")
            data["financial_account_type"] = account.get("account_type")
            data["financial_account_institution_name"] = account.get("institution_name")

        title = titles_by_id.get(row.financial_title_id) if row.financial_title_id else None
        participant_id = row.participant_id
        if title is not None:
            participant_id = participant_id or title.get("participant_id")
            data.update(
                {
                    "financial_title_reference": _title_reference_from_row(title),
                    "financial_title_direction": title.get("direction"),
                    "financial_title_status": title.get("status"),
                    "financial_title_installment_number": title.get("installment_number"),
                    "financial_title_installment_total": title.get("installment_total"),
                    "financial_title_open_amount": format(_money(title.get("open_amount")), "f"),
                    "financial_title_paid_amount": format(_money(title.get("paid_amount")), "f"),
                }
            )

        participant = participants_by_id.get(str(participant_id)) if participant_id else None
        if participant is not None:
            data["participant_name"] = participant.get("name")
            data["participant_document"] = participant.get("document")

        settlement = settlements_by_id.get(row.settlement_id) if row.settlement_id else None
        if settlement is not None:
            payment_method = payment_methods_by_id.get(str(settlement.get("payment_method_id"))) if settlement.get("payment_method_id") else None
            data.update(
                {
                    "settlement_status": settlement.get("status"),
                    "settlement_type": settlement.get("settlement_type"),
                    "settlement_date": settlement.get("settlement_date").isoformat() if settlement.get("settlement_date") is not None else None,
                    "settlement_evidence_reference": settlement.get("evidence_reference"),
                    "payment_method_id": settlement.get("payment_method_id"),
                    "payment_method_name": payment_method.get("name") if payment_method is not None else None,
                    "payment_method_code": payment_method.get("code") if payment_method is not None else None,
                }
            )
        enriched.append(data)
    return enriched


def _ensure_balance(db: Session, *, company_id: str, financial_account: FinancialAccountDB, now: Any):
    balance = get_balance_for_update(db, company_id=company_id, financial_account_id=financial_account.id)
    if balance is not None:
        return balance
    return create_balance(
        db,
        id=generate_id("cashbal"),
        company_id=company_id,
        financial_account_id=financial_account.id,
        current_balance_amount=_money(financial_account.opening_balance_amount),
        last_movement_id=None,
        updated_at=now,
    )


def _apply_account_delta(db: Session, *, company_id: str, financial_account: FinancialAccountDB, delta: Decimal, movement_id: str, now: Any) -> dict[str, Any]:
    balance = _ensure_balance(db, company_id=company_id, financial_account=financial_account, now=now)
    balance.current_balance_amount = _money(balance.current_balance_amount) + _money(delta)
    balance.last_movement_id = movement_id
    balance.updated_at = now
    db.flush()
    return balance_to_dict(balance)


def receive_title(db: Session, payload: SettlementCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, payload.company_id)
    assert_period_open(db, company_id=payload.company_id, event_date=payload.settlement_date, operation_label="registro de baixa/recebimento")
    assert_period_open(db, company_id=payload.company_id, event_date=payload.competency_date, operation_label="registro de competência da baixa/recebimento")
    assert_valid_id(payload.financial_title_id, "ar")
    account = _get_financial_account(db, payload.financial_account_id, company_id=payload.company_id)
    payment_method = _get_payment_method(db, payload.payment_method_id, company_id=payload.company_id)

    if payload.source_id and get_settlement_by_source(db, company_id=payload.company_id, source_type=payload.source_type, source_id=payload.source_id):
        raise ValueError("Já existe baixa/recebimento para esta origem.")

    title = get_title_for_update(db, payload.financial_title_id)
    if title is None or title.company_id != payload.company_id or title.direction != "receivable":
        raise ValueError("Título a receber não encontrado para a empresa.")
    if title.status in {"cancelled", "received", "written_off"}:
        raise ValueError("Título encerrado não pode receber nova baixa.")

    received = _money(payload.received_amount)
    discount = _money(payload.discount_amount)
    interest = _money(payload.interest_amount)
    penalty = _money(payload.penalty_amount)
    fee = _money(payload.fee_amount)
    title_effect = received + discount
    movement_amount = received + interest + penalty - fee
    if title_effect <= Decimal("0.00"):
        raise ValueError("Baixa precisa reduzir o saldo do título.")
    if movement_amount < Decimal("0.00"):
        raise ValueError("Movimento financeiro não pode ficar negativo.")
    if title_effect > _money(title.open_amount):
        raise ValueError("Valor da baixa excede o saldo em aberto do título.")

    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_title = title_to_dict(title)

    try:
        settlement = create_settlement(
            db,
            id=generate_id("sett"),
            company_id=payload.company_id,
            direction="inflow",
            settlement_type="receipt",
            financial_title_id=title.id,
            participant_id=title.participant_id,
            financial_account_id=account.id,
            payment_method_id=payment_method.id if payment_method is not None else payload.payment_method_id,
            settlement_date=payload.settlement_date,
            competency_date=payload.competency_date,
            received_amount=received,
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
            direction="inflow",
            movement_type="receipt",
            movement_date=payload.settlement_date,
            amount=movement_amount,
            currency=account.currency or "BRL",
            source_type="settlement",
            source_id=settlement.id,
            settlement_id=settlement.id,
            financial_title_id=title.id,
            participant_id=title.participant_id,
            description=f"Recebimento do título {title.id}",
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=None,
            metadata_json={"settlement_id": settlement.id, "title_id": title.id},
            created_at=now,
            updated_at=now,
        )
        balance = _apply_account_delta(db, company_id=payload.company_id, financial_account=account, delta=movement_amount, movement_id=movement.id, now=now)

        new_paid = _money(title.paid_amount) + received
        new_open = _money(title.open_amount) - title_effect
        status, collection_status = _status_after_settlement(due_date=title.due_date, open_amount=new_open)
        update_title_fields(title, paid_amount=new_paid, open_amount=new_open, status=status, collection_status=collection_status, updated_at=now)
        create_title_history(db, id=generate_id("arhist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before_title["status"], new_status=status, previous_collection_status=before_title["collection_status"], new_collection_status=collection_status, reason="Baixa/recebimento registrado.", source=context.source.value, actor_id=context.actor_id, occurred_at=now)

        after_title = title_to_dict(title)
        settlement_dict = settlement_to_dict(settlement)
        movement_dict = movement_to_dict(movement)
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=movement.id, context=context, after=movement_dict), company_id=payload.company_id)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, before=before_title, after=after_title, metadata={"settlement_id": settlement.id, "movement_id": movement.id}), company_id=payload.company_id)
        db.commit()
        return {"settlement": settlement_dict, "movement": movement_dict, "title": after_title, "balance": balance}
    except Exception:
        db.rollback()
        raise


def reverse_settlement(db: Session, settlement_id: str, payload: SettlementReverse, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(settlement_id, "sett")
    settlement = get_settlement_for_update(db, settlement_id)
    if settlement is None:
        raise ValueError("Baixa/recebimento não encontrado.")
    if settlement.status != "active":
        raise ValueError("Baixa/recebimento não está ativo para estorno.")
    title = get_title_for_update(db, settlement.financial_title_id)
    if title is None:
        raise ValueError("Título vinculado à baixa não encontrado.")
    account = _get_financial_account(db, settlement.financial_account_id, company_id=settlement.company_id)
    original_movement = get_posted_movement_by_settlement_for_update(db, settlement.id)
    if original_movement is None:
        raise ValueError("Movimento financeiro vinculado à baixa não encontrado.")
    if original_movement.reconciliation_status in {"matched", "divergent"}:
        raise ValueError("Baixa já conciliada. Estorne o match de conciliação antes de estornar a baixa.")
    assert_period_open(db, company_id=settlement.company_id, event_date=today_in_brazil(), operation_label="estorno de baixa/recebimento")
    assert_period_open(db, company_id=settlement.company_id, event_date=settlement.settlement_date, operation_label="estorno de baixa em período fechado")
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_title = title_to_dict(title)
    before_settlement = settlement_to_dict(settlement)
    before_movement = movement_to_dict(original_movement)

    try:
        settlement.status = "reversed"
        settlement.reversed_at = now
        settlement.updated_at = now
        settlement.metadata_json = {**(settlement.metadata_json or {}), "reverse_reason": payload.reason}

        original_movement.reconciliation_status = "reversed"
        original_movement.updated_at = now
        reversal_movement = create_movement(
            db,
            id=generate_id("cash"),
            company_id=settlement.company_id,
            financial_account_id=account.id,
            direction="outflow" if original_movement.direction == "inflow" else "inflow",
            movement_type="reversal",
            movement_date=today_in_brazil(),
            amount=_money(settlement.movement_amount),
            currency=account.currency or "BRL",
            source_type="settlement_reversal",
            source_id=settlement.id,
            settlement_id=settlement.id,
            financial_title_id=title.id,
            participant_id=title.participant_id,
            description=f"Estorno do movimento {original_movement.id} da baixa {settlement.id}",
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=original_movement.id,
            metadata_json={"settlement_id": settlement.id, "reversal_reason": payload.reason},
            created_at=now,
            updated_at=now,
        )
        balance = _apply_account_delta(
            db,
            company_id=settlement.company_id,
            financial_account=account,
            delta=-_money(settlement.movement_amount),
            movement_id=reversal_movement.id,
            now=now,
        )
        db.flush()

        new_paid = _money(title.paid_amount) - _money(settlement.received_amount)
        if new_paid < Decimal("0.00"):
            raise ValueError("Estorno deixaria o valor recebido do título negativo.")
        new_open = _money(title.open_amount) + _money(settlement.title_settled_amount)
        status = "overdue" if title.due_date and title.due_date < today_in_brazil() else "open"
        if new_paid > Decimal("0.00"):
            status = "partially_received"
        collection = "in_collection" if status == "overdue" else "not_started"
        update_title_fields(title, paid_amount=new_paid, open_amount=new_open, status=status, collection_status=collection, updated_at=now)
        create_title_history(db, id=generate_id("arhist"), company_id=title.company_id, financial_title_id=title.id, previous_status=before_title["status"], new_status=status, previous_collection_status=before_title["collection_status"], new_collection_status=collection, reason=f"Estorno de baixa: {payload.reason}", source=context.source.value, actor_id=context.actor_id, occurred_at=now)

        after_title = title_to_dict(title)
        after_settlement = settlement_to_dict(settlement)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=settlement.id, context=context, before=before_settlement, after=after_settlement, metadata={"reason": payload.reason}, expected_entity_prefix="sett"), company_id=settlement.company_id)
        create_audit_event(
            db,
            build_audit_event(
                event_type=AuditEventType.CANCELLED,
                entity_type=AuditEntityType.CASH_MOVEMENT,
                entity_id=original_movement.id,
                context=context,
                before=before_movement,
                after=movement_to_dict(original_movement),
                metadata={"reason": payload.reason, "reversed_settlement_id": settlement.id},
                expected_entity_prefix="cash",
            ),
            company_id=settlement.company_id,
        )
        create_audit_event(
            db,
            build_created_event(
                entity_type=AuditEntityType.CASH_MOVEMENT,
                entity_id=reversal_movement.id,
                context=context,
                after=movement_to_dict(reversal_movement),
            ),
            company_id=settlement.company_id,
        )
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.ACCOUNT_RECEIVABLE, entity_id=title.id, context=context, before=before_title, after=after_title, metadata={"reversed_settlement_id": settlement.id}), company_id=settlement.company_id)
        db.commit()
        return {
            "settlement": after_settlement,
            "reversed_movement_id": original_movement.id,
            "reversal_movement": movement_to_dict(reversal_movement),
            "title": after_title,
            "balance": balance,
        }
    except IntegrityError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

def create_manual_movement(db: Session, payload: ManualFinancialMovementCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, payload.company_id)
    assert_period_open(db, company_id=payload.company_id, event_date=payload.movement_date, operation_label="lançamento manual de movimento financeiro")
    account = _get_financial_account(db, payload.financial_account_id, company_id=payload.company_id)
    if payload.source_id and get_movement_by_source(db, company_id=payload.company_id, source_type=payload.source_type, source_id=payload.source_id):
        raise ValueError("Já existe movimento financeiro para esta origem.")
    amount = _money(payload.amount)
    delta = amount if payload.direction == "inflow" else -amount
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    try:
        movement = create_movement(
            db,
            id=generate_id("cash"),
            company_id=payload.company_id,
            financial_account_id=account.id,
            direction=payload.direction,
            movement_type=payload.movement_type,
            movement_date=payload.movement_date,
            amount=amount,
            currency=account.currency or "BRL",
            source_type=payload.source_type,
            source_id=payload.source_id or generate_id("cash"),
            settlement_id=None,
            financial_title_id=None,
            participant_id=None,
            description=payload.description,
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=None,
            metadata_json=payload.metadata or {},
            created_at=now,
            updated_at=now,
        )
        balance = _apply_account_delta(db, company_id=payload.company_id, financial_account=account, delta=delta, movement_id=movement.id, now=now)
        movement_dict = movement_to_dict(movement)
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=movement.id, context=context, after=movement_dict), company_id=payload.company_id)
        db.commit()
        return {"movement": movement_dict, "balance": balance}
    except Exception:
        db.rollback()
        raise


def reverse_manual_movement(db: Session, movement_id: str, payload: ManualFinancialMovementReverse, *, company_id: str, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(movement_id, "cash")
    movement = get_movement_for_update(db, movement_id)
    if movement is None or movement.company_id != company_id:
        raise ValueError("Movimento financeiro não encontrado para a empresa.")
    if movement.status != "posted":
        raise ValueError("Movimento financeiro não está postado para estorno.")
    if movement.reconciliation_status in {"matched", "divergent"}:
        raise ValueError("Movimento financeiro já conciliado/divergente. Estorne o match de conciliação antes de estornar o movimento.")
    if movement.reconciliation_status == "reversed":
        raise ValueError("Movimento financeiro já foi estornado.")
    if movement.reversal_of_movement_id:
        raise ValueError("Movimento de estorno não pode ser estornado por esta rotina.")
    if movement.source_type != "manual" or movement.settlement_id or movement.financial_title_id:
        raise ValueError("Somente movimento manual sem título/baixa vinculada pode ser estornado por esta rotina.")
    existing_reversal = get_reversal_movement_by_original_for_update(db, movement.id)
    if existing_reversal is not None:
        raise ValueError("Já existe movimento de estorno para este lançamento manual.")

    account = _get_financial_account(db, movement.financial_account_id, company_id=movement.company_id)
    assert_period_open(db, company_id=movement.company_id, event_date=today_in_brazil(), operation_label="estorno de movimento manual")
    assert_period_open(db, company_id=movement.company_id, event_date=movement.movement_date, operation_label="estorno de movimento manual em período fechado")

    amount = _money(movement.amount)
    delta = -amount if movement.direction == "inflow" else amount
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_movement = movement_to_dict(movement)

    try:
        movement.status = "reversed"
        movement.reconciliation_status = "reversed"
        movement.updated_at = now
        movement.metadata_json = {**(movement.metadata_json or {}), "reverse_reason": payload.reason}

        reversal_movement = create_movement(
            db,
            id=generate_id("cash"),
            company_id=movement.company_id,
            financial_account_id=account.id,
            direction="outflow" if movement.direction == "inflow" else "inflow",
            movement_type="reversal",
            movement_date=today_in_brazil(),
            amount=amount,
            currency=account.currency or "BRL",
            source_type="manual_reversal",
            source_id=movement.id,
            settlement_id=None,
            financial_title_id=None,
            participant_id=None,
            description=f"Estorno do movimento manual {movement.id}",
            status="posted",
            reconciliation_status="pending",
            reversal_of_movement_id=movement.id,
            metadata_json={"reversal_reason": payload.reason, "reversed_movement_id": movement.id},
            created_at=now,
            updated_at=now,
        )
        balance = _apply_account_delta(db, company_id=movement.company_id, financial_account=account, delta=delta, movement_id=reversal_movement.id, now=now)
        after_movement = movement_to_dict(movement)
        reversal_dict = movement_to_dict(reversal_movement)

        create_audit_event(
            db,
            build_audit_event(
                event_type=AuditEventType.CANCELLED,
                entity_type=AuditEntityType.CASH_MOVEMENT,
                entity_id=movement.id,
                context=context,
                before=before_movement,
                after=after_movement,
                metadata={"reason": payload.reason, "reversal_movement_id": reversal_movement.id},
            ),
            company_id=movement.company_id,
        )
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=reversal_movement.id, context=context, after=reversal_dict), company_id=movement.company_id)
        db.commit()
        return {"movement": after_movement, "reversed_movement_id": movement.id, "reversal_movement": reversal_dict, "balance": balance}
    except Exception:
        db.rollback()
        raise


def list_settlements(db: Session, *, company_id: str, financial_title_id: str | None = None, financial_account_id: str | None = None, payment_method_id: str | None = None, status: str | None = None, settlement_from: Any | None = None, settlement_to: Any | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_title_id:
        assert_valid_id(financial_title_id, "ar")
    if financial_account_id:
        assert_valid_id(financial_account_id, "bankacc")
    if payment_method_id and payment_method_id != "__none__":
        assert_valid_id(payment_method_id, "paym")
    rows = repository_list_settlements(db, company_id=company_id, financial_title_id=financial_title_id, financial_account_id=financial_account_id, payment_method_id=payment_method_id, status=status, settlement_from=settlement_from, settlement_to=settlement_to, q=q, limit=limit, offset=offset)
    return _enrich_settlement_rows(db, rows)


def list_movements(db: Session, *, company_id: str, financial_account_id: str | None = None, direction: str | None = None, movement_type: str | None = None, status: str | None = None, reconciliation_status: str | None = None, movement_from: Any | None = None, movement_to: Any | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_account_id:
        assert_valid_id(financial_account_id, "bankacc")
    if direction and direction not in {"inflow", "outflow"}:
        raise ValueError("Direção do movimento financeiro inválida.")
    rows = repository_list_movements(db, company_id=company_id, financial_account_id=financial_account_id, direction=direction, movement_type=movement_type, status=status, reconciliation_status=reconciliation_status, movement_from=movement_from, movement_to=movement_to, q=q, limit=limit, offset=offset)
    return _enrich_movement_rows(db, rows)


def list_account_balances(db: Session, *, company_id: str, financial_account_id: str | None = None) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_account_id:
        assert_valid_id(financial_account_id, "bankacc")
    return [balance_to_dict(row) for row in repository_list_balances(db, company_id=company_id, financial_account_id=financial_account_id)]


def get_settlement_detail(db: Session, settlement_id: str) -> dict[str, Any]:
    assert_valid_id(settlement_id, "sett")
    row = get_settlement(db, settlement_id)
    if row is None:
        raise ValueError("Baixa/recebimento não encontrado.")
    return settlement_to_dict(row)


def get_cash_summary(db: Session, *, company_id: str) -> dict[str, Any]:
    _assert_company(db, company_id)
    return summary_by_company(db, company_id=company_id)


def get_cash_diagnostics() -> dict[str, Any]:
    return {
        "module": "cash",
        "status": "ready",
        "storage": "database",
        "persistence": "postgresql",
        "id_prefixes": {"settlement": "sett", "financial_movement": "cash", "account_balance": "cashbal"},
        "tables": ["settlements", "financial_movements", "financial_account_balances"],
        "integrations": ["financial_titles", "financial_accounts", "payment_methods", "participants", "future_reconciliation"],
        "safety": ["título a receber com SELECT FOR UPDATE", "saldo interno por conta com SELECT FOR UPDATE", "estorno remove movimento da baixa original", "conciliação não é marcada automaticamente"],
    }


def get_cash_rules() -> dict[str, Any]:
    return {
        "principles": [
            "Venda não é recebimento.",
            "Título a receber não é dinheiro no banco.",
            "Baixa reduz saldo em aberto do título, mas conciliação fica pendente.",
            "Movimento financeiro interno altera saldo interno da conta financeira.",
            "Estorno marca baixa como reversa, remove o movimento financeiro da baixa e reabre o título quando aplicável.",
        ],
        "flows": {
            "receipt": "financial_titles -> settlements -> financial_movements -> financial_account_balances -> future reconciliation_matches",
            "reversal": "settlements.status=reversed + delete financial_movement(settlement) + title reopened/partial",
        },
        "out_of_scope_now": ["importação de extrato", "match bancário", "CNAB", "Pix real", "gateway automático", "fechamento de caixa"],
    }
