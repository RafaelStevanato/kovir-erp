import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
} from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import {
  generateStressData,
  getStressRules,
  getStressSummary,
} from "./stressTestsApi"
import type {
  StressGeneratePayload,
  StressGenerateResult,
  StressRules,
  StressSummary,
} from "./types"

type Notice = { type: "success" | "error"; message: string } | null

const DEFAULT_PAYLOAD: StressGeneratePayload = {
  participants: 2,
  fiscal_classifications: 2,
  products: 2,
  services: 1,
  sales: 3,
  receivables: 2,
  purchases: 2,
  confirm_sales: true,
  confirm_purchases: true,
}

export function StressTestsPage() {
  const { companyId, activeCompanyName } = useActiveCompany()
  const [rules, setRules] = useState<StressRules | null>(null)
  const [summary, setSummary] = useState<StressSummary | null>(null)
  const [result, setResult] = useState<StressGenerateResult | null>(null)
  const [payload, setPayload] = useState<StressGeneratePayload>(DEFAULT_PAYLOAD)
  const [isLoading, setIsLoading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [notice, setNotice] = useState<Notice>(null)

  const totalRequested = useMemo(
    () =>
      payload.participants +
      payload.fiscal_classifications +
      payload.products +
      payload.services +
      payload.sales +
      payload.receivables +
      payload.purchases,
    [payload],
  )

  async function loadData() {
    setIsLoading(true)
    setNotice(null)
    try {
      const [rulesResponse, summaryResponse] = await Promise.all([
        getStressRules(),
        getStressSummary(),
      ])
      setRules(rulesResponse.data)
      setSummary(summaryResponse.data)
    } catch (error) {
      setNotice({
        type: "error",
        message:
          error instanceof Error
            ? error.message
            : "Falha ao carregar módulo de stress.",
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [companyId])

  async function handleGenerate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsGenerating(true)
    setNotice(null)
    try {
      const response = await generateStressData(payload)
      setResult(response.data)
      setNotice({
        type: "success",
        message: "Massa de stress gerada com sucesso para a empresa logada.",
      })
      const summaryResponse = await getStressSummary()
      setSummary(summaryResponse.data)
    } catch (error) {
      setNotice({
        type: "error",
        message:
          error instanceof Error
            ? error.message
            : "Falha ao gerar massa de stress.",
      })
    } finally {
      setIsGenerating(false)
    }
  }

  function setCountField(
    field:
      | "participants"
      | "fiscal_classifications"
      | "products"
      | "services"
      | "sales"
      | "receivables"
      | "purchases",
    value: string,
  ) {
    const parsed = Number(value)
    const normalized = Number.isFinite(parsed) ? Math.max(0, Math.min(200, Math.trunc(parsed))) : 0
    setPayload((current) => ({
      ...current,
      [field]: normalized,
    }))
  }

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <InfoPill icon={<Database className="h-4 w-4" />} label="Stress e Testes" />
              <InfoPill icon={<ShieldCheck className="h-4 w-4" />} label="Empresa da sessão" />
            </div>
            <h1 className="text-3xl font-black text-[var(--color-text)] sm:text-4xl">
              Geração de massa sintética
            </h1>
            <p className="mt-2 text-sm text-[var(--color-text-muted)]">
              Gera títulos, vendas, produtos, classificações fiscais e participantes
              para validar banco e lógica sem trocar de empresa.
            </p>
            <p className="mt-2 text-xs font-semibold text-[var(--color-primary)]">
              Empresa logada: {activeCompanyName || "Empresa da sessão"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadData()}
            disabled={isLoading || isGenerating}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-semibold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-60"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Atualizar
          </button>
        </div>
      </header>

      {notice ? (
        <section
          className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
            notice.type === "success"
              ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
              : "border-red-400/40 bg-red-500/10 text-red-100"
          }`}
        >
          <span className="inline-flex items-center gap-2">
            {notice.type === "success" ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <AlertTriangle className="h-4 w-4" />
            )}
            {notice.message}
          </span>
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Participantes" value={String(summary?.counts.participants ?? 0)} />
        <MetricCard label="Itens catálogo" value={String(summary?.counts.catalog_items ?? 0)} />
        <MetricCard label="Vendas" value={String(summary?.counts.sales ?? 0)} />
        <MetricCard label="Títulos a receber" value={String(summary?.counts.receivables ?? 0)} />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <form onSubmit={handleGenerate} className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-lg font-black text-[var(--color-text)]">Configuração da geração</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Limite por gerador: {rules?.limits.max_per_generator ?? 200}
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <NumericField label="Participantes" value={payload.participants} onChange={(value) => setCountField("participants", value)} />
            <NumericField label="Classificações fiscais" value={payload.fiscal_classifications} onChange={(value) => setCountField("fiscal_classifications", value)} />
            <NumericField label="Produtos" value={payload.products} onChange={(value) => setCountField("products", value)} />
            <NumericField label="Serviços" value={payload.services} onChange={(value) => setCountField("services", value)} />
            <NumericField label="Vendas" value={payload.sales} onChange={(value) => setCountField("sales", value)} />
            <NumericField label="Títulos a receber" value={payload.receivables} onChange={(value) => setCountField("receivables", value)} />
            <NumericField label="Compras/AP" value={payload.purchases} onChange={(value) => setCountField("purchases", value)} />
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
              <input
                type="checkbox"
                checked={payload.confirm_sales}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    confirm_sales: event.target.checked,
                  }))
                }
              />
              Confirmar vendas automaticamente
            </label>
            <label className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
              <input
                type="checkbox"
                checked={payload.confirm_purchases}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    confirm_purchases: event.target.checked,
                  }))
                }
              />
              Confirmar compras automaticamente
            </label>
          </div>

          <button
            type="submit"
            disabled={isGenerating || totalRequested <= 0}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-60"
          >
            {isGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Gerar dados de stress
          </button>
        </form>

        <aside className="space-y-3 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-lg font-black text-[var(--color-text)]">Resultado da última execução</h2>
          {result ? (
            <>
              <MetricCard label="Registros solicitados" value={String(totalFromRequested(result.requested))} tone="info" />
              <MetricCard label="Variação catálogo" value={withSignal(result.delta.catalog_items)} tone={result.delta.catalog_items > 0 ? "success" : "neutral"} />
              <MetricCard label="Variação vendas" value={withSignal(result.delta.sales)} tone={result.delta.sales > 0 ? "success" : "neutral"} />
              <MetricCard label="Variação títulos AP/AR" value={withSignal(result.delta.payables + result.delta.receivables)} tone={result.delta.payables + result.delta.receivables > 0 ? "success" : "neutral"} />
            </>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">
              Nenhuma execução ainda. Configure as quantidades e clique em gerar.
            </p>
          )}
        </aside>
      </section>
    </div>
  )
}

function totalFromRequested(requested: StressGeneratePayload) {
  return (
    requested.participants +
    requested.fiscal_classifications +
    requested.products +
    requested.services +
    requested.sales +
    requested.receivables +
    requested.purchases
  )
}

function withSignal(value: number) {
  if (value > 0) return `+${value}`
  return String(value)
}

function NumericField({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
        {label}
      </span>
      <input
        type="number"
        min={0}
        max={200}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
      />
    </label>
  )
}

function MetricCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string
  value: string
  tone?: "neutral" | "success" | "info"
}) {
  const className =
    tone === "success"
      ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
      : tone === "info"
        ? "border-blue-400/40 bg-blue-500/10 text-blue-100"
        : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"

  return (
    <article className={`rounded-3xl border p-4 ${className}`}>
      <p className="text-xs font-black uppercase tracking-wide opacity-80">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
    </article>
  )
}

function InfoPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1.5 text-xs font-black text-[var(--color-primary)]">
      {icon}
      {label}
    </span>
  )
}
