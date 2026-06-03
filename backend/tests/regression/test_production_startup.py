import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
import app.core.security as security_module
import app.main as main_module

LEGACY_APP_NAME = "Flu" + "xor ERP API"
VALID_FERNET_KEY = Fernet.generate_key().decode("utf-8")
VALID_PRODUCTION_DATABASE_URL = (
    "postgresql+psycopg://kovir_app:fake-password@"
    "db.kovir.example.com:5432/kovir?sslmode=require"
)
VALID_PRODUCTION_ORIGIN = "https://erp.kovir.example.com"


@app.get("/__regression/unhandled-error", include_in_schema=False)
def _raise_unhandled_error() -> None:
    raise RuntimeError("falha com postgresql://user:senha-real@db.example/kovir")


def test_production_requires_explicit_safe_runtime_config() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_url=VALID_PRODUCTION_DATABASE_URL,
        secret_encryption_key=VALID_FERNET_KEY,
        cors_allowed_origins=VALID_PRODUCTION_ORIGIN,
        cors_allow_origin_regex=None,
        auto_migrate_on_startup=False,
        ddl_fallback_enabled=False,
    )

    settings.validate_runtime_configuration()


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_message"),
    [
        ("app_name", LEGACY_APP_NAME, "APP_NAME"),
        ("database_url", None, "DATABASE_URL"),
        ("debug", True, "DEBUG"),
        ("auto_migrate_on_startup", True, "AUTO_MIGRATE_ON_STARTUP"),
        ("ddl_fallback_enabled", True, "DDL_FALLBACK_ENABLED"),
        ("enable_internal_modules", True, "ENABLE_INTERNAL_MODULES"),
        ("bootstrap_admin_enabled", True, "BOOTSTRAP_ADMIN_ENABLED"),
        ("secret_encryption_key", "", "SECRET_ENCRYPTION_KEY"),
        ("secret_encryption_key", "x" * 44, "SECRET_ENCRYPTION_KEY"),
        ("cors_allow_origin_regex", r"^https:\/\/.*$", "CORS_ALLOW_ORIGIN_REGEX"),
        ("cors_allowed_origins", "http://localhost:5173", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://127.0.0.1", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://0.0.0.0", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://[::1]", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://demo.trycloudflare.com", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://demo.ngrok-free.app", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://demo.loca.lt", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "http://erp.kovir.example.com", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "*", "CORS_ALLOWED_ORIGINS"),
        ("cors_allowed_origins", "https://erp.kovir.example.com/api", "CORS_ALLOWED_ORIGINS"),
    ],
)
def test_production_rejects_unsafe_runtime_config(
    field_name: str,
    field_value: object,
    expected_message: str,
) -> None:
    payload = {
        "environment": "production",
        "debug": False,
        "database_url": VALID_PRODUCTION_DATABASE_URL,
        "secret_encryption_key": VALID_FERNET_KEY,
        "cors_allowed_origins": VALID_PRODUCTION_ORIGIN,
        "cors_allow_origin_regex": None,
        "auto_migrate_on_startup": False,
        "ddl_fallback_enabled": False,
    }
    payload[field_name] = field_value

    settings = Settings(_env_file=None, **payload)

    with pytest.raises(RuntimeError, match=expected_message):
        settings.validate_runtime_configuration()


def test_startup_does_not_run_migrations_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    settings = Settings(
        _env_file=None,
        environment="development",
        auto_migrate_on_startup=False,
        ddl_fallback_enabled=False,
    )

    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "_run_migrations", lambda: calls.append("run"))

    main_module._run_startup_checks()

    assert calls == []


def test_production_csp_does_not_include_development_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_url=VALID_PRODUCTION_DATABASE_URL,
        secret_encryption_key=VALID_FERNET_KEY,
        cors_allowed_origins=VALID_PRODUCTION_ORIGIN,
        cors_allow_origin_regex=None,
    )

    monkeypatch.setattr(security_module, "settings", settings)

    csp = security_module.build_content_security_policy()

    assert VALID_PRODUCTION_ORIGIN in csp
    assert "localhost" not in csp
    assert "127.0.0.1" not in csp
    assert "trycloudflare.com" not in csp


