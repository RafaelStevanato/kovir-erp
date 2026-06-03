from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

MASK = "***MASKED***"

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(authorization|token|access[_-]?token|refresh[_-]?token|bootstrap[_-]?token|focus[_-]?nfe[_-]?token|api[_-]?key|client[_-]?secret|secret|password|senha|database[_-]?url)"
)

_REDACTION_PATTERNS = (
    (
        re.compile(r"(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s,;]+"),
        lambda match: f"{match.group(1)}{match.group(2) or ''}{MASK}",
    ),
    (re.compile(r"(?i)(x-bootstrap-token\s*[:=]\s*)[^\s,;]+"), lambda match: f"{match.group(1)}{MASK}"),
    (
        re.compile(r"(?i)((?:access|refresh|bootstrap|focus_nfe|api)?[_-]?token\s*[:=]\s*)[^\s,;]+"),
        lambda match: f"{match.group(1)}{MASK}",
    ),
    (
        re.compile(r"(?i)((?:secret|password|senha|database_url)\s*[:=]\s*)[^\s,;]+"),
        lambda match: f"{match.group(1)}{MASK}",
    ),
    (
        re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:\s/@]+:)[^@\s]+(@[^\s]+)"),
        lambda match: f"{match.group(1)}{MASK}{match.group(2)}",
    ),
    (
        re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?%3a//[^:%\s/@]+%3a)[^@%]+(%40[^\s]+)"),
        lambda match: f"{match.group(1)}{MASK}{match.group(2)}",
    ),
    (
        re.compile(r'(?i)("(?:authorization|token|access[_-]?token|refresh[_-]?token|bootstrap[_-]?token|focus[_-]?nfe[_-]?token|api[_-]?key|client[_-]?secret|secret|password|senha|database[_-]?url)"\s*:\s*")[^"]*(")'),
        lambda match: f"{match.group(1)}{MASK}{match.group(2)}",
    ),
)


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_log_text(value)
    if isinstance(value, dict):
        return {
            key: MASK if _SENSITIVE_KEY_PATTERN.search(str(key)) else sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(sanitize_log_value(item) for item in value)
    if isinstance(value, list):
        return [sanitize_log_value(item) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return sanitize_log_text(str(value))


def sanitize_log_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RedactingLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize_log_value(record.msg)
        if record.args:
            record.args = sanitize_log_value(record.args)
        return True


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return sanitize_log_text(super().format(record))


class CloudWatchJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for field in ("request_id", "correlation_id", "company_id", "actor_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        sanitized = sanitize_log_value(payload)
        return sanitize_log_text(json.dumps(sanitized, ensure_ascii=False, default=str))


def configure_logging() -> None:
    log_format = settings_log_format()
    logging.basicConfig(
        level=getattr(logging, settings_log_level(), logging.INFO),
        format="%(message)s" if log_format == "json" else "%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    redacting_filter = RedactingLogFilter()
    formatter: logging.Formatter
    if log_format == "json":
        formatter = CloudWatchJsonFormatter()
    else:
        formatter = RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root_logger = logging.getLogger()

    for handler in root_logger.handlers:
        handler.addFilter(redacting_filter)
        handler.setFormatter(formatter)


def settings_log_level() -> str:
    from app.core.config import settings

    return settings.log_level.upper()


def settings_log_format() -> str:
    from app.core.config import settings

    value = (settings.log_format or "json").strip().lower()
    return value if value in {"json", "text"} else "json"
