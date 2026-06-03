import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, Banknote, CircleDollarSign, Clock3, Download, FilePlus2, Link2, RefreshCw, Search, XCircle } from "lucide-react"
import { dateCell, exportCsv, exportXlsx, moneyCell } from "../../lib/exportTable"

import { useActiveCompany } from "../../config/useActiveCompany"
import { ApiError } from "../../lib/api"
import { getParticipants } from "../participants/participantsApi"
import type { Participant } from "../participants/types"
import { listCostCenters, listFinancialAccounts, listFinancialCategories } from "../financial/financialApi"
import type { CostCenter, FinancialAccount, FinancialCategory } from "../financial/types"
import { getSales, getSalesPaymentMethods } from "../sales/salesApi"
import type { PaymentMethod, Sale } from "../sales/types"
import { cancelReceivableTitle, createReceivableTitle, generateReceivablesFromSale, getReceivablesSummary, listReceivableTitles } from "./accountsReceivableApi"
import type { ReceivableTitle, ReceivablesSummary } from "./types"
import { SearchableSelect } from "../../components/SearchableSelect"

type TabKey = "overview" | "list" | "create" | "fromSale"
type AgingKey = "current" | "overdue_1_30" | "overdue_31_60" | "overdue_61_90" | "overdue_90_plus"

const tabs: { key: TabKey; label: string; icon: ReactNode }[] = [
  { key: "overview", label: "Visao geral", icon: <CircleDollarSign className="h-4 w-4" /> },
  { key: "list", label: "Titulos", icon: <Banknote className="h-4 w-4" /> },
  { key: "create", label: "Novo titulo", icon: <FilePlus2 className="h-4 w-4" /> },
  { key: "fromSale", label: "Gerar por venda", icon: <Link2 className="h-4 w-4" /> },
]

const PAGE_SIZE = 20
const PAGE_FETCH_LIMIT = PAGE_SIZE + 1
const AUXILIARY_LIMIT = 200
const EXPORT_PAGE_SIZE = 200
const EXPORT_MAX_ROWS = 5000

type TitleFilterState = {
  status: string
  sourceType: string
  dueFrom: string
  dueTo: string
  search: string
}

const emptyTitleFilters: TitleFilterState = {
  status: "",
  sourceType: "",
  dueFrom: "",
  dueTo: "",
  search: "",
}
const agingLabels: Record<AgingKey, string> = {
  current: "A vencer",
  overdue_1_30: "Vencidos 1-30 dias",
  overdue_31_60: "Vencidos 31-60 dias",
  overdue_61_90: "Vencidos 61-90 dias",
  overdue_90_plus: "Vencidos acima de 90 dias",
}

function snapshotText(snapshot: Record<string, unknown> | null | undefined, key: string) {
  const value = snapshot?.[key]
  return typeof value === "string" && value.trim() ? value : null
}

function participantName(title: ReceivableTitle) {
  return snapshotText(title.participant_snapshot, "name") ?? title.participant_id
}

function titleOrigin(title: ReceivableTitle) {
  return title.document_reference ?? title.source_id ?? title.id
}

function saleParticipantName(sale: Sale) {
  return snapshotText(sale.participant_snapshot, "name") ?? sale.participant_id ?? "Sem participante"
}

function saleReference(sale: Sale) {
  return sale.sale_number_text ?? sale.id
}

function canCancelTitle(title: ReceivableTitle) {
  return ["open", "overdue"].includes(title.status) && Number(title.paid_amount) <= 0
}

function buildTitlesExportTable(rows: ReceivableTitle[]) {
  const header = [
    "ID",
    "Empresa",
    "Cliente / Origem",
    "Tipo",
    "Documento / Ref.",
    "Parcela",
    "Emissao",
    "Competencia",
    "Vencimento",
    "Previsao recebimento",
    "Valor bruto",
    "Desconto",
    "Juros",
    "Multa",
    "Taxa",
    "Valor liquido",
    "Valor recebido",
    "Valor aberto",
    "Status",
    "Cobranca",
    "Fiscal",
    "Forma de pagamento",
    "Conta prevista",
    "Categoria",
    "Centro de custo",
    "Origem",
    "ID origem",
    "Pedido",
    "Observacoes",
  ]
  const body = rows.map((title) => [
    title.id,
    title.company_id,
    participantName(title),
    title.title_type,
    titleOrigin(title),
    `${title.installment_number}/${title.installment_total}`,
    dateCell(title.issue_date),
    dateCell(title.competency_date),
    dateCell(title.due_date),
    dateCell(title.expected_payment_date),
    moneyCell(title.gross_amount),
    moneyCell(title.discount_amount),
    moneyCell(title.interest_amount),
    moneyCell(title.penalty_amount),
    moneyCell(title.fee_amount),
    moneyCell(title.net_amount),
    moneyCell(title.paid_amount),
    moneyCell(title.open_amount),
    statusLabel(title.status),
    collectionLabel(title.collection_status),
    fiscalLabel(title.fiscal_status),
    title.payment_method_name ?? title.payment_method_code ?? "",
    title.expected_financial_account_id ?? "",
    title.financial_category_id ?? "",
    title.cost_center_id ?? "",
    title.source_type,
    title.source_id,
    title.sale_id ?? "",
    title.notes ?? "",
  ])
  return [header, ...body]
}

function formatMoney(value?: string | null) {
  const number = Number(value ?? 0)
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isFinite(number) ? number : 0)
}

function formatDate(value?: string | null) {
  if (!value) return "-"
  const [year, month, day] = value.split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    open: "Em aberto",
    overdue: "Vencido",
    partially_received: "Parcial",
    received: "Recebido",
    cancelled: "Cancelado",
    written_off: "Perda",
    renegotiated: "Renegociado",
  }
  return labels[status] ?? status
}

