import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  Database,
  Link2,
  PlugZap,
  RefreshCcw,
  ShieldCheck,
  ShoppingBag,
  Store,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { getActiveCompanyId } from "../../config/activeCompany"
import {
  getMarketplaceAccounts,
  getMarketplacesDiagnostics,
  getMarketplaceRules,
  getMarketplaceSyncRuns,
  updateMarketplaceAccount,
} from "./marketplacesApi"
import type { MarketplaceAccount, MarketplacesDiagnostics, MarketplacesRules, MarketplaceSyncRun } from "./types"

const connectionLabels: Record<string, string> = {
  not_connected: "Não conectado",
  configured: "Configurado",
  connected: "Conectado",
  needs_reauth: "Reautenticação necessária",
  error: "Erro",
  disabled: "Desabilitado",
}

const providerDescriptions: Record<string, string> = {
  mercado_pago: "Gateway/intermediador para pagamentos, taxas, repasses e conciliação futura.",
  shopee: "Canal de marketplace para pedidos, catálogo, repasses, devoluções e integração futura com vendas.",
}

function statusClasses(status: string) {
  if (status === "connected") return "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200"
  if (status === "configured") return "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200"
  if (status === "needs_reauth" || status === "error") return "border-red-300 bg-red-50 text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200"
  return "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
}

function providerIcon(providerCode: string) {
  return providerCode === "mercado_pago" ? PlugZap : ShoppingBag
}

function formatDateTime(value: string | null) {
  if (!value) return "Nunca"
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value))
  } catch {
    return value
  }
}

function JsonPreview({ value }: { value: unknown }) {
  const json = useMemo(() => JSON.stringify(value ?? {}, null, 2), [value])
  return (
    <pre className="max-h-56 overflow-auto rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4 text-xs leading-5 text-[var(--color-text-muted)]">
      {json}
    </pre>
  )
}

