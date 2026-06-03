import { AlertTriangle, Banknote, CheckCircle2, CreditCard, FileText, KeyRound, Link2, RefreshCcw, RotateCcw, ShieldAlert, ShieldCheck, Wallet } from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { getActiveCompanyId } from "../../config/activeCompany"
import {
  getMercadoPagoAccount,
  getMercadoPagoChargebacks,
  getMercadoPagoCheckoutPreferences,
  getMercadoPagoDiagnostics,
  getMercadoPagoPayments,
  getMercadoPagoRefunds,
  getMercadoPagoReleases,
  getMercadoPagoRules,
  getMercadoPagoWebhooks,
  preconfigureMercadoPagoAccount,
} from "./mercadoPagoApi"
import type { MercadoPagoAccount, MercadoPagoDiagnostics, MercadoPagoGenericRow, MercadoPagoRules } from "./types"

const connectionLabels: Record<string, string> = {
  not_connected: "Não conectado",
  configured: "Pré-configurado",
  connected: "Conectado",
  needs_reauth: "Reautenticar",
  error: "Erro",
  disabled: "Desabilitado",
}

const badgeClasses: Record<string, string> = {
  not_connected: "border-slate-300 bg-slate-50 text-slate-700 dark:border-slate-500/40 dark:bg-slate-500/10 dark:text-slate-200",
  configured: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200",
  connected: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200",
  needs_reauth: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/40 dark:bg-orange-500/10 dark:text-orange-200",
  error: "border-red-300 bg-red-50 text-red-800 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200",
  disabled: "border-slate-300 bg-slate-50 text-slate-500 dark:border-slate-500/40 dark:bg-slate-500/10 dark:text-slate-300",
}

