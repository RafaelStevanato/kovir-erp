from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
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
from app.modules.financial.period_schemas import FinancialPeriodClosureCreate, FinancialPeriodClosureDeactivate
from app.modules.financial.period_service import create_period_closure, deactivate_period_closure, list_period_closures
from app.modules.financial.service import (
    create_chart_account,
    create_cost_center,
    create_default_financial_masters,
    create_financial_account,
    create_financial_category,
    create_payment_term,
    get_chart_account,
    get_cost_center,
    get_financial_account,
    get_financial_audit_events,
    get_financial_category,
    get_financial_diagnostics,
    get_financial_rules,
    get_payment_term,
    list_chart_accounts,
    list_cost_centers,
    list_financial_accounts,
    list_financial_categories,
    list_payment_terms,
    update_chart_account,
    update_cost_center,
    update_financial_account,
    update_financial_category,
    update_payment_term,
)
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse

router = APIRouter(tags=["Financial"])


def _api_response(success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content=_api_response(success=False, message=message, data=None))


def _kwargs(request: Request, principal: SecurityPrincipal | None = None) -> dict[str, Any]:
    return {
        "source": AuditSource.API,
        "request_id": _request_id_from_request(request),
        "correlation_id": _correlation_id_from_request(request),
        "actor_id": principal.user_id if principal is not None else None,
    }


def _resolve_company_id(company_id: str | None, principal: SecurityPrincipal) -> str:
    resolved = company_id or principal.company_id
    if resolved != principal.company_id:
        raise ValueError("Sessão autenticada não pertence à empresa informada.")
    return resolved


def _assert_company_scope(company_id: str, principal: SecurityPrincipal) -> None:
    if company_id != principal.company_id:
        raise ValueError("Sessão autenticada não pertence à empresa informada.")


def _require_finance_read(principal: SecurityPrincipal) -> None:
    require_permission(principal, "finance.read")


def _require_finance_write(principal: SecurityPrincipal) -> None:
    require_permission(principal, "finance.write")


def _assert_data_company_scope(data: dict[str, Any], principal: SecurityPrincipal) -> None:
    if data.get("company_id") != principal.company_id:
        raise ValueError("Sessão autenticada não pertence à empresa informada.")


