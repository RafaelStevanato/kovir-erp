from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.company.db_models import CompanyDB
from app.modules.security.dependencies import get_current_principal
from app.modules.security.service import SecurityPrincipal, require_permission
from app.shared.datetime import utc_now


def _run_demo_financial_flow(*, sales_count: int, purchases_count: int) -> dict[str, Any]:
    """Carrega o gerador legado de demo somente quando ele for realmente executado.

    O endpoint de demo deve permitir importar o backend mesmo quando os scripts
    locais de stress/teste não foram enviados no pacote. Sem isso, o Uvicorn quebra
    durante o import de app.main antes de qualquer rota ficar disponível.
    """
    try:
        from tools.stress_real_company_financial_demo import run as run_demo_financial_flow
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Script opcional tools.stress_real_company_financial_demo não encontrado. "
            "O backend pode iniciar normalmente, mas a geração real da demo depende "
            "desse script local. Use dry_run=true ou inclua o arquivo em backend/tools/. "
        ) from exc

    return run_demo_financial_flow(
        sales_count=sales_count,
        purchases_count=purchases_count,
    )


router = APIRouter(prefix="/demo", tags=["Demo"])
DEMO_CONFIRM_PHRASE = "DEMO_SAFE_OP"


class DemoGeneratePayload(BaseModel):
    sales: int = Field(default=40, ge=1, le=120)
    purchases: int = Field(default=25, ge=1, le=80)
    dry_run: bool = False
    confirm_phrase: str | None = None


class DemoArchivePayload(BaseModel):
    keep_latest: int = Field(default=1, ge=0, le=10)
    keep_company_id: str | None = None
    dry_run: bool = False
    confirm_phrase: str | None = None


def _api_response(success: bool, message: str, data: Any = None) -> dict[str, Any]:
    return {"success": success, "message": message, "data": data}


def _assert_demo_operation_allowed(confirm_phrase: str | None) -> None:
    environment = (settings.environment or "").strip().lower()
    if environment in {"production", "prod"} and confirm_phrase != DEMO_CONFIRM_PHRASE:
        raise ValueError(
            "Operação demo bloqueada em ambiente de produção. "
            "Use confirm_phrase=DEMO_SAFE_OP apenas se esta execução for intencional."
        )


def _assert_demo_permission(principal: SecurityPrincipal) -> None:
    require_permission(principal, "users.manage")


def _demo_company_filter():
    return or_(
        CompanyDB.legal_name.ilike("DEMO Kovir%"),
        CompanyDB.trade_name.ilike("DEMO Kovir%"),
    )


