from __future__ import annotations

import io
import json
import logging

from app.core.logging import (
    MASK,
    CloudWatchJsonFormatter,
    RedactingFormatter,
    RedactingLogFilter,
    sanitize_log_text,
    sanitize_log_value,
)


def test_sanitize_log_text_masks_common_secret_shapes() -> None:
    text = (
        "Authorization: Bearer abc123 "
        "password=minha-senha "
        "DATABASE_URL=postgresql+psycopg://user:senha-real@db.example/kovir "
        '{"access_token":"token-real","client_secret":"segredo"}'
    )

    sanitized = sanitize_log_text(text)

    assert MASK in sanitized
    assert "abc123" not in sanitized
    assert "minha-senha" not in sanitized
    assert "senha-real" not in sanitized
    assert "token-real" not in sanitized
    assert "segredo" not in sanitized


def test_sanitize_log_value_masks_sensitive_mapping_values() -> None:
    sanitized = sanitize_log_value(
        {
            "email": "cliente@erpkovir.com.br",
            "password": "senha-real",
            "nested": {"focus_nfe_token": "token-focus"},
        }
    )

    assert sanitized["email"] == "cliente@erpkovir.com.br"
    assert sanitized["password"] == MASK
    assert sanitized["nested"]["focus_nfe_token"] == MASK


def test_redacting_formatter_and_filter_mask_logged_args_and_exceptions() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingLogFilter())
    handler.setFormatter(RedactingFormatter("%(levelname)s %(message)s"))

    logger = logging.getLogger("kovir.redaction.regression")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    logger.info("login payload=%s", {"password": "senha-real", "Authorization": "Bearer token-real"})

    try:
        raise RuntimeError("falha com postgresql://user:senha-real@db.example/kovir")
    except RuntimeError:
        logger.exception("erro processando token=%s", "token-real")

    output = stream.getvalue()

    assert MASK in output
    assert "senha-real" not in output
    assert "token-real" not in output


def test_cloudwatch_json_formatter_outputs_structured_masked_log() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingLogFilter())
    handler.setFormatter(CloudWatchJsonFormatter())

    logger = logging.getLogger("kovir.cloudwatch.regression")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info(
        "operacao request_id=%s payload=%s",
        "req-123",
        {"password": "senha-real", "database_url": "postgresql://user:senha-real@db.example/kovir"},
        extra={"request_id": "req-123", "correlation_id": "corr-456", "company_id": "cmp-789"},
    )

    output = stream.getvalue()
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "kovir.cloudwatch.regression"
    assert parsed["request_id"] == "req-123"
    assert parsed["correlation_id"] == "corr-456"
    assert parsed["company_id"] == "cmp-789"
    assert MASK in parsed["message"]
    assert "senha-real" not in output
    assert "postgresql://user:senha-real" not in output
