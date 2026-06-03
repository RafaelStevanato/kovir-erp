from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.company.repository import get_company as repository_get_company
from app.modules.financial.db_models import (
    ChartAccountDB,
    CostCenterDB,
    FinancialAccountDB,
    FinancialCategoryDB,
    PaymentTermDB,
)
from app.modules.financial.repository import (
    add_row,
    chart_account_db_to_dict,
    cost_center_db_to_dict,
    count_rows,
    financial_account_db_to_dict,
    financial_category_db_to_dict,
    get_by_company_code,
    get_by_id,
    get_payment_term_by_company_name,
    list_rows,
    payment_term_db_to_dict,
)
from app.modules.financial.schemas import (
    ChartAccountCreate,
    ChartAccountUpdate,
    CostCenterCreate,
    CostCenterUpdate,
    FinancialAccountCreate,
    FinancialAccountUpdate,
    FinancialCategoryCreate,
    FinancialCategoryUpdate,
    PaymentTermCreate,
    PaymentTermUpdate,
)
from app.shared.audit import AuditContext, AuditEntityType, AuditSource, build_created_event, build_updated_event
from app.shared.audit_repository import audit_event_db_to_dict, create_audit_event, list_audit_events_for_entity
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id

FinancialDB = TypeVar("FinancialDB", ChartAccountDB, FinancialCategoryDB, CostCenterDB, FinancialAccountDB, PaymentTermDB)

ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "chart_accounts": {
        "model": ChartAccountDB,
        "prefix": "acc",
        "to_dict": chart_account_db_to_dict,
        "entity_type": AuditEntityType.CHART_ACCOUNT,
        "label": "Conta do plano de contas",
    },
    "financial_categories": {
        "model": FinancialCategoryDB,
        "prefix": "cat",
        "to_dict": financial_category_db_to_dict,
        "entity_type": AuditEntityType.FINANCIAL_CATEGORY,
        "label": "Categoria financeira",
    },
    "cost_centers": {
        "model": CostCenterDB,
        "prefix": "cc",
        "to_dict": cost_center_db_to_dict,
        "entity_type": AuditEntityType.COST_CENTER,
        "label": "Centro de custo",
    },
    "financial_accounts": {
        "model": FinancialAccountDB,
        "prefix": "bankacc",
        "to_dict": financial_account_db_to_dict,
        "entity_type": AuditEntityType.FINANCIAL_ACCOUNT,
        "label": "Conta financeira",
    },
    "payment_terms": {
        "model": PaymentTermDB,
        "prefix": "term",
        "to_dict": payment_term_db_to_dict,
        "entity_type": AuditEntityType.PAYMENT_TERM,
        "label": "Condição de pagamento",
    },
}

CASH_FLOW_GROUPS = {
    "operating_inflows",
    "operating_outflows",
    "investing_inflows",
    "investing_outflows",
    "financing_inflows",
    "financing_outflows",
    "transfers",
}


