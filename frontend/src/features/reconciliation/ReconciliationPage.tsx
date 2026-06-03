import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  Database,
  EyeOff,
  FileSearch,
  FileSpreadsheet,
  FileUp,
  History,
  LayoutDashboard,
  Link2,
  RefreshCw,
  Search,
  UploadCloud,
  X,
} from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import { buildExportFileName } from "../../lib/exportStandard"
import { dateCell, dateTimeCell, exportXlsxWorkbook, integerCell, moneyCell, type ExportSheet, type ExportTable } from "../../lib/exportTable"
import { listFinancialMovements } from "../cash/cashApi"
import type { FinancialMovement } from "../cash/types"
import { listFinancialAccounts } from "../financial/financialApi"
import type { FinancialAccount } from "../financial/types"
import {
  confirmReconciliationMatch,
  getReconciliationDiagnostics,
  getReconciliationOverviewEvidence,
  getReconciliationSummary,
  ignoreStatementLine,
  importBankStatement,
  importOfxBankStatement,
  listReconciliationMatches,
  listStatementImports,
  listStatementLines,
  reverseReconciliationMatch,
  suggestMatches,
} from "./reconciliationApi"
import type {
  BankStatementImport,
  BankStatementLine,
  MovementCandidate,
  ReconciliationDiagnostics,
  ReconciliationMatch,
  ReconciliationOverviewEvidence,
  ReconciliationSummary,
} from "./types"

type Tab = "overview" | "import" | "lines" | "match" | "matches"
type Notice = { type: "success" | "error"; message: string } | null
type OverviewExportBlock =
  | "pending_statement_lines"
  | "pending_financial_movements"
  | "confirmed_matches"
  | "divergences"
  | "ignored_statement_lines"

type LineMetrics = {
  totalCount: number
  totalAmount: number
  inflowCount: number
  inflowAmount: number
  outflowCount: number
  outflowAmount: number
}

type MatchHistoryMetrics = {
  totalCount: number
  confirmedCount: number
  confirmedWithDifferenceCount: number
  reversedCount: number
  matchedAmount: number
  differenceAmount: number
}

const MATCH_TOLERANCE_AMOUNT = 0.05
const PAGE_SIZE = 50
const PAGE_FETCH_LIMIT = PAGE_SIZE + 1
const EXPORT_PAGE_SIZE = 200
const EXPORT_MAX_ROWS = 5000

const money = (value: string | number | null | undefined) => {
  const n = Number(value ?? 0)
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    Number.isFinite(n) ? n : 0,
  )
}

const today = () => new Date().toISOString().slice(0, 10)

function makeManualImportDefaults() {
  const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  return {
    source_id: `manual-${stamp}`,
    file_name: `extrato-manual-${today()}.csv`,
    statement_start_date: today(),
    statement_end_date: today(),
    closing_balance_amount: "0,00",
    external_id: `line-${stamp}`,
    line_date: today(),
    direction: "inflow" as "inflow" | "outflow",
    amount: "0,00",
    description: "Linha de extrato manual",
    bank_reference: "",
  }
}

function normalizeMoneyInput(value: string) {
  return value.trim().replace(/\./g, "").replace(",", ".")
}

function isPositiveMoneyInput(value: string) {
  const parsed = Number(normalizeMoneyInput(value))
  return Number.isFinite(parsed) && parsed > 0
}

function parseMoneyValue(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatDate(value: string | null | undefined) {
  if (!value) return ""
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-")
    return `${day}/${month}/${year}`
  }
  return value
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date)
}

async function readStatementFileContent(file: File) {
  const buffer = await file.arrayBuffer()
  const utf8 = new TextDecoder("utf-8", { fatal: false }).decode(buffer)
  if (utf8.includes("<OFX") || utf8.includes("<ofx")) return utf8
  return new TextDecoder("windows-1252", { fatal: false }).decode(buffer)
}

function directionLabel(direction: string) {
  return direction === "inflow" ? "Entrada" : "Saída"
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pendente",
    matched: "Conciliado",
    divergent: "Divergente",
    ignored: "Ignorado",
    confirmed: "Confirmado",
    confirmed_with_difference: "Conf. com diferença",
    reversed: "Estornado",
  }
  return labels[status] ?? status
}

function statusColor(status: string) {
  switch (status) {
    case "confirmed":
      return "bg-emerald-500/10 text-emerald-700 border-emerald-500/30"
    case "confirmed_with_difference":
      return "bg-amber-500/10 text-amber-700 border-amber-500/30"
    case "reversed":
      return "bg-red-500/10 text-red-600 border-red-500/30"
    case "divergent":
      return "bg-amber-500/10 text-amber-700 border-amber-500/30"
    case "ignored":
      return "bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)] border-[var(--color-border-soft)]"
    default:
      return "bg-[var(--color-primary-soft)] text-[var(--color-primary)] border-[var(--color-primary-border)]"
  }
}

const OVERVIEW_BLOCK_LABELS: Record<OverviewExportBlock, string> = {
  pending_statement_lines: "Linhas pendentes",
  pending_financial_movements: "Movimentos pendentes",
  confirmed_matches: "Matches confirmados",
  divergences: "Divergências",
  ignored_statement_lines: "Linhas ignoradas",
}

function summaryRows(summary: ReconciliationSummary): ExportTable {
  return [
    ["Indicador", "Quantidade", "Valor"],
    ["Linhas de extrato pendentes", integerCell(summary.pending_statement_lines), moneyCell(summary.pending_statement_lines_amount)],
    ["Linhas de extrato conciliadas", integerCell(summary.matched_statement_lines), moneyCell(summary.matched_statement_lines_amount)],
    ["Linhas de extrato divergentes", integerCell(summary.divergent_statement_lines), moneyCell(summary.divergent_statement_lines_amount)],
    ["Linhas de extrato ignoradas", integerCell(summary.ignored_statement_lines), moneyCell(summary.ignored_statement_lines_amount)],
    ["Movimentos financeiros pendentes", integerCell(summary.pending_financial_movements), moneyCell(summary.pending_financial_movements_amount)],
    ["Movimentos financeiros divergentes", integerCell(summary.divergent_financial_movements), moneyCell(summary.divergent_financial_movements_amount)],
    ["Matches confirmados", integerCell(summary.confirmed_matches), moneyCell(summary.confirmed_matches_amount)],
    ["Diferença total em matches", integerCell(summary.confirmed_matches), moneyCell(summary.confirmed_matches_difference_amount)],
  ]
}

function statementLinesRows(lines: BankStatementLine[]): ExportTable {
  return [
    [
      "ID da linha",
      "Data",
      "Conta financeira",
      "Direção",
      "Valor",
      "Valor conciliado",
      "Status",
      "Descrição",
      "Documento",
      "Contraparte",
      "Referência bancária",
      "Importação",
      "Criado em",
    ],
    ...lines.map((line) => [
      line.id,
      dateCell(line.line_date),
      line.financial_account_id,
      directionLabel(line.direction),
      moneyCell(line.amount),
      moneyCell(line.matched_amount),
      statusLabel(line.status),
      line.description ?? "",
      line.document_number ?? "",
      line.counterparty_name ?? "",
      line.bank_reference ?? "",
      line.statement_import_id ?? "",
      dateTimeCell(line.created_at),
    ]),
  ]
}

function statementLinesSummaryRows(lines: BankStatementLine[]): ExportTable {
  const metrics = buildLineMetrics(lines)
  const byStatus = lines.reduce<Record<string, { count: number; amount: number }>>((acc, line) => {
    const current = acc[line.status] ?? { count: 0, amount: 0 }
    current.count += 1
    current.amount += parseMoneyValue(line.amount)
    acc[line.status] = current
    return acc
  }, {})

  return [
    ["Indicador", "Quantidade", "Valor"],
    ["Total filtrado", integerCell(metrics.totalCount), moneyCell(metrics.totalAmount)],
    ["Entradas", integerCell(metrics.inflowCount), moneyCell(metrics.inflowAmount)],
    ["Saídas", integerCell(metrics.outflowCount), moneyCell(metrics.outflowAmount)],
    ...Object.entries(byStatus).map(([status, item]) => [
      statusLabel(status),
      integerCell(item.count),
      moneyCell(item.amount),
    ]),
  ]
}

function buildLineMetrics(lines: BankStatementLine[]): LineMetrics {
  return lines.reduce<LineMetrics>(
    (acc, line) => {
      const amount = parseMoneyValue(line.amount)
      acc.totalCount += 1
      acc.totalAmount += amount
      if (line.direction === "inflow") {
        acc.inflowCount += 1
        acc.inflowAmount += amount
      } else {
        acc.outflowCount += 1
        acc.outflowAmount += amount
      }
      return acc
    },
    {
      totalCount: 0,
      totalAmount: 0,
      inflowCount: 0,
      inflowAmount: 0,
      outflowCount: 0,
      outflowAmount: 0,
    },
  )
}

function movementPassesReconciliationFilters(
  movement: FinancialMovement | MovementCandidate,
  financialAccountId: string,
  matchDateFilter: string,
  matchSearch: string,
  options: { ignoreDate?: boolean } = {},
) {
  if (movement.status !== "posted") return false
  if (!["pending", "divergent"].includes(movement.reconciliation_status)) return false
  if (financialAccountId && movement.financial_account_id !== financialAccountId) return false
  if (!options.ignoreDate && matchDateFilter && movement.movement_date !== matchDateFilter) return false
  if (matchSearch.trim()) {
    const q = matchSearch.trim().toLowerCase()
    const haystack = [
      movement.description,
      movement.source_id,
      movement.financial_title_id,
      movement.settlement_id,
      movement.participant_id,
    ]
      .join(" ")
      .toLowerCase()
    if (!haystack.includes(q)) return false
  }
  return true
}

