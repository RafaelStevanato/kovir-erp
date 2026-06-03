from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal
from app.shared.ids import split_id

PUBLIC_PATHS = {
    "/",
    "/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
}

PUBLIC_PATH_PREFIXES = (
    "/docs/",
    "/redoc/",
)

TENANT_TABLE_BY_PREFIX: dict[str, tuple[str, bool]] = {
    "part": ("participants", True),
    "item": ("catalog_items", True),
    "fprof": ("fiscal_profiles", True),
    "fclass": ("fiscal_classifications", True),
    "fiscalrule": ("catalog_item_fiscal_rules", True),
    "sale": ("sales", False),
    "salehist": ("sale_status_history", False),
    "saleitem": ("sale_items", False),
    "salepay": ("sale_payment_plans", False),
    "buy": ("purchases", True),
    "buyhist": ("purchase_status_history", False),
    "buyitem": ("purchase_items", False),
    "ar": ("financial_titles", True),
    "ap": ("financial_titles", True),
    "arhist": ("financial_title_history", False),
    "aphist": ("financial_title_history", False),
    "arlink": ("sale_financial_links", False),
    "aplink": ("purchase_financial_links", False),
    "cash": ("financial_movements", False),
    "cashbal": ("financial_account_balances", False),
    "sett": ("settlements", False),
    "bankacc": ("financial_accounts", True),
    "cat": ("financial_categories", True),
    "cc": ("cost_centers", True),
    "acc": ("chart_accounts", True),
    "term": ("payment_terms", True),
    "paym": ("payment_methods", True),
    "fclose": ("financial_period_closures", False),
    "opnat": ("operation_natures", True),
    "loc": ("stock_locations", True),
    "stmov": ("stock_movements", False),
    "stlot": ("stock_lots", False),
    "stocklink": ("sale_stock_links", False),
    "stpin": ("stock_purchase_entries", False),
    "stpini": ("stock_purchase_entry_items", False),
    "stmtimp": ("bank_statement_imports", False),
    "stmtln": ("bank_statement_lines", False),
    "recmatch": ("reconciliation_matches", False),
    "mkacc": ("marketplace_accounts", True),
    "mksync": ("marketplace_sync_runs", False),
    "mkord": ("marketplace_external_orders", False),
    "mkpay": ("marketplace_payment_events", False),
    "mpacc": ("mercado_pago_accounts", True),
    "mpoauth": ("mercado_pago_oauth_states", False),
    "mpweb": ("mercado_pago_webhook_events", False),
    "mppref": ("mercado_pago_checkout_preferences", False),
    "mppay": ("mercado_pago_payments", False),
    "mprel": ("mercado_pago_releases", False),
    "mpref": ("mercado_pago_refunds", False),
    "mpchg": ("mercado_pago_chargebacks", False),
    "sess": ("user_sessions", False),
    "cmpusr": ("company_users", False),
    "urole": ("user_roles", False),
    "apol": ("approval_policies", False),
    "apreq": ("approval_requests", False),
    "apdec": ("approval_decisions", False),
    "saevt": ("security_audit_events", False),
    "audit": ("audit_events", False),
}


def _normalize_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return "/"
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


