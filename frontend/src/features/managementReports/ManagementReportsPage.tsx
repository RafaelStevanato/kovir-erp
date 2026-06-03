import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  BarChart3,
  Building2,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FileText,
  Gauge,
  ListChecks,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Table2,
  WalletCards,
  XCircle,
} from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import { buildExportFileName } from "../../lib/exportStandard"
import {
  dateCell,
  dateTimeCell,
  exportCsv as exportCsvFile,
  exportXlsx as exportXlsxFile,
  exportXlsxWorkbook,
  integerCell,
  moneyCell,
  type ExportCell,
  type ExportSheet,
  type ExportTable,
} from "../../lib/exportTable"
import {
  getAccountantPackReport,
  getAvailableReportCompanies,
  getFinancialCloseMvpReport,
  getFinancialCycleReport,
  getHealthIndicatorDetailsReport,
  getManagementCompanyContext,
  getManagementReportRules,
  getMvpHealthReport,
  getOperationalBacklogReport,
  getPreparatoryFiscalDocumentsReport,
  getTitleReferencesReport,
} from "./managementReportsApi"
import type {
  AccountantPackReport,
  AvailableCompaniesReport,
  BacklogMovementItem,
  BacklogStatementLineItem,
  BacklogTitleItem,
  CompanyContextReport,
  DirectionSummary,
  FinancialCloseMvpReport,
  FinancialAccountBalanceReport,
  FinancialCycleReport,
  HealthIndicatorCell,
  HealthIndicatorDetailsReport,
  HealthIndicatorKey,
  ManagementReportRules,
  MvpHealthReport,
  OperationalBacklogReport,
  PreparatoryFiscalDocumentsReport,
  TitleReference,
  TitleReferencesReport,
} from "./types"

type TabKey = "overview" | "cycle" | "backlog" | "titles" | "fiscalPrep" | "closing" | "accountant" | "rules"
type Notice = { type: "success" | "error"; message: string } | null
type PeriodPreset = "month" | "30d" | "quarter" | "year" | "custom"
type BacklogExportKey = Extract<
  HealthIndicatorKey,
  "overdue_titles" | "titles_without_clear_origin" | "unreconciled_movements" | "unmatched_bank_statement_lines"
>
type BacklogExportState = BacklogExportKey | "all" | null
type FiscalExportKey = "sales" | "purchases" | "titles" | "documents" | "all"
type AccountantExportBlock =
  | "receivable_open"
  | "receivable_overdue"
  | "payable_open"
  | "payable_overdue"
  | "cash_flow_projected"
  | "cash_flow_realized"
  | "reconciliation_pendencies"
  | "fiscal_pendencies"
  | "settlements_without_movement"
  | "settlement_cash_difference"
  | "ignored_quotes"
  | "ignored_drafts"
type FiscalExportState = FiscalExportKey | null

const BACKLOG_EXPORT_KEYS: BacklogExportKey[] = [
  "overdue_titles",
  "titles_without_clear_origin",
  "unreconciled_movements",
  "unmatched_bank_statement_lines",
]

const PRESETS: Array<{ key: PeriodPreset; label: string }> = [
  { key: "month", label: "Este mês" },
  { key: "30d", label: "30 dias" },
  { key: "quarter", label: "Trimestre" },
  { key: "year", label: "Este ano" },
  { key: "custom", label: "Personalizado" },
]

function getPeriodDates(preset: PeriodPreset): { start: string; end: string } | null {
  if (preset === "custom") return null
  const now = new Date()
  const end = now.toISOString().slice(0, 10)
  switch (preset) {
    case "month":
      return { start: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10), end }
    case "30d":
      return { start: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10), end }
    case "quarter": {
      const q = Math.floor(now.getMonth() / 3) * 3
      return { start: new Date(now.getFullYear(), q, 1).toISOString().slice(0, 10), end }
    }
    case "year":
      return { start: new Date(now.getFullYear(), 0, 1).toISOString().slice(0, 10), end }
    default:
      return null
  }
}

function monthStart() {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10)
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function toNumber(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0
  const parsed = Number(String(value).replace(",", "."))
  return Number.isFinite(parsed) ? parsed : 0
}

function formatMoney(value?: string | number | null) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(toNumber(value))
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const normalized = value.slice(0, 10)
  const [year, month, day] = normalized.split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function formatDateTime(value?: string | null) {
  if (!value) return "—"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed)
}

function directionLabel(direction?: string | null) {
  const labels: Record<string, string> = {
    receivable: "A receber",
    payable: "A pagar",
    inflow: "Entrada",
    outflow: "Saída",
  }
  return labels[direction ?? ""] ?? direction ?? "—"
}

function statusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    healthy: "Saudável",
    attention: "Atenção",
    blocked: "Bloqueado",
    PASS: "Aprovado",
    WARN: "Atenção",
    FAIL: "Falhou",
    READY: "Pronto",
    ATTENTION: "Atenção",
    BLOCKED: "Bloqueado",
    active: "Ativa",
    inactive: "Inativa",
    draft: "Rascunho",
    open: "Em aberto",
    partially_paid: "Pago parcial",
    partially_received: "Recebido parcial",
    received: "Recebido",
    paid: "Pago",
    overdue: "Vencido",
    cancelled: "Cancelado",
    written_off: "Baixado sem pagamento",
    renegotiated: "Renegociado",
    not_started: "Não iniciado",
    in_collection: "Em cobrança",
    closed: "Fechado",
    pending_document: "Documento pendente",
    pending_classification: "Classificação pendente",
    linked: "Vinculado",
    not_required: "Não exigido",
    fiscal_ready: "Pronto fiscalmente",
    document_generated: "Documento gerado",
    document_cancelled: "Documento cancelado",
    pending: "Pendente",
    processing: "Processando",
    contingency: "Contingência",
    authorized: "Autorizado",
    issued: "Emitido",
    denied: "Denegado",
    error: "Erro",
    matched: "Conciliado",
    reconciled: "Conciliado",
    divergent: "Divergente",
    ignored: "Ignorado",
    posted: "Postado",
    reversed: "Estornado",
  }
  return labels[status ?? ""] ?? status ?? "—"
}

function statusTone(status?: string | null) {
  if (["healthy", "paid", "received", "matched", "reconciled", "active", "posted", "closed", "linked", "not_required", "fiscal_ready", "document_generated", "authorized", "issued", "PASS", "READY"].includes(status ?? "")) return "success"
  if (["attention", "open", "draft", "partially_paid", "partially_received", "not_started", "in_collection", "pending_document", "pending_classification", "pending", "processing", "contingency", "divergent", "renegotiated", "WARN", "ATTENTION"].includes(status ?? "")) return "warning"
  if (["blocked", "overdue", "cancelled", "document_cancelled", "denied", "error", "reversed", "FAIL", "BLOCKED"].includes(status ?? "")) return "danger"
  return "neutral"
}

function scoreColor(score?: number): string {
  if ((score ?? 0) >= 85) return "#16a34a"
  if ((score ?? 0) >= 70) return "#d97706"
  return "#dc2626"
}

function exportRows(rows: ExportTable, baseName: string, format: "csv" | "xlsx") {
  if (rows.length <= 1) return
  const fileName = buildExportFileName("kovir_relatorios", baseName, format)
  if (format === "csv") {
    exportCsvFile(rows, fileName)
    return
  }
  exportXlsxFile(rows, "Relatorio", fileName)
}

function formatInstallment(item: TitleReference): string {
  if (!item.installment_number || !item.installment_total) return ""
  return `${item.installment_number}/${item.installment_total}`
}

function titleRows(report: TitleReferencesReport | null): ExportTable {
  const items = report?.items ?? []
  return [
    [
      "Empresa",
      "Referência",
      "ID técnico",
      "Direção",
      "Tipo",
      "Status",
      "Status cobrança",
      "Status fiscal",
      "Participante",
      "Documento participante",
      "Vencimento",
      "Dias em atraso",
      "Parcela",
      "Valor líquido",
      "Valor baixado",
      "Valor aberto",
      "Documento",
      "Pedido",
      "Origem",
      "Forma de pagamento",
      "Conta prevista",
      "Emissão",
      "Competência",
      "Observação operacional",
    ],
    ...items.map((item) => [
      item.company_display_name,
      item.human_reference,
      item.id,
      directionLabel(item.direction),
      item.title_type ?? "",
      statusLabel(item.status),
      statusLabel(item.collection_status),
      statusLabel(item.fiscal_status),
      item.participant_name ?? "",
      item.participant_document ?? "",
      dateCell(item.due_date),
      integerCell(daysOverdue(item.due_date)),
      formatInstallment(item),
      moneyCell(item.net_amount),
      moneyCell(item.paid_amount),
      moneyCell(item.open_amount),
      item.document_reference ?? "",
      item.sale_number_text ?? item.sale_id ?? "",
      [item.source_type, item.source_id].filter(Boolean).join(" / "),
      item.payment_method_name ?? "",
      item.expected_financial_account_name ?? "",
      dateCell(item.issue_date),
      dateCell(item.competency_date),
      "Título financeiro não é dinheiro; baixa/movimento/conciliação são fatos separados.",
    ]),
  ]
}

function fiscalSaleReason(item: PreparatoryFiscalDocumentsReport["sales_documents"][number]): string {
  const reasons: string[] = []
  if (item.missing_issue_date) reasons.push("sem data de emissão")
  if (item.pending_fiscal_status) reasons.push(`status fiscal ${statusLabel(item.fiscal_status)}`)
  if (item.blocked_fiscal_status) reasons.push("bloqueada fiscalmente")
  if (item.cancelled_fiscal_document_status) reasons.push("documento fiscal cancelado")
  return reasons.join("; ") || "pendência fiscal"
}

function fiscalPurchaseReason(item: PreparatoryFiscalDocumentsReport["purchase_documents"][number]): string {
  const reasons: string[] = []
  if (item.missing_issue_date) reasons.push("sem data de emissão")
  if (item.missing_document_number) reasons.push("sem número de documento")
  if (item.pending_fiscal_status) reasons.push(`status fiscal ${statusLabel(item.fiscal_status)}`)
  if (item.divergent_fiscal_status) reasons.push("vínculo fiscal divergente")
  return reasons.join("; ") || "documento fiscal incompleto"
}

function fiscalDocumentReason(item: PreparatoryFiscalDocumentsReport["fiscal_documents"][number]): string {
  if (item.error_message) return item.error_message
  if (item.error_code) return `Código de erro ${item.error_code}`
  if (item.status === "processing" || item.status === "pending" || item.status === "contingency") return "aguardando processamento/autorização"
  if (item.status === "cancelled") return "documento cancelado"
  if (item.status === "authorized" || item.status === "issued") return "documento autorizado"
  return statusLabel(item.status)
}

function fiscalRows(report: PreparatoryFiscalDocumentsReport | null, group: FiscalExportKey = "all"): ExportTable {
  const shouldInclude = (key: FiscalExportKey) => group === "all" || group === key
  const context = [
    report?.company_display_name ?? "",
    dateCell(report?.period.start_date),
    dateCell(report?.period.end_date),
  ]

  return [
    [
      "Grupo",
      "Empresa",
      "Período inicial",
      "Período final",
      "Referência",
      "Tipo",
      "Status operacional",
      "Status fiscal/documento",
      "Participante",
      "Documento participante",
      "Data operacional",
      "Data emissão",
      "Vencimento",
      "Valor total",
      "Valor aberto",
      "Pedido",
      "Documento fiscal",
      "Série",
      "Chave de acesso",
      "Protocolo",
      "Motivo / observação",
      "ID técnico",
    ],
    ...(shouldInclude("sales")
      ? (report?.sales_documents ?? []).map((item) => [
          "Venda pendente",
          ...context,
          item.sale_number_text ?? item.sale_id,
          item.sale_type,
          statusLabel(item.status),
          statusLabel(item.fiscal_status),
          item.participant_name ?? "",
          "",
          dateCell(item.operation_date),
          dateCell(item.issue_date),
          "",
          moneyCell(item.total_amount),
          "",
          item.sale_number_text ?? item.sale_id,
          "",
          "",
          "",
          "",
          fiscalSaleReason(item),
          item.sale_id,
        ])
      : []),
    ...(shouldInclude("purchases")
      ? (report?.purchase_documents ?? []).map((item) => [
          "Compra pendente",
          ...context,
          item.document_number ?? item.purchase_id,
          item.purchase_type,
          statusLabel(item.status),
          statusLabel(item.fiscal_status),
          item.participant_name ?? "",
          "",
          dateCell(item.operation_date),
          dateCell(item.issue_date),
          "",
          moneyCell(item.total_amount),
          "",
          "",
          item.document_number ?? "",
          item.document_series ?? "",
          item.access_key ?? "",
          "",
          fiscalPurchaseReason(item),
          item.purchase_id,
        ])
      : []),
    ...(shouldInclude("titles")
      ? (report?.title_documents ?? []).map((item) => [
          "Título com pendência fiscal",
          ...context,
          item.document_reference ?? item.sale_number_text ?? item.id,
          item.title_type ?? "",
          statusLabel(item.status),
          statusLabel(item.fiscal_status),
          item.participant_name ?? "",
          item.participant_document ?? "",
          "",
          dateCell(item.issue_date),
          dateCell(item.due_date),
          moneyCell(item.net_amount),
          moneyCell(item.open_amount),
          item.sale_number_text ?? item.sale_id ?? "",
          item.document_reference ?? "",
          "",
          "",
          "",
          `Parcela ${item.installment_number}/${item.installment_total}; título financeiro não é documento fiscal.`,
          item.id,
        ])
      : []),
    ...(shouldInclude("documents")
      ? (report?.fiscal_documents ?? []).map((item) => [
          "Documento fiscal registrado",
          ...context,
          item.reference,
          item.document_type,
          statusLabel(item.status),
          item.focus_status ?? statusLabel(item.status),
          item.participant_name ?? "",
          "",
          dateTimeCell(item.created_at),
          dateTimeCell(item.issued_at ?? item.authorized_at),
          "",
          moneyCell(item.sale_total_amount),
          "",
          item.sale_number_text ?? item.sale_id,
          item.number ?? "",
          item.serie ?? "",
          item.access_key ?? "",
          item.protocol ?? "",
          fiscalDocumentReason(item),
          item.id,
        ])
      : []),
  ]
}

const CLOSING_EVIDENCE_LABELS: Record<string, string> = {
  fiscal_documents_error: "Documentos fiscais com erro",
  pending_items: "Pendencias fiscais/preparatorias",
  pending_sales_documents: "Vendas fiscais pendentes",
  pending_purchase_documents: "Compras fiscais pendentes",
  pending_fiscal_titles: "Titulos fiscais pendentes",
  fiscal_documents_pending: "Documentos fiscais processando",
  pending_fiscal_open_amount: "Valor aberto com pendencia fiscal",
  unreconciled_movements: "Movimentos sem conciliacao",
  unreconciled_amount: "Valor sem conciliacao",
  pending_statement_lines: "Linhas de extrato pendentes",
  divergent_items: "Itens divergentes",
  duplicate_balance_rows: "Duplicidades de saldo",
  overdue_count: "Titulos vencidos",
  overdue_amount: "Valor vencido",
}

function closingEvidenceValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "0"
  if (key.includes("amount")) return formatMoney(String(value))
  return String(value)
}

function closingEvidenceText(evidence: Record<string, unknown>): string {
  return Object.entries(evidence)
    .map(([key, value]) => `${CLOSING_EVIDENCE_LABELS[key] ?? key}: ${closingEvidenceValue(key, value)}`)
    .join("; ")
}

