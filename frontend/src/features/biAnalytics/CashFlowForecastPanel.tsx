import {
  AlertTriangle,
  BarChart3,
  Download,
  Loader2,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"

import { buildExportFileName } from "../../lib/exportStandard"
import { dateCell, exportXlsxWorkbook, integerCell, moneyCell, type ExportSheet, type ExportTable } from "../../lib/exportTable"
import { downloadBiCsv, getCashFlow13w, getCashFlowByCategory } from "./biApi"
import type { CashFlow13wReport, CashFlowByCategoryReport } from "./types"

type Props = {
  companyId: string
  startDate: string
  endDate: string
  financialAccountId?: string
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
  const [year, month, day] = value.slice(0, 10).split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return
    query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `?${serialized}` : ""
}

function forecastSheets(report: CashFlow13wReport): ExportSheet[] {
  const summary: ExportTable = [
    ["Campo", "Valor"],
    ["Empresa", report.company_display_name],
    ["Empresa ID", report.company_id],
    ["Conta financeira", report.financial_account_id ?? "Todas"],
    ["Semana inicial", dateCell(report.starting_week)],
    ["Semana final", dateCell(report.ending_week)],
    ["Semanas", integerCell(report.weeks)],
    ["Saldo de abertura", moneyCell(report.opening_balance_amount)],
    ["Vencidos a receber", moneyCell(report.overdue_inflow_amount)],
    ["Qtd. vencidos a receber", integerCell(report.overdue_inflow_count)],
    ["Vencidos a pagar", moneyCell(report.overdue_outflow_amount)],
    ["Qtd. vencidos a pagar", integerCell(report.overdue_outflow_count)],
    [],
    ["Nota", "Previsão baseada em títulos em aberto por vencimento. Não inclui vendas futuras, compras futuras ou sazonalidade."],
  ]
  return [
    { name: "Resumo", rows: summary },
    {
      name: "13 semanas",
      rows: [
        ["Semana", "Início", "Fim", "Entradas previstas", "Qtd. entradas", "Saídas previstas", "Qtd. saídas", "Líquido", "Saldo projetado", "Inclui vencidos"],
        ...report.weekly.map((week) => [
          integerCell(week.week_index),
          dateCell(week.week_start),
          dateCell(week.week_end),
          moneyCell(week.expected_inflow_amount),
          integerCell(week.expected_inflow_count),
          moneyCell(week.expected_outflow_amount),
          integerCell(week.expected_outflow_count),
          moneyCell(week.net_amount),
          moneyCell(week.projected_balance_amount),
          week.includes_overdue ? "Sim" : "Não",
        ]),
      ],
    },
  ]
}

function categorySheets(report: CashFlowByCategoryReport): ExportSheet[] {
  const summary: ExportTable = [
    ["Campo", "Valor"],
    ["Empresa", report.company_display_name],
    ["Empresa ID", report.company_id],
    ["Conta financeira", report.financial_account_id ?? "Todas"],
    ["Período inicial", dateCell(report.period.start_date)],
    ["Período final", dateCell(report.period.end_date)],
    ["Entradas realizadas", moneyCell(report.total_inflow_amount)],
    ["Saídas realizadas", moneyCell(report.total_outflow_amount)],
    ["Líquido realizado", moneyCell(report.total_net_amount)],
    [],
    ["Nota", "Fluxo por categoria usa baixas realizadas, não títulos previstos."],
  ]
  const rows: ExportTable = [
    ["Grupo", "Categoria ID", "Categoria", "Entradas", "Saídas", "Líquido", "Baixas"],
    ...report.groups.flatMap((group) => group.categories.map((category) => [
      group.label,
      category.category_id,
      category.category_name,
      moneyCell(category.inflow_amount),
      moneyCell(category.outflow_amount),
      moneyCell(category.net_amount),
      integerCell(category.settlement_count),
    ])),
  ]
  return [{ name: "Resumo", rows: summary }, { name: "Categorias", rows }]
}

export function CashFlowForecastPanel({ companyId, startDate, endDate, financialAccountId }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forecast, setForecast] = useState<CashFlow13wReport | null>(null)
  const [byCategory, setByCategory] = useState<CashFlowByCategoryReport | null>(null)

  useEffect(() => {
    if (!companyId) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [forecastR, catR] = await Promise.all([
          getCashFlow13w(companyId, { weeks: 13, start_date: startDate, financial_account_id: financialAccountId }),
          getCashFlowByCategory(companyId, { start_date: startDate, end_date: endDate, financial_account_id: financialAccountId }),
        ])
        if (cancelled) return
        setForecast(forecastR.data)
        setByCategory(catR.data)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? err.message : "Falha ao carregar previsão de caixa.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [companyId, startDate, endDate, financialAccountId])

  async function downloadForecastCsv() {
    await downloadBiCsv(`/bi/exports/cash-flow-13w.csv${buildQuery({ company_id: companyId, weeks: 13, start_date: startDate, financial_account_id: financialAccountId })}`, `previsao_13s_${companyId}_${startDate}`)
  }

  async function downloadCategoryCsv() {
    await downloadBiCsv(`/bi/exports/cash-flow-by-category.csv${buildQuery({ company_id: companyId, start_date: startDate, end_date: endDate, financial_account_id: financialAccountId })}`, `fluxo_categoria_${companyId}_${startDate}_${endDate}`)
  }

  function downloadForecastXlsx() {
    if (!forecast) return
    exportXlsxWorkbook(forecastSheets(forecast), buildExportFileName("kovir_bi", `previsao_13s_${companyId}_${startDate}`, "xlsx"))
  }

  function downloadCategoryXlsx() {
    if (!byCategory) return
    exportXlsxWorkbook(categorySheets(byCategory), buildExportFileName("kovir_bi", `fluxo_categoria_${companyId}_${startDate}_${endDate}`, "xlsx"))
  }

  return (
    <div className="space-y-5">
      {loading ? (
        <div className="flex items-center gap-2 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando previsão de caixa...
        </div>
      ) : null}

      {error ? (
        <div className="flex items-start gap-3 rounded-3xl border border-red-400/30 bg-red-500/10 p-4 text-sm font-semibold text-red-200">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /> {error}
        </div>
      ) : null}

      {!loading && !error && forecast ? <ForecastTable report={forecast} onDownloadCsv={downloadForecastCsv} onDownloadXlsx={downloadForecastXlsx} /> : null}
      {!loading && !error && byCategory ? <CategoryBreakdown report={byCategory} onDownloadCsv={downloadCategoryCsv} onDownloadXlsx={downloadCategoryXlsx} /> : null}
    </div>
  )
}

function ForecastTable({ report, onDownloadCsv, onDownloadXlsx }: { report: CashFlow13wReport; onDownloadCsv: () => Promise<void>; onDownloadXlsx: () => void }) {
  const maxAbs = Math.max(...report.weekly.map((w) => Math.abs(toNumber(w.net_amount))), 1)
  const openingBalance = toNumber(report.opening_balance_amount)

  return (
    <section className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border-soft)] p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <BarChart3 className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-black text-[var(--color-text)]">Previsão de caixa — 13 semanas</h2>
            <p className="text-xs text-[var(--color-text-muted)]">
              Saldo abertura: {formatMoney(report.opening_balance_amount)} •
              Vencidos a receber: {formatMoney(report.overdue_inflow_amount)} ({report.overdue_inflow_count}) •
              Vencidos a pagar: {formatMoney(report.overdue_outflow_amount)} ({report.overdue_outflow_count})
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onDownloadCsv}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
          >
            <Download className="h-4 w-4" /> CSV
          </button>
          <button
            type="button"
            onClick={onDownloadXlsx}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-bold text-[var(--color-primary)] hover:bg-[var(--color-hover)]"
          >
            <Download className="h-4 w-4" /> XLSX
          </button>
        </div>
      </div>

      <div className="border-b border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-3 text-xs font-semibold leading-5 text-[var(--color-text-muted)]">
        Previsão baseada em títulos em aberto por vencimento. Não inclui novas vendas, novas compras ou sazonalidade. O fluxo por categoria abaixo é realizado por baixas, não previsão.
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="bg-[var(--color-bg-soft)] text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
              <th className="px-4 py-3 text-left">Semana</th>
              <th className="px-4 py-3 text-left">Período</th>
              <th className="px-4 py-3 text-right">Entradas prev.</th>
              <th className="px-4 py-3 text-right">Saídas prev.</th>
              <th className="px-4 py-3 text-right">Líquido</th>
              <th className="px-4 py-3 text-right">Saldo projetado</th>
              <th className="px-4 py-3 pl-2">Balanço</th>
            </tr>
          </thead>
          <tbody>
            {report.weekly.map((week) => {
              const net = toNumber(week.net_amount)
              const ratio = (Math.abs(net) / maxAbs) * 100
              const isPositive = net >= 0
              const projBalance = toNumber(week.projected_balance_amount)
              const isBalanceLow = projBalance < openingBalance * 0.2
              return (
                <tr key={week.week_index} className="border-t border-[var(--color-border-soft)]">
                  <td className="px-4 py-3 font-black text-[var(--color-text)]">S{week.week_index}</td>
                  <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                    {formatDate(week.week_start)} → {formatDate(week.week_end)}
                    {week.includes_overdue ? <span className="ml-1 text-amber-400">*</span> : null}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-400">{formatMoney(week.expected_inflow_amount)}</td>
                  <td className="px-4 py-3 text-right font-mono text-red-400">{formatMoney(week.expected_outflow_amount)}</td>
                  <td className={`px-4 py-3 text-right font-black font-mono ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
                    {isPositive ? "+" : ""}{formatMoney(week.net_amount)}
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${isBalanceLow ? "text-amber-400" : "text-[var(--color-text)]"}`}>
                    {formatMoney(week.projected_balance_amount)}
                  </td>
                  <td className="px-4 py-3 pl-2">
                    <div className="flex h-3 w-full min-w-[60px] overflow-hidden rounded-full bg-[var(--color-bg-soft)]">
                      <div
                        className={`h-full rounded-full ${isPositive ? "bg-emerald-500/70" : "bg-red-500/70"}`}
                        style={{ width: `${ratio}%` }}
                      />
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {Object.keys(report.interpretation).length > 0 ? (
        <div className="border-t border-[var(--color-border-soft)] p-4 text-xs text-[var(--color-text-muted)]">
          <p className="font-black uppercase tracking-wide text-[var(--color-text)]">Interpretação</p>
          <ul className="mt-2 space-y-1">
            {Object.entries(report.interpretation).map(([code, text]) => (
              <li key={code}><span className="font-bold text-[var(--color-text)]">{code}:</span> {text}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

function CategoryBreakdown({ report, onDownloadCsv, onDownloadXlsx }: { report: CashFlowByCategoryReport; onDownloadCsv: () => Promise<void>; onDownloadXlsx: () => void }) {
  const groupColors: Record<string, string> = {
    OPERATIONAL: "text-emerald-400 border-emerald-400/30 bg-emerald-500/10",
    INVESTMENT: "text-blue-400 border-blue-400/30 bg-blue-500/10",
    FINANCING: "text-purple-400 border-purple-400/30 bg-purple-500/10",
  }

  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border-soft)] p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            <Wallet className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-black text-[var(--color-text)]">Fluxo por categoria — DFC</h2>
            <p className="text-xs text-[var(--color-text-muted)]">
              Realizado por baixas no período. Operacional / Investimento / Financiamento.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <NetIndicator inflow={report.total_inflow_amount} outflow={report.total_outflow_amount} net={report.total_net_amount} />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onDownloadCsv}
              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            >
              <Download className="h-4 w-4" /> CSV
            </button>
            <button
              type="button"
              onClick={onDownloadXlsx}
              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-bold text-[var(--color-primary)] hover:bg-[var(--color-hover)]"
            >
              <Download className="h-4 w-4" /> XLSX
            </button>
          </div>
        </div>
      </div>

      <div className="divide-y divide-[var(--color-border-soft)]">
        {report.groups.map((group) => {
          const colorClass = groupColors[group.cash_flow_group] ?? "text-[var(--color-text-muted)] border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]"
          return (
            <div key={group.cash_flow_group} className="p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 rounded-2xl border px-3 py-1 text-xs font-black ${colorClass}`}>
                    {group.label}
                  </span>
                </div>
                <NetIndicator inflow={group.inflow_amount} outflow={group.outflow_amount} net={group.net_amount} />
              </div>

              {group.categories.length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[var(--color-text-muted)]">
                      <th className="pb-1 pr-3">Categoria</th>
                      <th className="pb-1 pr-3 text-right">Entradas</th>
                      <th className="pb-1 pr-3 text-right">Saídas</th>
                      <th className="pb-1 text-right">Líquido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.categories.map((cat) => {
                      const net = toNumber(cat.net_amount)
                      return (
                        <tr key={cat.category_id} className="border-t border-[var(--color-border-soft)]/40">
                          <td className="py-1.5 pr-3 font-semibold text-[var(--color-text)]">{cat.category_name}</td>
                          <td className="py-1.5 pr-3 text-right font-mono text-emerald-400">{formatMoney(cat.inflow_amount)}</td>
                          <td className="py-1.5 pr-3 text-right font-mono text-red-400">{formatMoney(cat.outflow_amount)}</td>
                          <td className={`py-1.5 text-right font-black font-mono ${net >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {net >= 0 ? "+" : ""}{formatMoney(cat.net_amount)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="text-xs text-[var(--color-text-muted)]">Sem movimentos categorizados neste grupo.</p>
              )}
            </div>
          )
        })}
        {report.groups.length === 0 ? (
          <p className="p-4 text-sm text-[var(--color-text-muted)]">Sem dados de fluxo por categoria no período.</p>
        ) : null}
      </div>

      {Object.keys(report.interpretation ?? {}).length > 0 ? (
        <div className="border-t border-[var(--color-border-soft)] p-4 text-xs text-[var(--color-text-muted)]">
          <p className="font-black uppercase tracking-wide text-[var(--color-text)]">Notas de interpretação</p>
          <ul className="mt-2 space-y-1">
            {Object.entries(report.interpretation).map(([code, text]) => (
              <li key={code}><span className="font-bold text-[var(--color-text)]">{code}:</span> {text}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

function NetIndicator({ inflow, outflow, net }: { inflow: string; outflow: string; net: string }) {
  const netValue = toNumber(net)
  const isPositive = netValue >= 0
  const Icon = isPositive ? TrendingUp : TrendingDown
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-emerald-400">{formatMoney(inflow)}</span>
      <span className="text-[var(--color-text-muted)]">/</span>
      <span className="text-red-400">{formatMoney(outflow)}</span>
      <span className={`inline-flex items-center gap-1 font-black ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
        <Icon className="h-3.5 w-3.5" />
        {isPositive ? "+" : ""}{formatMoney(net)}
      </span>
    </div>
  )
}

export function ForecastSummaryCards({ report }: { report: CashFlow13wReport }): ReactNode {
  const totalInflow = report.weekly.reduce((sum, w) => sum + toNumber(w.expected_inflow_amount), 0)
  const totalOutflow = report.weekly.reduce((sum, w) => sum + toNumber(w.expected_outflow_amount), 0)
  const finalBalance = report.weekly.length > 0
    ? toNumber(report.weekly[report.weekly.length - 1]?.projected_balance_amount)
    : toNumber(report.opening_balance_amount)

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <SummaryCard label="Entradas previstas (13s)" value={formatMoney(totalInflow)} tone="success" icon={<TrendingUp className="h-5 w-5" />} />
      <SummaryCard label="Saídas previstas (13s)" value={formatMoney(totalOutflow)} tone="warning" icon={<TrendingDown className="h-5 w-5" />} />
      <SummaryCard label="Saldo projetado final" value={formatMoney(finalBalance)} tone={finalBalance >= 0 ? "success" : "danger"} icon={<Wallet className="h-5 w-5" />} />
    </div>
  )
}

function SummaryCard({ label, value, icon, tone }: { label: string; value: string; icon: ReactNode; tone: "success" | "warning" | "danger" | "neutral" }) {
  const toneClass = {
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
        </div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border ${toneClass}`}>{icon}</span>
      </div>
    </div>
  )
}
