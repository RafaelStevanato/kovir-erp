import { useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, ClipboardList, CreditCard, FolderTree, Landmark, Layers3, LockKeyhole, RefreshCw, Save, Tags } from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import { ApiError } from "../../lib/api"
import {
  createChartAccount,
  createCostCenter,
  createFinancialAccount,
  createFinancialCategory,
  createFinancialDefaults,
  createPaymentTerm,
  getFinancialDiagnostics,
  listChartAccounts,
  listCostCenters,
  listFinancialAccounts,
  listFinancialCategories,
  listFinancialPeriodClosures,
  listPaymentTerms,
  updateChartAccount,
  updateCostCenter,
  updateFinancialAccount,
  updateFinancialCategory,
  updatePaymentTerm,
} from "./financialApi"
import type { ChartAccount, CostCenter, FinancialAccount, FinancialCategory, FinancialDiagnostics, FinancialPeriodClosure, PaymentTerm } from "./types"

type TabKey = "overview" | "chart" | "categories" | "costCenters" | "accounts" | "terms"

const tabs: { key: TabKey; label: string; icon: ReactNode }[] = [
  { key: "overview",    label: "Visão geral",        icon: <Layers3 className="h-4 w-4" /> },
  { key: "chart",       label: "Plano de contas",    icon: <FolderTree className="h-4 w-4" /> },
  { key: "categories",  label: "Categorias",          icon: <Tags className="h-4 w-4" /> },
  { key: "costCenters", label: "Centros de custo",   icon: <ClipboardList className="h-4 w-4" /> },
  { key: "accounts",    label: "Contas financeiras", icon: <Landmark className="h-4 w-4" /> },
  { key: "terms",       label: "Condições",           icon: <CreditCard className="h-4 w-4" /> },
]

const SECTION_PAGE_SIZE = 50
const SECTION_FETCH_LIMIT = SECTION_PAGE_SIZE + 1

const typeLabels: Record<string, string> = {
  asset: "Ativo", liability: "Passivo", equity: "Patrimônio",
  revenue: "Receita", cost: "Custo", expense: "Despesa",
  tax: "Tributo", income: "Entrada", fee: "Taxa",
  deduction: "Dedução", transfer: "Transferência",
  administrative: "Administrativo", commercial: "Comercial",
  financial: "Financeiro", technology: "Tecnologia",
  marketplace: "Marketplace", store: "Loja", project: "Projeto",
  logistics: "Logística", bank_account: "Conta bancária",
  cash: "Caixa físico", gateway: "Gateway",
  digital_wallet: "Carteira digital", credit_card: "Cartão",
  cpf: "CPF", cnpj: "CNPJ", email: "E-mail", phone: "Telefone", random: "Aleatoria",
  cash_term: "À vista", installments: "Parcelado",
  recurring: "Recorrente", custom: "Personalizado", other: "Outro",
  debit: "Devedor", credit: "Credor",
  draft: "Rascunho", active: "Ativo", inactive: "Inativo",
  blocked: "Bloqueado", archived: "Arquivado",
  operating_inflows: "Operacional - entradas",
  operating_outflows: "Operacional - saídas",
  investing_inflows: "Investimento - entradas",
  investing_outflows: "Investimento - saídas",
  financing_inflows: "Financiamento - entradas",
  financing_outflows: "Financiamento - saídas",
  transfers: "Transferências",
}

function labelFor(value?: string | null) {
  if (!value) return "Não informado"
  return typeLabels[value] ?? value
}

function formatMoney(value?: string | null) {
  const number = Number(value ?? 0)
  if (Number.isNaN(number)) return "R$ 0,00"
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(number)
}