function closingRows(report: FinancialCloseMvpReport | null): ExportTable {
  const context = [
    report?.company_display_name ?? "",
    dateCell(report?.period.start_date),
    dateCell(report?.period.end_date),
    dateCell(report?.reference_date),
    dateTimeCell(report?.generated_at),
  ]

  return [
    [
      "Grupo",
      "Empresa",
      "Periodo inicial",
      "Periodo final",
      "Data de referencia",
      "Gerado em",
      "Indicador",
      "Status",
      "Bloqueante",
      "Quantidade",
      "Valor",
      "Evidencia",
      "Observacao",
    ],
    [
      "Resumo",
      ...context,
      "Status de fechamento",
      statusLabel(report?.close_status),
      report?.can_close_with_warnings ? "Nao ha bloqueio estrutural" : "Bloqueado",
      "",
      "",
      `can_close_mvp=${String(report?.can_close_mvp ?? false)}; can_close_with_warnings=${String(report?.can_close_with_warnings ?? false)}`,
      "Fechamento e leitura de prontidao; nao cria lancamento contabil.",
    ],
    [
      "Snapshot",
      ...context,
      "A receber aberto",
      "",
      "",
      integerCell(report?.snapshot.open_receivable_count ?? 0),
      moneyCell(report?.snapshot.open_receivable_amount),
      "",
      "Titulos ativos no periodo.",
    ],
    [
      "Snapshot",
      ...context,
      "A pagar aberto",
      "",
      "",
      integerCell(report?.snapshot.open_payable_count ?? 0),
      moneyCell(report?.snapshot.open_payable_amount),
      "",
      "Obrigacoes ativas no periodo.",
    ],
    [
      "Snapshot",
      ...context,
      "Titulos vencidos",
      "",
      "",
      integerCell(report?.snapshot.overdue_count ?? 0),
      moneyCell(report?.snapshot.overdue_amount),
      "",
      "Alerta operacional, nao altera caixa por si so.",
    ],
    [
      "Snapshot",
      ...context,
      "Conciliação pendente",
      "",
      "",
      integerCell((report?.snapshot.unreconciled_movements ?? 0) + (report?.snapshot.pending_statement_lines ?? 0)),
      moneyCell(report?.snapshot.unreconciled_amount),
      `Divergentes: ${report?.snapshot.divergent_items ?? 0}`,
      "Bloqueia confianca de fechamento quando houver pendencia.",
    ],
    [
      "Snapshot",
      ...context,
      "Pendencias fiscais",
      "",
      "",
      integerCell((report?.snapshot.fiscal_preparatory_pending ?? 0) + (report?.snapshot.fiscal_documents_pending ?? 0) + (report?.snapshot.fiscal_documents_error ?? 0)),
      "",
      `Preparatórias: ${report?.snapshot.fiscal_preparatory_pending ?? 0}; processando: ${report?.snapshot.fiscal_documents_pending ?? 0}; erros: ${report?.snapshot.fiscal_documents_error ?? 0}`,
      "Erro fiscal bloqueia; pendencia preparatoria gera atencao.",
    ],
    ...(report?.checklist ?? []).map((item) => [
      "Checklist",
      ...context,
      item.label,
      statusLabel(item.status),
      item.blocking ? "Sim" : "Nao",
      "",
      "",
      closingEvidenceText(item.evidence),
      item.status === "FAIL" ? "Corrigir antes de confiar no fechamento." : item.status === "WARN" ? "Revisar antes de fechar sem ressalva." : "Sem acao obrigatoria.",
    ]),
    ...(report?.recommended_actions ?? []).map((action) => [
      "Acao recomendada",
      ...context,
      action,
      "",
      "",
      "",
      "",
      "",
      "",
    ]),
  ]
}

function cycleRows(cycle: FinancialCycleReport | null): ExportTable {
  if (!cycle) return []
  const context = [
    cycle.company_display_name,
    dateCell(cycle.period.start_date),
    dateCell(cycle.period.end_date),
  ]
  return [
    [
      "Grupo",
      "Empresa",
      "Período inicial",
      "Período final",
      "Direção / Conta",
      "Quantidade",
      "Quantidade ativa",
      "Valor líquido",
      "Valor aberto ativo",
      "Valor vencido",
      "Valor liquidado no título",
      "Valor movimentado",
      "Valor conciliado",
      "Valor pendente de conciliação",
      "Saldo atual",
      "Observação",
    ],
    ...cycle.titles_by_direction.map((row) => [
      "Títulos",
      ...context,
      directionLabel(row.direction),
      integerCell(row.total_titles ?? 0),
      integerCell(row.active_titles ?? 0),
      moneyCell(row.net_amount ?? "0.00"),
      moneyCell(row.active_open_amount ?? "0.00"),
      moneyCell(row.overdue_amount ?? "0.00"),
      "",
      "",
      "",
      "",
      "",
      "Direitos/obrigações por vencimento; não é caixa realizado.",
    ]),
    ...cycle.settlements_by_direction.map((row) => [
      "Baixas",
      ...context,
      directionLabel(row.direction),
      integerCell(row.total_settlements ?? 0),
      "",
      "",
      "",
      "",
      moneyCell(row.title_settled_amount ?? "0.00"),
      moneyCell(row.movement_amount ?? "0.00"),
      "",
      "",
      "",
      "Baixa/liquidação realizada; não é conciliação bancária.",
    ]),
    ...cycle.movements_by_direction.map((row) => [
      "Movimentos",
      ...context,
      directionLabel(row.direction),
      integerCell(row.total_movements ?? 0),
      "",
      "",
      "",
      "",
      "",
      moneyCell(row.amount ?? "0.00"),
      moneyCell(row.reconciled_amount ?? "0.00"),
      moneyCell(row.unreconciled_amount ?? "0.00"),
      "",
      "Dinheiro interno registrado; conciliação é conferência posterior.",
    ]),
    ...cycle.financial_account_balances.map((row) => [
      "Saldos internos",
      ...context,
      row.financial_account_name,
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      "",
      moneyCell(row.balance_amount),
      "Saldo atual materializado por conta; não é saldo final do período.",
    ]),
  ]
}

function accountantRows(report: AccountantPackReport | null): ExportTable {
  if (!report) return []
  const indicators = report.indicators
  const consistency = report.consistency_checks
  const ignored = report.operational_ignored
  return [
    ["Campo", "Valor"],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    ["Data de referencia", dateCell(report.filters_used.reference_date)],
    ["Empresa", report.company_display_name],
    ["Snapshot versao", report.snapshot.version],
    ["Snapshot gerado em", dateTimeCell(report.snapshot.generated_at)],
    ["Snapshot chave", report.snapshot.snapshot_key],
    ["Modo de calculo", report.snapshot.calculation_mode],
    [],
    ["Indicador", "Escopo", "Quantidade", "Valor entrada/1", "Valor saida/2", "Liquido / observacao"],
    ["Contas a receber em aberto", "posicao atual", integerCell(indicators.accounts_receivable_open.count), moneyCell(indicators.accounts_receivable_open.amount), "", "inclui recebiveis parcialmente recebidos"],
    ["Contas a receber vencidas", "posicao atual", integerCell(indicators.accounts_receivable_overdue.count), moneyCell(indicators.accounts_receivable_overdue.amount), "", "due_date menor que data de referencia Brasil"],
    ["Contas a pagar em aberto", "posicao atual", integerCell(indicators.accounts_payable_open.count), moneyCell(indicators.accounts_payable_open.amount), "", "inclui pagaveis parcialmente pagos"],
    ["Contas a pagar vencidas", "posicao atual", integerCell(indicators.accounts_payable_overdue.count), moneyCell(indicators.accounts_payable_overdue.amount), "", "due_date menor que data de referencia Brasil"],
    ["Fluxo de caixa previsto", "periodo por vencimento", "", moneyCell(indicators.cash_flow_projected.inflow_amount), moneyCell(indicators.cash_flow_projected.outflow_amount), moneyCell(indicators.cash_flow_projected.net_amount)],
    ["Fluxo de caixa realizado", "periodo por baixa", "", moneyCell(indicators.cash_flow_realized.inflow_amount), moneyCell(indicators.cash_flow_realized.outflow_amount), moneyCell(indicators.cash_flow_realized.net_amount)],
    ["Pendencias de conciliacao", "periodo", integerCell(indicators.reconciliation_pendencies.unreconciled_movements), "movimentos internos", integerCell(indicators.reconciliation_pendencies.unmatched_statement_lines), "linhas de extrato"],
    ["Pendencias documentais/fiscais", "periodo", integerCell(indicators.fiscal_document_pendencies.pending_sales_documents + indicators.fiscal_document_pendencies.pending_purchase_documents + indicators.fiscal_document_pendencies.pending_fiscal_titles), moneyCell(indicators.fiscal_document_pendencies.pending_fiscal_open_amount), integerCell(indicators.fiscal_document_pendencies.fiscal_documents_error ?? 0), "erros fiscais bloqueiam confianca"],
    ["Orcamentos ignorados", "periodo", integerCell(ignored.sale_quotes_ignored_count), moneyCell(ignored.sale_quotes_ignored_amount), "", "nao sao venda realizada"],
    ["Compras em rascunho ignoradas", "periodo", integerCell(ignored.purchase_drafts_ignored_count), moneyCell(ignored.purchase_drafts_ignored_amount), "", "nao sao obrigacao confirmada"],
    [],
    ["Consistencia", "Quantidade", "Valor settlements", "Valor movimentos", "Diferenca", "Observacao"],
    ["Baixas com movimento financeiro", integerCell(consistency.active_settlements), moneyCell(consistency.settlement_movement_amount), moneyCell(consistency.posted_movement_amount), moneyCell(consistency.difference_amount), "diferenca deve ser zero"],
    ["Baixas sem movimento vinculado", integerCell(consistency.settlements_without_movement_count), moneyCell(consistency.settlements_without_movement_amount), "", "", "deve ser zero"],
    ["Baixas com multiplos movimentos", integerCell(consistency.settlements_with_multiple_movements), "", "", "", "revisar duplicidade"],
    [],
    ["Saldo por conta financeira", "Tipo", "Moeda", "Saldo atual", "Observacao"],
    ...report.balances_by_account.map((row) => [row.financial_account_name, row.account_type, row.currency ?? "BRL", moneyCell(row.balance_amount), "posicao atual; nao e saldo final do periodo"]),
    [],
    ["Movimentacoes por periodo", "Quantidade", "Valor", "Valor conciliado", "Valor pendente", "Pendentes"],
    ...report.movements_by_period.map((row) => [directionLabel(row.direction), integerCell(row.total_movements), moneyCell(row.amount), moneyCell(row.reconciled_amount ?? "0.00"), moneyCell(row.unreconciled_amount ?? "0.00"), integerCell(row.unreconciled_movements)]),
    [],
    ["Vendas realizadas no periodo", "Quantidade", "Total comercial", "Total a receber", "Total fiscal"],
    ...report.sales_by_period.map((row) => [row.sale_type, integerCell(row.total_sales), moneyCell(row.total_amount), moneyCell(row.receivable_total_amount ?? "0.00"), moneyCell(row.invoice_total_amount ?? "0.00")]),
    [],
    ["Compras confirmadas no periodo", "Quantidade", "Total comercial", "Total a pagar", "Total fiscal"],
    ...report.purchases_by_period.map((row) => [row.purchase_type, integerCell(row.total_purchases), moneyCell(row.total_amount), moneyCell(row.payable_total_amount ?? "0.00"), moneyCell(row.invoice_total_amount ?? "0.00")]),
    [],
    ["Notas"],
    ...report.notes.map((note) => [note]),
  ]
}

const ACCOUNTANT_ACTIVE_TITLE_STATUSES = new Set(["open", "partially_paid", "partially_received", "overdue"])
const ACCOUNTANT_PENDING_RECONCILIATION_STATUSES = new Set(["pending", "divergent"])

function isAccountantActiveTitle(item: AccountantPackReport["open_title_details"][number]): boolean {
  return ACCOUNTANT_ACTIVE_TITLE_STATUSES.has(item.status)
}

function isAccountantOverdueTitle(report: AccountantPackReport, item: AccountantPackReport["open_title_details"][number]): boolean {
  const referenceDate = report.filters_used.reference_date
  return Boolean(referenceDate && item.due_date < referenceDate)
}

function accountantTitleRowsByDirection(
  report: AccountantPackReport,
  direction: "receivable" | "payable",
  overdueOnly = false,
): AccountantPackReport["open_title_details"] {
  return report.open_title_details.filter(
    (item) => item.direction === direction && isAccountantActiveTitle(item) && (!overdueOnly || isAccountantOverdueTitle(report, item)),
  )
}

function accountantProjectedTitleRows(report: AccountantPackReport): AccountantPackReport["period_title_details"] {
  return report.period_title_details.filter(isAccountantActiveTitle)
}

function accountantPendingMovementRows(report: AccountantPackReport): AccountantPackReport["movement_details"] {
  return report.movement_details.filter((item) => ACCOUNTANT_PENDING_RECONCILIATION_STATUSES.has(item.reconciliation_status))
}

function accountantPendingStatementRows(report: AccountantPackReport): AccountantPackReport["statement_line_details"] {
  return report.statement_line_details.filter((item) => ACCOUNTANT_PENDING_RECONCILIATION_STATUSES.has(item.status))
}

function accountantTitleDetailRows(
  report: AccountantPackReport,
  title: string,
  items: AccountantPackReport["open_title_details"],
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID tecnico",
      "Direcao",
      "Tipo",
      "Status",
      "Cobranca",
      "Fiscal",
      "Referencia",
      "Pedido",
      "Participante",
      "Documento participante",
      "Metodo",
      "Conta prevista",
      "Emissao",
      "Competencia",
      "Vencimento",
      "Pagamento previsto",
      "Parcela",
      "Valor bruto",
      "Valor liquido",
      "Valor recebido/pago",
      "Valor em aberto",
      "Origem",
    ],
    ...items.map((item) => [
      item.id,
      directionLabel(item.direction),
      item.title_type ?? "",
      statusLabel(item.status),
      statusLabel(item.collection_status),
      statusLabel(item.fiscal_status),
      item.document_reference ?? "",
      item.sale_number_text ?? item.sale_id ?? "",
      item.participant_name ?? "",
      item.participant_document ?? "",
      item.payment_method_name ?? "",
      item.financial_account_name ?? "",
      dateCell(item.issue_date),
      dateCell(item.competency_date),
      dateCell(item.due_date),
      dateCell(item.expected_payment_date),
      `${item.installment_number}/${item.installment_total}`,
      moneyCell(item.gross_amount),
      moneyCell(item.net_amount),
      moneyCell(item.paid_amount),
      moneyCell(item.open_amount),
      `${item.source_type ?? ""}:${item.source_id ?? ""}`,
    ]),
  ]
}

function accountantSettlementRows(
  report: AccountantPackReport,
  title = "Baixas / liquidacoes do periodo",
  items = report.settlement_details,
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID baixa",
      "Direcao",
      "Tipo",
      "Status",
      "Data baixa",
      "Competencia",
      "Titulo",
      "Referencia titulo",
      "Participante",
      "Conta financeira",
      "Metodo",
      "Valor pago/recebido",
      "Desconto",
      "Juros",
      "Multa",
      "Taxa",
      "Valor liquidado no titulo",
      "Valor movimentado",
      "Movimentos vinculados",
      "Valor dos movimentos",
      "Evidencia",
      "Origem",
    ],
    ...items.map((item) => [
      item.id,
      directionLabel(item.direction),
      item.settlement_type,
      statusLabel(item.status),
      dateCell(item.settlement_date),
      dateCell(item.competency_date),
      item.financial_title_id,
      item.title_reference ?? "",
      item.participant_name ?? "",
      item.financial_account_name ?? "",
      item.payment_method_name ?? "",
      moneyCell(item.received_amount),
      moneyCell(item.discount_amount),
      moneyCell(item.interest_amount),
      moneyCell(item.penalty_amount),
      moneyCell(item.fee_amount),
      moneyCell(item.title_settled_amount),
      moneyCell(item.movement_amount),
      integerCell(item.linked_movement_count),
      moneyCell(item.linked_movement_amount),
      item.evidence_reference ?? "",
      `${item.source_type ?? ""}:${item.source_id ?? ""}`,
    ]),
  ]
}

function accountantMovementRows(
  report: AccountantPackReport,
  title = "Movimentos financeiros do periodo",
  items = report.movement_details,
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID movimento",
      "Direcao",
      "Tipo",
      "Data",
      "Valor",
      "Moeda",
      "Status",
      "Conciliacao",
      "Conta financeira",
      "Baixa",
      "Titulo",
      "Referencia titulo",
      "Participante",
      "Origem",
      "Descricao",
    ],
    ...items.map((item) => [
      item.id,
      directionLabel(item.direction),
      item.movement_type,
      dateCell(item.movement_date),
      moneyCell(item.amount),
      item.currency,
      statusLabel(item.status),
      statusLabel(item.reconciliation_status),
      item.financial_account_name ?? "",
      item.settlement_id ?? "",
      item.financial_title_id ?? "",
      item.title_reference ?? "",
      item.participant_name ?? "",
      `${item.source_type ?? ""}:${item.source_id ?? ""}`,
      item.description ?? "",
    ]),
  ]
}

function accountantStatementLineRows(
  report: AccountantPackReport,
  title = "Extratos bancarios pendentes do periodo",
  items = report.statement_line_details,
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID linha",
      "Conta financeira",
      "Importacao",
      "ID externo",
      "Data linha",
      "Data postagem",
      "Direcao",
      "Valor",
      "Status",
      "Confianca match",
      "Valor conciliado",
      "Documento",
      "Contraparte",
      "Documento contraparte",
      "Referencia bancaria",
      "Descricao",
    ],
    ...items.map((item) => [
      item.id,
      item.financial_account_name ?? "",
      item.statement_import_id ?? "",
      item.external_id ?? "",
      dateCell(item.line_date),
      dateTimeCell(item.posted_at),
      directionLabel(item.direction),
      moneyCell(item.amount),
      statusLabel(item.status),
      item.match_confidence ?? "",
      moneyCell(item.matched_amount),
      item.document_number ?? "",
      item.counterparty_name ?? "",
      item.counterparty_document ?? "",
      item.bank_reference ?? "",
      item.description ?? "",
    ]),
  ]
}

