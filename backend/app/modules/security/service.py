from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.company.db_models import CompanyDB
from app.modules.security.db_models import (
    ApprovalDecisionDB,
    ApprovalPolicyDB,
    ApprovalRequestDB,
    CompanyUserDB,
    MasterPasswordDB,
    PermissionDB,
    RoleDB,
    RolePermissionDB,
    SecurityAuditEventDB,
    UserDB,
    UserRoleDB,
    UserSessionDB,
)
from app.modules.security.schemas import (
    ApprovalDecisionPayload,
    ApprovalPolicyUpdatePayload,
    BootstrapAdminPayload,
    CreateCompanyUserPayload,
    LoginPayload,
    UpdateCompanyUserRolesPayload,
)
from app.shared.datetime import utc_now
from app.shared.ids import assert_valid_id, generate_id

PASSWORD_ITERATIONS = 120_000
SESSION_DURATION_MINUTES = 30
MONEY_QUANT = Decimal("0.01")
PAYMENT_APPROVAL_ACTION = "payables.payment"
PAYMENT_APPROVAL_PERMISSION = "approval.decide"
MIN_BOOTSTRAP_TOKEN_LENGTH = 32

DEFAULT_PERMISSIONS: list[dict[str, str]] = [
    {
        "code": "users.manage",
        "name": "Gerenciar usuÃ¡rios",
        "description": "Criar usuÃ¡rios, definir papÃ©is e membros por empresa.",
    },
    {
        "code": "company.write",
        "name": "Alterar empresa",
        "description": "Alterar dados cadastrais, fiscais e operacionais da empresa ativa.",
    },
    {
        "code": "finance.read",
        "name": "Ler financeiro",
        "description": "Consultar mÃ³dulos financeiros e relatÃ³rios operacionais.",
    },
    {
        "code": "finance.write",
        "name": "Gravar financeiro base",
        "description": "Criar e alterar cadastros financeiros base da empresa.",
    },
    {
        "code": "payables.pay",
        "name": "Pagar contas",
        "description": "Registrar pagamento de tÃ­tulo a pagar.",
    },
    {
        "code": "approval.read",
        "name": "Ler alÃ§adas",
        "description": "Consultar solicitaÃ§Ãµes e decisÃµes de aprovaÃ§Ã£o.",
    },
    {
        "code": "approval.decide",
        "name": "Decidir alÃ§adas",
        "description": "Aprovar ou rejeitar solicitaÃ§Ãµes de alÃ§ada.",
    },
    {
        "code": "reports.read",
        "name": "Ler relatÃ³rios",
        "description": "Consultar relatÃ³rios gerenciais e de fechamento.",
    },
    {
        "code": "sales.unlock_closed",
        "name": "Reabrir pedido fechado",
        "description": "Reabrir pedido fechado usando senha mestre.",
    },
    {
        "code": "imports.run",
        "name": "Executar importacoes",
        "description": "Validar e executar importacoes de dados cadastrais.",
    },
    {
        "code": "participants.write",
        "name": "Gravar participantes",
        "description": "Criar e alterar participantes da empresa.",
    },
    {
        "code": "catalog.write",
        "name": "Gravar catalogo",
        "description": "Criar e alterar produtos e servicos.",
    },
    {
        "code": "stock.move",
        "name": "Movimentar estoque",
        "description": "Criar locais e movimentos manuais de estoque.",
    },
    {
        "code": "stock.purchase_entry",
        "name": "Registrar entrada de compra",
        "description": "Importar XML e registrar entrada de estoque por compra.",
    },
    {
        "code": "sales.view",
        "name": "Ler pedidos",
        "description": "Consultar pedidos, detalhes, histÃ³rico e documentos comerciais.",
    },
    {
        "code": "sales.create",
        "name": "Criar pedidos",
        "description": "Criar e alterar pedidos em orcamento.",
    },
    {
        "code": "sales.close",
        "name": "Fechar pedidos",
        "description": "Fechar pedido e gerar efeitos oficiais de estoque e financeiro previsto.",
    },
    {
        "code": "sales.cancel",
        "name": "Cancelar pedidos",
        "description": "Cancelar pedidos respeitando estoque, baixa e auditoria.",
    },
    {
        "code": "sales.pay",
        "name": "Receber pedido legado",
        "description": "Permitir tentativa controlada no endpoint legado de recebimento direto.",
    },
    {
        "code": "cash.receive",
        "name": "Registrar recebimentos",
        "description": "Registrar baixa de titulo a receber e movimento financeiro interno.",
    },
    {
        "code": "cash.reverse",
        "name": "Estornar recebimentos",
        "description": "Estornar baixa e movimento financeiro interno.",
    },
    {
        "code": "fiscal.issue",
        "name": "Emitir documento fiscal",
        "description": "Emitir, sincronizar ou cancelar documento fiscal.",
    },
    {
        "code": "fiscal.write",
        "name": "Gravar regras fiscais",
        "description": "Criar e alterar perfis e classificacoes fiscais.",
    },
    {
        "code": "technical.read",
        "name": "Ler diagnostico tecnico",
        "description": "Consultar diagnosticos tecnicos internos do backend.",
    },
    {
        "code": "technical.run",
        "name": "Executar regressao tecnica",
        "description": "Executar regressoes tecnicas internas controladas.",
    },
]

DEFAULT_ROLES: list[dict[str, Any]] = [
    {
        "code": "admin",
        "name": "Administrador",
        "description": "Controle total de seguranÃ§a e financeiro.",
        "permissions": [permission["code"] for permission in DEFAULT_PERMISSIONS],
    },
    {
        "code": "finance_manager",
        "name": "Gestor Financeiro",
        "description": "Opera financeiro e decide aprovaÃ§Ãµes de alÃ§ada.",
        "permissions": ["finance.read", "finance.write", "payables.pay", "approval.read", "approval.decide", "reports.read"],
    },
    {
        "code": "finance_operator",
        "name": "Operador Financeiro",
        "description": "Registra pagamentos e solicita aprovaÃ§Ãµes quando necessÃ¡rio.",
        "permissions": ["finance.read", "payables.pay", "approval.read", "reports.read"],
    },
    {
        "code": "viewer",
        "name": "Leitor",
        "description": "Acesso somente leitura.",
        "permissions": ["finance.read", "approval.read", "reports.read"],
    },
]

MASTER_ROLE_CODE = "admin"

