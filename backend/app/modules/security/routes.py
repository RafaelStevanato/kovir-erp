from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.security.dependencies import get_current_principal
from app.modules.security.schemas import (
    ApprovalDecisionPayload,
    ApprovalPolicyUpdatePayload,
    BootstrapAdminPayload,
    CreateCompanyUserPayload,
    CreatePaymentApprovalRequestPayload,
    LoginPayload,
    SetMasterPasswordPayload,
    UpdateCompanyUserRolesPayload,
)
from app.modules.security.service import (
    SecurityPrincipal,
    bootstrap_admin_user,
    create_company_user,
    create_payment_approval_request,
    decide_approval_request,
    diagnostics,
    ensure_security_catalog,
    get_allowed_views_catalog,
    get_payment_approval_policy,
    get_rules,
    is_master_password_configured,
    list_approval_requests,
    list_company_users,
    list_permissions,
    list_roles,
    login,
    logout,
    me,
    set_master_password,
    update_company_user_roles,
    update_payment_approval_policy,
)
from app.shared.schemas import ApiResponse

router = APIRouter(tags=["security"])

LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 10
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
_LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)


def _api_response(success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST
    lowered = message.lower()
    if "nÃ£o encontrado" in lowered or "nÃ£o encontrada" in lowered:
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(
        status_code=status_code,
        content=_api_response(False, message, None),
    )


def _request_ids(request: Request) -> dict[str, str | None]:
    request_id = request.headers.get("x-request-id")
    return {
        "request_id": request_id,
        "correlation_id": request.headers.get("x-correlation-id") or request_id,
    }


def _token_from_request(request: Request) -> str:
    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return ""
    return token.strip()


def _login_rate_key(payload: LoginPayload, request: Request) -> str:
    ip_address = request.client.host if request.client else "unknown"
    return f"{ip_address}|{payload.company_id.strip().lower()}|{payload.email.strip().lower()}"


def _assert_login_rate_limit(payload: LoginPayload, request: Request) -> str:
    key = _login_rate_key(payload, request)
    now = monotonic()
    attempts = _LOGIN_ATTEMPTS[key]
    while attempts and now - attempts[0] > LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Aguarde alguns minutos e tente novamente.",
        )
    attempts.append(now)
    return key


@router.post("/auth/bootstrap-admin", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_admin_route(
    payload: BootstrapAdminPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        data = bootstrap_admin_user(
            db,
            payload,
            bootstrap_token=request.headers.get("x-bootstrap-token"),
            **_request_ids(request),
        )
        return _api_response(True, "Administrador inicial criado com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/auth/login", response_model=ApiResponse)
def login_route(
    payload: LoginPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    rate_key = _assert_login_rate_limit(payload, request)
    try:
        data = login(
            db,
            payload,
            **_request_ids(request),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        _LOGIN_ATTEMPTS.pop(rate_key, None)
        return _api_response(True, "Login realizado com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/auth/logout", response_model=ApiResponse)
def logout_route(
    request: Request,
    db: Session = Depends(get_db),
):
    data = logout(
        db,
        _token_from_request(request),
        **_request_ids(request),
    )
    return _api_response(True, "SessÃ£o encerrada.", data)


@router.get("/auth/me", response_model=ApiResponse)
def me_route(principal: SecurityPrincipal = Depends(get_current_principal)):
    return _api_response(True, "SessÃ£o autenticada carregada.", me(principal))


@router.get("/security/rules", response_model=ApiResponse)
def rules_route():
    return _api_response(True, "Regras de seguranÃ§a carregadas.", get_rules())


@router.get("/security/diagnostics", response_model=ApiResponse)
def diagnostics_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    return _api_response(
        True,
        "DiagnÃ³stico de seguranÃ§a carregado.",
        diagnostics(db) | {"actor_company_id": principal.company_id},
    )


@router.post("/security/catalog/ensure", response_model=ApiResponse)
def ensure_catalog_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    if "users.manage" not in principal.permission_codes:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_response(False, "PermissÃ£o users.manage obrigatÃ³ria.", None),
        )
    data = ensure_security_catalog(db)
    db.commit()
    return _api_response(True, "CatÃ¡logo de seguranÃ§a garantido.", data)


@router.get("/security/roles", response_model=ApiResponse)
def roles_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    if "users.manage" not in principal.permission_codes:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_response(False, "PermissÃ£o users.manage obrigatÃ³ria.", None),
        )
    return _api_response(True, "PapÃ©is carregados.", list_roles(db))


@router.get("/security/permissions", response_model=ApiResponse)
def permissions_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    if "users.manage" not in principal.permission_codes:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_response(False, "PermissÃ£o users.manage obrigatÃ³ria.", None),
        )
    return _api_response(True, "PermissÃµes carregadas.", list_permissions(db))


@router.get("/security/allowed-views", response_model=ApiResponse)
def allowed_views_route(
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    if "users.manage" not in principal.permission_codes:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_response(False, "PermissÃ£o users.manage obrigatÃ³ria.", None),
        )
    if "admin" not in principal.role_codes:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_api_response(False, "Apenas usuÃ¡rio master pode delegar abas.", None),
        )
    return _api_response(True, "CatÃ¡logo de abas permitidas carregado.", get_allowed_views_catalog())


