from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

FERNET_SECRET_PREFIX = "fernet:v1:"


def _get_fernet() -> Fernet | None:
    key = (settings.secret_encryption_key or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise RuntimeError("SECRET_ENCRYPTION_KEY invalida. Gere uma chave Fernet valida.") from exc


def encrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith(FERNET_SECRET_PREFIX):
        return cleaned

    fernet = _get_fernet()
    if fernet is None:
        if settings.is_production:
            raise RuntimeError("SECRET_ENCRYPTION_KEY obrigatoria para gravar segredo em producao.")
        return cleaned

    encrypted = fernet.encrypt(cleaned.encode("utf-8")).decode("utf-8")
    return FERNET_SECRET_PREFIX + encrypted


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not cleaned.startswith(FERNET_SECRET_PREFIX):
        return cleaned

    fernet = _get_fernet()
    if fernet is None:
        raise RuntimeError("SECRET_ENCRYPTION_KEY obrigatoria para ler segredo criptografado.")

    encrypted = cleaned.removeprefix(FERNET_SECRET_PREFIX)
    try:
        return fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Segredo criptografado invalido ou chave incorreta.") from exc
