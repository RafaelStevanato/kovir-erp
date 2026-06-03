from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cash.db_models import FinancialMovementDB
from app.modules.company.db_models import CompanyDB
from app.modules.financial.db_models import FinancialAccountDB
from app.modules.financial.period_service import assert_period_open, assert_period_open_range
from app.modules.reconciliation.ofx_parser import OfxParseError, parse_ofx
from app.modules.reconciliation.repository import (
    create_reconciliation_match,
    create_statement_import,
    create_statement_line,
    find_candidate_movements,
    get_active_match_for_line_or_movement,
    get_financial_movement_for_update,
    get_import_by_source,
    get_line_by_external_id,
    get_match,
    get_match_for_update,
    get_statement_line,
    get_statement_line_for_update,
    list_movements_for_reconciliation,
    list_imports as repository_list_imports,
    list_lines as repository_list_lines,
    list_matches as repository_list_matches,
    list_matches_by_statuses,
    movement_candidate_to_dict,
    reconciliation_match_to_dict,
    statement_import_to_dict,
    statement_line_to_dict,
    summary_by_company,
)
from app.modules.reconciliation.schemas import BankStatementImportCreate, IgnoreStatementLine, OfxStatementImportText, ReconciliationMatchCreate, ReverseReconciliationMatch
from app.shared.audit import AuditContext, AuditEntityType, AuditEventType, AuditSource, build_audit_event, build_created_event
from app.shared.audit_repository import create_audit_event
from app.shared.datetime import utc_now
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
    row = db.scalar(select(FinancialAccountDB).where(FinancialAccountDB.id == account_id, FinancialAccountDB.company_id == company_id, FinancialAccountDB.deleted_at.is_(None)))
    if row is None:
        raise ValueError("Conta financeira não encontrada para a empresa.")
    if row.status != "active":
        raise ValueError("Conta financeira precisa estar ativa para conciliação.")
    return row


def import_statement(db: Session, payload: BankStatementImportCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, payload.company_id)
    line_dates = [line.line_date for line in payload.lines]
    min_line_date = min(line_dates) if line_dates else payload.statement_start_date
    max_line_date = max(line_dates) if line_dates else payload.statement_end_date
    assert_period_open_range(
        db,
        company_id=payload.company_id,
        start_date=payload.statement_start_date or min_line_date,
        end_date=payload.statement_end_date or max_line_date,
        operation_label="importação de extrato bancário",
    )
    account = _get_financial_account(db, payload.financial_account_id, company_id=payload.company_id)
    if payload.source_id and get_import_by_source(db, company_id=payload.company_id, financial_account_id=account.id, source_type=payload.source_type, source_id=payload.source_id):
        raise ValueError("Já existe importação de extrato para esta origem.")

    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    total_inflow = sum((_money(line.amount) for line in payload.lines if line.direction == "inflow"), Decimal("0.00"))
    total_outflow = sum((_money(line.amount) for line in payload.lines if line.direction == "outflow"), Decimal("0.00"))

    try:
        row = create_statement_import(
            db,
            id=generate_id("stmtimp"),
            company_id=payload.company_id,
            financial_account_id=account.id,
            source_type=payload.source_type,
            source_id=payload.source_id or generate_id("stmtimp"),
            file_name=payload.file_name,
            statement_start_date=payload.statement_start_date,
            statement_end_date=payload.statement_end_date,
            opening_balance_amount=_money(payload.opening_balance_amount) if payload.opening_balance_amount is not None else None,
            closing_balance_amount=_money(payload.closing_balance_amount) if payload.closing_balance_amount is not None else None,
            line_count=len(payload.lines),
            total_inflow_amount=total_inflow,
            total_outflow_amount=total_outflow,
            status="processed",
            notes=payload.notes,
            raw_payload_json=payload.raw_payload or {},
            created_at=now,
            updated_at=now,
        )
        lines = []
        seen_external_ids: set[str] = set()
        for line in payload.lines:
            if line.external_id:
                if line.external_id in seen_external_ids:
                    raise ValueError(f"External ID duplicado no payload: {line.external_id}")
                seen_external_ids.add(line.external_id)
                existing = get_line_by_external_id(db, company_id=payload.company_id, financial_account_id=account.id, external_id=line.external_id)
                if existing:
                    raise ValueError(f"Linha de extrato já importada para external_id={line.external_id}")
            line_row = create_statement_line(
                db,
                id=generate_id("stmtln"),
                company_id=payload.company_id,
                financial_account_id=account.id,
                statement_import_id=row.id,
                external_id=line.external_id,
                line_date=line.line_date,
                posted_at=None,
                direction=line.direction,
                amount=_money(line.amount),
                description=line.description,
                document_number=line.document_number,
                counterparty_name=line.counterparty_name,
                counterparty_document=line.counterparty_document,
                bank_reference=line.bank_reference,
                status="pending",
                match_confidence=None,
                matched_amount=Decimal("0.00"),
                ignored_reason=None,
                raw_payload_json=line.raw_payload or {},
                created_at=now,
                updated_at=now,
            )
            lines.append(statement_line_to_dict(line_row))
        import_dict = statement_import_to_dict(row)
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.RECONCILIATION_IMPORT, entity_id=row.id, context=context, after=import_dict, expected_entity_prefix="stmtimp"), company_id=payload.company_id)
        db.commit()
        return {"statement_import": import_dict, "lines": lines}
    except Exception:
        db.rollback()
        raise



