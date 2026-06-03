"""Gerador de prévia PDF fiscal para vendas confirmadas.

Produz um PDF interno de consulta com todos os dados relevantes para
a emissão de NF-e, incluindo checklist de prontidão fiscal.

ESTE DOCUMENTO NÃO TEM VALIDADE FISCAL.

Dependência: reportlab (pip install reportlab)
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.modules.company.db_models import CompanyDB
from app.modules.participants.db_models import ParticipantDB
from app.modules.sales.db_models import SaleDB
from app.modules.sales.invoice_readiness import build_invoice_readiness


# ──────────────────────────────────────────────────────────────────────────────
# Paleta de cores e estilos
# ──────────────────────────────────────────────────────────────────────────────

_RED = (0.80, 0.10, 0.10)
_ORANGE = (0.90, 0.45, 0.00)
_GREEN = (0.10, 0.55, 0.10)
_GRAY = (0.50, 0.50, 0.50)
_DARK = (0.15, 0.15, 0.15)
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


def generate_fiscal_preview_pdf(db: Session, sale: SaleDB) -> bytes:
    """Gera o PDF de prévia fiscal e retorna os bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.colors import Color, HexColor
    except ImportError as exc:
        raise RuntimeError(
            "reportlab não instalado. Execute: pip install reportlab"
        ) from exc

    # ── Carrega dados ─────────────────────────────────────────────────────────
    company = db.query(CompanyDB).filter(CompanyDB.id == sale.company_id).first()
    readiness = build_invoice_readiness(db, sale)

    participant_snapshot: dict = sale.participant_snapshot_json or {}
    items = sorted(sale.items, key=lambda i: i.created_at)
    payment_plans = sorted(sale.payment_plans, key=lambda p: p.created_at)
    op_snapshot: dict = sale.operation_nature_snapshot_json or {}

    # ── Setup do documento ────────────────────────────────────────────────────
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

    def style(name: str = "Normal", **kw) -> ParagraphStyle:
        s = ParagraphStyle(name, parent=styles["Normal"], **kw)
        return s

    s_warning = style("warn", fontSize=9, textColor=Color(*_RED), alignment=TA_CENTER, leading=13)
    s_title = style("title", fontSize=16, textColor=Color(*_DARK), alignment=TA_CENTER, leading=20, fontName="Helvetica-Bold")
    s_subtitle = style("subtitle", fontSize=8, textColor=Color(*_GRAY), alignment=TA_CENTER, leading=11)
    s_section = style("section", fontSize=10, textColor=Color(*_BLUE), fontName="Helvetica-Bold", leading=14, spaceBefore=8)
    s_label = style("label", fontSize=7, textColor=Color(*_GRAY), leading=10)
    s_value = style("value", fontSize=9, textColor=Color(*_DARK), leading=12)
    s_small = style("small", fontSize=7, textColor=Color(*_GRAY), leading=10)
    s_issue_block = style("issue_b", fontSize=8, textColor=Color(*_DARK), leading=11)
    s_issue_error = style("issue_e", fontSize=8, textColor=Color(*_RED), fontName="Helvetica-Bold", leading=11)
    s_issue_warn = style("issue_w", fontSize=8, textColor=Color(*_ORANGE), leading=11)
    s_total_label = style("tlabel", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12)
    s_total_val = style("tval", fontSize=9, textColor=Color(*_DARK), fontName="Helvetica-Bold", leading=12, alignment=TA_RIGHT)

    story: list[Any] = []

    def HR(color: tuple = _GRAY, thickness: float = 0.5) -> HRFlowable:
        return HRFlowable(width="100%", thickness=thickness, color=Color(*color), spaceAfter=4, spaceBefore=2)

    def section_title(text: str) -> None:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(text.upper(), s_section))
        story.append(HR(_BLUE, 0.8))

    def row2(label1: str, val1: str, label2: str = "", val2: str = "") -> None:
        data = [
            [Paragraph(label1, s_label), Paragraph(val1, s_value),
             Paragraph(label2, s_label), Paragraph(val2, s_value)],
        ]
        t = Table(data, colWidths=[col_w * 0.15, col_w * 0.35, col_w * 0.15, col_w * 0.35])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)

    # ── Cabeçalho de aviso ────────────────────────────────────────────────────
    warning_box_data = [[
        Paragraph(
            "⚠ DOCUMENTO INTERNO — SEM VALIDADE FISCAL ⚠\n"
            "Esta prévia é exclusiva para conferência interna. "
            "Não substitui nota fiscal, não tem valor legal e não deve ser entregue ao cliente.",
            s_warning,
        )
    ]]
    warning_table = Table(warning_box_data, colWidths=[col_w])
    warning_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), Color(1.0, 0.95, 0.95)),
        ("BOX", (0, 0), (-1, -1), 1, Color(*_RED)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(warning_table)
    story.append(Spacer(1, 4 * mm))

    # ── Título ────────────────────────────────────────────────────────────────
    story.append(Paragraph("PRÉVIA FISCAL DO PEDIDO", s_title))
    generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    story.append(Paragraph(f"Gerado em {generated_at} · ID: {sale.id}", s_subtitle))
    story.append(Spacer(1, 3 * mm))

    # ── Status fiscal ─────────────────────────────────────────────────────────
    r = readiness
    if r.fiscal_status == "fiscal_ready":
        status_color = _GREEN
        status_text = "✓ PRONTO PARA FATURAR"
    elif r.blocking_count == 0:
        status_color = _ORANGE
        status_text = f"⚠ {r.warning_count} aviso(s) — revisão recomendada"
    else:
        status_color = _RED
        status_text = f"✗ {r.blocking_count} bloqueio(s) impedem o faturamento"

    status_data = [[Paragraph(status_text, style("ss", fontSize=11, textColor=Color(*status_color), fontName="Helvetica-Bold", alignment=TA_CENTER))]]
    st = Table(status_data, colWidths=[col_w])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), Color(*_LIGHT_GRAY_BG)),
        ("BOX", (0, 0), (-1, -1), 1.5, Color(*status_color)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(st)
    story.append(Spacer(1, 3 * mm))

    # ── Empresa emitente ──────────────────────────────────────────────────────
    section_title("Empresa Emitente")
    if company:
        row2("Razão Social", _clean(company.legal_name),
             "CNPJ", _clean(company.cnpj))
        row2("Nome Fantasia", _clean(company.trade_name),
             "IE", _clean(company.state_registration))
        row2("Regime Tributário", _clean(company.tax_regime),
             "CRT", _clean(company.crt))
        addr_parts = [
            company.address_street or "",
            company.address_number or "",
            company.address_district or "",
            company.address_city or "",
            company.address_state or "",
        ]
        addr = ", ".join(p for p in addr_parts if p)
        row2("Endereço", _clean(addr), "CEP", _clean(company.address_zip_code))
        row2("Município IBGE", _clean(company.address_ibge_municipality_code),
             "Ambiente Fiscal", _clean(company.fiscal_environment))
    else:
        story.append(Paragraph("Empresa não encontrada.", s_value))

    # ── Destinatário ──────────────────────────────────────────────────────────
    section_title("Destinatário")
    ps = participant_snapshot
    row2("Nome / Razão Social", _clean(ps.get("name") or ps.get("legal_name")),
         "Tipo", _clean(ps.get("person_type")))
    row2("CPF / CNPJ", _clean(ps.get("document") or ps.get("cpf") or ps.get("cnpj")),
         "Status", _clean(ps.get("status")))
    addr_j = ps.get("address_json") or {}
    dest_addr = ", ".join(p for p in [
        addr_j.get("street", ""), addr_j.get("number", ""),
        addr_j.get("district", ""), addr_j.get("city", ""),
        addr_j.get("state", ""),
    ] if p)
    row2("Endereço", _clean(dest_addr), "CEP", _clean(addr_j.get("zip_code")))
    fiscal_s = ps.get("fiscal_settings_json") or {}
    row2("Indicador IE", _clean(fiscal_s.get("ie_indicator")),
         "IE", _clean(fiscal_s.get("state_registration")))

    # ── Dados da operação ─────────────────────────────────────────────────────
    section_title("Dados da Operação")
    row2("Natureza da Operação", _clean(op_snapshot.get("name") or sale.operation_nature),
         "Tipo de Venda", _clean(sale.sale_type))
    row2("Data de Emissão", _fmt_date(sale.issue_date),
         "Data da Operação", _fmt_date(sale.operation_date))
    row2("Status da Venda", _clean(sale.status),
         "Status Fiscal", _clean(sale.fiscal_status))
    row2("Motivo da Operação", _clean(sale.operation_nature_reason),
         "Competência", _fmt_date(sale.competency_date))

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
        ncm_cfop = f"{ncm} / {cfop}"
        cst = _clean(fsn.get("cst_icms"), "—")
        item_rows.append([
            Paragraph(str(idx), s_small),
            Paragraph(_clean(item.description)[:60], s_small),
            Paragraph(ncm_cfop, s_small),
            Paragraph(cst, s_small),
            Paragraph(f"{_clean(str(item.quantity))} {_clean(item.unit, '')}", s_small),
            Paragraph(_fmt_money(item.unit_price), s_small),
            Paragraph(_fmt_money(item.total_amount), s_small),
        ])

    item_table = Table(
        item_rows,
        colWidths=[
            col_w * 0.04,
            col_w * 0.28,
            col_w * 0.16,
            col_w * 0.10,
            col_w * 0.12,
            col_w * 0.14,
            col_w * 0.16,
        ],
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
        [Paragraph("Subtotal", s_total_label), Paragraph(_fmt_money(sale.subtotal_amount), s_total_val)],
        [Paragraph("Desconto", s_total_label), Paragraph(f"- {_fmt_money(sale.discount_amount)}", s_total_val)],
        [Paragraph("Frete", s_total_label), Paragraph(_fmt_money(sale.freight_amount), s_total_val)],
        [Paragraph("Tributos", s_total_label), Paragraph(_fmt_money(sale.tax_amount), s_total_val)],
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

    if not r.issues:
        story.append(Paragraph("✓ Nenhum problema encontrado. Documento pronto para faturamento.", s_value))
    else:
        # Agrupa por escopo
        by_scope: dict[str, list[Any]] = {}
        for issue in r.issues:
            by_scope.setdefault(issue.scope, []).append(issue)

        scope_labels = {
            "company": "Empresa",
            "participant": "Destinatário",
            "item": "Itens",
            "operation": "Operação",
            "payment": "Pagamento",
            "totals": "Totais",
            "stock": "Estoque",
        }

        for scope, issues in by_scope.items():
            scope_label = scope_labels.get(scope, scope.title())
            story.append(Paragraph(f"<b>{scope_label}</b>", s_issue_block))
            for issue in issues:
                icon = "✗" if issue.severity == "blocking" else "⚠"
                item_ref = f" (Item {issue.item_index + 1})" if issue.item_index is not None else ""
                line = f"{icon}{item_ref} {issue.message}"
                p_style = s_issue_error if issue.severity == "blocking" else s_issue_warn
                story.append(Paragraph(line, p_style))
                if issue.fix_hint:
                    story.append(Paragraph(f"    → {issue.fix_hint}", s_small))

    # ── Observações ───────────────────────────────────────────────────────────
    if sale.notes:
        section_title("Observações")
        story.append(Paragraph(_clean(sale.notes), s_value))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(HR(_GRAY))
    story.append(Paragraph(
        f"DOCUMENTO INTERNO — SEM VALIDADE FISCAL · Documento gerado pelo sistema ERP — sem valor fiscal · {generated_at}",
        style("footer", fontSize=7, textColor=Color(*_GRAY), alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()
