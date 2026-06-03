import { AlertTriangle, ArrowRightLeft, ArrowUpCircle, CalendarDays, CheckCircle2, CircleDollarSign, Database, FileSpreadsheet, Filter, Landmark, Loader2, RefreshCw, Search, ShieldCheck, TrendingUp, WalletCards, Download } from "lucide-react"
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"

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
  type ExportSheet,
  type ExportTable,
} from "../../lib/exportTable"
import { listFinancialAccounts } from "../financial/financialApi"
import type { FinancialAccount } from "../financial/types"
import { CashFlowForecastPanel } from "../biAnalytics/CashFlowForecastPanel"
import { getCashFlowAccounts, getCashFlowDaily, getCashFlowDiagnostics, getCashFlowOverviewEvidence, getCashFlowPending, getCashFlowReconciliationStatus, getCashFlowSummary, type CashFlowFilters } from "./cashFlowApi"
import type { CashFlowAccountRow, CashFlowDailyRow, CashFlowDiagnostics, CashFlowEvidenceMovement, CashFlowEvidenceStatementLine, CashFlowEvidenceTitle, CashFlowOverviewEvidence, CashFlowPending, CashFlowReconciliationStatus, CashFlowSummary } from "./types"

type Tab = "overview" | "daily" | "accounts" | "pending" | "reconciliation" | "drilldown" | "forecast"
type OverviewExportBlock = "internal_balance" | "expected_inflow" | "expected_outflow" | "overdue" | "operational" | "quality" | "overdue_receivables" | "overdue_payables" | "unreconciled_movements" | "unmatched_statement_lines"
type PendingExportBlock = "all" | "overdue_receivables" | "upcoming_receivables" | "overdue_payables" | "upcoming_payables" | "unreconciled_movements" | "unmatched_statement_lines" | "divergent_matches"
type ReconciliationExportBlock = "all" | "movements" | "statements" | "matches"
type DrillDownFocus = "overdue_titles" | "overdue_payables" | "unreconciled_movements" | "unmatched_statement_lines" | "divergent_matches"
type DrillDownExportTarget = DrillDownFocus | "critical_day"

const ACCOUNT_PAGE_SIZE = 50
const ACCOUNT_PAGE_FETCH_LIMIT = ACCOUNT_PAGE_SIZE + 1

type LoadState = {
  diagnostics: CashFlowDiagnostics | null
  summary: CashFlowSummary | null
  daily: CashFlowDailyRow[]
  accounts: CashFlowAccountRow[]
  pending: CashFlowPending | null
  reconciliation: CashFlowReconciliationStatus | null
  financialAccounts: FinancialAccount[]
}

const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: "overview",       label: "Visão geral",  icon: <WalletCards className="h-4 w-4" /> },
  { id: "daily",          label: "Por dia",       icon: <CalendarDays className="h-4 w-4" /> },
  { id: "accounts",       label: "Por conta",     icon: <Landmark className="h-4 w-4" /> },
  { id: "pending",        label: "Pendências",    icon: <AlertTriangle className="h-4 w-4" /> },
  { id: "reconciliation", label: "Conciliação",   icon: <ArrowRightLeft className="h-4 w-4" /> },
  { id: "drilldown",      label: "Drill-down",    icon: <Search className="h-4 w-4" /> },
  { id: "forecast",       label: "Previsão 13s",  icon: <TrendingUp className="h-4 w-4" /> },
]

function todayIso() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date())
}

function daysAgoIso(days: number) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(date)
}

function formatMoney(value?: string | number | null) {
  const numeric = Number(value ?? 0)
  if (Number.isNaN(numeric)) return "R$ 0,00"
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numeric)
}

function formatDate(value?: string | null) {
  if (!value) return "-"
  const [year, month, day] = value.slice(0, 10).split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function moneyNet(inflow?: string | number | null, outflow?: string | number | null) {
  const result = Number(inflow ?? 0) - Number(outflow ?? 0)
  return Number.isFinite(result) ? result.toFixed(2) : "0.00"
}

function sumMoneyValues<T>(rows: T[], selector: (row: T) => string | number | null | undefined) {
  const total = rows.reduce((acc, row) => {
    const value = Number(selector(row) ?? 0)
    return acc + (Number.isFinite(value) ? value : 0)
  }, 0)
  return total.toFixed(2)
}

function statusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    pending: "Pendente",
    matched: "Conciliado",
    divergent: "Divergente",
    ignored: "Ignorado",
    confirmed: "Confirmado",
    confirmed_with_difference: "Com diferença",
    reversed: "Estornado",
    open: "Aberto",
    overdue: "Vencido",
    partially_received: "Parcial",
    received: "Recebido",
    active: "Ativo",
    posted: "Postado",
  }
  return labels[value ?? ""] ?? value ?? "—"
}

function sumStatusCount(statuses?: Record<string, { count: number }>) {
  return Object.values(statuses ?? {}).reduce((total, item) => total + Number(item.count || 0), 0)
}

function makeFileName(base: string, extension: "csv" | "xlsx") {
  return buildExportFileName("kovir_fluxo_caixa", base, extension)
}

function exportCsv(rows: ExportTable, fileName: string) {
  exportCsvFile(rows, fileName)
}

function exportXlsx(rows: ExportTable, sheetName: string, fileName: string) {
  exportXlsxFile(rows, sheetName, fileName)
}

function exportTable(rows: ExportTable, sheetName: string, fileBaseName: string, format: "csv" | "xlsx") {
  if (rows.length <= 1) return
  if (format === "csv") {
    exportCsv(rows, makeFileName(fileBaseName, "csv"))
    return
  }
  exportXlsx(rows, sheetName, makeFileName(fileBaseName, "xlsx"))
}

function dailyExportRows(rows: CashFlowDailyRow[]): ExportTable {
  return [
    ["Dia", "Entradas previstas", "Saídas previstas", "Recebido em baixas", "Pagamentos", "Entradas realizadas", "Saídas realizadas", "Líquido realizado", "Projeção do dia", "Extrato entrada", "Extrato saída", "Líquido extrato", "Movimentos sem match", "Extratos pendentes", "Pendências totais"],
    ...rows.map((row) => [
      dateCell(row.date),
      moneyCell(row.expected_inflow_amount),
      moneyCell(row.expected_outflow_amount ?? "0.00"),
      moneyCell(row.received_amount),
      moneyCell(row.paid_amount ?? "0.00"),
      moneyCell(row.movement_inflow_amount),
      moneyCell(row.movement_outflow_amount),
      moneyCell(row.realized_net_amount),
      moneyCell(row.projected_net_amount),
      moneyCell(row.statement_inflow_amount),
      moneyCell(row.statement_outflow_amount),
      moneyCell(moneyNet(row.statement_inflow_amount, row.statement_outflow_amount)),
      integerCell(row.unreconciled_movements),
      integerCell(row.pending_statement_lines),
      integerCell(row.unreconciled_movements + row.pending_statement_lines),
    ]),
  ]
}

function accountExportRows(rows: CashFlowAccountRow[]): ExportTable {
  return [
    ["Conta", "Tipo", "Instituição", "Moeda", "Saldo abertura", "Saldo atual", "Entradas no período", "Saídas no período", "Líquido no período", "Movimentos pendentes", "Valor movimentos pendentes", "Movimentos divergentes", "Valor movimentos divergentes", "Movimentos conciliados", "Valor movimentos conciliados", "Extratos pendentes", "Valor extratos pendentes", "Extratos divergentes", "Valor extratos divergentes", "Extratos conciliados", "Valor extratos conciliados", "Extrato entrada", "Extrato saída", "Status"],
    ...rows.map((row) => [
      row.financial_account_name,
      row.account_type,
      row.institution_name ?? "",
      row.currency,
      moneyCell(row.opening_balance_amount),
      moneyCell(row.current_balance_amount),
      moneyCell(row.period_inflow_amount),
      moneyCell(row.period_outflow_amount),
      moneyCell(row.period_net_amount),
      integerCell(row.reconciliation_by_status.pending?.count ?? 0),
      moneyCell(row.reconciliation_by_status.pending?.amount),
      integerCell(row.reconciliation_by_status.divergent?.count ?? 0),
      moneyCell(row.reconciliation_by_status.divergent?.amount),
      integerCell(row.reconciliation_by_status.matched?.count ?? 0),
      moneyCell(row.reconciliation_by_status.matched?.amount),
      integerCell(row.statement_by_status.pending?.count ?? 0),
      moneyCell(row.statement_by_status.pending?.amount),
      integerCell(row.statement_by_status.divergent?.count ?? 0),
      moneyCell(row.statement_by_status.divergent?.amount),
      integerCell(row.statement_by_status.matched?.count ?? 0),
      moneyCell(row.statement_by_status.matched?.amount),
      moneyCell(row.statement_by_direction.inflow),
      moneyCell(row.statement_by_direction.outflow),
      statusLabel(row.status),
    ]),
  ]
}

function pendingExportRows(pending: CashFlowPending | null): ExportTable {
  const rows: ExportTable = [["Grupo", "ID", "Data", "Direção", "Valor", "Status", "Origem/Referência", "Descrição"]]
  for (const item of pending?.overdue_titles ?? []) rows.push(["Títulos vencidos", item.id, dateCell(item.due_date), "inflow", moneyCell(item.open_amount), statusLabel(item.status), item.source_type, item.document_reference ?? ""])
  for (const item of pending?.upcoming_titles ?? []) rows.push(["Títulos previstos", item.id, dateCell(item.due_date), "inflow", moneyCell(item.open_amount), statusLabel(item.status), item.source_type, item.document_reference ?? ""])
  for (const item of pending?.overdue_payables ?? []) rows.push(["Contas a pagar vencidas", item.id, dateCell(item.due_date), "outflow", moneyCell(item.open_amount), statusLabel(item.status), item.source_type, item.document_reference ?? ""])
  for (const item of pending?.upcoming_payables ?? []) rows.push(["Contas a pagar previstas", item.id, dateCell(item.due_date), "outflow", moneyCell(item.open_amount), statusLabel(item.status), item.source_type, item.document_reference ?? ""])
  for (const item of pending?.unreconciled_movements ?? []) rows.push(["Movimentos sem match", item.id, dateCell(item.movement_date), item.direction, moneyCell(item.amount), statusLabel(item.reconciliation_status), item.source_type, item.description ?? ""])
  for (const item of pending?.unmatched_statement_lines ?? []) rows.push(["Extratos sem match", item.id, dateCell(item.line_date), item.direction, moneyCell(item.amount), statusLabel(item.status), item.bank_reference ?? "", item.description ?? ""])
  for (const item of pending?.divergent_matches ?? []) rows.push(["Matches divergentes", item.id, dateCell(item.created_at), "", moneyCell(item.difference_amount), "Divergente", item.financial_movement_id, item.confirmation_reason ?? ""])
  return rows
}