def import_ofx_statement_text(db: Session, payload: OfxStatementImportText, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    """Importa OFX lido no frontend e transforma as transações em linhas de extrato.

    O OFX é evidência externa. Esta função não cria baixa, não cria movimento
    financeiro e não altera saldo interno. Ela apenas cria bank_statement_imports
    e bank_statement_lines para conciliação posterior.
    """
    try:
        parsed = parse_ofx(payload.ofx_content)
    except OfxParseError as exc:
        raise ValueError(str(exc)) from exc

    lines_payload = [
        {
            "external_id": line.external_id,
            "line_date": line.line_date,
            "direction": line.direction,
            "amount": format(line.amount, "f"),
            "description": line.description,
            "document_number": line.document_number,
            "counterparty_name": line.counterparty_name,
            "bank_reference": line.bank_reference,
            "raw_payload": line.raw_payload,
        }
        for line in parsed.lines
    ]
    import_payload = BankStatementImportCreate(**{
        "company_id": payload.company_id,
        "financial_account_id": payload.financial_account_id,
        "source_type": "ofx",
        "source_id": payload.source_id or parsed.source_id,
        "file_name": payload.file_name or "extrato.ofx",
        "statement_start_date": parsed.statement_start_date,
        "statement_end_date": parsed.statement_end_date,
        "opening_balance_amount": format(parsed.opening_balance_amount, "f") if parsed.opening_balance_amount is not None else None,
        "closing_balance_amount": format(parsed.closing_balance_amount, "f") if parsed.closing_balance_amount is not None else None,
        "notes": payload.notes,
        "raw_payload": {
            "format": "ofx",
            "account_info": parsed.account_info,
            "header": parsed.raw_header,
            "parsed_line_count": len(parsed.lines),
        },
        "lines": lines_payload,
    })
    return import_statement(db, import_payload, actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
def suggest_matches(db: Session, *, company_id: str, statement_line_id: str, day_window: int = 3, limit: int = 10) -> dict[str, Any]:
    _assert_company(db, company_id)
    assert_valid_id(statement_line_id, "stmtln")
    line = get_statement_line(db, statement_line_id)
    if line is None or line.company_id != company_id:
        raise ValueError("Linha de extrato não encontrada para a empresa.")
    if line.status not in {"pending", "divergent"}:
        raise ValueError("Apenas linhas pendentes/divergentes podem receber sugestão de match.")
    candidates = find_candidate_movements(db, company_id=company_id, financial_account_id=line.financial_account_id, direction=line.direction, amount=_money(line.amount), line_date=line.line_date, day_window=day_window, limit=limit)
    return {
        "statement_line": statement_line_to_dict(line),
        "candidates": [movement_candidate_to_dict(row) | {"score": 100 if row.movement_date == line.line_date else 85, "reason": "mesmo valor, direção, conta e data próxima"} for row in candidates],
    }


def confirm_match(db: Session, payload: ReconciliationMatchCreate, *, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, payload.company_id)
    assert_valid_id(payload.statement_line_id, "stmtln")
    assert_valid_id(payload.financial_movement_id, "cash")
    line = get_statement_line_for_update(db, payload.statement_line_id)
    movement = get_financial_movement_for_update(db, payload.financial_movement_id)
    if line is None or line.company_id != payload.company_id:
        raise ValueError("Linha de extrato não encontrada para a empresa.")
    if movement is None or movement.company_id != payload.company_id:
        raise ValueError("Movimento financeiro não encontrado para a empresa.")
    if line.financial_account_id != movement.financial_account_id:
        raise ValueError("Linha de extrato e movimento financeiro pertencem a contas financeiras diferentes.")
    if line.direction != movement.direction:
        raise ValueError("Linha de extrato e movimento financeiro possuem direções diferentes.")
    if line.status not in {"pending", "divergent"}:
        raise ValueError("Linha de extrato não está disponível para conciliação.")
    if movement.status != "posted":
        raise ValueError("Apenas movimentos financeiros postados podem ser conciliados.")
    if movement.reconciliation_status not in {"pending", "divergent"}:
        raise ValueError("Movimento financeiro não está disponível para conciliação.")
    if get_active_match_for_line_or_movement(db, statement_line_id=line.id, financial_movement_id=movement.id):
        raise ValueError("Já existe match ativo para a linha ou para o movimento financeiro.")
    assert_period_open(db, company_id=payload.company_id, event_date=line.line_date, operation_label="confirmação de conciliação (data da linha de extrato)")
    assert_period_open(db, company_id=payload.company_id, event_date=movement.movement_date, operation_label="confirmação de conciliação (data do movimento)")

    tolerance = _money(payload.tolerance_amount)
    line_amount = _money(line.amount)
    movement_amount = _money(movement.amount)
    difference = abs(line_amount - movement_amount)
    if difference > tolerance and not payload.allow_difference:
        raise ValueError("Diferença entre extrato e movimento excede a tolerância informada.")
    if difference > Decimal("0.00") and not payload.confirmation_reason:
        raise ValueError("Conciliação com diferença exige justificativa.")

    now = utc_now()
    status = "confirmed" if difference == Decimal("0.00") else "confirmed_with_difference"
    line_status = "matched" if status == "confirmed" else "divergent"
    movement_status = "matched" if status == "confirmed" else "divergent"
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_line = statement_line_to_dict(line)
    before_movement = {"id": movement.id, "reconciliation_status": movement.reconciliation_status}

    try:
        match = create_reconciliation_match(
            db,
            id=generate_id("recmatch"),
            company_id=payload.company_id,
            financial_account_id=line.financial_account_id,
            statement_line_id=line.id,
            financial_movement_id=movement.id,
            match_type=payload.match_type,
            matched_amount=min(line_amount, movement_amount),
            line_amount=line_amount,
            movement_amount=movement_amount,
            difference_amount=difference,
            tolerance_amount=tolerance,
            status=status,
            confirmation_reason=payload.confirmation_reason,
            reversed_reason=None,
            confirmed_at=now,
            reversed_at=None,
            metadata_json=payload.metadata or {},
            created_at=now,
            updated_at=now,
        )
        line.status = line_status
        line.match_confidence = "exact" if difference == Decimal("0.00") else "forced_difference"
        line.matched_amount = min(line_amount, movement_amount)
        line.updated_at = now
        movement.reconciliation_status = movement_status
        movement.updated_at = now
        db.flush()
        match_dict = reconciliation_match_to_dict(match)
        after_line = statement_line_to_dict(line)
        after_movement = {"id": movement.id, "reconciliation_status": movement.reconciliation_status}
        create_audit_event(db, build_created_event(entity_type=AuditEntityType.RECONCILIATION_MATCH, entity_id=match.id, context=context, after=match_dict, expected_entity_prefix="recmatch"), company_id=payload.company_id)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.RECONCILIATION_LINE, entity_id=line.id, context=context, before=before_line, after=after_line, expected_entity_prefix="stmtln"), company_id=payload.company_id)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=movement.id, context=context, before=before_movement, after=after_movement), company_id=payload.company_id)
        db.commit()
        return {"match": match_dict, "statement_line": after_line, "financial_movement": movement_candidate_to_dict(movement)}
    except Exception:
        db.rollback()
        raise


