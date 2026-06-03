from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet
from urllib.parse import parse_qs, urlparse

LEGACY_BRANDING_TOKEN = "flu" + "xor"


class Settings(BaseSettings):
    app_name: str = "Kovir ERP API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    postgres_db: str = "kovir_erp"
    postgres_user: str = "kovir"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: str | None = Field(default=None)

    auto_migrate_on_startup: bool = False
    ddl_fallback_enabled: bool = False
    enable_internal_modules: bool = False

    bootstrap_admin_enabled: bool = False
    bootstrap_admin_token: str = ""
    secret_encryption_key: str = ""

    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_allow_origin_regex: str | None = None

    log_level: str = "INFO"
    log_format: str = "json"

    max_request_body_bytes: int = 10 * 1024 * 1024
    security_headers_enabled: bool = True
    csp_report_only: bool = False
    hsts_enabled: bool = False
    hsts_max_age_seconds: int = 15552000

    # Focus NFe - SaaS para emissao de NF-e/NFC-e.
    focus_nfe_token: str = ""
    focus_nfe_environment: str = "homologacao"  # "homologacao" ou "producao"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def normalized_environment(self) -> str:
        return (self.environment or "development").strip().lower()

    @property
    def is_production(self) -> bool:
        return self.normalized_environment in {"production", "prod"}

    @property
    def is_local_development(self) -> bool:
        return self.normalized_environment in {"development", "dev", "local", "test"}

    @property
    def resolved_cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in (self.cors_allowed_origins or "").split(",")
            if origin.strip()
        ]

    @property
    def resolved_cors_allow_origin_regex(self) -> str | None:
        regex = (self.cors_allow_origin_regex or "").strip()
        return regex or None

    def _validate_production_database_url(self, errors: list[str]) -> None:
        database_url = (self.database_url or "").strip()
        if not database_url:
            return

        if any(token in database_url.lower() for token in ("placeholder", "<", ">")):
            errors.append("DATABASE_URL de producao nao pode conter placeholder.")

        try:
            parsed = urlparse(database_url)
            port = parsed.port
        except ValueError:
            errors.append("DATABASE_URL deve ser uma URL PostgreSQL valida.")
            return

        if parsed.scheme not in {"postgresql+psycopg", "postgresql"}:
            errors.append("DATABASE_URL deve usar postgresql+psycopg ou postgresql.")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            errors.append("DATABASE_URL deve conter host remoto seguro.")
        else:
            forbidden_host_tokens = (
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "[::1]",
                "ngrok",
                "trycloudflare.com",
                "loca.lt",
                "localtunnel",
            )
            if any(token in hostname for token in forbidden_host_tokens):
                errors.append("DATABASE_URL nao pode apontar para host local ou temporario em producao.")

        if port != 5432:
            errors.append("DATABASE_URL de producao deve usar a porta PostgreSQL padrao 5432.")

        database_name = parsed.path.lstrip("/")
        if not database_name:
            errors.append("DATABASE_URL deve conter o nome do banco.")

        username = parsed.username or ""
        if not username or not parsed.password:
            errors.append("DATABASE_URL deve conter usuario e senha da aplicacao.")
        if username.lower() in {"postgres", "root", "admin"}:
            errors.append("DATABASE_URL nao deve usar usuario master/superuser em producao.")

        query = parse_qs(parsed.query)
        sslmode = (query.get("sslmode") or [""])[0].lower()
        if sslmode not in {"require", "verify-full"}:
            errors.append("DATABASE_URL de producao deve exigir TLS com sslmode=require ou sslmode=verify-full.")

    def validate_runtime_configuration(self) -> None:
        errors: list[str] = []

        if self.is_production:
            if LEGACY_BRANDING_TOKEN in (self.app_name or "").lower():
                errors.append("APP_NAME nao pode conter branding legado em producao.")
            if not self.database_url:
                errors.append("DATABASE_URL deve ser definido explicitamente em producao.")
            else:
                self._validate_production_database_url(errors)
            if self.debug:
                errors.append("DEBUG deve ser false em producao.")
            if self.auto_migrate_on_startup:
                errors.append("AUTO_MIGRATE_ON_STARTUP nao pode ficar ativo em producao.")
            if self.ddl_fallback_enabled:
                errors.append("DDL_FALLBACK_ENABLED nao pode ficar ativo em producao.")
            if self.enable_internal_modules:
                errors.append("ENABLE_INTERNAL_MODULES nao pode ficar ativo em producao.")
            if self.bootstrap_admin_enabled:
                errors.append("BOOTSTRAP_ADMIN_ENABLED nao pode ficar ativo em producao.")
            secret_key = (self.secret_encryption_key or "").strip()
            if not secret_key:
                errors.append("SECRET_ENCRYPTION_KEY deve ser definido em producao.")
            else:
                try:
                    Fernet(secret_key.encode("utf-8"))
                except ValueError:
                    errors.append("SECRET_ENCRYPTION_KEY deve ser uma chave Fernet valida.")
            if self.resolved_cors_allow_origin_regex:
                errors.append("CORS_ALLOW_ORIGIN_REGEX deve ficar vazio em producao.")

            origins = self.resolved_cors_allowed_origins
            if not origins:
                errors.append("CORS_ALLOWED_ORIGINS deve listar dominios reais em producao.")

            forbidden_origin_tokens = (
                "localhost",
                "127.0.0.1",
                "0.0.0.0",
                "[::1]",
                "trycloudflare.com",
                "ngrok",
                "loca.lt",
                "localtunnel",
                LEGACY_BRANDING_TOKEN,
            )
            invalid_origins = [
                origin
                for origin in origins
                if any(token in origin.lower() for token in forbidden_origin_tokens)
            ]
            invalid_origin_shapes: list[str] = []
            for origin in origins:
                parsed = urlparse(origin)
                if (
                    origin == "*"
                    or parsed.scheme != "https"
                    or not parsed.netloc
                    or parsed.path not in ("", "/")
                    or parsed.params
                    or parsed.query
                    or parsed.fragment
                ):
                    invalid_origin_shapes.append(origin)
            if invalid_origins:
                errors.append(
                    "CORS_ALLOWED_ORIGINS contem origem invalida para producao: "
                    + ", ".join(invalid_origins)
                )
            if invalid_origin_shapes:
                errors.append(
                    "CORS_ALLOWED_ORIGINS deve conter apenas origins HTTPS reais, sem path/query/wildcard: "
                    + ", ".join(invalid_origin_shapes)
                )

        if self.bootstrap_admin_enabled and len((self.bootstrap_admin_token or "").strip()) < 32:
            errors.append("BOOTSTRAP_ADMIN_TOKEN deve ter pelo menos 32 caracteres quando bootstrap estiver ativo.")

        if errors:
            raise RuntimeError("Configuracao invalida do Kovir ERP: " + " | ".join(errors))


settings = Settings()
