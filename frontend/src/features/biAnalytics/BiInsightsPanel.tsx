import {
  AlertTriangle,
  BarChart3,
  Briefcase,
  CalendarRange,
  Clock,
  Database,
  Download,
  FileSpreadsheet,
  Loader2,
  PieChart,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"

import {
  downloadBiCsv,
  getAgingPayables,
  getAgingReceivables,
  getCustomerConcentration,
  getDreMonthly,
  getPaymentMethodMix,
  getPowerBiManifest,
  getSupplierConcentration,
  getWorkingCapitalKpis,
} from "./biApi"
import type {
  AgingReport,
  ConcentrationReport,
  DreMonthlyReport,
  PaymentMethodMixReport,
  PowerBiManifest,
  WorkingCapitalKpis,
} from "./types"

type Props = {
  companyId: string
  startDate: string
  endDate: string
}

type SubTab = "kpis" | "aging" | "concentration" | "trend" | "payments" | "powerbi"

const SUB_TABS: Array<{ key: SubTab; label: string; icon: ReactNode }> = [
  { key: "kpis", label: "KPIs executivos", icon: <Briefcase className="h-4 w-4" /> },
  { key: "aging", label: "Aging", icon: <Clock className="h-4 w-4" /> },
  { key: "concentration", label: "Concentração", icon: <Users className="h-4 w-4" /> },
  { key: "trend", label: "Tendência (DRE)", icon: <TrendingUp className="h-4 w-4" /> },
  { key: "payments", label: "Mix pagamentos", icon: <PieChart className="h-4 w-4" /> },
  { key: "powerbi", label: "Power BI Hub", icon: <Database className="h-4 w-4" /> },
]

function toNumber(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0
  const parsed = Number(String(value).replace(",", "."))
  return Number.isFinite(parsed) ? parsed : 0
}

function formatMoney(value?: string | number | null) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(toNumber(value))
}

function formatPercent(value?: string | number | null, fractionDigits = 2) {
  if (value === null || value === undefined || value === "") return "—"
  const numeric = toNumber(value)
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits }).format(numeric) + "%"
}

function formatDays(value?: string | null) {
  if (value === null || value === undefined || value === "") return "—"
  const numeric = toNumber(value)
  return `${numeric.toFixed(1)} d`
}