function formatDate(value?: string | null) {
  if (!value) return "não informado"
  const [year, month, day] = value.slice(0, 10).split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function defaultCashFlowGroupForCategoryType(categoryType: string) {
  if (categoryType === "income") return "operating_inflows"
  if (categoryType === "transfer") return "transfers"
  return "operating_outflows"
}

function firstPageRows<T>(rows: T[]) {
  return rows.slice(0, SECTION_PAGE_SIZE)
}

function hasNextSectionPage<T>(rows: T[]) {
  return rows.length > SECTION_PAGE_SIZE
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "Erro inesperado."
}

export function FinancialMasterDataPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview")
  const { companyId, activeCompanyName, isCompanyResolved, companyError } = useActiveCompany()
  const [chartAccounts, setChartAccounts] = useState<ChartAccount[]>([])
  const [categories, setCategories] = useState<FinancialCategory[]>([])
  const [costCenters, setCostCenters] = useState<CostCenter[]>([])
  const [accounts, setAccounts] = useState<FinancialAccount[]>([])
  const [terms, setTerms] = useState<PaymentTerm[]>([])
  const [diagnostics, setDiagnostics] = useState<FinancialDiagnostics | null>(null)
  const [periodClosures, setPeriodClosures] = useState<FinancialPeriodClosure[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function loadData() {
    if (!companyId || !isCompanyResolved) return
    setLoading(true)
    setError(null)
    try {
      const [diagnosticsResponse, closuresResponse, chartResponse, categoryResponse, costCenterResponse, accountResponse, termResponse] = await Promise.all([
        getFinancialDiagnostics(companyId),
        listFinancialPeriodClosures(companyId),
        listChartAccounts(companyId),
        listFinancialCategories(companyId),
        listCostCenters(companyId),
        listFinancialAccounts(companyId),
        listPaymentTerms(companyId),
      ])
      setDiagnostics(diagnosticsResponse.data)
      setPeriodClosures(closuresResponse.data)
      setChartAccounts(chartResponse.data)
      setCategories(categoryResponse.data)
      setCostCenters(costCenterResponse.data)
      setAccounts(accountResponse.data)
      setTerms(termResponse.data)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!isCompanyResolved) return
    void loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCompanyResolved, companyId])

  async function handleCreateDefaults() {
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      await createFinancialDefaults(companyId)
      setSuccess("Cadastros financeiros padrão criados ou preservados com sucesso.")
      await loadData()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const fallbackTotals = useMemo(() => ({
    chart_accounts: chartAccounts.length,
    financial_categories: categories.length,
    cost_centers: costCenters.length,
    financial_accounts: accounts.length,
    payment_terms: terms.length,
  }), [chartAccounts.length, categories.length, costCenters.length, accounts.length, terms.length])

  const fallbackActiveTotals = useMemo(() => ({
    chart_accounts: chartAccounts.filter((row) => row.status === "active").length,
    financial_categories: categories.filter((row) => row.status === "active").length,
    cost_centers: costCenters.filter((row) => row.status === "active").length,
    financial_accounts: accounts.filter((row) => row.status === "active").length,
    payment_terms: terms.filter((row) => row.status === "active").length,
  }), [chartAccounts, categories, costCenters, accounts, terms])

  const totals = diagnostics?.records_count ?? fallbackTotals
  const activeTotals = diagnostics?.active_records_count ?? fallbackActiveTotals
  const readinessIssues = useMemo(() => {
    const issues: { title: string; description: string; critical: boolean }[] = []
    if ((activeTotals.chart_accounts ?? 0) === 0) {
      issues.push({ title: "Plano de contas sem registro ativo", description: "Cadastre contas analíticas para classificar títulos, baixas e movimentos.", critical: true })
    }
    if ((activeTotals.financial_categories ?? 0) === 0) {
      issues.push({ title: "Categorias financeiras ausentes", description: "Receitas, custos, despesas e taxas ficam sem classificação operacional.", critical: true })
    }
    if ((activeTotals.financial_accounts ?? 0) === 0) {
      issues.push({ title: "Nenhuma conta financeira ativa", description: "Baixas e movimentos precisam de caixa, banco, gateway ou carteira ativa.", critical: true })
    }
    if ((activeTotals.payment_terms ?? 0) === 0) {
      issues.push({ title: "Condições de pagamento ausentes", description: "Pedidos fechados não têm base operacional clara para vencimento e parcelas.", critical: true })
    }
    if ((activeTotals.cost_centers ?? 0) === 0) {
      issues.push({ title: "Centro de custo não configurado", description: "A análise gerencial por área/projeto ficará limitada.", critical: false })
    }
    return issues
  }, [activeTotals])

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Bloco 7 — Cadastros Financeiros Base</p>
            <h1 className="mt-2 text-3xl font-black text-[var(--color-text)]">Financeiro</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="min-w-64 text-xs font-bold uppercase text-[var(--color-text-muted)]">Empresa da sessão
              <div className="mt-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm normal-case text-[var(--color-text)]">
                {activeCompanyName || "Empresa não identificada"}
              </div>
              <span className="mt-1 block max-w-64 truncate text-[10px] normal-case text-[var(--color-text-muted)]">Escopo travado na empresa da sessão</span>
            </label>
            <button type="button" onClick={loadData} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              <RefreshCw className="h-4 w-4" /> Atualizar
            </button>
            <button type="button" onClick={handleCreateDefaults} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" /> Criar padrões
            </button>
          </div>
        </div>
      </header>

      {companyError && <Alert tone="error" message={companyError} />}
      {error && <Alert tone="error" message={error} />}
      {success && <Alert tone="success" message={success} />}

      <nav className="flex gap-2 overflow-x-auto rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2 shadow-xl shadow-[var(--color-card-shadow)]">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`inline-flex shrink-0 items-center gap-2 rounded-2xl px-4 py-3 text-sm font-bold transition ${
              activeTab === tab.key
                ? "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            }`}
          >
            {tab.icon}{tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "overview" && (
        <section className="space-y-5">
          <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-5">
            <Metric accent="#16a34a" icon={<FolderTree className="h-5 w-5" />} title="Plano de contas" value={totals.chart_accounts ?? 0} helper={`${activeTotals.chart_accounts ?? 0} ativo(s)`} />
            <Metric accent="#2563eb" icon={<Tags className="h-5 w-5" />} title="Categorias" value={totals.financial_categories ?? 0} helper={`${activeTotals.financial_categories ?? 0} ativa(s)`} />
            <Metric accent="#7c3aed" icon={<ClipboardList className="h-5 w-5" />} title="Centros de custo" value={totals.cost_centers ?? 0} helper={`${activeTotals.cost_centers ?? 0} ativo(s)`} />
            <Metric accent="#d97706" icon={<Landmark className="h-5 w-5" />} title="Contas financeiras" value={totals.financial_accounts ?? 0} helper={`${activeTotals.financial_accounts ?? 0} ativa(s)`} />
            <Metric accent="#0891b2" icon={<CreditCard className="h-5 w-5" />} title="Condições" value={totals.payment_terms ?? 0} helper={`${activeTotals.payment_terms ?? 0} ativa(s)`} />
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <article className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
              <div className="flex items-start gap-3">
                <span className={`rounded-2xl p-3 ${readinessIssues.some((issue) => issue.critical) ? "bg-red-500/10 text-red-500" : "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"}`}>
                  {readinessIssues.some((issue) => issue.critical) ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
                </span>
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Prontidão operacional</p>
                  <h2 className="mt-1 text-xl font-black text-[var(--color-text)]">
                    {readinessIssues.length === 0 ? "Base mínima pronta" : "Base financeira exige revisão"}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
                    Esta leitura usa contagem consolidada do backend por empresa. Listas paginadas da tela não são usadas como total oficial.
                  </p>
                </div>
              </div>

              {readinessIssues.length === 0 ? (
                <div className="mt-5 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 text-sm font-semibold text-[var(--color-primary)]">
                  Plano, categorias, centros, contas e condições possuem registros ativos para operar vendas, caixa e relatórios.
                </div>
              ) : (
                <div className="mt-5 grid gap-3">
                  {readinessIssues.map((issue) => (
                    <div key={issue.title} className={`rounded-2xl border p-4 ${issue.critical ? "border-red-500/30 bg-red-500/10" : "border-amber-500/30 bg-amber-500/10"}`}>
                      <p className="text-sm font-black text-[var(--color-text)]">{issue.title}</p>
                      <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{issue.description}</p>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
              <div className="flex items-start gap-3">
                <span className="rounded-2xl bg-[var(--color-primary-soft)] p-3 text-[var(--color-primary)]">
                  <LockKeyhole className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Períodos fechados</p>
                  <h2 className="mt-1 text-xl font-black text-[var(--color-text)]">{periodClosures.length} ativo(s)</h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
                    Fechamentos ativos bloqueiam alterações em competência/período fechado nos módulos financeiros integrados.
                  </p>
                </div>
              </div>
              <div className="mt-5 space-y-2">
                {periodClosures.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-4 text-sm text-[var(--color-text-muted)]">Nenhum período fechado ativo.</p>
                ) : (
                  periodClosures.slice(0, 5).map((closure) => (
                    <div key={closure.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                      <p className="text-sm font-black text-[var(--color-text)]">{formatDate(closure.start_date)} a {formatDate(closure.end_date)}</p>
                      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{closure.reason || "Sem justificativa informada."}</p>
                    </div>
                  ))
                )}
              </div>
            </article>
          </div>
        </section>
      )}

      {activeTab === "chart"       && <ChartAccountSection rows={chartAccounts} onCreated={loadData} companyId={companyId} />}
      {activeTab === "categories"  && <CategorySection rows={categories} onCreated={loadData} companyId={companyId} chartAccounts={chartAccounts} />}
      {activeTab === "costCenters" && <CostCenterSection rows={costCenters} onCreated={loadData} companyId={companyId} />}
      {activeTab === "accounts"    && <AccountSection rows={accounts} onCreated={loadData} companyId={companyId} />}
      {activeTab === "terms"       && <TermSection rows={terms} onCreated={loadData} companyId={companyId} />}
    </div>
  )
}

function Alert({ tone, message }: { tone: "success" | "error"; message: string }) {
  const cls = tone === "success"
    ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
    : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-danger)]"
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${cls}`}>{message}</div>
}

function Metric({ title, value, helper, accent, icon }: { title: string; value: string | number; helper: string; accent: string; icon?: ReactNode }) {
  return (
    <article className="rounded-3xl p-5 shadow-xl shadow-[var(--color-card-shadow)]" style={{ background: accent, border: `1px solid ${accent}` }}>
      {icon && <span className="text-white/60">{icon}</span>}
      <p className="mt-3 text-xs font-bold uppercase tracking-wide text-white/75">{title}</p>
      <p className="mt-2 text-3xl font-black text-white">{value}</p>
      <p className="mt-1 text-xs text-white/65">{helper}</p>
    </article>
  )
}

function SectionShell({ title, description, form, table }: { title: string; description: string; form: ReactNode; table: ReactNode }) {
  return (
    <section className="grid gap-5 xl:grid-cols-[1fr_1.5fr]">
      <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        <h2 className="text-xl font-black text-[var(--color-text)]">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">{description}</p>
        {form}
      </div>
      <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        {table}
      </div>
    </section>
  )
}

function Field({ label, value, onChange, type = "text", placeholder }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string }) {
  return (
    <label className="block text-sm font-semibold text-[var(--color-text-muted)]">
      {label}
      <input
        value={value}
        type={type}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary-soft)]"
      />
    </label>
  )
}

function TextareaField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="block text-sm font-semibold text-[var(--color-text-muted)]">
      {label}
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-24 w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary-soft)]"
      />
    </label>
  )
}

function CheckboxField({ label, checked, onChange, disabled = false }: { label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <label className={`flex items-center gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] ${disabled ? "opacity-60" : ""}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-[var(--color-primary)]"
      />
      {label}
    </label>
  )
}

function SelectField({ label, value, onChange, options, disabled = false }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; disabled?: boolean }) {
  return (
    <label className="block text-sm font-semibold text-[var(--color-text-muted)]">
      {label}
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] disabled:opacity-60"
      >
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  )
}