def _is_public_path(path: str) -> bool:
    normalized = _normalize_path(path)
    if normalized in PUBLIC_PATHS:
        return True
    return any(normalized.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _bootstrap_token_is_valid(request: Request) -> bool:
    configured_token = (settings.bootstrap_admin_token or "").strip()
    provided_token = (request.headers.get("x-bootstrap-token") or "").strip()
    if not settings.bootstrap_admin_enabled or not configured_token or not provided_token:
        return False
    return hmac.compare_digest(configured_token, provided_token)


def _bootstrap_admin_is_allowed(db: Session, request: Request) -> bool:
    if not _bootstrap_token_is_valid(request):
        return False

    try:
        users_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE deleted_at IS NULL
                    """
                )
            ).scalar_one()
            or 0
        )
    except Exception:
        return False

    return users_count == 0


def _is_id_param_key(key: str) -> bool:
    normalized = key.strip().lower()
    if normalized == "company_id":
        return True
    if normalized == "id":
        return True
    if normalized.endswith("_id"):
        return True
    if normalized.endswith("_ids"):
        return True
    return False


def _maybe_collect_candidate_id(value: Any, collector: set[str]) -> None:
    if not isinstance(value, str):
        return

    normalized = value.strip().lower()
    if not normalized:
        return

    try:
        prefix, _ = split_id(normalized)
    except ValueError:
        return

    if prefix == "emp" or prefix in TENANT_TABLE_BY_PREFIX:
        collector.add(normalized)


def _collect_ids_from_named_value(
    key: str,
    value: Any,
    *,
    explicit_company_ids: set[str],
    candidate_entity_ids: set[str],
) -> None:
    normalized_key = key.strip().lower()

    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            _collect_ids_from_named_value(
                nested_key,
                nested_value,
                explicit_company_ids=explicit_company_ids,
                candidate_entity_ids=candidate_entity_ids,
            )
        return

    if isinstance(value, list):
        for item in value:
            _collect_ids_from_named_value(
                normalized_key,
                item,
                explicit_company_ids=explicit_company_ids,
                candidate_entity_ids=candidate_entity_ids,
            )
        return

    if not isinstance(value, str):
        return

    raw = value.strip()
    if not raw:
        return

    if normalized_key == "company_id":
        explicit_company_ids.add(raw.lower())

    if not _is_id_param_key(normalized_key):
        return

    if normalized_key.endswith("_ids"):
        for token in raw.split(","):
            _maybe_collect_candidate_id(token, candidate_entity_ids)
        return

    _maybe_collect_candidate_id(raw, candidate_entity_ids)


async def _collect_request_scope_values(request: Request) -> tuple[set[str], set[str]]:
    explicit_company_ids: set[str] = set()
    candidate_entity_ids: set[str] = set()

    for key, value in request.query_params.multi_items():
        _collect_ids_from_named_value(
            key,
            value,
            explicit_company_ids=explicit_company_ids,
            candidate_entity_ids=candidate_entity_ids,
        )

    for key, value in request.path_params.items():
        _collect_ids_from_named_value(
            key,
            value,
            explicit_company_ids=explicit_company_ids,
            candidate_entity_ids=candidate_entity_ids,
        )

    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        return explicit_company_ids, candidate_entity_ids

    body_bytes = await request.body()
    if not body_bytes:
        return explicit_company_ids, candidate_entity_ids

    try:
        body_payload = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return explicit_company_ids, candidate_entity_ids

    if isinstance(body_payload, dict):
        for key, value in body_payload.items():
            _collect_ids_from_named_value(
                key,
                value,
                explicit_company_ids=explicit_company_ids,
                candidate_entity_ids=candidate_entity_ids,
            )
    elif isinstance(body_payload, list):
        for item in body_payload:
            _collect_ids_from_named_value(
                "id",
                item,
                explicit_company_ids=explicit_company_ids,
                candidate_entity_ids=candidate_entity_ids,
            )

    return explicit_company_ids, candidate_entity_ids


def _resolve_owner_company_id(db: Session, entity_id: str) -> str | None:
    try:
        prefix, _ = split_id(entity_id)
    except ValueError:
        return None

    if prefix == "emp":
        return entity_id

    table_meta = TENANT_TABLE_BY_PREFIX.get(prefix)
    if table_meta is None:
        return None

    table_name, has_deleted_at = table_meta
    sql = f"SELECT company_id FROM {table_name} WHERE id = :entity_id"
    if has_deleted_at:
        sql += " AND deleted_at IS NULL"

    return db.execute(text(sql), {"entity_id": entity_id}).scalar_one_or_none()


def _assert_same_company(
    *,
    request_path: str,
    principal: SecurityPrincipal,
    explicit_company_ids: set[str],
    candidate_entity_ids: set[str],
    db: Session,
) -> None:
    for company_id in explicit_company_ids:
        if company_id and company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Acesso bloqueado. A sessÃ£o estÃ¡ vinculada Ã  empresa {principal.company_id} "
                    f"e a requisiÃ§Ã£o tentou acessar {company_id} em {request_path}."
                ),
            )

    for entity_id in candidate_entity_ids:
        owner_company_id = _resolve_owner_company_id(db, entity_id)
        if owner_company_id is None:
            continue
        if owner_company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Acesso bloqueado. O recurso {entity_id} pertence Ã  empresa {owner_company_id} "
                    f"e a sessÃ£o atual pertence Ã  empresa {principal.company_id}."
                ),
            )


async def enforce_session_tenant_scope(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    if request.method.upper() == "OPTIONS":
        return

    normalized_path = _normalize_path(request.url.path)
    if normalized_path == "/auth/bootstrap-admin":
        if _bootstrap_admin_is_allowed(db, request):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Bootstrap inicial desativado. "
                "Use BOOTSTRAP_ADMIN_ENABLED com X-Bootstrap-Token apenas durante setup controlado."
            ),
        )

    if _is_public_path(normalized_path):
        return

    principal = get_current_principal(request=request, db=db)
    request.state.security_principal = principal

    explicit_company_ids, candidate_entity_ids = await _collect_request_scope_values(
        request
    )
    _assert_same_company(
        request_path=normalized_path,
        principal=principal,
        explicit_company_ids=explicit_company_ids,
        candidate_entity_ids=candidate_entity_ids,
        db=db,
    )