function formatRatio(value?: string | null) {
  if (value === null || value === undefined || value === "") return "—"
  return toNumber(value).toFixed(2)
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const [year, month, day] = value.slice(0, 10).split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

export function BiInsightsPanel({ companyId, startDate, endDate }: Props) {
  const [subTab, setSubTab] = useState<SubTab>("kpis")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kpis, setKpis] = useState<WorkingCapitalKpis | null>(null)
  const [agingReceivable, setAgingReceivable] = useState<AgingReport | null>(null)
  const [agingPayable, setAgingPayable] = useState<AgingReport | null>(null)
  const [customerConc, setCustomerConc] = useState<ConcentrationReport | null>(null)
  const [supplierConc, setSupplierConc] = useState<ConcentrationReport | null>(null)
  const [dreMonthly, setDreMonthly] = useState<DreMonthlyReport | null>(null)
  const [paymentMix, setPaymentMix] = useState<PaymentMethodMixReport | null>(null)
  const [manifest, setManifest] = useState<PowerBiManifest | null>(null)

  useEffect(() => {
    if (!companyId) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const filters = { start_date: startDate, end_date: endDate }
        const [kpisR, recR, payR, custR, supR, dreR, payMixR, manifestR] = await Promise.all([
          getWorkingCapitalKpis(companyId, filters),
          getAgingReceivables(companyId),
          getAgingPayables(companyId),
          getCustomerConcentration(companyId, { ...filters, top: 10 }),
          getSupplierConcentration(companyId, { ...filters, top: 10 }),
          getDreMonthly(companyId, 12),
          getPaymentMethodMix(companyId, filters),
          getPowerBiManifest(),
        ])
        if (cancelled) return
        setKpis(kpisR.data)
        setAgingReceivable(recR.data)
        setAgingPayable(payR.data)
        setCustomerConc(custR.data)
        setSupplierConc(supR.data)
        setDreMonthly(dreR.data)
        setPaymentMix(payMixR.data)
        setManifest(manifestR.data)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Falha ao carregar BI Analytics.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [companyId, startDate, endDate])

  return (
    <div className="space-y-4">
      {/* Sub-tabs */}
      <div className="flex flex-wrap gap-2 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2">
        {SUB_TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setSubTab(t.key)}
            className={`inline-flex items-center gap-2 rounded-2xl px-3 py-2 text-xs font-black transition ${
              subTab === t.key
                ? "border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando dados de BI...
        </div>
      ) : null}

      {error ? (
        <div className="flex items-start gap-3 rounded-3xl border border-red-400/30 bg-red-500/10 p-4 text-sm font-semibold text-red-200">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /> {error}
        </div>
      ) : null}

      {!loading && !error ? (
        <>
          {subTab === "kpis" && kpis ? <KpisView kpis={kpis} /> : null}
          {subTab === "aging" && agingReceivable && agingPayable ? (
            <AgingView companyId={companyId} receivable={agingReceivable} payable={agingPayable} />
          ) : null}
          {subTab === "concentration" && customerConc && supplierConc ? (
            <ConcentrationView customers={customerConc} suppliers={supplierConc} />
          ) : null}
          {subTab === "trend" && dreMonthly ? (
            <DreTrendView companyId={companyId} report={dreMonthly} />
          ) : null}
          {subTab === "payments" && paymentMix ? <PaymentMixView report={paymentMix} /> : null}
          {subTab === "powerbi" && manifest ? <PowerBiHub companyId={companyId} manifest={manifest} startDate={startDate} endDate={endDate} /> : null}
        </>
      ) : null}
    </div>
  )
}

// =============================================================================
// KPIs view
// =============================================================================

function KpisView({ kpis }: { kpis: WorkingCapitalKpis }) {
  const k = kpis.kpis
  const grossMarginTone = toneFromMargin(k.gross_margin_percent)
  const cccTone = toneFromCCC(k.ccc_days)
  const currentRatioTone = toneFromRatio(k.current_ratio)

  return (
    <div className="space-y-4">
      <KpiHeader
        title="KPIs executivos de capital de giro"
        subtitle={`${kpis.company_display_name} • ${formatDate(kpis.period.start_date)} → ${formatDate(kpis.period.end_date)} (${kpis.period.days ?? 0} dias)`}
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Receita do período"            value={formatMoney(k.revenue_amount)}    helper={`${k.sales_count} vendas`}      icon={<TrendingUp className="h-5 w-5" />}     tone="primary" />
        <KpiCard label="Compras (proxy COGS)"          value={formatMoney(k.purchases_amount)}  helper={`${k.purchases_count} compras`} icon={<Briefcase className="h-5 w-5" />}      tone="neutral" />
        <KpiCard label="Lucro bruto"                   value={formatMoney(k.gross_profit_amount)} helper={`Margem: ${formatPercent(k.gross_margin_percent)}`} icon={<BarChart3 className="h-5 w-5" />} tone={grossMarginTone} />
        <KpiCard label="Caixa total (saldo interno)"   value={formatMoney(k.cash_balance_total)} helper="Soma current_balance"          icon={<Wallet className="h-5 w-5" />}         tone="primary" />

        <KpiCard label="Contas a receber abertas"      value={formatMoney(k.accounts_receivable_open)}  helper={`Vencidas: ${formatMoney(k.accounts_receivable_overdue)}`} icon={<Wallet className="h-5 w-5" />} tone="success" />
        <KpiCard label="Contas a pagar abertas"        value={formatMoney(k.accounts_payable_open)}    helper={`Vencidas: ${formatMoney(k.accounts_payable_overdue)}`}    icon={<Wallet className="h-5 w-5" />} tone="warning" />
        <KpiCard label="Capital de giro"               value={formatMoney(k.working_capital)}          helper="(Caixa + AR) − AP"                                          icon={<Briefcase className="h-5 w-5" />} tone={toNumber(k.working_capital) >= 0 ? "success" : "danger"} />
        <KpiCard label="Liquidez corrente"             value={formatRatio(k.current_ratio)}            helper="Acima de 1.00 = solvente curto prazo"                       icon={<BarChart3 className="h-5 w-5" />} tone={currentRatioTone} />

        <KpiCard label="DSO (dias de recebimento)"     value={formatDays(k.dso_days)} helper="AR aberto ÷ receita diária"     icon={<Clock className="h-5 w-5" />} tone="neutral" />
        <KpiCard label="DPO (dias de pagamento)"       value={formatDays(k.dpo_days)} helper="AP aberto ÷ compras diárias"    icon={<Clock className="h-5 w-5" />} tone="neutral" />
        <KpiCard label="CCC (ciclo de conversão)"      value={formatDays(k.ccc_days)} helper="DSO − DPO. Negativo é melhor."  icon={<Clock className="h-5 w-5" />} tone={cccTone} />
        <KpiCard label="Runway de caixa"               value={formatDays(k.cash_runway_days)} helper={k.cash_runway_days ? "Dias até zerar ao burn atual" : "Geração positiva no período"} icon={<AlertTriangle className="h-5 w-5" />} tone={toneFromRunway(k.cash_runway_days)} />
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 text-xs text-[var(--color-text-muted)]">
        <p className="font-black uppercase tracking-wide text-[var(--color-text)]">Como interpretar</p>
        <ul className="mt-2 space-y-1">
          {Object.entries(kpis.interpretation).map(([code, text]) => (
            <li key={code}>
              <span className="font-bold text-[var(--color-text)]">{code}:</span> {text}
            </li>
          ))}
        </ul>
        {kpis.data_quality.uses_purchases_as_cogs_proxy ? (
          <p className="mt-2 rounded-2xl border border-amber-400/30 bg-amber-500/10 p-3 text-amber-200">
            <strong>Qualidade dos dados:</strong> {kpis.data_quality.note}
          </p>
        ) : null}
      </div>
    </div>
  )
}

function toneFromMargin(percent: string | null) {
  const numeric = toNumber(percent ?? "0")
  if (!percent) return "neutral"
  if (numeric >= 30) return "success"
  if (numeric >= 10) return "warning"
  return "danger"
}

function toneFromCCC(days: string | null) {
  const numeric = toNumber(days ?? "0")
  if (!days) return "neutral"
  if (numeric <= 0) return "success"
  if (numeric <= 30) return "warning"
  return "danger"
}

function toneFromRatio(ratio: string | null) {
  const numeric = toNumber(ratio ?? "0")
  if (!ratio) return "neutral"
  if (numeric >= 1.5) return "success"
  if (numeric >= 1.0) return "warning"
  return "danger"
}

function toneFromRunway(days: string | null) {
  if (!days) return "success"
  const numeric = toNumber(days)
  if (numeric >= 180) return "success"
  if (numeric >= 90) return "warning"
  return "danger"
}

// =============================================================================
// Aging view
// =============================================================================

function AgingView({ companyId, receivable, payable }: { companyId: string; receivable: AgingReport; payable: AgingReport }) {
  return (
    <div className="space-y-4">
      <KpiHeader title="Aging (envelhecimento de títulos)" subtitle="Snapshot de hoje. Buckets por dias vencidos." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AgingCard companyId={companyId} report={receivable} colorTheme="success" />
        <AgingCard companyId={companyId} report={payable} colorTheme="warning" />
      </div>
    </div>
  )
}

function AgingCard({ companyId, report, colorTheme }: { companyId: string; report: AgingReport; colorTheme: "success" | "warning" }) {
  const max = Math.max(...report.buckets.map((b) => toNumber(b.amount)), 1)
  const directionLabel = report.direction === "receivable" ? "A receber" : "A pagar"
  const themeBar = colorTheme === "success" ? "bg-emerald-500/70" : "bg-amber-500/70"

  async function downloadCsv() {
    const path = report.direction === "receivable" ? "/bi/exports/aging-receivables.csv" : "/bi/exports/aging-payables.csv"
    await downloadBiCsv(`${path}?company_id=${companyId}`, `aging_${report.direction}_${companyId}_${report.as_of}`)
  }

  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">{directionLabel}</p>
          <p className="text-lg font-black text-[var(--color-text)]">{formatMoney(report.total_amount)}</p>
          <p className="text-xs text-[var(--color-text-muted)]">{report.total_count} títulos • Vencido: {formatMoney(report.overdue_amount)} ({formatPercent(report.overdue_share_percent)})</p>
        </div>
        <button
          type="button"
          onClick={downloadCsv}
          className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
        >
          <Download className="h-4 w-4" /> CSV
        </button>
      </div>
      <ul className="space-y-2">
        {report.buckets.map((b) => {
          const ratio = (toNumber(b.amount) / max) * 100
          return (
            <li key={b.code} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[var(--color-text)]">{b.label}</span>
                <span className="text-[var(--color-text-muted)]">{b.count} • {formatMoney(b.amount)} • {formatPercent(b.share_percent)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--color-bg-soft)]">
                <div className={`h-full rounded-full ${themeBar}`} style={{ width: `${ratio}%` }} />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// =============================================================================
// Concentration view
// =============================================================================

function ConcentrationView({ customers, suppliers }: { customers: ConcentrationReport; suppliers: ConcentrationReport }) {
  return (
    <div className="space-y-4">
      <KpiHeader title="Concentração (Pareto + ABC)" subtitle="Top 10 por volume no período. ABC: A=80%, B=15%, C=5%." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ConcentrationTable title="Top clientes" report={customers} />
        <ConcentrationTable title="Top fornecedores" report={suppliers} />
      </div>
    </div>
  )
}

function ConcentrationTable({ title, report }: { title: string; report: ConcentrationReport }) {
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <div className="mb-3">
        <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">{title}</p>
        <p className="text-lg font-black text-[var(--color-text)]">{formatMoney(report.total_amount)} • {report.total_participants} participantes</p>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--color-border-soft)] text-left text-[var(--color-text-muted)]">
            <th className="pb-2 pr-2">#</th>
            <th className="pb-2 pr-2">Participante</th>
            <th className="pb-2 pr-2 text-right">Volume</th>
            <th className="pb-2 pr-2 text-right">Share</th>
            <th className="pb-2 text-right">Acum.</th>
            <th className="pb-2 pl-2 text-center">ABC</th>
          </tr>
        </thead>
        <tbody>
          {report.items.map((item) => (
            <tr key={item.participant_id ?? item.rank} className="border-b border-[var(--color-border-soft)]/50 text-[var(--color-text)]">
              <td className="py-1.5 pr-2 font-bold">{item.rank}</td>
              <td className="py-1.5 pr-2 truncate max-w-[180px]">{item.participant_name}</td>
              <td className="py-1.5 pr-2 text-right font-mono">{formatMoney(item.amount)}</td>
              <td className="py-1.5 pr-2 text-right text-[var(--color-text-muted)]">{formatPercent(item.share_percent)}</td>
              <td className="py-1.5 text-right text-[var(--color-text-muted)]">{formatPercent(item.cumulative_share_percent)}</td>
              <td className="py-1.5 pl-2 text-center">
                <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-black ${
                  item.abc_class === "A" ? "bg-emerald-500/20 text-emerald-300" : item.abc_class === "B" ? "bg-amber-500/20 text-amber-300" : "bg-slate-500/20 text-slate-300"
                }`}>{item.abc_class}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.others_summary.count > 0 ? (
        <p className="mt-2 text-xs text-[var(--color-text-muted)]">
          + {report.others_summary.count} outros ({formatMoney(report.others_summary.amount)} • {formatPercent(report.others_summary.share_percent)})
        </p>
      ) : null}
    </div>
  )
}

