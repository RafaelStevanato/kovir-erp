from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.security.service import SecurityPrincipal, require_permission, resolve_principal_by_token


def _extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer obrigatório.",
        )
    return token.strip()


def get_current_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> SecurityPrincipal:
    cached_principal = getattr(request.state, "security_principal", None)
    if isinstance(cached_principal, SecurityPrincipal):
        return cached_principal

    token = _extract_bearer_token(request)
    principal = resolve_principal_by_token(db, token)
    request.state.security_principal = principal
    return principal


def require_permission_dependency(permission_code: str) -> Callable[[SecurityPrincipal], SecurityPrincipal]:
    def dependency(principal: SecurityPrincipal = Depends(get_current_principal)) -> SecurityPrincipal:
        require_permission(principal, permission_code)
        return principal

    return dependency


def require_internal_modules_enabled() -> None:
    if settings.enable_internal_modules and not settings.is_production:
        return

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Modulo interno indisponivel.",
    )
