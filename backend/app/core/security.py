from __future__ import annotations

import re
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _safe_request_id(value: str | None) -> str:
    if value and _REQUEST_ID_PATTERN.match(value):
        return value
    return str(uuid4())


def build_content_security_policy() -> str:
    """Política CSP conservadora para a API e documentação local.

    O frontend estático também recebe CSP no Vite dev/preview e no arquivo
    frontend/public/_headers para deploys estáticos compatíveis.
    """

    connect_sources = ["'self'", *settings.resolved_cors_allowed_origins]
    if not settings.is_production:
        connect_sources.extend(
            [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        )
    connect_sources = list(dict.fromkeys(connect_sources))

    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "img-src 'self' data: https://fastapi.tiangolo.com",
        "font-src 'self' data: https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "connect-src " + " ".join(connect_sources),
    ]

    if settings.is_production:
        directives.append("upgrade-insecure-requests")

    return "; ".join(directives)


SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), autoplay=(), camera=(), clipboard-read=(), "
        "clipboard-write=(self), geolocation=(), gyroscope=(), magnetometer=(), "
        "microphone=(), payment=(), usb=(), interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
    "Cross-Origin-Resource-Policy": "same-site",
    "X-Permitted-Cross-Domain-Policies": "none",
    "X-DNS-Prefetch-Control": "off",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = _safe_request_id(request.headers.get("x-request-id"))
        correlation_id = _safe_request_id(request.headers.get("x-correlation-id"))

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        max_bytes = settings.max_request_body_bytes
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                size = 0

            if max_bytes > 0 and size > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "message": "Requisição muito grande para o limite configurado.",
                        "data": None,
                    },
                    headers={"X-Request-ID": getattr(request.state, "request_id", str(uuid4()))},
                )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if not settings.security_headers_enabled:
            return response

        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers.setdefault(header_name, header_value)

        csp_header_name = (
            "Content-Security-Policy-Report-Only"
            if settings.csp_report_only
            else "Content-Security-Policy"
        )
        response.headers.setdefault(csp_header_name, build_content_security_policy())

        if settings.hsts_enabled:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={settings.hsts_max_age_seconds}; includeSubDomains",
            )

        response.headers.setdefault("Cache-Control", "no-store")
        return response
