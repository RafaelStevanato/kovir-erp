import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ClipboardList,
  History,
  Inbox,
  RefreshCw,
  Save,
  ShieldCheck,
} from "lucide-react"


import {
  getCompany,
  getCompanyAuditEvents,
  getCompanyRules,
  updateCompany,
} from "./companyApi"
import { getAuthSession } from "../../config/authSession"

import type {
  Company,
  CompanyAuditEvent,
  CompanyFiscalSettings,
  CompanyDiagnostics,
  CompanyRules,
  CompanyUpdatePayload,
} from "./types"

type LoadState = "idle" | "loading" | "success" | "error"

type CompanyTab =
  | "general"
  | "address"
  | "financial"
  | "fiscal"
  | "operational"
  | "audit"

type CompanyFormState = {
  legal_name: string
  trade_name: string
  cnpj: string
  email: string
  phone: string
  responsible_name: string
  status: "draft" | "active" | "inactive" | "blocked"

  street: string
  number: string
  complement: string
  district: string
  city: string
  state: string
  zip_code: string
  ibge_municipality_code: string

  tax_regime:
    | "simples_nacional"
    | "lucro_presumido"
    | "lucro_real"
    | "mei"
    | "unknown"
  main_cnae: string
  state_registration: string
  municipal_registration: string
  fiscal_environment: "production" | "homologation" | "none"
  uses_fiscal_control: boolean
  prepared_for_tax_reform: boolean
  crt: "" | "1" | "2" | "3"
  nfe_serie: string
  nfce_serie: string
  focus_nfe_token: string
  focus_nfe_token_configured: boolean

  currency: string
  monthly_closing_day: number
  uses_accounts_receivable: boolean
  uses_accounts_payable: boolean
  uses_cash_control: boolean
  uses_cost_center: boolean
  uses_chart_of_accounts: boolean

  timezone: string
  date_format: string
  money_format: string
  allow_manual_entries: boolean
  allow_imports: boolean
}

const EMPTY_COMPANY_FORM: CompanyFormState = {
  legal_name: "",
  trade_name: "",
  cnpj: "",
  email: "",
  phone: "",
  responsible_name: "",
  status: "active",

  street: "",
  number: "",
  complement: "",
  district: "",
  city: "",
  state: "SP",
  zip_code: "",
  ibge_municipality_code: "",

  tax_regime: "simples_nacional",
  main_cnae: "",
  state_registration: "",
  municipal_registration: "",
  fiscal_environment: "homologation",
  uses_fiscal_control: true,
  prepared_for_tax_reform: true,
  crt: "",
  nfe_serie: "1",
  nfce_serie: "1",
  focus_nfe_token: "",
  focus_nfe_token_configured: false,

  currency: "BRL",
  monthly_closing_day: 31,
  uses_accounts_receivable: true,
  uses_accounts_payable: true,
  uses_cash_control: true,
  uses_cost_center: false,
  uses_chart_of_accounts: false,

  timezone: "America/Sao_Paulo",
  date_format: "YYYY-MM-DD",
  money_format: "BRL",
  allow_manual_entries: true,
  allow_imports: true,
}

const companyTabs: Array<{ id: CompanyTab; label: string }> = [
  { id: "general", label: "Dados gerais" },
  { id: "address", label: "Endereço" },
  { id: "financial", label: "Financeiro" },
  { id: "fiscal", label: "Fiscal" },
  { id: "operational", label: "Operacional" },
  { id: "audit", label: "Auditoria" },
]

const STATUS_LABEL: Record<CompanyFormState["status"], string> = {
  draft: "Rascunho",
  active: "Ativa",
  inactive: "Inativa",
  blocked: "Bloqueada",
}

const EVENT_TYPE_LABEL: Record<string, string> = {
  created: "Criada",
  updated: "Atualizada",
  deleted: "Removida",
}

const fieldInputClass =
  "w-full rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm text-[var(--color-text)] outline-none transition placeholder:text-[var(--color-text-weak)] focus-visible:border-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary-soft)] disabled:cursor-not-allowed disabled:opacity-60"