function accountantSalesRowsFromItems(
  report: AccountantPackReport,
  title: string,
  items: AccountantPackReport["sales_details"],
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID venda",
      "Pedido",
      "Status",
      "Tipo",
      "Origem",
      "Natureza",
      "Fiscal",
      "Emissao",
      "Operacao",
      "Competencia",
      "Participante",
      "Documento participante",
      "Subtotal",
      "Desconto",
      "Frete",
      "Imposto",
      "Total comercial",
      "Total a receber",
      "Total fiscal",
    ],
    ...items.map((item) => [
      item.id,
      item.sale_number_text ?? "",
      statusLabel(item.status),
      item.sale_type,
      item.origin,
      item.operation_nature ?? "",
      statusLabel(item.fiscal_status),
      dateCell(item.issue_date),
      dateTimeCell(item.operation_date),
      dateCell(item.competency_date),
      item.participant_name ?? "",
      item.participant_document ?? "",
      moneyCell(item.subtotal_amount),
      moneyCell(item.discount_amount),
      moneyCell(item.freight_amount),
      moneyCell(item.tax_amount),
      moneyCell(item.total_amount),
      moneyCell(item.receivable_total_amount),
      moneyCell(item.invoice_total_amount),
    ]),
  ]
}

function accountantSalesRows(report: AccountantPackReport): ExportTable {
  return accountantSalesRowsFromItems(report, "Vendas realizadas no periodo", report.sales_details)
}

function accountantPurchasesRowsFromItems(
  report: AccountantPackReport,
  title: string,
  items: AccountantPackReport["purchase_details"],
): ExportTable {
  return [
    [title],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "ID compra",
      "Status",
      "Tipo",
      "Origem",
      "Fiscal",
      "Emissao",
      "Operacao",
      "Competencia",
      "Participante",
      "Documento participante",
      "Documento",
      "Numero",
      "Serie",
      "Chave acesso",
      "Subtotal",
      "Desconto",
      "Frete",
      "Imposto",
      "Total comercial",
      "Total a pagar",
      "Total fiscal",
    ],
    ...items.map((item) => [
      item.id,
      statusLabel(item.status),
      item.purchase_type,
      item.origin,
      statusLabel(item.fiscal_status),
      dateCell(item.issue_date),
      dateTimeCell(item.operation_date),
      dateCell(item.competency_date),
      item.participant_name ?? "",
      item.participant_document ?? "",
      item.document_type ?? "",
      item.document_number ?? "",
      item.document_series ?? "",
      item.access_key ?? "",
      moneyCell(item.subtotal_amount),
      moneyCell(item.discount_amount),
      moneyCell(item.freight_amount),
      moneyCell(item.tax_amount),
      moneyCell(item.total_amount),
      moneyCell(item.payable_total_amount),
      moneyCell(item.invoice_total_amount),
    ]),
  ]
}

function accountantPurchasesRows(report: AccountantPackReport): ExportTable {
  return accountantPurchasesRowsFromItems(report, "Compras confirmadas no periodo", report.purchase_details)
}

function accountantFiscalRows(report: AccountantPackReport): ExportTable {
  const fiscal = report.fiscal_pending_details
  return [
    ["Pendencias e documentos fiscais do periodo"],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    [],
    [
      "Grupo",
      "Referencia",
      "Status operacional",
      "Status fiscal/documento",
      "Participante",
      "Data operacional",
      "Data emissao/autorizacao",
      "Vencimento",
      "Valor total",
      "Valor aberto",
      "Pedido",
      "Documento",
      "Serie",
      "Chave de acesso",
      "Motivo",
      "ID tecnico",
    ],
    ...fiscal.sales_documents.map((item) => [
      "Venda pendente",
      item.sale_number_text ?? item.sale_id,
      statusLabel(item.status),
      statusLabel(item.fiscal_status),
      item.participant_name ?? "",
      dateCell(item.operation_date),
      dateCell(item.issue_date),
      "",
      moneyCell(item.total_amount),
      "",
      item.sale_number_text ?? item.sale_id,
      "",
      "",
      "",
      fiscalSaleReason(item),
      item.sale_id,
    ]),
    ...fiscal.purchase_documents.map((item) => [
      "Compra pendente",
      item.document_number ?? item.purchase_id,
      statusLabel(item.status),
      statusLabel(item.fiscal_status),
      item.participant_name ?? "",
      dateCell(item.operation_date),
      dateCell(item.issue_date),
      "",
      moneyCell(item.total_amount),
      "",
      "",
      item.document_number ?? "",
      item.document_series ?? "",
      item.access_key ?? "",
      fiscalPurchaseReason(item),
      item.purchase_id,
    ]),
    ...fiscal.title_documents.map((item) => [
      "Titulo com pendencia fiscal",
      item.document_reference ?? item.sale_number_text ?? item.id,
      statusLabel(item.status),
      statusLabel(item.fiscal_status),
      item.participant_name ?? "",
      "",
      dateCell(item.issue_date),
      dateCell(item.due_date),
      moneyCell(item.net_amount),
      moneyCell(item.open_amount),
      item.sale_number_text ?? item.sale_id ?? "",
      item.document_reference ?? "",
      "",
      "",
      `Parcela ${item.installment_number}/${item.installment_total}`,
      item.id,
    ]),
    ...fiscal.fiscal_documents.map((item) => [
      "Documento fiscal registrado",
      item.reference,
      statusLabel(item.status),
      item.focus_status ?? statusLabel(item.status),
      item.participant_name ?? "",
      dateTimeCell(item.created_at),
      dateTimeCell(item.issued_at ?? item.authorized_at),
      "",
      moneyCell(item.sale_total_amount),
      "",
      item.sale_number_text ?? item.sale_id,
      item.number ?? "",
      item.serie ?? "",
      item.access_key ?? "",
      fiscalDocumentReason(item),
      item.id,
    ]),
  ]
}

function accountantExportBlockLabel(block: AccountantExportBlock): string {
  const labels: Record<AccountantExportBlock, string> = {
    receivable_open: "A receber em aberto",
    receivable_overdue: "A receber vencido",
    payable_open: "A pagar em aberto",
    payable_overdue: "A pagar vencido",
    cash_flow_projected: "Fluxo previsto",
    cash_flow_realized: "Fluxo realizado",
    reconciliation_pendencies: "Conciliacao pendente",
    fiscal_pendencies: "Pendencias fiscais",
    settlements_without_movement: "Baixas sem movimento",
    settlement_cash_difference: "Diferenca baixa x caixa",
    ignored_quotes: "Orcamentos ignorados",
    ignored_drafts: "Rascunhos ignorados",
  }
  return labels[block]
}

function accountantExportBlockBaseName(block: AccountantExportBlock): string {
  const names: Record<AccountantExportBlock, string> = {
    receivable_open: "a_receber_aberto",
    receivable_overdue: "a_receber_vencido",
    payable_open: "a_pagar_aberto",
    payable_overdue: "a_pagar_vencido",
    cash_flow_projected: "fluxo_previsto",
    cash_flow_realized: "fluxo_realizado",
    reconciliation_pendencies: "conciliacao_pendente",
    fiscal_pendencies: "pendencias_fiscais",
    settlements_without_movement: "baixas_sem_movimento",
    settlement_cash_difference: "diferenca_baixa_caixa",
    ignored_quotes: "orcamentos_ignorados",
    ignored_drafts: "rascunhos_ignorados",
  }
  return names[block]
}

function accountantBlockSummaryRows(report: AccountantPackReport, block: AccountantExportBlock): ExportTable {
  const indicators = report.indicators
  const consistency = report.consistency_checks
  const ignored = report.operational_ignored
  const fiscal = indicators.fiscal_document_pendencies
  const base: ExportTable = [
    ["Campo", "Valor"],
    ["Indicador", accountantExportBlockLabel(block)],
    ["Empresa", report.company_display_name],
    ["Periodo inicial", dateCell(report.period.start_date)],
    ["Periodo final", dateCell(report.period.end_date)],
    ["Data de referencia", dateCell(report.filters_used.reference_date)],
    ["Snapshot versao", report.snapshot.version],
    ["Snapshot gerado em", dateTimeCell(report.snapshot.generated_at)],
    [],
  ]

  const rowsByBlock: Record<AccountantExportBlock, ExportTable> = {
    receivable_open: [
      ["Quantidade", integerCell(indicators.accounts_receivable_open.count)],
      ["Valor em aberto", moneyCell(indicators.accounts_receivable_open.amount)],
      ["Escopo", indicators.accounts_receivable_open.scope ?? "current_position"],
    ],
    receivable_overdue: [
      ["Quantidade", integerCell(indicators.accounts_receivable_overdue.count)],
      ["Valor vencido", moneyCell(indicators.accounts_receivable_overdue.amount)],
      ["Escopo", indicators.accounts_receivable_overdue.scope ?? "current_position"],
    ],
    payable_open: [
      ["Quantidade", integerCell(indicators.accounts_payable_open.count)],
      ["Valor em aberto", moneyCell(indicators.accounts_payable_open.amount)],
      ["Escopo", indicators.accounts_payable_open.scope ?? "current_position"],
    ],
    payable_overdue: [
      ["Quantidade", integerCell(indicators.accounts_payable_overdue.count)],
      ["Valor vencido", moneyCell(indicators.accounts_payable_overdue.amount)],
      ["Escopo", indicators.accounts_payable_overdue.scope ?? "current_position"],
    ],
    cash_flow_projected: [
      ["Entrada prevista", moneyCell(indicators.cash_flow_projected.inflow_amount)],
      ["Saida prevista", moneyCell(indicators.cash_flow_projected.outflow_amount)],
      ["Liquido previsto", moneyCell(indicators.cash_flow_projected.net_amount)],
      ["Escopo", indicators.cash_flow_projected.scope ?? "period_due_date"],
    ],
    cash_flow_realized: [
      ["Entrada realizada", moneyCell(indicators.cash_flow_realized.inflow_amount)],
      ["Saida realizada", moneyCell(indicators.cash_flow_realized.outflow_amount)],
      ["Liquido realizado", moneyCell(indicators.cash_flow_realized.net_amount)],
      ["Escopo", indicators.cash_flow_realized.scope ?? "period_settlement_date"],
    ],
    reconciliation_pendencies: [
      ["Movimentos pendentes/divergentes", integerCell(indicators.reconciliation_pendencies.unreconciled_movements)],
      ["Extratos pendentes/divergentes", integerCell(indicators.reconciliation_pendencies.unmatched_statement_lines)],
    ],
    fiscal_pendencies: [
      ["Vendas com pendencia fiscal", integerCell(fiscal.pending_sales_documents)],
      ["Compras com pendencia fiscal", integerCell(fiscal.pending_purchase_documents)],
      ["Titulos com pendencia fiscal", integerCell(fiscal.pending_fiscal_titles)],
      ["Documentos fiscais com erro", integerCell(fiscal.fiscal_documents_error ?? 0)],
      ["Valor aberto com pendencia fiscal", moneyCell(fiscal.pending_fiscal_open_amount)],
    ],
    settlements_without_movement: [
      ["Baixas sem movimento", integerCell(consistency.settlements_without_movement_count)],
      ["Valor sem movimento", moneyCell(consistency.settlements_without_movement_amount)],
    ],
    settlement_cash_difference: [
      ["Baixas ativas", integerCell(consistency.active_settlements)],
      ["Valor informado nas baixas", moneyCell(consistency.settlement_movement_amount)],
      ["Valor postado no caixa", moneyCell(consistency.posted_movement_amount)],
      ["Diferenca", moneyCell(consistency.difference_amount)],
      ["Baixas com multiplos movimentos", integerCell(consistency.settlements_with_multiple_movements)],
    ],
    ignored_quotes: [
      ["Orcamentos ignorados", integerCell(ignored.sale_quotes_ignored_count)],
      ["Valor fora de venda realizada", moneyCell(ignored.sale_quotes_ignored_amount)],
    ],
    ignored_drafts: [
      ["Rascunhos ignorados", integerCell(ignored.purchase_drafts_ignored_count)],
      ["Valor fora de compra confirmada", moneyCell(ignored.purchase_drafts_ignored_amount)],
    ],
  }

  return [...base, ...rowsByBlock[block]]
}

function accountantWorkbookSheets(report: AccountantPackReport): ExportSheet[] {
  return [
    { name: "Resumo", rows: accountantRows(report) },
    { name: "Titulos abertos", rows: accountantTitleDetailRows(report, "Titulos em aberto - posicao atual", report.open_title_details) },
    { name: "Titulos periodo", rows: accountantTitleDetailRows(report, "Titulos com vencimento no periodo", report.period_title_details) },
    { name: "Baixas", rows: accountantSettlementRows(report) },
    { name: "Movimentos", rows: accountantMovementRows(report) },
    { name: "Extratos pendentes", rows: accountantStatementLineRows(report) },
    { name: "Vendas", rows: accountantSalesRows(report) },
    { name: "Compras", rows: accountantPurchasesRows(report) },
    { name: "Orcamentos ignorados", rows: accountantSalesRowsFromItems(report, "Orcamentos ignorados no periodo", report.ignored_sale_details) },
    { name: "Rascunhos ignorados", rows: accountantPurchasesRowsFromItems(report, "Rascunhos ignorados no periodo", report.ignored_purchase_details) },
    { name: "Fiscal", rows: accountantFiscalRows(report) },
  ]
}

function accountantBlockWorkbookSheets(report: AccountantPackReport, block: AccountantExportBlock): ExportSheet[] {
  const summary = { name: "Resumo", rows: accountantBlockSummaryRows(report, block) }
  switch (block) {
    case "receivable_open":
      return [
        summary,
        { name: "Titulos", rows: accountantTitleDetailRows(report, "A receber em aberto - posicao atual", accountantTitleRowsByDirection(report, "receivable")) },
      ]
    case "receivable_overdue":
      return [
        summary,
        { name: "Titulos", rows: accountantTitleDetailRows(report, "A receber vencido - posicao atual", accountantTitleRowsByDirection(report, "receivable", true)) },
      ]
    case "payable_open":
      return [
        summary,
        { name: "Titulos", rows: accountantTitleDetailRows(report, "A pagar em aberto - posicao atual", accountantTitleRowsByDirection(report, "payable")) },
      ]
    case "payable_overdue":
      return [
        summary,
        { name: "Titulos", rows: accountantTitleDetailRows(report, "A pagar vencido - posicao atual", accountantTitleRowsByDirection(report, "payable", true)) },
      ]
    case "cash_flow_projected":
      return [
        summary,
        { name: "Titulos por vencimento", rows: accountantTitleDetailRows(report, "Fluxo previsto - titulos ativos por vencimento", accountantProjectedTitleRows(report)) },
      ]
    case "cash_flow_realized":
      return [
        summary,
        { name: "Baixas", rows: accountantSettlementRows(report, "Fluxo realizado - baixas do periodo") },
      ]
    case "reconciliation_pendencies":
      return [
        summary,
        { name: "Movimentos pendentes", rows: accountantMovementRows(report, "Movimentos internos pendentes/divergentes", accountantPendingMovementRows(report)) },
        { name: "Extratos pendentes", rows: accountantStatementLineRows(report, "Extratos bancarios pendentes/divergentes", accountantPendingStatementRows(report)) },
      ]
    case "fiscal_pendencies":
      return [summary, { name: "Fiscal", rows: accountantFiscalRows(report) }]
    case "settlements_without_movement":
      return [
        summary,
        {
          name: "Baixas sem movimento",
          rows: accountantSettlementRows(
            report,
            "Baixas ativas sem movimento financeiro vinculado",
            report.settlement_details.filter((item) => item.linked_movement_count <= 0),
          ),
        },
      ]
    case "settlement_cash_difference":
      return [
        summary,
        { name: "Baixas", rows: accountantSettlementRows(report, "Baixas consideradas na consistencia") },
        { name: "Movimentos", rows: accountantMovementRows(report, "Movimentos financeiros vinculados/periodo") },
      ]
    case "ignored_quotes":
      return [
        summary,
        { name: "Orcamentos", rows: accountantSalesRowsFromItems(report, "Orcamentos ignorados no periodo", report.ignored_sale_details) },
      ]
    case "ignored_drafts":
      return [
        summary,
        { name: "Rascunhos", rows: accountantPurchasesRowsFromItems(report, "Rascunhos de compra ignorados no periodo", report.ignored_purchase_details) },
      ]
  }
}

const HEALTH_EXPORT_COLUMN_LABELS: Record<string, string> = {
  id: "ID",
  name: "Nome",
  trade_name: "Nome fantasia",
  participant_type: "Tipo de participante",
  person_type: "Tipo de pessoa",
  document: "Documento",
  email: "E-mail",
  phone: "Telefone",
  status: "Status",
  origin: "Origem",
  direction: "Direção",
  title_reference: "Referência do título",
  participant_name: "Participante",
  collection_status: "Status de cobrança",
  fiscal_status: "Status fiscal",
  issue_date: "Emissão",
  competency_date: "Competência",
  due_date: "Vencimento",
  gross_amount: "Valor bruto",
  net_amount: "Valor líquido",
  paid_amount: "Valor pago",
  open_amount: "Valor em aberto",
  source_type: "Tipo de origem",
  source_id: "ID da origem",
  sale_id: "Venda",
  document_reference: "Documento de referência",
  installment_number: "Parcela",
  installment_total: "Total de parcelas",
  created_at: "Criado em",
  updated_at: "Atualizado em",
  movement_type: "Tipo de movimento",
  movement_date: "Data do movimento",
  amount: "Valor",
  reconciliation_status: "Status de conciliação",
  financial_account_name: "Conta financeira",
  financial_title_id: "Título financeiro",
  settlement_id: "Baixa",
  description: "Descrição",
  sale_number_text: "Número do pedido",
  sale_type: "Tipo de venda",
  operation_nature: "Natureza da operação",
  operation_date: "Data da operação",
  subtotal_amount: "Subtotal",
  discount_amount: "Desconto",
  freight_amount: "Frete",
  tax_amount: "Tributos",
  total_amount: "Total",
  receivable_total_amount: "Total a receber",
  payable_total_amount: "Total a pagar",
  invoice_total_amount: "Total fiscal",
  closed_at: "Fechado em",
  paid_at: "Pago em",
  purchase_type: "Tipo de compra",
  document_type: "Tipo de documento",
  document_number: "Número do documento",
  document_series: "Série",
  confirmed_at: "Confirmado em",
  match_type: "Tipo de match",
  matched_amount: "Valor conciliado",
  line_amount: "Valor no extrato",
  movement_amount: "Valor do movimento",
  difference_amount: "Diferença",
  tolerance_amount: "Tolerância",
  statement_line_id: "Linha do extrato",
  financial_movement_id: "Movimento financeiro",
  confirmation_reason: "Motivo da confirmação",
  statement_date: "Data do extrato",
  counterparty_name: "Contraparte",
  counterparty_document: "Documento da contraparte",
  bank_reference: "Referência bancária",
  external_id: "ID externo",
  indicator: "Indicador",
  company_id: "Empresa ID",
  company_display_name: "Empresa",
  period_start_date: "Período inicial",
  period_end_date: "Período final",
  reference_date: "Data de referência",
}

