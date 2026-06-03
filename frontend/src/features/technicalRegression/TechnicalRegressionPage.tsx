import { useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, Database, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import {
  getTechnicalRegressionAvailableCompanies,
  getTechnicalRegressionDatabaseHealth,
  getTechnicalRegressionFinancialIntegrity,
  getTechnicalRegressionRules,
  getTechnicalRegressionSchemaContract,
  runTechnicalRegression,
} from "./technicalRegressionApi"
import type {
  TechnicalRegressionAvailableCompanies,
  TechnicalRegressionCheck,
  TechnicalRegressionDatabaseHealth,
  TechnicalRegressionFinancialIntegrity,
  TechnicalRegressionRules,
  TechnicalRegressionRun,
  TechnicalRegressionSchemaContract,
} from "./types"

type Notice = { type: "error" | "success"; message: string } | null

function statusTone(status?: string | null) {
  if (status === "PASS") return "success"
  if (status === "WARN" || status === "SKIP") return "warning"
  if (status === "FAIL") return "danger"
  return "neutral"
}

function statusClass(status?: string | null) {
  const tone = statusTone(status)
  if (tone === "success") return "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
  if (tone === "warning") return "border-amber-400/40 bg-amber-500/10 text-amber-100"
  if (tone === "danger") return "border-red-400/40 bg-red-500/10 text-red-100"
  return "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)]"
}

export function TechnicalRegressionPage() {
  const { companyId, activeCompanyName, isCompanyResolved } = useActiveCompany()
  const [profile, setProfile] = useState<"quick" | "full">("quick")
  const [rules, setRules] = useState<TechnicalRegressionRules | null>(null)
  const [availableCompanies, setAvailableCompanies] = useState<TechnicalRegressionAvailableCompanies | null>(null)
  const [databaseHealth, setDatabaseHealth] = useState<TechnicalRegressionDatabaseHealth | null>(null)
  const [schemaContract, setSchemaContract] = useState<TechnicalRegressionSchemaContract | null>(null)
  const [financialIntegrity, setFinancialIntegrity] = useState<TechnicalRegressionFinancialIntegrity | null>(null)
  const [runResult, setRunResult] = useState<TechnicalRegressionRun | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [isLoading, setIsLoading] = useState(false)

  const selectedCompanyId = isCompanyResolved && companyId ? companyId : undefined
  const selectedCompanyName = runResult?.company?.display_name ?? activeCompanyName

  async function loadRegression() {
    setIsLoading(true)
    setNotice(null)
    try {
      const [rulesResponse, companiesResponse, databaseResponse, schemaResponse, integrityResponse, runResponse] =
        await Promise.all([
          getTechnicalRegressionRules(),
          getTechnicalRegressionAvailableCompanies(10),
          getTechnicalRegressionDatabaseHealth(),
          getTechnicalRegressionSchemaContract(),
          getTechnicalRegressionFinancialIntegrity(selectedCompanyId),
          runTechnicalRegression({ companyId: selectedCompanyId, profile }),
        ])

      setRules(rulesResponse.data)
      setAvailableCompanies(companiesResponse.data)
      setDatabaseHealth(databaseResponse.data)
      setSchemaContract(schemaResponse.data)
      setFinancialIntegrity(integrityResponse.data)
      setRunResult(runResponse.data)
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Erro ao carregar regressão técnica." })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadRegression()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCompanyId, profile])

  const failedChecks = useMemo(
    () => (financialIntegrity?.checks ?? []).filter((check) => check.status === "FAIL"),
    [financialIntegrity],
  )

  return (
    <div className="space-y-6">
      <header className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="grid gap-0 xl:grid-cols-[1.35fr_0.65fr]">
          <div className="p-6 sm:p-8">
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <InfoPill icon={<ShieldCheck className="h-4 w-4" />} label="Bloco 15" />
              <InfoPill icon={<Database className="h-4 w-4" />} label="Regressão técnica" />
              <InfoPill icon={<AlertTriangle className="h-4 w-4" />} label="Read-only" />
            </div>

            <p className="text-sm font-semibold text-[var(--color-primary)]">Governança de backend</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-[var(--color-text)] sm:text-5xl">
              Regressão Técnica <span className="text-[var(--color-primary)]">Permanente</span>
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)] sm:text-base sm:leading-7">
              Esta tela valida saúde do banco, contrato de schema e integridade financeira sem criar fatos novos. Use como gate
              antes de avançar backend ou frontend.
            </p>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Empresa em análise" value={selectedCompanyName} helper="Escopo travado na empresa da sessão" />
              <MetricCard label="Status geral" value={runResult?.overall_status ?? "—"} helper={runResult?.recommended_gate.reason ?? "Carregando"} tone={statusTone(runResult?.overall_status)} />
              <MetricCard label="Checks com falha" value={String(failedChecks.length)} helper="integridade financeira" tone={failedChecks.length > 0 ? "danger" : "success"} />
            </div>
          </div>

          <aside className="border-t border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 xl:border-l xl:border-t-0 sm:p-8">
            <div className="flex items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                {isLoading ? <Loader2 className="h-6 w-6 animate-spin" /> : <ShieldCheck className="h-6 w-6" />}
              </span>
              <div>
                <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Perfil</p>
                <h2 className="text-lg font-black text-[var(--color-text)]">{profile.toUpperCase()}</h2>
              </div>
            </div>

            <div className="mt-6 space-y-3">
              <label className="space-y-1">
                <span className="text-xs font-bold text-[var(--color-text-muted)]">Modo de execução</span>
                <select value={profile} onChange={(event) => setProfile(event.target.value as "quick" | "full")} className="w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]">
                  <option value="quick">quick</option>
                  <option value="full">full</option>
                </select>
              </label>

              <button type="button" onClick={() => void loadRegression()} className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:bg-[var(--color-hover)]">
                <RefreshCw className="h-4 w-4" /> Reexecutar regressão
              </button>
            </div>
          </aside>
        </div>
      </header>

      {notice ? <NoticeBox type={notice.type} message={notice.message} /> : null}

      <section className="grid gap-5 lg:grid-cols-3">
        <StatusCard title="Banco" status={databaseHealth?.status} helper={databaseHealth ? `${databaseHealth.database_name} • ${databaseHealth.table_count} tabelas` : "Carregando"} />
        <StatusCard title="Schema" status={schemaContract?.status} helper={schemaContract ? `${schemaContract.summary.missing_required_tables} tabelas ausentes` : "Carregando"} />
        <StatusCard title="Integridade" status={financialIntegrity?.status} helper={financialIntegrity ? `${financialIntegrity.summary.failed} falhas críticas` : "Carregando"} />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Card title="Checks financeiros">
          <div className="space-y-2">
            {(financialIntegrity?.checks ?? []).slice(0, 12).map((check) => (
              <CheckRow key={check.code} check={check} />
            ))}
          </div>
        </Card>

        <Card title="Contrato de schema">
          <div className="space-y-3 text-sm">
            <p className="text-[var(--color-text-muted)]">Grupos com ausência: {(schemaContract?.summary.groups_with_missing_tables ?? []).length}</p>
            <p className="text-[var(--color-text-muted)]">Tabelas com colunas faltantes: {schemaContract?.summary.tables_with_missing_columns ?? 0}</p>
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3">
              <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">Exemplo de lacunas</p>
              <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                {Object.keys(schemaContract?.missing_columns ?? {}).slice(0, 4).join(", ") || "Sem lacunas reportadas."}
              </p>
            </div>
          </div>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Card title="Princípios do bloco">
          <ul className="space-y-2">
            {(rules?.principles ?? []).map((item) => (
              <li key={item} className="rounded-2xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">{item}</li>
            ))}
          </ul>
        </Card>
        <Card title="Empresas disponíveis">
          <div className="space-y-2">
            {(availableCompanies?.items ?? []).slice(0, 8).map((company) => (
              <div key={company.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                <p className="text-sm font-bold text-[var(--color-text)]">{company.display_name}</p>
              </div>
            ))}
          </div>
        </Card>
      </section>
    </div>
  )
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function CheckRow({ check }: { check: TechnicalRegressionCheck }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
      <div>
        <p className="text-sm font-bold text-[var(--color-text)]">{check.label}</p>
        <p className="text-xs text-[var(--color-text-muted)]">{check.code}</p>
      </div>
      <span className={`rounded-full border px-3 py-1 text-xs font-black ${statusClass(check.status)}`}>{check.status}</span>
    </div>
  )
}

function MetricCard({
  label,
  value,
  helper,
  tone = "neutral",
}: {
  label: string
  value: string
  helper: string
  tone?: "success" | "warning" | "danger" | "neutral"
}) {
  const toneClass =
    tone === "success"
      ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
      : tone === "warning"
        ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
        : tone === "danger"
          ? "border-red-400/40 bg-red-500/10 text-red-100"
          : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"

  return (
    <div className={`rounded-3xl border p-4 ${toneClass}`}>
      <p className="text-xs font-black uppercase tracking-wide opacity-80">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs opacity-80">{helper}</p>
    </div>
  )
}

function StatusCard({ title, status, helper }: { title: string; status?: string; helper: string }) {
  const icon = status === "PASS" ? <CheckCircle2 className="h-4 w-4" /> : status === "FAIL" ? <XCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-black text-[var(--color-text)]">{title}</p>
        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-black ${statusClass(status)}`}>{icon}{status ?? "—"}</span>
      </div>
      <p className="mt-2 text-sm text-[var(--color-text-muted)]">{helper}</p>
    </section>
  )
}

function NoticeBox({ type, message }: { type: "error" | "success"; message: string }) {
  const style = type === "success" ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100" : "border-red-400/30 bg-red-500/10 text-red-100"
  return (
    <section className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${style}`}>
      {message}
    </section>
  )
}

function InfoPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-xs font-black text-[var(--color-primary)]">
      {icon}
      {label}
    </span>
  )
}