function reconciliationExportRows(data: CashFlowReconciliationStatus | null): ExportTable {
  const rows: ExportTable = [["Bloco", "Status", "Quantidade", "Valor", "Diferença"]]
  for (const [status, value] of Object.entries(data?.financial_movements ?? {})) rows.push(["Movimentos internos", statusLabel(status), integerCell(value.count), moneyCell(value.amount), ""])
  for (const [status, value] of Object.entries(data?.statement_lines ?? {})) rows.push(["Linhas de extrato", statusLabel(status), integerCell(value.count), moneyCell(value.amount), ""])
  for (const [status, value] of Object.entries(data?.matches ?? {})) rows.push(["Matches", statusLabel(status), integerCell(value.count), "", moneyCell(value.difference_amount)])
  return rows
}

function reconciliationBlockFileBase(block: ReconciliationExportBlock) {
  const names: Record<ReconciliationExportBlock, string> = {
    all: "conciliacao_todos",
    movements: "conciliacao_movimentos_internos",
    statements: "conciliacao_extratos_bancarios",
    matches: "conciliacao_matches_divergentes",
  }
  return names[block]
}

function overviewBlockLabel(block: OverviewExportBlock) {
  const labels: Record<OverviewExportBlock, string> = {
    internal_balance: "Saldo interno",
    expected_inflow: "Entradas previstas",
    expected_outflow: "Saídas previstas",
    overdue: "Titulos vencidos",
    operational: "Leitura operacional",
    quality: "Alertas de qualidade",
    overdue_receivables: "Recebiveis vencidos",
    overdue_payables: "A pagar vencidos",
    unreconciled_movements: "Movimentos sem match",
    unmatched_statement_lines: "Extratos pendentes",
  }
  return labels[block]
}

function overviewBlockFileBase(block: OverviewExportBlock) {
  const names: Record<OverviewExportBlock, string> = {
    internal_balance: "visao_geral_saldo_interno",
    expected_inflow: "visao_geral_entradas_previstas",
    expected_outflow: "visao_geral_saidas_previstas",
    overdue: "visao_geral_titulos_vencidos",
    operational: "visao_geral_leitura_operacional",
    quality: "visao_geral_alertas_qualidade",
    overdue_receivables: "visao_geral_recebiveis_vencidos",
    overdue_payables: "visao_geral_pagar_vencidos",
    unreconciled_movements: "visao_geral_movimentos_sem_match",
    unmatched_statement_lines: "visao_geral_extratos_pendentes",
  }
  return names[block]
}

function overviewSummaryRows(summary: CashFlowSummary | null, evidence: CashFlowOverviewEvidence, block: OverviewExportBlock): ExportTable {
  return [
    ["Campo", "Valor"],
    ["Bloco", overviewBlockLabel(block)],
    ["Empresa ID", evidence.company_id],
    ["Periodo inicial", dateCell(evidence.start_date)],
    ["Periodo final", dateCell(evidence.end_date)],
    ["Data de referencia", dateCell(evidence.reference_date)],
    ["Conta financeira", evidence.financial_account_id ?? "Todas"],
    [],
    ["Indicador", "Valor"],
    ["Saldo interno atual", moneyCell(summary?.internal_balance_total)],
    ["Entradas previstas", moneyCell(summary?.expected_inflow_amount)],
    ["Saídas previstas", moneyCell(summary?.expected_outflow_amount)],
    ["Recebiveis vencidos", moneyCell(summary?.overdue_receivable_amount)],
    ["A pagar vencidos", moneyCell(summary?.overdue_payable_amount)],
    ["Recebido em baixas", moneyCell(summary?.received_amount)],
    ["Pago em baixas", moneyCell(summary?.paid_amount)],
    ["Entradas realizadas no caixa", moneyCell(summary?.realized_inflow_amount)],
    ["Saidas realizadas no caixa", moneyCell(summary?.realized_outflow_amount)],
    ["Linhas de extrato pendentes", integerCell(summary?.pending_statement_lines)],
    ["Linhas de extrato divergentes", integerCell(summary?.divergent_statement_lines)],
    ["Movimentos pendentes", integerCell(summary?.pending_reconciliation_count)],
    ["Movimentos divergentes", integerCell(summary?.divergent_reconciliation_count)],
  ]
}

function evidenceAccountRows(evidence: CashFlowOverviewEvidence): ExportTable {
  return [
    ["Conta", "Tipo", "Instituicao", "Moeda", "Saldo abertura", "Saldo atual", "Ultima atualizacao", "Status"],
    ...evidence.account_balances.map((row) => [
      row.financial_account_name,
      row.account_type,
      row.institution_name ?? "",
      row.currency,
      moneyCell(row.opening_balance_amount),
      moneyCell(row.current_balance_amount),
      dateTimeCell(row.last_balance_update),
      statusLabel(row.status),
    ]),
  ]
}

function evidenceTitleRows(title: string, rows: CashFlowEvidenceTitle[]): ExportTable {
  return [
    [title],
    [],
    ["ID", "Direção", "Participante", "Documento participante", "Conta prevista", "Documento", "Emissao", "Competencia", "Vencimento", "Pagamento previsto", "Parcela", "Valor bruto", "Valor liquido", "Valor pago", "Valor aberto", "Status", "Cobranca", "Origem"],
    ...rows.map((row) => [
      row.id,
      row.direction,
      row.participant_name ?? "",
      row.participant_document ?? "",
      row.financial_account_name ?? "",
      row.document_reference ?? "",
      dateCell(row.issue_date),
      dateCell(row.competency_date),
      dateCell(row.due_date),
      dateCell(row.expected_payment_date),
      `${row.installment_number}/${row.installment_total}`,
      moneyCell(row.gross_amount),
      moneyCell(row.net_amount),
      moneyCell(row.paid_amount),
      moneyCell(row.open_amount),
      statusLabel(row.status),
      statusLabel(row.collection_status),
      `${row.source_type ?? ""}:${row.source_id ?? ""}`,
    ]),
  ]
}

function evidenceSettlementRows(rows: CashFlowOverviewEvidence["settlements"]): ExportTable {
  return [
    ["Baixas do periodo"],
    [],
    ["ID", "Direção", "Tipo", "Status", "Data baixa", "Competencia", "Titulo", "Referencia titulo", "Participante", "Conta", "Valor recebido/pago", "Desconto", "Juros", "Multa", "Taxa", "Valor liquidado", "Valor movimentado", "Evidencia", "Origem"],
    ...rows.map((row) => [
      row.id,
      row.direction,
      row.settlement_type,
      statusLabel(row.status),
      dateCell(row.settlement_date),
      dateCell(row.competency_date),
      row.financial_title_id,
      row.title_reference ?? "",
      row.participant_name ?? "",
      row.financial_account_name ?? "",
      moneyCell(row.received_amount),
      moneyCell(row.discount_amount),
      moneyCell(row.interest_amount),
      moneyCell(row.penalty_amount),
      moneyCell(row.fee_amount),
      moneyCell(row.title_settled_amount),
      moneyCell(row.movement_amount),
      row.evidence_reference ?? "",
      `${row.source_type ?? ""}:${row.source_id ?? ""}`,
    ]),
  ]
}

function evidenceMovementRows(title: string, rows: CashFlowEvidenceMovement[]): ExportTable {
  return [
    [title],
    [],
    ["ID", "Conta", "Direção", "Tipo", "Data", "Valor", "Moeda", "Status", "Conciliacao", "Baixa", "Titulo", "Referencia titulo", "Participante", "Origem", "Descrição"],
    ...rows.map((row) => [
      row.id,
      row.financial_account_name ?? row.financial_account_id,
      row.direction,
      row.movement_type,
      dateCell(row.movement_date),
      moneyCell(row.amount),
      row.currency,
      statusLabel(row.status),
      statusLabel(row.reconciliation_status),
      row.settlement_id ?? "",
      row.financial_title_id ?? "",
      row.title_reference ?? "",
      row.participant_name ?? "",
      `${row.source_type ?? ""}:${row.source_id ?? ""}`,
      row.description ?? "",
    ]),
  ]
}

function evidenceStatementRows(title: string, rows: CashFlowEvidenceStatementLine[]): ExportTable {
  return [
    [title],
    [],
    ["ID", "Conta", "Importacao", "ID externo", "Data linha", "Data postagem", "Direção", "Valor", "Status", "Confianca match", "Valor conciliado", "Documento", "Contraparte", "Documento contraparte", "Referencia bancaria", "Descrição"],
    ...rows.map((row) => [
      row.id,
      row.financial_account_name ?? row.financial_account_id,
      row.statement_import_id ?? "",
      row.external_id ?? "",
      dateCell(row.line_date),
      dateTimeCell(row.posted_at),
      row.direction,
      moneyCell(row.amount),
      statusLabel(row.status),
      row.match_confidence ?? "",
      moneyCell(row.matched_amount),
      row.document_number ?? "",
      row.counterparty_name ?? "",
      row.counterparty_document ?? "",
      row.bank_reference ?? "",
      row.description ?? "",
    ]),
  ]
}

function evidenceDivergentRows(evidence: CashFlowOverviewEvidence): ExportTable {
  return [
    ["Matches divergentes"],
    [],
    ["ID", "Conta", "Linha extrato", "Movimento", "Valor match", "Valor extrato", "Valor movimento", "Diferenca", "Tolerancia", "Status", "Justificativa", "Criado em"],
    ...evidence.divergent_matches.map((row) => [
      row.id,
      row.financial_account_id,
      row.statement_line_id,
      row.financial_movement_id,
      moneyCell(row.matched_amount),
      moneyCell(row.line_amount),
      moneyCell(row.movement_amount),
      moneyCell(row.difference_amount),
      moneyCell(row.tolerance_amount),
      statusLabel(row.status),
      row.confirmation_reason ?? "",
      dateTimeCell(row.created_at),
    ]),
  ]
}

