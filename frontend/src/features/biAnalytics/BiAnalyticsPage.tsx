import { BarChart3 } from "lucide-react"

export function BiAnalyticsPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-12 text-center shadow-2xl shadow-[var(--color-card-shadow)]">
      <span className="flex h-20 w-20 items-center justify-center rounded-3xl border border-[#10b981]/30 bg-[#10b981]/10 text-[#10b981]">
        <BarChart3 className="h-10 w-10" />
      </span>
      <div>
        <h1 className="text-3xl font-black tracking-tight text-[var(--color-text)]">
          BI / KPIs
        </h1>
        <p className="mt-3 max-w-md text-base text-[var(--color-text-muted)]">
          Esta area esta em desenvolvimento e nao entra no escopo da v1.0. Os indicadores executivos e conexoes Power BI serao homologados em uma etapa posterior.
        </p>
      </div>
      <span className="rounded-full border border-[#10b981]/30 bg-[#10b981]/10 px-4 py-1.5 text-xs font-black uppercase tracking-widest text-[#10b981]">
        Em desenvolvimento
      </span>
    </div>
  )
}
