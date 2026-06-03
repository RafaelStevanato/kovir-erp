import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.shared.exceptions import KovirException, NotFoundException

logger = logging.getLogger(__name__)


async def not_found_exception_handler(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": str(exc),
            "data": None,
        },
    )


async def kovir_exception_handler(request: Request, exc: KovirException):
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": str(exc),
            "data": None,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "Erro interno nao tratado na API request_id=%s path=%s method=%s",
        request_id,
        request.url.path,
        request.method,
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Erro interno do servidor.",
            "data": None,
        },
        headers=headers,
    )