def reverse_match(db: Session, match_id: str, payload: ReverseReconciliationMatch, *, company_id: str | None = None, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(match_id, "recmatch")
    match = get_match_for_update(db, match_id)
    if match is None:
        raise ValueError("Match de conciliação não encontrado.")
    if company_id is not None and match.company_id != company_id:
        raise ValueError("Match de conciliação não encontrado para a empresa.")
    if match.status == "reversed":
        raise ValueError("Match já está estornado.")
    line = get_statement_line_for_update(db, match.statement_line_id)
    movement = get_financial_movement_for_update(db, match.financial_movement_id)
    if line is None or movement is None:
        raise ValueError("Linha ou movimento vinculado ao match não encontrado.")
    assert_period_open(db, company_id=match.company_id, event_date=line.line_date, operation_label="estorno de conciliação (data da linha de extrato)")
    assert_period_open(db, company_id=match.company_id, event_date=movement.movement_date, operation_label="estorno de conciliação (data do movimento)")
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before_match = reconciliation_match_to_dict(match)
    before_line = statement_line_to_dict(line)
    before_movement = {"id": movement.id, "reconciliation_status": movement.reconciliation_status}
    try:
        match.status = "reversed"
        match.reversed_reason = payload.reason
        match.reversed_at = now
        match.updated_at = now
        line.status = "pending"
        line.match_confidence = None
        line.matched_amount = Decimal("0.00")
        line.updated_at = now
        movement.reconciliation_status = "pending"
        movement.updated_at = now
        db.flush()
        after_match = reconciliation_match_to_dict(match)
        after_line = statement_line_to_dict(line)
        after_movement = {"id": movement.id, "reconciliation_status": movement.reconciliation_status}
        create_audit_event(db, build_audit_event(event_type=AuditEventType.CANCELLED, entity_type=AuditEntityType.RECONCILIATION_MATCH, entity_id=match.id, context=context, before=before_match, after=after_match, metadata={"reason": payload.reason}, expected_entity_prefix="recmatch"), company_id=match.company_id)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.RECONCILIATION_LINE, entity_id=line.id, context=context, before=before_line, after=after_line, expected_entity_prefix="stmtln"), company_id=match.company_id)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.CASH_MOVEMENT, entity_id=movement.id, context=context, before=before_movement, after=after_movement), company_id=match.company_id)
        db.commit()
        return {"match": after_match, "statement_line": after_line, "financial_movement": movement_candidate_to_dict(movement)}
    except Exception:
        db.rollback()
        raise