function collectionLabel(status: string) {
  const labels: Record<string, string> = {
    not_started: "Nao iniciada",
    scheduled: "Agendada",
    reminder_sent: "Lembrete enviado",
    in_collection: "Em cobranca",
    promised: "Promessa",
    disputed: "Disputa",
    paused: "Pausada",
    closed: "Encerrada",
  }
  return labels[status] ?? status
}

function fiscalLabel(status: string) {
  const labels: Record<string, string> = {
    pending_document: "Documento pendente",
    linked: "Vinculado",
    not_required: "Nao requerido",
    divergent: "Divergente",
  }
  return labels[status] ?? status
}

function statusMetric(summary: ReceivablesSummary | null, status: string) {
  return summary?.by_status[status] ?? { count: 0, open_amount: "0", net_amount: "0", paid_amount: "0" }
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function parseMoneyInput(value: string) {
  const cleaned = value.replace(/R\$/gi, "").replace(/\s/g, "").trim()
  if (!cleaned) return 0
  const normalized = cleaned.includes(",")
    ? cleaned.replace(/\./g, "").replace(",", ".")
    : /^-?\d{1,3}(\.\d{3})+$/.test(cleaned)
      ? cleaned.replace(/\./g, "")
      : cleaned
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

function moneyPayload(value: string) {
  const parsed = parseMoneyInput(value)
  return Number.isFinite(parsed) ? parsed.toFixed(2) : value
}

function createDefaultForm() {
  const today = todayIso()
  return {
    participant_id: "",
    issue_date: today,
    competency_date: today,
    due_date: today,
    expected_payment_date: "",
    gross_amount: "0,00",
    discount_amount: "0,00",
    interest_amount: "0,00",
    penalty_amount: "0,00",
    fee_amount: "0,00",
    document_reference: "",
    payment_method_id: "",
    financial_category_id: "",
    cost_center_id: "",
    expected_financial_account_id: "",
    fiscal_status: "pending_document",
    notes: "",
  }
}

type NewTitleForm = ReturnType<typeof createDefaultForm>

function buildTitleRequestFilters(filters: TitleFilterState, page: number, limit = PAGE_FETCH_LIMIT) {
  return {
    status: filters.status || undefined,
    source_type: filters.sourceType || undefined,
    due_from: filters.dueFrom || undefined,
    due_to: filters.dueTo || undefined,
    q: filters.search.trim() || undefined,
    limit,
    offset: page * PAGE_SIZE,
  }
}

export function AccountsReceivablePage() {
  const { companyId, activeCompanyName, isCompanyResolved, companyError } = useActiveCompany()
  const [activeTab, setActiveTab] = useState<TabKey>("overview")
  const [titles, setTitles] = useState<ReceivableTitle[]>([])
  const [summary, setSummary] = useState<ReceivablesSummary | null>(null)
  const [participants, setParticipants] = useState<Participant[]>([])
  const [categories, setCategories] = useState<FinancialCategory[]>([])
  const [costCenters, setCostCenters] = useState<CostCenter[]>([])
  const [accounts, setAccounts] = useState<FinancialAccount[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [closedSales, setClosedSales] = useState<Sale[]>([])
  const [saleReceivableTitles, setSaleReceivableTitles] = useState<ReceivableTitle[]>([])
  const [statusFilter, setStatusFilter] = useState("")
  const [sourceTypeFilter, setSourceTypeFilter] = useState("")
  const [dueFromFilter, setDueFromFilter] = useState("")
  const [dueToFilter, setDueToFilter] = useState("")
  const [search, setSearch] = useState("")
  const [appliedFilters, setAppliedFilters] = useState<TitleFilterState>(emptyTitleFilters)
  const [listPage, setListPage] = useState(0)
  const [hasNextListPage, setHasNextListPage] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saleId, setSaleId] = useState("")
  const [generatedSaleTitles, setGeneratedSaleTitles] = useState<ReceivableTitle[]>([])
  const [form, setForm] = useState<NewTitleForm>(() => createDefaultForm())

  const loadTitlesPage = useCallback(async (page: number, filters: TitleFilterState) => {
    if (!companyId || !isCompanyResolved) return
    const [titlesRes, summaryRes] = await Promise.all([
      listReceivableTitles(companyId, buildTitleRequestFilters(filters, page)),
      getReceivablesSummary(companyId),
    ])
    setTitles(titlesRes.data.slice(0, PAGE_SIZE))
    setHasNextListPage(titlesRes.data.length > PAGE_SIZE)
    setSummary(summaryRes.data)
  }, [companyId, isCompanyResolved])

  const loadAuxData = useCallback(async () => {
    if (!companyId || !isCompanyResolved) return
    const [participantsRes, categoriesRes, costCentersRes, accountsRes, paymentMethodsRes, closedSalesRes] = await Promise.all([
      getParticipants({ company_id: companyId, status: "active", limit: AUXILIARY_LIMIT, offset: 0 }),
      listFinancialCategories(companyId, { status: "active", limit: AUXILIARY_LIMIT, offset: 0 }),
      listCostCenters(companyId, { status: "active", limit: AUXILIARY_LIMIT, offset: 0 }),
      listFinancialAccounts(companyId, { status: "active", limit: AUXILIARY_LIMIT, offset: 0 }),
      getSalesPaymentMethods({ company_id: companyId }),
      getSales({ company_id: companyId, status: "closed", limit: AUXILIARY_LIMIT, offset: 0 }),
    ])
    setParticipants(participantsRes.data)
    setCategories(categoriesRes.data)
    setCostCenters(costCentersRes.data)
    setAccounts(accountsRes.data)
    setPaymentMethods(paymentMethodsRes.data)
    setClosedSales(closedSalesRes.data)
  }, [companyId, isCompanyResolved])

  const loadData = useCallback(async (page = listPage, filters = appliedFilters, includeAux = false) => {
    if (!companyId || !isCompanyResolved) return
    setLoading(true)
    setError(null)
    try {
      await Promise.all([
        loadTitlesPage(page, filters),
        includeAux ? loadAuxData() : Promise.resolve(),
      ])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar Contas a Receber.")
    } finally {
      setLoading(false)
    }
  }, [appliedFilters, companyId, isCompanyResolved, listPage, loadAuxData, loadTitlesPage])

  useEffect(() => {
    void loadData(listPage, appliedFilters, listPage === 0)
  }, [appliedFilters, listPage, loadData])

  const loadSaleReceivableTitles = useCallback(async (nextSaleId: string) => {
    if (!companyId || !isCompanyResolved || !nextSaleId) {
      setSaleReceivableTitles([])
      return
    }
    try {
      const response = await listReceivableTitles(companyId, {
        sale_id: nextSaleId,
        source_type: "sale_payment_plan",
        limit: AUXILIARY_LIMIT,
        offset: 0,
      })
      setSaleReceivableTitles(response.data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar titulos do pedido selecionado.")
    }
  }, [companyId, isCompanyResolved])

  useEffect(() => {
    void loadSaleReceivableTitles(saleId)
  }, [loadSaleReceivableTitles, saleId])

  const safeListPage = listPage + 1
  const pagedTitles = titles

  const customerOptions = useMemo(() => participants.filter((participant) => ["customer", "marketplace", "gateway", "other"].includes(participant.participant_type)), [participants])
  const openStatus = statusMetric(summary, "open")
  const overdueStatus = statusMetric(summary, "overdue")
  const receivedStatus = statusMetric(summary, "received")
  const cancelledStatus = statusMetric(summary, "cancelled")
  const agingRows = (Object.keys(agingLabels) as AgingKey[]).map((key) => ({
    key,
    label: agingLabels[key],
    value: summary?.aging[key] ?? { count: 0, amount: "0" },
  }))
  const selectedCategory = categories.find((category) => category.id === form.financial_category_id)
  const grossPreview = parseMoneyInput(form.gross_amount)
  const discountPreview = parseMoneyInput(form.discount_amount)
  const interestPreview = parseMoneyInput(form.interest_amount)
  const penaltyPreview = parseMoneyInput(form.penalty_amount)
  const feePreview = parseMoneyInput(form.fee_amount)
  const moneyInputsValid = [grossPreview, discountPreview, interestPreview, penaltyPreview, feePreview].every(Number.isFinite)
  const netPreview = moneyInputsValid ? grossPreview - discountPreview + interestPreview + penaltyPreview - feePreview : Number.NaN
  const previewStatus = form.due_date && form.due_date < todayIso() ? "overdue" : "open"
  const categoryRequiresCostCenter = Boolean(selectedCategory?.requires_cost_center)
  const canCreateTitle = Boolean(
    !saving &&
    form.participant_id &&
    form.due_date &&
    moneyInputsValid &&
    grossPreview > 0 &&
    netPreview >= 0 &&
    (!categoryRequiresCostCenter || form.cost_center_id),
  )
  const saleOptions = closedSales.map((sale) => {
    const reference = saleReference(sale)
    const participant = saleParticipantName(sale)
    return {
      value: sale.id,
      label: reference,
      description: `${participant} - ${formatMoney(sale.receivable_total_amount)}`,
      keywords: [sale.id, sale.sale_number_text ?? "", participant, sale.status].filter(Boolean),
    }
  })
  const selectedSale = closedSales.find((sale) => sale.id === saleId) ?? null
  const selectedSaleTitles = saleReceivableTitles.filter((title) => title.sale_id === saleId)
  const selectedSaleExistingPlanIds = new Set(
    selectedSaleTitles
      .map((title) => title.sale_payment_plan_id)
      .filter((id): id is string => Boolean(id)),
  )
  const selectedSaleMissingPlans = selectedSale?.payment_plans.filter((plan) => !selectedSaleExistingPlanIds.has(plan.id)) ?? []
  const selectedSaleReceivableTotal = Number(selectedSale?.receivable_total_amount ?? 0)
  const canGenerateFromSale = Boolean(!saving && selectedSale && selectedSaleReceivableTotal > 0)

  function updateForm<K extends keyof NewTitleForm>(field: K, value: NewTitleForm[K]) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function handleApplyFilters() {
    const nextFilters = {
      status: statusFilter,
      sourceType: sourceTypeFilter,
      dueFrom: dueFromFilter,
      dueTo: dueToFilter,
      search,
    }
    setAppliedFilters(nextFilters)
    setListPage(0)
  }

  async function loadFilteredTitlesForExport() {
    if (!companyId) return []
    const rows: ReceivableTitle[] = []
    for (let offset = 0; offset < EXPORT_MAX_ROWS; offset += EXPORT_PAGE_SIZE) {
      const response = await listReceivableTitles(companyId, {
        ...buildTitleRequestFilters(appliedFilters, 0, EXPORT_PAGE_SIZE),
        offset,
      })
      rows.push(...response.data)
      if (response.data.length < EXPORT_PAGE_SIZE || rows.length >= EXPORT_MAX_ROWS) break
    }
    return rows.slice(0, EXPORT_MAX_ROWS)
  }

  async function handleExport(format: "xlsx" | "csv") {
    setExporting(true)
    setError(null)
    setMessage(null)
    try {
      const rows = await loadFilteredTitlesForExport()
      if (rows.length === 0) {
        setMessage("Nenhum titulo encontrado para exportar com o filtro atual.")
        return
      }
      const filename = `contas_receber_${new Date().toISOString().slice(0, 10)}`
      if (format === "xlsx") {
        exportXlsx(buildTitlesExportTable(rows), "Titulos a Receber", filename)
      } else {
        exportCsv(buildTitlesExportTable(rows), filename)
      }
      setMessage(`Exportacao gerada com ${rows.length} titulo(s).`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao exportar titulos a receber.")
    } finally {
      setExporting(false)
    }
  }

  async function handleCreate() {
    if (!canCreateTitle) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const paymentMethod = paymentMethods.find((method) => method.id === form.payment_method_id)
      await createReceivableTitle({
        company_id: companyId,
        participant_id: form.participant_id,
        title_type: "manual",
        source_type: "manual",
        issue_date: form.issue_date || null,
        competency_date: form.competency_date || null,
        due_date: form.due_date,
        expected_payment_date: form.expected_payment_date || null,
        gross_amount: moneyPayload(form.gross_amount),
        discount_amount: moneyPayload(form.discount_amount),
        interest_amount: moneyPayload(form.interest_amount),
        penalty_amount: moneyPayload(form.penalty_amount),
        fee_amount: moneyPayload(form.fee_amount),
        document_reference: form.document_reference || null,
        payment_method_id: form.payment_method_id || null,
        payment_method_code: paymentMethod?.code ?? null,
        financial_category_id: form.financial_category_id || null,
        cost_center_id: form.cost_center_id || null,
        expected_financial_account_id: form.expected_financial_account_id || null,
        fiscal_status: form.fiscal_status,
        notes: form.notes || null,
      })
      setMessage("Titulo a receber criado com sucesso.")
      setForm(createDefaultForm())
      await loadData(listPage, appliedFilters)
      setActiveTab("list")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao criar titulo a receber.")
    } finally {
      setSaving(false)
    }
  }

  async function handleGenerateFromSale() {
    if (!canGenerateFromSale) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      const response = await generateReceivablesFromSale(saleId)
      setGeneratedSaleTitles(response.data)
      setMessage(`${response.data.length} titulo(s) retornado(s) para ${selectedSale ? saleReference(selectedSale) : "pedido selecionado"}.`)
      await Promise.all([loadData(listPage, appliedFilters), loadSaleReceivableTitles(saleId)])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao gerar titulos pela venda.")
    } finally {
      setSaving(false)
    }
  }

  function handleViewSaleTitles() {
    if (!selectedSale) return
    const nextFilters = {
      status: "",
      sourceType: "sale_payment_plan",
      dueFrom: "",
      dueTo: "",
      search: saleReference(selectedSale),
    }
    setSourceTypeFilter("sale_payment_plan")
    setStatusFilter("")
    setDueFromFilter("")
    setDueToFilter("")
    setSearch(saleReference(selectedSale))
    setAppliedFilters(nextFilters)
    setListPage(0)
    setActiveTab("list")
  }

  async function handleCancel(title: ReceivableTitle) {
    const reason = window.prompt("Informe o motivo do cancelamento do titulo:")
    if (!reason) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      await cancelReceivableTitle(title.id, reason)
      setMessage("Titulo cancelado com rastreabilidade.")
      await loadData(listPage, appliedFilters)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao cancelar titulo.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Bloco 8</p>
            <h1 className="mt-2 text-3xl font-black text-[var(--color-text)]">Contas a Receber</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">
              Controle o direito financeiro de receber. Pedido fechado gera titulo; titulo ainda nao e baixa, caixa ou conciliacao.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="min-w-64 text-xs font-bold uppercase text-[var(--color-text-muted)]">Empresa da sessao
              <div className="mt-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm normal-case text-[var(--color-text)]">
                {activeCompanyName || "Empresa nao identificada"}
              </div>
              <span className="mt-1 block max-w-64 truncate text-[10px] normal-case text-[var(--color-text-muted)]">Escopo travado na empresa da sessao</span>
            </label>
            <button type="button" onClick={() => void loadData(listPage, appliedFilters, true)} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-5 py-3 text-sm font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Atualizar
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-black ${activeTab === tab.key ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"}`}>
            {tab.icon}{tab.label}
          </button>
        ))}
      </div>

      {companyError && <Notice tone="error" message={companyError} />}
      {error && <Notice tone="error" message={error} />}
      {message && <Notice tone="success" message={message} />}

      {activeTab === "overview" && (
        <div className="space-y-4">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric accent="#16a34a" icon={<Banknote className="h-5 w-5" />} title="Titulos em aberto" value={summary?.open_count ?? 0} helper={`${formatMoney(summary?.open_amount)} aguardando recebimento`} />
            <Metric accent="#2563eb" icon={<CircleDollarSign className="h-5 w-5" />} title="A receber ativo" value={formatMoney(summary?.open_amount)} helper={`${summary?.open_count ?? 0} titulo(s) ativos`} />
            <Metric accent="#d97706" icon={<AlertTriangle className="h-5 w-5" />} title="Titulos vencidos" value={summary?.overdue_count ?? 0} helper={`${formatMoney(summary?.overdue_amount)} em atraso`} />
            <Metric accent="#7c3aed" icon={<Clock3 className="h-5 w-5" />} title="Vence em 7 dias" value={summary?.due_next_7_count ?? 0} helper={`${formatMoney(summary?.due_next_7_amount)} proximos`} />
            <Metric accent="#0f766e" icon={<CircleDollarSign className="h-5 w-5" />} title="Recebidos" value={summary?.received_count ?? 0} helper={`${formatMoney(summary?.received_amount)} baixado no titulo`} />
            <Metric accent="#0891b2" icon={<Clock3 className="h-5 w-5" />} title="Parciais" value={summary?.partially_received_count ?? 0} helper={`${formatMoney(summary?.partially_received_open_amount)} ainda aberto`} />
            <Metric accent="#dc2626" icon={<XCircle className="h-5 w-5" />} title="Cancelados" value={summary?.cancelled_count ?? 0} helper={`${formatMoney(summary?.cancelled_amount)} retirado do aberto`} />
            <Metric accent="#4f46e5" icon={<AlertTriangle className="h-5 w-5" />} title="Vence em 30 dias" value={summary?.due_next_30_count ?? 0} helper={`${formatMoney(summary?.due_next_30_amount)} no horizonte`} />
          </section>

          <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <Panel title="Aging de recebiveis" subtitle={`Referencia: ${formatDate(summary?.as_of)}`} icon={<Clock3 className="h-5 w-5" />}>
              <div className="space-y-3">
                {agingRows.map((row) => (
                  <div key={row.key} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-black text-[var(--color-text)]">{row.label}</span>
                      <span className="text-sm font-black text-[var(--color-text)]">{row.value.count} - {formatMoney(row.value.amount)}</span>
                    </div>
                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--color-surface-elevated)]">
                      <div className="h-full rounded-full bg-[var(--color-primary)]" style={{ width: `${Math.min(100, Number(row.value.amount) / Math.max(Number(summary?.open_amount ?? 0), 1) * 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Resumo por status" subtitle="Leitura oficial do backend" icon={<Banknote className="h-5 w-5" />}>
              <div className="space-y-3 text-sm">
                <SummaryRow label="Em aberto" count={openStatus.count} amount={openStatus.open_amount} />
                <SummaryRow label="Vencido real" count={summary?.overdue_count ?? overdueStatus.count} amount={summary?.overdue_amount ?? overdueStatus.open_amount} />
                <SummaryRow label="Recebido" count={receivedStatus.count} amount={receivedStatus.paid_amount || receivedStatus.net_amount} />
                <SummaryRow label="Cancelado" count={cancelledStatus.count} amount={cancelledStatus.net_amount} />
                <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs leading-5 text-[var(--color-text-muted)]">
                  Titulo e direito financeiro. Baixa, movimento de caixa e conciliacao bancaria continuam sendo fatos separados.
                </div>
              </div>
            </Panel>
          </section>
        </div>
      )}

      {activeTab === "list" && (
        <Panel
          title="Titulos a receber"
          subtitle={titles.length > 0 ? `${titles.length} titulo${titles.length !== 1 ? "s" : ""} nesta pagina - pagina ${safeListPage}${hasNextListPage ? " com mais registros" : ""}` : undefined}
          icon={<Banknote className="h-5 w-5" />}
        >
          {/* -- Filtros + exportacao -- */}
          <div className="mb-4 flex flex-col gap-3">
            <div className="grid gap-3 xl:grid-cols-[1.4fr_180px_180px_180px_180px_auto]">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar por cliente, pedido, documento, origem ou observacao" className="w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] py-3 pl-11 pr-4 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary-soft)] placeholder:text-[var(--color-text-weak)]" />
              </label>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]">
                <option value="">Todos os status</option>
                <option value="open">Em aberto</option>
                <option value="overdue">Vencido real</option>
                <option value="partially_received">Recebido parcial</option>
                <option value="received">Recebido</option>
                <option value="cancelled">Cancelado</option>
              </select>
              <select value={sourceTypeFilter} onChange={(event) => setSourceTypeFilter(event.target.value)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]">
                <option value="">Todas as origens</option>
                <option value="sale_payment_plan">Pedido fechado</option>
                <option value="manual">Manual</option>
                <option value="marketplace_order">Marketplace</option>
                <option value="gateway_payment">Gateway</option>
                <option value="other">Outros</option>
              </select>
              <input type="date" value={dueFromFilter} onChange={(event) => setDueFromFilter(event.target.value)} aria-label="Vencimento inicial" className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]" />
              <input type="date" value={dueToFilter} onChange={(event) => setDueToFilter(event.target.value)} aria-label="Vencimento final" className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]" />
              <button type="button" onClick={handleApplyFilters} disabled={loading} className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] disabled:opacity-50">Filtrar</button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-[var(--color-text-muted)]">Exportar titulos filtrados sob demanda:</span>
              <button
                type="button"
                disabled={exporting}
                onClick={() => void handleExport("xlsx")}
                className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40"
              >
                <Download className="h-4 w-4" /> {exporting ? "Gerando..." : "XLSX"}
              </button>
              <button
                type="button"
                disabled={exporting}
                onClick={() => void handleExport("csv")}
                className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40"
              >
                <Download className="h-4 w-4" /> CSV
              </button>
              <span className="text-xs text-[var(--color-text-weak)]">Limite por exportacao: {EXPORT_MAX_ROWS} registros.</span>
            </div>
          </div>

          {/* -- Tabela -- */}
          <div className="overflow-x-auto rounded-3xl border border-[var(--color-border-soft)]">
            <table className="min-w-[1180px] divide-y divide-[var(--color-border-soft)] text-sm">
              <thead className="bg-[var(--color-surface-elevated)] text-left text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                <tr>
                  <th className="px-4 py-3">Cliente / origem</th>
                  <th className="px-4 py-3">Parcela</th>
                  <th className="px-4 py-3">Vencimento</th>
                  <th className="px-4 py-3 text-right">Bruto</th>
                  <th className="px-4 py-3 text-right">Recebido</th>
                  <th className="px-4 py-3 text-right">Aberto</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Forma / fiscal</th>
                  <th className="px-4 py-3 text-right">Acoes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border-soft)]">
                {pagedTitles.map((title) => (
                  <tr key={title.id} className="bg-[var(--color-surface)] align-top">
                    <td className="px-4 py-3">
                      <p className="font-black text-[var(--color-text)]">{participantName(title)}</p>
                      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{title.source_type} - {titleOrigin(title)}</p>
                      {title.sale_id ? <p className="mt-1 text-xs text-[var(--color-text-weak)]">Pedido: {title.sale_id}</p> : null}
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{title.installment_number}/{title.installment_total}</td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      <p>{formatDate(title.due_date)}</p>
                      {title.expected_payment_date ? <p className="mt-1 text-xs text-[var(--color-text-weak)]">prev. {formatDate(title.expected_payment_date)}</p> : null}
                    </td>
                    <td className="px-4 py-3 text-right font-black text-[var(--color-text)]">{formatMoney(title.gross_amount)}</td>
                    <td className="px-4 py-3 text-right font-black text-emerald-600">{formatMoney(title.paid_amount)}</td>
                    <td className="px-4 py-3 text-right font-black text-[var(--color-text)]">{formatMoney(title.open_amount)}</td>
                    <td className="px-4 py-3"><StatusPill status={title.status} /></td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      <p>{title.payment_method_name ?? title.payment_method_code ?? "Sem forma"}</p>
                      <p className="mt-1 text-xs text-[var(--color-text-weak)]">{fiscalLabel(title.fiscal_status)} - {collectionLabel(title.collection_status)}</p>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canCancelTitle(title) ? (
                        <button type="button" onClick={() => handleCancel(title)} className="inline-flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-black text-red-600"><XCircle className="h-4 w-4" /> Cancelar</button>
                      ) : title.status === "partially_received" ? (
                        <span className="text-xs font-semibold text-amber-600">Estorne a baixa antes</span>
                      ) : (
                        <span className="text-xs text-[var(--color-text-weak)]">-</span>
                      )}
                    </td>
                  </tr>
                ))}
                {titles.length === 0 && <tr><td colSpan={9} className="px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">Nenhum titulo encontrado para o filtro atual.</td></tr>}
              </tbody>
            </table>
          </div>

          {/* -- Paginacao -- */}
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <button type="button" disabled={loading || listPage === 0} onClick={() => setListPage((page) => Math.max(0, page - 1))} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40">Anterior</button>
            <span className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2 text-sm font-black text-[var(--color-text)]">Pagina {safeListPage}</span>
            <button type="button" disabled={loading || !hasNextListPage} onClick={() => setListPage((page) => page + 1)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40">Proxima</button>
          </div>
        </Panel>
      )}

      {activeTab === "create" && (
        <Panel title="Criar titulo manual" subtitle="Cria direito financeiro. Nao registra baixa, caixa ou conciliacao." icon={<FilePlus2 className="h-5 w-5" />}>
          <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Cliente/participante"><SearchableSelect value={form.participant_id} onChange={(v) => updateForm("participant_id", v)} placeholder="Buscar por nome ou CPF/CNPJ..." options={customerOptions.map((p) => ({ value: p.id, label: p.name, description: p.document ?? undefined, keywords: p.document ? [p.document] : [] }))} maxResults={10} /></Field>
              <Field label="Documento/referencia"><input value={form.document_reference} onChange={(event) => updateForm("document_reference", event.target.value)} className="field-input" placeholder="NF, contrato, acordo, pedido externo..." /></Field>
              <Field label="Emissao"><input type="date" value={form.issue_date} onChange={(event) => updateForm("issue_date", event.target.value)} className="field-input" /></Field>
              <Field label="Competencia"><input type="date" value={form.competency_date} onChange={(event) => updateForm("competency_date", event.target.value)} className="field-input" /></Field>
              <Field label="Vencimento"><input type="date" value={form.due_date} onChange={(event) => updateForm("due_date", event.target.value)} className="field-input" /></Field>
              <Field label="Previsao de recebimento"><input type="date" value={form.expected_payment_date} onChange={(event) => updateForm("expected_payment_date", event.target.value)} className="field-input" /></Field>
              <Field label="Valor bruto"><input value={form.gross_amount} onChange={(event) => updateForm("gross_amount", event.target.value)} inputMode="decimal" className="field-input" placeholder="R$ 1.000,00" /></Field>
              <Field label="Desconto"><input value={form.discount_amount} onChange={(event) => updateForm("discount_amount", event.target.value)} inputMode="decimal" className="field-input" placeholder="0,00" /></Field>
              <Field label="Juros"><input value={form.interest_amount} onChange={(event) => updateForm("interest_amount", event.target.value)} inputMode="decimal" className="field-input" placeholder="0,00" /></Field>
              <Field label="Multa"><input value={form.penalty_amount} onChange={(event) => updateForm("penalty_amount", event.target.value)} inputMode="decimal" className="field-input" placeholder="0,00" /></Field>
              <Field label="Taxa"><input value={form.fee_amount} onChange={(event) => updateForm("fee_amount", event.target.value)} inputMode="decimal" className="field-input" placeholder="0,00" /></Field>
              <Field label="Forma de pagamento"><select value={form.payment_method_id} onChange={(event) => updateForm("payment_method_id", event.target.value)} className="field-input"><option value="">Sem forma definida</option>{paymentMethods.map((method) => <option key={method.id} value={method.id}>{method.name}</option>)}</select></Field>
              <Field label="Categoria financeira"><select value={form.financial_category_id} onChange={(event) => updateForm("financial_category_id", event.target.value)} className="field-input"><option value="">Sem categoria</option>{categories.filter((category) => category.status === "active" && (category.category_type === "income" || category.category_type === "other")).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Field>
              <Field label="Centro de custo"><select value={form.cost_center_id} onChange={(event) => updateForm("cost_center_id", event.target.value)} className="field-input"><option value="">Sem centro de custo</option>{costCenters.filter((center) => center.status === "active" && center.is_analytical).map((center) => <option key={center.id} value={center.id}>{center.name}</option>)}</select>{categoryRequiresCostCenter && !form.cost_center_id ? <span className="mt-1 block text-xs font-semibold text-amber-600">Categoria exige centro de custo.</span> : null}</Field>
              <Field label="Conta prevista"><select value={form.expected_financial_account_id} onChange={(event) => updateForm("expected_financial_account_id", event.target.value)} className="field-input"><option value="">Sem conta prevista</option>{accounts.filter((account) => account.status === "active").map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></Field>
              <Field label="Status fiscal"><select value={form.fiscal_status} onChange={(event) => updateForm("fiscal_status", event.target.value)} className="field-input"><option value="pending_document">Documento pendente</option><option value="not_required">Nao requerido</option><option value="linked">Vinculado</option><option value="divergent">Divergente</option></select></Field>
              <label className="md:col-span-2"><span className="text-sm font-semibold text-[var(--color-text-muted)]">Observacao</span><textarea value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} className="field-input mt-2 min-h-28" placeholder="Contexto operacional do titulo manual." /></label>
            </div>

            <aside className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-5">
              <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Previa antes de criar</p>
              <div className="mt-4 space-y-3 text-sm">
                <PreviewRow label="Bruto" value={moneyInputsValid ? formatMoney(String(grossPreview)) : "Valor invalido"} />
                <PreviewRow label="Desconto" value={moneyInputsValid ? formatMoney(String(discountPreview)) : "Valor invalido"} />
                <PreviewRow label="Acrescimos" value={moneyInputsValid ? formatMoney(String(interestPreview + penaltyPreview)) : "Valor invalido"} />
                <PreviewRow label="Taxas" value={moneyInputsValid ? formatMoney(String(feePreview)) : "Valor invalido"} />
                <div className="border-t border-[var(--color-border-soft)] pt-3">
                  <PreviewRow label="Liquido aberto" value={moneyInputsValid ? formatMoney(String(netPreview)) : "Valor invalido"} strong />
                  <PreviewRow label="Status inicial" value={statusLabel(previewStatus)} />
                  <PreviewRow label="Vencimento" value={formatDate(form.due_date)} />
                </div>
              </div>
              {!moneyInputsValid ? <p className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-xs font-semibold text-red-600">Revise os valores monetarios.</p> : null}
              {moneyInputsValid && netPreview < 0 ? <p className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-xs font-semibold text-red-600">Valor liquido nao pode ser negativo.</p> : null}
              <p className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs leading-5 text-[var(--color-text-muted)]">Este cadastro gera apenas o titulo. O recebimento deve ser feito em Caixa e Baixas.</p>
              <button type="button" onClick={handleCreate} disabled={!canCreateTitle} className="mt-5 w-full rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50">{saving ? "Criando..." : "Criar titulo"}</button>
            </aside>
          </div>
        </Panel>
      )}

      {activeTab === "fromSale" && (
        <Panel title="Gerar titulos por venda fechada" subtitle="Reprocessa pedidos fechados sem duplicar parcelas ja existentes." icon={<Link2 className="h-5 w-5" />}>
          <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <Field label="Pedido fechado">
                <SearchableSelect
                  value={saleId}
                  onChange={(value) => {
                    setSaleId(value)
                    setGeneratedSaleTitles([])
                  }}
                  placeholder="Buscar por PED, cliente ou identificador..."
                  emptyMessage="Nenhum pedido fechado encontrado."
                  options={saleOptions}
                  maxResults={12}
                />
              </Field>

              {!selectedSale ? (
                <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-5 text-sm leading-6 text-[var(--color-text-muted)]">
                  Selecione uma venda com status fechado. Pedidos em rascunho, orcamento, cancelados ou pagos nao entram nesta rotina.
                </div>
              ) : (
                <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-5">
                  <div className="grid gap-3 md:grid-cols-4">
                    <PreviewRow label="Pedido" value={saleReference(selectedSale)} strong />
                    <PreviewRow label="Cliente" value={saleParticipantName(selectedSale)} strong />
                    <PreviewRow label="A receber" value={formatMoney(selectedSale.receivable_total_amount)} strong />
                    <PreviewRow label="Planos" value={`${selectedSale.payment_plans.length}`} strong />
                  </div>
                  <div className="mt-5 overflow-x-auto rounded-2xl border border-[var(--color-border-soft)]">
                    <table className="min-w-[760px] divide-y divide-[var(--color-border-soft)] text-sm">
                      <thead className="bg-[var(--color-surface-elevated)] text-left text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                        <tr>
                          <th className="px-4 py-3">Parcela</th>
                          <th className="px-4 py-3">Forma</th>
                          <th className="px-4 py-3">Vencimento</th>
                          <th className="px-4 py-3 text-right">Valor</th>
                          <th className="px-4 py-3">Situacao</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border-soft)]">
                        {selectedSale.payment_plans.map((plan, index) => {
                          const exists = selectedSaleExistingPlanIds.has(plan.id)
                          return (
                            <tr key={plan.id} className="bg-[var(--color-surface)]">
                              <td className="px-4 py-3 font-black text-[var(--color-text)]">{index + 1}/{selectedSale.payment_plans.length}</td>
                              <td className="px-4 py-3 text-[var(--color-text-muted)]">{plan.payment_method_name ?? plan.payment_method_code}</td>
                              <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatDate(plan.due_date)}</td>
                              <td className="px-4 py-3 text-right font-black text-[var(--color-text)]">{formatMoney(plan.amount)}</td>
                              <td className="px-4 py-3">
                                <span className={`rounded-full border px-3 py-1 text-xs font-black ${exists ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-700" : "border-amber-500/50 bg-amber-500/15 text-amber-600"}`}>
                                  {exists ? "Titulo existente" : "Pendente gerar"}
                                </span>
                              </td>
                            </tr>
                          )
                        })}
                        {selectedSale.payment_plans.length === 0 ? <tr><td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">Venda fechada sem plano de pagamento.</td></tr> : null}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {selectedSaleTitles.length > 0 ? (
                <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5">
                  <h3 className="text-sm font-black uppercase tracking-wide text-[var(--color-primary)]">Titulos ja vinculados a este pedido</h3>
                  <div className="mt-4 overflow-x-auto rounded-2xl border border-[var(--color-border-soft)]">
                    <table className="min-w-[760px] divide-y divide-[var(--color-border-soft)] text-sm">
                      <thead className="bg-[var(--color-surface-elevated)] text-left text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                        <tr>
                          <th className="px-4 py-3">Titulo</th>
                          <th className="px-4 py-3">Parcela</th>
                          <th className="px-4 py-3">Vencimento</th>
                          <th className="px-4 py-3 text-right">Aberto</th>
                          <th className="px-4 py-3">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border-soft)]">
                        {selectedSaleTitles.map((title) => (
                          <tr key={title.id} className="bg-[var(--color-surface)]">
                            <td className="px-4 py-3 font-black text-[var(--color-text)]">{titleOrigin(title)}</td>
                            <td className="px-4 py-3 text-[var(--color-text-muted)]">{title.installment_number}/{title.installment_total}</td>
                            <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatDate(title.due_date)}</td>
                            <td className="px-4 py-3 text-right font-black text-[var(--color-text)]">{formatMoney(title.open_amount)}</td>
                            <td className="px-4 py-3"><StatusPill status={title.status} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              {generatedSaleTitles.length > 0 ? (
                <div className="rounded-3xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-5">
                  <h3 className="text-sm font-black uppercase tracking-wide text-[var(--color-primary)]">Resultado da ultima geracao</h3>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {generatedSaleTitles.map((title) => (
                      <div key={title.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
                        <p className="font-black text-[var(--color-text)]">{titleOrigin(title)}</p>
                        <p className="mt-1 text-sm text-[var(--color-text-muted)]">Parcela {title.installment_number}/{title.installment_total} - vence {formatDate(title.due_date)}</p>
                        <p className="mt-2 text-lg font-black text-[var(--color-text)]">{formatMoney(title.open_amount)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <aside className="h-fit rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-5">
              <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Controle da operacao</p>
              <div className="mt-4 space-y-3 text-sm">
                <PreviewRow label="Pedidos fechados carregados" value={`${closedSales.length}`} />
                <PreviewRow label="Titulos existentes do pedido" value={`${selectedSaleTitles.length}`} />
                <PreviewRow label="Parcelas pendentes" value={`${selectedSaleMissingPlans.length}`} />
                <PreviewRow label="Valor a receber" value={selectedSale ? formatMoney(selectedSale.receivable_total_amount) : "-"} strong />
              </div>
              {selectedSale && selectedSaleReceivableTotal <= 0 ? (
                <p className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs font-semibold text-amber-700">Venda fechada sem valor a receber. Nenhum titulo deve ser criado.</p>
              ) : null}
              <p className="mt-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-3 text-xs leading-5 text-[var(--color-text-muted)]">
                Esta rotina cria ou retorna titulos de Contas a Receber. Ela nao registra baixa, movimento de caixa nem conciliacao bancaria.
              </p>
              <button type="button" onClick={handleGenerateFromSale} disabled={!canGenerateFromSale} className="mt-5 w-full rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50">
                {saving ? "Processando..." : selectedSaleMissingPlans.length > 0 ? "Gerar titulos faltantes" : "Recarregar titulos"}
              </button>
              <button type="button" onClick={handleViewSaleTitles} disabled={!selectedSale} className="mt-3 w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-5 py-3 text-sm font-black text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-50">
                Ver titulos deste pedido
              </button>
            </aside>
          </div>
        </Panel>
      )}
    </div>
  )
}

function Metric({ title, value, helper, accent, icon }: { title: string; value: string | number; helper: string; accent: string; icon?: ReactNode }) {
  return (
    <article className="min-w-0 rounded-3xl p-5 shadow-xl shadow-[var(--color-card-shadow)]" style={{ background: accent, border: `1px solid ${accent}` }}>
      {icon && <span className="text-white/60">{icon}</span>}
      <p className="mt-3 text-xs font-bold uppercase tracking-wide text-white/75">{title}</p>
      <p className="mt-2 break-words text-3xl font-black text-white">{value}</p>
      <p className="mt-1 text-xs text-white/65">{helper}</p>
    </article>
  )
}

function SummaryRow({ label, count, amount }: { label: string; count: number; amount: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
      <span className="font-bold text-[var(--color-text-muted)]">{label}</span>
      <span className="text-right font-black text-[var(--color-text)]">{count} - {formatMoney(amount)}</span>
    </div>
  )
}

function Panel({ title, subtitle, icon, children }: { title: string; subtitle?: string; icon: ReactNode; children: ReactNode }) {
  return <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-2xl shadow-[var(--color-card-shadow)]"><div className="mb-5 flex items-center gap-3"><span className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-2 text-[var(--color-primary)]">{icon}</span><div><h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>{subtitle ? <p className="text-sm text-[var(--color-text-muted)]">{subtitle}</p> : null}</div></div>{children}</section>
}

function PreviewRow({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[var(--color-text-muted)]">{label}</span>
      <span className={strong ? "text-lg font-black text-[var(--color-text)]" : "font-bold text-[var(--color-text)]"}>{value}</span>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label><span className="text-sm font-semibold text-[var(--color-text-muted)]">{label}</span><div className="mt-2">{children}</div></label>
}

function StatusPill({ status }: { status: string }) {
  const cls =
    status === "overdue"   ? "border-amber-500/50 bg-amber-500/15 text-amber-600" :
    status === "cancelled" ? "border-red-500/50 bg-red-500/15 text-red-600" :
    status === "received"  ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-700" :
                             "border-blue-500/50 bg-blue-500/15 text-blue-600"
  return <span className={`rounded-full border px-3 py-1 text-xs font-black ${cls}`}>{statusLabel(status)}</span>
}

function Notice({ tone, message }: { tone: "success" | "error"; message: string }) {
  const cls = tone === "success"
    ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
    : "border-red-500/50 bg-red-500/10 text-red-600"
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${cls}`}>{message}</div>
}