const HEALTH_EXPORT_MONEY_COLUMNS = new Set([
  "gross_amount",
  "discount_amount",
  "interest_amount",
  "penalty_amount",
  "fee_amount",
  "net_amount",
  "paid_amount",
  "open_amount",
  "subtotal_amount",
  "freight_amount",
  "tax_amount",
  "total_amount",
  "receivable_total_amount",
  "payable_total_amount",
  "invoice_total_amount",
  "amount",
  "matched_amount",
  "line_amount",
  "movement_amount",
  "difference_amount",
  "tolerance_amount",
])

const HEALTH_EXPORT_INTEGER_COLUMNS = new Set(["installment_number", "installment_total"])
const HEALTH_EXPORT_DATE_COLUMNS = new Set([
  "issue_date",
  "competency_date",
  "due_date",
  "movement_date",
  "statement_date",
])
const HEALTH_EXPORT_DATETIME_COLUMNS = new Set([
  "created_at",
  "updated_at",
  "operation_date",
  "closed_at",
  "paid_at",
  "confirmed_at",
])

function healthExportCell(column: string, value: HealthIndicatorCell): ExportCell {
  if (value === null || value === undefined) return ""
  if (HEALTH_EXPORT_MONEY_COLUMNS.has(column)) {
    return typeof value === "boolean" ? String(value) : moneyCell(value)
  }
  if (HEALTH_EXPORT_INTEGER_COLUMNS.has(column)) {
    return typeof value === "boolean" ? String(value) : integerCell(value)
  }
  if (HEALTH_EXPORT_DATE_COLUMNS.has(column)) {
    return typeof value === "boolean" ? String(value) : dateCell(String(value))
  }
  if (HEALTH_EXPORT_DATETIME_COLUMNS.has(column)) {
    return typeof value === "boolean" ? String(value) : dateTimeCell(String(value))
  }
  if (column === "direction") return directionLabel(String(value))
  if (column.endsWith("status") || column === "status") return statusLabel(String(value))
  return value
}

function healthIndicatorRows(report: HealthIndicatorDetailsReport): ExportTable {
  const contextColumns = ["indicator", "company_id", "company_display_name", "period_start_date", "period_end_date", "reference_date"]
  return [
    [...contextColumns, ...report.columns].map((column) => HEALTH_EXPORT_COLUMN_LABELS[column] ?? column),
    ...report.rows.map((row) => [
      report.label,
      report.company_id,
      report.company_display_name,
      dateCell(report.period.start_date),
      dateCell(report.period.end_date),
      dateCell(report.reference_date),
      ...report.columns.map((column) => healthExportCell(column, row[column] ?? null)),
    ]),
  ]
}

function cellText(value: HealthIndicatorCell | undefined): string {
  if (value === null || value === undefined) return ""
  return String(value)
}

function backlogReportDateCell(report: HealthIndicatorDetailsReport, row: Record<string, HealthIndicatorCell>): ExportCell {
  if (report.indicator === "overdue_titles" || report.indicator === "titles_without_clear_origin") {
    return dateCell(cellText(row.due_date))
  }
  if (report.indicator === "unreconciled_movements") return dateCell(cellText(row.movement_date))
  return dateCell(cellText(row.statement_date))
}

function backlogReportAmountCell(report: HealthIndicatorDetailsReport, row: Record<string, HealthIndicatorCell>): ExportCell {
  if (report.indicator === "overdue_titles" || report.indicator === "titles_without_clear_origin") {
    return moneyCell(cellText(row.open_amount) || "0.00")
  }
  return moneyCell(cellText(row.amount) || "0.00")
}

function backlogReportReference(report: HealthIndicatorDetailsReport, row: Record<string, HealthIndicatorCell>): string {
  if (report.indicator === "overdue_titles" || report.indicator === "titles_without_clear_origin") {
    return cellText(row.title_reference) || cellText(row.document_reference) || cellText(row.id)
  }
  return cellText(row.description) || cellText(row.bank_reference) || cellText(row.external_id) || cellText(row.id)
}

function backlogReportOwner(row: Record<string, HealthIndicatorCell>): string {
  return cellText(row.participant_name) || cellText(row.financial_account_name) || cellText(row.counterparty_name)
}

function backlogReportStatus(report: HealthIndicatorDetailsReport, row: Record<string, HealthIndicatorCell>): string {
  if (report.indicator === "unreconciled_movements") return statusLabel(cellText(row.reconciliation_status))
  return statusLabel(cellText(row.status))
}

function backlogReportDetail(report: HealthIndicatorDetailsReport, row: Record<string, HealthIndicatorCell>): string {
  if (report.indicator === "overdue_titles" || report.indicator === "titles_without_clear_origin") {
    return [
      `Líquido: ${formatMoney(cellText(row.net_amount))}`,
      `Pago: ${formatMoney(cellText(row.paid_amount))}`,
      `Documento: ${cellText(row.document_reference) || "não informado"}`,
      `Origem: ${[cellText(row.source_type), cellText(row.source_id)].filter(Boolean).join(" / ") || "não informada"}`,
    ].join("; ")
  }
  if (report.indicator === "unreconciled_movements") {
    return [
      `Conta: ${cellText(row.financial_account_name) || "não informada"}`,
      `Título: ${cellText(row.financial_title_id) || "não vinculado"}`,
      `Baixa: ${cellText(row.settlement_id) || "não vinculada"}`,
    ].join("; ")
  }
  return [
    `Conta: ${cellText(row.financial_account_name) || "não informada"}`,
    `Contraparte: ${cellText(row.counterparty_name) || "não informada"}`,
    `Referência bancária: ${cellText(row.bank_reference) || "não informada"}`,
  ].join("; ")
}

function backlogConsolidatedRows(reports: HealthIndicatorDetailsReport[]): ExportTable {
  return [
    [
      "Categoria",
      "Empresa",
      "Período inicial",
      "Período final",
      "Referência",
      "Direção",
      "Participante / Conta",
      "Status",
      "Data",
      "Valor em pendência",
      "Detalhe",
      "ID técnico",
    ],
    ...reports.flatMap((report) =>
      report.rows.map((row) => [
        report.label,
        report.company_display_name,
        dateCell(report.period.start_date),
        dateCell(report.period.end_date),
        backlogReportReference(report, row),
        directionLabel(cellText(row.direction)),
        backlogReportOwner(row),
        backlogReportStatus(report, row),
        backlogReportDateCell(report, row),
        backlogReportAmountCell(report, row),
        backlogReportDetail(report, row),
        cellText(row.id),
      ]),
    ),
  ]
}