function MetricCard({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "green" | "blue" | "amber" }) {
  const toneClass =
    tone === "green"
      ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-100"
      : tone === "blue"
        ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-100"
        : tone === "amber"
          ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
          : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"

  return (
    <div className={`rounded-3xl border p-5 shadow-lg shadow-[var(--color-card-shadow)] ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">{label}</p>
      <p className="mt-2 text-3xl font-black">{value}</p>
    </div>
  )
}

export function MarketplacesPage() {
  const [activeCompanyId] = useState(() => getActiveCompanyId())
  const [accounts, setAccounts] = useState<MarketplaceAccount[]>([])
  const [syncRuns, setSyncRuns] = useState<MarketplaceSyncRun[]>([])
  const [diagnostics, setDiagnostics] = useState<MarketplacesDiagnostics | null>(null)
  const [rules, setRules] = useState<MarketplacesRules | null>(null)
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingAccountId, setSavingAccountId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const selectedAccount = accounts.find((account) => account.id === selectedAccountId) ?? accounts[0] ?? null

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accountsResponse, diagnosticsResponse, rulesResponse, syncRunsResponse] = await Promise.all([
        getMarketplaceAccounts({ company_id: activeCompanyId, provider_type: "marketplace", limit: 50, offset: 0 }),
        getMarketplacesDiagnostics({ company_id: activeCompanyId }),
        getMarketplaceRules(),
        getMarketplaceSyncRuns({ company_id: activeCompanyId, limit: 20, offset: 0 }),
      ])
      setAccounts(accountsResponse.data)
      setDiagnostics(diagnosticsResponse.data)
      setRules(rulesResponse.data)
      setSyncRuns(syncRunsResponse.data)
      setSelectedAccountId((current) => current ?? accountsResponse.data[0]?.id ?? null)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao carregar Marketplaces."
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [activeCompanyId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  async function markAsConfigured(account: MarketplaceAccount) {
    setSavingAccountId(account.id)
    setError(null)
    setSuccess(null)
    try {
      const response = await updateMarketplaceAccount(account.id, {
        connection_status: "configured",
        status: "active",
        notes: account.notes ?? "Conta marcada como configurada para preparação de integração futura.",
      })
      setAccounts((current) => current.map((item) => (item.id === account.id ? response.data : item)))
      setSuccess(`${account.provider_name} marcado como configurado.`)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao atualizar marketplace."
      setError(message)
    } finally {
      setSavingAccountId(null)
    }
  }

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200">
              <Store className="h-4 w-4" />
              Aba preparatória
            </div>

            <h1 className="text-3xl font-black tracking-tight text-[var(--color-text)] sm:text-4xl">
              Marketplaces
            </h1>

            <p className="mt-3 max-w-4xl text-sm leading-6 text-[var(--color-text-muted)]">
              Fundação para integrações futuras com Shopee e outros marketplaces. Nesta etapa, o Kovir ainda não chama APIs externas; ele prepara cadastros, tabelas, status, histórico de sincronização, camada de pedidos externos e eventos de pagamento para evitar improviso quando a integração real começar.
            </p>
          </div>

          <div className="rounded-3xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 text-sm text-[var(--color-primary)]">
            <p className="font-bold">Empresa ativa da sessão</p>
            <p className="mt-1 font-mono text-xs">Empresa ativa simulada</p>
            <p className="mt-1 font-mono text-[10px] opacity-80">{activeCompanyId}</p>
          </div>
        </div>
      </header>

      {error ? (
        <div className="flex items-start gap-3 rounded-3xl border border-red-300 bg-red-50 p-5 text-red-800 shadow-lg shadow-[var(--color-card-shadow)] dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div>
            <p className="font-bold">Erro ao carregar Marketplaces</p>
            <p className="mt-1 text-sm">{error}</p>
          </div>
        </div>
      ) : null}

      {success ? (
        <div className="flex items-start gap-3 rounded-3xl border border-emerald-300 bg-emerald-50 p-5 text-emerald-800 shadow-lg shadow-[var(--color-card-shadow)] dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">
          <CheckCircle2 className="mt-0.5 h-5 w-5" />
          <div>
            <p className="font-bold">Atualização registrada</p>
            <p className="mt-1 text-sm">{success}</p>
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Contas preparadas" value={diagnostics?.total_accounts ?? "-"} tone="blue" />
        <MetricCard label="Sincronizações" value={diagnostics?.total_sync_runs ?? "-"} />
        <MetricCard label="Pedidos externos" value={diagnostics?.total_external_orders ?? "-"} tone="amber" />
        <MetricCard label="Eventos de pagamento" value={diagnostics?.total_payment_events ?? "-"} tone="green" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-black text-[var(--color-text)]">Canais preparados</h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">Shopee e outros canais ficam cadastrados por empresa como contas de integração.</p>
            </div>
            <button
              type="button"
              onClick={() => void loadData()}
              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)] transition hover:-translate-y-0.5 hover:bg-[var(--color-hover)]"
            >
              <RefreshCcw className="h-4 w-4" />
              Atualizar
            </button>
          </div>

          {loading ? (
            <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">
              Carregando canais de marketplace...
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {accounts.map((account) => {
                const Icon = providerIcon(account.provider_code)
                const active = selectedAccount?.id === account.id
                return (
                  <button
                    key={account.id}
                    type="button"
                    onClick={() => setSelectedAccountId(account.id)}
                    className={`text-left rounded-3xl border p-5 shadow-lg shadow-[var(--color-card-shadow)] transition hover:-translate-y-0.5 ${
                      active
                        ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)]"
                        : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] hover:bg-[var(--color-hover)]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-surface)] text-[var(--color-primary)]">
                          <Icon className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="font-black text-[var(--color-text)]">{account.provider_name}</p>
                          <p className="text-xs uppercase tracking-[0.18em] text-[var(--color-text-weak)]">{account.provider_type === "payment_gateway" ? "Gateway" : "Marketplace"}</p>
                        </div>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs font-bold ${statusClasses(account.connection_status)}`}>
                        {connectionLabels[account.connection_status] ?? account.connection_status}
                      </span>
                    </div>

                    <p className="mt-4 text-sm leading-6 text-[var(--color-text-muted)]">
                      {providerDescriptions[account.provider_code] ?? account.notes}
                    </p>

                    <div className="mt-4 grid gap-2 text-xs text-[var(--color-text-muted)]">
                      <p><strong>Ambiente:</strong> {account.environment}</p>
                      <p><strong>Última sincronização:</strong> {formatDateTime(account.last_sync_at)}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <div className="mb-5 flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-[var(--color-primary)]" />
            <h2 className="text-xl font-black text-[var(--color-text)]">Detalhe técnico</h2>
          </div>

          {selectedAccount ? (
            <div className="space-y-5">
              <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-weak)]">Conta selecionada</p>
                <p className="mt-2 text-lg font-black text-[var(--color-text)]">{selectedAccount.display_name}</p>
                <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{selectedAccount.id}</p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
                  <p className="text-xs text-[var(--color-text-weak)]">Status interno</p>
                  <p className="mt-1 font-bold text-[var(--color-text)]">{selectedAccount.status}</p>
                </div>
                <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
                  <p className="text-xs text-[var(--color-text-weak)]">Conta externa</p>
                  <p className="mt-1 font-bold text-[var(--color-text)]">{selectedAccount.external_account_id ?? "Pendente"}</p>
                </div>
              </div>

              <button
                type="button"
                disabled={savingAccountId === selectedAccount.id}
                onClick={() => void markAsConfigured(selectedAccount)}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-black text-emerald-800 transition hover:-translate-y-0.5 hover:bg-emerald-100 disabled:cursor-wait disabled:opacity-70 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200"
              >
                <Link2 className="h-4 w-4" />
                {savingAccountId === selectedAccount.id ? "Salvando..." : "Marcar como configurado"}
              </button>

              <div>
                <p className="mb-2 text-sm font-bold text-[var(--color-text)]">Metadados não sensíveis</p>
                <JsonPreview value={selectedAccount.credential_metadata} />
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--color-text-muted)]">Nenhuma conta de marketplace selecionada.</p>
          )}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <div className="mb-5 flex items-center gap-3">
            <ArrowRightLeft className="h-5 w-5 text-[var(--color-primary)]" />
            <h2 className="text-xl font-black text-[var(--color-text)]">Fluxo futuro preparado</h2>
          </div>

          <div className="space-y-3">
            {(rules?.prepared_flow ?? ["marketplace_accounts", "marketplace_sync_runs", "marketplace_external_orders", "sales/sale_items", "sale_payment_plans", "marketplace_payment_events"]).map((step, index) => (
              <div key={step} className="flex items-center gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-xs font-black text-[var(--color-primary)]">{index + 1}</span>
                <p className="font-mono text-xs text-[var(--color-text-muted)]">{step}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <div className="mb-5 flex items-center gap-3">
            <Database className="h-5 w-5 text-[var(--color-primary)]" />
            <h2 className="text-xl font-black text-[var(--color-text)]">Histórico de sincronização</h2>
          </div>

          {syncRuns.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-6 text-sm leading-6 text-[var(--color-text-muted)]">
              Nenhuma sincronização foi executada. Isso está correto nesta fase: a estrutura já existe, mas OAuth, workers, webhooks e chamadas para APIs externas ficam para bloco futuro.
            </div>
          ) : (
            <div className="overflow-hidden rounded-3xl border border-[var(--color-border-soft)]">
              {syncRuns.map((run) => (
                <div key={run.id} className="border-b border-[var(--color-border-soft)] p-4 last:border-b-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold text-[var(--color-text)]">{run.sync_type}</p>
                    <span className="rounded-full border border-[var(--color-border-soft)] px-3 py-1 text-xs text-[var(--color-text-muted)]">{run.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{formatDateTime(run.started_at)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-[2rem] border border-amber-300 bg-amber-50 p-6 text-amber-900 shadow-xl shadow-[var(--color-card-shadow)] dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div>
            <h2 className="font-black">Limite proposital desta fase</h2>
            <p className="mt-2 text-sm leading-6">
              Esta aba ainda não autentica Mercado Pago nem Shopee. O objetivo agora é deixar banco, backend, frontend, rotas, status e conceitos preparados. A integração real precisa de OAuth, armazenamento seguro de credenciais, webhooks, política de retry, logs de erro, mapeamento de pedidos, taxas, chargebacks, repasses e conciliação.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
