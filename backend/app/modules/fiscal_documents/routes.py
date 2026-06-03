from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.fiscal_documents.db_models import FiscalDocumentDB
from app.modules.fiscal_documents.focus_nfe_client import FocusNFeError
from app.modules.fiscal_documents.repository import get_fiscal_document_by_id, get_fiscal_documents_for_sale
from app.modules.fiscal_documents.schemas import FiscalDocumentCancelRequest
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.modules.fiscal_documents.service import (
    cancel_fiscal_document,
    get_fiscal_documents_for_sale_dict,
    sync_fiscal_document_status,
)
from app.shared.schemas import ApiResponse

router = APIRouter(tags=["Fiscal Documents"])


def _api_response(*, success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=_api_response(success=False, message=message),
    )


def _get_doc_or_404(db: Session, doc_id: str) -> FiscalDocumentDB:
    doc = get_fiscal_document_by_id(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento fiscal não encontrado.")
    return doc


@router.get("/fiscal-documents/sale/{sale_id}", response_model=ApiResponse)
def list_fiscal_documents_for_sale_route(
    sale_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.issue")),
):
    docs = get_fiscal_documents_for_sale_dict(db, sale_id)
    return _api_response(
        success=True,
        message=f"{len(docs)} documento(s) fiscal(is) encontrado(s).",
        data=docs,
    )


@router.post("/fiscal-documents/{doc_id}/sync-status", response_model=ApiResponse)
def sync_fiscal_document_status_route(
    doc_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.issue")),
):
    doc = _get_doc_or_404(db, doc_id)
    try:
        result = sync_fiscal_document_status(db, doc)
        return _api_response(
            success=True,
            message="Status do documento fiscal sincronizado.",
            data=result,
        )
    except FocusNFeError as exc:
        return _error_response(f"Erro Focus NFe: {exc}")
    except ValueError as exc:
        return _error_response(str(exc))


@router.delete("/fiscal-documents/{doc_id}", response_model=ApiResponse)
def cancel_fiscal_document_route(
    doc_id: str,
    payload: FiscalDocumentCancelRequest,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.issue")),
):
    doc = _get_doc_or_404(db, doc_id)
    if doc.status != "authorized":
        return _error_response("Apenas documentos autorizados podem ser cancelados.", status_code=422)

    try:
        result = cancel_fiscal_document(db, doc, payload.justificativa)
        return _api_response(
            success=True,
            message="Cancelamento enviado para a Focus NFe.",
            data=result,
        )
    except FocusNFeError as exc:
        return _error_response(f"Erro Focus NFe: {exc}")
    except ValueError as exc:
        return _error_response(str(exc))