export function ManagementReportsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview")
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("month")
  const { companyId, activeCompanyName, isCompanyResolved, isCompanyLoading, companyError } = useActiveCompany()
  const [startDate, setStartDate] = useState(monthStart())
  const [endDate, setEndDate] = useState(today())
  const [titleDirection, setTitleDirection] = useState("")
  const [titleStatus, setTitleStatus] = useState("")
  const [titleSearch, setTitleSearch] = useState("")
  const [titleOffset, setTitleOffset] = useState(0)
  const [limit, setLimit] = useState(20)
  const [rules, setRules] = useState<ManagementReportRules | null>(null)
  const [availableCompanies, setAvailableCompanies] = useState<AvailableCompaniesReport | null>(null)
  const [companyContext, setCompanyContext] = useState<CompanyContextReport | null>(null)
  const [cycle, setCycle] = useState<FinancialCycleReport | null>(null)
  const [health, setHealth] = useState<MvpHealthReport | null>(null)
  const [backlog, setBacklog] = useState<OperationalBacklogReport | null>(null)
  const [titles, setTitles] = useState<TitleReferencesReport | null>(null)
  const [fiscalPrep, setFiscalPrep] = useState<PreparatoryFiscalDocumentsReport | null>(null)
  const [closing, setClosing] = useState<FinancialCloseMvpReport | null>(null)
  const [accountantPack, setAccountantPack] = useState<AccountantPackReport | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [exportingHealthIndicator, setExportingHealthIndicator] = useState<HealthIndicatorKey | null>(null)
  const [exportingBacklog, setExportingBacklog] = useState<BacklogExportState>(null)
  const [isExportingTitles, setIsExportingTitles] = useState(false)
  const [exportingFiscal, setExportingFiscal] = useState<FiscalExportState>(null)
  const [isExportingClosing, setIsExportingClosing] = useState(false)
  const [isExportingAccountant, setIsExportingAccountant] = useState(false)
  const [exportingAccountantBlock, setExportingAccountantBlock] = useState<AccountantExportBlock | null>(null)

  // The company hook initializes isCompanyLoading = false, then its own useEffect
  // sets it to true when it starts fetching. Both effects flush after the same
  // render, so on mount ManagementReportsPage's effect sees isCompanyLoading = false
  // before the hook has started. We use this ref to skip the first fire.
  const seenLoadingRef = useRef(false)

  const periodFilters = useMemo(() => ({ start_date: startDate, end_date: endDate }), [startDate, endDate])

  async function loadReports() {
    setIsLoading(true)
    setNotice(null)

    try {
      const [rulesResponse, availableCompaniesResponse] = await Promise.all([
        getManagementReportRules(),
        getAvailableReportCompanies(10),
      ])

      setRules(rulesResponse.data)
      setAvailableCompanies(availableCompaniesResponse.data)

      if (!companyId || !isCompanyResolved) {
        setCompanyContext(null)
        setCycle(null)
        setHealth(null)
        setBacklog(null)
        setTitles(null)
        setFiscalPrep(null)
        setClosing(null)
        setAccountantPack(null)
        setNotice({
          type: "error",
          message: "Nenhuma empresa ativa encontrada. Selecione uma empresa para carregar os relatórios.",
        })
        return
      }

      const [contextResponse, cycleResponse, healthResponse, backlogResponse, titlesResponse, fiscalPrepResponse, closingResponse, accountantPackResponse] = await Promise.all([
        getManagementCompanyContext(companyId),
        getFinancialCycleReport(companyId, periodFilters),
        getMvpHealthReport(companyId, periodFilters),
        getOperationalBacklogReport(companyId, { ...periodFilters, limit }),
        getTitleReferencesReport(companyId, {
          direction: titleDirection || undefined,
          status: titleStatus || undefined,
          search: titleSearch || undefined,
          due_from: startDate,
          due_to: endDate,
          limit,
          offset: titleOffset,
        }),
        getPreparatoryFiscalDocumentsReport(companyId, { ...periodFilters, limit }),
        getFinancialCloseMvpReport(companyId, periodFilters),
        getAccountantPackReport(companyId, periodFilters),
      ])

      setCompanyContext(contextResponse.data)
      setCycle(cycleResponse.data)
      setHealth(healthResponse.data)
      setBacklog(backlogResponse.data)
      setTitles(titlesResponse.data)
      setFiscalPrep(fiscalPrepResponse.data)
      setClosing(closingResponse.data)
      setAccountantPack(accountantPackResponse.data)
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Erro ao carregar relatórios gerenciais." })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isCompanyLoading) {
      seenLoadingRef.current = true // mark: hook started its first fetch
      return
    }
    if (!seenLoadingRef.current) return // hook hasn't started loading yet — skip
    void loadReports()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, isCompanyResolved, isCompanyLoading, startDate, endDate, titleDirection, titleStatus, limit, titleOffset])

  const pendencyTotal = useMemo(() => {
    if (!backlog) return 0
    return backlog.totals?.total_pendencies ?? (
      backlog.overdue_titles.length +
      backlog.titles_without_clear_origin.length +
      backlog.unreconciled_movements.length +
      backlog.unmatched_bank_statement_lines.length
    )
  }, [backlog])

  // Derived financial hero numbers from cycle
  const openReceivable = useMemo(() => {
    if (!cycle) return null
    const row = cycle.titles_by_direction.find((r) => r.direction === "receivable")
    return row ? { amount: row.active_open_amount ?? row.open_amount ?? "0", count: row.active_titles ?? row.total_titles ?? 0 } : null
  }, [cycle])

  const openPayable = useMemo(() => {
    if (!cycle) return null
    const row = cycle.titles_by_direction.find((r) => r.direction === "payable")
    return row ? { amount: row.active_open_amount ?? row.open_amount ?? "0", count: row.active_titles ?? row.total_titles ?? 0 } : null
  }, [cycle])

  function handlePresetChange(preset: PeriodPreset) {
    setPeriodPreset(preset)
    setTitleOffset(0)
    if (preset === "custom") return
    const dates = getPeriodDates(preset)
    if (dates) {
      setStartDate(dates.start)
      setEndDate(dates.end)
    }
  }

  function handleTitleSearchSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (titleOffset !== 0) {
      setTitleOffset(0)
      return
    }
    void loadReports()
  }

  async function handleTitleExport(format: "csv" | "xlsx") {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar os títulos." })
      return
    }

    setIsExportingTitles(true)
    setNotice(null)
    try {
      const response = await getTitleReferencesReport(companyId, {
        direction: titleDirection || undefined,
        status: titleStatus || undefined,
        search: titleSearch || undefined,
        due_from: startDate,
        due_to: endDate,
        export_all: true,
      })
      const report = response.data
      exportRows(titleRows(report), "titulos", format)
      setNotice({
        type: "success",
        message: `Títulos financeiros: ${report.items.length} de ${report.total} registro(s) exportado(s).`,
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar títulos financeiros.",
      })
    } finally {
      setIsExportingTitles(false)
    }
  }

  async function handleHealthIndicatorExport(indicator: HealthIndicatorKey) {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar o indicador." })
      return
    }

    setExportingHealthIndicator(indicator)
    setNotice(null)
    try {
      const response = await getHealthIndicatorDetailsReport(companyId, indicator, periodFilters)
      const report = response.data
      const rows = healthIndicatorRows(report)
      const fileName = buildExportFileName("kovir_saude", report.indicator, "xlsx")
      exportXlsxFile(rows, report.label, fileName)
      setNotice({
        type: "success",
        message: `${report.label}: ${report.total} registro(s) exportado(s) em XLSX.`,
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar indicador da Saúde do Kovir.",
      })
    } finally {
      setExportingHealthIndicator(null)
    }
  }

  async function handleBacklogExport(indicator: BacklogExportKey | "all") {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar as pendências." })
      return
    }

    setExportingBacklog(indicator)
    setNotice(null)
    try {
      if (indicator === "all") {
        const responses = await Promise.all(
          BACKLOG_EXPORT_KEYS.map((key) => getHealthIndicatorDetailsReport(companyId, key, periodFilters)),
        )
        const reports = responses.map((response) => response.data)
        const rows = backlogConsolidatedRows(reports)
        const totalRows = reports.reduce((sum, report) => sum + report.total, 0)
        const fileName = buildExportFileName("kovir_pendencias", "consolidado", "xlsx")
        exportXlsxFile(rows, "Pendencias", fileName)
        setNotice({ type: "success", message: `Pendências consolidadas: ${totalRows} registro(s) exportado(s) em XLSX.` })
        return
      }

      const response = await getHealthIndicatorDetailsReport(companyId, indicator, periodFilters)
      const report = response.data
      const rows = healthIndicatorRows(report)
      const fileName = buildExportFileName("kovir_pendencias", report.indicator, "xlsx")
      exportXlsxFile(rows, report.label, fileName)
      setNotice({ type: "success", message: `${report.label}: ${report.total} registro(s) exportado(s) em XLSX.` })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar pendências operacionais.",
      })
    } finally {
      setExportingBacklog(null)
    }
  }

  async function handleFiscalExport(group: FiscalExportKey) {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar os dados fiscais." })
      return
    }

    setExportingFiscal(group)
    setNotice(null)
    try {
      const response = await getPreparatoryFiscalDocumentsReport(companyId, {
        ...periodFilters,
        export_all: true,
      })
      const report = response.data
      const rows = fiscalRows(report, group)
      const groupName = group === "all" ? "consolidado" : group
      const fileName = buildExportFileName("kovir_docs_fiscais", groupName, "xlsx")
      exportXlsxFile(rows, "Docs fiscais", fileName)
      setNotice({
        type: "success",
        message: `Docs fiscais: ${Math.max(rows.length - 1, 0)} registro(s) exportado(s) em XLSX.`,
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar documentos fiscais.",
      })
    } finally {
      setExportingFiscal(null)
    }
  }

  async function handleClosingExport() {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar o fechamento." })
      return
    }

    setIsExportingClosing(true)
    setNotice(null)
    try {
      const response = await getFinancialCloseMvpReport(companyId, periodFilters)
      const report = response.data
      const rows = closingRows(report)
      const fileName = buildExportFileName("kovir_fechamento", "prontidao", "xlsx")
      exportXlsxFile(rows, "Fechamento", fileName)
      setNotice({
        type: "success",
        message: "Prontidao de fechamento exportada em XLSX.",
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar fechamento.",
      })
    } finally {
      setIsExportingClosing(false)
    }
  }

  async function handleAccountantExport(format: "csv" | "xlsx") {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar o relatorio do contador." })
      return
    }

    setIsExportingAccountant(true)
    setNotice(null)
    try {
      const response = await getAccountantPackReport(companyId, {
        ...periodFilters,
        include_details: format === "xlsx",
        export_all: format === "xlsx",
      })
      const report = response.data
      const fileName = buildExportFileName("kovir_contador", "pacote", format)
      if (format === "csv") {
        exportCsvFile(accountantRows(report), fileName)
      } else {
        exportXlsxWorkbook(accountantWorkbookSheets(report), fileName)
      }
      setAccountantPack(report)
      setNotice({
        type: "success",
        message: format === "xlsx"
          ? "Pacote do contador exportado em XLSX com abas de resumo e evidencias."
          : "Resumo do contador exportado em CSV.",
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar relatorio do contador.",
      })
    } finally {
      setIsExportingAccountant(false)
    }
  }

  async function handleAccountantBlockExport(block: AccountantExportBlock) {
    if (!companyId || !isCompanyResolved) {
      setNotice({ type: "error", message: "Selecione uma empresa ativa para exportar o relatorio do contador." })
      return
    }

    setExportingAccountantBlock(block)
    setNotice(null)
    try {
      const response = await getAccountantPackReport(companyId, {
        ...periodFilters,
        include_details: true,
        export_all: true,
      })
      const report = response.data
      const fileName = buildExportFileName("kovir_contador", accountantExportBlockBaseName(block), "xlsx")
      exportXlsxWorkbook(accountantBlockWorkbookSheets(report, block), fileName)
      setAccountantPack(report)
      setNotice({
        type: "success",
        message: `${accountantExportBlockLabel(block)} exportado em XLSX com evidencias.`,
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar bloco do contador.",
      })
    } finally {
      setExportingAccountantBlock(null)
    }
  }

  const isPageLoading = isLoading || isCompanyLoading

  const tabs: Array<{ key: TabKey; label: string; icon: ReactNode; badge?: number }> = [
    { key: "overview", label: "Saúde do Kovir", icon: <Gauge className="h-4 w-4" /> },
    { key: "cycle", label: "Ciclo financeiro", icon: <BarChart3 className="h-4 w-4" /> },
    { key: "backlog", label: "Pendências", icon: <AlertTriangle className="h-4 w-4" />, badge: pendencyTotal > 0 ? pendencyTotal : undefined },
    { key: "titles", label: "Títulos", icon: <WalletCards className="h-4 w-4" /> },
    { key: "fiscalPrep", label: "Docs fiscais", icon: <FileText className="h-4 w-4" /> },
    { key: "closing", label: "Fechamento", icon: <ClipboardList className="h-4 w-4" /> },
    { key: "accountant", label: "Contador", icon: <ListChecks className="h-4 w-4" /> },
    { key: "rules", label: "Regras", icon: <ShieldCheck className="h-4 w-4" /> },
  ]

  return (
    <div className="space-y-6">
      {/* ── HEADER ─────────────────────────────────────────────────────── */}
      <header className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="grid gap-0 xl:grid-cols-[1.55fr_0.45fr]">
          {/* Left: title + 4 vibrant KPI cards */}
          <div className="p-6 sm:p-8">
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <InfoPill icon={<BarChart3 className="h-4 w-4" />} label="Bloco 16 — Relatórios Gerenciais" />
              <InfoPill icon={<Table2 className="h-4 w-4" />} label="CSV / XLSX" />
              {isPageLoading && (
                <InfoPill icon={<Loader2 className="h-4 w-4 animate-spin" />} label="Carregando…" />
              )}
            </div>

            <h1 className="mt-2 max-w-4xl text-3xl font-black tracking-tight text-[var(--color-text)] sm:text-4xl">
              Saúde e relatórios do <span className="text-[var(--color-primary)]">Kovir</span>
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">
              Visão consolidada de títulos, movimentos, conciliação e pendências financeiras da empresa ativa. Nenhum dado é criado aqui — apenas lido.
            </p>

            {/* 4 vibrant KPI cards */}
            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <VibrantMetric
                label="Score Kovir"
                value={health ? String(health.score) : "—"}
                sub={health ? statusLabel(health.status) : isPageLoading ? "Carregando…" : "Aguardando"}
                icon={<Gauge className="h-5 w-5" />}
                accent={health ? scoreColor(health.score) : "#16a34a"}
                score={health?.score}
              />
              <VibrantMetric
                label="A receber aberto"
                value={openReceivable ? formatMoney(openReceivable.amount) : "—"}
                sub={openReceivable ? `${openReceivable.count} título(s) ativo(s)` : isPageLoading ? "Carregando…" : "—"}
                icon={<WalletCards className="h-5 w-5" />}
                accent="#2563eb"
              />
              <VibrantMetric
                label="A pagar aberto"
                value={openPayable ? formatMoney(openPayable.amount) : "—"}
                sub={openPayable ? `${openPayable.count} título(s) ativo(s)` : isPageLoading ? "Carregando…" : "—"}
                icon={<FileText className="h-5 w-5" />}
                accent="#7c3aed"
              />
              <VibrantMetric
                label="Pendências"
                value={isPageLoading && !backlog ? "…" : String(pendencyTotal)}
                sub={pendencyTotal === 0 ? (isPageLoading ? "Carregando…" : "Tudo em ordem ✓") : "itens críticos"}
                icon={<AlertTriangle className="h-5 w-5" />}
                accent={pendencyTotal > 0 ? "#d97706" : "#16a34a"}
              />
            </div>
          </div>

          {/* Right: period selector */}
          <aside className="border-t border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5 xl:border-l xl:border-t-0">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <CalendarDays className="h-5 w-5" />
              </span>
              <div>
                <p className="text-xs font-bold text-[var(--color-text-muted)]">Período analisado</p>
                <p className="text-sm font-black text-[var(--color-text)]">{formatDate(startDate)} – {formatDate(endDate)}</p>
              </div>
            </div>

            {/* Quick presets */}
            <div className="mb-4 grid grid-cols-2 gap-1.5 sm:grid-cols-3 xl:grid-cols-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => handlePresetChange(preset.key)}
                  className={`rounded-2xl border px-3 py-2 text-xs font-black transition ${
                    periodPreset === preset.key
                      ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                      : "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Custom date inputs — shown when "Personalizado" is active */}
            {periodPreset === "custom" && (
              <div className="mb-4 space-y-2">
                <label className="block space-y-1">
                  <span className="text-xs font-bold text-[var(--color-text-muted)]">Data inicial</span>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => {
                      setStartDate(e.target.value)
                      setTitleOffset(0)
                    }}
                    className="field-input text-sm font-semibold"
                  />
                </label>
                <label className="block space-y-1">
                  <span className="text-xs font-bold text-[var(--color-text-muted)]">Data final</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => {
                      setEndDate(e.target.value)
                      setTitleOffset(0)
                    }}
                    className="field-input text-sm font-semibold"
                  />
                </label>
              </div>
            )}

            <button
              type="button"
              onClick={() => void loadReports()}
              disabled={isPageLoading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm font-black text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)] disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${isPageLoading ? "animate-spin" : ""}`} />
              {isPageLoading ? "Carregando…" : "Recarregar"}
            </button>

            {/* Company info pill */}
            <div className="mt-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
              <p className="text-xs font-bold text-[var(--color-text-muted)]">Empresa ativa</p>
              <p className="mt-0.5 truncate text-sm font-black text-[var(--color-text)]">{companyContext?.display_name ?? activeCompanyName ?? "—"}</p>
              {companyContext?.cnpj && (
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{companyContext.cnpj}</p>
              )}
            </div>
          </aside>
        </div>
      </header>

      {/* ── NOTICE ─────────────────────────────────────────────────────── */}
      {(notice || companyError) ? (
        <NoticeBox type={notice?.type ?? "error"} message={notice?.message ?? companyError ?? ""} />
      ) : null}

      {/* ── SKELETON ───────────────────────────────────────────────────── */}
      {isPageLoading && !health && !cycle && (
        <div className="animate-pulse space-y-4">
          <div className="h-44 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)]" />
          <div className="grid gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)]" />
            ))}
          </div>
        </div>
      )}

      {/* ── TAB NAVIGATION ─────────────────────────────────────────────── */}
      <section className="flex flex-wrap gap-2 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2 shadow-xl shadow-[var(--color-card-shadow)]">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2.5 text-sm font-black transition ${
              activeTab === tab.key
                ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                : "border-[var(--color-border-soft)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.badge !== undefined && (
              <span className="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 text-[10px] font-black text-white">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </section>

      {/* ── TAB PANELS ─────────────────────────────────────────────────── */}
      {(!isPageLoading || health || cycle) ? (
        <>
          {activeTab === "overview" && (
            <OverviewPanel
              health={health}
              context={companyContext}
              availableCompanies={availableCompanies}
              exportingIndicator={exportingHealthIndicator}
              onIndicatorExport={(indicator) => void handleHealthIndicatorExport(indicator)}
            />
          )}
          {activeTab === "cycle" && (
            <CyclePanel cycle={cycle} onExport={(format) => exportRows(cycleRows(cycle), "ciclo_financeiro", format)} />
          )}
          {activeTab === "backlog" && (
            <BacklogPanel
              backlog={backlog}
              exporting={exportingBacklog}
              onExport={(indicator) => void handleBacklogExport(indicator)}
            />
          )}
          {activeTab === "titles" && (
            <TitlesPanel
              titles={titles}
              titleDirection={titleDirection}
              titleStatus={titleStatus}
              titleSearch={titleSearch}
              limit={limit}
              offset={titleOffset}
              periodStart={startDate}
              periodEnd={endDate}
              isExporting={isExportingTitles}
              onDirectionChange={(value) => {
                setTitleDirection(value)
                setTitleOffset(0)
              }}
              onStatusChange={(value) => {
                setTitleStatus(value)
                setTitleOffset(0)
              }}
              onSearchChange={setTitleSearch}
              onLimitChange={(value) => {
                setLimit(value)
                setTitleOffset(0)
              }}
              onPageChange={setTitleOffset}
              onSubmit={handleTitleSearchSubmit}
              onExport={(format) => void handleTitleExport(format)}
            />
          )}
          {activeTab === "fiscalPrep" && (
            <FiscalPreparatoryPanel
              report={fiscalPrep}
              onExport={handleFiscalExport}
              exportingGroup={exportingFiscal}
            />
          )}
          {activeTab === "closing" && (
            <FinancialClosingPanel
              report={closing}
              onExport={handleClosingExport}
              isExporting={isExportingClosing}
            />
          )}
          {activeTab === "accountant" && (
            <AccountantPanel
              report={accountantPack}
              onExport={(format) => void handleAccountantExport(format)}
              isExporting={isExportingAccountant}
              onBlockExport={(block) => void handleAccountantBlockExport(block)}
              exportingBlock={exportingAccountantBlock}
            />
          )}
          {activeTab === "rules" && <RulesPanel rules={rules} />}
        </>
      ) : null}
    </div>
  )
}

// ── SHARED COMPONENTS ────────────────────────────────────────────────────────

function InfoPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-1.5 text-xs font-bold text-[var(--color-text-muted)]">
      {icon}
      {label}
    </span>
  )
}