function companyToForm(company: Company): CompanyFormState {
  return {
    legal_name: company.legal_name ?? "",
    trade_name: company.trade_name ?? "",
    cnpj: company.cnpj ?? "",
    email: company.email ?? "",
    phone: company.phone ?? "",
    responsible_name: company.responsible_name ?? "",
    status: company.status,

    street: company.address.street ?? "",
    number: company.address.number ?? "",
    complement: company.address.complement ?? "",
    district: company.address.district ?? "",
    city: company.address.city ?? "",
    state: company.address.state ?? "SP",
    zip_code: company.address.zip_code ?? "",
    ibge_municipality_code: company.address.ibge_municipality_code ?? "",

    tax_regime: company.fiscal_settings.tax_regime,
    main_cnae: company.fiscal_settings.main_cnae ?? "",
    state_registration: company.fiscal_settings.state_registration ?? "",
    municipal_registration:
      company.fiscal_settings.municipal_registration ?? "",
    fiscal_environment: company.fiscal_settings.fiscal_environment,
    uses_fiscal_control: company.fiscal_settings.uses_fiscal_control,
    prepared_for_tax_reform:
      company.fiscal_settings.prepared_for_tax_reform,
    crt: company.fiscal_settings.crt ?? "",
    nfe_serie: company.fiscal_settings.nfe_serie ?? "1",
    nfce_serie: company.fiscal_settings.nfce_serie ?? "1",
    focus_nfe_token: "",
    focus_nfe_token_configured:
      company.fiscal_settings.focus_nfe_token_configured ?? false,

    currency: company.financial_settings.currency,
    monthly_closing_day: company.financial_settings.monthly_closing_day,
    uses_accounts_receivable:
      company.financial_settings.uses_accounts_receivable,
    uses_accounts_payable: company.financial_settings.uses_accounts_payable,
    uses_cash_control: company.financial_settings.uses_cash_control,
    uses_cost_center: company.financial_settings.uses_cost_center,
    uses_chart_of_accounts:
      company.financial_settings.uses_chart_of_accounts,

    timezone: company.operational_settings.timezone,
    date_format: company.operational_settings.date_format,
    money_format: company.operational_settings.money_format,
    allow_manual_entries: company.operational_settings.allow_manual_entries,
    allow_imports: company.operational_settings.allow_imports,
  }
}

function formatDateTimeBR(value: string | null) {
  if (!value) return "—"

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value))
}


function onlyDigits(value: string) {
  return value.replace(/\D/g, "")
}

function normalizeNullable(value: string) {
  const cleaned = value.trim()
  return cleaned.length > 0 ? cleaned : null
}

function StatusBadge({ children }: { children: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-bold text-[var(--color-primary)]">
      {children}
    </span>
  )
}

function InfoPill({
  icon,
  label,
}: {
  icon: React.ReactNode
  label: string
}) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-muted)]">
      {icon}
      {label}
    </span>
  )
}

