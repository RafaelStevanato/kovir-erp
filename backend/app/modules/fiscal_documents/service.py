"""Serviço de documentos fiscais — emissão NF-e via Focus NFe.

Responsabilidades:
- Montar o payload JSON da NF-e no formato Focus NFe a partir da venda
- Persistir o FiscalDocumentDB antes e depois da chamada à API
- Consultar e sincronizar status de notas emitidas
- Não tomar decisões fiscais: apenas mapeia dados já validados pela readiness layer
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.db_models import CompanyDB
from app.core.secrets import decrypt_secret
from app.modules.fiscal_documents.db_models import FiscalDocumentDB
from app.modules.fiscal_documents.focus_nfe_client import FocusNFeError, cancel_nfe, emit_nfe, get_nfe_status
from app.modules.fiscal_documents.repository import (
    create_fiscal_document,
    get_fiscal_documents_for_sale,
    update_fiscal_document,
)
from app.modules.sales.db_models import SaleDB, SaleItemDB, SalePaymentPlanDB

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Mapeamento de formas de pagamento → código ABNT Focus NFe
# ──────────────────────────────────────────────────────────────────────────────

_PAYMENT_CODE_MAP: dict[str, str] = {
    "pix": "17",
    "credit_card": "03",
    "debit_card": "04",
    "cash": "01",
    "boleto": "15",
    "bank_transfer": "18",
    "store_credit": "99",
    "other": "99",
}


def _digits_only(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def _fmt_date(value: Any) -> str:
    """Formata uma data para YYYY-MM-DD usado pela Focus NFe."""
    if value is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if isinstance(value, str):
        return value[:10]
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _fmt_decimal(value: Any, places: int = 2) -> str:
    if value is None:
        return "0.00"
    d = Decimal(str(value))
    return format(d, f".{places}f")


def _build_emitente(company: CompanyDB) -> dict[str, Any]:
    """Monta o bloco emitente da NF-e."""
    cnpj = _digits_only(company.cnpj)
    crt = company.crt or "3"  # Regime Normal como default seguro

    # CRT → regime_tributario Focus NFe
    regime_map = {"1": "1", "2": "2", "3": "3"}
    regime = regime_map.get(crt, "3")

    emitente: dict[str, Any] = {
        "cnpj": cnpj,
        "nome": (company.trade_name or company.legal_name or "")[:60],
        "razao_social": (company.legal_name or "")[:60],
        "logradouro": (company.address_street or "")[:60],
        "numero": (company.address_number or "S/N")[:60],
        "bairro": (company.address_district or "Centro")[:60],
        "municipio": (company.address_city or "")[:60],
        "uf": (company.address_state or "SP").upper(),
        "cep": _digits_only(company.address_zip_code),
        "regime_tributario": regime,
    }

    if company.address_complement:
        emitente["complemento"] = company.address_complement[:60]

    if company.phone:
        emitente["telefone"] = _digits_only(company.phone)[:14]

    if company.state_registration:
        emitente["inscricao_estadual"] = re.sub(r"\D", "", company.state_registration)[:14]

    return emitente


def _build_destinatario(participant_snapshot: dict) -> dict[str, Any]:
    """Monta o bloco destinatário da NF-e a partir do snapshot do participante."""
    doc = _digits_only(participant_snapshot.get("document") or participant_snapshot.get("cpf") or participant_snapshot.get("cnpj") or "")
    person_type = participant_snapshot.get("person_type", "pf")
    name = (participant_snapshot.get("name") or participant_snapshot.get("legal_name") or "CONSUMIDOR FINAL")[:60]

    dest: dict[str, Any] = {"nome": name}

    if doc:
        if person_type == "pj" or len(doc) == 14:
            dest["cnpj"] = doc
        else:
            dest["cpf"] = doc

    # Endereço (pode vir de address_json ou campos diretos)
    addr = participant_snapshot.get("address_json") or {}
    state = addr.get("state") or participant_snapshot.get("address_state") or "SP"
    city = addr.get("city") or participant_snapshot.get("address_city") or ""
    street = addr.get("street") or participant_snapshot.get("address_street") or ""
    number = addr.get("number") or participant_snapshot.get("address_number") or "S/N"
    district = addr.get("district") or participant_snapshot.get("address_district") or "Centro"
    zip_code = _digits_only(addr.get("zip_code") or participant_snapshot.get("address_zip_code") or "")

    dest["logradouro"] = street[:60] or "Não informado"
    dest["numero"] = number[:60]
    dest["bairro"] = district[:60]
    dest["municipio"] = city[:60] or "Não informado"
    dest["uf"] = state[:2].upper() if state else "SP"
    dest["cep"] = zip_code

    if addr.get("complement") or participant_snapshot.get("address_complement"):
        dest["complemento"] = (addr.get("complement") or participant_snapshot.get("address_complement") or "")[:60]

    # Indicador IE destinatário
    fiscal_settings = participant_snapshot.get("fiscal_settings_json") or {}
    ie_indicator = fiscal_settings.get("ie_indicator") or "9"
    dest["indicador_ie_destinatario"] = str(ie_indicator)

    if fiscal_settings.get("state_registration"):
        dest["inscricao_estadual"] = re.sub(r"\D", "", fiscal_settings["state_registration"])[:14]

    email = participant_snapshot.get("email") or ""
    if email:
        dest["email"] = email[:60]

    return dest


def _build_item(idx: int, item: SaleItemDB) -> dict[str, Any]:
    """Monta um item da NF-e no formato Focus NFe."""
    fiscal = item.fiscal_snapshot_json or {}
    catalog = item.item_snapshot_json or {}

    ncm = _digits_only(fiscal.get("ncm") or catalog.get("ncm") or "")
    cfop = fiscal.get("cfop_default") or fiscal.get("cfop") or "5102"  # venda mercadoria normal
    cst_icms = fiscal.get("cst_icms") or "400"  # isento como fallback
    cst_pis = fiscal.get("cst_pis") or "07"
    cst_cofins = fiscal.get("cst_cofins") or "07"
    origem = fiscal.get("origem_mercadoria") or "0"  # nacional

    qty = _fmt_decimal(item.quantity, 4)
    unit_price = _fmt_decimal(item.unit_price, 4)
    total = _fmt_decimal(item.total_amount, 2)

    result: dict[str, Any] = {
        "numero_item": str(idx),
        "codigo_produto": catalog.get("sku") or catalog.get("id") or item.item_id,
        "descricao": (item.description or catalog.get("name") or "")[:120],
        "ncm": ncm or "00000000",
        "cfop": cfop,
        "unidade_comercial": (item.unit or "UN")[:6],
        "quantidade_comercial": qty,
        "valor_unitario_comercial": unit_price,
        "valor_bruto": total,
        "unidade_tributavel": (item.unit or "UN")[:6],
        "quantidade_tributavel": qty,
        "valor_unitario_tributavel": unit_price,
        "valor_total_tributos": _fmt_decimal(item.tax_amount, 2),
        "inclui_no_total": "1",
        "impostos": {
            "icms": {
                "origem": origem,
                "cst": cst_icms,
            },
            "pis": {
                "situacao_tributaria": cst_pis,
                "aliquota": "0.00",
                "valor": "0.00",
            },
            "cofins": {
                "situacao_tributaria": cst_cofins,
                "aliquota": "0.00",
                "valor": "0.00",
            },
        },
    }

    if item.discount_amount and Decimal(str(item.discount_amount)) > 0:
        result["valor_desconto"] = _fmt_decimal(item.discount_amount, 2)

    if item.freight_amount and Decimal(str(item.freight_amount)) > 0:
        result["valor_frete"] = _fmt_decimal(item.freight_amount, 2)

    cest = _digits_only(fiscal.get("cest") or "")
    if cest:
        result["cest"] = cest

    nbs = fiscal.get("nbs") or ""
    if nbs:
        result["nbs"] = nbs

    return result


def _build_pagamentos(payment_plans: list[SalePaymentPlanDB]) -> list[dict[str, Any]]:
    """Monta o bloco formas_pagamento da NF-e."""
    if not payment_plans:
        return [{"forma_pagamento": "99", "valor_pagamento": "0.00"}]

    result = []
    for plan in payment_plans:
        code = _PAYMENT_CODE_MAP.get(plan.payment_method_code or "", "99")
        result.append({
            "forma_pagamento": code,
            "valor_pagamento": _fmt_decimal(plan.amount, 2),
        })
    return result


def _build_nfe_payload(
    sale: SaleDB,
    company: CompanyDB,
) -> dict[str, Any]:
    """Monta o payload JSON completo da NF-e para a Focus NFe."""
    participant_snapshot: dict = sale.participant_snapshot_json or {}
    items = sorted(sale.items, key=lambda i: i.created_at)
    payment_plans = sorted(sale.payment_plans, key=lambda p: p.created_at)

    issue_date = _fmt_date(sale.issue_date or sale.operation_date)

    # Tipo de documento: 1=saída (venda)
    tipo_documento = "1"

    # Destino: 1=interna, 2=interestadual, 3=exterior
    # Comparamos UF emitente x UF destinatário
    emitente_uf = (company.address_state or "SP").upper()
    addr = participant_snapshot.get("address_json") or {}
    dest_uf = (addr.get("state") or participant_snapshot.get("address_state") or emitente_uf).upper()
    if dest_uf == emitente_uf:
        local_destino = "1"
    elif dest_uf in ("EX", ""):
        local_destino = "3"
    else:
        local_destino = "2"

    # Presença do comprador: 9=não presencial (padrão seguro)
    presenca_comprador = "9"

    # Consumidor final: 1=sim (venda direta a pessoa física ou varejo)
    person_type = participant_snapshot.get("person_type", "pf")
    consumidor_final = "1" if person_type == "pf" else "0"

    # Natureza da operação
    op_snapshot = sale.operation_nature_snapshot_json or {}
    natureza_operacao = op_snapshot.get("name") or "Venda de Mercadoria"

    payload: dict[str, Any] = {
        "natureza_operacao": natureza_operacao[:60],
        "data_emissao": issue_date,
        "data_entrada_saida": issue_date,
        "tipo_documento": tipo_documento,
        "local_destino": local_destino,
        "presenca_comprador": presenca_comprador,
        "consumidor_final": consumidor_final,
        "finalidade_emissao": "1",  # NF-e normal
        "emitente": _build_emitente(company),
        "destinatario": _build_destinatario(participant_snapshot),
        "items": [_build_item(i + 1, item) for i, item in enumerate(items)],
        "formas_pagamento": _build_pagamentos(payment_plans),
    }

    # Totais agregados
    if sale.freight_amount and Decimal(str(sale.freight_amount)) > 0:
        payload["valor_frete"] = _fmt_decimal(sale.freight_amount, 2)

    if sale.discount_amount and Decimal(str(sale.discount_amount)) > 0:
        payload["valor_desconto"] = _fmt_decimal(sale.discount_amount, 2)

    if sale.notes:
        payload["informacoes_adicionais_contribuinte"] = sale.notes[:2000]

    return payload


def _build_reference(company: CompanyDB, sale: SaleDB, seq: int = 1) -> str:
    """Gera a referência única para a Focus NFe.

    Formato: NF_{cnpj_digits}_{sale_id_short}_{seq}
    Máximo 50 chars.
    """
    cnpj = _digits_only(company.cnpj or "")[:14]
    sale_short = sale.id.split("_")[-1][:12]  # UUID parcial
    ref = f"NF_{cnpj}_{sale_short}_{seq:03d}"
    return ref[:50]


# ──────────────────────────────────────────────────────────────────────────────
# API pública do módulo
# ──────────────────────────────────────────────────────────────────────────────

def emit_invoice_for_sale(
    db: Session,
    sale: SaleDB,
) -> dict[str, Any]:
    """Emite NF-e para a venda via Focus NFe.

    Cria um FiscalDocumentDB com status 'pending', chama a Focus NFe,
    atualiza o documento com o resultado e retorna um dict com o resultado.

    Raises:
        ValueError: Se a empresa não for encontrada ou o token não estiver configurado.
        FocusNFeError: Em caso de erro na API da Focus NFe.
    """
    company = db.query(CompanyDB).filter(CompanyDB.id == sale.company_id).first()
    if not company:
        raise ValueError(f"Empresa {sale.company_id} não encontrada.")

    # Determina o próximo seq para não reutilizar referência
    existing = get_fiscal_documents_for_sale(db, sale.id)
    seq = len(existing) + 1
    ref = _build_reference(company, sale, seq)

    # Determina modelo (55=NF-e, 65=NFC-e)
    sale_type = sale.sale_type
    model = "65" if sale_type == "product" else "55"  # NFC-e para varejo, NF-e para padrão
    serie = company.nfce_serie if model == "65" else company.nfe_serie
    document_type = "nfce" if model == "65" else "nfe"

    # Cria o documento como pending
    fiscal_doc = create_fiscal_document(
        db=db,
        company_id=sale.company_id,
        sale_id=sale.id,
        document_type=document_type,
        reference=ref,
        model=model,
        serie=serie,
    )

    try:
        payload = _build_nfe_payload(sale, company)
        token = decrypt_secret(company.focus_nfe_token)
        response = emit_nfe(ref=ref, payload=payload, company_token=token)

        # Atualiza com resposta da Focus
        status = _map_focus_status(response.get("status") or "processando")
        updates: dict[str, Any] = {
            "status": status,
            "focus_status": response.get("status"),
            "focus_response_json": json.dumps(response, ensure_ascii=False),
            "access_key": response.get("chave_nfe"),
            "protocol": response.get("protocolo"),
            "number": str(response.get("numero") or ""),
            "danfe_url": response.get("danfe_url"),
            "xml_url": response.get("xml_url"),
        }
        if status == "authorized":
            updates["authorized_at"] = datetime.now(timezone.utc)
        if status == "issued":
            updates["issued_at"] = datetime.now(timezone.utc)

        fiscal_doc = update_fiscal_document(db, fiscal_doc, updates)
        db.commit()

        logger.info(
            "Focus NFe: NF-e emitida sale_id=%s ref=%s status=%s",
            sale.id, ref, status,
        )

    except (FocusNFeError, Exception) as exc:
        error_msg = str(exc)
        update_fiscal_document(db, fiscal_doc, {
            "status": "error",
            "error_message": error_msg[:2000],
        })
        db.commit()
        raise

    return _serialize_fiscal_document(fiscal_doc)


def sync_fiscal_document_status(
    db: Session,
    doc: FiscalDocumentDB,
) -> dict[str, Any]:
    """Consulta a Focus NFe e atualiza o status do documento."""
    company = db.query(CompanyDB).filter(CompanyDB.id == doc.company_id).first()
    token = decrypt_secret(company.focus_nfe_token) if company else None

    response = get_nfe_status(ref=doc.reference, company_token=token)
    status = _map_focus_status(response.get("status") or "processando")

    updates: dict[str, Any] = {
        "focus_status": response.get("status"),
        "focus_response_json": json.dumps(response, ensure_ascii=False),
        "status": status,
        "access_key": response.get("chave_nfe") or doc.access_key,
        "protocol": response.get("protocolo") or doc.protocol,
        "danfe_url": response.get("danfe_url") or doc.danfe_url,
        "xml_url": response.get("xml_url") or doc.xml_url,
    }
    if status == "authorized" and not doc.authorized_at:
        updates["authorized_at"] = datetime.now(timezone.utc)

    updated = update_fiscal_document(db, doc, updates)
    db.commit()
    return _serialize_fiscal_document(updated)


def cancel_fiscal_document(
    db: Session,
    doc: FiscalDocumentDB,
    justificativa: str,
) -> dict[str, Any]:
    """Cancela uma NF-e autorizada via Focus NFe."""
    company = db.query(CompanyDB).filter(CompanyDB.id == doc.company_id).first()
    token = decrypt_secret(company.focus_nfe_token) if company else None

    response = cancel_nfe(ref=doc.reference, justificativa=justificativa, company_token=token)
    status = _map_focus_status(response.get("status") or "cancelado")

    updates: dict[str, Any] = {
        "status": status,
        "focus_status": response.get("status"),
        "focus_response_json": json.dumps(response, ensure_ascii=False),
        "cancelled_at": datetime.now(timezone.utc),
    }
    updated = update_fiscal_document(db, doc, updates)
    db.commit()
    return _serialize_fiscal_document(updated)


def get_fiscal_documents_for_sale_dict(db: Session, sale_id: str) -> list[dict[str, Any]]:
    docs = get_fiscal_documents_for_sale(db, sale_id)
    return [_serialize_fiscal_document(d) for d in docs]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────

def _map_focus_status(focus_status: str) -> str:
    """Mapeia status Focus NFe → status interno."""
    mapping: dict[str, str] = {
        "autorizado": "authorized",
        "cancelado": "cancelled",
        "denegado": "denied",
        "erro_autorizacao": "error",
        "processando": "processing",
        "contingencia": "contingency",
        "aguardando_recibo": "processing",
        "aguardando_cancelamento": "processing",
    }
    return mapping.get(focus_status.lower(), "processing")


def _serialize_fiscal_document(doc: FiscalDocumentDB) -> dict[str, Any]:
    return {
        "id": doc.id,
        "company_id": doc.company_id,
        "sale_id": doc.sale_id,
        "document_type": doc.document_type,
        "model": doc.model,
        "serie": doc.serie,
        "number": doc.number,
        "reference": doc.reference,
        "status": doc.status,
        "focus_status": doc.focus_status,
        "access_key": doc.access_key,
        "protocol": doc.protocol,
        "error_code": doc.error_code,
        "error_message": doc.error_message,
        "danfe_url": doc.danfe_url,
        "xml_url": doc.xml_url,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "authorized_at": doc.authorized_at.isoformat() if doc.authorized_at else None,
        "cancelled_at": doc.cancelled_at.isoformat() if doc.cancelled_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
