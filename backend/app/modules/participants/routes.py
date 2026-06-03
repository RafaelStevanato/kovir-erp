from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.participants.models import ParticipantStatus, ParticipantType, PersonType
from app.modules.participants.schemas import ParticipantCreate, ParticipantUpdate
from app.modules.participants.service import (
    count_filtered_participants,
    create_participant,
    get_participant,
    get_participant_audit_events,
    get_participant_diagnostics,
    get_participant_rules,
    get_participant_summary,
    list_participants,
    update_participant,
)
from app.modules.security.dependencies import require_permission_dependency
from app.modules.security.service import SecurityPrincipal
from app.shared.audit import AuditSource
from app.shared.schemas import ApiResponse


router = APIRouter(tags=["Participants"])


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
    return request.headers.get("x-correlation-id") or request.headers.get(
        "x-request-id"
    )


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


def _resolve_company_id(company_id: str | None, principal: SecurityPrincipal) -> str:
    resolved = company_id or principal.company_id
    if resolved != principal.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Acesso bloqueado. A empresa informada não corresponde "
                "à empresa ativa da sessão."
            ),
        )
    return resolved


@router.get("/participants", response_model=ApiResponse)
def list_participants_route(
    company_id: str | None = Query(default=None),
    participant_type: ParticipantType | None = Query(default=None),
    person_type: PersonType | None = Query(default=None),
    status_filter: ParticipantStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    try:
        resolved_company_id = _resolve_company_id(company_id, principal)
        participants = list_participants(
            db=db,
            company_id=resolved_company_id,
            participant_type=participant_type,
            person_type=person_type,
            status=status_filter,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = count_filtered_participants(
            db=db,
            company_id=resolved_company_id,
            participant_type=participant_type,
            person_type=person_type,
            status=status_filter,
            search=search,
        )

        return _api_response(
            success=True,
            message="Participantes carregados com sucesso.",
            data={"items": participants, "total": total, "limit": limit, "offset": offset},
        )
    except ValueError as error:
        return _error_response(error)


@router.post(
    "/participants",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_participant_route(
    payload: ParticipantCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("participants.write")),
):
    try:
        if payload.company_id != principal.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A empresa do participante deve ser a empresa ativa da sessão.",
            )
        participant = create_participant(
            db=db,
            payload=payload,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Participante criado com sucesso.",
            data=participant,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/participants/summary", response_model=ApiResponse)
def get_participant_summary_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    resolved_company_id = _resolve_company_id(company_id, principal)
    return _api_response(
        success=True,
        message="Resumo de participantes carregado com sucesso.",
        data=get_participant_summary(db, company_id=resolved_company_id),
    )


@router.get("/participants/{participant_id}", response_model=ApiResponse)
def get_participant_route(
    participant_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    try:
        participant = get_participant(
            db,
            participant_id,
            expected_company_id=principal.company_id,
        )

        return _api_response(
            success=True,
            message="Participante carregado com sucesso.",
            data=participant,
        )
    except ValueError as error:
        return _error_response(error)


@router.patch("/participants/{participant_id}", response_model=ApiResponse)
def update_participant_route(
    participant_id: str,
    payload: ParticipantUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("participants.write")),
):
    try:
        participant = update_participant(
            db=db,
            participant_id=participant_id,
            payload=payload,
            expected_company_id=principal.company_id,
            actor_id=principal.user_id,
            source=AuditSource.API,
            request_id=_request_id_from_request(request),
            correlation_id=_correlation_id_from_request(request),
        )

        return _api_response(
            success=True,
            message="Participante atualizado com sucesso.",
            data=participant,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/participants/{participant_id}/audit", response_model=ApiResponse)
def get_participant_audit_events_route(
    participant_id: str,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    try:
        audit_events = get_participant_audit_events(
            db,
            participant_id,
            expected_company_id=principal.company_id,
        )

        return _api_response(
            success=True,
            message="Eventos de auditoria do participante carregados com sucesso.",
            data=audit_events,
        )
    except ValueError as error:
        return _error_response(error)


@router.get("/system/participant-rules", response_model=ApiResponse)
def get_participant_rules_route(
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    _ = principal
    return _api_response(
        success=True,
        message="Regras de participantes do Kovir carregadas com sucesso.",
        data=get_participant_rules(),
    )


@router.get("/system/participant-diagnostics", response_model=ApiResponse)
def get_participant_diagnostics_route(
    company_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(require_permission_dependency("view.participants")),
):
    resolved_company_id = _resolve_company_id(company_id, principal)
    return _api_response(
        success=True,
        message="Diagnóstico do módulo participants carregado com sucesso.",
        data=get_participant_diagnostics(db, company_id=resolved_company_id),
    )
