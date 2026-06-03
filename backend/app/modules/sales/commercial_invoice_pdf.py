"""Gerador de PDF comercial para pedidos CLOSED e PAID.

Layout inspirado em DANFE Modelo 55, sem valor fiscal.
Modo "closed" → azul, texto: PEDIDO COMERCIAL
Modo "paid"   → verde, texto: ESPELHO DE NF-e
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.modules.company.db_models import CompanyDB
from app.modules.sales.db_models import SaleDB
from app.modules.sales.invoice_readiness import build_invoice_readiness


_DARK = (0.15, 0.15, 0.15)
_GRAY = (0.50, 0.50, 0.50)
_BLUE = (0.10, 0.30, 0.65)
_GREEN = (0.05, 0.50, 0.15)
_LIGHT_GRAY_BG = (0.94, 0.94, 0.94)
_WHITE = (1.0, 1.0, 1.0)
_RED = (0.80, 0.10, 0.10)
_ORANGE = (0.90, 0.45, 0.00)

_MODE_COLOR = {
    "closed": _BLUE,
    "paid": _GREEN,
}

_MODE_TITLE = {
    "closed": "PEDIDO COMERCIAL",
    "paid": "ESPELHO DE NF-e",
}

_MODE_WARNING = {
    "closed": "PEDIDO COMERCIAL — Documento sem valor fiscal. Aguardando emissão de NF-e.",
    "paid": "ESPELHO DE NF-e — Documento sem valor fiscal. Para fins de conferência.",
}


def _fmt_money(value: Any) -> str:
    if value is None:
        return "R$ 0,00"
    d = Decimal(str(value))
    return f"R$ {d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value[:10]
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)[:10]


def _clean(value: Any, fallback: str = "—") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _try_qr_code(data: str, size_mm: float) -> Any | None:
    """Tenta gerar imagem QR; retorna None se qrcode não estiver instalado."""
    try:
        import qrcode
        from reportlab.lib.units import mm
        from reportlab.platypus import Image
        import tempfile, os

        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        tmp.close()
        size = size_mm * mm
        return Image(tmp.name, width=size, height=size)
    except Exception:
        return None


def generate_commercial_invoice_pdf(
    db: Session,
    sale: SaleDB,
    *,
    mode: Literal["closed", "paid"],
) -> bytes:
    """Gera PDF comercial e retorna os bytes."""
    try:
        from reportlab.lib.colors import Color
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab não instalado. Execute: pip install reportlab") from exc

    accent = _MODE_COLOR[mode]
    title_text = _MODE_TITLE[mode]
    warning_text = _MODE_WARNING[mode]

    company = db.query(CompanyDB).filter(CompanyDB.id == sale.company_id).first()
    readiness = build_invoice_readiness(db, sale)
    participant_snapshot: dict = sale.participant_snapshot_json or {}
    items = sorted(sale.items, key=lambda i: i.created_at)
    payment_plans = sorted(sale.payment_plans, key=lambda p: p.created_at)
    op_snapshot: dict = sale.operation_nature_snapshot_json or {}

    generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    buffer = io.BytesIO()
    page_w, page_h = A4
    margin = 15 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    styles = getSampleStyleSheet()
    col_w = page_w - 2 * margin

    def style(name: str, **kw) -> ParagraphStyle:
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    s_warning = style("warn", fontSize=8, textColor=Color(*accent), alignment=TA_CENTER, leading=12)
    s_section = style("section", fontSize=10, textColor=Color(*accent), fontName="Helvetica-Bold", leading=14, spaceBefore=8)
    s_label = style("label", fontSize=7, textColor=Color(*_GRAY), leading=10)
    s_value = style("value", fontSize=9, textColor=Color(*_DARK), leading=12)
    s_small = style("small", fontSize=7, textColor=Color(*_DARK), leading=10)
    s_issue_error = style("issue_e", fontSize=8, textColor=Color(*_RED), fontName="Helvetica-Bold", leading=11)
    s_issue_warn = style("issue_w", fontSize=8, textColor=Color(*_ORANGE), leading=11)
    s_issue_block = style("issue_b", fontSize=8, textColor=Color(*_DARK), leading=11)
    s_small_gray = style("small_g", fontSize=7, textColor=Color(*_GRAY), leading=10)
    s_footer = style("footer", fontSize=7, textColor=Color(*_GRAY), alignment=TA_CENTER, leading=10)

    story: list[Any] = []

    def HR(color: tuple = _GRAY, thickness: float = 0.5) -> HRFlowable:
        return HRFlowable(width="100%", thickness=thickness, color=Color(*color), spaceAfter=4, spaceBefore=2)

    def section_title(text: str) -> None:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(text.upper(), s_section))
        story.append(HR(accent, 0.8))

    def row2(label1: str, val1: str, label2: str = "", val2: str = "") -> None:
        data = [[
            Paragraph(label1, s_label), Paragraph(val1, s_value),
            Paragraph(label2, s_label), Paragraph(val2, s_value),
        ]]
        t = Table(data, colWidths=[col_w * 0.15, col_w * 0.35, col_w * 0.15, col_w * 0.35])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)

    # ── Cabeçalho 2 colunas ───────────────────────────────────────────────────
    # Coluna esquerda: emitente
    # Coluna direita: box com numeração + título
    left_lines = []
    if company:
        left_lines.append(Paragraph(
            _clean(company.legal_name or company.trade_name),
            style("cname", fontSize=10, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=14),
        ))
        left_lines.append(Paragraph(f"CNPJ: {_clean(company.cnpj)}", s_value))
        addr_parts = [
            company.address_street or "", company.address_number or "",
            company.address_city or "", company.address_state or "",
        ]
        addr = ", ".join(p for p in addr_parts if p)
        left_lines.append(Paragraph(_clean(addr), s_value))
        if company.address_zip_code:
            left_lines.append(Paragraph(f"CEP: {_clean(company.address_zip_code)}", s_value))
    else:
        left_lines.append(Paragraph("Empresa não encontrada.", s_value))

    # Número box
    number_lines = [
        Paragraph(title_text, style("htitle", fontSize=12, textColor=Color(*accent), fontName="Helvetica-Bold", leading=15, alignment=TA_CENTER)),
    ]
    if sale.sale_number_text:
        number_lines.append(Paragraph(
            f"Pedido Nº {sale.sale_number_text}",
            style("hped", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12, alignment=TA_CENTER),
        ))
    if mode == "paid" and sale.paid_number_text:
        number_lines.append(Paragraph(
            f"Espelho NF-e Nº {sale.paid_number_text}",
            style("hpago", fontSize=9, textColor=Color(*_GREEN), fontName="Helvetica-Bold", leading=12, alignment=TA_CENTER),
        ))
    number_lines.append(Paragraph(f"Gerado em {generated_at}", style("hdate", fontSize=7, textColor=Color(*_GRAY), leading=10, alignment=TA_CENTER)))

    # Tentar QR code
    qr_data = {
        "sale_id": sale.id,
        "sale_number_text": sale.sale_number_text or "",
        "paid_number_text": sale.paid_number_text or "",
        "total_amount": str(sale.total_amount),
    }
    qr_str = "&".join(f"{k}={v}" for k, v in qr_data.items())
    qr_img = _try_qr_code(qr_str, size_mm=20)

    if qr_img:
        from reportlab.platypus import KeepInFrame
        number_lines.append(Spacer(1, 2 * mm))
        number_lines.append(qr_img)

    left_cell = left_lines
    right_cell = number_lines

    header_data = [[left_cell, right_cell]]
    header_table = Table(header_data, colWidths=[col_w * 0.60, col_w * 0.40])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (1, 0), (1, 0), 1.5, Color(*accent)),
        ("BACKGROUND", (1, 0), (1, 0), Color(*_LIGHT_GRAY_BG)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("RIGHTPADDING", (1, 0), (1, 0), 6),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    # ── Warning box ───────────────────────────────────────────────────────────
    warn_data = [[Paragraph(warning_text, s_warning)]]
    warn_table = Table(warn_data, colWidths=[col_w])
    warn_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), Color(*_LIGHT_GRAY_BG)),
        ("BOX", (0, 0), (-1, -1), 1, Color(*accent)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(warn_table)
    story.append(Spacer(1, 3 * mm))

    # ── Destinatário ──────────────────────────────────────────────────────────
    section_title("Destinatário")
    ps = participant_snapshot
    row2("Nome / Razão Social", _clean(ps.get("name") or ps.get("legal_name")),
         "CPF / CNPJ", _clean(ps.get("document") or ps.get("cpf") or ps.get("cnpj")))
    addr_j = ps.get("address_json") or {}
    dest_addr = ", ".join(p for p in [
        addr_j.get("street", ""), addr_j.get("number", ""),
        addr_j.get("district", ""), addr_j.get("city", ""),
        addr_j.get("state", ""),
    ] if p)
    row2("Endereço", _clean(dest_addr), "CEP", _clean(addr_j.get("zip_code")))
    fiscal_s = ps.get("fiscal_settings_json") or {}
    row2("Indicador IE", _clean(fiscal_s.get("ie_indicator")), "IE", _clean(fiscal_s.get("state_registration")))

    # ── Dados da operação ─────────────────────────────────────────────────────
    section_title("Dados da Operação")
    row2("Natureza da Operação", _clean(op_snapshot.get("name") or sale.operation_nature),
         "Tipo de Venda", _clean(sale.sale_type))
    row2("Data de Emissão", _fmt_date(sale.issue_date),
         "Data da Operação", _fmt_date(sale.operation_date))
    row2("Status da Venda", _clean(sale.status),
         "Status Fiscal", _clean(sale.fiscal_status))

    # ── Itens ─────────────────────────────────────────────────────────────────
    section_title("Itens")

    item_header = [
        Paragraph("#", s_label),
        Paragraph("Descrição", s_label),
        Paragraph("NCM / CFOP", s_label),
        Paragraph("CST ICMS", s_label),
        Paragraph("Qtd", s_label),
        Paragraph("Preço Unit.", s_label),
        Paragraph("Total", s_label),
    ]
    item_rows = [item_header]

    for idx, item in enumerate(items, 1):
        fsn = item.fiscal_snapshot_json or {}
        isn = item.item_snapshot_json or {}
        ncm = _clean(fsn.get("ncm") or isn.get("ncm"), "—")
        cfop = _clean(fsn.get("cfop_default") or fsn.get("cfop"), "—")
        cst = _clean(fsn.get("cst_icms"), "—")
        item_rows.append([
            Paragraph(str(idx), s_small),
            Paragraph(_clean(item.description)[:60], s_small),
            Paragraph(f"{ncm} / {cfop}", s_small),
            Paragraph(cst, s_small),
            Paragraph(f"{_clean(str(item.quantity))} {_clean(item.unit, '')}", s_small),
            Paragraph(_fmt_money(item.unit_price), s_small),
            Paragraph(_fmt_money(item.total_amount), s_small),
        ])

    item_table = Table(
        item_rows,
        colWidths=[col_w * 0.04, col_w * 0.28, col_w * 0.16, col_w * 0.10,
                   col_w * 0.12, col_w * 0.14, col_w * 0.16],
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), Color(*accent)),
        ("TEXTCOLOR", (0, 0), (-1, 0), Color(*_WHITE)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [Color(*_WHITE), Color(*_LIGHT_GRAY_BG)]),
        ("GRID", (0, 0), (-1, -1), 0.3, Color(*_GRAY)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(item_table)

    # ── Totais ────────────────────────────────────────────────────────────────
    section_title("Totais")
    totais_data = [
        [Paragraph("Subtotal", style("tl", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)),
         Paragraph(_fmt_money(sale.subtotal_amount), style("tv", fontSize=9, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT))],
        [Paragraph("Desconto", style("tl2", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)),
         Paragraph(f"- {_fmt_money(sale.discount_amount)}", style("tv2", fontSize=9, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT))],
        [Paragraph("Frete", style("tl3", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)),
         Paragraph(_fmt_money(sale.freight_amount), style("tv3", fontSize=9, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT))],
        [Paragraph("Tributos", style("tl4", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)),
         Paragraph(_fmt_money(sale.tax_amount), style("tv4", fontSize=9, fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT))],
        [Paragraph("TOTAL", style("ttotal", fontSize=11, fontName="Helvetica-Bold")),
         Paragraph(_fmt_money(sale.total_amount), style("ttotalv", fontSize=11, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
    ]
    total_table = Table(totais_data, colWidths=[col_w * 0.5, col_w * 0.5])
    total_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 4), (-1, 4), 1, Color(*_DARK)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(total_table)

    # ── Formas de pagamento ───────────────────────────────────────────────────
    section_title("Formas de Pagamento")
    for plan in payment_plans:
        story.append(Paragraph(
            f"• {_clean(plan.payment_method_name)} — {_fmt_money(plan.amount)}"
            + (f" · Venc: {_fmt_date(plan.due_date)}" if plan.due_date else ""),
            s_value,
        ))
    if not payment_plans:
        story.append(Paragraph("Nenhuma forma de pagamento cadastrada.", s_value))

    # ── Checklist de prontidão fiscal ─────────────────────────────────────────
    section_title("Checklist de Prontidão Fiscal")
    r = readiness
    if not r.issues:
        story.append(Paragraph("✓ Nenhum problema encontrado.", s_value))
    else:
        by_scope: dict[str, list[Any]] = {}
        for issue in r.issues:
            by_scope.setdefault(issue.scope, []).append(issue)
        scope_labels = {
            "company": "Empresa", "participant": "Destinatário",
            "item": "Itens", "operation": "Operação",
            "payment": "Pagamento", "totals": "Totais", "stock": "Estoque",
        }
        for scope, issues in by_scope.items():
            story.append(Paragraph(f"<b>{scope_labels.get(scope, scope.title())}</b>", s_issue_block))
            for issue in issues:
                icon = "✗" if issue.severity == "blocking" else "⚠"
                item_ref = f" (Item {issue.item_index + 1})" if issue.item_index is not None else ""
                p_style = s_issue_error if issue.severity == "blocking" else s_issue_warn
                story.append(Paragraph(f"{icon}{item_ref} {issue.message}", p_style))
                if issue.fix_hint:
                    story.append(Paragraph(f"    → {issue.fix_hint}", s_small_gray))

    # ── Observações ───────────────────────────────────────────────────────────
    if sale.notes:
        section_title("Observações")
        story.append(Paragraph(_clean(sale.notes), s_value))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(HR(_GRAY))
    story.append(Paragraph(
        f"Documento gerado pelo sistema ERP — sem valor fiscal · {generated_at}",
        s_footer,
    ))

    doc.build(story)
    return buffer.getvalue()