function movementRows(movements: MovementCandidate[]): ExportTable {
  return [
    [
      "ID do movimento",
      "Data",
      "Conta financeira",
      "Direção",
      "Tipo",
      "Valor",
      "Status",
      "Status de conciliação",
      "Origem",
      "ID da origem",
      "Baixa",
      "Título",
      "Participante",
      "Descrição",
    ],
    ...movements.map((movement) => [
      movement.id,
      dateCell(movement.movement_date),
      movement.financial_account_id,
      directionLabel(movement.direction),
      movement.movement_type,
      moneyCell(movement.amount),
      statusLabel(movement.status),
      statusLabel(movement.reconciliation_status),
      movement.source_type,
      movement.source_id,
      movement.settlement_id ?? "",
      movement.financial_title_id ?? "",
      movement.participant_id ?? "",
      movement.description ?? "",
    ]),
  ]
}

function matchRows(matches: ReconciliationMatch[]): ExportTable {
  return [
    [
      "ID do match",
      "Conta financeira",
      "Linha de extrato",
      "Movimento financeiro",
      "Tipo",
      "Valor conciliado",
      "Valor no extrato",
      "Valor no movimento",
      "Diferença",
      "Tolerância",
      "Status",
      "Justificativa",
      "Motivo do estorno",
      "Confirmado em",
      "Estornado em",
      "Criado em",
    ],
    ...matches.map((match) => [
      match.id,
      match.financial_account_id,
      match.statement_line_id,
      match.financial_movement_id,
      match.match_type,
      moneyCell(match.matched_amount),
      moneyCell(match.line_amount),
      moneyCell(match.movement_amount),
      moneyCell(match.difference_amount),
      moneyCell(match.tolerance_amount),
      statusLabel(match.status),
      match.confirmation_reason ?? "",
      match.reversed_reason ?? "",
      dateTimeCell(match.confirmed_at),
      dateTimeCell(match.reversed_at),
      dateTimeCell(match.created_at),
    ]),
  ]
}

function matchHistorySummaryRows(metrics: MatchHistoryMetrics): ExportTable {
  return [
    ["Indicador", "Quantidade", "Valor"],
    ["Matches filtrados", integerCell(metrics.totalCount), moneyCell(metrics.matchedAmount)],
    ["Confirmados", integerCell(metrics.confirmedCount), ""],
    ["Confirmados com diferença", integerCell(metrics.confirmedWithDifferenceCount), moneyCell(metrics.differenceAmount)],
    ["Estornados", integerCell(metrics.reversedCount), ""],
  ]
}

function buildMatchHistoryMetrics(matches: ReconciliationMatch[]): MatchHistoryMetrics {
  return matches.reduce<MatchHistoryMetrics>(
    (acc, match) => {
      acc.totalCount += 1
      acc.matchedAmount += parseMoneyValue(match.matched_amount)
      acc.differenceAmount += parseMoneyValue(match.difference_amount)
      if (match.status === "confirmed") acc.confirmedCount += 1
      if (match.status === "confirmed_with_difference") acc.confirmedWithDifferenceCount += 1
      if (match.status === "reversed") acc.reversedCount += 1
      return acc
    },
    {
      totalCount: 0,
      confirmedCount: 0,
      confirmedWithDifferenceCount: 0,
      reversedCount: 0,
      matchedAmount: 0,
      differenceAmount: 0,
    },
  )
}

function matchPassesHistoryFilters(match: ReconciliationMatch, statusFilter: string, search: string) {
  if (statusFilter && match.status !== statusFilter) return false
  if (search.trim()) {
    const q = search.trim().toLowerCase()
    const haystack = [
      match.id,
      match.statement_line_id,
      match.financial_movement_id,
      match.match_type,
      match.status,
      match.confirmation_reason,
      match.reversed_reason,
      match.matched_amount,
      match.difference_amount,
    ]
      .join(" ")
      .toLowerCase()
    if (!haystack.includes(q)) return false
  }
  return true
}

function overviewEvidenceSheets(block: OverviewExportBlock, evidence: ReconciliationOverviewEvidence): ExportSheet[] {
  const sheets: ExportSheet[] = [{ name: "Resumo", rows: summaryRows(evidence.summary) }]
  if (block === "pending_statement_lines") {
    sheets.push({ name: "Linhas pendentes", rows: statementLinesRows(evidence.pending_statement_lines) })
  }
  if (block === "pending_financial_movements") {
    sheets.push({ name: "Movimentos pendentes", rows: movementRows(evidence.pending_financial_movements) })
  }
  if (block === "confirmed_matches") {
    sheets.push({ name: "Matches", rows: matchRows(evidence.confirmed_matches) })
  }
  if (block === "divergences") {
    sheets.push({ name: "Linhas divergentes", rows: statementLinesRows(evidence.divergent_statement_lines) })
    sheets.push({ name: "Movimentos divergentes", rows: movementRows(evidence.divergent_financial_movements) })
  }
  if (block === "ignored_statement_lines") {
    sheets.push({ name: "Linhas ignoradas", rows: statementLinesRows(evidence.ignored_statement_lines) })
  }
  return sheets
}

const TABS: Array<{ id: Tab; label: string; icon: ReactNode }> = [
  { id: "overview", label: "Visão geral", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "import", label: "Importar extrato", icon: <FileUp className="h-4 w-4" /> },
  { id: "lines", label: "Linhas do extrato", icon: <Database className="h-4 w-4" /> },
  { id: "match", label: "Conciliar", icon: <Link2 className="h-4 w-4" /> },
  { id: "matches", label: "Histórico", icon: <History className="h-4 w-4" /> },
]