V1_APP_VIEWS: tuple[str, ...] = (
    "overview",
    "company",
    "participants",
    "catalog",
    "fiscalClassification",
    "imports",
    "orders",
    "stock",
    "financial",
    "accountsReceivable",
    "cash",
    "reconciliation",
    "cashFlow",
    "purchasesPayables",
    "managementReports",
    "security",
)

INTERNAL_APP_VIEWS: tuple[str, ...] = (
    "biAnalytics",
    "easyManagement",
    "ai",
    "productSales",
    "serviceSales",
    "marketplaces",
    "mercadoPago",
    "technicalRegression",
    "stressTests",
)

ALL_APP_VIEWS: tuple[str, ...] = (
    "overview",
    "company",
    "participants",
    "catalog",
    "fiscalClassification",
    "imports",
    "orders",
    "productSales",
    "serviceSales",
    "marketplaces",
    "mercadoPago",
    "stock",
    "financial",
    "accountsReceivable",
    "cash",
    "reconciliation",
    "cashFlow",
    "purchasesPayables",
    "managementReports",
    "biAnalytics",
    "easyManagement",
    "ai",
    "technicalRegression",
    "security",
    "stressTests",
)

FINANCIAL_APP_VIEWS: tuple[str, ...] = (
    "overview",
    "financial",
    "accountsReceivable",
    "cash",
    "reconciliation",
    "cashFlow",
    "purchasesPayables",
    "managementReports",
)

PARTICIPANT_DEPENDENT_APP_VIEWS: tuple[str, ...] = (
    "orders",
    "stock",
    "accountsReceivable",
    "cash",
    "purchasesPayables",
)

APP_VIEW_LABELS: dict[str, str] = {
    "overview": "VisÃ£o Geral",
    "company": "Empresa",
    "participants": "Participantes",
    "catalog": "Produtos",
    "fiscalClassification": "Fiscal",
    "imports": "Importacoes",
    "orders": "Pedidos",
    "productSales": "Vendas de Produtos",
    "serviceSales": "Vendas de ServiÃ§os",
    "marketplaces": "Marketplaces",
    "mercadoPago": "Mercado Pago",
    "stock": "Estoque",
    "financial": "Financeiro",
    "accountsReceivable": "Contas a Receber",
    "cash": "Recebimentos e Baixas",
    "reconciliation": "ConciliaÃ§Ã£o BancÃ¡ria",
    "cashFlow": "Fluxo de Caixa",
    "purchasesPayables": "Compras e Contas a Pagar",
    "managementReports": "RelatÃ³rios Gerenciais",
    "biAnalytics": "BI / KPIs",
    "easyManagement": "GestÃ£o FÃ¡cil",
    "ai": "InteligÃªncia Artificial",
    "technicalRegression": "RegressÃ£o TÃ©cnica",
    "security": "SeguranÃ§a e AlÃ§adas",
    "stressTests": "Stress e Testes",
}


def _exposed_app_views() -> tuple[str, ...]:
    if settings.enable_internal_modules and not settings.is_production:
        return ALL_APP_VIEWS
    return V1_APP_VIEWS


def _view_permission_code(view: str) -> str:
    return f"view.{view}"


for _view in ALL_APP_VIEWS:
    _view_code = _view_permission_code(_view)
    if not any(item["code"] == _view_code for item in DEFAULT_PERMISSIONS):
        DEFAULT_PERMISSIONS.append(
            {
                "code": _view_code,
                "name": f"Acessar aba {_view}",
                "description": f"Permite abrir a aba {_view} no frontend.",
            }
        )


def _upsert_default_role_permissions() -> None:
    role_map = {item["code"]: item for item in DEFAULT_ROLES}
    admin_permissions = [item["code"] for item in DEFAULT_PERMISSIONS]
    finance_base = {"finance.read", "payables.pay", "approval.read", "reports.read"}
    finance_views = {_view_permission_code(view) for view in FINANCIAL_APP_VIEWS}
    finance_operator_permissions = sorted(
        finance_base | finance_views | {"view.company", "view.participants"}
    )
    finance_manager_permissions = sorted(set(finance_operator_permissions) | {"approval.decide", "finance.write"})
    viewer_permissions = [_view_permission_code("overview"), _view_permission_code("company")]

    if MASTER_ROLE_CODE in role_map:
        role_map[MASTER_ROLE_CODE]["permissions"] = admin_permissions
    if "finance_manager" in role_map:
        role_map["finance_manager"]["permissions"] = finance_manager_permissions
    if "finance_operator" in role_map:
        role_map["finance_operator"]["permissions"] = finance_operator_permissions
    if "viewer" in role_map:
        role_map["viewer"]["permissions"] = viewer_permissions


_upsert_default_role_permissions()


@dataclass(frozen=True)
class SecurityPrincipal:
    user_id: str
    email: str
    full_name: str
    company_id: str
    session_id: str
    role_codes: set[str]
    permission_codes: set[str]


def _money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    ).hex()
    return password_hash, salt.hex()


def _verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    recalculated_hash, _ = _hash_password(password, salt_hex=salt_hex)
    return hmac.compare_digest(recalculated_hash, password_hash)


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _assert_company_exists(db: Session, company_id: str) -> CompanyDB:
    assert_valid_id(company_id, "emp")
    company = db.scalar(
        select(CompanyDB).where(
            CompanyDB.id == company_id,
            CompanyDB.deleted_at.is_(None),
        )
    )
    if company is None:
        raise ValueError("Empresa nÃ£o encontrada.")
    return company