// =============================================================================
// DRE trend view
// =============================================================================

function DreTrendView({ companyId, report }: { companyId: string; report: DreMonthlyReport }) {
  const max = Math.max(...report.series.map((r) => toNumber(r.revenue_amount)), 1)
  async function downloadCsv() {
    await downloadBiCsv(`/bi/exports/dre-monthly.csv?company_id=${companyId}&months=${report.months}`, `dre_monthly_${companyId}`)
  }
  return (
    <div className="space-y-4">
      <KpiHeader
        title={`Tendência mensal — ${report.months} meses`}
        subtitle="Receita, lucro bruto e margem. MoM e YoY na tabela."
        action={
          <button
            type="button"
            onClick={downloadCsv}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
          >
            <Download className="h-4 w-4" /> CSV
          </button>
        }
      />
      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <div className="mb-3 grid grid-cols-12 gap-2">
          {report.series.map((row) => {
            const ratio = (toNumber(row.revenue_amount) / max) * 100
            return (
              <div key={row.month_key} className="col-span-1 flex flex-col items-center gap-1">
                <div className="h-32 w-full rounded-lg bg-[var(--color-bg-soft)] flex items-end overflow-hidden" title={`Receita ${formatMoney(row.revenue_amount)}`}>
                  <div className="w-full bg-gradient-to-t from-[var(--color-primary)] to-[var(--color-primary)]/50" style={{ height: `${ratio}%` }} />
                </div>
                <span className="text-[10px] font-bold text-[var(--color-text-muted)]">{row.month_label}</span>
              </div>
            )
          })}
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--color-border-soft)] text-left text-[var(--color-text-muted)]">
              <th className="pb-2 pr-2">Mês</th>
              <th className="pb-2 pr-2 text-right">Receita</th>
              <th className="pb-2 pr-2 text-right">Compras</th>
              <th className="pb-2 pr-2 text-right">Lucro bruto</th>
              <th className="pb-2 pr-2 text-right">Margem</th>
              <th className="pb-2 pr-2 text-right">MoM</th>
              <th className="pb-2 text-right">YoY</th>
            </tr>
          </thead>
          <tbody>
            {report.series.map((row) => (
              <tr key={row.month_key} className="border-b border-[var(--color-border-soft)]/50 text-[var(--color-text)]">
                <td className="py-1.5 pr-2 font-bold">{row.month_label}</td>
                <td className="py-1.5 pr-2 text-right font-mono">{formatMoney(row.revenue_amount)}</td>
                <td className="py-1.5 pr-2 text-right font-mono text-[var(--color-text-muted)]">{formatMoney(row.purchases_amount)}</td>
                <td className="py-1.5 pr-2 text-right font-mono">{formatMoney(row.gross_profit_amount)}</td>
                <td className="py-1.5 pr-2 text-right">{formatPercent(row.gross_margin_percent)}</td>
                <td className={`py-1.5 pr-2 text-right ${signTone(row.revenue_mom_percent)}`}>{formatPercent(row.revenue_mom_percent)}</td>
                <td className={`py-1.5 text-right ${signTone(row.revenue_yoy_percent)}`}>{formatPercent(row.revenue_yoy_percent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function signTone(value: string | null) {
  if (!value) return "text-[var(--color-text-muted)]"
  const n = toNumber(value)
  if (n > 0) return "text-emerald-400"
  if (n < 0) return "text-red-400"
  return "text-[var(--color-text-muted)]"
}

// =============================================================================
// Payment mix view
// =============================================================================

function PaymentMixView({ report }: { report: PaymentMethodMixReport }) {
  return (
    <div className="space-y-4">
      <KpiHeader title="Mix de meios de pagamento" subtitle="Baseado nos planos de pagamento das vendas no período." />
      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <p className="mb-3 text-xs text-[var(--color-text-muted)]">
          Volume total: <span className="font-black text-[var(--color-text)]">{formatMoney(report.total_amount)}</span>
        </p>
        <ul className="space-y-2">
          {report.items.map((item) => {
            const ratio = toNumber(item.share_percent)
            return (
              <li key={item.method_code} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-[var(--color-text)]">{item.method_name}</span>
                  <span className="text-[var(--color-text-muted)]">{item.plan_count} planos • {formatMoney(item.amount)} • {formatPercent(item.share_percent)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[var(--color-bg-soft)]">
                  <div className="h-full rounded-full bg-[var(--color-primary)]" style={{ width: `${ratio}%` }} />
                </div>
              </li>
            )
          })}
          {report.items.length === 0 ? <p className="text-xs text-[var(--color-text-muted)]">Sem registros no período.</p> : null}
        </ul>
      </div>
    </div>
  )
}

// =============================================================================
// Power BI Hub view
// =============================================================================

function PowerBiHub({ companyId, manifest, startDate, endDate }: { companyId: string; manifest: PowerBiManifest; startDate: string; endDate: string }) {
  const [copied, setCopied] = useState(false)

  function copyTemplate() {
    const tpl = manifest.power_query_template_m.replace("emp_xxxxxxx", companyId)
    void navigator.clipboard.writeText(tpl).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2500)
    })
  }

  return (
    <div className="space-y-4">
      <KpiHeader title="Power BI Hub" subtitle={`Manifest v${manifest.version} • Atualizado em ${formatDate(manifest.generated_at.slice(0, 10))}`} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
          <p className="mb-2 text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Formato dos arquivos</p>
          <ul className="text-xs text-[var(--color-text)] space-y-0.5">
            {Object.entries(manifest.format).map(([k, v]) => (
              <li key={k}><span className="text-[var(--color-text-muted)]">{k}:</span> <span className="font-mono">{v}</span></li>
            ))}
          </ul>
        </div>
        <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
          <p className="mb-2 text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Autenticação</p>
          <p className="text-xs text-[var(--color-text)]"><span className="text-[var(--color-text-muted)]">Esquema:</span> <span className="font-mono">{manifest.auth.scheme}</span></p>
          <p className="text-xs text-[var(--color-text)]"><span className="text-[var(--color-text-muted)]">Header:</span> <span className="font-mono">{manifest.auth.header_name}</span></p>
          <p className="mt-2 rounded-2xl border border-amber-400/30 bg-amber-500/10 p-2 text-[10px] text-amber-200">{manifest.auth.note}</p>
        </div>
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Tabelas Fato</p>
          <span className="text-[10px] text-[var(--color-text-muted)]">Click para baixar CSV / abrir JSON</span>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {manifest.facts.map((f) => (
            <ExportRow key={f.name} entry={f} companyId={companyId} startDate={startDate} endDate={endDate} kind="fact" />
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <p className="mb-3 text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Dimensões</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {manifest.dimensions.map((d) => (
            <ExportRow key={d.name} entry={d} companyId={companyId} startDate={startDate} endDate={endDate} kind="dim" />
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Power Query M (cole no Power BI Desktop)</p>
          <button
            type="button"
            onClick={copyTemplate}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-bold text-[var(--color-primary)] hover:bg-[var(--color-hover)]"
          >
            <FileSpreadsheet className="h-4 w-4" /> {copied ? "Copiado!" : "Copiar template"}
          </button>
        </div>
        <pre className="overflow-x-auto rounded-2xl bg-[var(--color-bg)] p-3 text-[11px] text-[var(--color-text)]">
{manifest.power_query_template_m.replace("emp_xxxxxxx", companyId)}
        </pre>
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
        <p className="mb-2 text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Recomendações Power BI</p>
        <ul className="list-disc pl-5 text-xs text-[var(--color-text)] space-y-1">
          {manifest.powerbi_recommendations.map((rec) => (
            <li key={rec}>{rec}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function ExportRow({ entry, companyId, startDate, endDate, kind }: { entry: { name: string; endpoint: string; grain?: string; key?: string }; companyId: string; startDate: string; endDate: string; kind: "fact" | "dim" }) {
  const isCalendar = entry.name === "dim_calendar"
  const path = entry.endpoint
    .replace("/api", "")
    .replace("{company_id}", companyId)
    .replace("{start}", isCalendar ? startDate : "")
    .replace("{end}", isCalendar ? endDate : "")
  async function download() {
    const fileName = `${entry.name}_${companyId}`
    await downloadBiCsv(path, fileName)
  }
  const themeIcon = kind === "fact" ? "text-[var(--color-primary)]" : "text-emerald-400"
  return (
    <div className="flex items-center justify-between gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3">
      <div className="min-w-0">
        <p className={`text-xs font-black ${themeIcon}`}>{entry.name}</p>
        <p className="truncate text-[10px] text-[var(--color-text-muted)]">{entry.grain ?? entry.key ?? entry.endpoint}</p>
      </div>
      <div className="flex shrink-0 gap-1">
        <button
          type="button"
          onClick={download}
          className="inline-flex items-center gap-1 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-2 py-1 text-[10px] font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
        >
          <Download className="h-3 w-3" /> CSV
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// Building blocks
// =============================================================================

function KpiHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-[var(--color-text)]">
          <CalendarRange className="h-4 w-4" /> {title}
        </p>
        <p className="text-xs text-[var(--color-text-muted)]">{subtitle}</p>
      </div>
      {action}
    </div>
  )
}

function KpiCard({
  label,
  value,
  helper,
  icon,
  tone = "neutral",
}: {
  label: string
  value: string
  helper: string
  icon: ReactNode
  tone?: "primary" | "success" | "warning" | "danger" | "neutral"
}) {
  const toneClass = {
    primary: "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]",
    success: "border-emerald-400/30 bg-emerald-500/10 text-emerald-300",
    warning: "border-amber-400/30 bg-amber-500/10 text-amber-300",
    danger: "border-red-400/30 bg-red-500/10 text-red-300",
    neutral: "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)]",
  }[tone]

  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-black uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
          <p className="mt-1.5 truncate text-xl font-black text-[var(--color-text)]">{value}</p>
          <p className="mt-0.5 truncate text-[10px] text-[var(--color-text-muted)]">{helper}</p>
        </div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border ${toneClass}`}>{icon}</span>
      </div>
    </div>
  )
}