def ignore_statement_line(db: Session, statement_line_id: str, payload: IgnoreStatementLine, *, company_id: str | None = None, actor_id: str | None = None, source: AuditSource | str = AuditSource.SYSTEM, request_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
    assert_valid_id(statement_line_id, "stmtln")
    line = get_statement_line_for_update(db, statement_line_id)
    if line is None:
        raise ValueError("Linha de extrato não encontrada.")
    if company_id is not None and line.company_id != company_id:
        raise ValueError("Linha de extrato não encontrada para a empresa.")
    if line.status not in {"pending", "divergent"}:
        raise ValueError("Apenas linhas pendentes/divergentes podem ser ignoradas.")
    now = utc_now()
    context = _audit_context(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)
    before = statement_line_to_dict(line)
    try:
        line.status = "ignored"
        line.ignored_reason = payload.reason
        line.updated_at = now
        db.flush()
        after = statement_line_to_dict(line)
        create_audit_event(db, build_audit_event(event_type=AuditEventType.STATUS_CHANGED, entity_type=AuditEntityType.RECONCILIATION_LINE, entity_id=line.id, context=context, before=before, after=after, metadata={"reason": payload.reason}, expected_entity_prefix="stmtln"), company_id=line.company_id)
        db.commit()
        return after
    except Exception:
        db.rollback()
        raise


def list_statement_imports(db: Session, *, company_id: str, financial_account_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_account_id:
        _get_financial_account(db, financial_account_id, company_id=company_id)
    return [statement_import_to_dict(row) for row in repository_list_imports(db, company_id=company_id, financial_account_id=financial_account_id, status=status, limit=limit, offset=offset)]


def list_statement_lines(db: Session, *, company_id: str, financial_account_id: str | None = None, statement_import_id: str | None = None, status: str | None = None, statuses: list[str] | None = None, line_from: Any | None = None, line_to: Any | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_account_id:
        _get_financial_account(db, financial_account_id, company_id=company_id)
    if statement_import_id:
        assert_valid_id(statement_import_id, "stmtimp")
    if status and statuses:
        raise ValueError("Use apenas um filtro de status por vez.")
    if line_from and line_to and line_to < line_from:
        raise ValueError("Data final do filtro não pode ser anterior à data inicial.")
    return [statement_line_to_dict(row) for row in repository_list_lines(db, company_id=company_id, financial_account_id=financial_account_id, statement_import_id=statement_import_id, status=status, statuses=statuses, line_from=line_from, line_to=line_to, q=q, limit=limit, offset=offset)]


def list_reconciliation_matches(db: Session, *, company_id: str, financial_account_id: str | None = None, status: str | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    _assert_company(db, company_id)
    if financial_account_id:
        _get_financial_account(db, financial_account_id, company_id=company_id)
    return [reconciliation_match_to_dict(row) for row in repository_list_matches(db, company_id=company_id, financial_account_id=financial_account_id, status=status, q=q, limit=limit, offset=offset)]


def get_reconciliation_summary(db: Session, *, company_id: str, financial_account_id: str | None = None) -> dict[str, Any]:
    _assert_company(db, company_id)
    if financial_account_id:
        _get_financial_account(db, financial_account_id, company_id=company_id)
    return summary_by_company(db, company_id=company_id, financial_account_id=financial_account_id)


def get_reconciliation_overview_evidence(db: Session, *, company_id: str, financial_account_id: str | None = None, limit: int = 5000, block: str | None = None) -> dict[str, Any]:
    _assert_company(db, company_id)
    if financial_account_id:
        _get_financial_account(db, financial_account_id, company_id=company_id)

    valid_blocks = {
        "pending_statement_lines",
        "pending_financial_movements",
        "confirmed_matches",
        "divergences",
        "ignored_statement_lines",
    }
    if block is not None and block not in valid_blocks:
        raise ValueError("Bloco de evidência de conciliação inválido.")

    def should_load(*keys: str) -> bool:
        return block is None or block in keys

    pending_statement_lines = []
    divergent_statement_lines = []
    ignored_statement_lines = []
    pending_financial_movements = []
    divergent_financial_movements = []
    confirmed_matches = []

    if should_load("pending_statement_lines"):
        pending_statement_lines = [
            statement_line_to_dict(row)
            for row in repository_list_lines(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                status="pending",
                limit=limit,
                offset=0,
            )
        ]

    if should_load("divergences"):
        divergent_statement_lines = [
            statement_line_to_dict(row)
            for row in repository_list_lines(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                status="divergent",
                limit=limit,
                offset=0,
            )
        ]

    if should_load("ignored_statement_lines"):
        ignored_statement_lines = [
            statement_line_to_dict(row)
            for row in repository_list_lines(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                status="ignored",
                limit=limit,
                offset=0,
            )
        ]

    if should_load("pending_financial_movements"):
        pending_financial_movements = [
            movement_candidate_to_dict(row)
            for row in list_movements_for_reconciliation(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                reconciliation_status="pending",
                limit=limit,
                offset=0,
            )
        ]

    if should_load("divergences"):
        divergent_financial_movements = [
            movement_candidate_to_dict(row)
            for row in list_movements_for_reconciliation(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                reconciliation_status="divergent",
                limit=limit,
                offset=0,
            )
        ]

    if should_load("confirmed_matches"):
        confirmed_matches = [
            reconciliation_match_to_dict(row)
            for row in list_matches_by_statuses(
                db,
                company_id=company_id,
                financial_account_id=financial_account_id,
                statuses=["confirmed", "confirmed_with_difference"],
                limit=limit,
                offset=0,
            )
        ]

    return {
        "company_id": company_id,
        "financial_account_id": financial_account_id,
        "summary": summary_by_company(db, company_id=company_id, financial_account_id=financial_account_id),
        "pending_statement_lines": pending_statement_lines,
        "divergent_statement_lines": divergent_statement_lines,
        "ignored_statement_lines": ignored_statement_lines,
        "pending_financial_movements": pending_financial_movements,
        "divergent_financial_movements": divergent_financial_movements,
        "confirmed_matches": confirmed_matches,
    }


def get_reconciliation_diagnostics() -> dict[str, Any]:
    return {
        "module": "reconciliation",
        "status": "ready",
        "storage": "database",
        "persistence": "postgresql",
        "id_prefixes": {"statement_import": "stmtimp", "statement_line": "stmtln", "reconciliation_match": "recmatch"},
        "tables": ["bank_statement_imports", "bank_statement_lines", "reconciliation_matches"],
        "integrations": ["financial_accounts", "financial_movements", "financial_titles", "settlements", "future_external_integrations"],
        "safety": ["extrato não altera saldo interno", "match exige mesma empresa, conta, direção e status", "FOR UPDATE na linha e no movimento ao confirmar", "estorno reabre linha e movimento para conciliação"],
    }


def get_reconciliation_rules() -> dict[str, Any]:
    return {
        "principles": [
            "Movimento interno não é extrato bancário.",
            "Baixa não é conciliação.",
            "Extrato importado é evidência externa; não movimenta saldo sozinho.",
            "Conciliação é o vínculo auditável entre uma linha externa e um movimento financeiro interno.",
            "Diferença de valor exige justificativa e permanece sinalizada como divergente.",
        ],
        "flow": "financial_movements(pending) + bank_statement_lines(pending) -> reconciliation_matches -> status matched/divergent",
        "ofx_support": "Importação OFX básica via conteúdo de arquivo, com leitura de STMTTRN, FITID, DTPOSTED, TRNAMT, NAME, MEMO, REFNUM e CHECKNUM.",
        "out_of_scope_now": ["Open Finance", "CNAB", "Pix real", "match N:N avançado", "fechamento bancário mensal"],
    }