function PaginationControls({
  page,
  hasNext,
  loading,
  onPrev,
  onNext,
}: {
  page: number
  hasNext: boolean
  loading: boolean
  onPrev: () => void
  onNext: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
      <span>Pagina {page + 1} - {SECTION_PAGE_SIZE} registros por pagina</span>
      <div className="flex gap-2">
        <button type="button" onClick={onPrev} disabled={loading || page === 0} className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-40">
          Anterior
        </button>
        <button type="button" onClick={onNext} disabled={loading || !hasNext} className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-40">
          Proxima
        </button>
      </div>
    </div>
  )
}

function ChartAccountSection({ rows, companyId, onCreated }: { rows: ChartAccount[]; companyId: string; onCreated: () => Promise<void> }) {
  const [sectionRows, setSectionRows] = useState<ChartAccount[]>(() => firstPageRows(rows))
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(() => hasNextSectionPage(rows))
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [accountType, setAccountType] = useState("expense")
  const [parentId, setParentId] = useState("")
  const [isAnalytical, setIsAnalytical] = useState(true)
  const [acceptsEntries, setAcceptsEntries] = useState(true)
  const [normalBalance, setNormalBalance] = useState("")
  const [status, setStatus] = useState("active")
  const [notes, setNotes] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [localSuccess, setLocalSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    setSectionRows(firstPageRows(rows))
    setHasNextPage(hasNextSectionPage(rows))
    setPage(0)
  }, [rows])

  const accountById = useMemo(() => new Map(sectionRows.map((row) => [row.id, row])), [sectionRows])
  const parentOptions = useMemo(() => sectionRows
    .filter((row) => row.id !== editingId && row.status === "active" && !row.is_analytical && !row.accepts_entries)
    .map((row) => ({ value: row.id, label: `${row.code} — ${row.name}` })), [sectionRows, editingId])

  function resetForm() {
    setCode("")
    setName("")
    setAccountType("expense")
    setParentId("")
    setIsAnalytical(true)
    setAcceptsEntries(true)
    setNormalBalance("")
    setStatus("active")
    setNotes("")
    setEditingId(null)
  }

  function startEdit(row: ChartAccount) {
    setEditingId(row.id)
    setCode(row.code)
    setName(row.name)
    setAccountType(row.account_type)
    setParentId(row.parent_id ?? "")
    setIsAnalytical(row.is_analytical)
    setAcceptsEntries(row.accepts_entries)
    setNormalBalance(row.normal_balance ?? "")
    setStatus(row.status)
    setNotes(row.notes ?? "")
    setLocalError(null)
    setLocalSuccess(null)
  }

  async function refreshFilteredRows(nextPage = 0) {
    setLocalError(null)
    setFilterLoading(true)
    try {
      const response = await listChartAccounts(companyId, {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        account_type: typeFilter || undefined,
        limit: SECTION_FETCH_LIMIT,
        offset: nextPage * SECTION_PAGE_SIZE,
      })
      setSectionRows(firstPageRows(response.data))
      setHasNextPage(hasNextSectionPage(response.data))
      setPage(nextPage)
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setFilterLoading(false)
    }
  }

  function updateIsAnalytical(value: boolean) {
    setIsAnalytical(value)
    if (!value) setAcceptsEntries(false)
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setLocalError(null)
    setLocalSuccess(null)
    try {
      const payload = {
        code,
        name,
        account_type: accountType,
        parent_id: parentId || null,
        is_analytical: isAnalytical,
        normal_balance: normalBalance || null,
        accepts_entries: acceptsEntries,
        status,
        notes: notes || null,
      }
      if (editingId) {
        await updateChartAccount(editingId, payload)
        setLocalSuccess("Conta do plano de contas atualizada com sucesso.")
      } else {
        await createChartAccount({ company_id: companyId, ...payload })
        setLocalSuccess("Conta do plano de contas criada com sucesso.")
      }
      resetForm()
      await onCreated()
      await refreshFilteredRows()
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionShell
      title="Plano de contas"
      description="Classifica a natureza econômica do lançamento. Conta sintética organiza hierarquia; conta analítica aceita vínculo operacional."
      form={
        <form onSubmit={submit} className="mt-5 grid gap-3">
          {localError && <Alert tone="error" message={localError} />}
          {localSuccess && <Alert tone="success" message={localSuccess} />}
          {editingId && (
            <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]">
              Editando conta existente. Alterações são auditadas.
            </div>
          )}
          <Field label="Código" value={code} onChange={setCode} placeholder="Ex.: 3.01" />
          <Field label="Nome" value={name} onChange={setName} placeholder="Ex.: Receita de vendas" />
          <SelectField label="Tipo" value={accountType} onChange={setAccountType} options={["asset", "liability", "equity", "revenue", "cost", "expense", "tax", "other"].map((v) => ({ value: v, label: labelFor(v) }))} />
          <SelectField label="Conta pai" value={parentId} onChange={setParentId} options={[{ value: "", label: "Sem conta pai" }, ...parentOptions]} />
          <SelectField label="Saldo normal" value={normalBalance} onChange={setNormalBalance} options={[{ value: "", label: "Não informado" }, { value: "debit", label: "Devedor" }, { value: "credit", label: "Credor" }]} />
          <SelectField label="Status" value={status} onChange={setStatus} options={["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))} />
          <div className="grid gap-3 sm:grid-cols-2">
            <CheckboxField label="Conta analítica" checked={isAnalytical} onChange={updateIsAnalytical} />
            <CheckboxField label="Aceita lançamento direto" checked={acceptsEntries} onChange={setAcceptsEntries} disabled={!isAnalytical} />
          </div>
          <TextareaField label="Observações" value={notes} onChange={setNotes} placeholder="Uso interno, restrições ou mapeamento contábil." />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" />{editingId ? "Salvar alterações" : "Criar conta"}
            </button>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                Cancelar edição
              </button>
            )}
          </div>
        </form>
      }
      table={
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_180px_180px_auto]">
            <Field label="Buscar" value={search} onChange={setSearch} placeholder="Código ou nome" />
            <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={[{ value: "", label: "Todos" }, ...["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))]} />
            <SelectField label="Tipo" value={typeFilter} onChange={setTypeFilter} options={[{ value: "", label: "Todos" }, ...["asset", "liability", "equity", "revenue", "cost", "expense", "tax", "other"].map((value) => ({ value, label: labelFor(value) }))]} />
            <button type="button" onClick={() => void refreshFilteredRows(0)} disabled={filterLoading} className="self-end rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              Aplicar filtros
            </button>
          </div>
          {sectionRows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">Nenhuma conta cadastrada.</div>
          ) : (
            <div className="overflow-x-auto overflow-hidden rounded-2xl border border-[var(--color-border-soft)]">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                  <tr>
                    <th className="px-4 py-3">Código</th>
                    <th className="px-4 py-3">Nome</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Estrutura</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                  {sectionRows.map((row) => {
                    const parent = row.parent_id ? accountById.get(row.parent_id) : null
                    return (
                      <tr key={row.id}>
                        <td className="px-4 py-3 font-mono text-xs">{row.code}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.name}</p>
                          <p className="mt-1 text-xs">{row.notes || "Sem observações."}</p>
                        </td>
                        <td className="px-4 py-3">{labelFor(row.account_type)}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.is_analytical ? "Analítica" : "Sintética"}</p>
                          <p className="text-xs">{row.accepts_entries ? "Aceita lançamento" : "Não aceita lançamento"}{row.normal_balance ? ` · ${labelFor(row.normal_balance)}` : ""}</p>
                          <p className="text-xs">Pai: {parent ? `${parent.code} — ${parent.name}` : "sem conta pai"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{labelFor(row.status)}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button type="button" onClick={() => startEdit(row)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-black text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                            Editar
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls page={page} hasNext={hasNextPage} loading={filterLoading} onPrev={() => void refreshFilteredRows(Math.max(0, page - 1))} onNext={() => void refreshFilteredRows(page + 1)} />
        </div>
      }
    />
  )
}

function CategorySection({ rows, companyId, onCreated, chartAccounts }: { rows: FinancialCategory[]; companyId: string; onCreated: () => Promise<void>; chartAccounts: ChartAccount[] }) {
  const [sectionRows, setSectionRows] = useState<FinancialCategory[]>(() => firstPageRows(rows))
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(() => hasNextSectionPage(rows))
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [categoryType, setCategoryType] = useState("expense")
  const [parentId, setParentId] = useState("")
  const [chartAccountId, setChartAccountId] = useState("")
  const [cashFlowGroup, setCashFlowGroup] = useState(defaultCashFlowGroupForCategoryType("expense"))
  const [affectsCashFlow, setAffectsCashFlow] = useState(true)
  const [requiresCostCenter, setRequiresCostCenter] = useState(false)
  const [status, setStatus] = useState("active")
  const [notes, setNotes] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [groupFilter, setGroupFilter] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [localSuccess, setLocalSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    setSectionRows(firstPageRows(rows))
    setHasNextPage(hasNextSectionPage(rows))
    setPage(0)
  }, [rows])

  const categoryById = useMemo(() => new Map(sectionRows.map((row) => [row.id, row])), [sectionRows])
  const parentOptions = useMemo(() => sectionRows
    .filter((row) => row.id !== editingId && row.status === "active")
    .map((row) => ({ value: row.id, label: `${row.code || "SEM-CODIGO"} — ${row.name}` })), [sectionRows, editingId])
  const chartAccountOptions = useMemo(() => chartAccounts
    .filter((row) => row.status === "active" && row.is_analytical && row.accepts_entries)
    .map((row) => ({ value: row.id, label: `${row.code} — ${row.name}` })), [chartAccounts])
  const categoryTypeOptions = ["income", "expense", "cost", "tax", "fee", "deduction", "transfer", "other"].map((value) => ({ value, label: labelFor(value) }))
  const cashFlowGroupOptions = ["operating_inflows", "operating_outflows", "investing_inflows", "investing_outflows", "financing_inflows", "financing_outflows", "transfers"].map((value) => ({ value, label: labelFor(value) }))
  const statusOptions = ["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))

  function resetForm() {
    setCode("")
    setName("")
    setCategoryType("expense")
    setParentId("")
    setChartAccountId("")
    setCashFlowGroup(defaultCashFlowGroupForCategoryType("expense"))
    setAffectsCashFlow(true)
    setRequiresCostCenter(false)
    setStatus("active")
    setNotes("")
    setEditingId(null)
  }

  function startEdit(row: FinancialCategory) {
    setEditingId(row.id)
    setCode(row.code ?? "")
    setName(row.name)
    setCategoryType(row.category_type)
    setParentId(row.parent_id ?? "")
    setChartAccountId(row.chart_account_id ?? "")
    setCashFlowGroup(row.cash_flow_group ?? defaultCashFlowGroupForCategoryType(row.category_type))
    setAffectsCashFlow(row.affects_cash_flow)
    setRequiresCostCenter(row.requires_cost_center)
    setStatus(row.status)
    setNotes(row.notes ?? "")
    setLocalError(null)
    setLocalSuccess(null)
  }

  function updateCategoryType(value: string) {
    setCategoryType(value)
    if (affectsCashFlow) setCashFlowGroup(defaultCashFlowGroupForCategoryType(value))
  }

  function updateAffectsCashFlow(value: boolean) {
    setAffectsCashFlow(value)
    setCashFlowGroup(value ? defaultCashFlowGroupForCategoryType(categoryType) : "")
  }

  async function refreshFilteredRows(nextPage = 0) {
    setLocalError(null)
    setFilterLoading(true)
    try {
      const response = await listFinancialCategories(companyId, {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        category_type: typeFilter || undefined,
        cash_flow_group: groupFilter || undefined,
        limit: SECTION_FETCH_LIMIT,
        offset: nextPage * SECTION_PAGE_SIZE,
      })
      setSectionRows(firstPageRows(response.data))
      setHasNextPage(hasNextSectionPage(response.data))
      setPage(nextPage)
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setFilterLoading(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setLocalError(null)
    setLocalSuccess(null)
    try {
      const payload = {
        code: code || null,
        name,
        category_type: categoryType,
        parent_id: parentId || null,
        chart_account_id: chartAccountId || null,
        cash_flow_group: affectsCashFlow ? cashFlowGroup : null,
        affects_cash_flow: affectsCashFlow,
        requires_cost_center: requiresCostCenter,
        status,
        notes: notes || null,
      }
      if (editingId) {
        await updateFinancialCategory(editingId, payload)
        setLocalSuccess("Categoria financeira atualizada com sucesso.")
      } else {
        await createFinancialCategory({ company_id: companyId, ...payload })
        setLocalSuccess("Categoria financeira criada com sucesso.")
      }
      resetForm()
      await onCreated()
      await refreshFilteredRows()
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionShell
      title="Categorias financeiras"
      description="Classificação operacional para contas a receber, contas a pagar, BI e fluxo de caixa."
      form={
        <form onSubmit={submit} className="mt-5 grid gap-3">
          {localError && <Alert tone="error" message={localError} />}
          {localSuccess && <Alert tone="success" message={localSuccess} />}
          {editingId && (
            <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]">
              Editando categoria existente. Alterações são auditadas.
            </div>
          )}
          <Field label="Código" value={code} onChange={setCode} placeholder="Ex.: VENDA-PRODUTOS" />
          <Field label="Nome" value={name} onChange={setName} placeholder="Ex.: Venda de produtos" />
          <SelectField label="Tipo" value={categoryType} onChange={updateCategoryType} options={categoryTypeOptions} />
          <SelectField label="Categoria pai" value={parentId} onChange={setParentId} options={[{ value: "", label: "Sem categoria pai" }, ...parentOptions]} />
          <SelectField label="Conta do plano de contas" value={chartAccountId} onChange={setChartAccountId} options={[{ value: "", label: "Sem vínculo" }, ...chartAccountOptions]} />
          <div className="grid gap-3 sm:grid-cols-2">
            <CheckboxField label="Afeta fluxo de caixa" checked={affectsCashFlow} onChange={updateAffectsCashFlow} />
            <CheckboxField label="Exige centro de custo" checked={requiresCostCenter} onChange={setRequiresCostCenter} />
          </div>
          <SelectField label="Grupo do fluxo de caixa" value={cashFlowGroup} onChange={setCashFlowGroup} disabled={!affectsCashFlow} options={[{ value: "", label: "Não afeta fluxo" }, ...cashFlowGroupOptions]} />
          <SelectField label="Status" value={status} onChange={setStatus} options={statusOptions} />
          <TextareaField label="Observações" value={notes} onChange={setNotes} placeholder="Uso da categoria, restrições ou mapeamento gerencial." />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" />{editingId ? "Salvar alterações" : "Criar categoria"}
            </button>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                Cancelar edição
              </button>
            )}
          </div>
        </form>
      }
      table={
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_160px_160px_190px_auto]">
            <Field label="Buscar" value={search} onChange={setSearch} placeholder="Código ou nome" />
            <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={[{ value: "", label: "Todos" }, ...statusOptions]} />
            <SelectField label="Tipo" value={typeFilter} onChange={setTypeFilter} options={[{ value: "", label: "Todos" }, ...categoryTypeOptions]} />
            <SelectField label="Grupo" value={groupFilter} onChange={setGroupFilter} options={[{ value: "", label: "Todos" }, ...cashFlowGroupOptions]} />
            <button type="button" onClick={() => void refreshFilteredRows(0)} disabled={filterLoading} className="self-end rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              Aplicar filtros
            </button>
          </div>
          {sectionRows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">Nenhuma categoria cadastrada.</div>
          ) : (
            <div className="overflow-x-auto overflow-hidden rounded-2xl border border-[var(--color-border-soft)]">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                  <tr>
                    <th className="px-4 py-3">Código</th>
                    <th className="px-4 py-3">Nome</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Fluxo / vínculos</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                  {sectionRows.map((row) => {
                    const parent = row.parent_id ? categoryById.get(row.parent_id) : null
                    const chartAccount = row.chart_account_id ? chartAccounts.find((account) => account.id === row.chart_account_id) : null
                    return (
                      <tr key={row.id}>
                        <td className="px-4 py-3 font-mono text-xs">{row.code || "—"}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.name}</p>
                          <p className="mt-1 text-xs">{row.notes || "Sem observações."}</p>
                        </td>
                        <td className="px-4 py-3">{labelFor(row.category_type)}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.affects_cash_flow ? labelFor(row.cash_flow_group ?? "") : "Não afeta fluxo"}</p>
                          <p className="text-xs">{row.requires_cost_center ? "Exige centro de custo" : "Centro de custo opcional"}</p>
                          <p className="text-xs">Plano: {chartAccount ? `${chartAccount.code} — ${chartAccount.name}` : "sem vínculo"}</p>
                          <p className="text-xs">Pai: {parent ? `${parent.code || "SEM-CODIGO"} — ${parent.name}` : "sem categoria pai"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{labelFor(row.status)}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button type="button" onClick={() => startEdit(row)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-black text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                            Editar
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls page={page} hasNext={hasNextPage} loading={filterLoading} onPrev={() => void refreshFilteredRows(Math.max(0, page - 1))} onNext={() => void refreshFilteredRows(page + 1)} />
        </div>
      }
    />
  )
}

function CostCenterSection({ rows, companyId, onCreated }: { rows: CostCenter[]; companyId: string; onCreated: () => Promise<void> }) {
  const [sectionRows, setSectionRows] = useState<CostCenter[]>(() => firstPageRows(rows))
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(() => hasNextSectionPage(rows))
  const [code, setCode] = useState("")
  const [name, setName] = useState("")
  const [centerType, setCenterType] = useState("other")
  const [parentId, setParentId] = useState("")
  const [isAnalytical, setIsAnalytical] = useState(true)
  const [responsibleName, setResponsibleName] = useState("")
  const [monthlyBudgetAmount, setMonthlyBudgetAmount] = useState("")
  const [status, setStatus] = useState("active")
  const [notes, setNotes] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [localSuccess, setLocalSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    setSectionRows(firstPageRows(rows))
    setHasNextPage(hasNextSectionPage(rows))
    setPage(0)
  }, [rows])

  const costCenterById = useMemo(() => new Map(rows.map((row) => [row.id, row])), [rows])
  const centerTypeOptions = ["administrative", "commercial", "financial", "technology", "marketplace", "store", "project", "logistics", "other"].map((value) => ({ value, label: labelFor(value) }))
  const statusOptions = ["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))
  const parentOptions = useMemo(() => rows
    .filter((row) => row.id !== editingId && row.status === "active" && !row.is_analytical)
    .map((row) => ({ value: row.id, label: `${row.code} - ${row.name}` })), [rows, editingId])

  function resetForm() {
    setCode("")
    setName("")
    setCenterType("other")
    setParentId("")
    setIsAnalytical(true)
    setResponsibleName("")
    setMonthlyBudgetAmount("")
    setStatus("active")
    setNotes("")
    setEditingId(null)
  }

  function startEdit(row: CostCenter) {
    setEditingId(row.id)
    setCode(row.code)
    setName(row.name)
    setCenterType(row.center_type)
    setParentId(row.parent_id ?? "")
    setIsAnalytical(row.is_analytical)
    setResponsibleName(row.responsible_name ?? "")
    setMonthlyBudgetAmount(row.monthly_budget_amount ?? "")
    setStatus(row.status)
    setNotes(row.notes ?? "")
    setLocalError(null)
    setLocalSuccess(null)
  }

  async function refreshFilteredRows(nextPage = 0) {
    setLocalError(null)
    setFilterLoading(true)
    try {
      const response = await listCostCenters(companyId, {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        center_type: typeFilter || undefined,
        limit: SECTION_FETCH_LIMIT,
        offset: nextPage * SECTION_PAGE_SIZE,
      })
      setSectionRows(firstPageRows(response.data))
      setHasNextPage(hasNextSectionPage(response.data))
      setPage(nextPage)
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setFilterLoading(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setLocalError(null)
    setLocalSuccess(null)
    try {
      const payload = {
        code,
        name,
        center_type: centerType,
        parent_id: parentId || null,
        is_analytical: isAnalytical,
        responsible_name: responsibleName || null,
        monthly_budget_amount: monthlyBudgetAmount || null,
        status,
        notes: notes || null,
      }
      if (editingId) {
        await updateCostCenter(editingId, payload)
        setLocalSuccess("Centro de custo atualizado com sucesso.")
      } else {
        await createCostCenter({ company_id: companyId, ...payload })
        setLocalSuccess("Centro de custo criado com sucesso.")
      }
      resetForm()
      await onCreated()
      await refreshFilteredRows()
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionShell
      title="Centros de custo"
      description="Identifica area, projeto ou loja responsavel pela receita, custo ou despesa. Centro sintetico organiza hierarquia; centro analitico recebe lancamento."
      form={
        <form onSubmit={submit} className="mt-5 grid gap-3">
          {localError && <Alert tone="error" message={localError} />}
          {localSuccess && <Alert tone="success" message={localSuccess} />}
          {editingId && (
            <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]">
              Editando centro de custo existente. Alteracoes sao auditadas.
            </div>
          )}
          <Field label="Codigo" value={code} onChange={setCode} placeholder="Ex.: COMERCIAL" />
          <Field label="Nome" value={name} onChange={setName} placeholder="Ex.: Comercial" />
          <SelectField label="Tipo" value={centerType} onChange={setCenterType} options={centerTypeOptions} />
          <SelectField label="Centro pai" value={parentId} onChange={setParentId} options={[{ value: "", label: "Sem centro pai" }, ...parentOptions]} />
          <CheckboxField label="Centro analitico" checked={isAnalytical} onChange={setIsAnalytical} />
          <Field label="Responsavel" value={responsibleName} onChange={setResponsibleName} placeholder="Ex.: Gerente comercial" />
          <Field label="Orcamento mensal" value={monthlyBudgetAmount} onChange={setMonthlyBudgetAmount} placeholder="Ex.: 15000,00" />
          <SelectField label="Status" value={status} onChange={setStatus} options={statusOptions} />
          <TextareaField label="Observacoes" value={notes} onChange={setNotes} placeholder="Uso do centro, regra de apropriacao ou restricoes." />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" />{editingId ? "Salvar alteracoes" : "Criar centro"}
            </button>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                Cancelar edicao
              </button>
            )}
          </div>
        </form>
      }
      table={
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_180px_180px_auto]">
            <Field label="Buscar" value={search} onChange={setSearch} placeholder="Codigo ou nome" />
            <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={[{ value: "", label: "Todos" }, ...statusOptions]} />
            <SelectField label="Tipo" value={typeFilter} onChange={setTypeFilter} options={[{ value: "", label: "Todos" }, ...centerTypeOptions]} />
            <button type="button" onClick={() => void refreshFilteredRows(0)} disabled={filterLoading} className="self-end rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              Aplicar filtros
            </button>
          </div>
          {sectionRows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">Nenhum centro de custo cadastrado.</div>
          ) : (
            <div className="overflow-x-auto overflow-hidden rounded-2xl border border-[var(--color-border-soft)]">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                  <tr>
                    <th className="px-4 py-3">Codigo</th>
                    <th className="px-4 py-3">Nome</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Estrutura</th>
                    <th className="px-4 py-3">Orcamento / responsavel</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Acao</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                  {sectionRows.map((row) => {
                    const parent = row.parent_id ? costCenterById.get(row.parent_id) : null
                    return (
                      <tr key={row.id}>
                        <td className="px-4 py-3 font-mono text-xs">{row.code}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.name}</p>
                          <p className="mt-1 text-xs">{row.notes || "Sem observacoes."}</p>
                        </td>
                        <td className="px-4 py-3">{labelFor(row.center_type)}</td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.is_analytical ? "Analitico" : "Sintetico"}</p>
                          <p className="text-xs">Pai: {parent ? `${parent.code} - ${parent.name}` : "sem centro pai"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[var(--color-text)]">{row.monthly_budget_amount ? formatMoney(row.monthly_budget_amount) : "Sem orcamento"}</p>
                          <p className="text-xs">{row.responsible_name || "Sem responsavel"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{labelFor(row.status)}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button type="button" onClick={() => startEdit(row)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-black text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                            Editar
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls page={page} hasNext={hasNextPage} loading={filterLoading} onPrev={() => void refreshFilteredRows(Math.max(0, page - 1))} onNext={() => void refreshFilteredRows(page + 1)} />
        </div>
      }
    />
  )
}

function AccountSection({ rows, companyId, onCreated }: { rows: FinancialAccount[]; companyId: string; onCreated: () => Promise<void> }) {
  const [sectionRows, setSectionRows] = useState<FinancialAccount[]>(() => firstPageRows(rows))
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(() => hasNextSectionPage(rows))
  const [name, setName] = useState("")
  const [accountType, setAccountType] = useState("bank_account")
  const [institutionName, setInstitutionName] = useState("")
  const [branchNumber, setBranchNumber] = useState("")
  const [accountNumber, setAccountNumber] = useState("")
  const [accountDigit, setAccountDigit] = useState("")
  const [pixKey, setPixKey] = useState("")
  const [pixKeyType, setPixKeyType] = useState("")
  const [currency, setCurrency] = useState("BRL")
  const [openingBalanceAmount, setOpeningBalanceAmount] = useState("0")
  const [isDefaultReceivable, setIsDefaultReceivable] = useState(false)
  const [isDefaultPayable, setIsDefaultPayable] = useState(false)
  const [status, setStatus] = useState("active")
  const [notes, setNotes] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [localSuccess, setLocalSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    setSectionRows(firstPageRows(rows))
    setHasNextPage(hasNextSectionPage(rows))
    setPage(0)
  }, [rows])

  function resetForm() {
    setName("")
    setAccountType("bank_account")
    setInstitutionName("")
    setBranchNumber("")
    setAccountNumber("")
    setAccountDigit("")
    setPixKey("")
    setPixKeyType("")
    setCurrency("BRL")
    setOpeningBalanceAmount("0")
    setIsDefaultReceivable(false)
    setIsDefaultPayable(false)
    setStatus("active")
    setNotes("")
    setEditingId(null)
  }

  function startEdit(row: FinancialAccount) {
    setEditingId(row.id)
    setName(row.name)
    setAccountType(row.account_type)
    setInstitutionName(row.institution_name ?? "")
    setBranchNumber(row.branch_number ?? "")
    setAccountNumber(row.account_number ?? "")
    setAccountDigit(row.account_digit ?? "")
    setPixKey(row.pix_key ?? "")
    setPixKeyType(row.pix_key_type ?? "")
    setCurrency(row.currency ?? "BRL")
    setOpeningBalanceAmount(row.opening_balance_amount ?? "0")
    setIsDefaultReceivable(row.is_default_receivable)
    setIsDefaultPayable(row.is_default_payable)
    setStatus(row.status)
    setNotes(row.notes ?? "")
    setLocalError(null)
    setLocalSuccess(null)
  }

  async function refreshFilteredRows(nextPage = 0) {
    setLocalError(null)
    setFilterLoading(true)
    try {
      const response = await listFinancialAccounts(companyId, {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        account_type: typeFilter || undefined,
        limit: SECTION_FETCH_LIMIT,
        offset: nextPage * SECTION_PAGE_SIZE,
      })
      setSectionRows(firstPageRows(response.data))
      setHasNextPage(hasNextSectionPage(response.data))
      setPage(nextPage)
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setFilterLoading(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setLocalError(null)
    setLocalSuccess(null)
    try {
      const payload = {
        name,
        account_type: accountType,
        institution_name: institutionName || null,
        branch_number: branchNumber || null,
        account_number: accountNumber || null,
        account_digit: accountDigit || null,
        pix_key: pixKey || null,
        pix_key_type: pixKey ? pixKeyType || "other" : null,
        currency: currency || "BRL",
        opening_balance_amount: openingBalanceAmount || "0",
        is_default_receivable: isDefaultReceivable,
        is_default_payable: isDefaultPayable,
        status,
        notes: notes || null,
      }
      if (editingId) {
        await updateFinancialAccount(editingId, payload)
        setLocalSuccess("Conta financeira atualizada com sucesso.")
      } else {
        await createFinancialAccount({ company_id: companyId, ...payload })
        setLocalSuccess("Conta financeira criada com sucesso.")
      }
      resetForm()
      await onCreated()
      await refreshFilteredRows()
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const accountTypeOptions = ["bank_account", "cash", "gateway", "marketplace", "digital_wallet", "credit_card", "other"].map((value) => ({ value, label: labelFor(value) }))

  return (
    <SectionShell
      title="Contas financeiras"
      description="Banco, caixa, gateway, marketplace ou carteira digital. Esta conta alimenta baixas, movimentos, saldos internos e conciliacao."
      form={
        <form onSubmit={submit} className="mt-5 grid gap-3">
          {localError && <Alert tone="error" message={localError} />}
          {localSuccess && <Alert tone="success" message={localSuccess} />}
          {editingId && (
            <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]">
              Editando conta existente. Nao inative contas com titulos, movimentos, baixas, saldos ou extratos vinculados.
            </div>
          )}
          <Field label="Nome" value={name} onChange={setName} placeholder="Ex.: Caixa Principal ou Banco Principal" />
          <SelectField label="Tipo" value={accountType} onChange={setAccountType} options={accountTypeOptions} />
          <Field label="Instituicao" value={institutionName} onChange={setInstitutionName} placeholder="Ex.: Banco do Brasil, Mercado Pago" />
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Agencia" value={branchNumber} onChange={setBranchNumber} placeholder="0001" />
            <Field label="Conta" value={accountNumber} onChange={setAccountNumber} placeholder="12345" />
            <Field label="Digito" value={accountDigit} onChange={setAccountDigit} placeholder="6" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Chave Pix" value={pixKey} onChange={setPixKey} placeholder="email, telefone, CNPJ ou aleatoria" />
            <SelectField label="Tipo Pix" value={pixKeyType} onChange={setPixKeyType} options={[{ value: "", label: "Nao informado" }, ...["cpf", "cnpj", "email", "phone", "random", "other"].map((value) => ({ value, label: labelFor(value) }))]} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Moeda" value={currency} onChange={setCurrency} placeholder="BRL" />
            <Field label="Saldo inicial" value={openingBalanceAmount} onChange={setOpeningBalanceAmount} placeholder="0,00" />
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
            Saldo inicial so deve ser usado antes da primeira movimentacao. Apos saldo materializado ou movimento, o backend bloqueia alteracao.
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <CheckboxField label="Padrao para recebimentos" checked={isDefaultReceivable} onChange={setIsDefaultReceivable} />
            <CheckboxField label="Padrao para pagamentos" checked={isDefaultPayable} onChange={setIsDefaultPayable} />
          </div>
          <SelectField label="Status" value={status} onChange={setStatus} options={["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))} />
          <TextareaField label="Observacoes" value={notes} onChange={setNotes} placeholder="Uso operacional, restricoes ou referencia interna." />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" />{editingId ? "Salvar alteracoes" : "Criar conta financeira"}
            </button>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                Cancelar edicao
              </button>
            )}
          </div>
        </form>
      }
      table={
        <div className="grid gap-4">
          <div>
            <h3 className="text-lg font-black text-[var(--color-text)]">Contas cadastradas</h3>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">Use filtros para revisar contas ativas, bloqueadas e intermediadores.</p>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_180px_220px_auto]">
            <Field label="Buscar" value={search} onChange={setSearch} placeholder="Nome, instituicao ou Pix" />
            <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={[{ value: "", label: "Todos" }, ...["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))]} />
            <SelectField label="Tipo" value={typeFilter} onChange={setTypeFilter} options={[{ value: "", label: "Todos" }, ...accountTypeOptions]} />
            <button type="button" onClick={() => void refreshFilteredRows(0)} disabled={filterLoading} className="self-end rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              Filtrar
            </button>
          </div>
          {sectionRows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">Nenhuma conta financeira cadastrada.</div>
          ) : (
            <div className="overflow-x-auto overflow-hidden rounded-2xl border border-[var(--color-border-soft)]">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                  <tr>
                    <th className="px-4 py-3">Conta</th>
                    <th className="px-4 py-3">Dados bancarios</th>
                    <th className="px-4 py-3">Pix</th>
                    <th className="px-4 py-3">Saldo inicial</th>
                    <th className="px-4 py-3">Padroes</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Acao</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                  {sectionRows.map((row) => (
                    <tr key={row.id}>
                      <td className="px-4 py-3">
                        <p className="font-bold text-[var(--color-text)]">{row.name}</p>
                        <p className="text-xs">{labelFor(row.account_type)} · {row.currency}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p>{row.institution_name || "Nao informado"}</p>
                        <p className="text-xs">{[row.branch_number, row.account_number, row.account_digit].filter(Boolean).join(" / ") || "Sem agencia/conta"}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p>{row.pix_key || "Nao informado"}</p>
                        <p className="text-xs">{labelFor(row.pix_key_type)}</p>
                      </td>
                      <td className="px-4 py-3 font-bold text-[var(--color-text)]">{formatMoney(row.opening_balance_amount)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          {row.is_default_receivable && <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-2 py-1 text-xs font-black text-[var(--color-primary)]">Receber</span>}
                          {row.is_default_payable && <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-2 py-1 text-xs font-black text-[var(--color-primary)]">Pagar</span>}
                          {!row.is_default_receivable && !row.is_default_payable && <span className="text-xs">Sem padrao</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{labelFor(row.status)}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button type="button" onClick={() => startEdit(row)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls page={page} hasNext={hasNextPage} loading={filterLoading} onPrev={() => void refreshFilteredRows(Math.max(0, page - 1))} onNext={() => void refreshFilteredRows(page + 1)} />
        </div>
      }
    />
  )
}

function TermSection({ rows, companyId, onCreated }: { rows: PaymentTerm[]; companyId: string; onCreated: () => Promise<void> }) {
  const [sectionRows, setSectionRows] = useState<PaymentTerm[]>(() => firstPageRows(rows))
  const [page, setPage] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(() => hasNextSectionPage(rows))
  const [name, setName] = useState("")
  const [termType, setTermType] = useState("cash")
  const [installments, setInstallments] = useState("1")
  const [firstDueDays, setFirstDueDays] = useState("0")
  const [intervalDays, setIntervalDays] = useState("0")
  const [generateOnSale, setGenerateOnSale] = useState(true)
  const [status, setStatus] = useState("active")
  const [notes, setNotes] = useState("")
  const [editingId, setEditingId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [localSuccess, setLocalSuccess] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)

  useEffect(() => {
    setSectionRows(firstPageRows(rows))
    setHasNextPage(hasNextSectionPage(rows))
    setPage(0)
  }, [rows])

  const termTypeOptions = ["cash", "installments", "recurring", "custom"].map((value) => ({ value, label: value === "cash" ? "A vista" : labelFor(value) }))

  function resetForm() {
    setName("")
    setTermType("cash")
    setInstallments("1")
    setFirstDueDays("0")
    setIntervalDays("0")
    setGenerateOnSale(true)
    setStatus("active")
    setNotes("")
    setEditingId(null)
  }

  function changeTermType(value: string) {
    setTermType(value)
    if (value === "cash") {
      setInstallments("1")
      setFirstDueDays("0")
      setIntervalDays("0")
      return
    }
    if (intervalDays === "0") setIntervalDays("30")
    if (firstDueDays === "0") setFirstDueDays("30")
  }

  function startEdit(row: PaymentTerm) {
    setEditingId(row.id)
    setName(row.name)
    setTermType(row.term_type)
    setInstallments(String(row.installments))
    setFirstDueDays(String(row.first_due_days))
    setIntervalDays(String(row.interval_days))
    setGenerateOnSale(row.generate_on_sale)
    setStatus(row.status)
    setNotes(row.notes ?? "")
    setLocalError(null)
    setLocalSuccess(null)
  }

  async function refreshFilteredRows(nextPage = 0) {
    setLocalError(null)
    setFilterLoading(true)
    try {
      const response = await listPaymentTerms(companyId, {
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        term_type: typeFilter || undefined,
        limit: SECTION_FETCH_LIMIT,
        offset: nextPage * SECTION_PAGE_SIZE,
      })
      setSectionRows(firstPageRows(response.data))
      setHasNextPage(hasNextSectionPage(response.data))
      setPage(nextPage)
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setFilterLoading(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    setLocalError(null)
    setLocalSuccess(null)
    try {
      const payload = {
        name,
        term_type: termType,
        installments: termType === "cash" ? 1 : Number(installments || "1"),
        first_due_days: termType === "cash" ? 0 : Number(firstDueDays || "0"),
        interval_days: termType === "cash" ? 0 : Number(intervalDays || "0"),
        generate_on_sale: generateOnSale,
        status,
        notes: notes || null,
      }
      if (editingId) {
        await updatePaymentTerm(editingId, payload)
        setLocalSuccess("Condicao de pagamento atualizada com sucesso.")
      } else {
        await createPaymentTerm({ company_id: companyId, ...payload })
        setLocalSuccess("Condicao de pagamento criada com sucesso.")
      }
      resetForm()
      await onCreated()
      await refreshFilteredRows()
    } catch (err) {
      setLocalError(getErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionShell
      title="Condições de pagamento"
      description="Define vencimento e parcelamento base. Na v1.0, este cadastro prepara a operacao; pedidos ainda informam planos de pagamento explicitamente."
      form={
        <form onSubmit={submit} className="mt-5 grid gap-3">
          {localError && <Alert tone="error" message={localError} />}
          {localSuccess && <Alert tone="success" message={localSuccess} />}
          {editingId && (
            <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)]">
              Editando condicao existente. Alteracoes afetam novos usos operacionais, nao reescrevem titulos ja gerados.
            </div>
          )}
          <Field label="Nome" value={name} onChange={setName} placeholder="Ex.: 30 dias" />
          <SelectField label="Tipo" value={termType} onChange={changeTermType} options={termTypeOptions} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Parcelas" value={installments} onChange={setInstallments} type="number" />
            <Field label="Primeiro vencimento em dias" value={firstDueDays} onChange={setFirstDueDays} type="number" />
            <Field label="Intervalo entre parcelas" value={intervalDays} onChange={setIntervalDays} type="number" />
          </div>
          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
            A vista deve ser 1 parcela, D+0 e intervalo 0. Parcelado com mais de uma parcela precisa de intervalo maior que zero.
          </div>
          <CheckboxField label="Disponivel para gerar plano em venda" checked={generateOnSale} onChange={setGenerateOnSale} />
          <SelectField label="Status" value={status} onChange={setStatus} options={["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))} />
          <TextareaField label="Observacoes" value={notes} onChange={setNotes} placeholder="Regras internas, combinados comerciais ou restricoes." />
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-bold text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-60">
              <Save className="h-4 w-4" />{editingId ? "Salvar alteracoes" : "Criar condicao"}
            </button>
            {editingId && (
              <button type="button" onClick={resetForm} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                Cancelar edicao
              </button>
            )}
          </div>
        </form>
      }
      table={
        <div className="grid gap-4">
          <div>
            <h3 className="text-lg font-black text-[var(--color-text)]">Condicoes cadastradas</h3>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">Revise vencimento, parcelamento e status antes de usar em operacao comercial.</p>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_180px_220px_auto]">
            <Field label="Buscar" value={search} onChange={setSearch} placeholder="Nome da condicao" />
            <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={[{ value: "", label: "Todos" }, ...["active", "inactive", "blocked", "archived"].map((value) => ({ value, label: labelFor(value) }))]} />
            <SelectField label="Tipo" value={typeFilter} onChange={setTypeFilter} options={[{ value: "", label: "Todos" }, ...termTypeOptions]} />
            <button type="button" onClick={() => void refreshFilteredRows(0)} disabled={filterLoading} className="self-end rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              Filtrar
            </button>
          </div>
          {sectionRows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">Nenhuma condicao cadastrada.</div>
          ) : (
            <div className="overflow-x-auto overflow-hidden rounded-2xl border border-[var(--color-border-soft)]">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
                  <tr>
                    <th className="px-4 py-3">Condicao</th>
                    <th className="px-4 py-3">Parcelamento</th>
                    <th className="px-4 py-3">Uso</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Observacao</th>
                    <th className="px-4 py-3 text-right">Acao</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                  {sectionRows.map((row) => (
                    <tr key={row.id}>
                      <td className="px-4 py-3">
                        <p className="font-bold text-[var(--color-text)]">{row.name}</p>
                        <p className="text-xs">{row.term_type === "cash" ? "A vista" : labelFor(row.term_type)}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[var(--color-text)]">{row.installments}x</p>
                        <p className="text-xs">D+{row.first_due_days} · intervalo {row.interval_days} dia(s)</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full border px-3 py-1 text-xs font-black ${row.generate_on_sale ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)]"}`}>
                          {row.generate_on_sale ? "Venda" : "Manual"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">{labelFor(row.status)}</span>
                      </td>
                      <td className="px-4 py-3">{row.notes || "-"}</td>
                      <td className="px-4 py-3 text-right">
                        <button type="button" onClick={() => startEdit(row)} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <PaginationControls page={page} hasNext={hasNextPage} loading={filterLoading} onPrev={() => void refreshFilteredRows(Math.max(0, page - 1))} onNext={() => void refreshFilteredRows(page + 1)} />
        </div>
      }
    />
  )
}
