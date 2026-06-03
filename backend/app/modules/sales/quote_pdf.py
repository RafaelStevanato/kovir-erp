"""Gerador de PDF de Orçamento para vendas no estado QUOTE.

Documento sem valor fiscal destinado ao cliente como proposta comercial.
Não mostra NCM, CFOP nem CST.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.db_models import CompanyDB
from app.modules.sales.db_models import SaleDB


_DARK = (0.15, 0.15, 0.15)
_GRAY = (0.50, 0.50, 0.50)
_BLUE = (0.10, 0.30, 0.65)
_LIGHT_GRAY_BG = (0.94, 0.94, 0.94)
_WHITE = (1.0, 1.0, 1.0)


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


def generate_quote_pdf(db: Session, sale: SaleDB, *, validity_days: int = 30) -> bytes:
    """Gera PDF de orçamento e retorna os bytes."""
    try:
        from reportlab.lib.colors import Color
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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

    company = db.query(CompanyDB).filter(CompanyDB.id == sale.company_id).first()
    participant_snapshot: dict = sale.participant_snapshot_json or {}
    items = sorted(sale.items, key=lambda i: i.created_at)
    payment_plans = sorted(sale.payment_plans, key=lambda p: p.created_at)

    validity_date = date.today() + timedelta(days=validity_days)
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

    s_title = style("title", fontSize=18, textColor=Color(*_BLUE), alignment=TA_CENTER, leading=22, fontName="Helvetica-Bold")
    s_subtitle = style("subtitle", fontSize=8, textColor=Color(*_GRAY), alignment=TA_CENTER, leading=11)
    s_section = style("section", fontSize=10, textColor=Color(*_BLUE), fontName="Helvetica-Bold", leading=14, spaceBefore=8)
    s_label = style("label", fontSize=7, textColor=Color(*_GRAY), leading=10)
    s_value = style("value", fontSize=9, textColor=Color(*_DARK), leading=12)
    s_small = style("small", fontSize=7, textColor=Color(*_DARK), leading=10)
    s_total_label = style("tlabel", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)
    s_footer = style("footer", fontSize=7, textColor=Color(*_GRAY), alignment=TA_CENTER, leading=10)
    s_validity = style("validity", fontSize=10, textColor=Color(*_BLUE), alignment=TA_CENTER, fontName="Helvetica-Bold", leading=14)

    story: list[Any] = []

    def HR(color: tuple = _GRAY, thickness: float = 0.5) -> HRFlowable:
        return HRFlowable(width="100%", thickness=thickness, color=Color(*color), spaceAfter=4, spaceBefore=2)

    def section_title(text: str) -> None:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(text.upper(), s_section))
        story.append(HR(_BLUE, 0.8))

    def row2(label1: str, val1: str, label2: str = "", val2: str = "") -> None:
        data = [[
            Paragraph(label1, s_label), Paragraph(val1, s_value),
            Paragraph(label2, s_label), Paragraph(val2, s_value),
        ]]
        t = Table(data, colWidths=[col_w * 0.15, col_w * 0.35, col_w * 0.15, col_w * 0.35])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)

    # ── Título ────────────────────────────────────────────────────────────────
    story.append(Paragraph("ORÇAMENTO", s_title))
    story.append(Paragraph(f"Gerado em {generated_at}", s_subtitle))
    story.append(Spacer(1, 3 * mm))

    validity_data = [[Paragraph(
        f"Válido até {_fmt_date(validity_date)} ({validity_days} dias)",
        s_validity,
    )]]
    validity_table = Table(validity_data, colWidths=[col_w])
    validity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), Color(*_LIGHT_GRAY_BG)),
        ("BOX", (0, 0), (-1, -1), 1, Color(*_BLUE)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(validity_table)
    story.append(Spacer(1, 3 * mm))

    # ── Emitente ──────────────────────────────────────────────────────────────
    section_title("Emitente")
    if company:
        row2("Razão Social / Nome", _clean(company.legal_name or company.trade_name),
             "CNPJ", _clean(company.cnpj))
        addr_parts = [
            company.address_street or "",
            company.address_number or "",
            company.address_city or "",
            company.address_state or "",
        ]
        addr = ", ".join(p for p in addr_parts if p)
        row2("Endereço", _clean(addr), "CEP", _clean(company.address_zip_code))
    else:
        story.append(Paragraph("Empresa não encontrada.", s_value))

    # ── Cliente ───────────────────────────────────────────────────────────────
    section_title("Cliente")
    ps = participant_snapshot
    row2("Nome / Razão Social", _clean(ps.get("name") or ps.get("legal_name")),
         "CPF / CNPJ", _clean(ps.get("document") or ps.get("cpf") or ps.get("cnpj")))
    addr_j = ps.get("address_json") or {}
    dest_addr = ", ".join(p for p in [
        addr_j.get("street", ""), addr_j.get("number", ""),
        addr_j.get("city", ""), addr_j.get("state", ""),
    ] if p)
    row2("Endereço", _clean(dest_addr), "CEP", _clean(addr_j.get("zip_code")))

    # ── Itens ─────────────────────────────────────────────────────────────────
    section_title("Itens")

    item_header = [
        Paragraph("#", s_label),
        Paragraph("Descrição", s_label),
        Paragraph("Qtd", s_label),
        Paragraph("Unitário", s_label),
        Paragraph("Total", s_label),
    ]
    item_rows = [item_header]

    for idx, item in enumerate(items, 1):
        item_rows.append([
            Paragraph(str(idx), s_small),
            Paragraph(_clean(item.description)[:80], s_small),
            Paragraph(f"{_clean(str(item.quantity))} {_clean(item.unit, '')}", s_small),
            Paragraph(_fmt_money(item.unit_price), s_small),
            Paragraph(_fmt_money(item.total_amount), s_small),
        ])

    item_table = Table(
        item_rows,
        colWidths=[col_w * 0.05, col_w * 0.45, col_w * 0.15, col_w * 0.17, col_w * 0.18],
    )
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), Color(*_BLUE)),
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
        [Paragraph("Subtotal", s_total_label), Paragraph(_fmt_money(sale.subtotal_amount), style("tv", fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
        [Paragraph("Desconto", s_total_label), Paragraph(f"- {_fmt_money(sale.discount_amount)}", style("tv2", fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
        [Paragraph("Frete", s_total_label), Paragraph(_fmt_money(sale.freight_amount), style("tv3", fontSize=9, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
        [Paragraph("TOTAL", style("ttotal", fontSize=11, fontName="Helvetica-Bold")),
         Paragraph(_fmt_money(sale.total_amount), style("ttotalv", fontSize=11, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
    ]
    total_table = Table(totais_data, colWidths=[col_w * 0.5, col_w * 0.5])
    total_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 3), (-1, 3), 1, Color(*_DARK)),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(total_table)

    # ── Formas de pagamento ───────────────────────────────────────────────────
    if payment_plans:
        section_title("Condições de Pagamento")
        for plan in payment_plans:
            story.append(Paragraph(
                f"• {_clean(plan.payment_method_name)} — {_fmt_money(plan.amount)}"
                + (f" · Venc: {_fmt_date(plan.due_date)}" if plan.due_date else ""),
                s_value,
            ))

    # ── Observações ───────────────────────────────────────────────────────────
    if sale.notes:
        section_title("Observações")
        story.append(Paragraph(_clean(sale.notes), s_value))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=Color(*_GRAY), spaceAfter=4, spaceBefore=2))
    story.append(Paragraph(
        f"Documento sem valor fiscal — válido até {_fmt_date(validity_date)} · "
        f"Documento gerado pelo sistema ERP — sem valor fiscal",
        s_footer,
    ))

    doc.build(story)
    return buffer.getvalue()
