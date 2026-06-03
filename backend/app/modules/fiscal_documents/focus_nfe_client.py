"""Cliente HTTP para a API Focus NFe.

Documentação: https://focusnfe.com.br/doc/

Auth: HTTP Basic com token como username, senha vazia.
Ambientes:
  - Homologação: https://homologacao.focusnfe.com.br/v2
  - Produção:    https://api.focusnfe.com.br/v2
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import sanitize_log_text

logger = logging.getLogger(__name__)

_HOMOLOGACAO_BASE = "https://homologacao.focusnfe.com.br/v2"
_PRODUCAO_BASE = "https://api.focusnfe.com.br/v2"


def _base_url(token: str | None = None) -> str:
    env = settings.focus_nfe_environment
    return _PRODUCAO_BASE if env == "producao" else _HOMOLOGACAO_BASE


def _auth(token: str) -> tuple[str, str]:
    """Basic auth: token como username, senha vazia."""
    return (token, "")


class FocusNFeError(Exception):
    """Erro retornado pela API da Focus NFe."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _resolve_token(company_token: str | None) -> str:
    """Retorna token da empresa ou token global do settings."""
    token = company_token or settings.focus_nfe_token
    if not token:
        raise FocusNFeError(
            "Token Focus NFe não configurado. Configure FOCUS_NFE_TOKEN no ambiente "
            "ou o campo focus_nfe_token na empresa."
        )
    return token


def emit_nfe(
    *,
    ref: str,
    payload: dict[str, Any],
    company_token: str | None = None,
) -> dict[str, Any]:
    """Envia NF-e para a Focus NFe.

    Args:
        ref: Referência única da nota (ex: "NF_123456789_001").
        payload: Corpo JSON com os dados da NF-e no formato Focus NFe.
        company_token: Token da empresa (sobrescreve settings global).

    Returns:
        Resposta JSON da Focus NFe.

    Raises:
        FocusNFeError: Em caso de erro HTTP ou resposta inválida.
    """
    token = _resolve_token(company_token)
    url = f"{_base_url(token)}/nfe"
    params = {"ref": ref}

    logger.info("Focus NFe: emitindo NF-e ref=%s", ref)

    try:
        response = httpx.post(
            url,
            params=params,
            json=payload,
            auth=_auth(token),
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise FocusNFeError(f"Erro de conexão com Focus NFe: {exc}") from exc

    body = response.text
    logger.debug("Focus NFe emit status=%d body=%s", response.status_code, sanitize_log_text(body[:500]))

    if response.status_code not in (200, 201, 202):
        raise FocusNFeError(
            f"Focus NFe retornou status {response.status_code}",
            status_code=response.status_code,
            body=body,
        )

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise FocusNFeError(f"Resposta inválida da Focus NFe: {sanitize_log_text(body[:200])}") from exc


def get_nfe_status(
    *,
    ref: str,
    company_token: str | None = None,
) -> dict[str, Any]:
    """Consulta status de uma NF-e na Focus NFe.

    Args:
        ref: Referência da nota enviada anteriormente.
        company_token: Token da empresa.

    Returns:
        Resposta JSON com status atual.
    """
    token = _resolve_token(company_token)
    url = f"{_base_url(token)}/nfe/{ref}"

    logger.info("Focus NFe: consultando status ref=%s", ref)

    try:
        response = httpx.get(url, auth=_auth(token), timeout=20.0)
    except httpx.RequestError as exc:
        raise FocusNFeError(f"Erro de conexão com Focus NFe: {exc}") from exc

    if response.status_code == 404:
        raise FocusNFeError(f"NF-e não encontrada na Focus NFe: ref={ref}", status_code=404)

    if response.status_code != 200:
        raise FocusNFeError(
            f"Focus NFe retornou status {response.status_code}",
            status_code=response.status_code,
            body=response.text,
        )

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise FocusNFeError(f"Resposta inválida da Focus NFe: {sanitize_log_text(response.text[:200])}") from exc


def cancel_nfe(
    *,
    ref: str,
    justificativa: str,
    company_token: str | None = None,
) -> dict[str, Any]:
    """Solicita cancelamento de uma NF-e autorizada.

    Args:
        ref: Referência da nota.
        justificativa: Motivo do cancelamento (mínimo 15 caracteres).
        company_token: Token da empresa.

    Returns:
        Resposta JSON da Focus NFe.
    """
    if len(justificativa.strip()) < 15:
        raise FocusNFeError("Justificativa de cancelamento deve ter no mínimo 15 caracteres.")

    token = _resolve_token(company_token)
    url = f"{_base_url(token)}/nfe/{ref}"

    logger.info("Focus NFe: cancelando NF-e ref=%s", ref)

    try:
        response = httpx.delete(
            url,
            json={"justificativa": justificativa.strip()},
            auth=_auth(token),
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise FocusNFeError(f"Erro de conexão com Focus NFe: {exc}") from exc

    if response.status_code not in (200, 201, 202):
        raise FocusNFeError(
            f"Focus NFe retornou status {response.status_code} ao cancelar",
            status_code=response.status_code,
            body=response.text,
        )

    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise FocusNFeError(f"Resposta inválida da Focus NFe: {sanitize_log_text(response.text[:200])}") from exc
