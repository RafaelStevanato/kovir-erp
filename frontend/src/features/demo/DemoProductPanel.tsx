import { useMemo, useState } from "react"
import { Archive, CheckCircle2, Database, Loader2, Play, RefreshCw, ShieldCheck, Sparkles, Trash2 } from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import { isDemoCompany } from "../../config/activeCompany"
import { archiveOldDemoCompanies, generateDemoCompany, type DemoGenerateResult } from "./demoApi"

function formatCount(value: number | undefined) {
  return new Intl.NumberFormat("pt-BR").format(value ?? 0)
}

function formatMoney(value: string | number | undefined) {
  const numericValue = Number(value ?? 0)

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number.isFinite(numericValue) ? numericValue : 0)
}

export function DemoProductPanel() {
  const { companyId, activeCompany, reloadCompanies, selectCompany } = useActiveCompany()
  const [sales, setSales] = useState(40)
  const [purchases, setPurchases] = useState(25)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isArchiving, setIsArchiving] = useState(false)
  const [result, setResult] = useState<DemoGenerateResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const activeIsDemo = useMemo(() => isDemoCompany(activeCompany), [activeCompany])
  const summary = result?.collections_summary
  const opening = result?.opening_summary
  const operationalCounts = result?.operational_counts

  async function handleGenerateDemo() {
    setIsGenerating(true)
    setError(null)
    setMessage(null)

    try {
      const response = await generateDemoCompany({ sales, purchases })
      const generatedCompanyId = response.data.company_id
      setResult(response.data)
      await reloadCompanies()
      if (generatedCompanyId) {
        selectCompany(generatedCompanyId)
      }
      setMessage("Empresa demo gerada e selecionada no topo da tela.")
    } catch (err) {
      const nextMessage = err instanceof Error ? err.message : "Falha ao gerar empresa demo."
      setError(nextMessage)
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleArchiveOldDemos() {
    setIsArchiving(true)
    setError(null)
    setMessage(null)

    try {
      const response = await archiveOldDemoCompanies({
        keep_latest: 1,
        keep_company_id: activeIsDemo ? companyId : null,
      })
      await reloadCompanies()
      setMessage(`Demos antigas arquivadas: ${response.data.archived_count}. Mantidas: ${response.data.kept_count}.`)
    } catch (err) {
      const nextMessage = err instanceof Error ? err.message : "Falha ao arquivar empresas demo antigas."
      setError(nextMessage)
    } finally {
      setIsArchiving(false)
    }
  }

  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-2xl shadow-[var(--color-card-shadow)]">
      <div className="grid gap-0 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="border-b border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5 sm:p-6 xl:border-b-0 xl:border-r">
          <div className="flex items-start gap-3">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
              <Database className="h-6 w-6" />
            </span>
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Modo demonstração</p>
              <h2 className="mt-1 text-xl font-black text-[var(--color-text)]">Gerar empresa demo realista</h2>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
                Cria massa operacional completa para abrir o Kovir com dados reais: clientes, fornecedores, catálogo, vendas, contas a receber, compras, contas a pagar, baixas, caixa, extrato e conciliação.
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <label className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3">
              <span className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Vendas demo</span>
              <input
                type="number"
                min={1}
                max={120}
                value={sales}
                onChange={(event) => setSales(Math.max(1, Math.min(120, Number(event.target.value) || 1)))}
                className="mt-2 w-full rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-sm font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
              />
            </label>

            <label className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3">
              <span className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Compras/despesas demo</span>
              <input
                type="number"
                min={1}
                max={80}
                value={purchases}
                onChange={(event) => setPurchases(Math.max(1, Math.min(80, Number(event.target.value) || 1)))}
                className="mt-2 w-full rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-sm font-bold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
              />
            </label>
          </div>

          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => void handleGenerateDemo()}
              disabled={isGenerating || isArchiving}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Gerar demo
            </button>
            <button
              type="button"
              onClick={() => void handleArchiveOldDemos()}
              disabled={isGenerating || isArchiving}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-sm font-black text-amber-100 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isArchiving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              Limpar demos antigas
            </button>
          </div>

          <div className="mt-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-xs leading-5 text-[var(--color-text-muted)]">
            <div className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />
              <p>
                A limpeza é conservadora: arquiva empresas demo antigas para tirá-las do seletor, sem apagar histórico transacional nem quebrar integridade relacional.
              </p>
            </div>
          </div>
        </div>

        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Empresa ativa</p>
              <h3 className="mt-1 text-lg font-black text-[var(--color-text)]">
                {activeCompany?.trade_name || activeCompany?.legal_name || "Nenhuma empresa selecionada"}
              </h3>
            </div>
            {activeIsDemo ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-black text-emerald-100">
                <Sparkles className="h-3.5 w-3.5" /> Demo ativa
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-1.5 text-xs font-black text-[var(--color-text-muted)]">
                <Archive className="h-3.5 w-3.5" /> Operação real/manual
              </span>
            )}
          </div>

          {message ? (
            <div className="mt-4 flex gap-3 rounded-2xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-100">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{message}</span>
            </div>
          ) : null}

          {error ? (
            <div className="mt-4 rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-100">
              {error}
            </div>
          ) : null}

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <DemoMetric label="Vendas" value={formatCount(summary?.sales)} helper="criadas na demo" />
            <DemoMetric label="Recebíveis" value={formatCount(summary?.receivables)} helper="títulos a receber" />
            <DemoMetric label="Contas a pagar" value={formatCount(summary?.payables)} helper="obrigações geradas" />
            <DemoMetric label="Inconsistências" value={formatCount(result?.summary?.inconsistencies)} helper="scan relacional" tone={result?.summary?.inconsistencies ? "risk" : "success"} />
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <DemoDetail label="Produtos / serviços" value={`${formatCount(summary?.products)} / ${formatCount(summary?.services)}`} />
            <DemoDetail label="Movimentos financeiros" value={formatCount(operationalCounts?.movements)} />
            <DemoDetail label="Baixas/liquidações" value={formatCount(operationalCounts?.settlements)} />
            <DemoDetail label="Estoque com saldo" value={formatCount(opening?.stock_balance_count)} />
            <DemoDetail label="AP em aberto" value={formatMoney(opening?.payables_summary?.open_payable_amount)} />
            <DemoDetail label="AP vencido" value={formatMoney(opening?.payables_summary?.overdue_payable_amount)} />
            <DemoDetail label="Stress" value={result ? `${result.summary.passed}/${result.summary.total} testes` : "Aguardando geração"} />
          </div>

          <button
            type="button"
            onClick={() => void reloadCompanies()}
            className="mt-5 inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-black text-[var(--color-text)] transition hover:bg-[var(--color-hover)]"
          >
            <RefreshCw className="h-4 w-4" />
            Recarregar seletor de empresas
          </button>
        </div>
      </div>
    </section>
  )
}

function DemoMetric({ label, value, helper, tone = "normal" }: { label: string; value: string; helper: string; tone?: "normal" | "success" | "risk" }) {
  const toneClass = tone === "success"
    ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
    : tone === "risk"
      ? "border-red-400/40 bg-red-500/10 text-red-100"
      : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"

  return (
    <div className={`rounded-3xl border p-4 ${toneClass}`}>
      <p className="text-xs font-black uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs font-semibold opacity-70">{helper}</p>
    </div>
  )
}

function DemoDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3">
      <p className="text-[10px] font-black uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 text-sm font-black text-[var(--color-text)]">{value}</p>
    </div>
  )
}