def test_health_endpoint_returns_200_when_database_is_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module,
        "check_database_connection",
        lambda: {
            "online": True,
            "database": "postgresql",
            "driver": "psycopg",
            "error": "postgresql+psycopg://user:secret@db.example.com/kovir",
        },
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "database_online": True}
    assert "secret" not in response.text
    assert "db.example.com" not in response.text


def test_security_headers_are_applied_without_exposing_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_url=VALID_PRODUCTION_DATABASE_URL,
        secret_encryption_key=VALID_FERNET_KEY,
        cors_allowed_origins=VALID_PRODUCTION_ORIGIN,
        cors_allow_origin_regex=None,
        hsts_enabled=True,
        csp_report_only=False,
    )

    monkeypatch.setattr(security_module, "settings", settings)
    monkeypatch.setattr(
        main_module,
        "check_database_connection",
        lambda: {"online": True},
    )

    with TestClient(app) as client:
        response = client.get("/health", headers={"x-request-id": "req-security-headers"})

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    assert "upgrade-insecure-requests" in response.headers["Content-Security-Policy"]
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    assert response.headers["X-Request-ID"] == "req-security-headers"


@pytest.mark.parametrize(
    ("database_url", "expected_message"),
    [
        ("postgresql+psycopg://kovir_app:fake-password@localhost:5432/kovir?sslmode=require", "host local"),
        (
            "postgresql+psycopg://kovir_app:fake-password@db.kovir.example.com:5432/kovir",
            "sslmode",
        ),
        (
            "postgresql+psycopg://kovir_app:fake-password@db.kovir.example.com:5432/kovir?sslmode=disable",
            "sslmode",
        ),
        (
            "postgresql+psycopg://postgres:fake-password@db.kovir.example.com:5432/kovir?sslmode=require",
            "master",
        ),
        (
            "postgresql+psycopg://kovir_app:fake-password@db.kovir.example.com/kovir?sslmode=require",
            "5432",
        ),
        (
            "sqlite:///tmp.db",
            "postgresql",
        ),
        (
            "postgresql+psycopg://kovir_app:fake-password@<db-host>:5432/kovir?sslmode=require",
            "placeholder",
        ),
    ],
)
def test_production_rejects_unsafe_database_url(
    database_url: str,
    expected_message: str,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        debug=False,
        database_url=database_url,
        secret_encryption_key=VALID_FERNET_KEY,
        cors_allowed_origins=VALID_PRODUCTION_ORIGIN,
        cors_allow_origin_regex=None,
        auto_migrate_on_startup=False,
        ddl_fallback_enabled=False,
    )

    with pytest.raises(RuntimeError, match=expected_message):
        settings.validate_runtime_configuration()


def test_unhandled_exception_response_is_generic() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/__regression/unhandled-error",
            headers={"x-request-id": "req-unhandled-error"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "message": "Erro interno do servidor.",
        "data": None,
    }
    assert response.headers["X-Request-ID"] == "req-unhandled-error"
    assert "senha-real" not in response.text
    assert "postgresql://" not in response.text
    assert "Traceback" not in response.text


def test_health_endpoint_returns_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module,
        "check_database_connection",
        lambda: {
            "online": False,
            "database": "postgresql",
            "driver": "psycopg",
            "error": "password=secret host=db.example.com",
        },
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"success": False, "database_online": False}
    assert "secret" not in response.text
    assert "db.example.com" not in response.text


def test_bootstrap_admin_is_blocked_without_bootstrap_token() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/auth/bootstrap-admin",
            json={
                "company_id": "emp_00000000-0000-4000-8000-000000000000",
                "email": "admin@kovir.local",
                "full_name": "Admin Kovir",
                "password": "senha-forte-local",
            },
        )

    assert response.status_code == 403