function MetricCard({ label, value, tone = "default" }: { label: string; value: string | number; tone?: "default" | "green" | "amber" | "blue" | "red" }) {
  const toneClass =
    tone === "green"
      ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-100"
      : tone === "amber"
        ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100"
        : tone === "blue"
          ? "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-100"
          : tone === "red"
            ? "border-red-300 bg-red-50 text-red-900 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-100"
            : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"

  return (
    <div className={`rounded-3xl border p-5 shadow-lg shadow-[var(--color-card-shadow)] ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">{label}</p>
      <p className="mt-2 text-3xl font-black">{value}</p>
    </div>
  )
}

function EmptyPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5 text-sm text-[var(--color-text-muted)]">
      <p className="font-bold text-[var(--color-text)]">{title}</p>
      <p className="mt-1 leading-6">{description}</p>
    </div>
  )
}

function RowsPreview({ rows, emptyTitle, emptyDescription }: { rows: MercadoPagoGenericRow[]; emptyTitle: string; emptyDescription: string }) {
  if (rows.length === 0) return <EmptyPanel title={emptyTitle} description={emptyDescription} />

  return (
    <div className="space-y-3">
      {rows.slice(0, 5).map((row, index) => (
        <div key={`${String(row.id ?? index)}`} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-xs text-[var(--color-text-muted)]">
          <pre className="overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(row, null, 2)}</pre>
        </div>
      ))}
    </div>
  )
}

export function MercadoPagoPage() {
  const [activeCompanyId] = useState(() => getActiveCompanyId())
  const [account, setAccount] = useState<MercadoPagoAccount | null>(null)
  const [diagnostics, setDiagnostics] = useState<MercadoPagoDiagnostics | null>(null)
  const [rules, setRules] = useState<MercadoPagoRules | null>(null)
  const [payments, setPayments] = useState<MercadoPagoGenericRow[]>([])
  const [releases, setReleases] = useState<MercadoPagoGenericRow[]>([])
  const [webhooks, setWebhooks] = useState<MercadoPagoGenericRow[]>([])
  const [refunds, setRefunds] = useState<MercadoPagoGenericRow[]>([])
  const [chargebacks, setChargebacks] = useState<MercadoPagoGenericRow[]>([])
  const [preferences, setPreferences] = useState<MercadoPagoGenericRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [accountResponse, diagnosticsResponse, rulesResponse, paymentsResponse, releasesResponse, webhooksResponse, refundsResponse, chargebacksResponse, preferencesResponse] = await Promise.all([
        getMercadoPagoAccount({ company_id: activeCompanyId }),
        getMercadoPagoDiagnostics({ company_id: activeCompanyId }),
        getMercadoPagoRules(),
        getMercadoPagoPayments({ company_id: activeCompanyId, limit: 10, offset: 0 }),
        getMercadoPagoReleases({ company_id: activeCompanyId, limit: 10, offset: 0 }),
        getMercadoPagoWebhooks({ company_id: activeCompanyId, limit: 10, offset: 0 }),
        getMercadoPagoRefunds({ company_id: activeCompanyId, limit: 10, offset: 0 }),
        getMercadoPagoChargebacks({ company_id: activeCompanyId, limit: 10, offset: 0 }),
        getMercadoPagoCheckoutPreferences({ company_id: activeCompanyId, limit: 10, offset: 0 }),
      ])
      setAccount(accountResponse.data)
      setDiagnostics(diagnosticsResponse.data)
      setRules(rulesResponse.data)
      setPayments(paymentsResponse.data)
      setReleases(releasesResponse.data)
      setWebhooks(webhooksResponse.data)
      setRefunds(refundsResponse.data)
      setChargebacks(chargebacksResponse.data)
      setPreferences(preferencesResponse.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar Mercado Pago.")
    } finally {
      setLoading(false)
    }
  }, [activeCompanyId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  async function handlePreconfigure() {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const response = await preconfigureMercadoPagoAccount({ company_id: activeCompanyId })
      setAccount(response.data)
      setSuccess("Mercado Pago marcado como pré-configurado. Integração real ainda exigirá OAuth, tokens seguros e webhooks validados.")
      void loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao pré-configurar Mercado Pago.")
    } finally {
      setSaving(false)
    }
  }

  const connectionClass = account ? badgeClasses[account.connection_status] ?? badgeClasses.not_connected : badgeClasses.not_connected

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200">
              <CreditCard className="h-4 w-4" />
              Integração dedicada
            </div>

            <h1 className="text-3xl font-black tracking-tight text-[var(--color-text)] sm:text-4xl">Mercado Pago</h1>

            <p className="mt-3 max-w-4xl text-sm leading-6 text-[var(--color-text-muted)]">
              Fundação técnica para pagamentos, Pix, cartão, boleto, Checkout, webhooks, reembolsos, chargebacks, liberações de dinheiro, taxas e conciliação futura. Esta tela ainda não executa chamada externa; ela prepara o Kovir para integrar com segurança sem confundir pagamento, título, baixa e conciliação.
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
            <p className="font-bold">Erro ao carregar Mercado Pago</p>
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

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Pagamentos" value={diagnostics?.total_payments ?? "-"} tone="blue" />
        <MetricCard label="Liberações" value={diagnostics?.total_releases ?? "-"} tone="green" />
        <MetricCard label="Webhooks" value={diagnostics?.total_webhook_events ?? "-"} tone="amber" />
        <MetricCard label="Reembolsos" value={diagnostics?.total_refunds ?? "-"} />
        <MetricCard label="Chargebacks" value={diagnostics?.total_chargebacks ?? "-"} tone="red" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-black text-[var(--color-text)]">Conta Mercado Pago</h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">Cadastro dedicado da integração. Credenciais sensíveis entram somente em bloco futuro com armazenamento seguro.</p>
            </div>
            <button type="button" onClick={() => void loadData()} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-bold text-[var(--color-primary)] transition hover:-translate-y-0.5 hover:bg-[var(--color-hover)]">
              <RefreshCcw className="h-4 w-4" />
              Atualizar
            </button>
          </div>

          {loading ? (
            <EmptyPanel title="Carregando Mercado Pago" description="Buscando conta, diagnóstico e tabelas preparadas." />
          ) : account ? (
            <div className="space-y-4">
              <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-sky-200">
                      <CreditCard className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="text-lg font-black text-[var(--color-text)]">{account.display_name}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-[var(--color-text-weak)]">{account.environment}</p>
                    </div>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-bold ${connectionClass}`}>{connectionLabels[account.connection_status] ?? account.connection_status}</span>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--color-text-weak)]">Credenciais</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--color-text)]">{account.credentials_status}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--color-text-weak)]">Webhooks</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--color-text)]">{account.webhook_status}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--color-text-weak)]">Collector ID</p>
                    <p className="mt-1 truncate text-sm font-semibold text-[var(--color-text)]">{account.collector_id ?? "Não informado"}</p>
                  </div>
                  <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--color-text-weak)]">Application ID</p>
                    <p className="mt-1 truncate text-sm font-semibold text-[var(--color-text)]">{account.application_id ?? "Não informado"}</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-wrap gap-3">
                  <button type="button" onClick={() => void handlePreconfigure()} disabled={saving} className="inline-flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-black text-emerald-800 shadow-lg shadow-[var(--color-card-shadow)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">
                    <ShieldCheck className="h-4 w-4" />
                    {saving ? "Salvando..." : "Marcar como pré-configurado"}
                  </button>
                </div>
              </div>

              <div className="rounded-3xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
                <div className="flex items-start gap-3">
                  <KeyRound className="mt-0.5 h-5 w-5" />
                  <div>
                    <p className="font-black">Segurança de credenciais</p>
                    <p className="mt-1 leading-6">Este bloco não grava token real. A integração de produção deve usar OAuth, renovação de token, validação de webhook e armazenamento seguro de segredo.</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <EmptyPanel title="Conta Mercado Pago ausente" description="A conta padrão deveria ser criada automaticamente ao carregar esta tela." />
          )}
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Arquitetura preparada</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">O módulo foi separado porque Mercado Pago exige fluxo financeiro próprio: pagamento, taxa, liberação, reembolso, chargeback e conciliação.</p>

          <div className="mt-5 grid gap-3">
            {[
              [Link2, "Checkout / preferência", "Preparado para linkar sale e sale_payment_plan a uma preferência futura."],
              [Wallet, "Pagamentos", "Tabela própria para status, método, bruto, taxa e líquido recebido."],
              [Banknote, "Liberações e repasses", "Estrutura para dinheiro liberado, data prevista e conciliação futura."],
              [FileText, "Webhooks", "Entrada idempotente e auditável antes de mexer em financeiro."],
              [RotateCcw, "Reembolsos", "Separado de pagamento para não distorcer recebível."],
              [ShieldAlert, "Chargebacks", "Separado para disputa, prazo, cobertura e evidência futura."],
            ].map(([Icon, title, description]) => {
              const RenderIcon = Icon as typeof CreditCard
              return (
                <div key={String(title)} className="flex gap-3 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                    <RenderIcon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-black text-[var(--color-text)]">{String(title)}</p>
                    <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{String(description)}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Pagamentos importados</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Futuro espelho dos pagamentos do Mercado Pago, vinculável a venda e plano de pagamento.</p>
          <RowsPreview rows={payments} emptyTitle="Nenhum pagamento importado" emptyDescription="A estrutura está pronta, mas ainda não há chamada real à API de pagamentos." />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Liberações / repasses</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Futuro controle do dinheiro liberado, taxas e valor líquido esperado para conciliação.</p>
          <RowsPreview rows={releases} emptyTitle="Nenhuma liberação importada" emptyDescription="A estrutura está pronta para relatórios de dinheiro liberado e conciliação futura." />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Webhooks recebidos</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Toda notificação futura deve entrar aqui antes de alterar venda, título ou baixa.</p>
          <RowsPreview rows={webhooks} emptyTitle="Nenhum webhook recebido" emptyDescription="Ainda não há endpoint público de produção/homologação configurado." />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Preferências Checkout</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Preparação para Checkout Pro/API com external_reference amarrado à venda.</p>
          <RowsPreview rows={preferences} emptyTitle="Nenhuma preferência criada" emptyDescription="Quando houver integração real, preferências poderão ser vinculadas a sales e sale_payment_plans." />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Reembolsos</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Reembolsos não devem apagar o pagamento original; devem ser evento próprio.</p>
          <RowsPreview rows={refunds} emptyTitle="Nenhum reembolso importado" emptyDescription="Estrutura preparada para reembolso total/parcial futuro." />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Chargebacks</h2>
          <p className="mb-4 mt-1 text-sm text-[var(--color-text-muted)]">Disputa/chargeback deve afetar risco, cobrança, fluxo de caixa e conciliação separadamente.</p>
          <RowsPreview rows={chargebacks} emptyTitle="Nenhum chargeback importado" emptyDescription="Estrutura preparada para disputa, documentação e prazo futuro." />
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Fluxo futuro correto</h2>
          <div className="mt-4 space-y-3">
            {(rules?.prepared_flow ?? []).map((step, index) => (
              <div key={step} className="flex items-center gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 text-sm text-[var(--color-text-muted)]">
                <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-[var(--color-primary-soft)] text-xs font-black text-[var(--color-primary)]">{index + 1}</span>
                {step}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-xl font-black text-[var(--color-text)]">Limites desta fase</h2>
          <div className="mt-4 space-y-3 text-sm leading-6 text-[var(--color-text-muted)]">
            <p>Não há chamada real para a API do Mercado Pago.</p>
            <p>Não há token real salvo.</p>
            <p>Não há webhook público validando assinatura.</p>
            <p>Não há baixa automática, movimento financeiro ou conciliação.</p>
            <p>O objetivo foi preparar a base para integrar sem destruir a modelagem financeira depois.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