function VibrantMetric({
  label,
  value,
  sub,
  icon,
  accent,
  score,
}: {
  label: string
  value: string
  sub: string
  icon: ReactNode
  accent: string
  score?: number
}) {
  return (
    <div
      className="relative overflow-hidden rounded-3xl p-4 shadow-lg"
      style={{ background: accent }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-white/70">{label}</p>
          <p className="mt-1 text-xl font-black leading-tight tracking-tight text-white">{value}</p>
          <p className="mt-1 text-xs text-white/70">{sub}</p>
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white/20 text-white">
          {icon}
        </span>
      </div>
      {score !== undefined && (
        <div className="mt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/25">
            <div
              className="h-full rounded-full bg-white/80 transition-all duration-700"
              style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  helper,
  icon,
  tone = "primary",
  onExport,
  isExporting = false,
  isExportDisabled = false,
}: {
  label: string
  value: string
  helper: string
  icon: ReactNode
  tone?: "primary" | "success" | "warning" | "danger"
  onExport?: () => void
  isExporting?: boolean
  isExportDisabled?: boolean
}) {
  const toneClass = {
    primary: "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]",
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-600",
    danger: "border-red-500/30 bg-red-500/10 text-red-600",
  }[tone]

  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 shadow-lg shadow-[var(--color-card-shadow)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-bold text-[var(--color-text-muted)]">{label}</p>
          <p className="mt-2 truncate text-2xl font-black text-[var(--color-text)]">{value}</p>
          <p className="mt-1 truncate text-xs text-[var(--color-text-muted)]">{helper}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className={`flex h-11 w-11 items-center justify-center rounded-2xl border ${toneClass}`}>
            {icon}
          </span>
          {onExport ? (
            <button
              type="button"
              onClick={onExport}
              disabled={isExporting || isExportDisabled}
              aria-label={`Exportar ${label} em XLSX`}
              title={`Exportar ${label} em XLSX`}
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function NoticeBox({ type, message }: { type: "success" | "error"; message: string }) {
  const isError = type === "error"
  return (
    <div
      className={`flex items-start gap-3 rounded-3xl border p-4 text-sm font-semibold ${
        isError
          ? "border-red-500/30 bg-red-500/10 text-red-700"
          : "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
      }`}
    >
      {isError ? (
        <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
      ) : (
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
      )}
      <span>{message}</span>
    </div>
  )
}

function StatusBadge({ status }: { status?: string | null }) {
  const tone = statusTone(status)
  const classes = {
    success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-700",
    danger: "border-red-500/30 bg-red-500/10 text-red-700",
    neutral: "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)]",
  }[tone]

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-black ${classes}`}>
      {statusLabel(status)}
    </span>
  )
}

function PanelHeader({
  title,
  description,
  icon,
  children,
}: {
  title: string
  description: string
  icon: ReactNode
  children?: ReactNode
}) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
          {icon}
        </span>
        <div>
          <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
          <p className="text-sm text-[var(--color-text-muted)]">{description}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

function ExportButtons({ onExport }: { onExport: (format: "csv" | "xlsx") => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onExport("csv")}
        className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-black text-[var(--color-text)] transition hover:bg-[var(--color-hover)]"
      >
        <Download className="h-4 w-4" /> CSV
      </button>
      <button
        type="button"
        onClick={() => onExport("xlsx")}
        className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)]"
      >
        <Download className="h-4 w-4" /> XLSX
      </button>
    </div>
  )
}

function ActionList({
  title,
  items,
  empty,
  tone,
}: {
  title: string
  items: string[]
  empty: string
  tone: "primary" | "warning" | "danger"
}) {
  const icon =
    tone === "danger" ? (
      <XCircle className="h-4 w-4" />
    ) : tone === "warning" ? (
      <AlertTriangle className="h-4 w-4" />
    ) : (
      <CheckCircle2 className="h-4 w-4" />
    )
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <h3 className="flex items-center gap-2 text-sm font-black text-[var(--color-text)]">
        {icon}
        {title}
      </h3>
      <div className="mt-3 space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">{empty}</p>
        ) : (
          items.map((item) => (
            <p key={item} className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
              {item}
            </p>
          ))
        )}
      </div>
    </section>
  )
}

// ── OVERVIEW PANEL ───────────────────────────────────────────────────────────

function OverviewPanel({
  health,
  context,
  availableCompanies,
  exportingIndicator,
  onIndicatorExport,
}: {
  health: MvpHealthReport | null
  context: CompanyContextReport | null
  availableCompanies: AvailableCompaniesReport | null
  exportingIndicator: HealthIndicatorKey | null
  onIndicatorExport: (indicator: HealthIndicatorKey) => void
}) {
  const counts = health?.counts ?? {}
  const pendencies = health?.pendencies ?? {}

  return (
    <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        {/* Score header with visual bar */}
        <div className="mb-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold text-[var(--color-text-muted)]">Saúde operacional</p>
              <h2 className="mt-1 text-2xl font-black text-[var(--color-text)]">
                {health ? statusLabel(health.status) : "Carregando"}
              </h2>
            </div>
            <StatusBadge status={health?.status} />
          </div>
          {health && (
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-semibold text-[var(--color-text-muted)]">Score Kovir</span>
                <span className="text-xl font-black" style={{ color: scoreColor(health.score) }}>
                  {health.score} / 100
                </span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-bg-soft)]">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${Math.max(0, Math.min(100, health.score))}%`,
                    background: scoreColor(health.score),
                  }}
                />
              </div>
              <p className="mt-1.5 text-xs text-[var(--color-text-muted)]">
                {health.score >= 85
                  ? "Sistema saudável — demonstrável com segurança."
                  : health.score >= 70
                    ? "Atenção: corrija as pendências antes de apresentar."
                    : "Bloqueado: há problemas críticos que precisam ser resolvidos."}
              </p>
            </div>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <MetricCard
            label="Participantes"
            value={String(counts.participants_count ?? 0)}
            helper="base cadastral"
            icon={<Building2 className="h-5 w-5" />}
            onExport={() => onIndicatorExport("participants")}
            isExporting={exportingIndicator === "participants"}
          />
          <MetricCard
            label="Títulos"
            value={String(counts.titles_count ?? 0)}
            helper="receber + pagar"
            icon={<WalletCards className="h-5 w-5" />}
            onExport={() => onIndicatorExport("titles")}
            isExporting={exportingIndicator === "titles"}
          />
          <MetricCard
            label="Movimentos"
            value={String(counts.movements_count ?? 0)}
            helper="caixa interno"
            icon={<BarChart3 className="h-5 w-5" />}
            onExport={() => onIndicatorExport("movements")}
            isExporting={exportingIndicator === "movements"}
          />
          <MetricCard
            label="Vendas"
            value={String(counts.sales_count ?? 0)}
            helper="ciclo comercial"
            icon={<FileText className="h-5 w-5" />}
            onExport={() => onIndicatorExport("sales")}
            isExporting={exportingIndicator === "sales"}
          />
          <MetricCard
            label="Compras"
            value={String(counts.purchases_count ?? 0)}
            helper="obrigações"
            icon={<ClipboardList className="h-5 w-5" />}
            onExport={() => onIndicatorExport("purchases")}
            isExporting={exportingIndicator === "purchases"}
          />
          <MetricCard
            label="Conciliações"
            value={String(counts.reconciliation_matches_count ?? 0)}
            helper="matches bancários"
            icon={<ListChecks className="h-5 w-5" />}
            onExport={() => onIndicatorExport("reconciliation_matches")}
            isExporting={exportingIndicator === "reconciliation_matches"}
          />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <PendencyCard
            label="Títulos vencidos"
            value={pendencies.overdue_titles ?? 0}
            helper={formatMoney(pendencies.overdue_amount as string)}
            onExport={() => onIndicatorExport("overdue_titles")}
            isExporting={exportingIndicator === "overdue_titles"}
          />
          <PendencyCard
            label="Sem origem clara"
            value={pendencies.titles_without_clear_origin ?? 0}
            helper={formatMoney(pendencies.titles_without_clear_origin_amount as string)}
            onExport={() => onIndicatorExport("titles_without_clear_origin")}
            isExporting={exportingIndicator === "titles_without_clear_origin"}
          />
          <PendencyCard
            label="Sem participante"
            value={pendencies.titles_without_participant ?? 0}
            helper={formatMoney(pendencies.titles_without_participant_amount as string)}
            onExport={() => onIndicatorExport("titles_without_participant")}
            isExporting={exportingIndicator === "titles_without_participant"}
          />
          <PendencyCard
            label="Sem conciliação"
            value={pendencies.unreconciled_movements ?? 0}
            helper={formatMoney(pendencies.unreconciled_amount as string)}
            onExport={() => onIndicatorExport("unreconciled_movements")}
            isExporting={exportingIndicator === "unreconciled_movements"}
          />
          <PendencyCard
            label="Extratos sem match"
            value={pendencies.unmatched_bank_statement_lines ?? 0}
            helper={formatMoney(pendencies.unmatched_bank_statement_amount as string)}
            onExport={() => onIndicatorExport("unmatched_bank_statement_lines")}
            isExporting={exportingIndicator === "unmatched_bank_statement_lines"}
          />
        </div>
      </section>

      <aside className="space-y-5">
        {/* Company context */}
        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
          <p className="text-xs font-bold text-[var(--color-text-muted)]">Empresa ativa</p>
          <h3 className="mt-2 text-xl font-black text-[var(--color-text)]">{context?.display_name ?? "—"}</h3>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[var(--color-text-muted)]">CNPJ</span>
              <span className="font-bold text-[var(--color-text)]">{context?.cnpj ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[var(--color-text-muted)]">Regime</span>
              <span className="font-bold text-[var(--color-text)]">{context?.tax_regime ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[var(--color-text-muted)]">Ambiente</span>
              <span className="font-bold text-[var(--color-text)]">{context?.fiscal_environment ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[var(--color-text-muted)]">Reforma tributária</span>
              <span className={`font-black ${context?.prepared_for_tax_reform ? "text-emerald-600" : "text-amber-600"}`}>
                {context?.prepared_for_tax_reform ? "Preparada ✓" : "Não sinalizada"}
              </span>
            </div>
          </div>
        </section>

        <ActionList title="Bloqueios críticos" empty="Sem bloqueios no período." items={health?.blockers ?? []} tone="danger" />
        <ActionList title="Alertas" empty="Sem alertas relevantes." items={health?.warnings ?? []} tone="warning" />
        <ActionList title="Próximas prioridades" empty="Sem prioridades retornadas." items={health?.next_backend_priorities ?? []} tone="primary" />
        <ActionList title="Notas de cálculo" empty="Sem notas de cálculo." items={health?.calculation_notes ?? []} tone="primary" />

        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-muted)] shadow-xl shadow-[var(--color-card-shadow)]">
          <p className="font-black text-[var(--color-text)]">Empresas no relatório</p>
          <p className="mt-1">{availableCompanies?.total_returned ?? 0} empresa(s) disponíveis no backend.</p>
        </section>
      </aside>
    </div>
  )
}

function PendencyCard({
  label,
  value,
  helper,
  onExport,
  isExporting = false,
}: {
  label: string
  value: string | number
  helper: string
  onExport?: () => void
  isExporting?: boolean
}) {
  const count = toNumber(value)
  return (
    <div
      className={`rounded-3xl border p-4 ${
        count > 0
          ? "border-amber-500/30 bg-amber-500/10"
          : "border-emerald-500/30 bg-emerald-500/10"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-bold text-[var(--color-text-muted)]">{label}</p>
        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting}
            aria-label={`Exportar ${label} em XLSX`}
            title={`Exportar ${label} em XLSX`}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          </button>
        ) : null}
      </div>
      <p className={`mt-1 text-2xl font-black ${count > 0 ? "text-amber-700" : "text-emerald-700"}`}>
        {String(value)}
      </p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{helper}</p>
    </div>
  )
}

// ── CYCLE PANEL ──────────────────────────────────────────────────────────────

function CyclePanel({ cycle, onExport }: { cycle: FinancialCycleReport | null; onExport: (format: "csv" | "xlsx") => void }) {
  return (
    <div className="space-y-5">
      <PanelHeader
        title="Ciclo financeiro integrado"
        description="Títulos, baixas, movimentos e saldos internos em leituras separadas. Venda não é recebimento; baixa não é conciliação."
        icon={<BarChart3 className="h-5 w-5" />}
      >
        <ExportButtons onExport={onExport} />
      </PanelHeader>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-muted)] shadow-xl shadow-[var(--color-card-shadow)]">
        <p className="font-black text-[var(--color-text)]">Leitura do período</p>
        <p className="mt-1">
          Títulos, baixas e movimentos respeitam {formatDate(cycle?.period.start_date)} a {formatDate(cycle?.period.end_date)}. Saldos internos são saldos atuais materializados por conta financeira, não saldo final do período.
        </p>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <TitleSummaryTable rows={cycle?.titles_by_direction ?? []} />
        <SettlementSummaryTable rows={cycle?.settlements_by_direction ?? []} />
        <MovementSummaryTable rows={cycle?.movements_by_direction ?? []} />
        <BalancesTable balances={cycle?.financial_account_balances ?? []} />
      </div>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <h3 className="text-sm font-black text-[var(--color-text-muted)]">Regras de interpretação</h3>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {(cycle?.interpretation_rules ?? []).length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">Sem regras retornadas para o período.</p>
          ) : (cycle?.interpretation_rules ?? []).map((rule) => (
            <p key={rule} className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
              {rule}
            </p>
          ))}
        </div>
      </section>
    </div>
  )
}

function TitleSummaryTable({ rows }: { rows: DirectionSummary[] }) {
  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="border-b border-[var(--color-border-soft)] p-5">
        <h3 className="text-lg font-black text-[var(--color-text)]">Títulos por direção</h3>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">Direitos e obrigações por vencimento. Título não é dinheiro.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[820px] text-left text-sm">
          <thead className="bg-[var(--color-bg-soft)] text-xs font-bold text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3">Direção</th>
              <th className="px-4 py-3">Títulos</th>
              <th className="px-4 py-3">Ativos</th>
              <th className="px-4 py-3">Líquido</th>
              <th className="px-4 py-3">Aberto ativo</th>
              <th className="px-4 py-3">Vencido</th>
              <th className="px-4 py-3">Pendências</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="px-4 py-5 text-[var(--color-text-muted)]" colSpan={7}>Sem títulos para o período.</td>
              </tr>
            ) : rows.map((row) => (
              <tr key={`titles-${row.direction}`} className="border-t border-[var(--color-border-soft)]">
                <td className="px-4 py-3 font-bold text-[var(--color-text)]">{directionLabel(row.direction)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.total_titles ?? 0}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.active_titles ?? 0}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(row.net_amount)}</td>
                <td className="px-4 py-3 font-bold text-[var(--color-text)]">{formatMoney(row.active_open_amount)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(row.overdue_amount)}</td>
                <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                  {(row.titles_without_participant ?? 0)} sem participante · {(row.titles_without_clear_origin ?? 0)} sem origem
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SettlementSummaryTable({ rows }: { rows: DirectionSummary[] }) {
  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="border-b border-[var(--color-border-soft)] p-5">
        <h3 className="text-lg font-black text-[var(--color-text)]">Baixas por direção</h3>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">Liquidação de título. Baixa não é conciliação bancária.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[720px] text-left text-sm">
          <thead className="bg-[var(--color-bg-soft)] text-xs font-bold text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3">Direção</th>
              <th className="px-4 py-3">Baixas</th>
              <th className="px-4 py-3">Liquidado no título</th>
              <th className="px-4 py-3">Movimentado no caixa</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="px-4 py-5 text-[var(--color-text-muted)]" colSpan={4}>Sem baixas para o período.</td>
              </tr>
            ) : rows.map((row) => (
              <tr key={`settlements-${row.direction}`} className="border-t border-[var(--color-border-soft)]">
                <td className="px-4 py-3 font-bold text-[var(--color-text)]">{directionLabel(row.direction)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.total_settlements ?? 0}</td>
                <td className="px-4 py-3 font-bold text-[var(--color-text)]">{formatMoney(row.title_settled_amount)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(row.movement_amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function MovementSummaryTable({ rows }: { rows: DirectionSummary[] }) {
  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="border-b border-[var(--color-border-soft)] p-5">
        <h3 className="text-lg font-black text-[var(--color-text)]">Movimentos por direção</h3>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">Dinheiro interno registrado. Match bancário apenas confere o movimento.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[820px] text-left text-sm">
          <thead className="bg-[var(--color-bg-soft)] text-xs font-bold text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3">Direção</th>
              <th className="px-4 py-3">Movimentos</th>
              <th className="px-4 py-3">Valor total</th>
              <th className="px-4 py-3">Conciliado</th>
              <th className="px-4 py-3">Pendente conciliação</th>
              <th className="px-4 py-3">Qtde. conc.</th>
              <th className="px-4 py-3">Qtde. pendente</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="px-4 py-5 text-[var(--color-text-muted)]" colSpan={7}>Sem movimentos para o período.</td>
              </tr>
            ) : rows.map((row) => (
              <tr key={`movements-${row.direction}`} className="border-t border-[var(--color-border-soft)]">
                <td className="px-4 py-3 font-bold text-[var(--color-text)]">{directionLabel(row.direction)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.total_movements ?? 0}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(row.amount)}</td>
                <td className="px-4 py-3 font-bold text-emerald-700">{formatMoney(row.reconciled_amount)}</td>
                <td className="px-4 py-3 font-bold text-amber-700">{formatMoney(row.unreconciled_amount)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.reconciled_movements ?? 0}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{row.unreconciled_movements ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function BalancesTable({ balances }: { balances: FinancialAccountBalanceReport[] }) {
  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="border-b border-[var(--color-border-soft)] p-5">
        <h3 className="text-lg font-black text-[var(--color-text)]">Saldos internos</h3>
        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
          Saldo atual materializado por conta financeira; não representa saldo final do período filtrado.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-[var(--color-bg-soft)] text-xs font-bold text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3">Conta</th>
              <th className="px-4 py-3">Tipo</th>
              <th className="px-4 py-3">Saldo</th>
            </tr>
          </thead>
          <tbody>
            {balances.length === 0 ? (
              <tr>
                <td className="px-4 py-5 text-[var(--color-text-muted)]" colSpan={3}>
                  Sem saldo interno registrado.
                </td>
              </tr>
            ) : (
              balances.map((balance) => (
                <tr key={balance.financial_account_id} className="border-t border-[var(--color-border-soft)]">
                  <td className="px-4 py-3 font-bold text-[var(--color-text)]">{balance.financial_account_name}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{balance.account_type}</td>
                  <td className="px-4 py-3 font-bold text-[var(--color-text)]">{formatMoney(balance.balance_amount)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

// ── BACKLOG PANEL ────────────────────────────────────────────────────────────

function daysOverdue(dueDate: string | undefined): number {
  if (!dueDate) return 0
  const due = new Date(`${dueDate}T00:00:00`)
  const now = new Date(`${today()}T00:00:00`)
  if (Number.isNaN(due.getTime())) return 0
  return Math.max(0, Math.floor((now.getTime() - due.getTime()) / 86400000))
}

function BacklogPanel({
  backlog,
  exporting,
  onExport,
}: {
  backlog: OperationalBacklogReport | null
  exporting: BacklogExportState
  onExport: (indicator: BacklogExportKey | "all") => void
}) {
  const visibleTotal =
    (backlog?.overdue_titles.length ?? 0) +
    (backlog?.titles_without_clear_origin.length ?? 0) +
    (backlog?.unreconciled_movements.length ?? 0) +
    (backlog?.unmatched_bank_statement_lines.length ?? 0)
  const total = backlog?.totals?.total_pendencies ?? visibleTotal
  const isExportingAll = exporting === "all"

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Pendências operacionais"
        description={`${total} item(ns) exigem ação ou revisão antes de uma leitura financeira limpa.${backlog?.totals?.is_limited ? ` A tela mostra até ${backlog.limit} por categoria; o XLSX exporta a base completa.` : ""}`}
        icon={<AlertTriangle className="h-5 w-5" />}
      >
        <button
          type="button"
          onClick={() => onExport("all")}
          disabled={!backlog || exporting !== null}
          className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-black text-emerald-700 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isExportingAll ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          XLSX consolidado
        </button>
      </PanelHeader>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-muted)] shadow-xl shadow-[var(--color-card-shadow)]">
        <p className="font-black text-[var(--color-text)]">Como ler esta seção</p>
        <p className="mt-1">
          Títulos vencidos e títulos sem origem clara são pendências globais da empresa. Movimentos sem conciliação e linhas de extrato sem match respeitam o período filtrado: {formatDate(backlog?.period.start_date)} a {formatDate(backlog?.period.end_date)}.
        </p>
        <p className="mt-1">
          Linhas de extrato ignoradas não entram como pendência. Conciliação continua sendo conferência posterior; ela não cria baixa nem movimento financeiro.
        </p>
      </section>

      {total === 0 && backlog && (
        <div className="rounded-[2rem] border border-emerald-500/30 bg-emerald-500/10 p-8 text-center shadow-xl shadow-[var(--color-card-shadow)]">
          <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
          <p className="mt-3 text-lg font-black text-emerald-700">Tudo em ordem!</p>
          <p className="mt-1 text-sm text-emerald-600">Nenhuma pendência operacional encontrada nos critérios atuais.</p>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-2">
        <BacklogList
          title="Títulos vencidos"
          scope="Global: todos os títulos ativos vencidos até hoje."
          items={backlog?.overdue_titles ?? []}
          kind="title"
          category="overdue_titles"
          totalCount={backlog?.totals?.overdue_titles ?? 0}
          totalAmount={backlog?.totals?.overdue_titles_amount ?? "0.00"}
          exporting={exporting}
          onExport={onExport}
        />
        <BacklogList
          title="Títulos sem origem clara"
          scope="Global: títulos sem venda, documento, referência ou origem rastreável."
          items={backlog?.titles_without_clear_origin ?? []}
          kind="title"
          category="titles_without_clear_origin"
          totalCount={backlog?.totals?.titles_without_clear_origin ?? 0}
          totalAmount={backlog?.totals?.titles_without_clear_origin_amount ?? "0.00"}
          exporting={exporting}
          onExport={onExport}
        />
        <BacklogList
          title="Movimentos sem conciliação"
          scope="Período filtrado: movimentos internos postados com status pending/divergent."
          items={backlog?.unreconciled_movements ?? []}
          kind="movement"
          category="unreconciled_movements"
          totalCount={backlog?.totals?.unreconciled_movements ?? 0}
          totalAmount={backlog?.totals?.unreconciled_movements_amount ?? "0.00"}
          exporting={exporting}
          onExport={onExport}
        />
        <BacklogList
          title="Linhas de extrato sem match"
          scope="Período filtrado: extratos externos pending/divergent ainda sem match confirmado."
          items={backlog?.unmatched_bank_statement_lines ?? []}
          kind="statement"
          category="unmatched_bank_statement_lines"
          totalCount={backlog?.totals?.unmatched_bank_statement_lines ?? 0}
          totalAmount={backlog?.totals?.unmatched_bank_statement_amount ?? "0.00"}
          exporting={exporting}
          onExport={onExport}
        />
      </div>
    </div>
  )
}

function BacklogList({
  title,
  scope,
  items,
  kind,
  category,
  totalCount,
  totalAmount,
  exporting,
  onExport,
}: {
  title: string
  scope: string
  items: BacklogTitleItem[] | BacklogMovementItem[] | BacklogStatementLineItem[]
  kind: "title" | "movement" | "statement"
  category: BacklogExportKey
  totalCount: number
  totalAmount: string
  exporting: BacklogExportState
  onExport: (indicator: BacklogExportKey | "all") => void
}) {
  const isExporting = exporting === category
  const visibleCount = items.length
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-black text-[var(--color-text)]">{title}</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">{scope}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => onExport(category)}
            disabled={exporting !== null}
            aria-label={`Exportar ${title} em XLSX`}
            title={`Exportar ${title} em XLSX`}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          </button>
          <span
            className={`rounded-full border px-3 py-1 text-xs font-black ${
              totalCount > 0
                ? "border-amber-500/30 bg-amber-500/10 text-amber-700"
                : "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
            }`}
          >
            {totalCount}
          </span>
        </div>
      </div>

      <div className="mb-4 grid gap-2 rounded-2xl bg-[var(--color-bg-soft)] p-4 text-sm sm:grid-cols-2">
        <p className="text-[var(--color-text-muted)]">
          Total real: <span className="font-black text-[var(--color-text)]">{totalCount}</span>
        </p>
        <p className="text-[var(--color-text-muted)]">
          Valor total: <span className="font-black text-[var(--color-text)]">{formatMoney(totalAmount)}</span>
        </p>
        <p className="text-xs text-[var(--color-text-muted)] sm:col-span-2">
          Mostrando {visibleCount} de {totalCount}. Use o XLSX para baixar a lista completa.
        </p>
      </div>

      <div className="space-y-3">
        {items.length === 0 ? (
          <p className="rounded-2xl bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
            Sem pendências nesta seção. ✓
          </p>
        ) : (
          items.map((item) => (
            <div key={String(item.id)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
              {kind === "title" ? (
                <TitleBacklogItem item={item as BacklogTitleItem} category={category} />
              ) : kind === "movement" ? (
                <MovementBacklogItem item={item as BacklogMovementItem} />
              ) : (
                <StatementBacklogItem item={item as BacklogStatementLineItem} />
              )}
            </div>
          ))
        )}
      </div>
    </section>
  )
}

function TitleBacklogItem({ item, category }: { item: BacklogTitleItem; category: BacklogExportKey }) {
  const overdueDays = daysOverdue(item.due_date)
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-black text-[var(--color-text)]">{item.title_reference ?? item.id}</p>
        <StatusBadge status={item.status ?? ""} />
      </div>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {directionLabel(item.direction)} · {item.participant_name ?? "Sem participante"}
      </p>
      <p className="mt-2 text-sm font-bold text-[var(--color-text)]">
        Aberto: {formatMoney(item.open_amount)} · Vencimento: {formatDate(item.due_date)}
        {category === "overdue_titles" && overdueDays > 0 ? ` · ${overdueDays} dia(s) em atraso` : ""}
      </p>
      <p className="mt-2 text-xs text-[var(--color-text-muted)]">
        Ação: {category === "overdue_titles" ? "registrar baixa, renegociar ou justificar cobrança." : "vincular origem, documento ou referência operacional antes de usar como base gerencial."}
      </p>
    </>
  )
}

function MovementBacklogItem({ item }: { item: BacklogMovementItem }) {
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-black text-[var(--color-text)]">{item.description ?? item.id}</p>
        <StatusBadge status={item.reconciliation_status ?? ""} />
      </div>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {directionLabel(item.direction)} · {item.financial_account_name ?? "Conta não informada"}
      </p>
      <p className="mt-2 text-sm font-bold text-[var(--color-text)]">
        {formatMoney(item.amount)} · {formatDate(item.movement_date)}
      </p>
      <p className="mt-2 text-xs text-[var(--color-text-muted)]">
        Ação: conciliar com extrato ou revisar divergência. Movimento interno não é conciliação.
      </p>
    </>
  )
}

function StatementBacklogItem({ item }: { item: BacklogStatementLineItem }) {
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-black text-[var(--color-text)]">{item.description ?? item.id}</p>
        <StatusBadge status={item.status ?? ""} />
      </div>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">
        {directionLabel(item.direction)} · {item.financial_account_name ?? "Conta não informada"}
      </p>
      <p className="mt-2 text-sm font-bold text-[var(--color-text)]">
        {formatMoney(item.amount)} · {formatDate(item.statement_date)}
      </p>
      <p className="mt-2 text-xs text-[var(--color-text-muted)]">
        Ação: fazer match com movimento interno, criar registro financeiro correspondente ou ignorar com justificativa quando não for item operacional.
      </p>
    </>
  )
}

// ── TITLES PANEL ─────────────────────────────────────────────────────────────

function TitlesPanel({
  titles,
  titleDirection,
  titleStatus,
  titleSearch,
  limit,
  offset,
  periodStart,
  periodEnd,
  isExporting,
  onDirectionChange,
  onStatusChange,
  onSearchChange,
  onLimitChange,
  onPageChange,
  onSubmit,
  onExport,
}: {
  titles: TitleReferencesReport | null
  titleDirection: string
  titleStatus: string
  titleSearch: string
  limit: number
  offset: number
  periodStart: string
  periodEnd: string
  isExporting: boolean
  onDirectionChange: (value: string) => void
  onStatusChange: (value: string) => void
  onSearchChange: (value: string) => void
  onLimitChange: (value: number) => void
  onPageChange: (offset: number) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onExport: (format: "csv" | "xlsx") => void
}) {
  const summary = titles?.summary
  const hasPrevious = Boolean(summary?.has_previous)
  const hasNext = Boolean(summary?.has_next)
  const pageStart = titles && titles.total > 0 ? offset + 1 : 0
  const pageEnd = titles ? offset + (titles.items?.length ?? 0) : 0

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Títulos financeiros"
        description="Carteira de direitos e obrigações. Título não é dinheiro; baixa, movimento e conciliação são fatos separados."
        icon={<WalletCards className="h-5 w-5" />}
      >
        <div className="flex flex-wrap items-center gap-2">
          {isExporting ? (
            <span className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-black text-emerald-700">
              <Loader2 className="h-4 w-4 animate-spin" /> Exportando base completa
            </span>
          ) : null}
          <ExportButtons onExport={onExport} />
        </div>
      </PanelHeader>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-muted)] shadow-xl shadow-[var(--color-card-shadow)]">
        <p className="font-black text-[var(--color-text)]">Filtro financeiro aplicado</p>
        <p className="mt-1">
          Esta seção usa o período global como filtro de vencimento: {formatDate(periodStart)} a {formatDate(periodEnd)}. A exportação CSV/XLSX baixa a base completa filtrada, não apenas a página visível.
        </p>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Títulos no filtro" value={String(summary?.total_count ?? 0)} helper={`${summary?.page_count ?? 0} visível(is)`} icon={<WalletCards className="h-5 w-5" />} />
        <MetricCard label="Aberto ativo" value={formatMoney(summary?.active_open_amount)} helper={`${summary?.active_count ?? 0} título(s) ativo(s)`} icon={<AlertTriangle className="h-5 w-5" />} tone="warning" />
        <MetricCard label="Vencido" value={formatMoney(summary?.overdue_open_amount)} helper={`${summary?.overdue_count ?? 0} vencido(s)`} icon={<XCircle className="h-5 w-5" />} tone="danger" />
        <MetricCard label="Baixado no título" value={formatMoney(summary?.total_paid_amount)} helper={`Líquido ${formatMoney(summary?.total_net_amount)}`} icon={<CheckCircle2 className="h-5 w-5" />} tone="success" />
      </div>

      <form
        onSubmit={onSubmit}
        className="grid gap-3 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)] lg:grid-cols-[1fr_1fr_1fr_0.8fr_auto]"
      >
        <label className="space-y-1">
          <span className="text-xs font-bold text-[var(--color-text-muted)]">Direção</span>
          <select
            value={titleDirection}
            onChange={(e) => onDirectionChange(e.target.value)}
            className="field-input text-sm font-semibold"
          >
            <option value="">Todas</option>
            <option value="receivable">A receber</option>
            <option value="payable">A pagar</option>
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-bold text-[var(--color-text-muted)]">Status</span>
          <select
            value={titleStatus}
            onChange={(e) => onStatusChange(e.target.value)}
            className="field-input text-sm font-semibold"
          >
            <option value="">Todos</option>
            <option value="open">Em aberto</option>
            <option value="overdue">Vencido</option>
            <option value="partially_received">Recebido parcial</option>
            <option value="received">Recebido</option>
            <option value="partially_paid">Pago parcial</option>
            <option value="paid">Pago</option>
            <option value="written_off">Baixado sem pagamento</option>
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-bold text-[var(--color-text-muted)]">Busca</span>
          <input
            value={titleSearch}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Participante, documento, pedido…"
            className="field-input text-sm font-semibold"
          />
        </label>

        <label className="space-y-1">
          <span className="text-xs font-bold text-[var(--color-text-muted)]">Limite</span>
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value || 20))}
            className="field-input text-sm font-semibold"
          />
        </label>

        <button
          type="submit"
          className="mt-auto inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)]"
        >
          <Search className="h-4 w-4" /> Filtrar
        </button>
      </form>

      <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="border-b border-[var(--color-border-soft)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-black text-[var(--color-text)]">
                {titles?.total ?? 0} título(s) encontrado(s)
              </h3>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                Página exibindo {pageStart} a {pageEnd}. Total em aberto do filtro: {formatMoney(summary?.total_open_amount)}.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={!hasPrevious}
                onClick={() => onPageChange(Math.max(0, offset - limit))}
                className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2 text-sm font-black text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={!hasNext}
                onClick={() => onPageChange(offset + limit)}
                className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Próxima
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-[1320px] text-left text-sm">
            <thead className="bg-[var(--color-bg-soft)] text-xs font-bold text-[var(--color-text-muted)]">
              <tr>
                <th className="px-4 py-3">Referência</th>
                <th className="px-4 py-3">Direção</th>
                <th className="px-4 py-3">Participante</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Parcela</th>
                <th className="px-4 py-3">Vencimento</th>
                <th className="px-4 py-3">Atraso</th>
                <th className="px-4 py-3">Líquido</th>
                <th className="px-4 py-3">Baixado</th>
                <th className="px-4 py-3">Aberto</th>
                <th className="px-4 py-3">Origem</th>
              </tr>
            </thead>
            <tbody>
              {(titles?.items ?? []).length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-[var(--color-text-muted)]" colSpan={11}>
                    Nenhum título encontrado para os filtros selecionados.
                  </td>
                </tr>
              ) : (
                titles?.items.map((item) => (
                  <tr key={item.id} className="border-t border-[var(--color-border-soft)] hover:bg-[var(--color-hover)]">
                    <td className="px-4 py-3">
                      <p className="font-black text-[var(--color-text)]">{item.human_reference}</p>
                      <p className="max-w-[18rem] truncate text-xs text-[var(--color-text-muted)]" title={item.id}>
                        {item.id}
                      </p>
                      {item.document_reference ? (
                        <p className="mt-1 text-xs font-bold text-[var(--color-text-muted)]">{item.document_reference}</p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{directionLabel(item.direction)}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      <p>{item.participant_name ?? "—"}</p>
                      <p className="text-xs">{item.participant_document ?? ""}</p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={item.status} />
                      {item.collection_status ? <p className="mt-1 text-xs text-[var(--color-text-muted)]">{statusLabel(item.collection_status)}</p> : null}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatInstallment(item) || "—"}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatDate(item.due_date)}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{daysOverdue(item.due_date) || "—"}</td>
                    <td className="px-4 py-3 font-bold text-[var(--color-text)]">{formatMoney(item.net_amount)}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(item.paid_amount)}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatMoney(item.open_amount)}</td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                      <p>{item.sale_number_text ?? item.sale_id ?? "—"}</p>
                      <p>{[item.source_type, item.source_id].filter(Boolean).join(" / ")}</p>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

// ── FISCAL PREPARATORY PANEL ─────────────────────────────────────────────────

function FiscalPreparatoryPanel({
  report,
  onExport,
  exportingGroup,
}: {
  report: PreparatoryFiscalDocumentsReport | null
  onExport: (group: FiscalExportKey) => void
  exportingGroup: FiscalExportState
}) {
  const summary = report?.summary
  return (
    <div className="space-y-5">
      <PanelHeader
        title="Docs fiscais"
        description="Pré-checagem fiscal e documentos fiscais registrados. Esta tela lê dados; não emite nota."
        icon={<FileText className="h-5 w-5" />}
      >
        <button
          type="button"
          onClick={() => onExport("all")}
          disabled={exportingGroup !== null}
          className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {exportingGroup === "all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          XLSX consolidado
        </button>
      </PanelHeader>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Vendas pendentes"
          value={String(summary?.pending_sales_documents ?? 0)}
          helper={formatMoney(summary?.pending_sales_amount)}
          icon={<FileText className="h-5 w-5" />}
          tone={(summary?.pending_sales_documents ?? 0) > 0 ? "warning" : "success"}
          onExport={() => onExport("sales")}
          isExporting={exportingGroup !== null}
        />
        <MetricCard
          label="Compras pendentes"
          value={String(summary?.pending_purchase_documents ?? 0)}
          helper={formatMoney(summary?.pending_purchase_amount)}
          icon={<ClipboardList className="h-5 w-5" />}
          tone={(summary?.pending_purchase_documents ?? 0) > 0 ? "warning" : "success"}
          onExport={() => onExport("purchases")}
          isExporting={exportingGroup !== null}
        />
        <MetricCard
          label="Títulos fiscais pendentes"
          value={String(summary?.pending_fiscal_titles ?? 0)}
          helper={formatMoney(summary?.pending_fiscal_open_amount)}
          icon={<WalletCards className="h-5 w-5" />}
          tone={(summary?.pending_fiscal_titles ?? 0) > 0 ? "warning" : "success"}
          onExport={() => onExport("titles")}
          isExporting={exportingGroup !== null}
        />
        <MetricCard
          label="NF-e/NFC-e registradas"
          value={String(summary?.fiscal_documents_total ?? 0)}
          helper={`${summary?.fiscal_documents_authorized ?? 0} autorizada(s), ${summary?.fiscal_documents_error ?? 0} erro(s)`}
          icon={<Gauge className="h-5 w-5" />}
          tone={(summary?.fiscal_documents_error ?? 0) > 0 ? "danger" : (summary?.fiscal_documents_pending ?? 0) > 0 ? "warning" : "success"}
          onExport={() => onExport("documents")}
          isExporting={exportingGroup !== null}
        />
      </div>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-black text-[var(--color-text)]">Leitura fiscal do período</p>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              Vendas em orçamento não entram como pendência fiscal. Compra marcada como não exigida também não entra. Título financeiro não é documento fiscal.
            </p>
          </div>
          <StatusBadge status={summary?.status ?? "ATTENTION"} />
        </div>
        <div className="mt-4 grid gap-3 text-sm text-[var(--color-text-muted)] md:grid-cols-4">
          <p><span className="font-black text-[var(--color-text)]">{summary?.blocking_items ?? 0}</span> item(ns) bloqueantes</p>
          <p><span className="font-black text-[var(--color-text)]">{summary?.fiscal_documents_pending ?? 0}</span> documento(s) processando</p>
          <p><span className="font-black text-[var(--color-text)]">{summary?.fiscal_documents_cancelled ?? 0}</span> documento(s) cancelado(s)</p>
          <p><span className="font-black text-[var(--color-text)]">{report?.limit ?? 0}</span> limite visual por grupo</p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="text-lg font-black text-[var(--color-text)]">Vendas com pendência fiscal</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Total real: {summary?.pending_sales_documents ?? 0}. A lista abaixo mostra {report?.returned_rows.sales_documents ?? 0}.
          </p>
          <div className="mt-3 space-y-2">
            {(report?.sales_documents ?? []).length === 0 ? (
              <p className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
                Sem pendências de venda para o período. ✓
              </p>
            ) : (
              report?.sales_documents.map((item) => (
                <div key={item.sale_id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-black text-[var(--color-text)]">{item.sale_number_text ?? item.sale_id}</p>
                    <StatusBadge status={item.fiscal_status} />
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {formatDate(item.operation_date)} · {item.participant_name ?? "Sem participante"} · {formatMoney(item.total_amount)}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{fiscalSaleReason(item)}</p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="text-lg font-black text-[var(--color-text)]">Compras com pendência fiscal</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Total real: {summary?.pending_purchase_documents ?? 0}. A lista abaixo mostra {report?.returned_rows.purchase_documents ?? 0}.
          </p>
          <div className="mt-3 space-y-2">
            {(report?.purchase_documents ?? []).length === 0 ? (
              <p className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
                Sem pendências de compra para o período. ✓
              </p>
            ) : (
              report?.purchase_documents.map((item) => (
                <div key={item.purchase_id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-black text-[var(--color-text)]">{item.document_number ?? item.purchase_id}</p>
                    <StatusBadge status={item.fiscal_status} />
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {formatDate(item.operation_date)} · {item.participant_name ?? "Sem participante"} · {formatMoney(item.total_amount)}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                    Documento: {item.document_number ?? "não informado"}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{fiscalPurchaseReason(item)}</p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="text-lg font-black text-[var(--color-text)]">Títulos com status fiscal pendente</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Total real: {summary?.pending_fiscal_titles ?? 0}. Valor aberto: {formatMoney(summary?.pending_fiscal_open_amount)}.
          </p>
          <div className="mt-3 space-y-2">
            {(report?.title_documents ?? []).length === 0 ? (
              <p className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
                Sem títulos fiscais pendentes para o período. ✓
              </p>
            ) : (
              report?.title_documents.map((item) => (
                <div key={item.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-black text-[var(--color-text)]">{item.document_reference ?? item.sale_number_text ?? item.id}</p>
                    <StatusBadge status={item.fiscal_status} />
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {directionLabel(item.direction)} · vence {formatDate(item.due_date)} · aberto {formatMoney(item.open_amount)}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                    {item.participant_name ?? "Sem participante"} · parcela {item.installment_number}/{item.installment_total}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="text-lg font-black text-[var(--color-text)]">Documentos fiscais registrados</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Total real: {summary?.fiscal_documents_total ?? 0}. Erros: {summary?.fiscal_documents_error ?? 0}.
          </p>
          <div className="mt-3 space-y-2">
            {(report?.fiscal_documents ?? []).length === 0 ? (
              <p className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
                Nenhum documento fiscal registrado no período.
              </p>
            ) : (
              report?.fiscal_documents.map((item) => (
                <div key={item.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-black text-[var(--color-text)]">{item.reference}</p>
                    <StatusBadge status={item.status} />
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {item.document_type.toUpperCase()} {item.serie ? `série ${item.serie}` : ""} {item.number ? `nº ${item.number}` : ""} · {item.sale_number_text ?? item.sale_id}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{fiscalDocumentReason(item)}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

// ── FINANCIAL CLOSING PANEL ──────────────────────────────────────────────────

function FinancialClosingPanel({
  report,
  onExport,
  isExporting,
}: {
  report: FinancialCloseMvpReport | null
  onExport: () => void
  isExporting: boolean
}) {
  const snapshot = report?.snapshot
  const reconciliationPending = (snapshot?.unreconciled_movements ?? 0) + (snapshot?.pending_statement_lines ?? 0)
  const fiscalPending =
    (snapshot?.fiscal_preparatory_pending ?? 0) +
    (snapshot?.fiscal_documents_pending ?? 0) +
    (snapshot?.fiscal_documents_error ?? 0)
  const warningCount = report?.checklist.filter((item) => item.status === "WARN").length ?? 0
  const blockingCount = report?.blocking_issues.length ?? 0
  const statusTone: "success" | "warning" | "danger" =
    report?.close_status === "READY" ? "success" : report?.close_status === "BLOCKED" ? "danger" : "warning"

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Prontidão de fechamento"
        description="Checklist de confiança do período. Esta tela não fecha contabilidade nem cria lançamento."
        icon={<ShieldCheck className="h-5 w-5" />}
      >
        <button
          type="button"
          onClick={onExport}
          disabled={isExporting || !report}
          className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          XLSX do fechamento
        </button>
      </PanelHeader>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Período</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">
              {formatDate(report?.period.start_date)} a {formatDate(report?.period.end_date)}
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Data de referência</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">{formatDate(report?.reference_date)}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Gerado em</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">{formatDateTime(report?.generated_at)}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Fechamento com ressalva</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">
              {report?.can_close_with_warnings ? "Sem bloqueio estrutural" : "Bloqueado"}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Status de fechamento"
          value={report ? statusLabel(report.close_status) : "Carregando"}
          helper={`${blockingCount} bloqueio(s), ${warningCount} alerta(s)`}
          icon={<ShieldCheck className="h-5 w-5" />}
          tone={statusTone}
        />
        <MetricCard label="A receber aberto" value={formatMoney(snapshot?.open_receivable_amount)} helper={`${snapshot?.open_receivable_count ?? 0} título(s)`} icon={<WalletCards className="h-5 w-5" />} />
        <MetricCard label="A pagar aberto" value={formatMoney(snapshot?.open_payable_amount)} helper={`${snapshot?.open_payable_count ?? 0} título(s)`} icon={<FileText className="h-5 w-5" />} />
        <MetricCard label="Títulos vencidos" value={String(snapshot?.overdue_count ?? 0)} helper={formatMoney(snapshot?.overdue_amount)} icon={<AlertTriangle className="h-5 w-5" />} tone={(snapshot?.overdue_count ?? 0) > 0 ? "warning" : "success"} />
        <MetricCard
          label="Conciliação pendente"
          value={String(reconciliationPending)}
          helper={`${formatMoney(snapshot?.unreconciled_amount)} sem conciliação`}
          icon={<RefreshCw className="h-5 w-5" />}
          tone={reconciliationPending > 0 || (snapshot?.divergent_items ?? 0) > 0 ? "danger" : "success"}
        />
        <MetricCard
          label="Pendências fiscais"
          value={String(fiscalPending)}
          helper={`${snapshot?.fiscal_documents_error ?? 0} erro(s) fiscal(is)`}
          icon={<ClipboardList className="h-5 w-5" />}
          tone={(snapshot?.fiscal_documents_error ?? 0) > 0 ? "danger" : fiscalPending > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="Duplicidade de saldo"
          value={String(snapshot?.duplicate_balance_rows ?? 0)}
          helper="saldos internos materializados"
          icon={<Gauge className="h-5 w-5" />}
          tone={(snapshot?.duplicate_balance_rows ?? 0) > 0 ? "danger" : "success"}
        />
        <MetricCard
          label="Divergências"
          value={String(snapshot?.divergent_items ?? 0)}
          helper="movimentos/extratos divergentes"
          icon={<XCircle className="h-5 w-5" />}
          tone={(snapshot?.divergent_items ?? 0) > 0 ? "danger" : "success"}
        />
      </div>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <h3 className="text-lg font-black text-[var(--color-text)]">Checklist de fechamento</h3>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          PASS libera o critério. WARN exige revisão operacional. FAIL bloqueia confiança no fechamento.
        </p>
        <div className="mt-4 space-y-2">
          {(report?.checklist ?? []).length === 0 ? (
            <p className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
              Nenhum item de checklist retornado.
            </p>
          ) : (
            report?.checklist.map((item) => (
              <div
                key={item.code}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-black text-[var(--color-text)]">{item.label}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {item.blocking ? "Bloqueante" : "Não bloqueante"} - {closingEvidenceText(item.evidence)}
                  </p>
                </div>
                <StatusBadge status={item.status} />
              </div>
            ))
          )}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <ActionList title="Bloqueios atuais" empty="Sem bloqueios críticos." items={report?.blocking_issues ?? []} tone="danger" />
        <ActionList title="Ações recomendadas" empty="Sem ações pendentes." items={report?.recommended_actions ?? []} tone="warning" />
      </div>

      <ActionList title="Regras de leitura" empty="Sem notas retornadas." items={report?.notes ?? []} tone="primary" />
    </div>
  )
}

// ── ACCOUNTANT PANEL ─────────────────────────────────────────────────────────

function AccountantPanel({
  report,
  onExport,
  isExporting,
  onBlockExport,
  exportingBlock,
}: {
  report: AccountantPackReport | null
  onExport: (format: "csv" | "xlsx") => void
  isExporting: boolean
  onBlockExport: (block: AccountantExportBlock) => void
  exportingBlock: AccountantExportBlock | null
}) {
  const indicators = report?.indicators
  const formulas = Object.entries(report?.indicator_formulas ?? {})
  const notes = report?.notes ?? []
  const consistency = report?.consistency_checks
  const ignored = report?.operational_ignored
  const detailRows = Object.values(report?.detail_limits.returned_rows ?? {}).reduce((sum, count) => sum + count, 0)
  const totalFiscalPendencies =
    (indicators?.fiscal_document_pendencies.pending_sales_documents ?? 0) +
    (indicators?.fiscal_document_pendencies.pending_purchase_documents ?? 0) +
    (indicators?.fiscal_document_pendencies.pending_fiscal_titles ?? 0) +
    (indicators?.fiscal_document_pendencies.fiscal_documents_error ?? 0)
  const consistencyProblem =
    (consistency?.settlements_without_movement_count ?? 0) > 0 ||
    (consistency?.settlements_with_multiple_movements ?? 0) > 0 ||
    toNumber(consistency?.difference_amount) !== 0
  const isAnyAccountantExporting = isExporting || exportingBlock !== null
  const blockExportProps = (block: AccountantExportBlock) => ({
    onExport: () => onBlockExport(block),
    isExporting: exportingBlock === block,
    isExportDisabled: isAnyAccountantExporting && exportingBlock !== block,
  })

  return (
    <div className="space-y-5">
      <PanelHeader
        title="Relatorio para contador"
        description="Pacote de conferencia: posicao atual, periodo filtrado, formulas e evidencias exportaveis. Nao substitui fechamento contabil oficial."
        icon={<ListChecks className="h-5 w-5" />}
      >
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onExport("csv")}
            disabled={isExporting}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-black text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} CSV resumo
          </button>
          <button
            type="button"
            onClick={() => onExport("xlsx")}
            disabled={isExporting}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />} XLSX com evidencias
          </button>
        </div>
      </PanelHeader>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Periodo operacional</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">
              {formatDate(report?.period.start_date)} a {formatDate(report?.period.end_date)}
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Data de referencia</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">{formatDate(report?.filters_used.reference_date)}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Empresa</p>
            <p className="mt-1 text-sm font-black text-[var(--color-text)]">{report?.company_display_name ?? "-"}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Snapshot</p>
            <p className="mt-1 text-xs font-semibold text-[var(--color-text-muted)]">
              {report?.snapshot.version ?? "-"} - {formatDateTime(report?.snapshot.generated_at)}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="A receber em aberto"
          value={formatMoney(indicators?.accounts_receivable_open.amount)}
          helper={`${indicators?.accounts_receivable_open.count ?? 0} titulos - posicao atual`}
          icon={<WalletCards className="h-5 w-5" />}
          {...blockExportProps("receivable_open")}
        />
        <MetricCard
          label="A receber vencido"
          value={formatMoney(indicators?.accounts_receivable_overdue.amount)}
          helper={`${indicators?.accounts_receivable_overdue.count ?? 0} titulos - referencia Brasil`}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="warning"
          {...blockExportProps("receivable_overdue")}
        />
        <MetricCard
          label="A pagar em aberto"
          value={formatMoney(indicators?.accounts_payable_open.amount)}
          helper={`${indicators?.accounts_payable_open.count ?? 0} titulos - posicao atual`}
          icon={<FileText className="h-5 w-5" />}
          {...blockExportProps("payable_open")}
        />
        <MetricCard
          label="A pagar vencido"
          value={formatMoney(indicators?.accounts_payable_overdue.amount)}
          helper={`${indicators?.accounts_payable_overdue.count ?? 0} titulos - referencia Brasil`}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone="warning"
          {...blockExportProps("payable_overdue")}
        />
        <MetricCard
          label="Fluxo previsto"
          value={formatMoney(indicators?.cash_flow_projected.net_amount)}
          helper={`${formatMoney(indicators?.cash_flow_projected.inflow_amount)} entrada por vencimento`}
          icon={<BarChart3 className="h-5 w-5" />}
          {...blockExportProps("cash_flow_projected")}
        />
        <MetricCard
          label="Fluxo realizado"
          value={formatMoney(indicators?.cash_flow_realized.net_amount)}
          helper={`${formatMoney(indicators?.cash_flow_realized.inflow_amount)} entrada por baixa`}
          icon={<CheckCircle2 className="h-5 w-5" />}
          {...blockExportProps("cash_flow_realized")}
        />
        <MetricCard
          label="Conciliacao pendente"
          value={String((indicators?.reconciliation_pendencies.unreconciled_movements ?? 0) + (indicators?.reconciliation_pendencies.unmatched_statement_lines ?? 0))}
          helper="movimentos + extratos pendentes/divergentes"
          icon={<ShieldCheck className="h-5 w-5" />}
          tone="warning"
          {...blockExportProps("reconciliation_pendencies")}
        />
        <MetricCard
          label="Pendencias fiscais"
          value={String(totalFiscalPendencies)}
          helper={formatMoney(indicators?.fiscal_document_pendencies.pending_fiscal_open_amount)}
          icon={<ClipboardList className="h-5 w-5" />}
          tone={totalFiscalPendencies > 0 ? "warning" : "success"}
          {...blockExportProps("fiscal_pendencies")}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Baixas sem movimento"
          value={String(consistency?.settlements_without_movement_count ?? 0)}
          helper={formatMoney(consistency?.settlements_without_movement_amount)}
          icon={<XCircle className="h-5 w-5" />}
          tone={(consistency?.settlements_without_movement_count ?? 0) > 0 ? "danger" : "success"}
          {...blockExportProps("settlements_without_movement")}
        />
        <MetricCard
          label="Diferenca baixa x caixa"
          value={formatMoney(consistency?.difference_amount)}
          helper="deve ser R$ 0,00"
          icon={<Gauge className="h-5 w-5" />}
          tone={toNumber(consistency?.difference_amount) !== 0 ? "danger" : "success"}
          {...blockExportProps("settlement_cash_difference")}
        />
        <MetricCard
          label="Orcamentos ignorados"
          value={String(ignored?.sale_quotes_ignored_count ?? 0)}
          helper={`${formatMoney(ignored?.sale_quotes_ignored_amount)} fora de venda realizada`}
          icon={<FileText className="h-5 w-5" />}
          tone="primary"
          {...blockExportProps("ignored_quotes")}
        />
        <MetricCard
          label="Rascunhos ignorados"
          value={String(ignored?.purchase_drafts_ignored_count ?? 0)}
          helper={`${formatMoney(ignored?.purchase_drafts_ignored_amount)} fora de compra confirmada`}
          icon={<ClipboardList className="h-5 w-5" />}
          tone="primary"
          {...blockExportProps("ignored_drafts")}
        />
      </div>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-black text-[var(--color-text)]">Leitura de confiabilidade</h3>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              O XLSX baixa detalhes por aba: titulos, baixas, movimentos, vendas, compras e fiscal. CSV baixa apenas o resumo.
            </p>
          </div>
          <StatusBadge status={consistencyProblem || totalFiscalPendencies > 0 ? "ATTENTION" : "READY"} />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Linhas detalhadas carregadas</p>
            <p className="mt-1 text-xl font-black text-[var(--color-text)]">{detailRows}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Limite por aba</p>
            <p className="mt-1 text-xl font-black text-[var(--color-text)]">{report?.detail_limits.limit ?? 0}</p>
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
            <p className="text-xs font-bold text-[var(--color-text-muted)]">Exportacao completa</p>
            <p className="mt-1 text-xl font-black text-[var(--color-text)]">{report?.detail_limits.export_all ? "Sim" : "Nao"}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <ActionList
          title="Formulas dos indicadores"
          empty="Sem formulas retornadas."
          items={formulas.map(([key, value]) => `${key}: ${value}`)}
          tone="primary"
        />
        <ActionList title="Notas de consistencia" empty="Sem notas retornadas." items={notes} tone="warning" />
      </div>
    </div>
  )
}

// ── RULES PANEL ──────────────────────────────────────────────────────────────

function RulesPanel({ rules }: { rules: ManagementReportRules | null }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        <p className="text-xs font-bold text-[var(--color-text-muted)]">
          {rules?.module ?? "management_reports"} · {rules?.version ?? "—"}
        </p>
        <h2 className="mt-2 text-2xl font-black text-[var(--color-text)]">{rules?.name ?? "Regras do módulo"}</h2>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">
          {rules?.goal ?? "Carregando regras do backend."}
        </p>
      </section>

      <ActionList title="Distinções críticas" empty="Sem regras retornadas." items={rules?.critical_distinctions ?? []} tone="warning" />
      <ActionList title="Garantias do backend" empty="Sem garantias retornadas." items={rules?.backend_guarantees ?? []} tone="primary" />
      <ActionList title="Endpoints consumidos" empty="Sem endpoints retornados." items={rules?.endpoints ?? []} tone="primary" />
    </div>
  )
}