def _audit_security_event(
    db: Session,
    *,
    event_type: str,
    severity: str,
    message: str,
    user_id: str | None = None,
    company_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> None:
    db.add(
        SecurityAuditEventDB(
            id=generate_id("saevt"),
            event_type=event_type,
            severity=severity,
            message=message,
            user_id=user_id,
            company_id=company_id,
            request_id=request_id,
            correlation_id=correlation_id,
            metadata_json=metadata or {},
            occurred_at=utc_now(),
        )
    )


def ensure_security_catalog(db: Session) -> dict[str, int]:
    existing_permissions = {
        row.code: row
        for row in db.scalars(select(PermissionDB)).all()
    }
    existing_roles = {
        row.code: row
        for row in db.scalars(select(RoleDB)).all()
    }

    created_permissions = 0
    for item in DEFAULT_PERMISSIONS:
        permission = existing_permissions.get(item["code"])
        if permission is not None:
            continue
        permission = PermissionDB(
            id=generate_id("perm"),
            code=item["code"],
            name=item["name"],
            description=item["description"],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(permission)
        db.flush()
        existing_permissions[item["code"]] = permission
        created_permissions += 1

    created_roles = 0
    for item in DEFAULT_ROLES:
        role = existing_roles.get(item["code"])
        if role is None:
            role = RoleDB(
                id=generate_id("role"),
                code=item["code"],
                name=item["name"],
                description=item["description"],
                is_system=True,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(role)
            db.flush()
            existing_roles[item["code"]] = role
            created_roles += 1

    existing_role_permissions = {
        (row.role_id, row.permission_id)
        for row in db.scalars(select(RolePermissionDB)).all()
    }
    created_links = 0
    for role in DEFAULT_ROLES:
        role_db = existing_roles[role["code"]]
        for permission_code in role["permissions"]:
            permission_db = existing_permissions.get(permission_code)
            if permission_db is None:
                continue
            key = (role_db.id, permission_db.id)
            if key in existing_role_permissions:
                continue
            db.add(
                RolePermissionDB(
                    id=generate_id("rperm"),
                    role_id=role_db.id,
                    permission_id=permission_db.id,
                    created_at=utc_now(),
                )
            )
            existing_role_permissions.add(key)
            created_links += 1
    db.flush()
    return {
        "created_permissions": created_permissions,
        "created_roles": created_roles,
        "created_role_permissions": created_links,
    }


def _serialize_user(user: UserDB) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _serialize_company_user(company_user: CompanyUserDB) -> dict[str, Any]:
    return {
        "id": company_user.id,
        "company_id": company_user.company_id,
        "user_id": company_user.user_id,
        "status": company_user.status,
        "is_primary": company_user.is_primary,
        "joined_at": company_user.joined_at.isoformat(),
    }


def _load_role_codes_by_user_company(db: Session, *, user_id: str, company_id: str) -> set[str]:
    statement: Select[tuple[str]] = (
        select(RoleDB.code)
        .join(UserRoleDB, UserRoleDB.role_id == RoleDB.id)
        .where(
            UserRoleDB.user_id == user_id,
            UserRoleDB.company_id == company_id,
        )
    )
    return set(db.scalars(statement).all())


def _load_permission_codes_by_user_company(db: Session, *, user_id: str, company_id: str) -> set[str]:
    statement: Select[tuple[str]] = (
        select(PermissionDB.code)
        .join(RolePermissionDB, RolePermissionDB.permission_id == PermissionDB.id)
        .join(RoleDB, RoleDB.id == RolePermissionDB.role_id)
        .join(UserRoleDB, UserRoleDB.role_id == RoleDB.id)
        .where(
            UserRoleDB.user_id == user_id,
            UserRoleDB.company_id == company_id,
        )
        .distinct()
    )
    return set(db.scalars(statement).all())


def _sanitize_allowed_views(values: list[str] | set[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return ["overview"]

    exposed_views = set(_exposed_app_views())
    normalized: set[str] = set()
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        if cleaned in exposed_views:
            normalized.add(cleaned)
            continue
        if cleaned in ALL_APP_VIEWS:
            raise ValueError(f"Aba fora do escopo comercial v1.0: {cleaned}.")

    if not normalized:
        normalized.add("overview")
    if "overview" not in normalized:
        normalized.add("overview")
    return sorted(normalized)


def _permission_codes_from_allowed_views(allowed_views: list[str]) -> set[str]:
    view_set = set(_sanitize_allowed_views(allowed_views))
    permission_codes = {_view_permission_code(view) for view in view_set}
    permission_codes.add(_view_permission_code("company"))

    if view_set.intersection(FINANCIAL_APP_VIEWS):
        permission_codes.add("finance.read")
    if view_set.intersection(PARTICIPANT_DEPENDENT_APP_VIEWS):
        permission_codes.add("view.participants")
    if "purchasesPayables" in view_set:
        permission_codes.update({"payables.pay", "approval.read"})
    if "managementReports" in view_set:
        permission_codes.add("reports.read")
    if "security" in view_set:
        permission_codes.update({"users.manage", "approval.read", "approval.decide", "payables.pay", "reports.read"})

    return permission_codes


def _allowed_views_from_access(*, role_codes: set[str], permission_codes: set[str]) -> list[str]:
    exposed_views = set(_exposed_app_views())
    if MASTER_ROLE_CODE in role_codes:
        return list(_exposed_app_views())

    views = {
        code[len("view."):]
        for code in permission_codes
        if code.startswith("view.") and code[len("view."):] in exposed_views
    }
    if views:
        return _sanitize_allowed_views(sorted(views))

    if role_codes.intersection({"finance_operator", "finance_manager"}):
        return list(FINANCIAL_APP_VIEWS)

    return ["overview"]


def _is_master_actor(principal: SecurityPrincipal) -> bool:
    return MASTER_ROLE_CODE in principal.role_codes


def _require_master_actor(principal: SecurityPrincipal) -> None:
    if _is_master_actor(principal):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Apenas usuÃ¡rio master da empresa pode gerenciar usuÃ¡rios e permissÃµes.",
    )


def _build_custom_role_code(company_id: str, allowed_views: list[str]) -> str:
    digest = hashlib.sha1(f"{company_id}|{'|'.join(allowed_views)}".encode("utf-8")).hexdigest()[:16]
    company_token = "".join(ch for ch in company_id.lower() if ch.isalnum())[:10] or "company"
    return f"custom_{company_token}_{digest}"


def _ensure_custom_role_for_allowed_views(db: Session, *, company_id: str, allowed_views: list[str]) -> str:
    normalized_views = _sanitize_allowed_views(allowed_views)
    role_code = _build_custom_role_code(company_id, normalized_views)
    permission_codes = _permission_codes_from_allowed_views(normalized_views)

    permission_rows = db.scalars(
        select(PermissionDB).where(PermissionDB.code.in_(sorted(permission_codes)))
    ).all()
    permission_map = {row.code: row for row in permission_rows}
    missing_permissions = sorted(code for code in permission_codes if code not in permission_map)
    if missing_permissions:
        raise ValueError(f"PermissÃµes nÃ£o encontradas para aba: {', '.join(missing_permissions)}.")

    role = db.scalar(select(RoleDB).where(RoleDB.code == role_code))
    now = utc_now()
    if role is None:
        role = RoleDB(
            id=generate_id("role"),
            code=role_code,
            name="Acesso personalizado por abas",
            description=f"Empresa {company_id} - abas: {', '.join(normalized_views)}",
            is_system=False,
            created_at=now,
            updated_at=now,
        )
        db.add(role)
        db.flush()
    else:
        role.updated_at = now
        role.description = f"Empresa {company_id} - abas: {', '.join(normalized_views)}"

    db.query(RolePermissionDB).filter(RolePermissionDB.role_id == role.id).delete(synchronize_session=False)
    db.flush()

    for permission_code in sorted(permission_codes):
        permission = permission_map[permission_code]
        db.add(
            RolePermissionDB(
                id=generate_id("rperm"),
                role_id=role.id,
                permission_id=permission.id,
                created_at=now,
            )
        )
    db.flush()
    return role_code


def _resolve_role_codes_for_company_user(
    db: Session,
    *,
    company_id: str,
    role_codes: list[str] | None,
    allowed_views: list[str] | None,
) -> list[str]:
    if role_codes:
        return sorted(set(role_codes))

    normalized_views = _sanitize_allowed_views(allowed_views)
    if set(normalized_views) == set(_exposed_app_views()):
        return [MASTER_ROLE_CODE]
    if set(normalized_views) == set(FINANCIAL_APP_VIEWS):
        return ["finance_operator"]
    if set(normalized_views) == {"overview"}:
        return ["viewer"]

    custom_role_code = _ensure_custom_role_for_allowed_views(
        db,
        company_id=company_id,
        allowed_views=normalized_views,
    )
    return [custom_role_code]


def _get_or_create_payment_policy(db: Session, company_id: str) -> ApprovalPolicyDB:
    policy = db.scalar(
        select(ApprovalPolicyDB).where(
            ApprovalPolicyDB.company_id == company_id,
            ApprovalPolicyDB.action_key == PAYMENT_APPROVAL_ACTION,
        )
    )
    if policy is not None:
        return policy

    policy = ApprovalPolicyDB(
        id=generate_id("apol"),
        company_id=company_id,
        action_key=PAYMENT_APPROVAL_ACTION,
        enabled=True,
        threshold_amount=Decimal("1000.00"),
        currency="BRL",
        required_permission_code=PAYMENT_APPROVAL_PERMISSION,
        allow_self_approval=False,
        metadata_json={"description": "Pagamento acima da alÃ§ada exige aprovaÃ§Ã£o."},
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(policy)
    db.flush()
    return policy


def bootstrap_admin_user(
    db: Session,
    payload: BootstrapAdminPayload,
    *,
    bootstrap_token: str | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    configured_token = (settings.bootstrap_admin_token or "").strip()
    provided_token = (bootstrap_token or "").strip()
    if (
        not settings.bootstrap_admin_enabled
        or len(configured_token) < MIN_BOOTSTRAP_TOKEN_LENGTH
        or not provided_token
        or not hmac.compare_digest(configured_token, provided_token)
    ):
        raise ValueError("Bootstrap inicial bloqueado. Configure BOOTSTRAP_ADMIN_ENABLED e X-Bootstrap-Token apenas durante setup controlado.")

    _assert_company_exists(db, payload.company_id)
    ensure_security_catalog(db)

    users_count = int(db.scalar(select(func.count()).select_from(UserDB)) or 0)
    if users_count > 0:
        raise ValueError("Bootstrap inicial jÃ¡ realizado. Use o cadastro por empresa.")

    password_hash, password_salt = _hash_password(payload.password)
    now = utc_now()

    user = UserDB(
        id=generate_id("user"),
        email=_normalize_email(payload.email),
        full_name=payload.full_name,
        password_hash=password_hash,
        password_salt=password_salt,
        status="active",
        must_change_password=False,
        last_login_at=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(user)
    db.flush()

    company_user = CompanyUserDB(
        id=generate_id("cmpusr"),
        company_id=payload.company_id,
        user_id=user.id,
        status="active",
        is_primary=True,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(company_user)
    db.flush()

    admin_role = db.scalar(select(RoleDB).where(RoleDB.code == MASTER_ROLE_CODE))
    if admin_role is None:
        raise ValueError("Papel admin nÃ£o encontrado.")

    db.add(
        UserRoleDB(
            id=generate_id("urole"),
            user_id=user.id,
            role_id=admin_role.id,
            company_id=payload.company_id,
            created_at=now,
        )
    )

    _get_or_create_payment_policy(db, payload.company_id)

    _audit_security_event(
        db,
        event_type="bootstrap_admin_created",
        severity="info",
        message="UsuÃ¡rio administrador inicial criado.",
        user_id=user.id,
        company_id=payload.company_id,
        metadata={"email": user.email},
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {
        "user": _serialize_user(user),
        "company_user": _serialize_company_user(company_user),
        "role_codes": ["admin"],
    }


def _load_user_by_email(db: Session, email: str) -> UserDB | None:
    normalized_email = _normalize_email(email)
    return db.scalar(
        select(UserDB).where(
            UserDB.email == normalized_email,
            UserDB.deleted_at.is_(None),
        )
    )


def _load_active_company_user(
    db: Session,
    *,
    company_id: str,
    user_id: str,
) -> CompanyUserDB | None:
    return db.scalar(
        select(CompanyUserDB).where(
            CompanyUserDB.company_id == company_id,
            CompanyUserDB.user_id == user_id,
            CompanyUserDB.status == "active",
        )
    )


def login(
    db: Session,
    payload: LoginPayload,
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    ensure_security_catalog(db)

    user = _load_user_by_email(db, payload.email)
    if user is None:
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="Tentativa de login com e-mail inexistente.",
            metadata={"email": _normalize_email(payload.email)},
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invÃ¡lidas.")

    if user.status != "active":
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="Tentativa de login com usuÃ¡rio inativo.",
            user_id=user.id,
            company_id=payload.company_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="UsuÃ¡rio inativo.")

    if not _verify_password(payload.password, user.password_hash, user.password_salt):
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="Tentativa de login com senha invÃ¡lida.",
            user_id=user.id,
            company_id=payload.company_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invÃ¡lidas.")

    company = _assert_company_exists(db, payload.company_id)
    if company.status != "active":
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="Tentativa de login em empresa inativa ou bloqueada.",
            user_id=user.id,
            company_id=payload.company_id,
            metadata={"company_status": company.status},
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Empresa inativa ou bloqueada.",
        )

    company_user = _load_active_company_user(db, company_id=payload.company_id, user_id=user.id)
    if company_user is None:
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="UsuÃ¡rio sem vÃ­nculo ativo com a empresa.",
            user_id=user.id,
            company_id=payload.company_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UsuÃ¡rio nÃ£o pertence Ã  empresa informada.",
        )

    role_codes = _load_role_codes_by_user_company(db, user_id=user.id, company_id=payload.company_id)
    permission_codes = _load_permission_codes_by_user_company(db, user_id=user.id, company_id=payload.company_id)
    if not role_codes or not permission_codes:
        _audit_security_event(
            db,
            event_type="login_failed",
            severity="warning",
            message="UsuÃ¡rio sem papÃ©is ou permissÃµes para a empresa.",
            user_id=user.id,
            company_id=payload.company_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UsuÃ¡rio sem permissÃµes para a empresa.",
        )

    allowed_views = _allowed_views_from_access(
        role_codes=role_codes,
        permission_codes=permission_codes,
    )

    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = utc_now()
    expires_at = now + timedelta(minutes=SESSION_DURATION_MINUTES)
    session = UserSessionDB(
        id=generate_id("sess"),
        user_id=user.id,
        company_id=payload.company_id,
        token_hash=token_hash,
        token_last4=token[-4:],
        status="active",
        issued_at=now,
        expires_at=expires_at,
        last_seen_at=now,
        revoked_at=None,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json={"request_id": request_id},
    )
    db.add(session)

    user.last_login_at = now
    user.updated_at = now

    _audit_security_event(
        db,
        event_type="login_success",
        severity="info",
        message="Login concluÃ­do com sucesso.",
        user_id=user.id,
        company_id=payload.company_id,
        metadata={"session_id": session.id},
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": expires_at.isoformat(),
        "session": {
            "id": session.id,
            "company_id": session.company_id,
            "issued_at": session.issued_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
        },
        "user": _serialize_user(user),
        "roles": sorted(role_codes),
        "permissions": sorted(permission_codes),
        "allowed_views": allowed_views,
    }


def _active_session_by_token(db: Session, token: str) -> UserSessionDB | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = utc_now()
    return db.scalar(
        select(UserSessionDB).where(
            UserSessionDB.token_hash == token_hash,
            UserSessionDB.status == "active",
            UserSessionDB.expires_at > now,
            UserSessionDB.revoked_at.is_(None),
        )
    )


def resolve_principal_by_token(db: Session, token: str) -> SecurityPrincipal:
    session = _active_session_by_token(db, token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="SessÃ£o invÃ¡lida ou expirada.")

    user = db.scalar(
        select(UserDB).where(
            UserDB.id == session.user_id,
            UserDB.deleted_at.is_(None),
        )
    )
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="UsuÃ¡rio da sessÃ£o nÃ£o estÃ¡ ativo.")

    membership_row = db.execute(
        select(CompanyUserDB.status, CompanyDB.status)
        .join(CompanyDB, CompanyDB.id == CompanyUserDB.company_id)
        .where(
            CompanyUserDB.company_id == session.company_id,
            CompanyUserDB.user_id == user.id,
            CompanyDB.deleted_at.is_(None),
        )
    ).first()
    if membership_row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UsuÃ¡rio sem vÃ­nculo ativo com a empresa da sessÃ£o.",
        )

    membership_status, company_status = membership_row
    if company_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Empresa inativa ou bloqueada.",
        )

    if membership_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UsuÃ¡rio sem vÃ­nculo ativo com a empresa da sessÃ£o.",
        )

    role_codes = _load_role_codes_by_user_company(db, user_id=user.id, company_id=session.company_id)
    permission_codes = _load_permission_codes_by_user_company(db, user_id=user.id, company_id=session.company_id)
    if not permission_codes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SessÃ£o sem permissÃµes.")

    return SecurityPrincipal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        company_id=session.company_id,
        session_id=session.id,
        role_codes=role_codes,
        permission_codes=permission_codes,
    )


def logout(
    db: Session,
    token: str,
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    session = _active_session_by_token(db, token)
    if session is None:
        return {"revoked": False}

    now = utc_now()
    session.status = "revoked"
    session.revoked_at = now
    session.last_seen_at = now

    _audit_security_event(
        db,
        event_type="logout",
        severity="info",
        message="SessÃ£o encerrada pelo usuÃ¡rio.",
        user_id=session.user_id,
        company_id=session.company_id,
        metadata={"session_id": session.id},
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {"revoked": True}


def require_permission(principal: SecurityPrincipal, permission_code: str) -> None:
    if permission_code in principal.permission_codes:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"AÃ§Ã£o bloqueada. PermissÃ£o obrigatÃ³ria: {permission_code}.",
    )


def me(principal: SecurityPrincipal) -> dict[str, Any]:
    return {
        "user_id": principal.user_id,
        "email": principal.email,
        "full_name": principal.full_name,
        "company_id": principal.company_id,
        "session_id": principal.session_id,
        "roles": sorted(principal.role_codes),
        "permissions": sorted(principal.permission_codes),
        "allowed_views": _allowed_views_from_access(
            role_codes=principal.role_codes,
            permission_codes=principal.permission_codes,
        ),
    }


def create_company_user(
    db: Session,
    payload: CreateCompanyUserPayload,
    *,
    actor: SecurityPrincipal,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    require_permission(actor, "users.manage")
    _require_master_actor(actor)
    if actor.company_id != payload.company_id:
        raise ValueError("UsuÃ¡rio autenticado sÃ³ pode gerenciar sua prÃ³pria empresa.")

    _assert_company_exists(db, payload.company_id)
    ensure_security_catalog(db)
    selected_role_codes = _resolve_role_codes_for_company_user(
        db,
        company_id=payload.company_id,
        role_codes=payload.role_codes,
        allowed_views=payload.allowed_views,
    )
    role_map = {
        row.code: row
        for row in db.scalars(select(RoleDB).where(RoleDB.code.in_(selected_role_codes))).all()
    }
    missing_roles = [code for code in selected_role_codes if code not in role_map]
    if missing_roles:
        raise ValueError(f"PapÃ©is invÃ¡lidos: {', '.join(missing_roles)}.")

    existing_user = _load_user_by_email(db, payload.email)
    now = utc_now()
    if existing_user is None:
        password_hash, password_salt = _hash_password(payload.password)
        user = UserDB(
            id=generate_id("user"),
            email=_normalize_email(payload.email),
            full_name=payload.full_name,
            password_hash=password_hash,
            password_salt=password_salt,
            status="active",
            must_change_password=True,
            last_login_at=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db.add(user)
        db.flush()
    else:
        user = existing_user
        if user.status != "active":
            user.status = "active"
        user.full_name = payload.full_name
        user.updated_at = now

    company_user = db.scalar(
        select(CompanyUserDB).where(
            CompanyUserDB.company_id == payload.company_id,
            CompanyUserDB.user_id == user.id,
        )
    )
    if company_user is None:
        company_user = CompanyUserDB(
            id=generate_id("cmpusr"),
            company_id=payload.company_id,
            user_id=user.id,
            status="active",
            is_primary=False,
            joined_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(company_user)
        db.flush()
    else:
        company_user.status = "active"
        company_user.updated_at = now

    db.query(UserRoleDB).filter(
        UserRoleDB.company_id == payload.company_id,
        UserRoleDB.user_id == user.id,
    ).delete(synchronize_session=False)
    db.flush()

    for role_code in selected_role_codes:
        role = role_map[role_code]
        db.add(
            UserRoleDB(
                id=generate_id("urole"),
                company_id=payload.company_id,
                user_id=user.id,
                role_id=role.id,
                created_at=now,
            )
        )

    permission_codes = _load_permission_codes_by_user_company(
        db,
        user_id=user.id,
        company_id=payload.company_id,
    )
    allowed_views = _allowed_views_from_access(
        role_codes=set(selected_role_codes),
        permission_codes=permission_codes,
    )

    _audit_security_event(
        db,
        event_type="company_user_upserted",
        severity="info",
        message="UsuÃ¡rio vinculado Ã  empresa com papÃ©is atualizados.",
        user_id=actor.user_id,
        company_id=actor.company_id,
        metadata={
            "target_user_id": user.id,
            "target_email": user.email,
            "roles": selected_role_codes,
            "allowed_views": allowed_views,
        },
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {
        "user": _serialize_user(user),
        "company_user": _serialize_company_user(company_user),
        "roles": selected_role_codes,
        "allowed_views": allowed_views,
    }


def update_company_user_roles(
    db: Session,
    membership_id: str,
    payload: UpdateCompanyUserRolesPayload,
    *,
    actor: SecurityPrincipal,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    require_permission(actor, "users.manage")
    _require_master_actor(actor)
    assert_valid_id(membership_id, "cmpusr")

    company_user = db.scalar(select(CompanyUserDB).where(CompanyUserDB.id == membership_id))
    if company_user is None:
        raise ValueError("VÃ­nculo empresa-usuÃ¡rio nÃ£o encontrado.")
    if company_user.company_id != actor.company_id:
        raise ValueError("Sem permissÃ£o para editar vÃ­nculo de outra empresa.")

    selected_role_codes = _resolve_role_codes_for_company_user(
        db,
        company_id=company_user.company_id,
        role_codes=payload.role_codes,
        allowed_views=payload.allowed_views,
    )
    role_map = {
        row.code: row
        for row in db.scalars(select(RoleDB).where(RoleDB.code.in_(selected_role_codes))).all()
    }
    missing_roles = [code for code in selected_role_codes if code not in role_map]
    if missing_roles:
        raise ValueError(f"PapÃ©is invÃ¡lidos: {', '.join(missing_roles)}.")

    db.query(UserRoleDB).filter(
        UserRoleDB.company_id == company_user.company_id,
        UserRoleDB.user_id == company_user.user_id,
    ).delete(synchronize_session=False)
    db.flush()

    now = utc_now()
    for role_code in selected_role_codes:
        db.add(
            UserRoleDB(
                id=generate_id("urole"),
                company_id=company_user.company_id,
                user_id=company_user.user_id,
                role_id=role_map[role_code].id,
                created_at=now,
            )
        )

    permission_codes = _load_permission_codes_by_user_company(
        db,
        user_id=company_user.user_id,
        company_id=company_user.company_id,
    )
    allowed_views = _allowed_views_from_access(
        role_codes=set(selected_role_codes),
        permission_codes=permission_codes,
    )

    _audit_security_event(
        db,
        event_type="company_user_roles_updated",
        severity="info",
        message="PapÃ©is do vÃ­nculo empresa-usuÃ¡rio atualizados.",
        user_id=actor.user_id,
        company_id=actor.company_id,
        metadata={
            "membership_id": membership_id,
            "target_user_id": company_user.user_id,
            "roles": selected_role_codes,
            "allowed_views": allowed_views,
        },
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return {
        "company_user": _serialize_company_user(company_user),
        "roles": selected_role_codes,
        "allowed_views": allowed_views,
    }


def list_company_users(db: Session, *, actor: SecurityPrincipal) -> list[dict[str, Any]]:
    require_permission(actor, "users.manage")
    _require_master_actor(actor)
    rows = db.scalars(
        select(CompanyUserDB).where(CompanyUserDB.company_id == actor.company_id)
    ).all()

    items: list[dict[str, Any]] = []
    for row in rows:
        user = db.scalar(select(UserDB).where(UserDB.id == row.user_id))
        role_codes = _load_role_codes_by_user_company(
            db,
            user_id=row.user_id,
            company_id=row.company_id,
        )
        permission_codes = _load_permission_codes_by_user_company(
            db,
            user_id=row.user_id,
            company_id=row.company_id,
        )
        items.append(
            {
                "membership": _serialize_company_user(row),
                "user": _serialize_user(user) if user is not None else None,
                "roles": sorted(role_codes),
                "permissions": sorted(permission_codes),
                "allowed_views": _allowed_views_from_access(
                    role_codes=role_codes,
                    permission_codes=permission_codes,
                ),
            }
        )
    return items


def list_roles(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(RoleDB).order_by(RoleDB.code.asc())).all()
    role_permissions_rows = db.execute(
        select(RoleDB.code, PermissionDB.code)
        .join(RolePermissionDB, RolePermissionDB.role_id == RoleDB.id)
        .join(PermissionDB, PermissionDB.id == RolePermissionDB.permission_id)
    ).all()
    permissions_by_role: dict[str, set[str]] = {}
    for role_code, permission_code in role_permissions_rows:
        permissions_by_role.setdefault(role_code, set()).add(permission_code)

    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "is_system": row.is_system,
            "permissions": sorted(permissions_by_role.get(row.code, set())),
            "allowed_views": _allowed_views_from_access(
                role_codes={row.code},
                permission_codes=permissions_by_role.get(row.code, set()),
            ),
        }
        for row in rows
    ]


def list_permissions(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(PermissionDB).order_by(PermissionDB.code.asc())).all()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
        }
        for row in rows
    ]


def get_allowed_views_catalog() -> list[dict[str, Any]]:
    financial_views = set(FINANCIAL_APP_VIEWS)
    return [
        {
            "view": view,
            "label": APP_VIEW_LABELS.get(view, view),
            "is_financial_default": view in financial_views,
            "requires_master": view == "security",
        }
        for view in _exposed_app_views()
    ]


def get_payment_approval_policy(db: Session, *, actor: SecurityPrincipal) -> dict[str, Any]:
    require_permission(actor, "approval.read")
    policy = _get_or_create_payment_policy(db, actor.company_id)
    db.commit()
    return _approval_policy_to_dict(policy)


def update_payment_approval_policy(
    db: Session,
    payload: ApprovalPolicyUpdatePayload,
    *,
    actor: SecurityPrincipal,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    require_permission(actor, "users.manage")
    policy = _get_or_create_payment_policy(db, actor.company_id)
    policy.threshold_amount = _money(payload.threshold_amount)
    policy.required_permission_code = payload.required_permission_code
    policy.allow_self_approval = payload.allow_self_approval
    policy.updated_at = utc_now()

    _audit_security_event(
        db,
        event_type="approval_policy_updated",
        severity="info",
        message="PolÃ­tica de alÃ§ada de pagamento atualizada.",
        user_id=actor.user_id,
        company_id=actor.company_id,
        metadata=_approval_policy_to_dict(policy),
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return _approval_policy_to_dict(policy)


def _approval_policy_to_dict(policy: ApprovalPolicyDB) -> dict[str, Any]:
    return {
        "id": policy.id,
        "company_id": policy.company_id,
        "action_key": policy.action_key,
        "enabled": policy.enabled,
        "threshold_amount": str(_money(policy.threshold_amount)),
        "currency": policy.currency,
        "required_permission_code": policy.required_permission_code,
        "allow_self_approval": policy.allow_self_approval,
    }


def _approval_request_to_dict(row: ApprovalRequestDB) -> dict[str, Any]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "policy_id": row.policy_id,
        "action_key": row.action_key,
        "status": row.status,
        "reason": row.reason,
        "requested_by_user_id": row.requested_by_user_id,
        "requested_amount": str(_money(row.requested_amount)),
        "currency": row.currency,
        "target_entity_type": row.target_entity_type,
        "target_entity_id": row.target_entity_id,
        "payload": row.payload_json or {},
        "decided_by_user_id": row.decided_by_user_id,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def create_payment_approval_request(
    db: Session,
    *,
    actor: SecurityPrincipal,
    financial_title_id: str,
    requested_amount: Decimal,
    payload_snapshot: dict[str, Any],
    reason: str,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    require_permission(actor, "payables.pay")
    assert_valid_id(financial_title_id, "ap")

    policy = _get_or_create_payment_policy(db, actor.company_id)
    if not policy.enabled:
        raise ValueError("PolÃ­tica de alÃ§ada de pagamento estÃ¡ desativada.")

    request_row = ApprovalRequestDB(
        id=generate_id("apreq"),
        company_id=actor.company_id,
        policy_id=policy.id,
        action_key=PAYMENT_APPROVAL_ACTION,
        status="pending",
        reason=reason,
        requested_by_user_id=actor.user_id,
        requested_amount=_money(requested_amount),
        currency=policy.currency,
        target_entity_type="financial_title",
        target_entity_id=financial_title_id,
        payload_json=payload_snapshot,
        decided_by_user_id=None,
        decided_at=None,
        expires_at=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(request_row)
    db.flush()

    _audit_security_event(
        db,
        event_type="approval_request_created",
        severity="info",
        message="SolicitaÃ§Ã£o de alÃ§ada de pagamento criada.",
        user_id=actor.user_id,
        company_id=actor.company_id,
        metadata={
            "approval_request_id": request_row.id,
            "requested_amount": str(_money(requested_amount)),
            "target_entity_id": financial_title_id,
        },
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return _approval_request_to_dict(request_row)


def list_approval_requests(
    db: Session,
    *,
    actor: SecurityPrincipal,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    require_permission(actor, "approval.read")
    statement = select(ApprovalRequestDB).where(ApprovalRequestDB.company_id == actor.company_id)
    if status_filter:
        statement = statement.where(ApprovalRequestDB.status == status_filter)
    statement = statement.order_by(ApprovalRequestDB.created_at.desc()).limit(limit).offset(offset)
    rows = db.scalars(statement).all()
    return [_approval_request_to_dict(row) for row in rows]


def decide_approval_request(
    db: Session,
    approval_request_id: str,
    payload: ApprovalDecisionPayload,
    *,
    actor: SecurityPrincipal,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    require_permission(actor, "approval.decide")
    assert_valid_id(approval_request_id, "apreq")
    row = db.scalar(select(ApprovalRequestDB).where(ApprovalRequestDB.id == approval_request_id))
    if row is None:
        raise ValueError("SolicitaÃ§Ã£o de aprovaÃ§Ã£o nÃ£o encontrada.")
    if row.company_id != actor.company_id:
        raise ValueError("SolicitaÃ§Ã£o pertence a outra empresa.")
    if row.status != "pending":
        raise ValueError("SolicitaÃ§Ã£o jÃ¡ foi decidida.")

    policy = db.scalar(select(ApprovalPolicyDB).where(ApprovalPolicyDB.id == row.policy_id))
    if policy is None:
        raise ValueError("PolÃ­tica de aprovaÃ§Ã£o nÃ£o encontrada.")
    if not policy.allow_self_approval and row.requested_by_user_id == actor.user_id:
        raise ValueError("AutoaprovaÃ§Ã£o nÃ£o permitida para esta polÃ­tica.")

    required_permission = policy.required_permission_code or PAYMENT_APPROVAL_PERMISSION
    require_permission(actor, required_permission)

    now = utc_now()
    row.status = payload.decision
    row.decided_by_user_id = actor.user_id
    row.decided_at = now
    row.updated_at = now

    db.add(
        ApprovalDecisionDB(
            id=generate_id("apdec"),
            approval_request_id=row.id,
            company_id=row.company_id,
            actor_user_id=actor.user_id,
            decision=payload.decision,
            reason=payload.reason,
            metadata_json={},
            decided_at=now,
        )
    )

    _audit_security_event(
        db,
        event_type="approval_request_decided",
        severity="info",
        message="SolicitaÃ§Ã£o de alÃ§ada decidida.",
        user_id=actor.user_id,
        company_id=actor.company_id,
        metadata={
            "approval_request_id": row.id,
            "decision": payload.decision,
            "reason": payload.reason,
        },
        request_id=request_id,
        correlation_id=correlation_id,
    )
    db.commit()
    return _approval_request_to_dict(row)


def assert_payment_within_policy_or_approved(
    db: Session,
    *,
    actor: SecurityPrincipal,
    financial_title_id: str,
    payment_amount: Decimal,
    approval_request_id: str | None,
) -> None:
    policy = _get_or_create_payment_policy(db, actor.company_id)
    threshold = _money(policy.threshold_amount)
    amount = _money(payment_amount)

    if not policy.enabled or amount <= threshold:
        return

    if approval_request_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Pagamento acima da alÃ§ada exige aprovaÃ§Ã£o prÃ©via. "
                "Crie uma solicitaÃ§Ã£o em /security/approval-requests."
            ),
        )

    assert_valid_id(approval_request_id, "apreq")
    request_row = db.scalar(select(ApprovalRequestDB).where(ApprovalRequestDB.id == approval_request_id))
    if request_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SolicitaÃ§Ã£o de aprovaÃ§Ã£o nÃ£o encontrada.")
    if request_row.company_id != actor.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SolicitaÃ§Ã£o pertence a outra empresa.")
    if request_row.status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SolicitaÃ§Ã£o de aprovaÃ§Ã£o ainda nÃ£o aprovada.")
    if request_row.target_entity_id != financial_title_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SolicitaÃ§Ã£o nÃ£o corresponde ao tÃ­tulo informado.")
    if _money(request_row.requested_amount) < amount:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valor aprovado Ã© menor que o valor deste pagamento.",
        )


def get_rules() -> dict[str, Any]:
    return {
        "module": "security",
        "purpose": "MultiusuÃ¡rio com autenticaÃ§Ã£o, papÃ©is, permissÃµes e alÃ§adas.",
        "session_duration_minutes": SESSION_DURATION_MINUTES,
        "approval_action_key": PAYMENT_APPROVAL_ACTION,
        "default_permissions": [item["code"] for item in DEFAULT_PERMISSIONS],
        "default_roles": [item["code"] for item in DEFAULT_ROLES],
        "all_app_views": list(_exposed_app_views()),
        "financial_app_views": list(FINANCIAL_APP_VIEWS),
        "critical_permissions": {
            "gravar_participantes": "participants.write",
            "gravar_catalogo": "catalog.write",
            "movimentar_estoque": "stock.move",
            "registrar_entrada_compra": "stock.purchase_entry",
            "criar_pedido": "sales.create",
            "fechar_pedido": "sales.close",
            "cancelar_pedido": "sales.cancel",
            "receber_pedido_legado": "sales.pay",
            "registrar_recebimento": "cash.receive",
            "estornar_recebimento": "cash.reverse",
            "emitir_documento_fiscal": "fiscal.issue",
            "gravar_regras_fiscais": "fiscal.write",
            "pagar_titulo": "payables.pay",
            "decidir_alcada": "approval.decide",
            "gerenciar_usuarios": "users.manage",
        },
    }


def diagnostics(db: Session) -> dict[str, Any]:
    users_count = int(db.scalar(select(func.count()).select_from(UserDB)) or 0)
    sessions_count = int(
        db.scalar(
            select(func.count()).select_from(UserSessionDB).where(UserSessionDB.status == "active")
        )
        or 0
    )
    approvals_pending = int(
        db.scalar(
            select(func.count()).select_from(ApprovalRequestDB).where(ApprovalRequestDB.status == "pending")
        )
        or 0
    )
    return {
        "module": "security",
        "status": "active",
        "users": users_count,
        "active_sessions": sessions_count,
        "pending_approvals": approvals_pending,
        "tables": [
            "users",
            "roles",
            "permissions",
            "user_roles",
            "role_permissions",
            "company_users",
            "approval_policies",
            "approval_requests",
            "approval_decisions",
            "user_sessions",
            "security_audit_events",
        ],
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Senha Mestre (reabertura de pedidos fechados)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def set_master_password(
    db: Session,
    company_id: str,
    new_password: str,
    *,
    actor: SecurityPrincipal,
) -> dict[str, Any]:
    require_permission(actor, "sales.unlock_closed")
    import bcrypt

    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = utc_now()
    existing = db.scalar(select(MasterPasswordDB).where(MasterPasswordDB.company_id == company_id))
    if existing is not None:
        existing.password_hash = password_hash
        existing.password_salt = None
        existing.set_by = actor.user_id
        existing.set_at = now
        existing.updated_at = now
    else:
        db.add(
            MasterPasswordDB(
                id=generate_id("mpwd"),
                company_id=company_id,
                password_hash=password_hash,
                password_salt=None,
                set_by=actor.user_id,
                set_at=now,
                updated_at=now,
            )
        )
    _audit_security_event(
        db,
        event_type="master_password_set",
        severity="warning",
        message="Senha mestre configurada/alterada.",
        user_id=actor.user_id,
        company_id=company_id,
    )
    db.commit()
    return {"company_id": company_id, "configured": True}


def verify_master_password(db: Session, company_id: str, password: str) -> bool:
    import bcrypt

    existing = db.scalar(select(MasterPasswordDB).where(MasterPasswordDB.company_id == company_id))
    if existing is None:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), existing.password_hash.encode("utf-8"))


def is_master_password_configured(db: Session, company_id: str) -> bool:
    existing = db.scalar(select(MasterPasswordDB).where(MasterPasswordDB.company_id == company_id))
    return existing is not None