function InfoCard({
  title,
  value,
  description,
  icon,
}: {
  title: string
  value: string | number
  description?: string
  icon?: React.ReactNode
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 shadow-lg shadow-[var(--color-card-shadow)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{title}</p>
          <p className="mt-2 truncate text-2xl font-black text-[var(--color-text)]">{value}</p>
          {description ? (
            <p className="mt-1 truncate text-xs text-[var(--color-text-muted)]">{description}</p>
          ) : null}
        </div>
        {icon ? (
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
            {icon}
          </span>
        ) : null}
      </div>
    </div>
  )
}

function Field({
  label,
  required,
  children,
}: {
  label: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-semibold text-[var(--color-text-muted)]">
        {label}
        {required ? (
          <span className="ml-1 text-[var(--color-primary)]" aria-hidden>
            *
          </span>
        ) : null}
      </span>
      {children}
    </label>
  )
}

function NoticeBox({
  type,
  message,
}: {
  type: "success" | "error"
  message: string
}) {
  const isError = type === "error"
  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border p-4 text-sm font-medium ${
        isError
          ? "border-red-500/40 bg-red-500/10 text-red-700"
          : "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
      }`}
    >
      {isError ? (
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
      ) : (
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
      )}
      <span>{message}</span>
    </div>
  )
}

type TextInputProps = {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  inputMode?: "text" | "email" | "numeric" | "tel" | "decimal"
  autoComplete?: string
  type?: "text" | "email"
  maxLength?: number
}

function TextInput({
  value,
  onChange,
  placeholder,
  disabled,
  inputMode,
  autoComplete,
  type = "text",
  maxLength,
}: TextInputProps) {
  return (
    <input
      type={type}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      inputMode={inputMode}
      autoComplete={autoComplete}
      maxLength={maxLength}
      className={fieldInputClass}
    />
  )
}

function SelectInput<TValue extends string>({
  value,
  onChange,
  options,
  disabled,
}: {
  value: TValue
  onChange: (value: TValue) => void
  options: Array<{ value: TValue; label: string }>
  disabled?: boolean
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value as TValue)}
      disabled={disabled}
      className={fieldInputClass}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

function ToggleField({
  label,
  description,
  checked,
  onChange,
  disabled,
}: {
  label: string
  description?: string
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4 transition hover:border-[var(--color-primary-border)] has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60">
      <span>
        <span className="block text-sm font-semibold text-[var(--color-text)]">
          {label}
        </span>
        {description ? (
          <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
            {description}
          </span>
        ) : null}
      </span>

      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
        className="mt-1 h-5 w-5 accent-[var(--color-primary)]"
      />
    </label>
  )
}

function FormSkeleton() {
  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-2" aria-busy>
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex flex-col gap-2">
          <div className="h-3 w-24 animate-pulse rounded bg-[var(--color-bg-soft)]" />
          <div className="h-10 w-full animate-pulse rounded-xl bg-[var(--color-bg-soft)]" />
        </div>
      ))}
    </div>
  )
}

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="mt-6 flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-10 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
        {icon}
      </span>
      <p className="text-base font-semibold text-[var(--color-text)]">{title}</p>
      <p className="max-w-md text-sm text-[var(--color-text-muted)]">{description}</p>
    </div>
  )
}

export function CompanyPage() {
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null)
  const [rules, setRules] = useState<CompanyRules | null>(null)
  const [auditEvents, setAuditEvents] = useState<CompanyAuditEvent[]>([])
  const [state, setState] = useState<LoadState>("idle")
  const [actionState, setActionState] = useState<LoadState>("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<CompanyTab>("general")
  const [form, setForm] = useState<CompanyFormState>(EMPTY_COMPANY_FORM)
  const authSession = getAuthSession()
  const sessionCompanyId = authSession?.companyId ?? ""
  const canWriteCompany = Boolean(
    authSession?.roles.includes("admin") ||
      authSession?.permissions.includes("company.write"),
  )

  const hasCompany = Boolean(selectedCompany)
  const companies = selectedCompany ? [selectedCompany] : []
  const diagnostics = useMemo<CompanyDiagnostics>(
    () => ({
      module: "company",
      status: "active",
      storage: "postgresql",
      persistence: "sqlalchemy_repository",
      id_prefix: "emp",
      audit_enabled: true,
      total_companies: companies.length,
      total_audit_events: auditEvents.length,
      available_operations: ["get_company", "update_company", "get_company_audit_events"],
      technical_notes: [
        "Escopo travado na empresa da sessão autenticada.",
      ],
    }),
    [companies.length, auditEvents.length],
  )

  useEffect(() => {
    if (!selectedCompany) {
      setForm(EMPTY_COMPANY_FORM)
      return
    }

    setForm(companyToForm(selectedCompany))
  }, [selectedCompany])

  const loadCompanyData = useCallback(async () => {
    try {
      setState("loading")
      setErrorMessage(null)

      if (!sessionCompanyId) {
        throw new Error("Sessão inválida. Faça login novamente para carregar a empresa.")
      }

      const [companyResponse, rulesResponse, auditResponse] = await Promise.all([
        getCompany(sessionCompanyId),
        getCompanyRules(),
        getCompanyAuditEvents(sessionCompanyId),
      ])

      setSelectedCompany(companyResponse.data)
      setRules(rulesResponse.data)
      setAuditEvents(auditResponse.data)

      setState("success")
    } catch (error) {
      setState("error")
      setSelectedCompany(null)
      setAuditEvents([])
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao carregar dados da empresa.",
      )
    }
  }, [sessionCompanyId])

  function buildCompanyPayload(): CompanyUpdatePayload {
    const fiscalSettings: Partial<CompanyFiscalSettings> = {
      tax_regime: form.tax_regime,
      main_cnae: normalizeNullable(onlyDigits(form.main_cnae)),
      state_registration: normalizeNullable(form.state_registration),
      municipal_registration: normalizeNullable(form.municipal_registration),
      fiscal_environment: form.fiscal_environment,
      uses_fiscal_control: form.uses_fiscal_control,
      prepared_for_tax_reform: form.prepared_for_tax_reform,
      crt: form.crt === "" ? null : form.crt,
      nfe_serie: onlyDigits(form.nfe_serie) || "1",
      nfce_serie: onlyDigits(form.nfce_serie) || "1",
    }
    const focusToken = normalizeNullable(form.focus_nfe_token)
    if (focusToken) {
      fiscalSettings.focus_nfe_token = focusToken
    }

    return {
      legal_name: form.legal_name,
      trade_name: normalizeNullable(form.trade_name),
      cnpj: onlyDigits(form.cnpj),
      email: normalizeNullable(form.email),
      phone: normalizeNullable(onlyDigits(form.phone)),
      responsible_name: normalizeNullable(form.responsible_name),
      status: form.status,
      address: {
        street: normalizeNullable(form.street),
        number: normalizeNullable(form.number),
        complement: normalizeNullable(form.complement),
        district: normalizeNullable(form.district),
        city: normalizeNullable(form.city),
        state: form.state.trim().toUpperCase(),
        zip_code: normalizeNullable(onlyDigits(form.zip_code)),
        ibge_municipality_code: normalizeNullable(
          form.ibge_municipality_code,
        ),
      },
      fiscal_settings: fiscalSettings,
      financial_settings: {
        currency: form.currency.trim().toUpperCase(),
        monthly_closing_day: form.monthly_closing_day,
        uses_accounts_receivable: form.uses_accounts_receivable,
        uses_accounts_payable: form.uses_accounts_payable,
        uses_cash_control: form.uses_cash_control,
        uses_cost_center: form.uses_cost_center,
        uses_chart_of_accounts: form.uses_chart_of_accounts,
      },
      operational_settings: {
        timezone: form.timezone,
        date_format: form.date_format,
        money_format: form.money_format,
        allow_manual_entries: form.allow_manual_entries,
        allow_imports: form.allow_imports,
      },
    }
  }

  function validateForm() {
    if (form.legal_name.trim().length < 2) {
      return "Informe a razão social com pelo menos 2 caracteres."
    }

    if (onlyDigits(form.cnpj).length !== 14) {
      return "Informe um CNPJ com 14 dígitos."
    }

    if (form.state.trim().length !== 2) {
      return "Informe a UF com 2 letras."
    }

    const ibgeCode = onlyDigits(form.ibge_municipality_code)
    if (ibgeCode && ibgeCode.length !== 7) {
      return "Informe o código IBGE do município com 7 dígitos."
    }

    const mainCnae = onlyDigits(form.main_cnae)
    if (mainCnae && mainCnae.length !== 7) {
      return "Informe o CNAE principal com 7 dígitos."
    }

    const nfeSerie = onlyDigits(form.nfe_serie)
    if (nfeSerie.length < 1 || nfeSerie.length > 3) {
      return "Informe a série NF-e com 1 a 3 dígitos."
    }

    const nfceSerie = onlyDigits(form.nfce_serie)
    if (nfceSerie.length < 1 || nfceSerie.length > 3) {
      return "Informe a série NFC-e com 1 a 3 dígitos."
    }

    if (form.monthly_closing_day < 1 || form.monthly_closing_day > 31) {
      return "O dia de fechamento mensal deve estar entre 1 e 31."
    }

    return null
  }

  async function handleSaveCompany() {
    try {
      setActionState("loading")
      setErrorMessage(null)
      setSuccessMessage(null)

      if (!canWriteCompany) {
        setActionState("error")
        setErrorMessage("Seu usuário não tem permissão para alterar dados da empresa.")
        return
      }

      const validationError = validateForm()

      if (validationError) {
        setActionState("error")
        setErrorMessage(validationError)
        return
      }

      const payload = buildCompanyPayload()

      if (!selectedCompany) {
        throw new Error("Empresa da sessão não encontrada para atualização.")
      }

      await updateCompany(selectedCompany.id, payload)
      setSuccessMessage("Empresa atualizada com sucesso.")

      await loadCompanyData()
      setActionState("success")
    } catch (error) {
      setActionState("error")
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao salvar empresa.",
      )
    }
  }

  useEffect(() => {
    void loadCompanyData()
  }, [loadCompanyData])

  const auditSummary = useMemo(() => {
    const created = auditEvents.some((event) => event.event_type === "created")
    const updated = auditEvents.some((event) => event.event_type === "updated")

    if (created && updated) return "Criada + atualizada"
    if (created) return "Criada"
    if (updated) return "Atualizada"

    return "Sem eventos"
  }, [auditEvents])

  const showSkeleton = state === "loading" && !hasCompany
  const showEmptyState = state !== "loading" && !hasCompany

  return (
    <section className="space-y-6 text-[var(--color-text)]">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] transition-colors sm:p-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <InfoPill icon={<Building2 className="h-4 w-4" />} label="Bloco 1 — Empresa" />
                <InfoPill icon={<ShieldCheck className="h-4 w-4" />} label="Escopo por sessão" />
                <InfoPill icon={<ClipboardList className="h-4 w-4" />} label="Auditoria ativa" />
              </div>

              <h1 className="text-3xl font-black tracking-tight text-[var(--color-text)] sm:text-4xl">
                {selectedCompany?.trade_name || selectedCompany?.legal_name || "Empresa da sessão"}
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--color-text-muted)] sm:text-base">
                Visualize e mantenha somente os dados da empresa logada no Kovir.
                Essas configurações são usadas pelos módulos financeiros, fiscais,
                operacionais e de auditoria.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row xl:flex-col">
              <button
                type="button"
                onClick={() => void loadCompanyData()}
                disabled={state === "loading"}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] transition hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {state === "loading" ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" /> Atualizando...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4" /> Atualizar dados
                  </>
                )}
              </button>
            </div>
          </div>
        </header>

        {errorMessage ? <NoticeBox type="error" message={errorMessage} /> : null}
        {successMessage ? <NoticeBox type="success" message={successMessage} /> : null}
        {!canWriteCompany && hasCompany ? (
          <NoticeBox
            type="error"
            message="Modo leitura: seu usuário não possui permissão company.write para alterar dados da empresa."
          />
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <InfoCard
            title="Status do módulo"
            value={diagnostics?.status ?? "—"}
            description="Diagnóstico técnico do backend"
            icon={<ShieldCheck className="h-5 w-5" />}
          />

          <InfoCard
            title="Empresa em sessão"
            value={diagnostics?.total_companies ?? companies.length}
            description="Escopo restrito à empresa autenticada"
            icon={<Building2 className="h-5 w-5" />}
          />

          <InfoCard
            title="Eventos de auditoria"
            value={diagnostics?.total_audit_events ?? auditEvents.length}
            description={auditSummary}
            icon={<ClipboardList className="h-5 w-5" />}
          />

          <InfoCard
            title="Prefixo oficial"
            value={rules?.id_prefix ?? "emp"}
            description={rules?.id_format ?? "emp_<uuid-v4>"}
            icon={<Building2 className="h-5 w-5" />}
          />
        </div>

        <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-6">
          <div className="flex flex-col gap-4 border-b border-[var(--color-border-soft)] pb-5 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-xl font-bold text-[var(--color-text)]">
                Cadastro da empresa
              </h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                {hasCompany
                  ? `Empresa ativa: ${selectedCompany?.legal_name}`
                  : "Empresa da sessão indisponível. Faça login novamente."}
              </p>
            </div>

            {selectedCompany ? (
              <div className="flex flex-col gap-2 text-sm sm:flex-row sm:items-center">
                <StatusBadge>{STATUS_LABEL[selectedCompany.status] ?? selectedCompany.status}</StatusBadge>
                <span className="break-all font-mono text-xs text-[var(--color-text-muted)]">
                  {selectedCompany.id}
                </span>
              </div>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-2">
            {companyTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={
                  activeTab === tab.id
                    ? "whitespace-nowrap rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2.5 text-sm font-bold text-[var(--color-primary)]"
                    : "whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-semibold text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
                }
              >
                {tab.label}
              </button>
            ))}
          </div>

          {showSkeleton ? <FormSkeleton /> : null}

          {showEmptyState ? (
            <EmptyState
              icon={<Building2 className="h-6 w-6" />}
              title="Empresa indisponível"
              description="Não foi possível carregar a empresa da sessão. Use “Atualizar dados” ou faça login novamente."
            />
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "general" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Field label="Razão social" required>
                <TextInput
                  value={form.legal_name}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      legal_name: value,
                    }))
                  }
                  placeholder="Ex.: STVN Software LTDA"
                  autoComplete="organization"
                />
              </Field>

              <Field label="Nome fantasia">
                <TextInput
                  value={form.trade_name}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      trade_name: value,
                    }))
                  }
                  placeholder="Ex.: STVN Software"
                />
              </Field>

              <Field label="CNPJ" required>
                <TextInput
                  value={form.cnpj}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      cnpj: value,
                    }))
                  }
                  placeholder="00.000.000/0000-00"
                  inputMode="numeric"
                  maxLength={18}
                />
              </Field>

              <Field label="Status">
                <SelectInput
                  value={form.status}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      status: value,
                    }))
                  }
                  options={[
                    { value: "draft", label: "Rascunho" },
                    { value: "active", label: "Ativa" },
                    { value: "inactive", label: "Inativa" },
                    { value: "blocked", label: "Bloqueada" },
                  ]}
                />
              </Field>

              <Field label="E-mail">
                <TextInput
                  type="email"
                  value={form.email}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      email: value,
                    }))
                  }
                  placeholder="contato@empresa.com.br"
                  inputMode="email"
                  autoComplete="email"
                />
              </Field>

              <Field label="Telefone">
                <TextInput
                  value={form.phone}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      phone: value,
                    }))
                  }
                  placeholder="(14) 99999-9999"
                  inputMode="tel"
                  autoComplete="tel"
                />
              </Field>

              <div className="lg:col-span-2">
                <Field label="Responsável">
                  <TextInput
                    value={form.responsible_name}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        responsible_name: value,
                      }))
                    }
                    placeholder="Nome do responsável pela empresa"
                  />
                </Field>
              </div>
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "address" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Field label="Rua / Logradouro">
                <TextInput
                  value={form.street}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      street: value,
                    }))
                  }
                  placeholder="Rua, avenida ou estrada"
                />
              </Field>

              <Field label="Número">
                <TextInput
                  value={form.number}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      number: value,
                    }))
                  }
                  placeholder="Número"
                  inputMode="numeric"
                />
              </Field>

              <Field label="Complemento">
                <TextInput
                  value={form.complement}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      complement: value,
                    }))
                  }
                  placeholder="Sala, bloco, conjunto..."
                />
              </Field>

              <Field label="Bairro">
                <TextInput
                  value={form.district}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      district: value,
                    }))
                  }
                  placeholder="Bairro"
                />
              </Field>

              <Field label="Cidade">
                <TextInput
                  value={form.city}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      city: value,
                    }))
                  }
                  placeholder="Cidade"
                />
              </Field>

              <Field label="UF" required>
                <TextInput
                  value={form.state}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      state: value.toUpperCase().slice(0, 2),
                    }))
                  }
                  placeholder="SP"
                  maxLength={2}
                />
              </Field>

              <Field label="CEP">
                <TextInput
                  value={form.zip_code}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      zip_code: value,
                    }))
                  }
                  placeholder="00000-000"
                  inputMode="numeric"
                  maxLength={9}
                />
              </Field>

              <Field label="Código IBGE do município">
                <TextInput
                  value={form.ibge_municipality_code}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      ibge_municipality_code: value,
                    }))
                  }
                  placeholder="Ex.: 3506003"
                  inputMode="numeric"
                />
              </Field>
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "financial" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Field label="Moeda">
                <TextInput
                  value={form.currency}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      currency: value.toUpperCase().slice(0, 3),
                    }))
                  }
                  placeholder="BRL"
                  maxLength={3}
                />
              </Field>

              <Field label="Dia de fechamento mensal">
                <input
                  type="number"
                  min={1}
                  max={31}
                  value={form.monthly_closing_day}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monthly_closing_day: Number(event.target.value),
                    }))
                  }
                  className={fieldInputClass}
                />
              </Field>

              <ToggleField
                label="Usar contas a receber"
                description="Habilita controle de valores que a empresa tem direito de receber."
                checked={form.uses_accounts_receivable}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    uses_accounts_receivable: value,
                  }))
                }
              />

              <ToggleField
                label="Usar contas a pagar"
                description="Habilita controle de obrigações, despesas e pagamentos."
                checked={form.uses_accounts_payable}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    uses_accounts_payable: value,
                  }))
                }
              />

              <ToggleField
                label="Usar controle de caixa"
                description="Habilita tesouraria, caixa e movimentações financeiras."
                checked={form.uses_cash_control}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    uses_cash_control: value,
                  }))
                }
              />

              <ToggleField
                label="Usar centro de custo"
                description="Permite classificar lançamentos por área, unidade, canal ou projeto."
                checked={form.uses_cost_center}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    uses_cost_center: value,
                  }))
                }
              />

              <ToggleField
                label="Usar plano de contas"
                description="Permite classificar receitas, despesas, ativos e passivos."
                checked={form.uses_chart_of_accounts}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    uses_chart_of_accounts: value,
                  }))
                }
              />
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "fiscal" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Field label="Regime tributário">
                <SelectInput
                  value={form.tax_regime}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      tax_regime: value,
                    }))
                  }
                  options={[
                    {
                      value: "simples_nacional",
                      label: "Simples Nacional",
                    },
                    {
                      value: "lucro_presumido",
                      label: "Lucro Presumido",
                    },
                    { value: "lucro_real", label: "Lucro Real" },
                    { value: "mei", label: "MEI" },
                    { value: "unknown", label: "Não informado" },
                  ]}
                />
              </Field>

              <Field label="CNAE principal">
                <TextInput
                  value={form.main_cnae}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      main_cnae: value,
                    }))
                  }
                  placeholder="Ex.: 6201501"
                  inputMode="numeric"
                />
              </Field>

              <Field label="Inscrição estadual">
                <TextInput
                  value={form.state_registration}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      state_registration: value,
                    }))
                  }
                  placeholder="Inscrição estadual"
                />
              </Field>

              <Field label="Inscrição municipal">
                <TextInput
                  value={form.municipal_registration}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      municipal_registration: value,
                    }))
                  }
                  placeholder="Inscrição municipal"
                />
              </Field>

              <Field label="Ambiente fiscal">
                <SelectInput
                  value={form.fiscal_environment}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      fiscal_environment: value,
                    }))
                  }
                  options={[
                    { value: "homologation", label: "Homologação" },
                    { value: "production", label: "Produção" },
                    { value: "none", label: "Sem ambiente fiscal" },
                  ]}
                />
              </Field>

              <Field label="CRT">
                <SelectInput
                  value={form.crt}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      crt: value,
                    }))
                  }
                  options={[
                    { value: "", label: "Não informado" },
                    { value: "1", label: "1 - Simples Nacional" },
                    {
                      value: "2",
                      label: "2 - Simples Nacional com sublimite excedido",
                    },
                    { value: "3", label: "3 - Regime Normal" },
                  ]}
                />
              </Field>

              <Field label="Série NF-e">
                <TextInput
                  value={form.nfe_serie}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      nfe_serie: onlyDigits(value).slice(0, 3),
                    }))
                  }
                  placeholder="1"
                  inputMode="numeric"
                  maxLength={3}
                />
              </Field>

              <Field label="Série NFC-e">
                <TextInput
                  value={form.nfce_serie}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      nfce_serie: onlyDigits(value).slice(0, 3),
                    }))
                  }
                  placeholder="1"
                  inputMode="numeric"
                  maxLength={3}
                />
              </Field>

              <div className="lg:col-span-2">
                <Field label="Token Focus NFe">
                  <TextInput
                    value={form.focus_nfe_token}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        focus_nfe_token: value,
                      }))
                    }
                    placeholder={
                      form.focus_nfe_token_configured
                        ? "Token já configurado. Preencha somente para substituir."
                        : "Token de homologação/produção da Focus NFe"
                    }
                    maxLength={255}
                  />
                </Field>
                <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">
                  O token nunca é exibido pela API. Campo vazio mantém a credencial atual.
                </p>
              </div>

              <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
                <ToggleField
                  label="Usar controle fiscal"
                  description="Habilita campos e vínculos fiscais nos módulos futuros."
                  checked={form.uses_fiscal_control}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      uses_fiscal_control: value,
                    }))
                  }
                />

                <ToggleField
                  label="Preparado para Reforma Tributária"
                  description="Mantém a empresa preparada para campos e regras de IBS, CBS e IS."
                  checked={form.prepared_for_tax_reform}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      prepared_for_tax_reform: value,
                    }))
                  }
                />
              </div>
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "operational" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Field label="Timezone">
                <TextInput
                  value={form.timezone}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      timezone: value,
                    }))
                  }
                  placeholder="America/Sao_Paulo"
                />
              </Field>

              <Field label="Formato de data">
                <TextInput
                  value={form.date_format}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      date_format: value,
                    }))
                  }
                  placeholder="YYYY-MM-DD"
                />
              </Field>

              <Field label="Formato monetário">
                <TextInput
                  value={form.money_format}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      money_format: value,
                    }))
                  }
                  placeholder="BRL"
                />
              </Field>

              <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
                <ToggleField
                  label="Permitir lançamentos manuais"
                  description="Permite criar registros manualmente quando não houver importação ou integração."
                  checked={form.allow_manual_entries}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      allow_manual_entries: value,
                    }))
                  }
                />

                <ToggleField
                  label="Permitir importações"
                  description="Permite uso futuro de importação de CSV, XLSX, XML e outros arquivos."
                  checked={form.allow_imports}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      allow_imports: value,
                    }))
                  }
                />
              </div>
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab === "audit" ? (
            <div className="mt-6">
              <div className="mb-5 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
                <p className="text-sm font-semibold text-[var(--color-text)]">
                  Histórico técnico da empresa
                </p>
                <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                  A auditoria registra eventos críticos como criação e alteração
                  da empresa. Em versões futuras, esta área poderá mostrar
                  diferenças detalhadas de before/after.
                </p>
              </div>

              <div className="space-y-3">
                {auditEvents.length === 0 ? (
                  <EmptyState
                    icon={<Inbox className="h-6 w-6" />}
                    title="Nenhum evento registrado"
                    description="Eventos aparecem aqui após criação ou atualização da empresa."
                  />
                ) : (
                  auditEvents.map((event) => (
                    <div
                      key={event.id}
                      className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="flex items-start gap-3">
                          <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                            <History className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="font-semibold text-[var(--color-text)]">
                              {EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}
                            </p>
                            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                              {formatDateTimeBR(event.occurred_at)}
                            </p>
                          </div>
                        </div>

                        <span className="w-fit rounded-full bg-[var(--color-primary-soft)] px-2 py-1 text-xs font-semibold text-[var(--color-primary)]">
                          {event.source}
                        </span>
                      </div>

                      <p className="mt-3 break-all font-mono text-xs text-[var(--color-text-muted)]">
                        {event.id}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}

          {!showSkeleton && !showEmptyState && activeTab !== "audit" ? (
            <div className="mt-8 flex flex-col gap-3 border-t border-[var(--color-border-soft)] pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-[var(--color-text-muted)]">
                {hasCompany
                  ? "As alterações serão registradas na auditoria da empresa."
                  : "Apenas a empresa da sessão pode ser alterada."}
              </p>

              <button
                type="button"
                onClick={() => void handleSaveCompany()}
                disabled={actionState === "loading" || !hasCompany || !canWriteCompany}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-[var(--color-card-shadow)] transition hover:bg-[var(--color-primary-hover)] hover:border-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {!canWriteCompany ? (
                  <><Save className="h-4 w-4" /> Sem permissão</>
                ) : actionState === "loading" ? (
                  <><Save className="h-4 w-4" /> Salvando...</>
                ) : (
                  <><Save className="h-4 w-4" /> Salvar alterações</>
                )}
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
