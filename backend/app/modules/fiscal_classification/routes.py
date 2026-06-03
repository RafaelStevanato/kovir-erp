from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.fiscal_classification.models import (
    FiscalAppliesTo,
    FiscalProfileType,
    FiscalRecordStatus,
    TaxRegimeScope,
)
from app.modules.fiscal_classification.schemas import (
    FiscalClassificationCreate,
    FiscalClassificationUpdate,
    FiscalProfileCreate,
    FiscalProfileUpdate,
)
from app.modules.fiscal_classification.service import (
    count_fiscal_classifications,
    count_fiscal_profiles,
    create_fiscal_classification,
    create_fiscal_profile,
    get_fiscal_classification,
    get_fiscal_classification_audit,
    get_fiscal_diagnostics,
    get_fiscal_profile,
    get_fiscal_profile_audit,
    get_fiscal_rules,
    list_fiscal_classifications,
    list_fiscal_profiles,
    update_fiscal_classification,
    update_fiscal_profile,
)
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(prefix="/fiscal", tags=["Fiscal Classification"])


def _api_response(
    *,
    success: bool,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": data,
    }


def _request_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-request-id")


def _correlation_id_from_request(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get("x-request-id")


def _error_response(error: ValueError) -> JSONResponse:
    message = str(error)
    status_code = status.HTTP_400_BAD_REQUEST

    if "não encontrado" in message.lower() or "não encontrada" in message.lower():
        status_code = status.HTTP_404_NOT_FOUND

    return JSONResponse(
        status_code=status_code,
        content=_api_response(
            success=False,
            message=message,
            data=None,
        ),
    )


@router.get("/profiles", response_model=ApiResponse)
def list_profiles(
    company_id: str | None = Query(default=None),
    status_filter: FiscalRecordStatus | None = Query(default=None),
    profile_type: FiscalProfileType | None = Query(default=None),
    applies_to: FiscalAppliesTo | None = Query(default=None),
    tax_regime: TaxRegimeScope | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        resolved_company_id = company_id or principal.company_id
        items = list_fiscal_profiles(
            db=db,
            company_id=resolved_company_id,
            status_filter=status_filter,
            profile_type=profile_type,
            applies_to=applies_to,
            tax_regime=tax_regime,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = count_fiscal_profiles(
            db=db,
            company_id=resolved_company_id,
            status_filter=status_filter,
            profile_type=profile_type,
            applies_to=applies_to,
            tax_regime=tax_regime,
            search=search,
        )

        return _api_response(
            success=True,
            message="Perfis fiscais listados com sucesso.",
            data={
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.post("/profiles", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: FiscalProfileCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.write")),
) -> dict[str, Any] | JSONResponse:
    try:
        profile = create_fiscal_profile(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Perfil fiscal criado com sucesso.",
            data=profile,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/profiles/{profile_id}", response_model=ApiResponse)
def get_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        return _api_response(
            success=True,
            message="Perfil fiscal encontrado com sucesso.",
            data=get_fiscal_profile(db, profile_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/profiles/{profile_id}", response_model=ApiResponse)
def update_profile(
    profile_id: str,
    payload: FiscalProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.write")),
) -> dict[str, Any] | JSONResponse:
    try:
        profile = update_fiscal_profile(
            db=db,
            profile_id=profile_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Perfil fiscal atualizado com sucesso.",
            data=profile,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/profiles/{profile_id}/audit", response_model=ApiResponse)
def get_profile_audit(
    profile_id: str,
    db: Session = Depends(get_db),
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        events = get_fiscal_profile_audit(db, profile_id)

        return _api_response(
            success=True,
            message="Auditoria do perfil fiscal listada com sucesso.",
            data={
                "items": events,
                "total": len(events),
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/classifications", response_model=ApiResponse)
def list_classifications(
    company_id: str | None = Query(default=None),
    status_filter: FiscalRecordStatus | None = Query(default=None),
    item_type: FiscalAppliesTo | None = Query(default=None),
    tax_regime: TaxRegimeScope | None = Query(default=None),
    ncm: str | None = Query(default=None),
    nbs: str | None = Query(default=None),
    cfop: str | None = Query(default=None),
    cst_ibs_cbs: str | None = Query(default=None),
    cclass_trib: str | None = Query(default=None),
    subject_to_ibs_cbs: bool | None = Query(default=None),
    subject_to_is: bool | None = Query(default=None),
    valid_on: date | None = Query(default=None),
    validity_filter: str | None = Query(default=None, pattern="^(current|future|expired)$"),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        resolved_company_id = company_id or principal.company_id
        items = list_fiscal_classifications(
            db=db,
            company_id=resolved_company_id,
            status_filter=status_filter,
            item_type=item_type,
            tax_regime=tax_regime,
            ncm=ncm,
            nbs=nbs,
            cfop=cfop,
            cst_ibs_cbs=cst_ibs_cbs,
            cclass_trib=cclass_trib,
            subject_to_ibs_cbs=subject_to_ibs_cbs,
            subject_to_is=subject_to_is,
            valid_on=valid_on,
            validity_filter=validity_filter,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = count_fiscal_classifications(
            db=db,
            company_id=resolved_company_id,
            status_filter=status_filter,
            item_type=item_type,
            tax_regime=tax_regime,
            ncm=ncm,
            nbs=nbs,
            cfop=cfop,
            cst_ibs_cbs=cst_ibs_cbs,
            cclass_trib=cclass_trib,
            subject_to_ibs_cbs=subject_to_ibs_cbs,
            subject_to_is=subject_to_is,
            valid_on=valid_on,
            validity_filter=validity_filter,
            search=search,
        )

        return _api_response(
            success=True,
            message="Classificações fiscais listadas com sucesso.",
            data={
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.post(
    "/classifications",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_classification(
    payload: FiscalClassificationCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.write")),
) -> dict[str, Any] | JSONResponse:
    try:
        classification = create_fiscal_classification(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Classificação fiscal criada com sucesso.",
            data=classification,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/classifications/{classification_id}", response_model=ApiResponse)
def get_classification(
    classification_id: str,
    db: Session = Depends(get_db),
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        return _api_response(
            success=True,
            message="Classificação fiscal encontrada com sucesso.",
            data=get_fiscal_classification(db, classification_id),
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/classifications/{classification_id}", response_model=ApiResponse)
def update_classification(
    classification_id: str,
    payload: FiscalClassificationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("fiscal.write")),
) -> dict[str, Any] | JSONResponse:
    try:
        classification = update_fiscal_classification(
            db=db,
            classification_id=classification_id,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Classificação fiscal atualizada com sucesso.",
            data=classification,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/classifications/{classification_id}/audit", response_model=ApiResponse)
def get_classification_audit(
    classification_id: str,
    db: Session = Depends(get_db),
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any] | JSONResponse:
    try:
        events = get_fiscal_classification_audit(db, classification_id)

        return _api_response(
            success=True,
            message="Auditoria da classificação fiscal listada com sucesso.",
            data={
                "items": events,
                "total": len(events),
            },
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/rules", response_model=ApiResponse)
def fiscal_rules(
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any]:
    return _api_response(
        success=True,
        message="Regras do módulo fiscal retornadas com sucesso.",
        data=get_fiscal_rules(),
    )


@router.get("/diagnostics", response_model=ApiResponse)
def fiscal_diagnostics(
    db: Session = Depends(get_db),
    _principal: SecurityPrincipal = Depends(require_permission_dependency("view.fiscalClassification")),
) -> dict[str, Any]:
    return _api_response(
        success=True,
        message="Diagnóstico fiscal retornado com sucesso.",
        data=get_fiscal_diagnostics(db),
    )
