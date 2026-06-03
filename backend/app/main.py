import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import check_database_connection
from app.core.exception_handlers import (
    kovir_exception_handler,
    not_found_exception_handler,
    unhandled_exception_handler,
)
from app.core.logging import configure_logging
from app.core.routes import router
from app.core.security import (
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.shared.exceptions import KovirException, NotFoundException

configure_logging()
logger = logging.getLogger(__name__)


def _ensure_schema_columns() -> None:
    """Fallback DDL legado permitido apenas em desenvolvimento local e opt-in."""
    if not settings.is_local_development or not settings.ddl_fallback_enabled:
        raise RuntimeError("Fallback DDL bloqueado fora de desenvolvimento local opt-in.")

    try:
        from sqlalchemy import text

        from app.core.database import engine

        ddl_statements = [
            "ALTER TABLE fiscal_classifications ADD COLUMN IF NOT EXISTS cest VARCHAR(7)",
            "ALTER TABLE fiscal_classifications ADD COLUMN IF NOT EXISTS ex_tipi VARCHAR(3)",
            "ALTER TABLE fiscal_classifications ADD COLUMN IF NOT EXISTS origem_mercadoria VARCHAR(1)",
            "CREATE INDEX IF NOT EXISTS ix_settlements_competency_date ON settlements (competency_date)",
            "CREATE INDEX IF NOT EXISTS ix_settlements_payment_method_id ON settlements (payment_method_id)",
            """CREATE TABLE IF NOT EXISTS fiscal_documents (
                id VARCHAR(80) PRIMARY KEY,
                company_id VARCHAR(80) NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
                sale_id VARCHAR(80) NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
                document_type VARCHAR(20) NOT NULL,
                model VARCHAR(5),
                serie VARCHAR(3),
                number VARCHAR(20),
                reference VARCHAR(120) NOT NULL,
                status VARCHAR(40) NOT NULL DEFAULT 'pending',
                focus_status VARCHAR(60),
                focus_response_json TEXT,
                access_key VARCHAR(50),
                protocol VARCHAR(30),
                error_code VARCHAR(20),
                error_message TEXT,
                danfe_url TEXT,
                xml_url TEXT,
                issued_at TIMESTAMPTZ,
                authorized_at TIMESTAMPTZ,
                cancelled_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS ix_fiscal_documents_company_id ON fiscal_documents (company_id)",
            "CREATE INDEX IF NOT EXISTS ix_fiscal_documents_sale_id ON fiscal_documents (sale_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_fiscal_documents_reference ON fiscal_documents (reference)",
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS crt VARCHAR(1)",
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS nfe_serie VARCHAR(3) NOT NULL DEFAULT '1'",
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS nfce_serie VARCHAR(3) NOT NULL DEFAULT '1'",
            "ALTER TABLE companies ADD COLUMN IF NOT EXISTS focus_nfe_token VARCHAR(255)",
        ]

        applied = 0
        skipped = 0
        for statement in ddl_statements:
            try:
                with engine.begin() as connection:
                    connection.execute(text(statement))
                applied += 1
            except Exception as statement_error:
                message = str(statement_error).lower()
                if any(token in message for token in ("already exists", "duplicate column", "ja existe")):
                    skipped += 1
                    continue
                logger.error("Fallback DDL falhou (%s...): %s", statement[:60], statement_error)
                skipped += 1

        logger.warning("Fallback DDL local executado: %d aplicados, %d ignorados.", applied, skipped)
    except Exception:
        logger.exception("Erro critico no fallback DDL local.")
        raise


def _run_migrations() -> None:
    """Executa Alembic somente quando AUTO_MIGRATE_ON_STARTUP estiver ativo fora de producao."""
    if settings.is_production:
        raise RuntimeError("Alembic automatico no startup e bloqueado em producao.")

    try:
        from alembic import command
        from alembic.config import Config

        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        command.upgrade(alembic_cfg, "head")
        logger.info("Migrations aplicadas com sucesso via startup opt-in.")
    except Exception:
        logger.exception("Alembic opt-in no startup falhou.")
        if settings.ddl_fallback_enabled and settings.is_local_development:
            logger.warning("Tentando fallback DDL local por configuracao explicita.")
            _ensure_schema_columns()
            return
        raise


def _run_startup_checks() -> None:
    settings.validate_runtime_configuration()

    if settings.auto_migrate_on_startup:
        _run_migrations()
        return

    logger.info("Migracao automatica desativada. Execute 'alembic upgrade head' no deploy.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _run_startup_checks()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Backend principal do Kovir ERP",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.resolved_cors_allowed_origins,
    allow_origin_regex=settings.resolved_cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(KovirException, kovir_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health", include_in_schema=False)
def health_check(response: Response) -> dict[str, object]:
    database_health = check_database_connection()
    if database_health.get("online") is not True:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "success": database_health.get("online") is True,
        "database_online": database_health.get("online") is True,
    }


app.include_router(router)