function evidenceMatchRows(title: string, rows: CashFlowOverviewEvidence["matches"]): ExportTable {
  return [
    [title],
    [],
    ["ID", "Conta", "Linha extrato", "Movimento", "Valor match", "Valor extrato", "Valor movimento", "Diferenca", "Tolerancia", "Status", "Justificativa", "Criado em"],
    ...rows.map((row) => [
      row.id,
      row.financial_account_id,
      row.statement_line_id,
      row.financial_movement_id,
      moneyCell(row.matched_amount),
      moneyCell(row.line_amount),
      moneyCell(row.movement_amount),
      moneyCell(row.difference_amount),
      moneyCell(row.tolerance_amount),
      statusLabel(row.status),
      row.confirmation_reason ?? "",
      dateTimeCell(row.created_at),
    ]),
  ]
}

function overviewEvidenceSheets(summary: CashFlowSummary | null, evidence: CashFlowOverviewEvidence, block: OverviewExportBlock): ExportSheet[] {
  const summarySheet = { name: "Resumo", rows: overviewSummaryRows(summary, evidence, block) }
  const pendingMovements = evidence.movements.filter((row) => row.reconciliation_status === "pending" || row.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((row) => row.status === "pending" || row.status === "divergent")

  if (block === "internal_balance") return [summarySheet, { name: "Contas", rows: evidenceAccountRows(evidence) }]
  if (block === "expected_inflow") return [summarySheet, { name: "Titulos", rows: evidenceTitleRows("Entradas previstas por vencimento", evidence.expected_receivable_titles) }]
  if (block === "expected_outflow") return [summarySheet, { name: "Titulos", rows: evidenceTitleRows("Saídas previstas por vencimento", evidence.expected_payable_titles) }]
  if (block === "overdue") {
    return [
      summarySheet,
      { name: "Recebiveis vencidos", rows: evidenceTitleRows("Recebiveis vencidos - posicao atual", evidence.overdue_receivable_titles) },
      { name: "A pagar vencidos", rows: evidenceTitleRows("A pagar vencidos - posicao atual", evidence.overdue_payable_titles) },
    ]
  }
  if (block === "operational") {
    return [
      summarySheet,
      { name: "Baixas", rows: evidenceSettlementRows(evidence.settlements) },
      { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos do periodo", evidence.movements) },
      { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato do periodo", evidence.statement_lines) },
    ]
  }
  if (block === "quality") {
    return [
      summarySheet,
      { name: "Movimentos pendentes", rows: evidenceMovementRows("Movimentos pendentes ou divergentes", pendingMovements) },
      { name: "Extratos pendentes", rows: evidenceStatementRows("Extratos pendentes ou divergentes", pendingStatements) },
      { name: "Matches divergentes", rows: evidenceDivergentRows(evidence) },
    ]
  }
  if (block === "overdue_receivables") return [summarySheet, { name: "Recebiveis", rows: evidenceTitleRows("Recebiveis vencidos - posicao atual", evidence.overdue_receivable_titles) }]
  if (block === "overdue_payables") return [summarySheet, { name: "A pagar", rows: evidenceTitleRows("A pagar vencidos - posicao atual", evidence.overdue_payable_titles) }]
  if (block === "unreconciled_movements") return [summarySheet, { name: "Movimentos", rows: evidenceMovementRows("Movimentos pendentes ou divergentes", pendingMovements) }]
  return [summarySheet, { name: "Extratos", rows: evidenceStatementRows("Extratos pendentes ou divergentes", pendingStatements) }]
}

function dailySummaryRows(row: CashFlowDailyRow, evidence: CashFlowOverviewEvidence): ExportTable {
  return [
    ["Campo", "Valor"],
    ["Empresa ID", evidence.company_id],
    ["Dia", dateCell(row.date)],
    ["Conta financeira", evidence.financial_account_id ?? "Todas"],
    [],
    ["Indicador", "Valor"],
    ["Entradas previstas por vencimento", moneyCell(row.expected_inflow_amount)],
    ["Quantidade de recebíveis previstos", integerCell(row.expected_inflow_count)],
    ["Saídas previstas por vencimento", moneyCell(row.expected_outflow_amount ?? "0.00")],
    ["Quantidade de contas a pagar previstas", integerCell(row.expected_outflow_count ?? 0)],
    ["Recebido em baixas", moneyCell(row.received_amount)],
    ["Pago em baixas", moneyCell(row.paid_amount ?? "0.00")],
    ["Entradas realizadas no caixa interno", moneyCell(row.movement_inflow_amount)],
    ["Saídas realizadas no caixa interno", moneyCell(row.movement_outflow_amount)],
    ["Líquido realizado no caixa interno", moneyCell(row.realized_net_amount)],
    ["Projeção do dia", moneyCell(row.projected_net_amount)],
    ["Extrato externo - entrada", moneyCell(row.statement_inflow_amount)],
    ["Extrato externo - saída", moneyCell(row.statement_outflow_amount)],
    ["Extrato externo - líquido", moneyCell(moneyNet(row.statement_inflow_amount, row.statement_outflow_amount))],
    ["Movimentos internos sem match/divergentes", integerCell(row.unreconciled_movements)],
    ["Extratos pendentes/divergentes", integerCell(row.pending_statement_lines)],
    ["Pendências totais", integerCell(row.unreconciled_movements + row.pending_statement_lines)],
  ]
}

function dailyEvidenceSheets(row: CashFlowDailyRow, evidence: CashFlowOverviewEvidence): ExportSheet[] {
  const expectedReceivables = evidence.expected_receivable_titles.filter((item) => item.due_date === row.date)
  const expectedPayables = evidence.expected_payable_titles.filter((item) => item.due_date === row.date)
  const settlements = evidence.settlements.filter((item) => item.settlement_date === row.date)
  const movements = evidence.movements.filter((item) => item.movement_date === row.date)
  const statements = evidence.statement_lines.filter((item) => item.line_date === row.date)
  const pendingMovements = movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = statements.filter((item) => item.status === "pending" || item.status === "divergent")

  return [
    { name: "Resumo", rows: dailySummaryRows(row, evidence) },
    { name: "Entradas previstas", rows: evidenceTitleRows("Recebíveis previstos por vencimento no dia", expectedReceivables) },
    { name: "Saídas previstas", rows: evidenceTitleRows("Contas a pagar previstas por vencimento no dia", expectedPayables) },
    { name: "Baixas", rows: evidenceSettlementRows(settlements) },
    { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos do dia", movements) },
    { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato do dia", statements) },
    { name: "Pendências", rows: [
      ["Grupo", "ID", "Data", "Direção", "Valor", "Status", "Referência", "Descrição"],
      ...pendingMovements.map((item) => ["Movimento interno", item.id, dateCell(item.movement_date), item.direction, moneyCell(item.amount), statusLabel(item.reconciliation_status), item.source_type, item.description ?? ""]),
      ...pendingStatements.map((item) => ["Extrato bancário", item.id, dateCell(item.line_date), item.direction, moneyCell(item.amount), statusLabel(item.status), item.bank_reference ?? "", item.description ?? ""]),
    ] },
  ]
}

function statusAmountRows(title: string, statuses: Record<string, { count: number; amount?: string; difference_amount?: string }>): ExportTable {
  return [
    [title, "Quantidade", "Valor"],
    ...Object.entries(statuses).map(([status, value]) => [
      statusLabel(status),
      integerCell(value.count),
      moneyCell(value.amount ?? value.difference_amount ?? "0.00"),
    ]),
  ]
}

function accountSummaryRows(row: CashFlowAccountRow, evidence: CashFlowOverviewEvidence): ExportTable {
  return [
    ["Campo", "Valor"],
    ["Empresa ID", evidence.company_id],
    ["Período inicial", dateCell(evidence.start_date)],
    ["Período final", dateCell(evidence.end_date)],
    ["Data de referência", dateCell(evidence.reference_date)],
    ["Conta ID", row.financial_account_id],
    ["Conta", row.financial_account_name],
    ["Tipo", row.account_type],
    ["Instituição", row.institution_name ?? ""],
    ["Moeda", row.currency],
    ["Status", statusLabel(row.status)],
    [],
    ["Indicador", "Valor"],
    ["Saldo de abertura", moneyCell(row.opening_balance_amount)],
    ["Saldo atual materializado", moneyCell(row.current_balance_amount)],
    ["Entradas no período", moneyCell(row.period_inflow_amount)],
    ["Saídas no período", moneyCell(row.period_outflow_amount)],
    ["Líquido no período", moneyCell(row.period_net_amount)],
    ["Extrato externo - entrada", moneyCell(row.statement_by_direction.inflow)],
    ["Extrato externo - saída", moneyCell(row.statement_by_direction.outflow)],
    ["Extrato externo - líquido", moneyCell(moneyNet(row.statement_by_direction.inflow, row.statement_by_direction.outflow))],
    [],
    ...statusAmountRows("Movimentos internos por status", row.reconciliation_by_status),
    [],
    ...statusAmountRows("Extratos bancários por status", row.statement_by_status),
  ]
}

function accountPendingRows(evidence: CashFlowOverviewEvidence): ExportTable {
  const pendingMovements = evidence.movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((item) => item.status === "pending" || item.status === "divergent")
  return [
    ["Grupo", "ID", "Data", "Direção", "Valor", "Status", "Referência", "Descrição"],
    ...pendingMovements.map((item) => ["Movimento interno", item.id, dateCell(item.movement_date), item.direction, moneyCell(item.amount), statusLabel(item.reconciliation_status), item.source_type, item.description ?? ""]),
    ...pendingStatements.map((item) => ["Extrato bancário", item.id, dateCell(item.line_date), item.direction, moneyCell(item.amount), statusLabel(item.status), item.bank_reference ?? "", item.description ?? ""]),
    ...evidence.divergent_matches.map((item) => ["Match divergente", item.id, dateTimeCell(item.created_at), "", moneyCell(item.difference_amount), statusLabel(item.status), item.financial_movement_id, item.confirmation_reason ?? ""]),
  ]
}

function accountEvidenceSheets(row: CashFlowAccountRow, evidence: CashFlowOverviewEvidence): ExportSheet[] {
  return [
    { name: "Resumo da conta", rows: accountSummaryRows(row, evidence) },
    { name: "Baixas", rows: evidenceSettlementRows(evidence.settlements) },
    { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos da conta no período", evidence.movements) },
    { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato da conta no período", evidence.statement_lines) },
    { name: "Pendências", rows: accountPendingRows(evidence) },
  ]
}

function pendingBlockLabel(block: PendingExportBlock) {
  const labels: Record<PendingExportBlock, string> = {
    all: "Todas as pendências",
    overdue_receivables: "Títulos a receber vencidos",
    upcoming_receivables: "Títulos a receber previstos",
    overdue_payables: "Contas a pagar vencidas",
    upcoming_payables: "Contas a pagar previstas",
    unreconciled_movements: "Movimentos sem conciliação",
    unmatched_statement_lines: "Extratos sem match",
    divergent_matches: "Matches com diferença",
  }
  return labels[block]
}

function pendingBlockFileBase(block: PendingExportBlock) {
  const names: Record<PendingExportBlock, string> = {
    all: "pendencias_todas",
    overdue_receivables: "pendencias_receber_vencidos",
    upcoming_receivables: "pendencias_receber_previstos",
    overdue_payables: "pendencias_pagar_vencidos",
    upcoming_payables: "pendencias_pagar_previstas",
    unreconciled_movements: "pendencias_movimentos_sem_conciliacao",
    unmatched_statement_lines: "pendencias_extratos_sem_match",
    divergent_matches: "pendencias_matches_com_diferenca",
  }
  return names[block]
}

function pendingSummaryRows(evidence: CashFlowOverviewEvidence, block: PendingExportBlock): ExportTable {
  const pendingMovements = evidence.movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((item) => item.status === "pending" || item.status === "divergent")
  return [
    ["Campo", "Valor"],
    ["Bloco", pendingBlockLabel(block)],
    ["Empresa ID", evidence.company_id],
    ["Período inicial", dateCell(evidence.start_date)],
    ["Período final", dateCell(evidence.end_date)],
    ["Data de referência", dateCell(evidence.reference_date)],
    ["Conta financeira", evidence.financial_account_id ?? "Todas"],
    [],
    ["Grupo", "Quantidade", "Valor"],
    ["Títulos a receber vencidos", integerCell(evidence.overdue_receivable_titles.length), moneyCell(sumMoneyValues(evidence.overdue_receivable_titles, (item) => item.open_amount))],
    ["Títulos a receber previstos", integerCell(evidence.expected_receivable_titles.length), moneyCell(sumMoneyValues(evidence.expected_receivable_titles, (item) => item.open_amount))],
    ["Contas a pagar vencidas", integerCell(evidence.overdue_payable_titles.length), moneyCell(sumMoneyValues(evidence.overdue_payable_titles, (item) => item.open_amount))],
    ["Contas a pagar previstas", integerCell(evidence.expected_payable_titles.length), moneyCell(sumMoneyValues(evidence.expected_payable_titles, (item) => item.open_amount))],
    ["Movimentos sem conciliação", integerCell(pendingMovements.length), moneyCell(sumMoneyValues(pendingMovements, (item) => item.amount))],
    ["Extratos sem match", integerCell(pendingStatements.length), moneyCell(sumMoneyValues(pendingStatements, (item) => item.amount))],
    ["Matches com diferença", integerCell(evidence.divergent_matches.length), moneyCell(sumMoneyValues(evidence.divergent_matches, (item) => item.difference_amount))],
  ]
}

function pendingEvidenceSheets(evidence: CashFlowOverviewEvidence, block: PendingExportBlock): ExportSheet[] {
  const summarySheet = { name: "Resumo", rows: pendingSummaryRows(evidence, block) }
  const pendingMovements = evidence.movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((item) => item.status === "pending" || item.status === "divergent")

  const sheets: Record<Exclude<PendingExportBlock, "all">, ExportSheet> = {
    overdue_receivables: { name: "Receber vencidos", rows: evidenceTitleRows("Títulos a receber vencidos", evidence.overdue_receivable_titles) },
    upcoming_receivables: { name: "Receber previstos", rows: evidenceTitleRows("Títulos a receber previstos por vencimento", evidence.expected_receivable_titles) },
    overdue_payables: { name: "Pagar vencidos", rows: evidenceTitleRows("Contas a pagar vencidas", evidence.overdue_payable_titles) },
    upcoming_payables: { name: "Pagar previstas", rows: evidenceTitleRows("Contas a pagar previstas por vencimento", evidence.expected_payable_titles) },
    unreconciled_movements: { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos pendentes ou divergentes", pendingMovements) },
    unmatched_statement_lines: { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato pendentes ou divergentes", pendingStatements) },
    divergent_matches: { name: "Matches", rows: evidenceDivergentRows(evidence) },
  }

  if (block !== "all") return [summarySheet, sheets[block]]
  return [
    summarySheet,
    sheets.overdue_receivables,
    sheets.upcoming_receivables,
    sheets.overdue_payables,
    sheets.upcoming_payables,
    sheets.unreconciled_movements,
    sheets.unmatched_statement_lines,
    sheets.divergent_matches,
  ]
}

function reconciliationSummaryRows(data: CashFlowReconciliationStatus | null, evidence: CashFlowOverviewEvidence, block: ReconciliationExportBlock): ExportTable {
  const blockLabel = {
    all: "Conciliação completa",
    movements: "Movimentos internos",
    statements: "Linhas de extrato",
    matches: "Matches com diferença",
  }[block]

  return [
    ["Campo", "Valor"],
    ["Bloco", blockLabel],
    ["Empresa ID", evidence.company_id],
    ["Período inicial", dateCell(evidence.start_date)],
    ["Período final", dateCell(evidence.end_date)],
    ["Data de referência", dateCell(evidence.reference_date)],
    ["Conta financeira", evidence.financial_account_id ?? "Todas"],
    [],
    ["Grupo", "Status", "Quantidade", "Valor", "Diferença"],
    ...Object.entries(data?.financial_movements ?? {}).map(([status, value]) => ["Movimentos internos", statusLabel(status), integerCell(value.count), moneyCell(value.amount), ""]),
    ...Object.entries(data?.statement_lines ?? {}).map(([status, value]) => ["Linhas de extrato", statusLabel(status), integerCell(value.count), moneyCell(value.amount), ""]),
    ...Object.entries(data?.matches ?? {}).map(([status, value]) => ["Matches", statusLabel(status), integerCell(value.count), "", moneyCell(value.difference_amount)]),
  ]
}

function reconciliationEvidenceSheets(data: CashFlowReconciliationStatus | null, evidence: CashFlowOverviewEvidence, block: ReconciliationExportBlock): ExportSheet[] {
  const summarySheet = { name: "Resumo", rows: reconciliationSummaryRows(data, evidence, block) }
  const sheets: Record<Exclude<ReconciliationExportBlock, "all">, ExportSheet> = {
    movements: { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos do periodo", evidence.movements) },
    statements: { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato do periodo", evidence.statement_lines) },
    matches: { name: "Matches", rows: evidenceMatchRows("Matches de conciliacao do periodo", evidence.matches ?? []) },
  }

  if (block !== "all") return [summarySheet, sheets[block]]
  return [summarySheet, sheets.movements, sheets.statements, sheets.matches]
}

function drillDownFocusLabel(focus: DrillDownFocus) {
  const labels: Record<DrillDownFocus, string> = {
    overdue_titles: "Títulos a receber vencidos",
    overdue_payables: "Títulos a pagar vencidos",
    unreconciled_movements: "Movimentos sem conciliação",
    unmatched_statement_lines: "Linhas de extrato sem match",
    divergent_matches: "Matches com diferença",
  }
  return labels[focus]
}

function drillDownFocusFileBase(focus: DrillDownFocus) {
  const names: Record<DrillDownFocus, string> = {
    overdue_titles: "drilldown_receber_vencidos",
    overdue_payables: "drilldown_pagar_vencidos",
    unreconciled_movements: "drilldown_movimentos_sem_conciliacao",
    unmatched_statement_lines: "drilldown_extratos_sem_match",
    divergent_matches: "drilldown_matches_com_diferenca",
  }
  return names[focus]
}

function drillDownFocusSummaryRows(evidence: CashFlowOverviewEvidence, focus: DrillDownFocus): ExportTable {
  const pendingMovements = evidence.movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((item) => item.status === "pending" || item.status === "divergent")
  const totals: Record<DrillDownFocus, { count: number; amount: string }> = {
    overdue_titles: { count: evidence.overdue_receivable_titles.length, amount: sumMoneyValues(evidence.overdue_receivable_titles, (item) => item.open_amount) },
    overdue_payables: { count: evidence.overdue_payable_titles.length, amount: sumMoneyValues(evidence.overdue_payable_titles, (item) => item.open_amount) },
    unreconciled_movements: { count: pendingMovements.length, amount: sumMoneyValues(pendingMovements, (item) => item.amount) },
    unmatched_statement_lines: { count: pendingStatements.length, amount: sumMoneyValues(pendingStatements, (item) => item.amount) },
    divergent_matches: { count: evidence.divergent_matches.length, amount: sumMoneyValues(evidence.divergent_matches, (item) => item.difference_amount) },
  }

  return [
    ["Campo", "Valor"],
    ["Foco", drillDownFocusLabel(focus)],
    ["Empresa ID", evidence.company_id],
    ["Período inicial", dateCell(evidence.start_date)],
    ["Período final", dateCell(evidence.end_date)],
    ["Data de referência", dateCell(evidence.reference_date)],
    ["Conta financeira", evidence.financial_account_id ?? "Todas"],
    [],
    ["Indicador", "Valor"],
    ["Quantidade completa exportada", integerCell(totals[focus].count)],
    ["Valor completo exportado", moneyCell(totals[focus].amount)],
    ["Observação", "A tela exibe uma amostra limitada; este XLSX usa evidências completas até 5000 registros."],
  ]
}

function drillDownEvidenceSheets(evidence: CashFlowOverviewEvidence, focus: DrillDownFocus): ExportSheet[] {
  const pendingMovements = evidence.movements.filter((item) => item.reconciliation_status === "pending" || item.reconciliation_status === "divergent")
  const pendingStatements = evidence.statement_lines.filter((item) => item.status === "pending" || item.status === "divergent")
  const sheets: Record<DrillDownFocus, ExportSheet> = {
    overdue_titles: { name: "Receber vencidos", rows: evidenceTitleRows("Títulos a receber vencidos - posição atual", evidence.overdue_receivable_titles) },
    overdue_payables: { name: "Pagar vencidos", rows: evidenceTitleRows("Títulos a pagar vencidos - posição atual", evidence.overdue_payable_titles) },
    unreconciled_movements: { name: "Movimentos", rows: evidenceMovementRows("Movimentos internos pendentes ou divergentes", pendingMovements) },
    unmatched_statement_lines: { name: "Extratos", rows: evidenceStatementRows("Linhas de extrato pendentes ou divergentes", pendingStatements) },
    divergent_matches: { name: "Matches", rows: evidenceDivergentRows(evidence) },
  }
  return [{ name: "Resumo", rows: drillDownFocusSummaryRows(evidence, focus) }, sheets[focus]]
}

export function CashFlowPage() {
  const { companyId, activeCompanyName, isCompanyLoading, isCompanyResolved, companyError, reloadCompanies } = useActiveCompany()
  const [activeTab, setActiveTab] = useState<Tab>("overview")
  const [startDate, setStartDate] = useState(() => daysAgoIso(30))
  const [endDate, setEndDate] = useState(() => todayIso())
  const [financialAccountId, setFinancialAccountId] = useState("")
  const [state, setState] = useState<LoadState>({
    diagnostics: null,
    summary: null,
    daily: [],
    accounts: [],
    pending: null,
    reconciliation: null,
    financialAccounts: [],
  })
  const [isLoading, setIsLoading] = useState(false)
  const [exportingOverviewBlock, setExportingOverviewBlock] = useState<OverviewExportBlock | null>(null)
  const [exportingDailyDate, setExportingDailyDate] = useState<string | null>(null)
  const [exportingAccountId, setExportingAccountId] = useState<string | null>(null)
  const [exportingPendingBlock, setExportingPendingBlock] = useState<PendingExportBlock | null>(null)
  const [exportingReconciliationBlock, setExportingReconciliationBlock] = useState<ReconciliationExportBlock | null>(null)
  const [exportingDrillDownTarget, setExportingDrillDownTarget] = useState<DrillDownExportTarget | null>(null)
  const [accountsPage, setAccountsPage] = useState(0)
  const [hasNextAccountsPage, setHasNextAccountsPage] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const filters = useMemo<CashFlowFilters>(() => ({
    start_date: startDate,
    end_date: endDate,
    financial_account_id: financialAccountId || undefined,
  }), [startDate, endDate, financialAccountId])

  const load = useCallback(async () => {
    if (!companyId) return
    setIsLoading(true)
    setError(null)
    try {
      const [diagnostics, summary, daily, accounts, pending, reconciliation, financialAccounts] = await Promise.all([
        getCashFlowDiagnostics(),
        getCashFlowSummary(companyId, filters),
        getCashFlowDaily(companyId, filters),
        getCashFlowAccounts(companyId, { ...filters, limit: ACCOUNT_PAGE_FETCH_LIMIT, offset: accountsPage * ACCOUNT_PAGE_SIZE }),
        getCashFlowPending(companyId, { ...filters, limit: "100" }),
        getCashFlowReconciliationStatus(companyId, filters),
        listFinancialAccounts(companyId, { status: "active", limit: 200, offset: 0 }),
      ])
      setState({
        diagnostics: diagnostics.data,
        summary: summary.data,
        daily: daily.data,
        accounts: accounts.data.slice(0, ACCOUNT_PAGE_SIZE),
        pending: pending.data,
        reconciliation: reconciliation.data,
        financialAccounts: financialAccounts.data,
      })
      setHasNextAccountsPage(accounts.data.length > ACCOUNT_PAGE_SIZE)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar fluxo de caixa.")
    } finally {
      setIsLoading(false)
    }
  }, [accountsPage, companyId, filters])

  useEffect(() => {
    void load()
  }, [load])

  async function handleOverviewExport(block: OverviewExportBlock) {
    if (!companyId) return
    setExportingOverviewBlock(block)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, { ...filters, limit: "5000" })
      const evidence = response.data
      const fileName = makeFileName(overviewBlockFileBase(block), "xlsx")
      exportXlsxWorkbook(overviewEvidenceSheets(state.summary, evidence, block), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências da visao geral.")
    } finally {
      setExportingOverviewBlock(null)
    }
  }

  async function handleDailyExport(row: CashFlowDailyRow) {
    if (!companyId) return
    setExportingDailyDate(row.date)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, {
        start_date: row.date,
        end_date: row.date,
        financial_account_id: filters.financial_account_id,
        limit: "5000",
      })
      const fileName = makeFileName(`por_dia_${row.date}`, "xlsx")
      exportXlsxWorkbook(dailyEvidenceSheets(row, response.data), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências do dia.")
    } finally {
      setExportingDailyDate(null)
    }
  }

  async function handleAccountExport(row: CashFlowAccountRow) {
    if (!companyId) return
    setExportingAccountId(row.financial_account_id)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, {
        ...filters,
        financial_account_id: row.financial_account_id,
        limit: "5000",
      })
      const fileName = makeFileName(`por_conta_${row.financial_account_name}_${row.financial_account_id}`, "xlsx")
      exportXlsxWorkbook(accountEvidenceSheets(row, response.data), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências da conta.")
    } finally {
      setExportingAccountId(null)
    }
  }

  async function handlePendingExport(block: PendingExportBlock) {
    if (!companyId) return
    setExportingPendingBlock(block)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, { ...filters, limit: "5000" })
      const fileName = makeFileName(pendingBlockFileBase(block), "xlsx")
      exportXlsxWorkbook(pendingEvidenceSheets(response.data, block), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências de pendências.")
    } finally {
      setExportingPendingBlock(null)
    }
  }

  async function handleReconciliationExport(block: ReconciliationExportBlock) {
    if (!companyId) return
    setExportingReconciliationBlock(block)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, { ...filters, limit: "5000" })
      const fileName = makeFileName(reconciliationBlockFileBase(block), "xlsx")
      exportXlsxWorkbook(reconciliationEvidenceSheets(state.reconciliation, response.data, block), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências de conciliação.")
    } finally {
      setExportingReconciliationBlock(null)
    }
  }

  async function handleDrillDownFocusExport(focus: DrillDownFocus) {
    if (!companyId) return
    setExportingDrillDownTarget(focus)
    setError(null)
    try {
      const response = await getCashFlowOverviewEvidence(companyId, { ...filters, limit: "5000" })
      const fileName = makeFileName(drillDownFocusFileBase(focus), "xlsx")
      exportXlsxWorkbook(drillDownEvidenceSheets(response.data, focus), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências do drill-down.")
    } finally {
      setExportingDrillDownTarget(null)
    }
  }

  async function handleDrillDownCriticalDayExport(day: string) {
    if (!companyId || !day) return
    setExportingDrillDownTarget("critical_day")
    setError(null)
    try {
      const row = state.daily.find((item) => item.date === day)
      if (!row) throw new Error("Dia crítico não encontrado no período filtrado.")
      const response = await getCashFlowOverviewEvidence(companyId, {
        start_date: day,
        end_date: day,
        financial_account_id: filters.financial_account_id,
        limit: "5000",
      })
      const fileName = makeFileName(`drilldown_dia_critico_${day}`, "xlsx")
      exportXlsxWorkbook(dailyEvidenceSheets(row, response.data), fileName)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao exportar evidências do dia crítico.")
    } finally {
      setExportingDrillDownTarget(null)
    }
  }

  if (!isCompanyLoading && !isCompanyResolved) {
    return (
      <div className="rounded-[2rem] border border-amber-500/30 bg-amber-500/10 p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <p className="text-xs font-bold uppercase tracking-wide text-amber-700">Empresa ativa necessária</p>
        <h1 className="mt-2 text-2xl font-black text-[var(--color-text)]">Selecione ou cadastre uma empresa para ver o fluxo de caixa.</h1>
        <p className="mt-3 text-sm text-[var(--color-text-muted)]">{companyError ?? "O dashboard financeiro sempre filtra por empresa para evitar mistura de dados."}</p>
        <button type="button" onClick={() => void reloadCompanies()} className="mt-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm font-bold text-amber-700 hover:bg-amber-500/20">Recarregar empresas</button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="grid gap-0 xl:grid-cols-[1.25fr_0.75fr]">
          <div className="p-6 sm:p-8">
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <InfoPill icon={<TrendingUp className="h-4 w-4" />} label="Bloco 11" />
              <InfoPill icon={<Database className="h-4 w-4" />} label="Derivado do banco" />
              <InfoPill icon={<ShieldCheck className="h-4 w-4" />} label="Não altera fatos" />
            </div>
            <p className="text-sm font-semibold text-[var(--color-primary)]">{activeCompanyName}</p>
            <h1 className="mt-2 text-4xl font-black tracking-tight text-[var(--color-text)]">Fluxo de Caixa</h1>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">
              Visão integrada de previsto, realizado, saldo interno, pendências e conciliação. Esta tela não corrige lançamentos — ela aponta onde cada divergência deve ser tratada.
            </p>
          </div>
          <aside className="border-t border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 xl:border-l xl:border-t-0 sm:p-8">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <WalletCards className="h-6 w-6" />
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--color-text-muted)]">Saldo interno</p>
                <h2 className="text-2xl font-black text-[var(--color-text)]">{formatMoney(state.summary?.internal_balance_total)}</h2>
              </div>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <StatusLine label="Contas financeiras" value={String(state.summary?.financial_account_count ?? 0)} />
              <StatusLine label="Pendencias de conciliacao" value={String((state.summary?.pending_reconciliation_count ?? 0) + (state.summary?.divergent_reconciliation_count ?? 0) + (state.summary?.pending_statement_lines ?? 0) + (state.summary?.divergent_statement_lines ?? 0))} />
            </div>
          </aside>
        </div>
      </header>

      {/* Barra de filtros */}
      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-xl shadow-[var(--color-card-shadow)] sm:p-5">
        <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1.3fr_auto]">
          <label className="space-y-2">
            <span className="text-sm font-semibold text-[var(--color-text-muted)]">De</span>
            <input type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); setAccountsPage(0) }} className="field-input w-full" />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-semibold text-[var(--color-text-muted)]">Até</span>
            <input type="date" value={endDate} onChange={(event) => { setEndDate(event.target.value); setAccountsPage(0) }} className="field-input w-full" />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-semibold text-[var(--color-text-muted)]">Conta financeira</span>
            <select value={financialAccountId} onChange={(event) => { setFinancialAccountId(event.target.value); setAccountsPage(0) }} className="field-input w-full">
              <option value="">Todas as contas</option>
              {state.financialAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
            </select>
          </label>
          <div className="flex items-end gap-2">
            <button type="button" onClick={() => void load()} disabled={isLoading} className="inline-flex h-[46px] items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
              Atualizar
            </button>
          </div>
        </div>
        {error ? <p className="mt-3 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-600">{error}</p> : null}
      </section>

      {/* Navegação compacta */}
      <nav className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2.5 text-sm font-bold transition ${
              activeTab === tab.id
                ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "overview"       ? <OverviewTab summary={state.summary} pending={state.pending} diagnostics={state.diagnostics} onExport={(block) => void handleOverviewExport(block)} exportingBlock={exportingOverviewBlock} /> : null}
      {activeTab === "daily"          ? <DailyTab rows={state.daily} onExportDay={(row) => void handleDailyExport(row)} exportingDay={exportingDailyDate} /> : null}
      {activeTab === "accounts"       ? <AccountsTab rows={state.accounts} page={accountsPage} hasNextPage={hasNextAccountsPage} isLoading={isLoading} onPreviousPage={() => setAccountsPage((current) => Math.max(current - 1, 0))} onNextPage={() => setAccountsPage((current) => current + 1)} onExportAccount={(row) => void handleAccountExport(row)} exportingAccountId={exportingAccountId} /> : null}
      {activeTab === "pending"        ? <PendingTab pending={state.pending} onExportBlock={(block) => void handlePendingExport(block)} exportingBlock={exportingPendingBlock} /> : null}
      {activeTab === "reconciliation" ? <ReconciliationTab data={state.reconciliation} onExportBlock={(block) => void handleReconciliationExport(block)} exportingBlock={exportingReconciliationBlock} /> : null}
      {activeTab === "drilldown"      ? <DrillDownTab pending={state.pending} daily={state.daily} onExportFocus={(focus) => void handleDrillDownFocusExport(focus)} onExportCriticalDay={(day) => void handleDrillDownCriticalDayExport(day)} exportingTarget={exportingDrillDownTarget} /> : null}
      {activeTab === "forecast"       ? <CashFlowForecastPanel companyId={companyId ?? ""} startDate={startDate} endDate={endDate} financialAccountId={financialAccountId || undefined} /> : null}
    </div>
  )
}

function OverviewTab({
  summary,
  pending,
  diagnostics,
  onExport,
  exportingBlock,
}: {
  summary: CashFlowSummary | null
  pending: CashFlowPending | null
  diagnostics: CashFlowDiagnostics | null
  onExport: (block: OverviewExportBlock) => void
  exportingBlock: OverviewExportBlock | null
}) {
  const flags = summary?.health_flags ?? []
  const reconciliationIssueCount =
    (summary?.pending_reconciliation_count ?? 0) +
    (summary?.divergent_reconciliation_count ?? 0) +
    (summary?.pending_statement_lines ?? 0) +
    (summary?.divergent_statement_lines ?? 0)
  const exportProps = (block: OverviewExportBlock) => ({
    onExport: () => onExport(block),
    isExporting: exportingBlock === block,
    isExportDisabled: exportingBlock !== null && exportingBlock !== block,
  })

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric accent="#16a34a" icon={<Landmark className="h-5 w-5" />} title="Saldo interno" value={formatMoney(summary?.internal_balance_total)} helper="posicao atual das contas internas" {...exportProps("internal_balance")} />
        <Metric accent="#2563eb" icon={<CalendarDays className="h-5 w-5" />} title="Entradas previstas" value={formatMoney(summary?.expected_inflow_amount)} helper={`${summary?.expected_inflow_count ?? 0} recebiveis por vencimento`} {...exportProps("expected_inflow")} />
        <Metric accent="#d97706" icon={<ArrowUpCircle className="h-5 w-5" />} title="Saídas previstas" value={formatMoney(summary?.expected_outflow_amount)} helper={`${summary?.expected_outflow_count ?? 0} contas a pagar por vencimento`} {...exportProps("expected_outflow")} />
        <Metric accent="#dc2626" icon={<AlertTriangle className="h-5 w-5" />} title="Vencidos" value={formatMoney(String(Number(summary?.overdue_receivable_amount ?? 0) + Number(summary?.overdue_payable_amount ?? 0)))} helper={`${(summary?.overdue_receivable_count ?? 0) + (summary?.overdue_payable_count ?? 0)} titulos - posicao atual`} {...exportProps("overdue")} />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Panel title="Leitura operacional" icon={<Search className="h-5 w-5" />} action={<ExportButton label="XLSX" onClick={() => onExport("operational")} isLoading={exportingBlock === "operational"} disabled={exportingBlock !== null && exportingBlock !== "operational"} />}>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatusLine label="Recebido em baixas" value={formatMoney(summary?.received_amount)} />
            <StatusLine label="Pago em baixas" value={formatMoney(summary?.paid_amount)} />
            <StatusLine label="Entradas realizadas no caixa" value={formatMoney(summary?.realized_inflow_amount)} />
            <StatusLine label="Saidas realizadas no caixa" value={formatMoney(summary?.realized_outflow_amount)} />
            <StatusLine label="Extrato entrada (externo)" value={formatMoney(summary?.statement_inflow_amount)} />
            <StatusLine label="Extrato saida (externo)" value={formatMoney(summary?.statement_outflow_amount)} />
            <StatusLine label="Movimentos conciliados" value={`${summary?.matched_movement_count ?? 0}`} />
            <StatusLine label="Pendencias de conciliacao" value={`${reconciliationIssueCount}`} />
          </div>
        </Panel>
        <Panel title="Alertas de qualidade" icon={<ShieldCheck className="h-5 w-5" />} action={<ExportButton label="XLSX" onClick={() => onExport("quality")} isLoading={exportingBlock === "quality"} disabled={exportingBlock !== null && exportingBlock !== "quality"} />}>
          <div className="space-y-3">
            {flags.length === 0 ? <EmptyState message="Sem alertas para o periodo." /> : flags.map((flag) => <HealthFlag key={flag.code} flag={flag} />)}
          </div>
          <p className="mt-4 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
            Fonte: {diagnostics?.storage === "derived" ? "indicadores derivados das tabelas operacionais" : "modulo de fluxo de caixa"}. Nenhum ajuste e feito por esta tela.
          </p>
        </Panel>
      </section>

      <section className="grid gap-6 xl:grid-cols-4">
        <MiniList title="Recebiveis vencidos" items={pending?.overdue_titles.map((item) => `${formatDate(item.due_date)} - ${formatMoney(item.open_amount)} - ${statusLabel(item.status)}`) ?? []} onExport={() => onExport("overdue_receivables")} isExporting={exportingBlock === "overdue_receivables"} disabled={exportingBlock !== null && exportingBlock !== "overdue_receivables"} />
        <MiniList title="A pagar vencidos" items={pending?.overdue_payables?.map((item) => `${formatDate(item.due_date)} - ${formatMoney(item.open_amount)} - ${statusLabel(item.status)}`) ?? []} onExport={() => onExport("overdue_payables")} isExporting={exportingBlock === "overdue_payables"} disabled={exportingBlock !== null && exportingBlock !== "overdue_payables"} />
        <MiniList title="Movimentos sem match" items={pending?.unreconciled_movements.map((item) => `${formatDate(item.movement_date)} - ${formatMoney(item.amount)} - ${statusLabel(item.reconciliation_status)}`) ?? []} onExport={() => onExport("unreconciled_movements")} isExporting={exportingBlock === "unreconciled_movements"} disabled={exportingBlock !== null && exportingBlock !== "unreconciled_movements"} />
        <MiniList title="Extratos pendentes" items={pending?.unmatched_statement_lines.map((item) => `${formatDate(item.line_date)} - ${formatMoney(item.amount)} - ${item.description ?? "sem descricao"}`) ?? []} onExport={() => onExport("unmatched_statement_lines")} isExporting={exportingBlock === "unmatched_statement_lines"} disabled={exportingBlock !== null && exportingBlock !== "unmatched_statement_lines"} />
      </section>
    </div>
  )
}

function DailyTab({ rows, onExportDay, exportingDay }: { rows: CashFlowDailyRow[]; onExportDay: (row: CashFlowDailyRow) => void; exportingDay: string | null }) {
  const exportRows = dailyExportRows(rows)
  return (
    <Panel title="Fluxo por dia" icon={<CalendarDays className="h-5 w-5" />}>
      <ExportActions rows={exportRows} sheetName="Fluxo por dia" fileBaseName="por_dia" />
      <p className="mb-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
        Previsto usa titulos por vencimento. Realizado usa baixas e movimentos internos postados. Extrato externo e apenas evidência bancaria. Projeção do dia não e saldo acumulado.
      </p>
      <ResponsiveTable headers={["Dia", "Entradas prev.", "Saídas prev.", "Recebido", "Pago", "Caixa líquido", "Projeção do dia", "Extrato líquido", "Pendências", "XLSX"]}>
        {rows.map((row) => (
          <tr key={row.date} className="border-t border-[var(--color-border-soft)]">
            <TableCell>{formatDate(row.date)}</TableCell>
            <TableCell>{formatMoney(row.expected_inflow_amount)}</TableCell>
            <TableCell>{formatMoney(row.expected_outflow_amount)}</TableCell>
            <TableCell>{formatMoney(row.received_amount)}</TableCell>
            <TableCell>{formatMoney(row.paid_amount)}</TableCell>
            <TableCell>{formatMoney(row.realized_net_amount)}</TableCell>
            <TableCell>{formatMoney(row.projected_net_amount)}</TableCell>
            <TableCell>{formatMoney(moneyNet(row.statement_inflow_amount, row.statement_outflow_amount))}</TableCell>
            <TableCell>{row.unreconciled_movements + row.pending_statement_lines}</TableCell>
            <TableCell>
              <button
                type="button"
                onClick={() => onExportDay(row)}
                disabled={exportingDay !== null}
                aria-label={`Exportar evidências de ${formatDate(row.date)} em XLSX`}
                className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {exportingDay === row.date ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
              </button>
            </TableCell>
          </tr>
        ))}
      </ResponsiveTable>
    </Panel>
  )
}

function statusCountLabel(statuses: Record<string, { count: number; amount?: string }>, status: string) {
  const value = statuses[status]
  return `${value?.count ?? 0} - ${formatMoney(value?.amount)}`
}

function AccountsTab({
  rows,
  page,
  hasNextPage,
  isLoading,
  onPreviousPage,
  onNextPage,
  onExportAccount,
  exportingAccountId,
}: {
  rows: CashFlowAccountRow[]
  page: number
  hasNextPage: boolean
  isLoading: boolean
  onPreviousPage: () => void
  onNextPage: () => void
  onExportAccount: (row: CashFlowAccountRow) => void
  exportingAccountId: string | null
}) {
  const exportRows = accountExportRows(rows)
  return (
    <div className="space-y-4">
      <ExportActions rows={exportRows} sheetName="Fluxo por conta" fileBaseName="por_conta" />
      <p className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
        Saldo atual é a posição materializada da conta. Entradas, saídas e líquido no período usam movimentos internos postados no filtro. Extrato bancário é evidência externa e não altera saldo interno sozinho.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        {rows.length === 0 ? <EmptyState message="Nenhuma conta financeira encontrada para o filtro." /> : rows.map((row) => (
          <article key={row.financial_account_id} className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-[var(--color-text-muted)]">{row.account_type}</p>
                <h3 className="mt-1 text-lg font-black text-[var(--color-text)]">{row.financial_account_name}</h3>
                <p className="mt-1 text-sm text-[var(--color-text-muted)]">{row.institution_name ?? "Sem instituição informada"}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{statusLabel(row.status)}</span>
                <ExportButton label="XLSX" onClick={() => onExportAccount(row)} isLoading={exportingAccountId === row.financial_account_id} disabled={exportingAccountId !== null && exportingAccountId !== row.financial_account_id} />
              </div>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <StatusLine label="Saldo atual" value={formatMoney(row.current_balance_amount)} />
              <StatusLine label="Líquido no período" value={formatMoney(row.period_net_amount)} />
              <StatusLine label="Entradas" value={formatMoney(row.period_inflow_amount)} />
              <StatusLine label="Saídas" value={formatMoney(row.period_outflow_amount)} />
              <StatusLine label="Mov. pendentes" value={statusCountLabel(row.reconciliation_by_status, "pending")} />
              <StatusLine label="Mov. divergentes" value={statusCountLabel(row.reconciliation_by_status, "divergent")} />
              <StatusLine label="Mov. conciliados" value={statusCountLabel(row.reconciliation_by_status, "matched")} />
              <StatusLine label="Extratos pendentes" value={statusCountLabel(row.statement_by_status, "pending")} />
              <StatusLine label="Extratos divergentes" value={statusCountLabel(row.statement_by_status, "divergent")} />
              <StatusLine label="Extratos conciliados" value={statusCountLabel(row.statement_by_status, "matched")} />
            </div>
          </article>
        ))}
      </div>
      <PaginationControls page={page} hasNextPage={hasNextPage} loading={isLoading} onPrevious={onPreviousPage} onNext={onNextPage} />
    </div>
  )
}

function pendingCountAndAmount(rows: Array<{ open_amount?: string; amount?: string; difference_amount?: string }>) {
  return {
    count: rows.length,
    amount: sumMoneyValues(rows, (item) => item.open_amount ?? item.amount ?? item.difference_amount ?? "0.00"),
  }
}

function PendingSummaryCard({ label, count, amount, onClick, isLoading, disabled }: { label: string; count: number; amount: string; onClick: () => void; isLoading: boolean; disabled: boolean }) {
  return (
    <article className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
          <p className="mt-2 text-2xl font-black text-[var(--color-text)]">{count}</p>
          <p className="mt-1 text-sm font-semibold text-[var(--color-text-muted)]">{formatMoney(amount)}</p>
        </div>
        <ExportButton label="XLSX" onClick={onClick} isLoading={isLoading} disabled={disabled} />
      </div>
    </article>
  )
}

function PendingTab({
  pending,
  onExportBlock,
  exportingBlock,
}: {
  pending: CashFlowPending | null
  onExportBlock: (block: PendingExportBlock) => void
  exportingBlock: PendingExportBlock | null
}) {
  const exportRows = pendingExportRows(pending)
  const exportProps = (block: PendingExportBlock) => ({
    onClick: () => onExportBlock(block),
    isLoading: exportingBlock === block,
    disabled: exportingBlock !== null && exportingBlock !== block,
  })
  const cards: Array<{ block: PendingExportBlock; label: string; count: number; amount: string }> = [
    { block: "overdue_receivables", label: "Receber vencidos", ...pendingCountAndAmount(pending?.overdue_titles ?? []) },
    { block: "upcoming_receivables", label: "Receber previstos", ...pendingCountAndAmount(pending?.upcoming_titles ?? []) },
    { block: "overdue_payables", label: "Pagar vencidos", ...pendingCountAndAmount(pending?.overdue_payables ?? []) },
    { block: "upcoming_payables", label: "Pagar previstas", ...pendingCountAndAmount(pending?.upcoming_payables ?? []) },
    { block: "unreconciled_movements", label: "Mov. sem conciliação", ...pendingCountAndAmount(pending?.unreconciled_movements ?? []) },
    { block: "unmatched_statement_lines", label: "Extratos sem match", ...pendingCountAndAmount(pending?.unmatched_statement_lines ?? []) },
    { block: "divergent_matches", label: "Matches com diferença", ...pendingCountAndAmount(pending?.divergent_matches ?? []) },
  ]

  return (
    <div className="space-y-4">
      <ExportActions rows={exportRows} sheetName="Pendências" fileBaseName="pendencias" />
      <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
        Pendência é fila operacional: vencimento, previsão, conciliação ou divergência. A tela lista até 100 itens por grupo; os botões XLSX por bloco buscam evidências completas até 5000 registros.
      </div>
      <div className="flex justify-end">
        <ExportButton label="Baixar todas as pendências" {...exportProps("all")} />
      </div>
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <PendingSummaryCard key={card.block} label={card.label} count={card.count} amount={card.amount} {...exportProps(card.block)} />
        ))}
      </section>
      <div className="grid gap-6 xl:grid-cols-2">
        <PendingTable title="Títulos vencidos" rows={pending?.overdue_titles ?? []} type="title" action={<ExportButton label="XLSX" {...exportProps("overdue_receivables")} />} />
        <PendingTable title="Títulos previstos" rows={pending?.upcoming_titles ?? []} type="title" action={<ExportButton label="XLSX" {...exportProps("upcoming_receivables")} />} />
        <PendingTable title="Contas a pagar vencidas" rows={pending?.overdue_payables ?? []} type="title" action={<ExportButton label="XLSX" {...exportProps("overdue_payables")} />} />
        <PendingTable title="Contas a pagar previstas" rows={pending?.upcoming_payables ?? []} type="title" action={<ExportButton label="XLSX" {...exportProps("upcoming_payables")} />} />
        <PendingTable title="Movimentos sem conciliação" rows={pending?.unreconciled_movements ?? []} type="movement" action={<ExportButton label="XLSX" {...exportProps("unreconciled_movements")} />} />
        <PendingTable title="Linhas de extrato sem match" rows={pending?.unmatched_statement_lines ?? []} type="statement" action={<ExportButton label="XLSX" {...exportProps("unmatched_statement_lines")} />} />
        <Panel title="Matches com diferença" icon={<AlertTriangle className="h-5 w-5" />} action={<ExportButton label="XLSX" {...exportProps("divergent_matches")} />}>
          {(pending?.divergent_matches ?? []).length === 0 ? <EmptyState message="Nenhum match com diferença em aberto." /> : (
            <div className="space-y-3">
              {pending?.divergent_matches.map((item) => (
                <div key={item.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                  <p className="text-sm font-black text-[var(--color-text)]">{formatMoney(item.difference_amount)}</p>
                  <p className="mt-1 text-xs font-semibold text-[var(--color-text-muted)]">{formatDate(item.created_at)} - movimento {item.financial_movement_id} - extrato {item.statement_line_id}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{item.confirmation_reason ?? "Sem justificativa"}</p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}

function ReconciliationTab({
  data,
  onExportBlock,
  exportingBlock,
}: {
  data: CashFlowReconciliationStatus | null
  onExportBlock: (block: ReconciliationExportBlock) => void
  exportingBlock: ReconciliationExportBlock | null
}) {
  const exportRows = reconciliationExportRows(data)
  const exportProps = (block: ReconciliationExportBlock) => ({
    onClick: () => onExportBlock(block),
    isLoading: exportingBlock === block,
    disabled: exportingBlock !== null && exportingBlock !== block,
  })

  return (
    <div className="space-y-4">
      <ExportActions rows={exportRows} sheetName="Conciliação" fileBaseName="conciliacao" />
      <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-semibold leading-6 text-[var(--color-text-muted)]">
        Conciliação compara movimento interno com extrato bancário. Match não cria fato financeiro; extrato não altera saldo interno sozinho. Pendências e divergências devem ser tratadas na Conciliação Bancária.
      </div>
      <div className="flex justify-end">
        <ExportButton label="Baixar conciliação completa" {...exportProps("all")} />
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <StatusBlock title="Movimentos internos" statuses={data?.financial_movements} action={<ExportButton label="XLSX" {...exportProps("movements")} />} />
        <StatusBlock title="Linhas de extrato" statuses={data?.statement_lines} action={<ExportButton label="XLSX" {...exportProps("statements")} />} />
        <StatusBlock title="Matches" statuses={data?.matches} difference action={<ExportButton label="XLSX" {...exportProps("matches")} />} />
      </div>
    </div>
  )
}

function DrillDownTab({
  pending,
  daily,
  onExportFocus,
  onExportCriticalDay,
  exportingTarget,
}: {
  pending: CashFlowPending | null
  daily: CashFlowDailyRow[]
  onExportFocus: (focus: DrillDownFocus) => void
  onExportCriticalDay: (day: string) => void
  exportingTarget: DrillDownExportTarget | null
}) {
  const [focus, setFocus] = useState<DrillDownFocus>("overdue_titles")

  const maxPendingDay = daily.reduce((max, row) => {
    const pendingCount = row.unreconciled_movements + row.pending_statement_lines
    if (pendingCount <= max.pendingCount) return max
    return {
      pendingCount,
      movementCount: row.unreconciled_movements,
      statementCount: row.pending_statement_lines,
      date: row.date,
    }
  }, { pendingCount: 0, movementCount: 0, statementCount: 0, date: "" })

  const focusRows = {
    overdue_titles: pending?.overdue_titles ?? [],
    overdue_payables: pending?.overdue_payables ?? [],
    unreconciled_movements: pending?.unreconciled_movements ?? [],
    unmatched_statement_lines: pending?.unmatched_statement_lines ?? [],
    divergent_matches: pending?.divergent_matches ?? [],
  }[focus]

  const focusAmount = {
    overdue_titles: sumMoneyValues(pending?.overdue_titles ?? [], (item) => item.open_amount),
    overdue_payables: sumMoneyValues(pending?.overdue_payables ?? [], (item) => item.open_amount),
    unreconciled_movements: sumMoneyValues(pending?.unreconciled_movements ?? [], (item) => item.amount),
    unmatched_statement_lines: sumMoneyValues(pending?.unmatched_statement_lines ?? [], (item) => item.amount),
    divergent_matches: sumMoneyValues(pending?.divergent_matches ?? [], (item) => item.difference_amount),
  }[focus]
  const focusTitle = drillDownFocusLabel(focus)
  const focusExportDisabled = exportingTarget !== null && exportingTarget !== focus
  const criticalDayExportDisabled = !maxPendingDay.date || (exportingTarget !== null && exportingTarget !== "critical_day")

  return (
    <div className="space-y-5">
      <Panel
        title="Drill-down operacional"
        icon={<Search className="h-5 w-5" />}
        action={<ExportButton label="Baixar foco XLSX" onClick={() => onExportFocus(focus)} isLoading={exportingTarget === focus} disabled={focusExportDisabled} />}
      >
        <div className="mb-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
          Drill-down é investigação operacional. A lista em tela usa a amostra carregada de até 100 itens por grupo; o XLSX do foco busca evidências completas até 5000 registros no período filtrado.
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatusLine label="Foco atual" value={focusTitle} />
          <StatusLine label="Itens exibidos" value={`${focusRows.length} · ${formatMoney(focusAmount)}`} />
          <StatusLine label="Maior dia com pendências" value={maxPendingDay.date ? `${formatDate(maxPendingDay.date)} · ${maxPendingDay.pendingCount}` : "Sem pendências"} />
          <StatusLine label="Origem do dia crítico" value={`${maxPendingDay.movementCount} mov. · ${maxPendingDay.statementCount} extratos`} />
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <ExportButton label="Baixar dia crítico" onClick={() => onExportCriticalDay(maxPendingDay.date)} isLoading={exportingTarget === "critical_day"} disabled={criticalDayExportDisabled} />
        </div>
        <label className="mt-4 block space-y-2">
          <span className="text-sm font-semibold text-[var(--color-text-muted)]">Foco da investigação</span>
          <select value={focus} onChange={(event) => setFocus(event.target.value as DrillDownFocus)} className="field-input w-full">
            <option value="overdue_titles">Recebíveis vencidos</option>
            <option value="overdue_payables">A pagar vencidos</option>
            <option value="unreconciled_movements">Movimentos sem conciliação</option>
            <option value="unmatched_statement_lines">Extratos sem match</option>
            <option value="divergent_matches">Matches divergentes</option>
          </select>
        </label>
      </Panel>

      {focus === "divergent_matches" ? (
        <Panel title={focusTitle} icon={<AlertTriangle className="h-5 w-5" />} action={<ExportButton label="XLSX" onClick={() => onExportFocus(focus)} isLoading={exportingTarget === focus} disabled={focusExportDisabled} />}>
          {focusRows.length === 0 ? <EmptyState message="Sem matches divergentes no período." /> : (
            <div className="space-y-3">
              {(focusRows as Array<{ id: string; financial_movement_id: string; statement_line_id: string; difference_amount: string; confirmation_reason?: string | null; created_at: string }>).map((item) => (
                <div key={item.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                  <p className="text-sm font-black text-[var(--color-text)]">{formatMoney(item.difference_amount)}</p>
                  <p className="mt-1 text-xs font-semibold text-[var(--color-text-muted)]">{formatDate(item.created_at)} · movimento {item.financial_movement_id} · extrato {item.statement_line_id}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{item.confirmation_reason ?? "Sem justificativa"}</p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      ) : (
        <PendingTable
          title={focusTitle}
          rows={focusRows}
          type={focus === "unreconciled_movements" ? "movement" : focus === "unmatched_statement_lines" ? "statement" : "title"}
          action={<ExportButton label="XLSX" onClick={() => onExportFocus(focus)} isLoading={exportingTarget === focus} disabled={focusExportDisabled} />}
        />
      )}
    </div>
  )
}

function Metric({
  title,
  value,
  helper,
  accent,
  icon,
  onExport,
  isExporting = false,
  isExportDisabled = false,
}: {
  title: string
  value: string | number
  helper: string
  accent: string
  icon?: ReactNode
  onExport?: () => void
  isExporting?: boolean
  isExportDisabled?: boolean
}) {
  return (
    <article className="rounded-3xl p-5 shadow-xl shadow-[var(--color-card-shadow)]" style={{ background: accent, border: `1px solid ${accent}` }}>
      <div className="flex items-start justify-between gap-3">
        <div>
          {icon && <span className="text-white/60">{icon}</span>}
          <p className="mt-3 text-xs font-bold uppercase tracking-wide text-white/75">{title}</p>
          <p className="mt-2 text-3xl font-black text-white">{value}</p>
          <p className="mt-1 text-xs text-white/65">{helper}</p>
        </div>
        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting || isExportDisabled}
            aria-label={`Exportar ${title} em XLSX`}
            title={`Exportar ${title} em XLSX`}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/30 bg-white/15 text-white transition hover:bg-white/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          </button>
        ) : null}
      </div>
    </article>
  )
}

function ExportActions({ rows, sheetName, fileBaseName }: { rows: ExportTable; sheetName: string; fileBaseName: string }) {
  const disabled = rows.length <= 1
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3">
      <p className="text-xs font-semibold leading-5 text-[var(--color-text-muted)]">Exportação da aba filtrada. Para importar extratos bancários, use Conciliação Bancária/OFX.</p>
      <div className="flex flex-wrap gap-2">
        <button type="button" disabled={disabled} onClick={() => exportTable(rows, sheetName, fileBaseName, "csv")} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-xs font-black text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50">
          <Download className="h-4 w-4" /> CSV
        </button>
        <button type="button" disabled={disabled} onClick={() => exportTable(rows, sheetName, fileBaseName, "xlsx")} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50">
          <Download className="h-4 w-4" /> XLSX
        </button>
      </div>
    </div>
  )
}

function PaginationControls({ page, hasNextPage, loading, onPrevious, onNext }: { page: number; hasNextPage: boolean; loading: boolean; onPrevious: () => void; onNext: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)] sm:flex-row sm:items-center sm:justify-between">
      <span>Pagina {page + 1} com ate {ACCOUNT_PAGE_SIZE} contas.</span>
      <div className="flex gap-2">
        <button type="button" onClick={onPrevious} disabled={loading || page === 0} className="rounded-xl border border-[var(--color-border-soft)] px-3 py-2 font-black text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50">Anterior</button>
        <button type="button" onClick={onNext} disabled={loading || !hasNextPage} className="rounded-xl border border-[var(--color-primary-border)] px-3 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50">Proxima</button>
      </div>
    </div>
  )
}

function PendingTable({ title, rows, type, action }: { title: string; rows: unknown[]; type: "title" | "movement" | "statement"; action?: ReactNode }) {
  return (
    <Panel title={title} icon={<Filter className="h-5 w-5" />} action={action}>
      {rows.length === 0 ? <EmptyState message="Sem registros para este filtro." /> : (
        <div className="space-y-3">
          {rows.map((rawRow) => {
            const row = rawRow as Record<string, unknown>
            const id = String(row.id)
            const date = String(row.due_date ?? row.movement_date ?? row.line_date ?? "")
            const amount = String(row.open_amount ?? row.amount ?? "0")
            const status = String(row.status ?? row.reconciliation_status ?? "")
            const description = String(row.document_reference ?? row.description ?? row.source_type ?? "")
            return (
              <article key={id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-black text-[var(--color-text)]">{formatMoney(amount)}</p>
                    <p className="mt-1 text-xs font-semibold text-[var(--color-text-muted)]">{formatDate(date)} · {description || type}</p>
                  </div>
                  <span className="rounded-full border border-[var(--color-border-soft)] px-3 py-1 text-xs font-black text-[var(--color-text-muted)]">{statusLabel(status)}</span>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </Panel>
  )
}

function StatusBlock({ title, statuses, difference = false, action }: { title: string; statuses?: Record<string, { count: number; amount?: string; difference_amount?: string }>; difference?: boolean; action?: ReactNode }) {
  const total = sumStatusCount(statuses)
  return (
    <Panel title={title} icon={<ArrowRightLeft className="h-5 w-5" />} action={action}>
      <p className="mb-4 text-2xl font-black text-[var(--color-text)]">{total}</p>
      <div className="space-y-3">
        {Object.entries(statuses ?? {}).length === 0 ? <EmptyState message="Sem dados no período." /> : Object.entries(statuses ?? {}).map(([status, value]) => (
          <StatusLine key={status} label={statusLabel(status)} value={`${value.count} · ${formatMoney(difference ? value.difference_amount : value.amount)}`} />
        ))}
      </div>
    </Panel>
  )
}

function Panel({ title, icon, children, action }: { title: string; icon: ReactNode; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">{icon}</span>
          <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function ExportButton({ label, onClick, isLoading = false, disabled = false }: { label: string; onClick: () => void; isLoading?: boolean; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLoading || disabled}
      className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
      {label}
    </button>
  )
}

function ResponsiveTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead>
          <tr className="text-xs font-semibold text-[var(--color-text-muted)]">
            {headers.map((header) => <th key={header} className="px-3 py-3">{header}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

function TableCell({ children }: { children: ReactNode }) {
  return <td className="px-3 py-3 font-semibold text-[var(--color-text-muted)]">{children}</td>
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3">
      <span className="text-sm font-semibold text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm font-black text-[var(--color-text)]">{value}</span>
    </div>
  )
}

function InfoPill({ icon, label }: { icon: ReactNode; label: string }) {
  return <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-xs font-bold text-[var(--color-primary)]">{icon}{label}</span>
}

function EmptyState({ message }: { message: string }) {
  return <p className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)]">{message}</p>
}

function HealthFlag({ flag }: { flag: { level: string; message: string } }) {
  const icon = flag.level === "ok" ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />
  const tone =
    flag.level === "ok"   ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700" :
    flag.level === "risk" ? "border-red-500/40 bg-red-500/10 text-red-600" :
                            "border-amber-500/40 bg-amber-500/10 text-amber-700"
  return <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm font-semibold ${tone}`}>{icon}<span>{flag.message}</span></div>
}

function MiniList({
  title,
  items,
  onExport,
  isExporting = false,
  disabled = false,
}: {
  title: string
  items: string[]
  onExport?: () => void
  isExporting?: boolean
  disabled?: boolean
}) {
  return (
    <Panel
      title={title}
      icon={<CircleDollarSign className="h-5 w-5" />}
      action={onExport ? <ExportButton label="XLSX" onClick={onExport} isLoading={isExporting} disabled={disabled} /> : undefined}
    >
      <div className="space-y-2">
        {items.length === 0
          ? <EmptyState message="Sem registros." />
          : items.slice(0, 5).map((item) => (
              <p key={item} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)]">{item}</p>
            ))
        }
      </div>
    </Panel>
  )
}