@router.get("/security/company-users", response_model=ApiResponse)
def company_users_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(True, "UsuÃ¡rios da empresa carregados.", list_company_users(db, actor=principal))
    except ValueError as error:
        return _error_response(error)


@router.post("/security/company-users", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_company_user_route(
    payload: CreateCompanyUserPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = create_company_user(
            db,
            payload,
            actor=principal,
            **_request_ids(request),
        )
        return _api_response(True, "UsuÃ¡rio da empresa criado/atualizado.", data)
    except ValueError as error:
        return _error_response(error)


@router.patch("/security/company-users/{membership_id}/roles", response_model=ApiResponse)
def update_company_user_roles_route(
    membership_id: str,
    payload: UpdateCompanyUserRolesPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = update_company_user_roles(
            db,
            membership_id,
            payload,
            actor=principal,
            **_request_ids(request),
        )
        return _api_response(True, "PapÃ©is do usuÃ¡rio atualizados.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/security/approval-policy/payment", response_model=ApiResponse)
def payment_policy_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        return _api_response(True, "PolÃ­tica de alÃ§ada carregada.", get_payment_approval_policy(db, actor=principal))
    except ValueError as error:
        return _error_response(error)


@router.put("/security/approval-policy/payment", response_model=ApiResponse)
def update_payment_policy_route(
    payload: ApprovalPolicyUpdatePayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = update_payment_approval_policy(
            db,
            payload,
            actor=principal,
            **_request_ids(request),
        )
        return _api_response(True, "PolÃ­tica de alÃ§ada atualizada.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/security/master-password", response_model=ApiResponse)
def set_master_password_route(
    payload: SetMasterPasswordPayload,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = set_master_password(db, principal.company_id, payload.password, actor=principal)
        return _api_response(True, "Senha mestre configurada com sucesso.", data)
    except ValueError as error:
        return _error_response(error)


@router.get("/security/master-password/status", response_model=ApiResponse)
def get_master_password_status_route(
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    configured = is_master_password_configured(db, principal.company_id)
    return _api_response(True, "Status da senha mestre carregado.", {"configured": configured})


@router.get("/security/approval-requests", response_model=ApiResponse)
def list_approval_requests_route(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = list_approval_requests(
            db,
            actor=principal,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        return _api_response(True, "SolicitaÃ§Ãµes de alÃ§ada carregadas.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/security/approval-requests", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_approval_request_route(
    payload: CreatePaymentApprovalRequestPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = create_payment_approval_request(
            db,
            actor=principal,
            financial_title_id=payload.financial_title_id,
            requested_amount=payload.requested_amount,
            payload_snapshot=payload.payload_snapshot,
            reason=payload.reason,
            **_request_ids(request),
        )
        return _api_response(True, "SolicitaÃ§Ã£o de alÃ§ada criada.", data)
    except ValueError as error:
        return _error_response(error)


@router.post("/security/approval-requests/{approval_request_id}/decision", response_model=ApiResponse)
def decide_approval_request_route(
    approval_request_id: str,
    payload: ApprovalDecisionPayload,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    try:
        data = decide_approval_request(
            db,
            approval_request_id,
            payload,
            actor=principal,
            **_request_ids(request),
        )
        return _api_response(True, "DecisÃ£o de alÃ§ada registrada.", data)
    except ValueError as error:
        return _error_response(error)