@router.get("/financial/diagnostics", response_model=ApiResponse)
def get_financial_diagnostics_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(
            success=True,
            message="Diagnóstico financeiro carregado com sucesso.",
            data=get_financial_diagnostics(db, company_id=resolved_company_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/rules", response_model=ApiResponse)
def get_financial_rules_route():
    return _api_response(success=True, message="Regras financeiras carregadas com sucesso.", data=get_financial_rules())


@router.get("/financial/period-closures", response_model=ApiResponse)
def list_financial_period_closures_route(
    company_id: str | None = Query(default=None),
    status_filter: str | None = Query(default="active", alias="status"),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        data = list_period_closures(
            db,
            company_id=resolved_company_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return _api_response(True, "Fechamentos de período carregados com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/period-closures", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_financial_period_closure_route(
    payload: FinancialPeriodClosureCreate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        require_permission(principal, "users.manage")
        if payload.company_id != principal.company_id:
            raise ValueError("Sessão autenticada não pertence à empresa informada.")
        data = create_period_closure(db, payload, actor_id=principal.user_id)
        return _api_response(True, "Período financeiro fechado com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/period-closures/{closure_id}/deactivate", response_model=ApiResponse)
def deactivate_financial_period_closure_route(
    closure_id: str,
    payload: FinancialPeriodClosureDeactivate,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        require_permission(principal, "users.manage")
        data = deactivate_period_closure(
            db,
            closure_id,
            payload,
            expected_company_id=principal.company_id,
            actor_id=principal.user_id,
        )
        return _api_response(True, "Fechamento de período desativado com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/defaults", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_financial_defaults_route(request: Request, company_id: str = Query(...), db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Cadastros financeiros padrão criados com sucesso.", data=create_default_financial_masters(db, company_id=_resolve_company_id(company_id, principal), **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/chart-accounts", response_model=ApiResponse)
def list_chart_accounts_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    account_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(success=True, message="Plano de contas carregado com sucesso.", data=list_chart_accounts(db, company_id=resolved_company_id, status=status_filter, type_value=account_type, search=search, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/chart-accounts", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_chart_account_route(payload: ChartAccountCreate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Conta do plano de contas criada com sucesso.", data=create_chart_account(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/chart-accounts/{account_id}", response_model=ApiResponse)
def get_chart_account_route(account_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        data = get_chart_account(db, account_id)
        _assert_data_company_scope(data, principal)
        return _api_response(success=True, message="Conta do plano de contas carregada com sucesso.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/chart-accounts/{account_id}", response_model=ApiResponse)
def update_chart_account_route(account_id: str, payload: ChartAccountUpdate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Conta do plano de contas atualizada com sucesso.", data=update_chart_account(db, account_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/categories", response_model=ApiResponse)
def list_categories_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    category_type: str | None = Query(default=None),
    cash_flow_group: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(success=True, message="Categorias financeiras carregadas com sucesso.", data=list_financial_categories(db, company_id=resolved_company_id, status=status_filter, type_value=category_type, cash_flow_group=cash_flow_group, search=search, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/categories", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_category_route(payload: FinancialCategoryCreate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Categoria financeira criada com sucesso.", data=create_financial_category(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/categories/{category_id}", response_model=ApiResponse)
def get_category_route(category_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        data = get_financial_category(db, category_id)
        _assert_data_company_scope(data, principal)
        return _api_response(success=True, message="Categoria financeira carregada com sucesso.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/categories/{category_id}", response_model=ApiResponse)
def update_category_route(category_id: str, payload: FinancialCategoryUpdate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Categoria financeira atualizada com sucesso.", data=update_financial_category(db, category_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/cost-centers", response_model=ApiResponse)
def list_cost_centers_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    center_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(success=True, message="Centros de custo carregados com sucesso.", data=list_cost_centers(db, company_id=resolved_company_id, status=status_filter, type_value=center_type, search=search, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/cost-centers", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_cost_center_route(payload: CostCenterCreate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Centro de custo criado com sucesso.", data=create_cost_center(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/cost-centers/{cost_center_id}", response_model=ApiResponse)
def get_cost_center_route(cost_center_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        data = get_cost_center(db, cost_center_id)
        _assert_data_company_scope(data, principal)
        return _api_response(success=True, message="Centro de custo carregado com sucesso.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/cost-centers/{cost_center_id}", response_model=ApiResponse)
def update_cost_center_route(cost_center_id: str, payload: CostCenterUpdate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Centro de custo atualizado com sucesso.", data=update_cost_center(db, cost_center_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/accounts", response_model=ApiResponse)
def list_financial_accounts_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    account_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(success=True, message="Contas financeiras carregadas com sucesso.", data=list_financial_accounts(db, company_id=resolved_company_id, status=status_filter, type_value=account_type, search=search, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/accounts", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_financial_account_route(payload: FinancialAccountCreate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Conta financeira criada com sucesso.", data=create_financial_account(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/accounts/{account_id}", response_model=ApiResponse)
def get_financial_account_route(account_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        data = get_financial_account(db, account_id)
        _assert_data_company_scope(data, principal)
        return _api_response(success=True, message="Conta financeira carregada com sucesso.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/accounts/{account_id}", response_model=ApiResponse)
def update_financial_account_route(account_id: str, payload: FinancialAccountUpdate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Conta financeira atualizada com sucesso.", data=update_financial_account(db, account_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/payment-terms", response_model=ApiResponse)
def list_payment_terms_route(
    company_id: str = Query(...),
    status_filter: str | None = Query(default=None, alias="status"),
    term_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        _require_finance_read(principal)
        resolved_company_id = _resolve_company_id(company_id, principal)
        return _api_response(success=True, message="Condições de pagamento carregadas com sucesso.", data=list_payment_terms(db, company_id=resolved_company_id, status=status_filter, type_value=term_type, search=search, limit=limit, offset=offset))
    except ValueError as error:
        return _error_response(error)


@router.post("/financial/payment-terms", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_payment_term_route(payload: PaymentTermCreate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        _assert_company_scope(payload.company_id, principal)
        return _api_response(success=True, message="Condição de pagamento criada com sucesso.", data=create_payment_term(db, payload, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/payment-terms/{term_id}", response_model=ApiResponse)
def get_payment_term_route(term_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        data = get_payment_term(db, term_id)
        _assert_data_company_scope(data, principal)
        return _api_response(success=True, message="Condição de pagamento carregada com sucesso.", data=data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/financial/payment-terms/{term_id}", response_model=ApiResponse)
def update_payment_term_route(term_id: str, payload: PaymentTermUpdate, request: Request, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_write(principal)
        return _api_response(success=True, message="Condição de pagamento atualizada com sucesso.", data=update_payment_term(db, term_id, payload, expected_company_id=principal.company_id, **_kwargs(request, principal)))
    except ValueError as error:
        return _error_response(error)


@router.get("/financial/audit/{entity_type}/{entity_id}", response_model=ApiResponse)
def get_financial_audit_route(entity_type: str, entity_id: str, db: Session = Depends(get_db), principal: SecurityPrincipal = Depends(get_current_principal)):
    try:
        _require_finance_read(principal)
        return _api_response(success=True, message="Auditoria financeira carregada com sucesso.", data=get_financial_audit_events(db, entity_type=entity_type, entity_id=entity_id))
    except ValueError as error:
        return _error_response(error)