export function ReconciliationPage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview")
  const { companyId, activeCompanyName, isCompanyResolved, companyError } = useActiveCompany()
  const [financialAccountId, setFinancialAccountId] = useState("")
  const [accounts, setAccounts] = useState<FinancialAccount[]>([])
  const [diagnostics, setDiagnostics] = useState<ReconciliationDiagnostics | null>(null)
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null)
  const [imports, setImports] = useState<BankStatementImport[]>([])
  const [lines, setLines] = useState<BankStatementLine[]>([])
  const [matches, setMatches] = useState<ReconciliationMatch[]>([])
  const [movements, setMovements] = useState<FinancialMovement[]>([])
  const [candidates, setCandidates] = useState<MovementCandidate[]>([])
  const [selectedLineId, setSelectedLineId] = useState("")
  const [selectedMovementId, setSelectedMovementId] = useState("")
  const [lineStatusFilter, setLineStatusFilter] = useState("pending")
  const [lineDateFrom, setLineDateFrom] = useState("")
  const [lineDateTo, setLineDateTo] = useState("")
  const [lineSearch, setLineSearch] = useState("")
  const [matchDateFilter, setMatchDateFilter] = useState("")
  const [matchSearch, setMatchSearch] = useState("")
  const [matchHistoryStatusFilter, setMatchHistoryStatusFilter] = useState("")
  const [matchHistorySearch, setMatchHistorySearch] = useState("")
  const [linePage, setLinePage] = useState(0)
  const [hasNextLinePage, setHasNextLinePage] = useState(false)
  const [matchPage, setMatchPage] = useState(0)
  const [hasNextMatchPage, setHasNextMatchPage] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [exportingOverviewBlock, setExportingOverviewBlock] = useState<OverviewExportBlock | null>(null)
  const [isExportingLines, setIsExportingLines] = useState(false)
  const [isExportingMatches, setIsExportingMatches] = useState(false)
  const [isImportingOfx, setIsImportingOfx] = useState(false)
  const [isImportingManual, setIsImportingManual] = useState(false)
  const [ofxInputKey, setOfxInputKey] = useState(0)
  const [ofxFile, setOfxFile] = useState<File | null>(null)
  const [ofxNotes, setOfxNotes] = useState("")
  const [importForm, setImportForm] = useState(makeManualImportDefaults)

  const selectedLine = useMemo(
    () => lines.find((line) => line.id === selectedLineId) ?? null,
    [lines, selectedLineId],
  )
  const selectedMovement = useMemo(
    () =>
      movements.find((m) => m.id === selectedMovementId) ??
      candidates.find((m) => m.id === selectedMovementId) ??
      null,
    [movements, candidates, selectedMovementId],
  )
  const selectedAccount = useMemo(
    () => accounts.find((account) => account.id === financialAccountId) ?? null,
    [accounts, financialAccountId],
  )
  const lineMetrics = useMemo(() => buildLineMetrics(lines), [lines])
  const filteredMatches = useMemo(
    () => matches.filter((match) => matchPassesHistoryFilters(match, matchHistoryStatusFilter, matchHistorySearch)),
    [matches, matchHistoryStatusFilter, matchHistorySearch],
  )
  const matchHistoryMetrics = useMemo(() => buildMatchHistoryMetrics(filteredMatches), [filteredMatches])

  const matchStatementLines = useMemo(() => {
    return lines.filter((line) => {
      if (!["pending", "divergent"].includes(line.status)) return false
      if (financialAccountId && line.financial_account_id !== financialAccountId) return false
      if (matchDateFilter && line.line_date !== matchDateFilter) return false
      if (matchSearch.trim()) {
        const q = matchSearch.trim().toLowerCase()
        const haystack = [
          line.description,
          line.external_id,
          line.bank_reference,
          line.counterparty_name,
        ]
          .join(" ")
          .toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [lines, financialAccountId, matchDateFilter, matchSearch])

  const matchMovements = useMemo(() => {
    const visible = movements.filter((movement) =>
      movementPassesReconciliationFilters(movement, financialAccountId, matchDateFilter, matchSearch),
    )
    const visibleIds = new Set(visible.map((movement) => movement.id))
    const suggested = candidates.filter((candidate) => {
      if (visibleIds.has(candidate.id)) return false
      return movementPassesReconciliationFilters(candidate, financialAccountId, matchDateFilter, matchSearch, {
        ignoreDate: true,
      })
    })
    return [...suggested, ...visible]
  }, [movements, candidates, financialAccountId, matchDateFilter, matchSearch])

  const amountDiff =
    selectedLine && selectedMovement
      ? Math.abs(Number(selectedLine.amount) - Number(selectedMovement.amount))
      : null
  const pairIssues = useMemo(() => {
    const issues: string[] = []
    if (!selectedLine || !selectedMovement) return issues
    if (selectedLine.financial_account_id !== selectedMovement.financial_account_id) {
      issues.push("Linha e movimento pertencem a contas financeiras diferentes.")
    }
    if (selectedLine.direction !== selectedMovement.direction) {
      issues.push("Linha e movimento possuem direções diferentes.")
    }
    if (!["pending", "divergent"].includes(selectedLine.status)) {
      issues.push("Linha do extrato não está pendente/divergente.")
    }
    if (selectedMovement.status !== "posted") {
      issues.push("Movimento financeiro não está postado.")
    }
    if (!["pending", "divergent"].includes(selectedMovement.reconciliation_status)) {
      issues.push("Movimento financeiro não está pendente/divergente para conciliação.")
    }
    if (amountDiff !== null && amountDiff > MATCH_TOLERANCE_AMOUNT) {
      issues.push(`Diferença acima da tolerância de ${money(MATCH_TOLERANCE_AMOUNT)}.`)
    }
    return issues
  }, [selectedLine, selectedMovement, amountDiff])
  const canConfirm = Boolean(selectedLine && selectedMovement && pairIssues.length === 0)
  const divergenceCount =
    (summary?.divergent_statement_lines ?? 0) + (summary?.divergent_financial_movements ?? 0)
  const canImportOfx = Boolean(financialAccountId && ofxFile && !isImportingOfx)
  const canImportManual = Boolean(
    financialAccountId &&
      importForm.source_id.trim() &&
      importForm.external_id.trim() &&
      importForm.line_date &&
      importForm.description.trim() &&
      isPositiveMoneyInput(importForm.amount) &&
      !isImportingManual,
  )

  async function loadAll(companyIdOverride = companyId) {
    if (!companyIdOverride || !isCompanyResolved) return
    setIsLoading(true)
    setNotice(null)
    try {
      const commonFilters = { financial_account_id: financialAccountId || undefined }
      const matchDateFilters = matchDateFilter ? { line_from: matchDateFilter, line_to: matchDateFilter } : {}
      const movementDateFilters = matchDateFilter
        ? { movement_from: matchDateFilter, movement_to: matchDateFilter }
        : {}
      const statementLineFilters = {
        line_from: lineDateFrom || undefined,
        line_to: lineDateTo || undefined,
        q: lineSearch.trim() || undefined,
      }

      const [
        diagnosticsResponse,
        summaryResponse,
        accountsResponse,
      ] = await Promise.all([
        getReconciliationDiagnostics(),
        getReconciliationSummary(companyIdOverride, commonFilters),
        listFinancialAccounts(companyIdOverride, { status: "active", limit: 200, offset: 0 }),
      ])
      let importsData: BankStatementImport[] = []
      let linesData: BankStatementLine[] = []
      let matchesData: ReconciliationMatch[] = []
      let movementsData: FinancialMovement[] = []

      if (activeTab === "overview" || activeTab === "import") {
        const importsResponse = await listStatementImports(companyIdOverride, {
          financial_account_id: financialAccountId || undefined,
          limit: String(PAGE_FETCH_LIMIT),
          offset: "0",
        })
        importsData = importsResponse.data.slice(0, PAGE_SIZE)
      }

      if (activeTab === "lines") {
        const linesResponse = await listStatementLines(companyIdOverride, {
          ...commonFilters,
          status: lineStatusFilter || undefined,
          ...statementLineFilters,
          limit: String(PAGE_FETCH_LIMIT),
          offset: String(linePage * PAGE_SIZE),
        })
        linesData = linesResponse.data.slice(0, PAGE_SIZE)
        setHasNextLinePage(linesResponse.data.length > PAGE_SIZE)
      } else if (activeTab === "match") {
        const matchLineFilters = {
          ...commonFilters,
          ...matchDateFilters,
          q: matchSearch.trim() || undefined,
          limit: String(PAGE_FETCH_LIMIT),
          offset: String(linePage * PAGE_SIZE),
        }
        const movementFilters = {
          status: "posted",
          financial_account_id: financialAccountId || undefined,
          q: matchSearch.trim() || undefined,
          ...movementDateFilters,
          limit: String(PAGE_FETCH_LIMIT),
          offset: "0",
        }
        const [linesResponse, pendingMovementsResponse, divergentMovementsResponse] = await Promise.all([
          listStatementLines(companyIdOverride, { ...matchLineFilters, statuses: "pending,divergent" }),
          listFinancialMovements(companyIdOverride, { ...movementFilters, reconciliation_status: "pending" }),
          listFinancialMovements(companyIdOverride, { ...movementFilters, reconciliation_status: "divergent" }),
        ])
        linesData = linesResponse.data.slice(0, PAGE_SIZE)
        movementsData = [...pendingMovementsResponse.data, ...divergentMovementsResponse.data]
          .sort((a, b) => `${b.movement_date}${b.created_at}`.localeCompare(`${a.movement_date}${a.created_at}`))
        setHasNextLinePage(linesResponse.data.length > PAGE_SIZE)
      } else {
        setHasNextLinePage(false)
      }

      if (activeTab === "matches") {
        const matchesResponse = await listReconciliationMatches(companyIdOverride, {
          financial_account_id: financialAccountId || undefined,
          status: matchHistoryStatusFilter || undefined,
          q: matchHistorySearch.trim() || undefined,
          limit: String(PAGE_FETCH_LIMIT),
          offset: String(matchPage * PAGE_SIZE),
        })
        matchesData = matchesResponse.data.slice(0, PAGE_SIZE)
        setHasNextMatchPage(matchesResponse.data.length > PAGE_SIZE)
      } else {
        setHasNextMatchPage(false)
      }

      setDiagnostics(diagnosticsResponse.data)
      setSummary(summaryResponse.data)
      setAccounts(accountsResponse.data)
      setImports(importsData)
      setLines(linesData)
      setMatches(matchesData)
      setMovements(movementsData)
      if (!financialAccountId && accountsResponse.data.length > 0)
        setFinancialAccountId(accountsResponse.data[0].id)
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao carregar conciliação.",
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!isCompanyResolved) return
    void loadAll(companyId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompanyResolved, companyId, financialAccountId, lineStatusFilter, lineDateFrom, lineDateTo, lineSearch, linePage, matchDateFilter, matchSearch, matchHistoryStatusFilter, matchHistorySearch, matchPage, activeTab])

  useEffect(() => {
    setLinePage(0)
  }, [activeTab, financialAccountId, lineStatusFilter, lineDateFrom, lineDateTo, lineSearch, matchDateFilter, matchSearch])

  useEffect(() => {
    setMatchPage(0)
  }, [activeTab, financialAccountId, matchHistoryStatusFilter, matchHistorySearch])

  async function handleManualImport() {
    if (!financialAccountId) {
      setNotice({ type: "error", message: "Selecione uma conta financeira antes de importar extrato." })
      return
    }
    if (!canImportManual) {
      setNotice({
        type: "error",
        message: "Preencha origem, external ID, data, descrição e valor maior que zero para importar a linha.",
      })
      return
    }
    setIsImportingManual(true)
    try {
      const payload = {
        company_id: companyId,
        financial_account_id: financialAccountId,
        source_type: "manual",
        source_id: importForm.source_id,
        file_name: importForm.file_name,
        statement_start_date: importForm.line_date,
        statement_end_date: importForm.line_date,
        closing_balance_amount: normalizeMoneyInput(importForm.closing_balance_amount),
        lines: [
          {
            external_id: importForm.external_id,
            line_date: importForm.line_date,
            direction: importForm.direction,
            amount: normalizeMoneyInput(importForm.amount),
            description: importForm.description,
            bank_reference: importForm.bank_reference,
          },
        ],
      }
      const response = await importBankStatement(payload)
      setNotice({
        type: "success",
        message: `Extrato manual importado com ${response.data.lines.length} linha(s).`,
      })
      setSelectedLineId(response.data.lines[0]?.id ?? "")
      setSelectedMovementId("")
      setCandidates([])
      setMatchDateFilter(response.data.lines[0]?.line_date ?? "")
      setImportForm(makeManualImportDefaults())
      setActiveTab("match")
      await loadAll()
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao importar extrato manual.",
      })
    } finally {
      setIsImportingManual(false)
    }
  }

  async function handleOfxImport() {
    if (!financialAccountId) {
      setNotice({ type: "error", message: "Selecione uma conta financeira antes de importar OFX." })
      return
    }
    if (!ofxFile) {
      setNotice({ type: "error", message: "Selecione um arquivo .ofx antes de importar." })
      return
    }
    setIsImportingOfx(true)
    try {
      const content = await readStatementFileContent(ofxFile)
      const response = await importOfxBankStatement({
        company_id: companyId,
        financial_account_id: financialAccountId,
        file_name: ofxFile.name,
        notes: ofxNotes || null,
        ofx_content: content,
      })
      setNotice({
        type: "success",
        message: `OFX importado com ${response.data.lines.length} linha(s). Nenhum saldo interno foi alterado.`,
      })
      setSelectedLineId(response.data.lines[0]?.id ?? "")
      setSelectedMovementId("")
      setCandidates([])
      setMatchDateFilter(response.data.lines[0]?.line_date ?? "")
      setOfxFile(null)
      setOfxNotes("")
      setOfxInputKey((value) => value + 1)
      setActiveTab("match")
      await loadAll()
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao importar OFX.",
      })
    } finally {
      setIsImportingOfx(false)
    }
  }

  async function handleSuggest(lineId = selectedLineId) {
    if (!lineId) {
      setNotice({ type: "error", message: "Selecione uma linha do extrato antes de buscar sugestões." })
      return
    }
    setSelectedMovementId("")
    try {
      const response = await suggestMatches(companyId, lineId)
      setCandidates(response.data.candidates)
      if (response.data.candidates.length > 0) setSelectedMovementId(response.data.candidates[0].id)
      setNotice({
        type: "success",
        message: `${response.data.candidates.length} sugestão(ões) encontradas.`,
      })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao buscar sugestões.",
      })
    }
  }

  async function handleConfirmMatch() {
    if (!selectedLineId || !selectedMovementId) {
      setNotice({ type: "error", message: "Selecione uma linha de extrato e um movimento financeiro." })
      return
    }
    if (pairIssues.length > 0) {
      setNotice({ type: "error", message: pairIssues.join(" ") })
      return
    }
    try {
      await confirmReconciliationMatch({
        company_id: companyId,
        statement_line_id: selectedLineId,
        financial_movement_id: selectedMovementId,
        match_type: "manual",
        tolerance_amount: "0.05",
        allow_difference: false,
      })
      setNotice({ type: "success", message: "Match confirmado. Linha e movimento marcados como conciliados." })
      setCandidates([])
      setSelectedLineId("")
      setSelectedMovementId("")
      await loadAll()
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao confirmar match.",
      })
    }
  }

  async function handleIgnore(lineId: string) {
    const reason = window.prompt("Motivo para ignorar esta linha de extrato:")
    if (!reason) return
    try {
      await ignoreStatementLine(lineId, reason)
      setNotice({ type: "success", message: "Linha de extrato ignorada com justificativa." })
      await loadAll()
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Erro ao ignorar linha." })
    }
  }

  async function handleReverseMatch(matchId: string) {
    const reason = window.prompt("Motivo para estornar o match:")
    if (!reason) return
    try {
      await reverseReconciliationMatch(matchId, reason)
      setNotice({ type: "success", message: "Match estornado. Linha e movimento voltaram para pendente." })
      await loadAll()
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao estornar match.",
      })
    }
  }

  async function handleOverviewExport(block: OverviewExportBlock) {
    if (!companyId) return
    setExportingOverviewBlock(block)
    try {
      const filters = { financial_account_id: financialAccountId || undefined, block }
      const response = await getReconciliationOverviewEvidence(companyId, filters)
      exportXlsxWorkbook(
        overviewEvidenceSheets(block, response.data),
        buildExportFileName(
          "kovir_conciliacao_bancaria",
          `visao_geral_${OVERVIEW_BLOCK_LABELS[block]}_${financialAccountId || "todas_contas"}`,
          "xlsx",
        ),
      )
      setNotice({ type: "success", message: `Relatório de ${OVERVIEW_BLOCK_LABELS[block].toLowerCase()} exportado.` })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar relatório da visão geral.",
      })
    } finally {
      setExportingOverviewBlock(null)
    }
  }

  async function handleLinesExport() {
    if (!companyId) return
    setIsExportingLines(true)
    try {
      const rows: BankStatementLine[] = []
      for (let offset = 0; offset < EXPORT_MAX_ROWS; offset += EXPORT_PAGE_SIZE) {
        const response = await listStatementLines(companyId, {
          financial_account_id: financialAccountId || undefined,
          status: lineStatusFilter || undefined,
          line_from: lineDateFrom || undefined,
          line_to: lineDateTo || undefined,
          q: lineSearch.trim() || undefined,
          limit: EXPORT_PAGE_SIZE,
          offset,
        })
        rows.push(...response.data)
        if (response.data.length < EXPORT_PAGE_SIZE) break
      }
      exportXlsxWorkbook(
        [
          { name: "Resumo", rows: statementLinesSummaryRows(rows) },
          { name: "Linhas do extrato", rows: statementLinesRows(rows) },
        ],
        buildExportFileName(
          "kovir_conciliacao_bancaria",
          `linhas_extrato_${lineStatusFilter || "todos"}_${financialAccountId || "todas_contas"}`,
          "xlsx",
        ),
      )
      setNotice({ type: "success", message: `Relatorio de linhas exportado com ${rows.length} registro(s).` })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar linhas do extrato.",
      })
    } finally {
      setIsExportingLines(false)
    }
  }
  async function handleMatchesExport() {
    if (!companyId) return
    setIsExportingMatches(true)
    try {
      const rows: ReconciliationMatch[] = []
      for (let offset = 0; offset < EXPORT_MAX_ROWS; offset += EXPORT_PAGE_SIZE) {
        const response = await listReconciliationMatches(companyId, {
          financial_account_id: financialAccountId || undefined,
          status: matchHistoryStatusFilter || undefined,
          q: matchHistorySearch.trim() || undefined,
          limit: EXPORT_PAGE_SIZE,
          offset,
        })
        rows.push(...response.data)
        if (response.data.length < EXPORT_PAGE_SIZE) break
      }
      exportXlsxWorkbook(
        [
          { name: "Resumo", rows: matchHistorySummaryRows(buildMatchHistoryMetrics(rows)) },
          { name: "Historico de matches", rows: matchRows(rows) },
        ],
        buildExportFileName(
          "kovir_conciliacao_bancaria",
          `historico_matches_${matchHistoryStatusFilter || "todos"}_${financialAccountId || "todas_contas"}`,
          "xlsx",
        ),
      )
      setNotice({ type: "success", message: `Historico exportado com ${rows.length} match(es).` })
    } catch (error) {
      setNotice({
        type: "error",
        message: error instanceof Error ? error.message : "Erro ao exportar historico de matches.",
      })
    } finally {
      setIsExportingMatches(false)
    }
  }
  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-[var(--color-primary)]">
              {activeCompanyName ?? "Conciliação Bancária"}
            </p>
            <h1 className="mt-1 text-3xl font-black tracking-tight text-[var(--color-text)]">
              Conciliação Bancária
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-muted)]">
              Importe extratos OFX ou lance linhas manualmente, depois vincule cada linha ao
              movimento financeiro correspondente no ERP.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {accounts.length > 0 && (
              <div className="min-w-[200px]">
                <select
                  value={financialAccountId}
                  onChange={(e) => setFinancialAccountId(e.target.value)}
                  className="field-input text-sm"
                >
                  <option value="">Todas as contas</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button
              type="button"
              onClick={() => void loadAll()}
              disabled={isLoading}
              className="inline-flex shrink-0 items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
              Atualizar
            </button>
          </div>
        </div>
      </header>

      {/* ── Notices ── */}
      {companyError ? (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-600">
          {companyError}
        </div>
      ) : null}
      {notice ? (
        <div
          className={`rounded-2xl border p-4 text-sm ${
            notice.type === "success"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
              : "border-red-500/30 bg-red-500/10 text-red-600"
          }`}
        >
          {notice.message}
        </div>
      ) : null}

      {/* ── Tab Navigation ── */}
      <nav className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2.5 text-sm font-bold transition ${
              activeTab === tab.id
                ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.id === "lines" && (summary?.pending_statement_lines ?? 0) > 0 && (
              <span className="ml-0.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-black text-white">
                {summary?.pending_statement_lines}
              </span>
            )}
            {tab.id === "match" && matchStatementLines.length > 0 && (
              <span className="ml-0.5 rounded-full bg-[var(--color-primary)] px-1.5 py-0.5 text-[10px] font-black text-white">
                {matchStatementLines.length}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* ══════════════════════════════ OVERVIEW ══════════════════════════════ */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          {/* Metrics */}
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <VibrantMetric
              accent="#d97706"
              icon={<FileSearch className="h-5 w-5" />}
              title="Linhas pendentes"
              value={summary?.pending_statement_lines ?? 0}
              helper={`${money(summary?.pending_statement_lines_amount)} aguardando match`}
              onExport={() => void handleOverviewExport("pending_statement_lines")}
              isExporting={exportingOverviewBlock === "pending_statement_lines"}
            />
            <VibrantMetric
              accent="#2563eb"
              icon={<ArrowRightLeft className="h-5 w-5" />}
              title="Movimentos pendentes"
              value={summary?.pending_financial_movements ?? 0}
              helper={`${money(summary?.pending_financial_movements_amount)} caixa interno`}
              onExport={() => void handleOverviewExport("pending_financial_movements")}
              isExporting={exportingOverviewBlock === "pending_financial_movements"}
            />
            <VibrantMetric
              accent="#16a34a"
              icon={<CheckCircle2 className="h-5 w-5" />}
              title="Matches confirmados"
              value={summary?.confirmed_matches ?? 0}
              helper={`${money(summary?.confirmed_matches_amount)} conciliados`}
              onExport={() => void handleOverviewExport("confirmed_matches")}
              isExporting={exportingOverviewBlock === "confirmed_matches"}
            />
            <VibrantMetric
              accent="#dc2626"
              icon={<AlertTriangle className="h-5 w-5" />}
              title="Divergências"
              value={divergenceCount}
              helper={`${money(summary?.confirmed_matches_difference_amount)} diferença em matches`}
              onExport={() => void handleOverviewExport("divergences")}
              isExporting={exportingOverviewBlock === "divergences"}
            />
            <VibrantMetric
              accent="#64748b"
              icon={<EyeOff className="h-5 w-5" />}
              title="Ignoradas"
              value={summary?.ignored_statement_lines ?? 0}
              helper={`${money(summary?.ignored_statement_lines_amount)} fora do match`}
              onExport={() => void handleOverviewExport("ignored_statement_lines")}
              isExporting={exportingOverviewBlock === "ignored_statement_lines"}
            />
          </section>

          {/* Process guide */}
          <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-lg shadow-[var(--color-card-shadow)]">
            <h2 className="mb-4 text-base font-black text-[var(--color-text)]">
              Como funciona a conciliação
            </h2>
            <div className="grid gap-3 md:grid-cols-3">
              {[
                {
                  step: "1",
                  icon: <FileUp className="h-5 w-5" />,
                  title: "Importe o extrato",
                  desc: "Faça upload do arquivo OFX do banco ou lance uma linha manual para cada transação.",
                  tab: "import" as Tab,
                },
                {
                  step: "2",
                  icon: <Database className="h-5 w-5" />,
                  title: "Veja as linhas",
                  desc: "Confira as linhas importadas e quais estão pendentes de conciliação.",
                  tab: "lines" as Tab,
                },
                {
                  step: "3",
                  icon: <Link2 className="h-5 w-5" />,
                  title: "Concilie",
                  desc: "Vincule cada linha do extrato ao movimento financeiro correspondente no ERP.",
                  tab: "match" as Tab,
                },
              ].map(({ step, icon, title, desc, tab }) => (
                <button
                  key={step}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left transition hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)]"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-primary)] text-sm font-black text-white">
                      {step}
                    </span>
                    <span className="text-[var(--color-primary)]">{icon}</span>
                  </div>
                  <p className="mt-3 font-bold text-[var(--color-text)]">{title}</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">{desc}</p>
                </button>
              ))}
            </div>
          </section>

          {/* Diagnostics */}
          {(diagnostics?.safety ?? []).length > 0 && (
            <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5">
              <h2 className="mb-3 text-base font-black text-[var(--color-text)]">
                Regras críticas do sistema
              </h2>
              <ul className="grid gap-2 md:grid-cols-2">
                {(diagnostics?.safety ?? []).map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2 rounded-xl bg-[var(--color-surface-elevated)] p-3 text-sm text-[var(--color-text-muted)]"
                  >
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-center text-xs text-[var(--color-text-muted)]">
            {imports.length} importação(ões) recentes · {summary?.pending_statement_lines ?? 0} linhas pendentes ·{" "}
            {summary?.pending_financial_movements ?? 0} movimentos pendentes
          </p>
        </div>
      )}

      {/* ══════════════════════════════ IMPORT ══════════════════════════════ */}
      {activeTab === "import" && (
        <div className="space-y-4">
          <section className="rounded-[2rem] border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-5">
            <div className="grid gap-4 lg:grid-cols-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">Conta selecionada</p>
                <p className="mt-1 text-lg font-black text-[var(--color-text)]">
                  {selectedAccount?.name ?? "Selecione uma conta"}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  A importação sempre pertence a uma conta financeira específica.
                </p>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">OFX</p>
                <p className="mt-1 text-lg font-black text-[var(--color-text)]">{ofxFile ? "Pronto" : "Aguardando arquivo"}</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Aceita OFX XML/SGML e leitura UTF-8/Windows-1252.
                </p>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">Linha manual</p>
                <p className="mt-1 text-lg font-black text-[var(--color-text)]">
                  {canImportManual ? money(importForm.amount) : "Pendente"}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Use apenas para ajuste operacional ou extrato sem OFX.
                </p>
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">Garantia operacional</p>
                <p className="mt-1 text-lg font-black text-[var(--color-text)]">Sem saldo interno</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Importar extrato cria evidência externa; não baixa título e não movimenta caixa.
                </p>
              </div>
            </div>
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            {/* OFX */}
            <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <h2 className="mb-4 flex items-center gap-2 text-base font-black text-[var(--color-text)]">
              <FileUp className="h-5 w-5 text-[var(--color-primary)]" />
              Importar OFX
            </h2>
            <div className="space-y-4">
              <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 text-sm text-[var(--color-primary)]">
                <p className="font-bold">O que o OFX faz:</p>
                <ul className="mt-2 space-y-1 text-xs">
                  <li>✓ Cria linhas de extrato para conciliação</li>
                  <li>✗ Não cria baixas nem altera títulos</li>
                  <li>✗ Não modifica saldos internos do ERP</li>
                </ul>
              </div>
              <div>
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Conta financeira
                </span>
                <select
                  value={financialAccountId}
                  onChange={(e) => setFinancialAccountId(e.target.value)}
                  className="field-input"
                >
                  <option value="">Selecione a conta…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Arquivo OFX
                </span>
                <input
                  key={ofxInputKey}
                  type="file"
                  accept=".ofx,.OFX,application/x-ofx,text/plain"
                  onChange={(e) => setOfxFile(e.target.files?.[0] ?? null)}
                  className="field-input"
                />
                {ofxFile && (
                  <div className="mt-2 flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    <span className="flex-1 truncate">
                      {ofxFile.name} ({(ofxFile.size / 1024).toFixed(1)} KB)
                    </span>
                    <button type="button" onClick={() => setOfxFile(null)}>
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
              <InputField label="Observação (opcional)" value={ofxNotes} onChange={setOfxNotes} />
              <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 text-xs text-[var(--color-text-muted)]">
                <p className="font-bold text-[var(--color-text)]">Prévia antes de importar</p>
                <p className="mt-1">Conta: {selectedAccount?.name ?? "não selecionada"}</p>
                <p>Arquivo: {ofxFile?.name ?? "nenhum arquivo selecionado"}</p>
                <p>Resultado esperado: linhas de extrato pendentes para conciliação.</p>
              </div>
              <button
                type="button"
                onClick={() => void handleOfxImport()}
                disabled={!canImportOfx}
                className="w-full rounded-2xl bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white disabled:opacity-50"
              >
                {isImportingOfx ? "Importando OFX..." : "Importar OFX"}
              </button>
            </div>
          </section>

            {/* Manual */}
            <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <h2 className="mb-4 flex items-center gap-2 text-base font-black text-[var(--color-text)]">
              <UploadCloud className="h-5 w-5 text-[var(--color-primary)]" />
              Lançar linha manual
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="md:col-span-2">
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Conta financeira
                </span>
                <select
                  value={financialAccountId}
                  onChange={(e) => setFinancialAccountId(e.target.value)}
                  className="field-input"
                >
                  <option value="">Selecione a conta…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <InputField
                label="ID de origem"
                value={importForm.source_id}
                onChange={(v) => setImportForm((p) => ({ ...p, source_id: v }))}
              />
              <InputField
                label="Arquivo / referência"
                value={importForm.file_name}
                onChange={(v) => setImportForm((p) => ({ ...p, file_name: v }))}
              />
              <InputField
                label="Saldo final externo"
                value={importForm.closing_balance_amount}
                onChange={(v) => setImportForm((p) => ({ ...p, closing_balance_amount: v }))}
                inputMode="decimal"
              />
              <InputField
                label="Data da linha"
                type="date"
                value={importForm.line_date}
                onChange={(v) => setImportForm((p) => ({ ...p, line_date: v }))}
              />
              <div>
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Direção
                </span>
                <select
                  value={importForm.direction}
                  onChange={(e) =>
                    setImportForm((p) => ({
                      ...p,
                      direction: e.target.value as "inflow" | "outflow",
                    }))
                  }
                  className="field-input"
                >
                  <option value="inflow">Entrada</option>
                  <option value="outflow">Saída</option>
                </select>
              </div>
              <InputField
                label="Valor"
                value={importForm.amount}
                onChange={(v) => setImportForm((p) => ({ ...p, amount: v }))}
                inputMode="decimal"
              />
              <InputField
                label="External ID"
                value={importForm.external_id}
                onChange={(v) => setImportForm((p) => ({ ...p, external_id: v }))}
              />
              <InputField
                label="Referência bancária"
                value={importForm.bank_reference}
                onChange={(v) => setImportForm((p) => ({ ...p, bank_reference: v }))}
              />
              <div className="md:col-span-2">
                <InputField
                  label="Descrição"
                  value={importForm.description}
                  onChange={(v) => setImportForm((p) => ({ ...p, description: v }))}
                />
              </div>
            </div>
            <div className="mt-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 text-xs text-[var(--color-text-muted)]">
              <p className="font-bold text-[var(--color-text)]">Prévia antes de importar</p>
              <p className="mt-1">Conta: {selectedAccount?.name ?? "não selecionada"}</p>
              <p>
                Linha: {directionLabel(importForm.direction)} de {money(importForm.amount)} em{" "}
                {importForm.line_date || "data não informada"}
              </p>
              <p>Origem: {importForm.source_id || "não informada"}</p>
            </div>
            <button
              type="button"
              onClick={() => void handleManualImport()}
              disabled={!canImportManual}
              className="mt-4 w-full rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)] disabled:opacity-50"
            >
              {isImportingManual ? "Importando linha..." : "Importar linha manual"}
            </button>
          </section>
          </div>
        </div>
      )}

      {/* ══════════════════════════════ LINES ══════════════════════════════ */}
      {activeTab === "lines" && (
        <section className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-base font-black text-[var(--color-text)]">
                <Database className="h-5 w-5 text-[var(--color-primary)]" />
                Linhas do extrato
              </h2>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                Lista de evidências externas importadas. Linha de extrato não é baixa, não é movimento e não altera saldo interno.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleLinesExport()}
              disabled={isExportingLines}
              className="inline-flex items-center gap-2 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm font-bold text-emerald-700 disabled:cursor-wait disabled:opacity-60"
            >
              <FileSpreadsheet className="h-4 w-4" />
              {isExportingLines ? "Exportando..." : "XLSX filtrado"}
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Linhas filtradas</p>
              <p className="mt-1 text-2xl font-black text-[var(--color-text)]">{lineMetrics.totalCount}</p>
              <p className="text-xs text-[var(--color-text-muted)]">{money(lineMetrics.totalAmount)} em valor absoluto</p>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Entradas no extrato</p>
              <p className="mt-1 text-2xl font-black text-emerald-700">{lineMetrics.inflowCount}</p>
              <p className="text-xs text-emerald-700/80">{money(lineMetrics.inflowAmount)}</p>
            </div>
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-red-600">Saídas no extrato</p>
              <p className="mt-1 text-2xl font-black text-red-600">{lineMetrics.outflowCount}</p>
              <p className="text-xs text-red-600/80">{money(lineMetrics.outflowAmount)}</p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Conta</p>
              <p className="mt-1 truncate text-lg font-black text-[var(--color-text)]">{selectedAccount?.name ?? "Todas"}</p>
              <p className="text-xs text-[var(--color-text-muted)]">Filtro explícito por conta financeira</p>
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
            <div className="grid gap-3 lg:grid-cols-[1.3fr_0.7fr_0.7fr_auto]">
              <div>
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Buscar linha
                </span>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
                  <input
                    value={lineSearch}
                    onChange={(event) => setLineSearch(event.target.value)}
                    placeholder="Descrição, external ID, referência ou contraparte..."
                    className="field-input pl-9"
                  />
                </div>
              </div>
              <InputField label="Data inicial" type="date" value={lineDateFrom} onChange={setLineDateFrom} />
              <InputField label="Data final" type="date" value={lineDateTo} onChange={setLineDateTo} />
              <div className="flex items-end">
                {(lineSearch || lineDateFrom || lineDateTo) && (
                  <button
                    type="button"
                    onClick={() => {
                      setLineSearch("")
                      setLineDateFrom("")
                      setLineDateTo("")
                    }}
                    className="inline-flex h-[46px] items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] px-4 text-sm font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  >
                    <X className="h-4 w-4" /> Limpar
                  </button>
                )}
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(
                [
                  ["pending", "Pendentes"],
                  ["matched", "Conciliadas"],
                  ["divergent", "Divergentes"],
                  ["ignored", "Ignoradas"],
                  ["", "Todas"],
                ] as [string, string][]
              ).map(([status, label]) => (
                <button
                  key={status || "all"}
                  type="button"
                  onClick={() => setLineStatusFilter(status)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${
                    lineStatusFilter === status
                      ? "bg-[var(--color-primary)] text-white"
                      : "border border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {lines.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-10 text-center">
              <Database className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-weak)]" />
              <p className="font-semibold text-[var(--color-text-muted)]">Nenhuma linha encontrada</p>
              <p className="mt-1 text-xs text-[var(--color-text-weak)]">
                Importe um extrato OFX ou lance uma linha manualmente para começar.
              </p>
              <button
                type="button"
                onClick={() => setActiveTab("import")}
                className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2.5 text-sm font-bold text-[var(--color-primary)]"
              >
                <FileUp className="h-4 w-4" /> Ir para Importar
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-[var(--color-border-soft)]">
              <table className="min-w-full divide-y divide-[var(--color-border-soft)] text-sm">
                <thead className="bg-[var(--color-surface-elevated)]">
                  <tr>
                    {["Data", "Conta", "Descrição", "Direção", "Valor", "Conciliado", "Status", "Origem", "Ação"].map((col) => (
                      <th
                        key={col}
                        className="px-4 py-3 text-left text-xs font-bold uppercase text-[var(--color-text-muted)]"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)]">
                  {lines.map((line) => (
                    <tr key={line.id} className="hover:bg-[var(--color-hover)]">
                      <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                        {formatDate(line.line_date)}
                      </td>
                      <td className="max-w-[180px] px-4 py-3">
                        <p className="truncate font-semibold text-[var(--color-text)]">
                          {accounts.find((account) => account.id === line.financial_account_id)?.name ?? line.financial_account_id}
                        </p>
                      </td>
                      <td className="max-w-[260px] px-4 py-3">
                        <p className="truncate font-medium text-[var(--color-text)]">
                          {line.description ?? line.external_id}
                        </p>
                        {line.bank_reference && (
                          <p className="truncate text-xs text-[var(--color-text-muted)]">
                            Ref: {line.bank_reference}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ${
                            line.direction === "inflow"
                              ? "bg-emerald-500/10 text-emerald-700"
                              : "bg-red-500/10 text-red-600"
                          }`}
                        >
                          {directionLabel(line.direction)}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-[var(--color-text)]">
                        {money(line.amount)}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                        {money(line.matched_amount)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold ${statusColor(line.status)}`}
                        >
                          {statusLabel(line.status)}
                        </span>
                      </td>
                      <td className="max-w-[220px] px-4 py-3 text-xs text-[var(--color-text-muted)]">
                        <p className="truncate">External ID: {line.external_id ?? "não informado"}</p>
                        <p className="truncate">Importação: {line.statement_import_id ?? "manual/sem lote"}</p>
                      </td>
                      <td className="px-4 py-3">
                        {["pending", "divergent"].includes(line.status) ? (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedLineId(line.id)
                                setSelectedMovementId("")
                                setCandidates([])
                                setMatchDateFilter(line.line_date)
                                setActiveTab("match")
                                void handleSuggest(line.id)
                              }}
                              className="inline-flex items-center gap-1 rounded-xl bg-[var(--color-primary)] px-3 py-1.5 text-xs font-bold text-white"
                            >
                              <Link2 className="h-3 w-3" /> Conciliar
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleIgnore(line.id)}
                              className="inline-flex items-center gap-1 rounded-xl border border-[var(--color-border-soft)] px-3 py-1.5 text-xs font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                            >
                              <EyeOff className="h-3 w-3" /> Ignorar
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-[var(--color-text-muted)]">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls
            page={linePage}
            hasNextPage={hasNextLinePage}
            loading={isLoading}
            onPrevious={() => setLinePage((current) => Math.max(0, current - 1))}
            onNext={() => setLinePage((current) => current + 1)}
          />
        </section>
      )}

      {/* ══════════════════════════════ MATCH ══════════════════════════════ */}
      {activeTab === "match" && (
        <div className="space-y-4">
          {/* ── Step indicator ── */}
          <div className="overflow-hidden rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)]">
            <div className="flex divide-x divide-[var(--color-border-soft)]">
              {[
                {
                  n: 1,
                  label: "Selecione a linha do extrato",
                  done: Boolean(selectedLineId),
                  active: !selectedLineId,
                },
                {
                  n: 2,
                  label: "Selecione o movimento do ERP",
                  done: Boolean(selectedMovementId),
                  active: Boolean(selectedLineId && !selectedMovementId),
                },
                {
                  n: 3,
                  label: "Confirme o match",
                  done: false,
                  active: canConfirm,
                },
              ].map(({ n, label, done, active }) => (
                <div
                  key={n}
                  className={`flex flex-1 items-center gap-2 px-4 py-3 text-sm font-semibold ${
                    done
                      ? "bg-emerald-500/10 text-emerald-700"
                      : active
                        ? "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                        : "text-[var(--color-text-muted)]"
                  }`}
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-black text-white ${
                      done
                        ? "bg-emerald-500"
                        : active
                          ? "bg-[var(--color-primary)]"
                          : "bg-[var(--color-text-weak)]"
                    }`}
                  >
                    {done ? "✓" : n}
                  </span>
                  <span className="hidden sm:inline">{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ── Filters ── */}
          <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-sm">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[160px]">
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Filtrar por dia
                </span>
                <input
                  type="date"
                  value={matchDateFilter}
                  onChange={(e) => setMatchDateFilter(e.target.value)}
                  className="field-input"
                />
              </div>
              <div className="min-w-[200px] flex-1">
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Buscar texto
                </span>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
                  <input
                    value={matchSearch}
                    onChange={(e) => setMatchSearch(e.target.value)}
                    placeholder="Descrição, referência..."
                    className="field-input pl-9"
                  />
                </div>
              </div>
              {(matchDateFilter || matchSearch) && (
                <button
                  type="button"
                  onClick={() => {
                    setMatchDateFilter("")
                    setMatchSearch("")
                  }}
                  className="inline-flex items-center gap-1 rounded-2xl border border-[var(--color-border-soft)] px-4 py-2.5 text-sm font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  <X className="h-4 w-4" /> Limpar filtros
                </button>
              )}
            </div>
          </section>

          <section className="rounded-[2rem] border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-sm font-black text-[var(--color-primary)]">Critérios de conciliação v1.0</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  A tela só confirma pares compatíveis. O backend continua sendo a validação definitiva.
                </p>
              </div>
              <div className="grid gap-2 text-xs font-semibold text-[var(--color-text-muted)] sm:grid-cols-2 lg:min-w-[640px]">
                <span>Mesma conta financeira</span>
                <span>Mesma direção de entrada/saída</span>
                <span>Linha pendente ou divergente</span>
                <span>Movimento postado e pendente/divergente</span>
                <span>Diferença máxima: {money(MATCH_TOLERANCE_AMOUNT)}</span>
                <span>Conciliar não cria baixa, movimento ou saldo</span>
              </div>
            </div>
          </section>

          {/* ── Two-panel selection ── */}
          <div className="grid gap-4 xl:grid-cols-2">
            {/* Left: Statement lines */}
            <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
              <h2 className="mb-3 flex items-center gap-2 text-base font-black text-[var(--color-text)]">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-primary)] text-xs font-black text-white">
                  1
                </span>
                Extrato bancário / OFX
                <span className="ml-auto rounded-full bg-[var(--color-surface-elevated)] px-2 py-0.5 text-xs font-bold text-[var(--color-text-muted)]">
                  {matchStatementLines.length}
                </span>
              </h2>
              <div className="grid max-h-[480px] gap-2 overflow-auto pr-1">
                {matchStatementLines.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-6 text-center text-sm text-[var(--color-text-muted)]">
                    Nenhuma linha pendente para os filtros atuais.
                  </div>
                ) : (
                  matchStatementLines.map((line) => (
                    <button
                      key={line.id}
                      type="button"
                      onClick={() => {
                        setSelectedLineId(line.id)
                        setSelectedMovementId("")
                        setCandidates([])
                        void handleSuggest(line.id)
                      }}
                      className={`rounded-2xl border p-4 text-left transition ${
                        selectedLineId === line.id
                          ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)] ring-2 ring-[var(--color-primary-soft)]"
                          : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] hover:border-[var(--color-primary-border)]"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                line.direction === "inflow"
                                  ? "bg-emerald-500/10 text-emerald-700"
                                  : "bg-red-500/10 text-red-600"
                              }`}
                            >
                              {directionLabel(line.direction)}
                            </span>
                            <span className="text-xs text-[var(--color-text-muted)]">
                              {line.line_date}
                            </span>
                          </div>
                          <p className="mt-1 truncate font-bold text-[var(--color-text)]">
                            {line.description ?? line.external_id}
                          </p>
                          {line.bank_reference && (
                            <p className="truncate text-xs text-[var(--color-text-muted)]">
                              Ref: {line.bank_reference}
                            </p>
                          )}
                        </div>
                        <span className="shrink-0 text-lg font-black text-[var(--color-text)]">
                          {money(line.amount)}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </section>

            {/* Right: Movements */}
            <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
              <h2 className="mb-3 flex items-center gap-2 text-base font-black text-[var(--color-text)]">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-black text-white ${selectedLineId ? "bg-[var(--color-primary)]" : "bg-[var(--color-text-weak)]"}`}
                >
                  2
                </span>
                Movimentos financeiros
                <span className="ml-auto rounded-full bg-[var(--color-surface-elevated)] px-2 py-0.5 text-xs font-bold text-[var(--color-text-muted)]">
                  {matchMovements.length}
                </span>
              </h2>
              {!selectedLineId && (
                <div className="mb-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
                  ← Selecione uma linha do extrato para ver sugestões de match.
                </div>
              )}
              {candidates.length > 0 && (
                <div className="mb-3 rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs text-[var(--color-primary)]">
                  {candidates.length} sugestão(ões) automática(s) — destacadas abaixo.
                </div>
              )}
              <div className="grid max-h-[480px] gap-2 overflow-auto pr-1">
                {matchMovements.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-6 text-center text-sm text-[var(--color-text-muted)]">
                    Nenhum movimento financeiro pendente/divergente para os filtros atuais.
                  </div>
                ) : (
                  matchMovements.map((movement) => {
                    const isCandidate = candidates.some((c) => c.id === movement.id)
                    const candidateScore = candidates.find((c) => c.id === movement.id)?.score
                    return (
                      <button
                        key={movement.id}
                        type="button"
                        disabled={!selectedLineId}
                        onClick={() => setSelectedMovementId(movement.id)}
                        className={`rounded-2xl border p-4 text-left transition ${
                          selectedMovementId === movement.id
                            ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)] ring-2 ring-[var(--color-primary-soft)]"
                            : isCandidate
                              ? "border-emerald-500/40 bg-emerald-500/5 hover:border-emerald-500/60"
                              : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] hover:border-[var(--color-primary-border)]"
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                  movement.direction === "inflow"
                                    ? "bg-emerald-500/10 text-emerald-700"
                                    : "bg-red-500/10 text-red-600"
                                }`}
                              >
                                {directionLabel(movement.direction)}
                              </span>
                              <span className="text-xs text-[var(--color-text-muted)]">
                                {movement.movement_date}
                              </span>
                              {isCandidate && candidateScore !== undefined && (
                                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-black text-emerald-700">
                                  {candidateScore}% match
                                </span>
                              )}
                            </div>
                            <p className="mt-1 truncate font-bold text-[var(--color-text)]">
                              {movement.description ?? movement.id}
                            </p>
                            <p className="truncate text-xs text-[var(--color-text-muted)]">
                              Baixa: {movement.settlement_id ?? "—"} · Título:{" "}
                              {movement.financial_title_id ?? "—"}
                            </p>
                          </div>
                          <span className="shrink-0 text-lg font-black text-[var(--color-text)]">
                            {money(movement.amount)}
                          </span>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </section>
          </div>

          <PaginationControls
            page={linePage}
            hasNextPage={hasNextLinePage}
            loading={isLoading}
            onPrevious={() => setLinePage((current) => Math.max(0, current - 1))}
            onNext={() => setLinePage((current) => current + 1)}
          />

          {/* ── Step 3: Confirm ── */}
          <section
            className={`rounded-[2rem] border p-5 shadow-xl shadow-[var(--color-card-shadow)] transition-all ${
              canConfirm
                ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)]"
                : "border-[var(--color-border-soft)] bg-[var(--color-surface)]"
            }`}
          >
            <h2
              className={`mb-4 flex items-center gap-2 text-base font-black ${canConfirm ? "text-[var(--color-primary)]" : "text-[var(--color-text)]"}`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-black text-white ${canConfirm ? "bg-[var(--color-primary)]" : "bg-[var(--color-text-weak)]"}`}
              >
                3
              </span>
              Confirmação do match
              {canConfirm && (
                <span className="ml-2 text-xs font-semibold opacity-80">
                  — pronto para confirmar
                </span>
              )}
            </h2>

            {canConfirm ? (
              <div className="space-y-4">
                {/* Pairing display */}
                <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr]">
                  <MatchCard
                    label="Linha do extrato"
                    date={selectedLine?.line_date ?? ""}
                    amount={money(selectedLine?.amount)}
                    description={selectedLine?.description ?? selectedLine?.id ?? ""}
                    direction={selectedLine?.direction}
                  />
                  <div className="flex items-center justify-center">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full ${
                        amountDiff !== null && amountDiff > MATCH_TOLERANCE_AMOUNT
                          ? "bg-amber-500/20 text-amber-700"
                          : "bg-emerald-500/20 text-emerald-700"
                      }`}
                    >
                      <ArrowRightLeft className="h-5 w-5" />
                    </div>
                  </div>
                  <MatchCard
                    label="Movimento financeiro"
                    date={selectedMovement?.movement_date ?? ""}
                    amount={money(selectedMovement?.amount)}
                    description={selectedMovement?.description ?? selectedMovement?.id ?? ""}
                  />
                </div>

                {amountDiff !== null && amountDiff > 0.01 && (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-700">
                    ⚠ Diferença de {money(amountDiff)} entre os valores — confirme apenas se
                    estiver correto.
                  </div>
                )}

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void handleSuggest()}
                    className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-surface)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]"
                  >
                    <Search className="h-4 w-4" /> Buscar sugestões
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleConfirmMatch()}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[var(--color-primary)] px-6 py-3 text-sm font-black text-white shadow-lg"
                  >
                    <CheckCircle2 className="h-5 w-5" /> Confirmar match
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 py-4 text-center">
                <Link2 className="h-8 w-8 text-[var(--color-text-weak)]" />
                <p className="text-sm text-[var(--color-text-muted)]">
                  Selecione uma linha do extrato (passo 1) e um movimento (passo 2) para habilitar
                  a confirmação.
                </p>
                {selectedLine && selectedMovement && pairIssues.length > 0 && (
                  <div className="w-full rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-left text-sm text-red-700">
                    <p className="mb-2 font-black">Match bloqueado por incompatibilidade:</p>
                    <ul className="space-y-1">
                      {pairIssues.map((issue) => (
                        <li key={issue}>- {issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => void handleSuggest()}
                  disabled={!selectedLineId}
                  className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2.5 text-sm font-bold text-[var(--color-text-muted)] disabled:opacity-40"
                >
                  <Search className="h-4 w-4" /> Buscar sugestões automáticas
                </button>
              </div>
            )}
          </section>
        </div>
      )}

      {/* ══════════════════════════════ HISTORY ══════════════════════════════ */}
      {activeTab === "matches" && (
        <section className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-base font-black text-[var(--color-text)]">
                <History className="h-5 w-5 text-[var(--color-primary)]" />
                Histórico de matches
              </h2>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                Evidência operacional de conciliações confirmadas, conciliadas com diferença e estornadas. Histórico não cria baixa, movimento ou saldo.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleMatchesExport()}
              disabled={isExportingMatches}
              className="inline-flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm font-bold text-emerald-700 disabled:cursor-wait disabled:opacity-60"
            >
              <FileSpreadsheet className="h-4 w-4" />
              {isExportingMatches ? "Exportando..." : "XLSX filtrado"}
            </button>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Matches filtrados</p>
              <p className="mt-1 text-2xl font-black text-[var(--color-text)]">{matchHistoryMetrics.totalCount}</p>
              <p className="text-xs text-[var(--color-text-muted)]">{money(matchHistoryMetrics.matchedAmount)} conciliados</p>
            </div>
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">Confirmados</p>
              <p className="mt-1 text-2xl font-black text-emerald-700">{matchHistoryMetrics.confirmedCount}</p>
              <p className="text-xs text-emerald-700/80">sem diferença registrada</p>
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-amber-700">Com diferença</p>
              <p className="mt-1 text-2xl font-black text-amber-700">{matchHistoryMetrics.confirmedWithDifferenceCount}</p>
              <p className="text-xs text-amber-700/80">{money(matchHistoryMetrics.differenceAmount)} de diferença</p>
            </div>
            <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4">
              <p className="text-xs font-bold uppercase tracking-wide text-red-600">Estornados</p>
              <p className="mt-1 text-2xl font-black text-red-600">{matchHistoryMetrics.reversedCount}</p>
              <p className="text-xs text-red-600/80">linha e movimento voltam ao fluxo</p>
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
            <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
              <div>
                <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
                  Buscar no histórico
                </span>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
                  <input
                    value={matchHistorySearch}
                    onChange={(event) => setMatchHistorySearch(event.target.value)}
                    placeholder="ID do match, linha, movimento, status, justificativa ou valor..."
                    className="field-input pl-9"
                  />
                </div>
              </div>
              {(matchHistorySearch || matchHistoryStatusFilter) && (
                <button
                  type="button"
                  onClick={() => {
                    setMatchHistorySearch("")
                    setMatchHistoryStatusFilter("")
                  }}
                  className="inline-flex h-[46px] items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] px-4 text-sm font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                >
                  <X className="h-4 w-4" /> Limpar
                </button>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(
                [
                  ["", "Todos"],
                  ["confirmed", "Confirmados"],
                  ["confirmed_with_difference", "Com diferença"],
                  ["reversed", "Estornados"],
                ] as const
              ).map(([status, label]) => (
                <button
                  key={status || "all"}
                  type="button"
                  onClick={() => setMatchHistoryStatusFilter(status)}
                  className={
                    "rounded-xl px-3 py-1.5 text-xs font-bold transition " +
                    (matchHistoryStatusFilter === status
                      ? "bg-[var(--color-primary)] text-white"
                      : "border border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]")
                  }
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 text-xs text-[var(--color-text-muted)]">
            <p className="font-bold text-[var(--color-text)]">Leitura correta do histórico</p>
            <p className="mt-1">
              Match confirmado marca a ligação entre extrato e movimento financeiro. Estorno desfaz essa ligação, mas não apaga baixa, movimento financeiro ou linha de extrato.
            </p>
          </div>

          {filteredMatches.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-10 text-center">
              <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-[var(--color-text-weak)]" />
              <p className="font-semibold text-[var(--color-text-muted)]">
                Nenhum match encontrado para os filtros atuais
              </p>
              <p className="mt-1 text-xs text-[var(--color-text-weak)]">
                Após conciliar linhas do extrato, os matches aparecem aqui com status, valores e datas.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-[var(--color-border-soft)]">
              <table className="min-w-full divide-y divide-[var(--color-border-soft)] text-sm">
                <thead className="bg-[var(--color-surface-elevated)]">
                  <tr>
                    {["Criado em", "Evento", "Conta", "Linha", "Movimento", "Tipo", "Valores", "Status", "Ação"].map((col) => (
                      <th
                        key={col}
                        className="px-4 py-3 text-left text-xs font-bold uppercase text-[var(--color-text-muted)]"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)]">
                  {filteredMatches.map((match) => (
                    <tr key={match.id} className="hover:bg-[var(--color-hover)]">
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--color-text-muted)]">
                        {formatDateTime(match.created_at)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--color-text-muted)]">
                        {match.status === "reversed"
                          ? formatDateTime(match.reversed_at)
                          : formatDateTime(match.confirmed_at)}
                      </td>
                      <td className="max-w-[180px] px-4 py-3">
                        <p className="truncate font-semibold text-[var(--color-text)]">
                          {accounts.find((account) => account.id === match.financial_account_id)?.name ?? match.financial_account_id}
                        </p>
                      </td>
                      <td className="max-w-[170px] px-4 py-3">
                        <p className="truncate font-mono text-xs text-[var(--color-text-muted)]">
                          {match.statement_line_id}
                        </p>
                      </td>
                      <td className="max-w-[170px] px-4 py-3">
                        <p className="truncate font-mono text-xs text-[var(--color-text-muted)]">
                          {match.financial_movement_id}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-xs font-bold uppercase text-[var(--color-text-muted)]">
                        {match.match_type}
                      </td>
                      <td className="min-w-[180px] px-4 py-3">
                        <p className="font-black text-[var(--color-text)]">{money(match.matched_amount)}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Extrato {money(match.line_amount)} · ERP {money(match.movement_amount)}
                        </p>
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Diferença {money(match.difference_amount)} · tolerância {money(match.tolerance_amount)}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={"inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold " + statusColor(match.status)}
                        >
                          {statusLabel(match.status)}
                        </span>
                        {(match.confirmation_reason || match.reversed_reason) && (
                          <p className="mt-1 max-w-[220px] truncate text-xs text-[var(--color-text-muted)]">
                            {match.status === "reversed" ? match.reversed_reason : match.confirmation_reason}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {match.status !== "reversed" ? (
                          <button
                            type="button"
                            onClick={() => void handleReverseMatch(match.id)}
                            className="inline-flex items-center gap-1 rounded-xl border border-red-500/30 px-3 py-1 text-xs font-bold text-red-600 hover:bg-red-500/10"
                          >
                            Estornar
                          </button>
                        ) : (
                          <span className="text-xs text-[var(--color-text-muted)]">Sem ação</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls
            page={matchPage}
            hasNextPage={hasNextMatchPage}
            loading={isLoading}
            onPrevious={() => setMatchPage((current) => Math.max(0, current - 1))}
            onNext={() => setMatchPage((current) => current + 1)}
          />
        </section>
      )}
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function VibrantMetric({
  accent,
  icon,
  title,
  value,
  helper,
  onExport,
  isExporting = false,
}: {
  accent: string
  icon: ReactNode
  title: string
  value: ReactNode
  helper?: string
  onExport?: () => void
  isExporting?: boolean
}) {
  return (
    <div className="rounded-[2rem] p-5 shadow-xl" style={{ background: accent }}>
      <div className="flex items-start justify-between gap-3 text-white/75">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-bold uppercase tracking-wide">{title}</span>
        </div>
        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-white transition hover:bg-white/25 disabled:cursor-wait disabled:opacity-60"
            title={`Baixar XLSX - ${title}`}
          >
            <FileSpreadsheet className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      <p className="mt-3 text-3xl font-black text-white">{value}</p>
      {helper && <p className="mt-1 text-xs text-white/65">{helper}</p>}
    </div>
  )
}

function PaginationControls({
  page,
  hasNextPage,
  loading,
  onPrevious,
  onNext,
}: {
  page: number
  hasNextPage: boolean
  loading: boolean
  onPrevious: () => void
  onNext: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)]">
      <span>Pagina {page + 1} com ate {PAGE_SIZE} registros. Exportacao busca ate {EXPORT_MAX_ROWS} linhas filtradas.</span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onPrevious}
          disabled={loading || page === 0}
          className="rounded-xl border border-[var(--color-border-soft)] px-3 py-1.5 font-bold text-[var(--color-text)] disabled:opacity-40"
        >
          Anterior
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={loading || !hasNextPage}
          className="rounded-xl border border-[var(--color-border-soft)] px-3 py-1.5 font-bold text-[var(--color-text)] disabled:opacity-40"
        >
          Proxima
        </button>
      </div>
    </div>
  )
}

function InputField({
  label,
  value,
  onChange,
  type = "text",
  inputMode,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  inputMode?: "none" | "text" | "tel" | "url" | "email" | "numeric" | "decimal" | "search"
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-[var(--color-text-muted)]">
        {label}
      </span>
      <input
        type={type}
        value={value}
        inputMode={inputMode}
        onChange={(e) => onChange(e.target.value)}
        className="field-input"
      />
    </label>
  )
}

function MatchCard({
  label,
  date,
  amount,
  description,
  direction,
}: {
  label: string
  date: string
  amount: string
  description: string
  direction?: string
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-surface)] p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">{label}</p>
      <p className="mt-1 text-2xl font-black text-[var(--color-text)]">{amount}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[var(--color-text)]">{description}</p>
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs text-[var(--color-text-muted)]">{date}</span>
        {direction && (
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
              direction === "inflow"
                ? "bg-emerald-500/10 text-emerald-700"
                : "bg-red-500/10 text-red-600"
            }`}
          >
            {directionLabel(direction)}
          </span>
        )}
      </div>
    </div>
  )
}