def _demo_company_to_dict(company: CompanyDB) -> dict[str, Any]:
    return {
        "id": company.id,
        "legal_name": company.legal_name,
        "trade_name": company.trade_name,
        "status": company.status,
        "created_at": company.created_at,
        "updated_at": company.updated_at,
        "deleted_at": company.deleted_at,
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_demo_company(
    payload: DemoGeneratePayload,
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    """Gera massa demo realista usando os serviços oficiais do backend.

    Este endpoint é deliberadamente síncrono e deve ser usado apenas em ambiente de
    desenvolvimento/demonstração. Ele cria dados reais de demo no banco ativo.
    """
    try:
        _assert_demo_permission(principal)
        _assert_demo_operation_allowed(payload.confirm_phrase)

        if payload.dry_run:
            return _api_response(
                success=True,
                message="DRY RUN de geração demo concluído sem gravar dados.",
                data={
                    "dry_run": True,
                    "requested_sales": payload.sales,
                    "requested_purchases": payload.purchases,
                    "environment": settings.environment,
                    "safety": {
                        "operation": "demo.generate",
                        "no_data_written": True,
                        "confirmation_required_in_production": True,
                    },
                },
            )

        report = _run_demo_financial_flow(
            sales_count=payload.sales,
            purchases_count=payload.purchases,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_api_response(
                success=False,
                message=str(exc),
                data=None,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_api_response(
                success=False,
                message=f"Falha ao gerar empresa demo: {type(exc).__name__}: {exc}",
                data=None,
            ),
        )

    if report.get("status") != "PASS":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_api_response(
                success=False,
                message="A geração da empresa demo terminou com falhas. Veja o relatório retornado.",
                data=report,
            ),
        )

    ids = report.get("ids") or {}
    opening_summary = next(
        (
            case.get("evidence", {})
            for case in report.get("cases", [])
            if case.get("name") == "12_demo_data_ready_for_frontend"
        ),
        {},
    )
    consistency_summary = next(
        (
            case.get("evidence", {})
            for case in report.get("cases", [])
            if case.get("name") == "11_relational_integrity_and_inconsistency_scan"
        ),
        {},
    )
    cash_flow_summary = next(
        (
            case.get("evidence", {})
            for case in report.get("cases", [])
            if case.get("name") == "09_cash_flow_reads_real_demo_flow"
        ),
        {},
    )

    return _api_response(
        success=True,
        message="Empresa demo gerada com sucesso.",
        data={
            "company_id": ids.get("company_id") or opening_summary.get("demo_company_id"),
            "company_name_hint": opening_summary.get("demo_company_name_hint"),
            "status": report.get("status"),
            "summary": report.get("summary"),
            "collections_summary": report.get("collections_summary"),
            "opening_summary": opening_summary,
            "operational_counts": consistency_summary.get("entity_counts", {}),
            "cash_flow_summary": cash_flow_summary.get("summary", {}),
            "pending_counts": cash_flow_summary.get("pending_counts", {}),
            "report": report,
        },
    )


@router.get("/companies")
def list_demo_companies(
    db: Session = Depends(get_db),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _assert_demo_permission(principal)
    statement = select(CompanyDB).where(_demo_company_filter())
    statement = statement.where(CompanyDB.id == principal.company_id)

    if not include_archived:
        statement = statement.where(CompanyDB.deleted_at.is_(None))

    statement = statement.order_by(CompanyDB.created_at.desc(), CompanyDB.id.desc()).limit(limit)
    companies = list(db.scalars(statement).all())

    return _api_response(
        success=True,
        message="Empresas demo carregadas com sucesso.",
        data=[_demo_company_to_dict(company) for company in companies],
    )


@router.get("/safety-rules")
def get_demo_safety_rules(
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    _assert_demo_permission(principal)
    return _api_response(
        success=True,
        message="Regras de segurança da demo carregadas com sucesso.",
        data={
            "environment": settings.environment,
            "confirm_phrase": DEMO_CONFIRM_PHRASE,
            "rules": [
                "Geração demo usa serviços reais do backend e deve rodar apenas em dev/homologação.",
                "archive-old faz soft archive em companies e preserva dados transacionais.",
                "dry_run pode ser usado para validar impacto antes de qualquer alteração.",
                "Em ambiente production/prod, operações mutáveis exigem confirm_phrase explícita.",
            ],
            "safe_endpoints": [
                "GET /demo/companies",
                "GET /demo/safety-rules",
                "POST /demo/generate (dry_run=true)",
                "POST /demo/archive-old (dry_run=true)",
            ],
        },
    )


@router.post("/archive-old")
def archive_old_demo_companies(
    payload: DemoArchivePayload,
    db: Session = Depends(get_db),
    principal: SecurityPrincipal = Depends(get_current_principal),
):
    """Arquiva empresas demo antigas sem apagar dados transacionais.

    A limpeza é propositalmente conservadora: apenas marca companies.deleted_at.
    Isso remove a demo do seletor padrão, mas preserva trilha e integridade dos
    dados filhos. Não toca em empresas que não começam com "DEMO Kovir".
    """
    try:
        _assert_demo_permission(principal)
        _assert_demo_operation_allowed(payload.confirm_phrase)
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_api_response(
                success=False,
                message=str(exc),
                data=None,
            ),
        )

    statement = (
        select(CompanyDB)
        .where(
            _demo_company_filter(),
            CompanyDB.deleted_at.is_(None),
            CompanyDB.id == principal.company_id,
        )
        .order_by(CompanyDB.created_at.desc(), CompanyDB.id.desc())
    )
    demo_companies = list(db.scalars(statement).all())

    keep_ids: set[str] = set()
    if payload.keep_company_id and payload.keep_company_id == principal.company_id:
        keep_ids.add(payload.keep_company_id)

    keep_ids.update(company.id for company in demo_companies[: payload.keep_latest])

    now = utc_now()
    archived: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []

    for company in demo_companies:
        if company.id in keep_ids:
            kept.append(_demo_company_to_dict(company))
            continue

        company.deleted_at = now
        company.updated_at = now
        company.status = "inactive"
        archived.append(_demo_company_to_dict(company))

    if payload.dry_run:
        db.rollback()
        return _api_response(
            success=True,
            message="DRY RUN de archive demo concluído sem alterar dados.",
            data={
                "dry_run": True,
                "archived_count": len(archived),
                "kept_count": len(kept),
                "archived_preview": archived,
                "kept_preview": kept,
                "mode": "soft_archive_companies_only_preview",
                "note": "Nenhuma alteração foi persistida.",
            },
        )

    db.commit()

    return _api_response(
        success=True,
        message="Empresas demo antigas arquivadas com segurança.",
        data={
            "archived_count": len(archived),
            "kept_count": len(kept),
            "archived": archived,
            "kept": kept,
            "mode": "soft_archive_companies_only",
            "note": "Dados transacionais foram preservados; a limpeza remove as demos antigas da listagem padrão de empresas.",
        },
    )
