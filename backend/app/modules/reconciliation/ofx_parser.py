from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MONEY_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class ParsedOfxLine:
    external_id: str
    line_date: date
    direction: str
    amount: Decimal
    description: str | None
    document_number: str | None
    counterparty_name: str | None
    bank_reference: str | None
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ParsedOfxStatement:
    source_id: str
    statement_start_date: date | None
    statement_end_date: date | None
    opening_balance_amount: Decimal | None
    closing_balance_amount: Decimal | None
    account_info: dict[str, Any]
    lines: list[ParsedOfxLine]
    raw_header: dict[str, Any]


class OfxParseError(ValueError):
    """Erro de leitura/normalização de arquivo OFX."""


def _normalize_content(content: str) -> str:
    if not content or not content.strip():
        raise OfxParseError("Arquivo OFX vazio.")
    text = content.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    if "<OFX" not in text.upper():
        raise OfxParseError("Conteúdo não parece ser OFX: tag <OFX> não encontrada.")
    return text


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = html.unescape(value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or None


def _tag(block: str, tag: str) -> str | None:
    """Lê tag OFX em formato XML (<TAG>valor</TAG>) ou SGML (<TAG>valor)."""
    pattern_xml = re.compile(rf"<{tag}\b[^>]*>(.*?)</{tag}>", re.IGNORECASE | re.DOTALL)
    match = pattern_xml.search(block)
    if match:
        return _clean_text(match.group(1))

    pattern_sgml = re.compile(rf"<{tag}\b[^>]*>\s*([^<\n\r]*)", re.IGNORECASE)
    match = pattern_sgml.search(block)
    if match:
        return _clean_text(match.group(1))
    return None


def _headers(text: str) -> dict[str, str]:
    before_ofx = text[: text.upper().find("<OFX")]
    headers: dict[str, str] = {}
    for line in before_ofx.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().upper()
        value = value.strip()
        if key:
            headers[key] = value
    return headers


def _parse_ofx_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()
    # Exemplos: 20260429, 20260429123000, 20260429123000[-3:BRT]
    match = re.match(r"^(\d{4})(\d{2})(\d{2})", raw)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _money(value: str | None) -> Decimal:
    if value is None:
        raise OfxParseError("Valor monetário ausente em transação OFX.")
    raw = value.strip().replace(",", ".")
    try:
        return Decimal(raw).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise OfxParseError(f"Valor monetário inválido no OFX: {value!r}") from exc


def _blocks(text: str, tag: str) -> list[str]:
    pattern = re.compile(rf"<{tag}\b[^>]*>(.*?)</{tag}>", re.IGNORECASE | re.DOTALL)
    xml_blocks = [match.group(1) for match in pattern.finditer(text)]
    if xml_blocks:
        return xml_blocks

    # OFX 1.x costuma vir em SGML: <STMTTRN> abre o bloco, mas tags internas
    # não têm fechamento XML. Para importação bancária real, precisamos aceitar
    # esse formato sem tratar o arquivo como inválido.
    start_pattern = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
    starts = list(start_pattern.finditer(text))
    if not starts:
        return []

    closing_markers = {
        "STMTTRN": ["<STMTTRN", "</BANKTRANLIST", "<LEDGERBAL", "<AVAILBAL"],
        "BANKTRANLIST": ["</BANKTRANLIST", "<LEDGERBAL", "<AVAILBAL"],
        "LEDGERBAL": ["</LEDGERBAL", "<AVAILBAL", "</STMTRS", "</OFX"],
        "AVAILBAL": ["</AVAILBAL", "<LEDGERBAL", "</STMTRS", "</OFX"],
    }
    markers = closing_markers.get(tag.upper(), [f"</{tag}"])
    blocks: list[str] = []
    upper_text = text.upper()
    for index, start in enumerate(starts):
        content_start = start.end()
        candidate_ends = [starts[index + 1].start()] if index + 1 < len(starts) else [len(text)]
        for marker in markers:
            marker_index = upper_text.find(marker.upper(), content_start)
            if marker_index >= 0:
                candidate_ends.append(marker_index)
        content_end = min(candidate_ends)
        block = text[content_start:content_end].strip()
        if block:
            blocks.append(block)
    return blocks


def _direction(trn_type: str | None, amount: Decimal) -> str:
    if amount < Decimal("0"):
        return "outflow"
    if amount > Decimal("0"):
        return "inflow"
    debit_types = {"DEBIT", "CHECK", "PAYMENT", "XFER", "WITHDRAWAL", "ATM", "POS", "FEE", "SRVCHG"}
    return "outflow" if (trn_type or "").upper() in debit_types else "inflow"


def _line_external_id(*, fitid: str | None, account_info: dict[str, Any], line_date: date, amount: Decimal, description: str | None, index: int) -> str:
    if fitid:
        return f"ofx:{fitid}"[:180]
    basis = "|".join([
        str(account_info.get("bank_id") or ""),
        str(account_info.get("account_id") or ""),
        line_date.isoformat(),
        format(amount, "f"),
        description or "",
        str(index),
    ])
    return f"ofx:auto:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:40]}"


def parse_ofx(content: str) -> ParsedOfxStatement:
    text = _normalize_content(content)
    content_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    banktranlist = _blocks(text, "BANKTRANLIST")
    statement_window = banktranlist[0] if banktranlist else text
    statement_start = _parse_ofx_date(_tag(statement_window, "DTSTART"))
    statement_end = _parse_ofx_date(_tag(statement_window, "DTEND"))

    ledger_blocks = _blocks(text, "LEDGERBAL")
    ledger = ledger_blocks[0] if ledger_blocks else text
    closing_balance = None
    if _tag(ledger, "BALAMT") is not None:
        closing_balance = _money(_tag(ledger, "BALAMT"))

    avail_blocks = _blocks(text, "AVAILBAL")
    opening_balance = None
    if avail_blocks and _tag(avail_blocks[0], "BALAMT") is not None:
        opening_balance = _money(_tag(avail_blocks[0], "BALAMT"))

    account_info = {
        "bank_id": _tag(text, "BANKID"),
        "branch_id": _tag(text, "BRANCHID"),
        "account_id": _tag(text, "ACCTID"),
        "account_type": _tag(text, "ACCTTYPE"),
        "currency": _tag(text, "CURDEF") or "BRL",
    }

    transaction_blocks = _blocks(text, "STMTTRN")
    if not transaction_blocks:
        raise OfxParseError("Nenhuma transação <STMTTRN> encontrada no OFX.")

    parsed_lines: list[ParsedOfxLine] = []
    seen_external_ids: set[str] = set()
    for index, block in enumerate(transaction_blocks, start=1):
        trn_type = _tag(block, "TRNTYPE")
        raw_amount = _money(_tag(block, "TRNAMT"))
        amount = abs(raw_amount)
        if amount <= Decimal("0.00"):
            continue
        line_date = _parse_ofx_date(_tag(block, "DTPOSTED")) or _parse_ofx_date(_tag(block, "DTUSER"))
        if line_date is None:
            raise OfxParseError("Transação OFX sem data válida em DTPOSTED/DTUSER.")
        name = _tag(block, "NAME")
        memo = _tag(block, "MEMO")
        payee = _tag(block, "PAYEE")
        description = _clean_text(" — ".join([part for part in [name, memo] if part])) or payee or trn_type or "Transação OFX"
        fitid = _tag(block, "FITID")
        external_id = _line_external_id(fitid=fitid, account_info=account_info, line_date=line_date, amount=raw_amount, description=description, index=index)
        if external_id in seen_external_ids:
            external_id = f"{external_id[:150]}:{index}"
        seen_external_ids.add(external_id)
        refnum = _tag(block, "REFNUM")
        checknum = _tag(block, "CHECKNUM")
        parsed_lines.append(
            ParsedOfxLine(
                external_id=external_id,
                line_date=line_date,
                direction=_direction(trn_type, raw_amount),
                amount=amount,
                description=description,
                document_number=checknum or refnum,
                counterparty_name=payee or name,
                bank_reference=refnum or fitid,
                raw_payload={
                    "trn_type": trn_type,
                    "raw_amount": format(raw_amount, "f"),
                    "fitid": fitid,
                    "refnum": refnum,
                    "checknum": checknum,
                    "name": name,
                    "memo": memo,
                    "payee": payee,
                    "index": index,
                },
            )
        )

    if not parsed_lines:
        raise OfxParseError("OFX não possui transações com valor diferente de zero.")

    dates = [line.line_date for line in parsed_lines]
    return ParsedOfxStatement(
        source_id=f"ofx:{content_hash[:32]}",
        statement_start_date=statement_start or min(dates),
        statement_end_date=statement_end or max(dates),
        opening_balance_amount=opening_balance,
        closing_balance_amount=closing_balance,
        account_info=account_info,
        lines=parsed_lines,
        raw_header=_headers(text),
    )
