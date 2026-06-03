import { Building2, Loader2, RefreshCw, Sparkles } from "lucide-react"

import { getCompanySelectLabel, isDemoCompany } from "../config/activeCompany"
import { useActiveCompany } from "../config/useActiveCompany"

export function ActiveCompanySwitcher() {
  const {
    companyId,
    companies,
    activeCompany,
    activeCompanyName,
    isCompanyLoading,
    companyError,
    reloadCompanies,
    selectCompany,
  } = useActiveCompany()

  const demoCompanies = companies.filter((company) => isDemoCompany(company))
  const regularCompanies = companies.filter((company) => !isDemoCompany(company))
  const activeIsDemo = isDemoCompany(activeCompany)

  return (
    <div className="flex min-w-0 items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 shadow-lg shadow-[var(--color-card-shadow)]">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
        {isCompanyLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Building2 className="h-4 w-4" />}
      </span>

      <div className="min-w-0">
        <div className="hidden items-center gap-2 sm:flex">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
            Empresa ativa
          </p>
          {activeIsDemo ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-wide text-emerald-100">
              <Sparkles className="h-3 w-3" /> Demo
            </span>
          ) : null}
        </div>
        <select
          value={companyId}
          onChange={(event) => selectCompany(event.target.value)}
          disabled={isCompanyLoading || companies.length === 0}
          className="max-w-[13rem] rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-xs font-bold text-[var(--color-text)] outline-none transition focus:border-[var(--color-primary)] sm:max-w-[18rem]"
          title={companyError ?? activeCompanyName}
          aria-label="Trocar empresa ativa"
        >
          {companies.length === 0 ? (
            <option value="">Cadastre uma empresa</option>
          ) : null}

          {demoCompanies.length > 0 ? (
            <optgroup label="Empresas demo">
              {demoCompanies.map((company) => (
                <option key={company.id} value={company.id}>
                  {getCompanySelectLabel(company)}
                </option>
              ))}
            </optgroup>
          ) : null}

          {regularCompanies.length > 0 ? (
            <optgroup label="Empresas operacionais">
              {regularCompanies.map((company) => (
                <option key={company.id} value={company.id}>
                  {getCompanySelectLabel(company)}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </div>

      <button
        type="button"
        onClick={() => void reloadCompanies()}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
        title="Recarregar empresas do banco"
        aria-label="Recarregar empresas"
      >
        <RefreshCw className="h-4 w-4" />
      </button>
    </div>
  )
}