def _audit_context(
    actor_id: str | None = None,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> AuditContext:
    return AuditContext(actor_id=actor_id, source=source, request_id=request_id, correlation_id=correlation_id)


def _assert_company_exists(db: Session, company_id: str) -> None:
    assert_valid_id(company_id, "emp")
    if repository_get_company(db, company_id) is None:
        raise ValueError("Empresa não encontrada.")


def _assert_same_company(row: Any | None, company_id: str, label: str) -> None:
    if row is None:
        raise ValueError(f"{label} não encontrado.")
    if row.company_id != company_id:
        raise ValueError(f"{label} pertence a outra empresa.")
    if getattr(row, "status", None) in {"inactive", "blocked", "archived"}:
        raise ValueError(f"{label} não está ativo para novos vínculos.")


def _assert_chart_parent_can_receive_child(row: ChartAccountDB) -> None:
    if row.is_analytical or row.accepts_entries:
        raise ValueError("Conta pai do plano de contas deve ser sintética e não aceitar lançamento direto.")


def _assert_chart_account_can_classify_category(row: ChartAccountDB) -> None:
    if not row.is_analytical or not row.accepts_entries:
        raise ValueError("Categoria financeira deve apontar para conta analítica ativa que aceita lançamento direto.")


def _assert_cost_center_parent_can_receive_child(row: CostCenterDB) -> None:
    if row.is_analytical:
        raise ValueError("Centro de custo pai deve ser sintetico.")


def _chart_account_has_children(db: Session, account_id: str, company_id: str, *, active_only: bool = False) -> bool:
    statement = (
        select(ChartAccountDB.id)
        .where(ChartAccountDB.company_id == company_id)
        .where(ChartAccountDB.parent_id == account_id)
        .limit(1)
    )
    if active_only:
        statement = statement.where(ChartAccountDB.status == "active")
    return db.scalar(statement) is not None


def _chart_account_has_active_category(db: Session, account_id: str, company_id: str) -> bool:
    statement = (
        select(FinancialCategoryDB.id)
        .where(FinancialCategoryDB.company_id == company_id)
        .where(FinancialCategoryDB.chart_account_id == account_id)
        .where(FinancialCategoryDB.status == "active")
        .limit(1)
    )
    return db.scalar(statement) is not None


def _assert_chart_account_no_cycle(db: Session, row: ChartAccountDB, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == row.id:
        raise ValueError("Conta do plano de contas não pode ser pai dela mesma.")

    visited = {row.id}
    current_parent_id = parent_id
    while current_parent_id:
        if current_parent_id in visited:
            raise ValueError("Hierarquia do plano de contas não pode formar ciclo.")
        visited.add(current_parent_id)
        parent = get_by_id(db, ChartAccountDB, current_parent_id)
        if parent is None:
            raise ValueError("Conta pai não encontrada.")
        if parent.company_id != row.company_id:
            raise ValueError("Conta pai pertence a outra empresa.")
        current_parent_id = parent.parent_id


def _assert_chart_account_update_rules(db: Session, row: ChartAccountDB, data: dict[str, Any]) -> None:
    parent_id = data["parent_id"] if "parent_id" in data else row.parent_id
    is_analytical = data["is_analytical"] if "is_analytical" in data else row.is_analytical
    accepts_entries = data["accepts_entries"] if "accepts_entries" in data else row.accepts_entries
    status = data["status"] if "status" in data else row.status

    if not is_analytical and accepts_entries:
        raise ValueError("Conta sintética não deve receber lançamento direto.")

    _assert_chart_account_no_cycle(db, row, parent_id)

    if _chart_account_has_children(db, row.id, row.company_id) and (is_analytical or accepts_entries):
        raise ValueError("Conta com contas filhas deve permanecer sintética e sem lançamento direto.")

    if status in {"inactive", "blocked", "archived"}:
        if _chart_account_has_active_category(db, row.id, row.company_id):
            raise ValueError("Conta vinculada a categoria financeira ativa não pode ser inativada, bloqueada ou arquivada.")
        if _chart_account_has_children(db, row.id, row.company_id, active_only=True):
            raise ValueError("Conta com contas filhas ativas não pode ser inativada, bloqueada ou arquivada.")


def _financial_category_has_children(db: Session, category_id: str, company_id: str, *, active_only: bool = False) -> bool:
    statement = (
        select(FinancialCategoryDB.id)
        .where(FinancialCategoryDB.company_id == company_id)
        .where(FinancialCategoryDB.parent_id == category_id)
        .limit(1)
    )
    if active_only:
        statement = statement.where(FinancialCategoryDB.status == "active")
    return db.scalar(statement) is not None


def _financial_category_has_active_title(db: Session, category_id: str, company_id: str) -> bool:
    from app.modules.accounts_receivable.db_models import FinancialTitleDB

    active_statuses = {"draft", "open", "overdue", "partially_received", "partially_paid", "renegotiated"}
    statement = (
        select(FinancialTitleDB.id)
        .where(FinancialTitleDB.company_id == company_id)
        .where(FinancialTitleDB.financial_category_id == category_id)
        .where(FinancialTitleDB.deleted_at.is_(None))
        .where(FinancialTitleDB.status.in_(active_statuses))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_category_has_active_purchase(db: Session, category_id: str, company_id: str) -> bool:
    from app.modules.purchases_payables.db_models import PurchaseDB

    statement = (
        select(PurchaseDB.id)
        .where(PurchaseDB.company_id == company_id)
        .where(PurchaseDB.financial_category_id == category_id)
        .where(PurchaseDB.deleted_at.is_(None))
        .where(PurchaseDB.status.in_({"draft", "confirmed"}))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _assert_financial_category_no_cycle(db: Session, row: FinancialCategoryDB, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == row.id:
        raise ValueError("Categoria financeira não pode ser pai dela mesma.")

    visited = {row.id}
    current_parent_id = parent_id
    while current_parent_id:
        if current_parent_id in visited:
            raise ValueError("Hierarquia de categorias financeiras não pode formar ciclo.")
        visited.add(current_parent_id)
        parent = get_by_id(db, FinancialCategoryDB, current_parent_id)
        if parent is None:
            raise ValueError("Categoria pai não encontrada.")
        if parent.company_id != row.company_id:
            raise ValueError("Categoria pai pertence a outra empresa.")
        current_parent_id = parent.parent_id


def _assert_category_cash_flow_rules(affects_cash_flow: bool, cash_flow_group: str | None) -> None:
    if affects_cash_flow:
        if not cash_flow_group:
            raise ValueError("Categoria que afeta fluxo de caixa deve informar grupo de fluxo.")
        if cash_flow_group not in CASH_FLOW_GROUPS:
            raise ValueError("Grupo de fluxo de caixa inválido para categoria financeira.")
        return
    if cash_flow_group:
        raise ValueError("Categoria que não afeta fluxo de caixa não deve informar grupo de fluxo.")


def _assert_financial_category_update_rules(db: Session, row: FinancialCategoryDB, data: dict[str, Any]) -> None:
    parent_id = data["parent_id"] if "parent_id" in data else row.parent_id
    status = data["status"] if "status" in data else row.status
    affects_cash_flow = data["affects_cash_flow"] if "affects_cash_flow" in data else row.affects_cash_flow
    cash_flow_group = data["cash_flow_group"] if "cash_flow_group" in data else row.cash_flow_group

    _assert_financial_category_no_cycle(db, row, parent_id)
    _assert_category_cash_flow_rules(affects_cash_flow, cash_flow_group)

    if status in {"inactive", "blocked", "archived"}:
        if _financial_category_has_children(db, row.id, row.company_id, active_only=True):
            raise ValueError("Categoria com subcategorias ativas não pode ser inativada, bloqueada ou arquivada.")
        if _financial_category_has_active_title(db, row.id, row.company_id):
            raise ValueError("Categoria vinculada a título financeiro ativo não pode ser inativada, bloqueada ou arquivada.")
        if _financial_category_has_active_purchase(db, row.id, row.company_id):
            raise ValueError("Categoria vinculada a compra/despesa ativa não pode ser inativada, bloqueada ou arquivada.")


def _cost_center_has_children(db: Session, cost_center_id: str, company_id: str, *, active_only: bool = False) -> bool:
    statement = (
        select(CostCenterDB.id)
        .where(CostCenterDB.company_id == company_id)
        .where(CostCenterDB.parent_id == cost_center_id)
        .limit(1)
    )
    if active_only:
        statement = statement.where(CostCenterDB.status == "active")
    return db.scalar(statement) is not None


def _cost_center_has_active_title(db: Session, cost_center_id: str, company_id: str) -> bool:
    from app.modules.accounts_receivable.db_models import FinancialTitleDB

    active_statuses = {"draft", "open", "overdue", "partially_received", "partially_paid", "renegotiated"}
    statement = (
        select(FinancialTitleDB.id)
        .where(FinancialTitleDB.company_id == company_id)
        .where(FinancialTitleDB.cost_center_id == cost_center_id)
        .where(FinancialTitleDB.deleted_at.is_(None))
        .where(FinancialTitleDB.status.in_(active_statuses))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _cost_center_has_active_purchase(db: Session, cost_center_id: str, company_id: str) -> bool:
    from app.modules.purchases_payables.db_models import PurchaseDB

    statement = (
        select(PurchaseDB.id)
        .where(PurchaseDB.company_id == company_id)
        .where(PurchaseDB.cost_center_id == cost_center_id)
        .where(PurchaseDB.deleted_at.is_(None))
        .where(PurchaseDB.status.in_({"draft", "confirmed"}))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _assert_cost_center_no_cycle(db: Session, row: CostCenterDB, parent_id: str | None) -> None:
    if parent_id is None:
        return
    if parent_id == row.id:
        raise ValueError("Centro de custo nao pode ser pai dele mesmo.")

    visited = {row.id}
    current_parent_id = parent_id
    while current_parent_id:
        if current_parent_id in visited:
            raise ValueError("Hierarquia de centros de custo nao pode formar ciclo.")
        visited.add(current_parent_id)
        parent = get_by_id(db, CostCenterDB, current_parent_id)
        if parent is None:
            raise ValueError("Centro de custo pai nao encontrado.")
        if parent.company_id != row.company_id:
            raise ValueError("Centro de custo pai pertence a outra empresa.")
        current_parent_id = parent.parent_id


def _assert_cost_center_update_rules(db: Session, row: CostCenterDB, data: dict[str, Any]) -> None:
    parent_id = data["parent_id"] if "parent_id" in data else row.parent_id
    is_analytical = data["is_analytical"] if "is_analytical" in data else row.is_analytical
    status = data["status"] if "status" in data else row.status

    _assert_cost_center_no_cycle(db, row, parent_id)

    if _cost_center_has_children(db, row.id, row.company_id) and is_analytical:
        raise ValueError("Centro de custo com centros filhos deve permanecer sintetico.")

    if status in {"inactive", "blocked", "archived"}:
        if _cost_center_has_children(db, row.id, row.company_id, active_only=True):
            raise ValueError("Centro de custo com centros filhos ativos nao pode ser inativado, bloqueado ou arquivado.")
        if _cost_center_has_active_title(db, row.id, row.company_id):
            raise ValueError("Centro de custo vinculado a titulo financeiro ativo nao pode ser inativado, bloqueado ou arquivado.")
        if _cost_center_has_active_purchase(db, row.id, row.company_id):
            raise ValueError("Centro de custo vinculado a compra/despesa ativa nao pode ser inativado, bloqueado ou arquivado.")


def _financial_account_has_balance(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.cash.db_models import FinancialAccountBalanceDB

    statement = (
        select(FinancialAccountBalanceDB.id)
        .where(FinancialAccountBalanceDB.company_id == company_id)
        .where(FinancialAccountBalanceDB.financial_account_id == account_id)
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_account_has_posted_movement(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.cash.db_models import FinancialMovementDB

    statement = (
        select(FinancialMovementDB.id)
        .where(FinancialMovementDB.company_id == company_id)
        .where(FinancialMovementDB.financial_account_id == account_id)
        .where(FinancialMovementDB.status == "posted")
        .where(FinancialMovementDB.reconciliation_status != "reversed")
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_account_has_active_settlement(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.cash.db_models import SettlementDB

    statement = (
        select(SettlementDB.id)
        .where(SettlementDB.company_id == company_id)
        .where(SettlementDB.financial_account_id == account_id)
        .where(SettlementDB.status == "active")
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_account_has_active_title(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.accounts_receivable.db_models import FinancialTitleDB

    active_statuses = {"draft", "open", "overdue", "partially_received", "partially_paid", "renegotiated"}
    statement = (
        select(FinancialTitleDB.id)
        .where(FinancialTitleDB.company_id == company_id)
        .where(FinancialTitleDB.expected_financial_account_id == account_id)
        .where(FinancialTitleDB.deleted_at.is_(None))
        .where(FinancialTitleDB.status.in_(active_statuses))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_account_has_active_purchase(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.purchases_payables.db_models import PurchaseDB

    statement = (
        select(PurchaseDB.id)
        .where(PurchaseDB.company_id == company_id)
        .where(PurchaseDB.expected_financial_account_id == account_id)
        .where(PurchaseDB.deleted_at.is_(None))
        .where(PurchaseDB.status.in_({"draft", "confirmed"}))
        .limit(1)
    )
    return db.scalar(statement) is not None


def _financial_account_has_statement_data(db: Session, account_id: str, company_id: str) -> bool:
    from app.modules.reconciliation.db_models import BankStatementImportDB, BankStatementLineDB, ReconciliationMatchDB

    imports = (
        select(BankStatementImportDB.id)
        .where(BankStatementImportDB.company_id == company_id)
        .where(BankStatementImportDB.financial_account_id == account_id)
        .limit(1)
    )
    if db.scalar(imports) is not None:
        return True

    lines = (
        select(BankStatementLineDB.id)
        .where(BankStatementLineDB.company_id == company_id)
        .where(BankStatementLineDB.financial_account_id == account_id)
        .where(BankStatementLineDB.status.in_({"pending", "matched", "divergent"}))
        .limit(1)
    )
    if db.scalar(lines) is not None:
        return True

    matches = (
        select(ReconciliationMatchDB.id)
        .where(ReconciliationMatchDB.company_id == company_id)
        .where(ReconciliationMatchDB.financial_account_id == account_id)
        .where(ReconciliationMatchDB.status.in_({"confirmed", "confirmed_with_difference"}))
        .limit(1)
    )
    return db.scalar(matches) is not None


def _financial_account_is_in_use(db: Session, account_id: str, company_id: str) -> bool:
    return any(
        (
            _financial_account_has_balance(db, account_id, company_id),
            _financial_account_has_posted_movement(db, account_id, company_id),
            _financial_account_has_active_settlement(db, account_id, company_id),
            _financial_account_has_active_title(db, account_id, company_id),
            _financial_account_has_active_purchase(db, account_id, company_id),
            _financial_account_has_statement_data(db, account_id, company_id),
        )
    )


def _assert_financial_account_effective_rules(
    *,
    account_type: str,
    institution_name: str | None,
    pix_key: str | None,
    pix_key_type: str | None,
    status: str,
    is_default_receivable: bool,
    is_default_payable: bool,
) -> None:
    if account_type == "bank_account" and not institution_name:
        raise ValueError("Conta bancaria deve informar instituicao.")
    if pix_key and not pix_key_type:
        raise ValueError("Chave Pix deve informar tipo.")
    if status != "active" and (is_default_receivable or is_default_payable):
        raise ValueError("Conta financeira padrao precisa estar ativa.")


def _assert_financial_account_update_rules(db: Session, row: FinancialAccountDB, data: dict[str, Any]) -> None:
    account_type = data["account_type"] if "account_type" in data else row.account_type
    institution_name = data["institution_name"] if "institution_name" in data else row.institution_name
    pix_key = data["pix_key"] if "pix_key" in data else row.pix_key
    pix_key_type = data["pix_key_type"] if "pix_key_type" in data else row.pix_key_type
    status = data["status"] if "status" in data else row.status
    is_default_receivable = data["is_default_receivable"] if "is_default_receivable" in data else row.is_default_receivable
    is_default_payable = data["is_default_payable"] if "is_default_payable" in data else row.is_default_payable

    _assert_financial_account_effective_rules(
        account_type=account_type,
        institution_name=institution_name,
        pix_key=pix_key,
        pix_key_type=pix_key_type,
        status=status,
        is_default_receivable=is_default_receivable,
        is_default_payable=is_default_payable,
    )

    if "opening_balance_amount" in data:
        new_balance = _decimal(data.get("opening_balance_amount"), "0")
        current_balance = _decimal(str(row.opening_balance_amount or "0"), "0")
        if new_balance != current_balance and (
            _financial_account_has_balance(db, row.id, row.company_id)
            or _financial_account_has_posted_movement(db, row.id, row.company_id)
        ):
            raise ValueError("Saldo inicial nao pode ser alterado apos saldo materializado ou movimentacao.")

    if status in {"inactive", "blocked", "archived"} and _financial_account_is_in_use(db, row.id, row.company_id):
        raise ValueError("Conta financeira em uso nao pode ser inativada, bloqueada ou arquivada.")


def _clear_other_default_financial_accounts(db: Session, row: FinancialAccountDB) -> None:
    now = utc_now()
    if row.is_default_receivable:
        statement = (
            select(FinancialAccountDB)
            .where(FinancialAccountDB.company_id == row.company_id)
            .where(FinancialAccountDB.id != row.id)
            .where(FinancialAccountDB.is_default_receivable.is_(True))
        )
        for other in db.scalars(statement):
            other.is_default_receivable = False
            other.updated_at = now
    if row.is_default_payable:
        statement = (
            select(FinancialAccountDB)
            .where(FinancialAccountDB.company_id == row.company_id)
            .where(FinancialAccountDB.id != row.id)
            .where(FinancialAccountDB.is_default_payable.is_(True))
        )
        for other in db.scalars(statement):
            other.is_default_payable = False
            other.updated_at = now


def _assert_payment_term_effective_rules(
    *,
    term_type: str,
    installments: int,
    first_due_days: int,
    interval_days: int,
) -> None:
    if term_type == "cash":
        if installments != 1:
            raise ValueError("Condicao a vista deve ter uma parcela.")
        if first_due_days != 0:
            raise ValueError("Condicao a vista deve vencer em D+0.")
        if interval_days != 0:
            raise ValueError("Condicao a vista deve ter intervalo zero.")
        return

    if installments > 1 and interval_days <= 0:
        raise ValueError("Condicao parcelada deve ter intervalo maior que zero.")


def _assert_payment_term_update_rules(row: PaymentTermDB, data: dict[str, Any]) -> None:
    _assert_payment_term_effective_rules(
        term_type=data["term_type"] if "term_type" in data else row.term_type,
        installments=data["installments"] if "installments" in data else row.installments,
        first_due_days=data["first_due_days"] if "first_due_days" in data else row.first_due_days,
        interval_days=data["interval_days"] if "interval_days" in data else row.interval_days,
    )


def _decimal(value: str | None, default: str = "0") -> Decimal:
    if value is None:
        value = default
    return Decimal(str(value))


def _handle_integrity_error(error: IntegrityError) -> None:
    message = str(error.orig).lower() if getattr(error, "orig", None) is not None else str(error).lower()
    if "unique" in message or "duplicate" in message or "uq_" in message:
        raise ValueError("Já existe cadastro financeiro com este código/nome para a empresa.") from error
    raise ValueError("Erro de integridade ao salvar cadastro financeiro.") from error


def _commit_create(
    db: Session,
    *,
    row: FinancialDB,
    company_id: str,
    to_dict: Callable[[Any], dict[str, Any]],
    entity_type: AuditEntityType,
    prefix: str,
    context: AuditContext,
) -> dict[str, Any]:
    try:
        add_row(db, row)
        after = to_dict(row)
        event = build_created_event(
            entity_type=entity_type,
            entity_id=row.id,
            context=context,
            after=after,
            expected_entity_prefix=prefix,
        )
        create_audit_event(db, event, company_id=company_id)
        db.commit()
        return after
    except IntegrityError as error:
        db.rollback()
        _handle_integrity_error(error)
    except Exception:
        db.rollback()
        raise


def _commit_update(
    db: Session,
    *,
    row: FinancialDB,
    before: dict[str, Any],
    after: dict[str, Any],
    company_id: str,
    entity_type: AuditEntityType,
    prefix: str,
    context: AuditContext,
) -> dict[str, Any]:
    try:
        if before != after:
            event = build_updated_event(
                entity_type=entity_type,
                entity_id=row.id,
                context=context,
                before=before,
                after=after,
                expected_entity_prefix=prefix,
            )
            create_audit_event(db, event, company_id=company_id)
        db.commit()
        return after
    except IntegrityError as error:
        db.rollback()
        _handle_integrity_error(error)
    except Exception:
        db.rollback()
        raise


def create_chart_account(
    db: Session,
    payload: ChartAccountCreate,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    data = payload.model_dump()
    company_id = data["company_id"]
    _assert_company_exists(db, company_id)
    if data.get("parent_id"):
        assert_valid_id(data["parent_id"], "acc")
        parent = get_by_id(db, ChartAccountDB, data["parent_id"])
        _assert_same_company(parent, company_id, "Conta pai")
        _assert_chart_parent_can_receive_child(parent)

    now = utc_now()
    row = ChartAccountDB(
        id=generate_id("acc"),
        company_id=company_id,
        code=data["code"],
        name=data["name"],
        account_type=data["account_type"],
        parent_id=data.get("parent_id"),
        is_analytical=data["is_analytical"],
        normal_balance=data.get("normal_balance"),
        accepts_entries=data["accepts_entries"],
        status=data["status"],
        notes=data.get("notes"),
        metadata_json=data.get("metadata") or {},
        created_at=now,
        updated_at=now,
    )
    return _commit_create(db, row=row, company_id=company_id, to_dict=chart_account_db_to_dict, entity_type=AuditEntityType.CHART_ACCOUNT, prefix="acc", context=_audit_context(actor_id, source, request_id, correlation_id))


def create_financial_category(
    db: Session,
    payload: FinancialCategoryCreate,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    data = payload.model_dump()
    company_id = data["company_id"]
    _assert_company_exists(db, company_id)
    _assert_category_cash_flow_rules(data["affects_cash_flow"], data.get("cash_flow_group"))
    if data.get("parent_id"):
        assert_valid_id(data["parent_id"], "cat")
        _assert_same_company(get_by_id(db, FinancialCategoryDB, data["parent_id"]), company_id, "Categoria pai")
    if data.get("chart_account_id"):
        assert_valid_id(data["chart_account_id"], "acc")
        chart_account = get_by_id(db, ChartAccountDB, data["chart_account_id"])
        _assert_same_company(chart_account, company_id, "Conta contábil/financeira")
        _assert_chart_account_can_classify_category(chart_account)
    now = utc_now()
    row = FinancialCategoryDB(
        id=generate_id("cat"),
        company_id=company_id,
        code=data.get("code"),
        name=data["name"],
        category_type=data["category_type"],
        parent_id=data.get("parent_id"),
        chart_account_id=data.get("chart_account_id"),
        cash_flow_group=data.get("cash_flow_group"),
        affects_cash_flow=data["affects_cash_flow"],
        requires_cost_center=data["requires_cost_center"],
        status=data["status"],
        notes=data.get("notes"),
        metadata_json=data.get("metadata") or {},
        created_at=now,
        updated_at=now,
    )
    return _commit_create(db, row=row, company_id=company_id, to_dict=financial_category_db_to_dict, entity_type=AuditEntityType.FINANCIAL_CATEGORY, prefix="cat", context=_audit_context(actor_id, source, request_id, correlation_id))


def create_cost_center(
    db: Session,
    payload: CostCenterCreate,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    data = payload.model_dump()
    company_id = data["company_id"]
    _assert_company_exists(db, company_id)
    if data.get("parent_id"):
        assert_valid_id(data["parent_id"], "cc")
        parent = get_by_id(db, CostCenterDB, data["parent_id"])
        _assert_same_company(parent, company_id, "Centro pai")
        _assert_cost_center_parent_can_receive_child(parent)
    now = utc_now()
    row = CostCenterDB(
        id=generate_id("cc"),
        company_id=company_id,
        code=data["code"],
        name=data["name"],
        center_type=data["center_type"],
        parent_id=data.get("parent_id"),
        is_analytical=data["is_analytical"],
        responsible_name=data.get("responsible_name"),
        monthly_budget_amount=_decimal(data.get("monthly_budget_amount"), "0") if data.get("monthly_budget_amount") is not None else None,
        status=data["status"],
        notes=data.get("notes"),
        metadata_json=data.get("metadata") or {},
        created_at=now,
        updated_at=now,
    )
    return _commit_create(db, row=row, company_id=company_id, to_dict=cost_center_db_to_dict, entity_type=AuditEntityType.COST_CENTER, prefix="cc", context=_audit_context(actor_id, source, request_id, correlation_id))


def create_financial_account(
    db: Session,
    payload: FinancialAccountCreate,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    data = payload.model_dump()
    company_id = data["company_id"]
    _assert_company_exists(db, company_id)
    _assert_financial_account_effective_rules(
        account_type=data["account_type"],
        institution_name=data.get("institution_name"),
        pix_key=data.get("pix_key"),
        pix_key_type=data.get("pix_key_type"),
        status=data["status"],
        is_default_receivable=data["is_default_receivable"],
        is_default_payable=data["is_default_payable"],
    )
    now = utc_now()
    row = FinancialAccountDB(
        id=generate_id("bankacc"),
        company_id=company_id,
        name=data["name"],
        account_type=data["account_type"],
        institution_name=data.get("institution_name"),
        branch_number=data.get("branch_number"),
        account_number=data.get("account_number"),
        account_digit=data.get("account_digit"),
        pix_key=data.get("pix_key"),
        pix_key_type=data.get("pix_key_type"),
        currency=data.get("currency") or "BRL",
        opening_balance_amount=_decimal(data.get("opening_balance_amount"), "0"),
        is_default_receivable=data["is_default_receivable"],
        is_default_payable=data["is_default_payable"],
        status=data["status"],
        notes=data.get("notes"),
        metadata_json=data.get("metadata") or {},
        created_at=now,
        updated_at=now,
    )
    _clear_other_default_financial_accounts(db, row)
    return _commit_create(db, row=row, company_id=company_id, to_dict=financial_account_db_to_dict, entity_type=AuditEntityType.FINANCIAL_ACCOUNT, prefix="bankacc", context=_audit_context(actor_id, source, request_id, correlation_id))


def create_payment_term(
    db: Session,
    payload: PaymentTermCreate,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    data = payload.model_dump()
    company_id = data["company_id"]
    _assert_company_exists(db, company_id)
    _assert_payment_term_effective_rules(
        term_type=data["term_type"],
        installments=data["installments"],
        first_due_days=data["first_due_days"],
        interval_days=data["interval_days"],
    )
    now = utc_now()
    row = PaymentTermDB(
        id=generate_id("term"),
        company_id=company_id,
        name=data["name"],
        term_type=data["term_type"],
        installments=data["installments"],
        first_due_days=data["first_due_days"],
        interval_days=data["interval_days"],
        generate_on_sale=data["generate_on_sale"],
        status=data["status"],
        notes=data.get("notes"),
        metadata_json=data.get("metadata") or {},
        created_at=now,
        updated_at=now,
    )
    return _commit_create(db, row=row, company_id=company_id, to_dict=payment_term_db_to_dict, entity_type=AuditEntityType.PAYMENT_TERM, prefix="term", context=_audit_context(actor_id, source, request_id, correlation_id))


def _apply_update(row: Any, data: dict[str, Any]) -> None:
    if not data:
        raise ValueError("Nenhum campo informado para atualização.")
    for key, value in data.items():
        if key == "metadata":
            setattr(row, "metadata_json", value or {})
        elif key == "monthly_budget_amount":
            setattr(row, key, _decimal(value, "0") if value is not None else None)
        elif key == "opening_balance_amount":
            setattr(row, key, _decimal(value, "0") if value is not None else Decimal("0"))
        elif hasattr(row, key):
            setattr(row, key, value)
    row.updated_at = utc_now()


def _update_generic(
    db: Session,
    *,
    model: type[FinancialDB],
    row_id: str,
    payload: Any,
    prefix: str,
    to_dict: Callable[[Any], dict[str, Any]],
    entity_type: AuditEntityType,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
    expected_company_id: str | None = None,
) -> dict[str, Any]:
    assert_valid_id(row_id, prefix)
    row = get_by_id(db, model, row_id)
    if row is None:
        raise ValueError("Cadastro financeiro não encontrado.")
    if expected_company_id is not None and row.company_id != expected_company_id:
        raise ValueError("Cadastro financeiro pertence a outra empresa.")
    before = to_dict(row)
    data = payload.model_dump(exclude_unset=True)

    company_id = row.company_id
    if data.get("parent_id"):
        expected_parent_prefix = prefix if prefix in {"acc", "cat", "cc"} else prefix
        assert_valid_id(data["parent_id"], expected_parent_prefix)
        parent = get_by_id(db, model, data["parent_id"])
        _assert_same_company(parent, company_id, "Registro pai")
        if model is ChartAccountDB:
            _assert_chart_parent_can_receive_child(parent)
        if model is CostCenterDB:
            _assert_cost_center_parent_can_receive_child(parent)
    if data.get("chart_account_id"):
        assert_valid_id(data["chart_account_id"], "acc")
        chart_account = get_by_id(db, ChartAccountDB, data["chart_account_id"])
        _assert_same_company(chart_account, company_id, "Conta contábil/financeira")
        _assert_chart_account_can_classify_category(chart_account)

    if model in {ChartAccountDB, FinancialCategoryDB, CostCenterDB} and data.get("code"):
        existing = get_by_company_code(db, model, company_id, data["code"])
        if existing is not None and existing.id != row.id:
            raise ValueError("Já existe cadastro com este código para a empresa.")

    if model is ChartAccountDB:
        _assert_chart_account_update_rules(db, row, data)
    if model is FinancialCategoryDB:
        _assert_financial_category_update_rules(db, row, data)
    if model is CostCenterDB:
        _assert_cost_center_update_rules(db, row, data)
    if model is FinancialAccountDB:
        _assert_financial_account_update_rules(db, row, data)
    if model is PaymentTermDB:
        _assert_payment_term_update_rules(row, data)

    _apply_update(row, data)
    if model is FinancialAccountDB:
        _clear_other_default_financial_accounts(db, row)
    after = to_dict(row)
    return _commit_update(db, row=row, before=before, after=after, company_id=company_id, entity_type=entity_type, prefix=prefix, context=_audit_context(actor_id, source, request_id, correlation_id))


def update_chart_account(db: Session, row_id: str, payload: ChartAccountUpdate, **kwargs: Any) -> dict[str, Any]:
    return _update_generic(db, model=ChartAccountDB, row_id=row_id, payload=payload, prefix="acc", to_dict=chart_account_db_to_dict, entity_type=AuditEntityType.CHART_ACCOUNT, **kwargs)


def update_financial_category(db: Session, row_id: str, payload: FinancialCategoryUpdate, **kwargs: Any) -> dict[str, Any]:
    return _update_generic(db, model=FinancialCategoryDB, row_id=row_id, payload=payload, prefix="cat", to_dict=financial_category_db_to_dict, entity_type=AuditEntityType.FINANCIAL_CATEGORY, **kwargs)


def update_cost_center(db: Session, row_id: str, payload: CostCenterUpdate, **kwargs: Any) -> dict[str, Any]:
    return _update_generic(db, model=CostCenterDB, row_id=row_id, payload=payload, prefix="cc", to_dict=cost_center_db_to_dict, entity_type=AuditEntityType.COST_CENTER, **kwargs)


def update_financial_account(db: Session, row_id: str, payload: FinancialAccountUpdate, **kwargs: Any) -> dict[str, Any]:
    return _update_generic(db, model=FinancialAccountDB, row_id=row_id, payload=payload, prefix="bankacc", to_dict=financial_account_db_to_dict, entity_type=AuditEntityType.FINANCIAL_ACCOUNT, **kwargs)


def update_payment_term(db: Session, row_id: str, payload: PaymentTermUpdate, **kwargs: Any) -> dict[str, Any]:
    return _update_generic(db, model=PaymentTermDB, row_id=row_id, payload=payload, prefix="term", to_dict=payment_term_db_to_dict, entity_type=AuditEntityType.PAYMENT_TERM, **kwargs)


def _list_generic(db: Session, key: str, *, company_id: str, status: str | None = None, search: str | None = None, limit: int = 50, offset: int = 0, type_value: str | None = None, cash_flow_group: str | None = None) -> list[dict[str, Any]]:
    _assert_company_exists(db, company_id)
    config = ENTITY_CONFIG[key]
    type_field = {
        "chart_accounts": "account_type",
        "financial_categories": "category_type",
        "cost_centers": "center_type",
        "financial_accounts": "account_type",
        "payment_terms": "term_type",
    }[key]
    rows = list_rows(db, config["model"], company_id=company_id, status=status, search=search, limit=limit, offset=offset, type_field=type_field, type_value=type_value, cash_flow_group=cash_flow_group)
    return [config["to_dict"](row) for row in rows]


def list_chart_accounts(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_generic(db, "chart_accounts", **kwargs)


def list_financial_categories(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_generic(db, "financial_categories", **kwargs)


def list_cost_centers(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_generic(db, "cost_centers", **kwargs)


def list_financial_accounts(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_generic(db, "financial_accounts", **kwargs)


def list_payment_terms(db: Session, **kwargs: Any) -> list[dict[str, Any]]:
    return _list_generic(db, "payment_terms", **kwargs)


def _get_generic(db: Session, key: str, row_id: str) -> dict[str, Any]:
    config = ENTITY_CONFIG[key]
    assert_valid_id(row_id, config["prefix"])
    row = get_by_id(db, config["model"], row_id)
    if row is None:
        raise ValueError(f"{config['label']} não encontrado.")
    return config["to_dict"](row)


def get_chart_account(db: Session, row_id: str) -> dict[str, Any]:
    return _get_generic(db, "chart_accounts", row_id)


def get_financial_category(db: Session, row_id: str) -> dict[str, Any]:
    return _get_generic(db, "financial_categories", row_id)


def get_cost_center(db: Session, row_id: str) -> dict[str, Any]:
    return _get_generic(db, "cost_centers", row_id)


def get_financial_account(db: Session, row_id: str) -> dict[str, Any]:
    return _get_generic(db, "financial_accounts", row_id)


def get_payment_term(db: Session, row_id: str) -> dict[str, Any]:
    return _get_generic(db, "payment_terms", row_id)


def get_financial_audit_events(db: Session, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    events = list_audit_events_for_entity(db, entity_type=entity_type, entity_id=entity_id, limit=100, offset=0)
    return [audit_event_db_to_dict(event) for event in events]


def create_default_financial_masters(
    db: Session,
    company_id: str,
    *,
    source: AuditSource = AuditSource.SYSTEM,
    request_id: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    _assert_company_exists(db, company_id)
    created: dict[str, list[dict[str, Any]]] = {
        "chart_accounts": [],
        "financial_categories": [],
        "cost_centers": [],
        "financial_accounts": [],
        "payment_terms": [],
    }

    def exists_code(model: type[Any], code: str) -> bool:
        return get_by_company_code(db, model, company_id, code) is not None

    defaults_chart = [
        ("1.01", "Caixa e equivalentes", "asset", False),
        ("3.01", "Receita de vendas", "revenue", True),
        ("4.01", "Custo das mercadorias vendidas", "cost", True),
        ("5.01", "Despesas administrativas", "expense", True),
        ("5.02", "Taxas e tarifas", "expense", True),
        ("2.01", "Tributos a pagar", "liability", True),
    ]
    for code, name, acc_type, analytical in defaults_chart:
        if not exists_code(ChartAccountDB, code):
            created["chart_accounts"].append(create_chart_account(db, ChartAccountCreate(company_id=company_id, code=code, name=name, account_type=acc_type, is_analytical=analytical, accepts_entries=analytical), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))

    if not exists_code(CostCenterDB, "A-CLASSIFICAR"):
        created["cost_centers"].append(create_cost_center(db, CostCenterCreate(company_id=company_id, code="A-CLASSIFICAR", name="A Classificar", center_type="other", is_analytical=True, notes="Centro transitório para lançamentos ainda não classificados."), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))
    if not exists_code(CostCenterDB, "COMERCIAL"):
        created["cost_centers"].append(create_cost_center(db, CostCenterCreate(company_id=company_id, code="COMERCIAL", name="Comercial", center_type="commercial", is_analytical=True), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))
    if not exists_code(CostCenterDB, "ADMIN"):
        created["cost_centers"].append(create_cost_center(db, CostCenterCreate(company_id=company_id, code="ADMIN", name="Administrativo", center_type="administrative", is_analytical=True), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))

    has_financial_account = db.scalar(
        select(FinancialAccountDB.id)
        .where(FinancialAccountDB.company_id == company_id)
        .where(FinancialAccountDB.deleted_at.is_(None))
        .limit(1)
    ) is not None
    if not has_financial_account:
        created["financial_accounts"].append(
            create_financial_account(
                db,
                FinancialAccountCreate(
                    company_id=company_id,
                    name="Caixa Principal",
                    account_type="cash",
                    opening_balance_amount="0",
                    is_default_receivable=True,
                    is_default_payable=True,
                    notes="Conta financeira padrao para operacao inicial.",
                ),
                source=source,
                request_id=request_id,
                correlation_id=correlation_id,
                actor_id=actor_id,
            )
        )

    defaults_categories = [
        ("VENDA-PRODUTOS", "Venda de produtos", "income", "operating_inflows", False),
        ("VENDA-SERVICOS", "Venda de serviços", "income", "operating_inflows", False),
        ("TAXAS-GATEWAY", "Taxas de gateway/adquirente", "fee", "operating_outflows", False),
        ("TRIBUTOS-VENDAS", "Tributos sobre vendas", "tax", "operating_outflows", False),
        ("FORNECEDORES", "Fornecedores de mercadorias", "cost", "operating_outflows", True),
        ("DESP-ADMIN", "Despesas administrativas", "expense", "operating_outflows", True),
    ]
    for code, name, cat_type, group, req_cc in defaults_categories:
        if not exists_code(FinancialCategoryDB, code):
            created["financial_categories"].append(create_financial_category(db, FinancialCategoryCreate(company_id=company_id, code=code, name=name, category_type=cat_type, cash_flow_group=group, requires_cost_center=req_cc), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))

    if get_payment_term_by_company_name(db, company_id, "À vista") is None:
        created["payment_terms"].append(create_payment_term(db, PaymentTermCreate(company_id=company_id, name="À vista", term_type="cash", installments=1, first_due_days=0, interval_days=0), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))
    if get_payment_term_by_company_name(db, company_id, "30 dias") is None:
        created["payment_terms"].append(create_payment_term(db, PaymentTermCreate(company_id=company_id, name="30 dias", term_type="installments", installments=1, first_due_days=30, interval_days=30), source=source, request_id=request_id, correlation_id=correlation_id, actor_id=actor_id))

    return {"company_id": company_id, "created": created}


def get_financial_diagnostics(db: Session, company_id: str | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "module": "financial",
        "status": "ready",
        "storage": "database",
        "persistence": "postgresql",
        "tables": ["chart_accounts", "financial_categories", "cost_centers", "financial_accounts", "payment_terms"],
        "integration_role": "base_for_accounts_receivable_accounts_payable_cash_reconciliation_reports",
    }
    if company_id:
        _assert_company_exists(db, company_id)
        data["records_count"] = {
            "chart_accounts": count_rows(db, ChartAccountDB, company_id),
            "financial_categories": count_rows(db, FinancialCategoryDB, company_id),
            "cost_centers": count_rows(db, CostCenterDB, company_id),
            "financial_accounts": count_rows(db, FinancialAccountDB, company_id),
            "payment_terms": count_rows(db, PaymentTermDB, company_id),
        }
        data["active_records_count"] = {
            "chart_accounts": count_rows(db, ChartAccountDB, company_id, status="active"),
            "financial_categories": count_rows(db, FinancialCategoryDB, company_id, status="active"),
            "cost_centers": count_rows(db, CostCenterDB, company_id, status="active"),
            "financial_accounts": count_rows(db, FinancialAccountDB, company_id, status="active"),
            "payment_terms": count_rows(db, PaymentTermDB, company_id, status="active"),
        }
    return data


def get_financial_rules() -> dict[str, Any]:
    return {
        "module": "financial",
        "principles": [
            "Cadastro financeiro mestre antes de lançamento financeiro.",
            "Conta bancária, categoria, plano de contas, centro de custo e condição de pagamento não devem ser texto solto.",
            "Backend valida vínculos, status e empresa; frontend só antecipa bloqueios visuais.",
            "Títulos financeiros futuros devem guardar ID do cadastro mestre e snapshot histórico.",
            "Centro de custo não substitui plano de contas; categoria financeira não substitui classificação fiscal.",
        ],
        "id_prefixes": {
            "chart_account": "acc",
            "financial_category": "cat",
            "cost_center": "cc",
            "financial_account": "bankacc",
            "payment_term": "term",
        },
        "next_modules_prepared": ["accounts_receivable", "accounts_payable", "cash_treasury", "bank_reconciliation", "financial_reports"],
    }
