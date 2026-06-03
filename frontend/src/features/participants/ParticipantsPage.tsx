import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import {
  dateCell,
  exportCsv as exportCsvFile,
  exportXlsx as exportXlsxFile,
  moneyCell,
  type ExportTable,
} from "../../lib/exportTable"

import {
  getActiveCompanyId,
  getCompanyDisplayName,
  pickActiveCompanyId,
} from "../../config/activeCompany"
import { getAuthSession } from "../../config/authSession"
import { getCompanies } from "../company/companyApi"
import type { Company } from "../company/types"

import {
  createParticipant,
  getParticipantAuditEvents,
  getParticipantDiagnostics,
  getParticipantRules,
  getParticipantSummary,
  getParticipantsPage,
  updateParticipant,
  type ListParticipantsParams,
} from "./participantsApi"

import type {
  Participant,
  ParticipantAuditEvent,
  ParticipantCreatePayload,
  ParticipantDiagnostics,
  ParticipantOrigin,
  ParticipantRules,
  ParticipantStatus,
  ParticipantSummary,
  ParticipantType,
  PersonType,
  TaxpayerType,
} from "./types"

type LoadState = "idle" | "loading" | "success" | "error"
type ParticipantsView = "overview" | "form" | "list"
type DocumentType = "cpf" | "cnpj"
type ExportFormat = "xlsx" | "csv"

type ViaCepResponse = {
  cep: string
  logradouro: string
  complemento: string
  bairro: string
  localidade: string
  uf: string
  ibge: string
  erro?: boolean
}

type OptionalFieldKey =
  | "trade_name"
  | "secondary_phone"
  | "website"
  | "contact_name"
  | "contact_phone"
  | "contact_email"
  | "origin"
  | "complement"
  | "ibge_municipality_code"
  | "taxpayer_type"
  | "tax_regime"
  | "main_cnae"
  | "state_registration"
  | "municipal_registration"
  | "fiscal_notes"
  | "bank_name"
  | "bank_branch"
  | "bank_account"
  | "pix_key"
  | "credit_limit"
  | "payment_priority"
  | "notes"

type ParticipantFormState = {
  company_id: string
  participant_type: ParticipantType
  person_type: PersonType
  document_type: DocumentType
  name: string
  trade_name: string
  document: string
  email: string
  phone: string
  secondary_phone: string
  website: string
  contact_name: string
  contact_phone: string
  contact_email: string
  origin: ParticipantOrigin | ""
  status: ParticipantStatus

  street: string
  number: string
  complement: string
  district: string
  city: string
  state: string
  zip_code: string
  ibge_municipality_code: string

  taxpayer_type: TaxpayerType
  tax_regime: string
  main_cnae: string
  state_registration: string
  municipal_registration: string
  is_foreign: boolean
  fiscal_notes: string

  bank_name: string
  bank_branch: string
  bank_account: string
  pix_key: string
  credit_limit: string
  payment_priority: string

  notes: string
}

function getSessionCompanyId() {
  return getAuthSession()?.companyId ?? ""
}

const PARTICIPANT_TYPES: ParticipantType[] = [
  "customer",
  "supplier",
  "carrier",
  "service_provider",
  "marketplace",
  "gateway",
  "bank",
  "other",
]

const INITIAL_FORM: ParticipantFormState = {
  company_id: getSessionCompanyId() || getActiveCompanyId(),
  participant_type: "customer",
  person_type: "company",
  document_type: "cnpj",
  name: "",
  trade_name: "",
  document: "",
  email: "",
  phone: "",
  secondary_phone: "",
  website: "",
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  origin: "",
  status: "active",

  street: "",
  number: "",
  complement: "",
  district: "",
  city: "",
  state: "SP",
  zip_code: "",
  ibge_municipality_code: "",

  taxpayer_type: "unknown",
  tax_regime: "",
  main_cnae: "",
  state_registration: "",
  municipal_registration: "",
  is_foreign: false,
  fiscal_notes: "",

  bank_name: "",
  bank_branch: "",
  bank_account: "",
  pix_key: "",
  credit_limit: "",
  payment_priority: "",

  notes: "",
}

const TAX_REGIME_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "simples_nacional",  label: "Simples Nacional" },
  { value: "mei",               label: "MEI" },
  { value: "lucro_presumido",   label: "Lucro Presumido" },
  { value: "lucro_real",        label: "Lucro Real" },
  { value: "lucro_arbitrado",   label: "Lucro Arbitrado" },
  { value: "imune",             label: "Imune" },
  { value: "isento",            label: "Isento" },
  { value: "nao_contribuinte",  label: "Não contribuinte" },
  { value: "nao_se_aplica",     label: "Não se aplica" },
]

const ORIGIN_OPTIONS: Array<{ value: ParticipantOrigin; label: string }> = [
  { value: "direct",      label: "Venda direta" },
  { value: "marketplace", label: "Marketplace" },
  { value: "referral",    label: "Indicação" },
  { value: "import",      label: "Importação de dados" },
  { value: "organic",     label: "Orgânico / inbound" },
  { value: "manual",      label: "Cadastro manual" },
  { value: "other",       label: "Outro" },
]

const PAGE_SIZE = 20
const EXPORT_LIMIT = 5000

const INITIAL_OPTIONAL_FIELDS: Record<OptionalFieldKey, boolean> = {
  trade_name: false,
  secondary_phone: false,
  website: false,
  contact_name: false,
  contact_phone: false,
  contact_email: false,
  origin: false,
  complement: false,
  ibge_municipality_code: false,
  taxpayer_type: false,
  tax_regime: false,
  main_cnae: false,
  state_registration: false,
  municipal_registration: false,
  fiscal_notes: false,
  bank_name: false,
  bank_branch: false,
  bank_account: false,
  pix_key: false,
  credit_limit: false,
  payment_priority: false,
  notes: false,
}

function onlyDigits(value: string) {
  return value.replace(/\D/g, "")
}

function normalizeDocument(value: string) {
  return value.replace(/[.\-/\s]/g, "").toUpperCase()
}


function normalizeNullable(value: string) {
  const cleaned = value.trim()
  return cleaned.length > 0 ? cleaned : null
}

function normalizeOptionalText(
  enabled: boolean,
  value: string,
  defaultValue = "NI",
) {
  if (!enabled) return defaultValue

  return normalizeNullable(value) ?? defaultValue
}

function normalizeOptionalNumericCode(enabled: boolean, value: string) {
  if (!enabled) return null

  return normalizeNullable(onlyDigits(value))
}

function isFilledOptional(value: string | null | undefined) {
  return Boolean(value && value !== "NI")
}

function formatDateTimeBR(value: string | null) {
  if (!value) return "—"

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value))
}

function formatDocument(value: string | null) {
  if (!value) return "—"

  const cleaned = onlyDigits(value)

  if (cleaned.length === 11) {
    return cleaned.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4")
  }

  if (cleaned.length === 14) {
    return cleaned.replace(
      /^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,
      "$1.$2.$3/$4-$5",
    )
  }

  return value
}

function getParticipantTypeLabel(value: ParticipantType) {
  const labels: Record<ParticipantType, string> = {
    customer: "Cliente",
    supplier: "Fornecedor",
    carrier: "Transportadora",
    service_provider: "Prestador de serviço",
    marketplace: "Marketplace",
    gateway: "Gateway",
    bank: "Banco",
    other: "Outro",
  }

  return labels[value]
}

function getParticipantTypeDescription(value: ParticipantType) {
  const descriptions: Record<ParticipantType, string> = {
    customer: "Quem compra da empresa. Será usado em vendas, contas a receber, cobrança e documentos fiscais de saída.",
    supplier: "Quem vende para a empresa. Será usado em compras, despesas, contas a pagar e documentos fiscais de entrada.",
    carrier: "Quem transporta mercadorias. Será útil para frete, CT-e, entregas e vínculo fiscal/logístico.",
    service_provider: "Quem presta serviço para a empresa. Será usado em despesas, contratos, NFS-e e contas a pagar.",
    marketplace: "Canal externo de venda, como Mercado Livre, Amazon, Magalu ou Shopee.",
    gateway: "Intermediador de pagamento, como Mercado Pago, Vindi, Pagar.me ou adquirentes.",
    bank: "Banco ou instituição financeira usado para recebimentos, pagamentos e conciliação.",
    other: "Terceiro que participa da operação, mas não se encaixa nos tipos principais.",
  }

  return descriptions[value]
}

function getParticipantTypeExample(value: ParticipantType) {
  const examples: Record<ParticipantType, string> = {
    customer: "Ex.: cliente PJ, consumidor, comprador recorrente",
    supplier: "Ex.: fornecedor de mercadoria, distribuidor",
    carrier: "Ex.: transportadora, correios, operador logístico",
    service_provider: "Ex.: contador, agência, consultor, manutenção",
    marketplace: "Ex.: Mercado Livre, Amazon, Magalu",
    gateway: "Ex.: Mercado Pago, Vindi, Yapay, Stone",
    bank: "Ex.: Banco do Brasil, Itaú, Sicoob, Nubank PJ",
    other: "Ex.: parceiro, sócio, terceiro operacional",
  }

  return examples[value]
}

function getPersonTypeLabel(value: PersonType) {
  const labels: Record<PersonType, string> = {
    individual: "Pessoa física",
    company: "Pessoa jurídica",
    foreign: "Estrangeiro",
    unknown: "Não informado",
  }

  return labels[value]
}

function getStatusLabel(value: ParticipantStatus) {
  const labels: Record<ParticipantStatus, string> = {
    draft: "Rascunho",
    active: "Ativo",
    inactive: "Inativo",
    blocked: "Bloqueado",
  }

  return labels[value]
}

function getTaxpayerTypeLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    taxpayer: "Contribuinte",
    non_taxpayer: "Não contribuinte",
    exempt: "Isento",
    unknown: "NI — Não informado",
  }

  return labels[value ?? "unknown"] ?? "NI — Não informado"
}

function getTaxRegimeLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    simples_nacional: "Simples Nacional",
    lucro_presumido: "Lucro Presumido",
    lucro_real: "Lucro Real",
    mei: "MEI",
    isento: "Isento",
    imune: "Imune",
    produtor_rural: "Produtor Rural",
    pessoa_fisica: "Pessoa Física",
    estrangeiro: "Estrangeiro",
    NI: "NI — Não informado",
  }

  return labels[value ?? "NI"] ?? value ?? "NI"
}

function StatusBadge({ children }: { children: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-medium text-[var(--color-primary)]">
      {children}
    </span>
  )
}

function InfoCard({
  title,
  value,
  description,
}: {
  title: string
  value: string | number
  description?: string
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-lg shadow-[var(--color-card-shadow)]">
      <p className="text-sm text-[var(--color-text-muted)]">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-[var(--color-text)]">
        {value}
      </p>

      {description ? (
        <p className="mt-2 text-sm text-[var(--color-text-muted)]">
          {description}
        </p>
      ) : null}
    </div>
  )
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-6">
      <div className="mb-5">
        <h2 className="text-xl font-semibold text-[var(--color-text)]">
          {title}
        </h2>

        {description ? (
          <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
            {description}
          </p>
        ) : null}
      </div>

      {children}
    </section>
  )
}


function GuidedActionCard({
  step,
  title,
  description,
  actionLabel,
  onClick,
}: {
  step: string
  title: string
  description: string
  actionLabel: string
  onClick: () => void
}) {
  return (
    <div className="flex h-full flex-col rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5 shadow-lg shadow-[var(--color-card-shadow)]">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-sm font-black text-[var(--color-primary)]">
          {step}
        </span>
        <h3 className="text-base font-semibold text-[var(--color-text)]">
          {title}
        </h3>
      </div>

      <p className="mt-4 flex-1 text-sm leading-6 text-[var(--color-text-muted)]">
        {description}
      </p>

      <button
        type="button"
        onClick={onClick}
        className="mt-5 rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-primary)] transition hover:opacity-90"
      >
        {actionLabel}
      </button>
    </div>
  )
}

function GuideNote({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="mt-5 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 text-sm leading-6 text-[var(--color-primary)]">
      <p className="font-semibold">{title}</p>
      <div className="mt-1 text-[var(--color-text)]">{children}</div>
    </div>
  )
}

function ChecklistChip({
  label,
  done,
}: {
  label: string
  done: boolean
}) {
  return (
    <div
      className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${
        done
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600"
          : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)]"
      }`}
    >
      <span className="mr-2">{done ? "✓" : "○"}</span>
      {label}
    </div>
  )
}



function participantsTabClass(active: boolean) {
  return `kovir-module-tab rounded-2xl border ${
    active ? "kovir-module-tab-active" : "kovir-module-tab-inactive"
  }`
}



function ParticipantsModuleTabs({
  view,
  onSelect,
}: {
  view: ParticipantsView
  onSelect: (view: ParticipantsView) => void
}) {
  const tabs: Array<{
    view: ParticipantsView
    label: string
  }> = [
    {
      view: "overview",
      label: "Visão guiada",
    },
    {
      view: "list",
      label: "Buscar / editar",
    },
    {
      view: "form",
      label: "Cadastrar",
    },
  ]

  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.view}
          type="button"
          onClick={() => onSelect(tab.view)}
          className={participantsTabClass(view === tab.view)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}


function ParticipantFormSectionNav() {
  const sections = [
    {
      id: "participant-section-general",
      title: "1. Dados gerais",
    },
    {
      id: "participant-section-address",
      title: "2. Contato + Endereço",
    },
    {
      id: "participant-section-fiscal",
      title: "3. Fiscal",
    },
    {
      id: "participant-section-financial",
      title: "4. Financeiro",
    },
    {
      id: "participant-section-audit",
      title: "5. Auditoria",
    },
  ]

  function scrollToSection(sectionId: string) {
    document.getElementById(sectionId)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    })
  }

  return (
    <aside className="kovir-compact-section-nav xl:self-start">
      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 shadow-xl shadow-[var(--color-card-shadow)]">
        <p className="px-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-weak)]">
          Preencha em ordem
        </p>

        <div className="mt-3 grid gap-2">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => scrollToSection(section.id)}
              className="kovir-section-nav-button kovir-compact-section-nav-button rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-left text-sm font-semibold text-[var(--color-text)]"
            >
              {section.title}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}




function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium text-[var(--color-text-muted)]">
        {label}
      </span>
      {children}
    </label>
  )
}

const participantFieldClass =
  "w-full rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm text-[var(--color-text)] outline-none transition placeholder:text-[var(--color-text-weak)] focus-visible:border-[var(--color-primary)] focus-visible:ring-2 focus-visible:ring-[var(--color-primary-soft)] disabled:cursor-not-allowed disabled:opacity-60"

function TextInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className={participantFieldClass}
    />
  )
}

function SelectInput<TValue extends string>({
  value,
  onChange,
  options,
}: {
  value: TValue
  onChange: (value: TValue) => void
  options: Array<{ value: TValue; label: string }>
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value as TValue)}
      className={participantFieldClass}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

async function fetchAddressByCep(cep: string) {
  const cleanedCep = onlyDigits(cep)

  if (cleanedCep.length !== 8) {
    throw new Error("CEP deve conter exatamente 8 números.")
  }

  const response = await fetch(`https://viacep.com.br/ws/${cleanedCep}/json/`)

  if (!response.ok) {
    throw new Error("Não foi possível consultar o CEP informado.")
  }

  const data = (await response.json()) as ViaCepResponse

  if (data.erro) {
    throw new Error("CEP não encontrado.")
  }

  return data
}

function MoneyOptionalTextField({
  label,
  enabled,
  value,
  onToggle,
  onChange,
  placeholder = "0.00",
  helperText,
}: {
  label: string
  enabled: boolean
  value: string
  onToggle: (enabled: boolean) => void
  onChange: (value: string) => void
  placeholder?: string
  helperText?: string
}) {
  const [invalidMessage, setInvalidMessage] = useState<string | null>(null)

  function isValidMoneyInput(nextValue: string) {
    return /^\d*([,.]\d{0,2})?$/.test(nextValue)
  }

  function handleChange(nextValue: string) {
    if (!isValidMoneyInput(nextValue)) {
      setInvalidMessage(`${label} aceita apenas números, vírgula ou ponto.`)
      return
    }

    onChange(nextValue)
  }

  return (
    <>
      <ValidationModal
        message={invalidMessage}
        onClose={() => setInvalidMessage(null)}
      />

      <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
        <label className="flex items-start justify-between gap-4">
          <span>
            <span className="block text-sm font-medium text-[var(--color-text)]">
              {label}
            </span>
            <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
              {enabled
                ? helperText ?? "Campo monetário habilitado."
                : "NI — Não informado"}
            </span>
          </span>

          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => onToggle(event.target.checked)}
            className="mt-1 h-5 w-5 accent-[var(--color-primary)]"
          />
        </label>

        {enabled ? (
          <div className="mt-4 currency-input-shell">
            <span className="currency-input-prefix">R$</span>
            <input
              value={value}
              onChange={(event) => handleChange(event.target.value)}
              inputMode="decimal"
              placeholder={placeholder}
              className="input-like currency-input"
              aria-label={label}
            />
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-muted)]">
            NI — Não informado
          </div>
        )}
      </div>
    </>
  )
}

function OptionalTextField({
  label,
  enabled,
  value,
  onToggle,
  onChange,
  placeholder,
  helperText,
}: {
  label: string
  enabled: boolean
  value: string
  onToggle: (enabled: boolean) => void
  onChange: (value: string) => void
  placeholder?: string
  helperText?: string
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <label className="flex items-start justify-between gap-4">
        <span>
          <span className="block text-sm font-medium text-[var(--color-text)]">
            {label}
          </span>
          <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
            {enabled
              ? helperText ?? "Campo habilitado para preenchimento."
              : "NI — Não informado"}
          </span>
        </span>

        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          className="mt-1 h-5 w-5 accent-[var(--color-primary)]"
        />
      </label>

      {enabled ? (
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className={`mt-3 ${participantFieldClass}`}
        />
      ) : (
        <div className="mt-3 rounded-xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-2.5 text-sm text-[var(--color-text-muted)]">
          NI — Não informado
        </div>
      )}
    </div>
  )
}

function OptionalSelectField<TValue extends string>({
  label,
  enabled,
  value,
  onToggle,
  onChange,
  options,
  helperText,
}: {
  label: string
  enabled: boolean
  value: TValue
  onToggle: (enabled: boolean) => void
  onChange: (value: TValue) => void
  options: Array<{ value: TValue; label: string }>
  helperText?: string
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <label className="flex items-start justify-between gap-4">
        <span>
          <span className="block text-sm font-medium text-[var(--color-text)]">
            {label}
          </span>
          <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
            {enabled
              ? helperText ?? "Campo habilitado para seleção."
              : "NI — Não informado"}
          </span>
        </span>

        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          className="mt-1 h-5 w-5 accent-[var(--color-primary)]"
        />
      </label>

      {enabled ? (
        <select
          value={value}
          onChange={(event) => onChange(event.target.value as TValue)}
          className={`mt-3 ${participantFieldClass}`}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <div className="mt-3 rounded-xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-2.5 text-sm text-[var(--color-text-muted)]">
          NI — Não informado
        </div>
      )}
    </div>
  )
}

function ValidationModal({
  message,
  onClose,
}: {
  message: string | null
  onClose: () => void
}) {
  if (!message) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4">
      <style>
        {`
          @keyframes kovirModalIn {
            from {
              opacity: 0;
              transform: translateY(12px) scale(0.96);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }
        `}
      </style>

      <div
        className="w-full max-w-md rounded-[2rem] border border-red-500/40 bg-[var(--color-surface)] p-6 shadow-2xl shadow-black/40"
        style={{ animation: "kovirModalIn 180ms ease-out" }}
      >
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-red-500/40 bg-red-500/10 text-3xl font-bold text-red-400">
          ×
        </div>

        <h2 className="mt-5 text-center text-xl font-semibold text-[var(--color-text)]">
          Verifique o cadastro
        </h2>

        <p className="mt-3 text-center text-sm leading-6 text-[var(--color-text-muted)]">
          {message}
        </p>

        <button
          type="button"
          onClick={onClose}
          className="mt-6 w-full rounded-xl bg-red-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-red-400"
        >
          Entendi
        </button>
      </div>
    </div>
  )
}

export function ParticipantsPage() {
  const [view, setView] = useState<ParticipantsView>("overview")
  const [cepLookupState, setCepLookupState] = useState<LoadState>("idle")
  const [participants, setParticipants] = useState<Participant[]>([])
  const [companies, setCompanies] = useState<Company[]>([])
  const [rules, setRules] = useState<ParticipantRules | null>(null)
  const [summary, setSummary] = useState<ParticipantSummary | null>(null)
  const [diagnostics, setDiagnostics] =
    useState<ParticipantDiagnostics | null>(null)
  const [auditEvents, setAuditEvents] = useState<ParticipantAuditEvent[]>([])
  const [selectedParticipantId, setSelectedParticipantId] = useState<
    string | null
  >(null)
  const sessionCompanyId = getSessionCompanyId()
  const [activeCompanyId, setActiveCompanyIdState] = useState(() => sessionCompanyId || getActiveCompanyId())
  const [form, setForm] = useState<ParticipantFormState>(() => ({
    ...INITIAL_FORM,
    company_id: sessionCompanyId || getActiveCompanyId(),
  }))
  const [optionalFields, setOptionalFields] = useState<
    Record<OptionalFieldKey, boolean>
  >({ ...INITIAL_OPTIONAL_FIELDS })
  const [state, setState] = useState<LoadState>("idle")
  const [actionState, setActionState] = useState<LoadState>("idle")
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [modalMessage, setModalMessage] = useState<string | null>(null)

  const [listSearch, setListSearch] = useState("")
  const [listTypeFilter, setListTypeFilter] = useState<ParticipantType | "all">("all")
  const [listPersonTypeFilter, setListPersonTypeFilter] = useState<PersonType | "all">("all")
  const [listStatusFilter, setListStatusFilter] = useState<ParticipantStatus | "all">("all")
  const [hasListSearchStarted, setHasListSearchStarted] = useState(false)
  const [listPage, setListPage] = useState(1)
  const [listTotal, setListTotal] = useState(0)
  const [listState, setListState] = useState<LoadState>("idle")
  const authSession = getAuthSession()
  const canWriteParticipants = Boolean(
    authSession?.roles.includes("admin") ||
      authSession?.permissions.includes("participants.write"),
  )

  const activeCompany = useMemo(
    () => companies.find((company) => company.id === activeCompanyId) ?? null,
    [activeCompanyId, companies],
  )

  const activeCompanyName = getCompanyDisplayName(activeCompany)

  const typeCounts = useMemo(() => {
    if (summary) return summary.type_counts

    return participants.reduce<Record<ParticipantType, number>>(
      (accumulator, participant) => {
        accumulator[participant.participant_type] =
          (accumulator[participant.participant_type] ?? 0) + 1

        return accumulator
      },
      {
        customer: 0,
        supplier: 0,
        carrier: 0,
        service_provider: 0,
        marketplace: 0,
        gateway: 0,
        bank: 0,
        other: 0,
      },
    )
  }, [participants, summary])

  const statusCounts = useMemo(() => {
    if (summary) return summary.status_counts

    return participants.reduce<Record<ParticipantStatus, number>>(
      (accumulator, participant) => {
        accumulator[participant.status] =
          (accumulator[participant.status] ?? 0) + 1

        return accumulator
      },
      {
        draft: 0,
        active: 0,
        inactive: 0,
        blocked: 0,
      },
    )
  }, [participants, summary])

  const visibleParticipants = hasListSearchStarted ? participants : []
  const totalPages = Math.max(1, Math.ceil(listTotal / PAGE_SIZE))
  const safeListPage = Math.min(listPage, totalPages)
  const pagedParticipants = visibleParticipants

  const auditSummary = useMemo(() => {
    const created = auditEvents.some((event) => event.event_type === "created")
    const updated = auditEvents.some((event) => event.event_type === "updated")

    if (created && updated) return "Criado + atualizado"
    if (created) return "Criado"
    if (updated) return "Atualizado"

    return "Sem eventos"
  }, [auditEvents])

  const insights = useMemo(() => {
    const total = summary?.total_participants ?? participants.length
    const active = statusCounts.active
    const blocked = statusCounts.blocked
    const withoutEmail = participants.filter(
      (participant) => !participant.email,
    ).length
    const withoutPix = participants.filter(
      (participant) =>
        !participant.financial_settings?.pix_key ||
        participant.financial_settings.pix_key === "NI",
    ).length
    const customers = typeCounts.customer
    const suppliers = typeCounts.supplier

    return [
      {
        title: "Base operacional",
        text:
          total === 0
            ? "Nenhum participante cadastrado. O próximo passo é criar clientes e fornecedores de teste."
            : `${active} de ${total} participantes estão ativos para uso nos próximos módulos.`,
      },
      {
        title: "Composição da base",
        text:
          total === 0
            ? "Ainda não há distribuição por categorias."
            : `A base possui ${customers} cliente(s) e ${suppliers} fornecedor(es), que serão essenciais para vendas, compras, contas a receber e contas a pagar.`,
      },
      {
        title: "Risco cadastral",
        text:
          blocked > 0
            ? `${blocked} participante(s) estão bloqueados. Eles devem exigir atenção antes de uso operacional.`
            : "Nenhum participante bloqueado no momento.",
      },
      {
        title: "Qualidade dos dados",
        text:
          withoutEmail > 0 || withoutPix > 0
            ? `${withoutEmail} participante(s) sem e-mail e ${withoutPix} sem chave Pix cadastrada.`
            : "Os participantes possuem e-mail e chave Pix preenchidos.",
      },
    ]
  }, [participants, statusCounts, summary, typeCounts])

  const dataQualityCards = useMemo(() => {
    if (summary) {
      const quality = summary.quality_counts

      return [
        {
          label: "Documento",
          value: quality.with_document,
          total: quality.total,
          description:
            quality.with_document === quality.total
              ? "Todos possuem CPF/CNPJ informado."
              : `${quality.total - quality.with_document} cadastro(s) sem documento válido para operação.`,
        },
        {
          label: "Endereço",
          value: quality.with_address,
          total: quality.total,
          description:
            quality.with_address === quality.total
              ? "Todos possuem endereço base."
              : `${quality.total - quality.with_address} cadastro(s) sem endereço informado.`,
        },
        {
          label: "Contato",
          value: quality.with_contact,
          total: quality.total,
          description:
            quality.with_contact === quality.total
              ? "Todos possuem e-mail e telefone."
              : `${quality.total - quality.with_contact} cadastro(s) com contato incompleto.`,
        },
        {
          label: "Uso operacional",
          value: quality.operational,
          total: quality.total,
          description:
            quality.operational === quality.total
              ? "Nenhum cadastro inativo ou bloqueado."
              : `${quality.total - quality.operational} cadastro(s) não devem ser usados sem revisão.`,
        },
      ]
    }

    const total = participants.length
    const withoutDocument = participants.filter(
      (participant) => !participant.document,
    ).length
    const withoutAddress = participants.filter(
      (participant) => !participant.address?.zip_code,
    ).length
    const withoutContact = participants.filter(
      (participant) => !participant.email || !participant.phone,
    ).length
    const blockedOrInactive = statusCounts.blocked + statusCounts.inactive

    return [
      {
        label: "Documento",
        value: total - withoutDocument,
        total,
        description:
          withoutDocument === 0
            ? "Todos possuem CPF/CNPJ informado."
            : `${withoutDocument} cadastro(s) sem documento válido para operação.`,
      },
      {
        label: "Endereço",
        value: total - withoutAddress,
        total,
        description:
          withoutAddress === 0
            ? "Todos possuem CEP/endereço base."
            : `${withoutAddress} cadastro(s) sem endereço completo.`,
      },
      {
        label: "Contato",
        value: total - withoutContact,
        total,
        description:
          withoutContact === 0
            ? "Todos possuem e-mail e telefone."
            : `${withoutContact} cadastro(s) com contato incompleto.`,
      },
      {
        label: "Uso operacional",
        value: Math.max(total - blockedOrInactive, 0),
        total,
        description:
          blockedOrInactive === 0
            ? "Nenhum cadastro inativo ou bloqueado."
            : `${blockedOrInactive} cadastro(s) não devem ser usados sem revisão.`,
      },
    ]
  }, [participants, statusCounts, summary])

  const formChecklist = useMemo(() => {
    const normalizedDocument = normalizeDocument(form.document)
    const documentOk =
      form.document_type === "cpf"
        ? normalizedDocument.length === 11
        : normalizedDocument.length === 14

    return [
      {
        label: "Tipo escolhido",
        done: Boolean(form.participant_type),
      },
      {
        label: "Nome informado",
        done: form.name.trim().length >= 2,
      },
      {
        label: "Documento válido",
        done: documentOk,
      },
      {
        label: "Contato básico",
        done: form.email.includes("@") && onlyDigits(form.phone).length >= 8,
      },
      {
        label: "Endereço básico",
        done:
          onlyDigits(form.zip_code).length === 8 &&
          form.street.trim().length >= 2 &&
          form.city.trim().length >= 2 &&
          form.state.trim().length === 2,
      },
    ]
  }, [form])

  const hasActiveListFilters =
    listSearch.trim().length > 0 ||
    listTypeFilter !== "all" ||
    listPersonTypeFilter !== "all" ||
    listStatusFilter !== "all"

  function buildParticipantListParams(
    page: number,
    limit = PAGE_SIZE,
  ): ListParticipantsParams {
    return {
      company_id: activeCompanyId,
      participant_type: listTypeFilter === "all" ? undefined : listTypeFilter,
      person_type: listPersonTypeFilter === "all" ? undefined : listPersonTypeFilter,
      status: listStatusFilter === "all" ? undefined : listStatusFilter,
      search: listSearch.trim() || undefined,
      limit,
      offset: (page - 1) * limit,
    }
  }

  function markParticipantListFiltersDirty() {
    setHasListSearchStarted(false)
    setParticipants([])
    setListTotal(0)
    setListPage(1)
  }

  function clearParticipantListFilters() {
    setListSearch("")
    setListTypeFilter("all")
    setListPersonTypeFilter("all")
    setListStatusFilter("all")
    setHasListSearchStarted(false)
    setListPage(1)
    setListTotal(0)
    setParticipants([])
  }

  async function executeParticipantListSearch(page = 1) {
    try {
      setListState("loading")
      setModalMessage(null)
      const response = await getParticipantsPage(buildParticipantListParams(page))
      setParticipants(response.data.items)
      setListTotal(response.data.total)
      setHasListSearchStarted(true)
      setListPage(page)
      setListState("success")
    } catch (error) {
      setListState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao buscar participantes.",
      )
    }
  }

  function startParticipantListSearch() {
    setHasListSearchStarted(true)
    void executeParticipantListSearch(1)
  }

  function toggleOptionalField(key: OptionalFieldKey, enabled: boolean) {
    setOptionalFields((current) => ({
      ...current,
      [key]: enabled,
    }))
  }

  function handleZipCodeChange(value: string) {
    const cleanedCep = onlyDigits(value).slice(0, 8)

    setForm((current) => ({
      ...current,
      zip_code: cleanedCep,
    }))

    if (cleanedCep.length < 8) {
      setCepLookupState("idle")
      return
    }

    void lookupZipCode(cleanedCep)
  }

  async function lookupZipCode(cep: string) {
    try {
      setCepLookupState("loading")
      setModalMessage(null)

      const address = await fetchAddressByCep(cep)

      setForm((current) => ({
        ...current,
        street: address.logradouro?.trim() || current.street,
        complement: address.complemento?.trim() || current.complement,
        district: address.bairro?.trim() || current.district,
        city: address.localidade?.trim() || current.city,
        state: address.uf?.trim().toUpperCase().slice(0, 2) || current.state,
        ibge_municipality_code:
          address.ibge?.trim() || current.ibge_municipality_code,
      }))

      setOptionalFields((current) => ({
        ...current,
        complement: Boolean(address.complemento?.trim()) || current.complement,
        ibge_municipality_code: Boolean(address.ibge?.trim()),
      }))

      setCepLookupState("success")
    } catch (error) {
      setCepLookupState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao consultar o CEP.",
      )
    }
  }

  function syncFormFromParticipant(participant: Participant) {
    const documentDigits = onlyDigits(participant.document ?? "")

    setForm({
      company_id: participant.company_id,
      participant_type: participant.participant_type,
      person_type: participant.person_type,
      document_type: documentDigits.length === 11 ? "cpf" : "cnpj",
      name: participant.name,
      trade_name:
        participant.trade_name === "NI" ? "" : participant.trade_name ?? "",
      document: participant.document ?? "",
      email: participant.email ?? "",
      phone: participant.phone ?? "",
      secondary_phone: participant.secondary_phone ?? "",
      website: participant.website ?? "",
      contact_name: participant.contact_name ?? "",
      contact_phone: participant.contact_phone ?? "",
      contact_email: participant.contact_email ?? "",
      origin: (participant.origin ?? "") as ParticipantOrigin | "",
      status: participant.status,

      street: participant.address?.street ?? "",
      number: participant.address?.number ?? "",
      complement:
        participant.address?.complement === "NI"
          ? ""
          : participant.address?.complement ?? "",
      district: participant.address?.district ?? "",
      city: participant.address?.city ?? "",
      state: participant.address?.state ?? "SP",
      zip_code: participant.address?.zip_code ?? "",
      ibge_municipality_code:
        participant.address?.ibge_municipality_code ?? "",

      taxpayer_type: participant.fiscal_settings?.taxpayer_type ?? "unknown",
      tax_regime: participant.fiscal_settings?.tax_regime ?? "NI",
      main_cnae: participant.fiscal_settings?.main_cnae ?? "",
      state_registration:
        participant.fiscal_settings?.state_registration === "NI"
          ? ""
          : participant.fiscal_settings?.state_registration ?? "",
      municipal_registration:
        participant.fiscal_settings?.municipal_registration === "NI"
          ? ""
          : participant.fiscal_settings?.municipal_registration ?? "",
      is_foreign: participant.fiscal_settings?.is_foreign ?? false,
      fiscal_notes:
        participant.fiscal_settings?.fiscal_notes === "NI"
          ? ""
          : participant.fiscal_settings?.fiscal_notes ?? "",

      bank_name:
        participant.financial_settings?.bank_name === "NI"
          ? ""
          : participant.financial_settings?.bank_name ?? "",
      bank_branch:
        participant.financial_settings?.bank_branch === "NI"
          ? ""
          : participant.financial_settings?.bank_branch ?? "",
      bank_account:
        participant.financial_settings?.bank_account === "NI"
          ? ""
          : participant.financial_settings?.bank_account ?? "",
      pix_key:
        participant.financial_settings?.pix_key === "NI"
          ? ""
          : participant.financial_settings?.pix_key ?? "",
      credit_limit:
        participant.financial_settings?.credit_limit === "NI"
          ? ""
          : participant.financial_settings?.credit_limit ?? "",
      payment_priority:
        participant.financial_settings?.payment_priority === "NI"
          ? ""
          : participant.financial_settings?.payment_priority ?? "",

      notes: participant.notes === "NI" ? "" : participant.notes ?? "",
    })

    setOptionalFields({
      trade_name: isFilledOptional(participant.trade_name),
      secondary_phone: Boolean(participant.secondary_phone),
      website: Boolean(participant.website),
      contact_name: Boolean(participant.contact_name),
      contact_phone: Boolean(participant.contact_phone),
      contact_email: Boolean(participant.contact_email),
      origin: Boolean(participant.origin),
      complement: isFilledOptional(participant.address?.complement),
      ibge_municipality_code: isFilledOptional(
        participant.address?.ibge_municipality_code,
      ),
      taxpayer_type: Boolean(
        participant.fiscal_settings?.taxpayer_type &&
          participant.fiscal_settings.taxpayer_type !== "unknown",
      ),
      tax_regime: isFilledOptional(participant.fiscal_settings?.tax_regime),
      main_cnae: isFilledOptional(participant.fiscal_settings?.main_cnae),
      state_registration: isFilledOptional(
        participant.fiscal_settings?.state_registration,
      ),
      municipal_registration: isFilledOptional(
        participant.fiscal_settings?.municipal_registration,
      ),
      fiscal_notes: isFilledOptional(participant.fiscal_settings?.fiscal_notes),
      bank_name: isFilledOptional(participant.financial_settings?.bank_name),
      bank_branch: isFilledOptional(participant.financial_settings?.bank_branch),
      bank_account: isFilledOptional(
        participant.financial_settings?.bank_account,
      ),
      pix_key: isFilledOptional(participant.financial_settings?.pix_key),
      credit_limit: isFilledOptional(
        participant.financial_settings?.credit_limit,
      ),
      payment_priority: isFilledOptional(
        participant.financial_settings?.payment_priority,
      ),
      notes: isFilledOptional(participant.notes),
    })
  }

  const loadParticipants = useCallback(async (auditParticipantId?: string | null) => {
    try {
      setState("loading")
      setModalMessage(null)

      const [companiesResponse, rulesResponse] =
        await Promise.all([getCompanies(), getParticipantRules()])

      const companyList = companiesResponse.data
      const visibleCompanies = sessionCompanyId
        ? companyList.filter((company) => company.id === sessionCompanyId)
        : companyList
      const resolvedCompanyId = pickActiveCompanyId(
        visibleCompanies,
        sessionCompanyId || activeCompanyId,
      )

      setCompanies(visibleCompanies)
      setRules(rulesResponse.data)

      if (resolvedCompanyId !== activeCompanyId) {
        setActiveCompanyIdState(resolvedCompanyId)
      }

      setForm((current) => ({
        ...current,
        company_id: resolvedCompanyId,
      }))

      if (visibleCompanies.length === 0) {
        setParticipants([])
        setSummary(null)
        setDiagnostics(null)
        setState("success")
        return
      }

      const [summaryResponse, diagnosticsResponse] = await Promise.all([
        getParticipantSummary(resolvedCompanyId),
        getParticipantDiagnostics(resolvedCompanyId),
      ])

      setSummary(summaryResponse.data)
      setDiagnostics(diagnosticsResponse.data)
      setParticipants([])
      setListTotal(0)
      setHasListSearchStarted(false)
      setListPage(1)

      if (auditParticipantId) {
        const auditResponse = await getParticipantAuditEvents(auditParticipantId)
        setAuditEvents(auditResponse.data)
      }

      setState("success")
    } catch (error) {
      setState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao carregar participantes.",
      )
    }
  }, [activeCompanyId, sessionCompanyId])

  async function openEditParticipant(participant: Participant) {
    try {
      setSelectedParticipantId(participant.id)
      syncFormFromParticipant(participant)
      setModalMessage(null)
      setSuccessMessage(null)
      setView("form")

      const auditResponse = await getParticipantAuditEvents(participant.id)
      setAuditEvents(auditResponse.data)
    } catch (error) {
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro inesperado ao carregar auditoria do participante.",
      )
    }
  }

  function openNewParticipant() {
    if (!canWriteParticipants) {
      setModalMessage("Você não tem permissão participants.write para criar participantes.")
      return
    }

    setSelectedParticipantId(null)
    setAuditEvents([])
    setForm({ ...INITIAL_FORM, company_id: activeCompanyId })
    setOptionalFields({ ...INITIAL_OPTIONAL_FIELDS })
    setModalMessage(null)
    setSuccessMessage(null)
    setCepLookupState("idle")
    setView("form")
  }

  function openNewParticipantWithType(participantType: ParticipantType) {
    if (!canWriteParticipants) {
      setModalMessage("Você não tem permissão participants.write para criar participantes.")
      return
    }

    setSelectedParticipantId(null)
    setAuditEvents([])
    setForm({
      ...INITIAL_FORM,
      company_id: activeCompanyId,
      participant_type: participantType,
      person_type:
        participantType === "customer" || participantType === "supplier"
          ? "company"
          : INITIAL_FORM.person_type,
      document_type:
        participantType === "customer" || participantType === "supplier"
          ? "cnpj"
          : INITIAL_FORM.document_type,
    })
    setOptionalFields({ ...INITIAL_OPTIONAL_FIELDS })
    setModalMessage(null)
    setSuccessMessage(null)
    setCepLookupState("idle")
    setView("form")
  }

  function validateForm() {
    const normalizedDocument = normalizeDocument(form.document)

    if (!form.company_id.startsWith("emp_")) {
      return "Informe uma empresa válida com prefixo emp_."
    }

    if (form.name.trim().length < 2) {
      return "Informe o nome ou razão social do participante."
    }

    if (form.document_type === "cpf" && normalizedDocument.length !== 11) {
      return "CPF deve conter exatamente 11 números."
    }

    if (form.document_type === "cnpj" && normalizedDocument.length !== 14) {
      return "CNPJ deve conter exatamente 14 números."
    }


    if (form.email.trim() && !form.email.includes("@")) {
      return "O e-mail informado é inválido."
    }

    if (form.phone.trim() && onlyDigits(form.phone).length < 8) {
      return "O telefone informado deve conter pelo menos 8 dígitos."
    }

    if (form.contact_email.trim() && !form.contact_email.includes("@")) {
      return "O e-mail do contato informado é inválido."
    }

    if (onlyDigits(form.zip_code).length !== 8) {
      return "Informe o CEP com 8 dígitos."
    }

    if (form.street.trim().length < 2) {
      return "Informe o logradouro."
    }

    if (form.number.trim().length < 1) {
      return "Informe o número do endereço."
    }

    if (form.district.trim().length < 2) {
      return "Informe o bairro."
    }

    if (form.city.trim().length < 2) {
      return "Informe a cidade."
    }

    if (form.state.trim().length !== 2) {
      return "Informe a UF com 2 letras."
    }

    if (
      optionalFields.ibge_municipality_code &&
      onlyDigits(form.ibge_municipality_code).length !== 7
    ) {
      return "Código IBGE deve conter exatamente 7 números."
    }

    if (optionalFields.tax_regime && form.tax_regime.trim().length < 2) {
      return "Selecione o regime tributário do participante."
    }

    if (optionalFields.main_cnae && onlyDigits(form.main_cnae).length !== 7) {
      return "CNAE principal deve conter exatamente 7 números."
    }

    return null
  }

  function buildPayload(): ParticipantCreatePayload {
    return {
      company_id: form.company_id,
      participant_type: form.participant_type,
      person_type: form.person_type,
      name: form.name.trim(),
      trade_name: normalizeOptionalText(optionalFields.trade_name, form.trade_name),
      document: normalizeDocument(form.document) || null,
      email: form.email.trim() || null,
      phone: onlyDigits(form.phone) || null,
      secondary_phone: optionalFields.secondary_phone ? (onlyDigits(form.secondary_phone) || null) : null,
      website: optionalFields.website ? (form.website.trim() || null) : null,
      contact_name: optionalFields.contact_name ? (form.contact_name.trim() || null) : null,
      contact_phone: optionalFields.contact_phone ? (onlyDigits(form.contact_phone) || null) : null,
      contact_email: optionalFields.contact_email ? (form.contact_email.trim() || null) : null,
      origin: optionalFields.origin && form.origin ? (form.origin as ParticipantOrigin) : null,
      status: form.status,
      address: {
        street: form.street.trim(),
        number: form.number.trim(),
        complement: normalizeOptionalText(
          optionalFields.complement,
          form.complement,
        ),
        district: form.district.trim(),
        city: form.city.trim(),
        state: form.state.trim().toUpperCase(),
        zip_code: onlyDigits(form.zip_code),
        country: "BR",
        ibge_municipality_code: normalizeOptionalNumericCode(
          optionalFields.ibge_municipality_code,
          form.ibge_municipality_code,
        ),
      },
      fiscal_settings: {
        taxpayer_type: optionalFields.taxpayer_type ? form.taxpayer_type : "unknown",
        tax_regime: optionalFields.tax_regime ? form.tax_regime : null,
        main_cnae: normalizeOptionalNumericCode(optionalFields.main_cnae, form.main_cnae),
        state_registration: normalizeOptionalText(optionalFields.state_registration, form.state_registration),
        municipal_registration: normalizeOptionalText(optionalFields.municipal_registration, form.municipal_registration),
        suframa_registration: null,
        is_foreign: form.is_foreign,
        fiscal_notes: normalizeOptionalText(optionalFields.fiscal_notes, form.fiscal_notes),
      },
      financial_settings: {
        default_payment_method: null,
        default_payment_terms: null,
        bank_name: normalizeOptionalText(optionalFields.bank_name, form.bank_name),
        bank_branch: normalizeOptionalText(
          optionalFields.bank_branch,
          form.bank_branch,
        ),
        bank_account: normalizeOptionalText(
          optionalFields.bank_account,
          form.bank_account,
        ),
        pix_key: normalizeOptionalText(optionalFields.pix_key, form.pix_key),
        credit_limit: normalizeOptionalText(
          optionalFields.credit_limit,
          form.credit_limit,
        ),
        payment_priority: normalizeOptionalText(
          optionalFields.payment_priority,
          form.payment_priority,
        ),
      },
      notes: normalizeOptionalText(optionalFields.notes, form.notes),
    }
  }

  function buildExportRows(source: Participant[]): ExportTable {
    return [
      [
        "ID",
        "Empresa",
        "Tipo",
        "Tipo de pessoa",
        "Status",
        "Nome / Razão social",
        "Nome fantasia",
        "CPF/CNPJ",
        "CPF/CNPJ formatado",
        "E-mail",
        "Telefone",
        "Logradouro",
        "Número",
        "Complemento",
        "Bairro",
        "Cidade",
        "UF",
        "CEP",
        "Código IBGE",
        "Tipo de contribuinte",
        "Regime tributário",
        "CNAE principal",
        "Inscrição estadual",
        "Inscrição municipal",
        "Participante estrangeiro",
        "Observações fiscais",
        "Banco",
        "Agência",
        "Conta",
        "Chave Pix",
        "Limite de crédito",
        "Prioridade de pagamento",
        "Observacoes",
        "Criado em",
        "Atualizado em",
      ],
      ...source.map((participant) => [
        participant.id,
        participant.company_id,
        getParticipantTypeLabel(participant.participant_type),
        getPersonTypeLabel(participant.person_type),
        getStatusLabel(participant.status),
        participant.name,
        participant.trade_name ?? "NI",
        participant.document ?? "NI",
        formatDocument(participant.document),
        participant.email ?? "NI",
        participant.phone ?? "NI",
        participant.address?.street ?? "NI",
        participant.address?.number ?? "NI",
        participant.address?.complement ?? "NI",
        participant.address?.district ?? "NI",
        participant.address?.city ?? "NI",
        participant.address?.state ?? "NI",
        participant.address?.zip_code ?? "NI",
        participant.address?.ibge_municipality_code ?? "NI",
        getTaxpayerTypeLabel(participant.fiscal_settings?.taxpayer_type),
        getTaxRegimeLabel(participant.fiscal_settings?.tax_regime),
        participant.fiscal_settings?.main_cnae ?? "NI",
        participant.fiscal_settings?.state_registration ?? "NI",
        participant.fiscal_settings?.municipal_registration ?? "NI",
        participant.fiscal_settings?.is_foreign ? "Sim" : "Não",
        participant.fiscal_settings?.fiscal_notes ?? "NI",
        participant.financial_settings?.bank_name ?? "NI",
        participant.financial_settings?.bank_branch ?? "NI",
        participant.financial_settings?.bank_account ?? "NI",
        participant.financial_settings?.pix_key ?? "NI",
        participant.financial_settings?.credit_limit ? moneyCell(participant.financial_settings.credit_limit) : "NI",
        participant.financial_settings?.payment_priority ?? "NI",
        participant.notes ?? "NI",
        dateCell(participant.created_at),
        dateCell(participant.updated_at),
      ]),
    ]
  }

async function exportFilteredParticipants(format: ExportFormat) {
  if (!hasListSearchStarted) {
    setModalMessage("Realize uma busca antes de exportar os participantes.")
    return
  }

  if (listTotal === 0) {
    setModalMessage("Não há participantes no resultado filtrado para exportar.")
    return
  }

  if (listTotal > EXPORT_LIMIT) {
    setModalMessage(
      `O resultado possui ${listTotal} participantes. Refine os filtros para exportar até ${EXPORT_LIMIT} registros por vez.`,
    )
    return
  }

  try {
    const exportResponse = await getParticipantsPage(
      buildParticipantListParams(1, EXPORT_LIMIT),
    )
    const rows = buildExportRows(exportResponse.data.items)
    const today = new Date().toISOString().slice(0, 10)
    const fileBaseName = `kovir-participantes-${today}`

    if (format === "xlsx") {
      exportXlsxFile(rows, "Participantes", `${fileBaseName}.xlsx`)
      return
    }
    exportCsvFile(rows, `${fileBaseName}.csv`)
  } catch (error) {
    setModalMessage(
      error instanceof Error
        ? error.message
        : "Erro inesperado ao exportar participantes.",
    )
  }
}

async function handleSaveParticipant() {
  try {
    if (!canWriteParticipants) {
      setModalMessage("Você não tem permissão participants.write para salvar participantes.")
      return
    }

    setActionState("loading")
    setModalMessage(null)
    setSuccessMessage(null)

    const validationError = validateForm()

    if (validationError) {
      setActionState("error")
      setModalMessage(validationError)
      return
    }

    const payload = buildPayload()

    const response = selectedParticipantId
      ? await updateParticipant(selectedParticipantId, payload)
      : await createParticipant(payload)

    setSelectedParticipantId(response.data.id)
    setSuccessMessage(
      selectedParticipantId
        ? "Participante atualizado com sucesso."
        : "Participante cadastrado com sucesso.",
    )

    const [summaryResponse, diagnosticsResponse, auditResponse] =
      await Promise.all([
        getParticipantSummary(activeCompanyId),
        getParticipantDiagnostics(activeCompanyId),
        getParticipantAuditEvents(response.data.id),
      ])

    if (hasListSearchStarted) {
      const listResponse = await getParticipantsPage(buildParticipantListParams(safeListPage))
      setParticipants(listResponse.data.items)
      setListTotal(listResponse.data.total)
    }

    setSummary(summaryResponse.data)
    setDiagnostics(diagnosticsResponse.data)
    setAuditEvents(auditResponse.data)
    setActionState("success")
  } catch (error) {
    setActionState("error")
    setModalMessage(
      error instanceof Error
        ? error.message
        : "Erro inesperado ao salvar participante.",
    )
  }
}



  useEffect(() => {
    void loadParticipants()
  }, [loadParticipants])

  return (
    <section className="min-h-screen text-[var(--color-text)]">
      <ValidationModal
        message={modalMessage}
        onClose={() => setModalMessage(null)}
      />

      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] transition-colors sm:p-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <StatusBadge>Bloco 2 — Participantes</StatusBadge>

              <h1 className="mt-5 text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
                Participantes
              </h1>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)] sm:text-base">
                Use esta tela como uma base guiada para cadastrar quem participa
                das operações: clientes, fornecedores, bancos, gateways,
                marketplaces, transportadoras e terceiros. Cada cadastro bem feito
                evita retrabalho em vendas, compras, financeiro, fiscal e estoque.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row xl:flex-col">
              <button
                type="button"
                onClick={openNewParticipant}
                disabled={!canWriteParticipants}
                className="rounded-xl bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {canWriteParticipants ? "Novo participante guiado" : "Sem permissão"}
              </button>

              <button
                type="button"
                onClick={() => setView("list")}
                className="rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-5 py-3 text-sm font-semibold text-[var(--color-primary)] transition hover:opacity-90"
              >
                Buscar / editar cadastros
              </button>

              <button
                type="button"
                onClick={() => void loadParticipants()}
                disabled={state === "loading"}
                className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-3 text-sm font-medium text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {state === "loading" ? "Atualizando..." : "Atualizar dados"}
              </button>
            </div>
          </div>
        </header>

        {successMessage ? (
          <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm font-medium text-emerald-700">
            <span>✓</span>
            {successMessage}
          </div>
        ) : null}

        

        <ParticipantsModuleTabs
        view={view}
        onSelect={(nextView) => setView(nextView)}
      />

      {view === "overview" ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <InfoCard
                title="Participantes cadastrados"
                value={summary?.total_participants ?? diagnostics?.total_participants ?? 0}
                description="Base disponível para os próximos módulos"
              />

              <InfoCard
                title="Ativos para uso"
                value={statusCounts.active}
                description="Podem ser usados nas operações"
              />

              <InfoCard
                title="Bloqueados/inativos"
                value={statusCounts.blocked + statusCounts.inactive}
                description="Revise antes de usar"
              />

              <InfoCard
                title="Auditoria"
                value={diagnostics?.total_audit_events ?? auditEvents.length}
                description={auditSummary}
              />
            </div>

            <SectionCard
              title="Modo guiado: por onde começar"
              description="Para um ERP ficar fácil de usar depois, o cadastro precisa começar simples e com ordem. Comece pelos tipos que geram operação real."
            >
              <div className="grid gap-4 lg:grid-cols-3">
                <GuidedActionCard
                  step="1"
                  title="Cadastrar clientes"
                  description="Clientes serão usados em vendas, contas a receber, cobrança, faturamento e documentos fiscais de saída."
                  actionLabel="Novo cliente"
                  onClick={() => openNewParticipantWithType("customer")}
                />

                <GuidedActionCard
                  step="2"
                  title="Cadastrar fornecedores"
                  description="Fornecedores serão usados em compras, despesas, contas a pagar, entrada fiscal e controle de obrigações."
                  actionLabel="Novo fornecedor"
                  onClick={() => openNewParticipantWithType("supplier")}
                />

                <GuidedActionCard
                  step="3"
                  title="Revisar a base"
                  description="Use a busca para encontrar cadastros sem contato, bloqueados, inativos ou com dados fiscais incompletos."
                  actionLabel="Ir para busca"
                  onClick={() => setView("list")}
                />
              </div>
            </SectionCard>

            <SectionCard
              title="Qual tipo de participante escolher?"
              description="A escolha correta evita confusão nos módulos seguintes. Esta tela não é uma agenda de contatos; é a base operacional do ERP."
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {(rules?.participant_types ?? PARTICIPANT_TYPES).map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => openNewParticipantWithType(type)}
                    className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left transition hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-[var(--color-text)]">
                          {getParticipantTypeLabel(type)}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">
                          {getParticipantTypeExample(type)}
                        </p>
                      </div>

                      <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-2 py-1 text-xs font-bold text-[var(--color-primary)]">
                        {typeCounts[type] ?? 0}
                      </span>
                    </div>

                    <p className="mt-4 text-xs leading-5 text-[var(--color-text-muted)]">
                      {getParticipantTypeDescription(type)}
                    </p>
                  </button>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Qualidade da base cadastral"
              description="Antes de avançar para financeiro, fiscal e documentos, o ideal é reduzir cadastros incompletos."
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {dataQualityCards.map((card) => (
                  <div
                    key={card.label}
                    className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5"
                  >
                    <p className="text-sm text-[var(--color-text-muted)]">
                      {card.label}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-[var(--color-text)]">
                      {card.value}/{card.total}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">
                      {card.description}
                    </p>
                  </div>
                ))}
              </div>

              <GuideNote title="Regra prática">
                Cadastre apenas dados que ajudam a operar. Se não souber uma informação fiscal ou bancária agora, deixe como NI e complete quando ela for necessária.
              </GuideNote>
            </SectionCard>

            <SectionCard
              title="Conexões futuras deste cadastro"
              description="Participante é cadastro mestre. Ele será reaproveitado por praticamente todo o Kovir."
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {[
                  "Cliente → venda → conta a receber → cobrança",
                  "Fornecedor → compra/despesa → conta a pagar",
                  "Banco/gateway → recebimento → baixa → conciliação",
                  "Marketplace → pedido externo → venda interna",
                  "Transportadora → frete → vínculo fiscal/logístico",
                  "Prestador → serviço → despesa recorrente",
                ].map((item) => (
                  <div
                    key={item}
                    className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-sm font-medium leading-6 text-[var(--color-text)]"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Insights da base atual"
              description="Leituras automáticas para orientar a próxima ação."
            >
              <div className="grid gap-4 lg:grid-cols-2">
                {insights.map((insight) => (
                  <div
                    key={insight.title}
                    className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-5"
                  >
                    <h3 className="font-semibold text-[var(--color-text)]">
                      {insight.title}
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
                      {insight.text}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </>
        ) : null}
        {view === "list" ? (
          <SectionCard
            title="Buscar, revisar e editar participantes"
            description="Use esta área como uma mesa de revisão. Primeiro filtre, depois busque, então edite ou exporte somente o resultado encontrado."
          >
            <div className="mb-6 grid gap-4 lg:grid-cols-3">
              {[
                {
                  step: "1",
                  title: "Escolha os filtros",
                  text: "Busque por nome, documento, e-mail, tipo ou status. Evite editar cadastro no escuro.",
                },
                {
                  step: "2",
                  title: "Clique em buscar",
                  text: "A listagem só aparece após a busca para manter a tela leve e controlada.",
                },
                {
                  step: "3",
                  title: "Edite ou exporte",
                  text: "Abra o cadastro para corrigir dados ou exporte exatamente o resultado filtrado.",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4"
                >
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--color-primary-soft)] text-sm font-black text-[var(--color-primary)]">
                      {item.step}
                    </span>
                    <p className="font-semibold text-[var(--color-text)]">
                      {item.title}
                    </p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[var(--color-text-muted)]">
                    {item.text}
                  </p>
                </div>
              ))}
            </div>

            <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <InfoCard
                title="Total cadastrado"
                value={summary?.total_participants ?? diagnostics?.total_participants ?? 0}
                description="Todos os participantes"
              />

              <InfoCard
                title="Ativos"
                value={statusCounts.active}
                description="Disponíveis para uso"
              />

              <InfoCard
                title="Bloqueados"
                value={statusCounts.blocked}
                description="Exigem atenção"
              />

              <InfoCard
                title="Resultado atual"
                value={listTotal}
                description={
                  hasListSearchStarted
                    ? "Após busca/filtros"
                    : "Busca ainda não realizada"
                }
              />
            </div>

            <div className="mb-5 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="font-semibold text-[var(--color-text)]">
                    Filtros guiados
                  </h3>

                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    Comece amplo. Se vier resultado demais, refine por tipo ou status.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={clearParticipantListFilters}
                  disabled={!hasActiveListFilters && !hasListSearchStarted}
                  className="w-fit rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-2 text-sm font-medium text-[var(--color-text-muted)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Limpar filtros
                </button>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Buscar">
                  <TextInput
                    value={listSearch}
                    onChange={(value) => {
                      setListSearch(value)
                      markParticipantListFiltersDirty()
                    }}
                    placeholder="Nome, doc, e-mail, contato..."
                  />
                </Field>

                <Field label="Tipo">
                  <SelectInput
                    value={listTypeFilter}
                    onChange={(value) => {
                      setListTypeFilter(value as ParticipantType | "all")
                      markParticipantListFiltersDirty()
                    }}
                    options={[
                      { value: "all", label: "Todos os tipos" },
                      { value: "customer", label: "Cliente" },
                      { value: "supplier", label: "Fornecedor" },
                      { value: "carrier", label: "Transportadora" },
                      { value: "service_provider", label: "Prestador de serviço" },
                      { value: "marketplace", label: "Marketplace" },
                      { value: "gateway", label: "Gateway" },
                      { value: "bank", label: "Banco" },
                      { value: "other", label: "Outro" },
                    ]}
                  />
                </Field>

                <Field label="Pessoa">
                  <SelectInput
                    value={listPersonTypeFilter}
                    onChange={(value) => {
                      setListPersonTypeFilter(value as PersonType | "all")
                      markParticipantListFiltersDirty()
                    }}
                    options={[
                      { value: "all", label: "Todos" },
                      { value: "individual", label: "Pessoa física" },
                      { value: "company", label: "Pessoa jurídica" },
                    ]}
                  />
                </Field>

                <Field label="Status">
                  <SelectInput
                    value={listStatusFilter}
                    onChange={(value) => {
                      setListStatusFilter(value as ParticipantStatus | "all")
                      markParticipantListFiltersDirty()
                    }}
                    options={[
                      { value: "all", label: "Todos" },
                      { value: "draft", label: "Rascunho" },
                      { value: "active", label: "Ativo" },
                      { value: "inactive", label: "Inativo" },
                      { value: "blocked", label: "Bloqueado" },
                    ]}
                  />
                </Field>
              </div>

              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <button
                  type="button"
                  onClick={startParticipantListSearch}
                  disabled={listState === "loading"}
                  className="rounded-xl bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {listState === "loading" ? "Buscando..." : "Buscar participantes"}
                </button>

                <div className="flex flex-col gap-3 sm:flex-row">
                  <button
                    type="button"
                    onClick={() => void exportFilteredParticipants("xlsx")}
                    disabled={!hasListSearchStarted || listTotal === 0}
                    className="rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-5 py-3 text-sm font-semibold text-[var(--color-primary)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    title={hasListSearchStarted && listTotal > 0 ? `Exportar todos os ${listTotal} participantes encontrados` : undefined}
                  >
                    Exportar XLSX{hasListSearchStarted && listTotal > 0 ? ` (${listTotal})` : ""}
                  </button>

                  <button
                    type="button"
                    onClick={() => void exportFilteredParticipants("csv")}
                    disabled={!hasListSearchStarted || listTotal === 0}
                    className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-5 py-3 text-sm font-semibold text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                    title={hasListSearchStarted && listTotal > 0 ? `Exportar todos os ${listTotal} participantes encontrados` : undefined}
                  >
                    Exportar CSV{hasListSearchStarted && listTotal > 0 ? ` (${listTotal})` : ""}
                  </button>
                </div>
              </div>

              {hasListSearchStarted ? (
                <div className="mt-4 rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm text-[var(--color-primary)]">
                  Resultado:{" "}
                  <strong>{listTotal}</strong> participante(s) encontrado(s).
                  {totalPages > 1 ? ` Exibindo ${PAGE_SIZE} por página — o export inclui todos.` : ""}
                </div>
              ) : null}
            </div>

            <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-[var(--color-text)]">
                  {hasListSearchStarted
                    ? `${listTotal} participante(s) encontrado(s)${totalPages > 1 ? ` • exibindo página ${safeListPage} de ${totalPages}` : ""}`
                    : "Nenhuma busca realizada"}
                </p>

                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {hasListSearchStarted && totalPages > 1
                    ? `Lista paginada em ${PAGE_SIZE} por página. O export XLSX/CSV inclui todos os ${listTotal} resultados.`
                    : "Após realizar a busca, os dados poderão ser exportados em XLSX ou CSV."}
                </p>
              </div>

              <button
                type="button"
                onClick={openNewParticipant}
                disabled={!canWriteParticipants}
                className="rounded-xl bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {canWriteParticipants ? "Cadastrar novo participante" : "Sem permissão"}
              </button>
            </div>

            {!hasListSearchStarted ? (
              <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">
                Realize uma busca para carregar a listagem de participantes.
              </div>
            ) : listTotal === 0 ? (
              <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-6 text-sm text-[var(--color-text-muted)]">
                Nenhum participante encontrado para os filtros atuais.
              </div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)]">
                <div className="hidden overflow-x-auto xl:block">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="border-b border-[var(--color-border-soft)] bg-[var(--color-surface)] text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
                      <tr>
                        <th className="px-5 py-4 font-semibold">Participante</th>
                        <th className="px-5 py-4 font-semibold">Tipo</th>
                        <th className="px-5 py-4 font-semibold">Documento</th>
                        <th className="px-5 py-4 font-semibold">Contato</th>
                        <th className="px-5 py-4 font-semibold">Status</th>
                        <th className="px-5 py-4 font-semibold">Atualizado em</th>
                        <th className="px-5 py-4 text-right font-semibold">
                          Ação
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {pagedParticipants.map((participant) => (
                        <tr
                          key={participant.id}
                          className="border-b border-[var(--color-border-soft)] last:border-b-0 hover:bg-[var(--color-hover)]"
                        >
                          <td className="px-5 py-4">
                            <p className="font-semibold text-[var(--color-text)]">
                              {participant.name}
                            </p>

                            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                              {participant.trade_name &&
                              participant.trade_name !== "NI"
                                ? participant.trade_name
                                : "Nome fantasia não informado"}
                            </p>

                            <p className="mt-2 max-w-[260px] truncate font-mono text-xs text-[var(--color-primary)]">
                              {participant.id}
                            </p>
                          </td>

                          <td className="px-5 py-4 text-[var(--color-text-muted)]">
                            {getParticipantTypeLabel(
                              participant.participant_type,
                            )}
                          </td>

                          <td className="px-5 py-4 text-[var(--color-text-muted)]">
                            {formatDocument(participant.document)}
                          </td>

                          <td className="px-5 py-4">
                            <p className="text-[var(--color-text-muted)]">
                              {participant.email ?? "sem e-mail"}
                            </p>

                            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                              {participant.phone ?? "sem telefone"}
                            </p>
                          </td>

                          <td className="px-5 py-4">
                            <StatusBadge>
                              {getStatusLabel(participant.status)}
                            </StatusBadge>
                          </td>

                          <td className="px-5 py-4 text-xs text-[var(--color-text-muted)]">
                            {formatDateTimeBR(participant.updated_at)}
                          </td>

                          <td className="px-5 py-4 text-right">
                            <button
                              type="button"
                              onClick={() =>
                                void openEditParticipant(participant)
                              }
                              className="rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] transition hover:opacity-90"
                            >
                              Editar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="space-y-3 p-4 xl:hidden">
                  {pagedParticipants.map((participant) => (
                    <div
                      key={participant.id}
                      className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4"
                    >
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold text-[var(--color-text)]">
                              {participant.name}
                            </h3>

                            <StatusBadge>
                              {getStatusLabel(participant.status)}
                            </StatusBadge>
                          </div>

                          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                            {getParticipantTypeLabel(
                              participant.participant_type,
                            )}{" "}
                            • {formatDocument(participant.document)}
                          </p>

                          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                            {participant.email ?? "sem e-mail"} •{" "}
                            {participant.phone ?? "sem telefone"}
                          </p>

                          <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                            Atualizado em{" "}
                            {formatDateTimeBR(participant.updated_at)}
                          </p>

                          <p className="mt-2 break-all font-mono text-xs text-[var(--color-primary)]">
                            {participant.id}
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() => void openEditParticipant(participant)}
                          className="w-fit rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] transition hover:opacity-90"
                        >
                          Editar cadastro
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {hasListSearchStarted && listTotal > 0 && (
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-[var(--color-text-muted)]">
                  Mostrando{" "}
                  <strong className="text-[var(--color-text)]">
                    {(safeListPage - 1) * PAGE_SIZE + 1}–{Math.min((safeListPage - 1) * PAGE_SIZE + visibleParticipants.length, listTotal)}
                  </strong>{" "}
                  de{" "}
                  <strong className="text-[var(--color-text)]">
                    {listTotal}
                  </strong>{" "}
                  participante(s)
                  {totalPages > 1 ? ` • página ${safeListPage} de ${totalPages}` : ""}
                </p>

                {totalPages > 1 && (
                  <div className="flex flex-wrap items-center gap-1">
                    <button
                      type="button"
                      disabled={safeListPage === 1}
                      onClick={() => void executeParticipantListSearch(safeListPage - 1)}
                      className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-sm font-medium text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      ← Anterior
                    </button>

                    {Array.from({ length: totalPages }, (_, i) => i + 1)
                      .filter((p) => p === 1 || p === totalPages || Math.abs(p - safeListPage) <= 2)
                      .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                        if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…")
                        acc.push(p)
                        return acc
                      }, [])
                      .map((item, idx) =>
                        item === "…" ? (
                          <span
                            key={`ellipsis-${idx}`}
                            className="px-2 text-sm text-[var(--color-text-muted)]"
                          >
                            …
                          </span>
                        ) : (
                          <button
                            key={item}
                            type="button"
                            onClick={() => void executeParticipantListSearch(item as number)}
                            className={`min-w-[2.5rem] rounded-xl border px-3 py-2 text-sm font-medium transition ${
                              safeListPage === item
                                ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                                : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text)] hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)]"
                            }`}
                          >
                            {item}
                          </button>
                        ),
                      )}

                    <button
                      type="button"
                      disabled={safeListPage === totalPages}
                      onClick={() => void executeParticipantListSearch(safeListPage + 1)}
                      className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-sm font-medium text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Próxima →
                    </button>
                  </div>
                )}
              </div>
            )}
          </SectionCard>
        ) : null}

        {view === "form" ? (
          <SectionCard
            title={
              selectedParticipantId
                ? "Editar participante"
                : "Cadastrar participante no modo guiado"
            }
            description="Preencha primeiro o mínimo operacional. Campos opcionais só devem ser ligados quando você realmente tiver a informação."
          >
            <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {formChecklist.map((item) => (
                <ChecklistChip
                  key={item.label}
                  label={item.label}
                  done={item.done}
                />
              ))}
            </div>

            <GuideNote title="Como usar este formulário">
              Siga as seções em ordem: dados gerais, endereço, fiscal, financeiro e auditoria. O botão de ligar/desligar campo opcional evita cadastro poluído com dados chutados.
            </GuideNote>

            <div className="mt-6 grid gap-6 xl:grid-cols-[210px_minmax(0,1fr)]">
              <ParticipantFormSectionNav />

              <div className="grid gap-6">
              <section id="participant-section-general" className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    1. Identificação do participante
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Diga quem é, que tipo de relação ele tem com a empresa e como será encontrado depois.
                  </p>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <Field label="Empresa da sessão">
                    <select
                      value={form.company_id || activeCompanyId}
                      disabled
                      className="field-input"
                    >
                        <option value={form.company_id || activeCompanyId}>
                                {activeCompanyName || "Empresa não identificada"}
                        </option>
                    </select>
                    <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">
                      Usando {activeCompanyName}. A mesma empresa alimenta Participantes, Produtos, Vendas e Estoque.
                    </p>
                  </Field>

                  <Field label="Tipo de participante">
                    <SelectInput
                      value={form.participant_type}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          participant_type: value,
                        }))
                      }
                      options={[
                        { value: "customer", label: "Cliente" },
                        { value: "supplier", label: "Fornecedor" },
                        { value: "carrier", label: "Transportadora" },
                        {
                          value: "service_provider",
                          label: "Prestador de serviço",
                        },
                        { value: "marketplace", label: "Marketplace" },
                        { value: "gateway", label: "Gateway" },
                        { value: "bank", label: "Banco" },
                        { value: "other", label: "Outro" },
                      ]}
                    />
                  </Field>

                  <Field label="Tipo de pessoa">
                    <SelectInput
                      value={form.person_type}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          person_type: value,
                          document_type:
                            value === "individual"
                              ? "cpf"
                              : value === "company"
                                ? "cnpj"
                                : current.document_type,
                          document:
                            value === "individual" || value === "company"
                              ? ""
                              : current.document,
                        }))
                      }
                      options={[
                        { value: "company", label: "Pessoa jurídica" },
                        { value: "individual", label: "Pessoa física" },
                      ]}
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
                        { value: "active", label: "Ativo" },
                        { value: "inactive", label: "Inativo" },
                        { value: "blocked", label: "Bloqueado" },
                      ]}
                    />
                  </Field>

                  <Field label="Nome / Razão social">
                    <TextInput
                      value={form.name}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          name: value,
                        }))
                      }
                      placeholder="Ex.: Cliente LTDA"
                    />
                  </Field>

                  <Field label="Tipo de documento">
                    <SelectInput
                      value={form.document_type}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          document_type: value,
                          document: "",
                        }))
                      }
                      options={
                        form.person_type === "individual"
                          ? [{ value: "cpf", label: "CPF — 11 números" }]
                          : form.person_type === "company"
                            ? [{ value: "cnpj", label: "CNPJ — 14 números" }]
                            : [
                                { value: "cpf", label: "CPF — 11 números" },
                                { value: "cnpj", label: "CNPJ — 14 números" },
                              ]
                      }
                    />
                  </Field>

                  <Field
                    label={form.document_type === "cpf" ? "CPF" : "CNPJ"}
                  >
                    <TextInput
                      value={form.document}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          document: value,
                        }))
                      }
                      placeholder={
                        form.document_type === "cpf"
                          ? "000.000.000-00"
                          : "00.000.000/0000-00"
                      }
                    />
                  </Field>

                  <Field label="E-mail">
                    <TextInput
                      value={form.email}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          email: value,
                        }))
                      }
                      placeholder="contato@empresa.com.br"
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
                    />
                  </Field>

                  <OptionalTextField
                    label="Nome fantasia"
                    enabled={optionalFields.trade_name}
                    value={form.trade_name}
                    onToggle={(enabled) =>
                      toggleOptionalField("trade_name", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        trade_name: value,
                      }))
                    }
                    placeholder="Ex.: Cliente"
                  />
                </div>
              </section>

              {/* ── Contato operacional ─────────────────────────────────────── */}
              <section className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    2. Contato operacional
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Dados de contato do dia-a-dia. Para PJ, quem atende a empresa? Útil para cobranças, negociações e suporte.
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <OptionalTextField
                    label="Segundo telefone"
                    enabled={optionalFields.secondary_phone}
                    value={form.secondary_phone}
                    onToggle={(enabled) => toggleOptionalField("secondary_phone", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, secondary_phone: value }))}
                    placeholder="(11) 91234-5678"
                    helperText="Celular adicional, WhatsApp ou ramal."
                  />
                  <OptionalTextField
                    label="Site / URL"
                    enabled={optionalFields.website}
                    value={form.website}
                    onToggle={(enabled) => toggleOptionalField("website", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, website: value }))}
                    placeholder="https://exemplo.com.br"
                    helperText="Endereço do site da empresa ou perfil."
                  />
                  <OptionalTextField
                    label="Nome do contato"
                    enabled={optionalFields.contact_name}
                    value={form.contact_name}
                    onToggle={(enabled) => toggleOptionalField("contact_name", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, contact_name: value }))}
                    placeholder="Ex.: Maria da Silva"
                    helperText="Pessoa de contato: gerente, comprador, financeiro."
                  />
                  <OptionalTextField
                    label="Telefone do contato"
                    enabled={optionalFields.contact_phone}
                    value={form.contact_phone}
                    onToggle={(enabled) => toggleOptionalField("contact_phone", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, contact_phone: value }))}
                    placeholder="(11) 91234-5678"
                    helperText="Telefone direto do responsável pelo contato."
                  />
                  <OptionalTextField
                    label="E-mail do contato"
                    enabled={optionalFields.contact_email}
                    value={form.contact_email}
                    onToggle={(enabled) => toggleOptionalField("contact_email", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, contact_email: value }))}
                    placeholder="contato@empresa.com.br"
                    helperText="E-mail direto do responsável pelo contato."
                  />
                  <OptionalSelectField
                    label="Origem do cadastro"
                    enabled={optionalFields.origin}
                    value={(form.origin || "manual") as ParticipantOrigin}
                    onToggle={(enabled) => toggleOptionalField("origin", enabled)}
                    onChange={(value) => setForm((f) => ({ ...f, origin: value }))}
                    options={ORIGIN_OPTIONS}
                    helperText="Como este participante entrou no sistema."
                  />
                </div>
              </section>

              <section id="participant-section-address" className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    3. Endereço base
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Informe o CEP primeiro. Quando possível, o endereço será preenchido automaticamente.
                  </p>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <Field label="CEP">
                    <div className="flex flex-col gap-2">
                      <TextInput
                        value={form.zip_code}
                        onChange={handleZipCodeChange}
                        placeholder="17000000"
                      />

                      {cepLookupState === "loading" ? (
                        <p className="text-xs text-[var(--color-text-muted)]">
                          Consultando CEP...
                        </p>
                      ) : null}

                      {cepLookupState === "success" ? (
                        <p className="text-xs text-emerald-400">
                          Endereço preenchido automaticamente.
                        </p>
                      ) : null}
                    </div>
                  </Field>

                  <Field label="Logradouro">
                    <TextInput
                      value={form.street}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          street: value,
                        }))
                      }
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
                    />
                  </Field>

                  <Field label="UF">
                    <TextInput
                      value={form.state}
                      onChange={(value) =>
                        setForm((current) => ({
                          ...current,
                          state: value.toUpperCase().slice(0, 2),
                        }))
                      }
                    />
                  </Field>

                  <OptionalTextField
                    label="Complemento"
                    enabled={optionalFields.complement}
                    value={form.complement}
                    onToggle={(enabled) =>
                      toggleOptionalField("complement", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        complement: value,
                      }))
                    }
                    placeholder="Sala, bloco, referência..."
                  />

                  <OptionalTextField
                    label="Código IBGE"
                    enabled={optionalFields.ibge_municipality_code}
                    value={form.ibge_municipality_code}
                    onToggle={(enabled) =>
                      toggleOptionalField("ibge_municipality_code", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        ibge_municipality_code: value,
                      }))
                    }
                    placeholder="3506003"
                    helperText="Campo técnico. Se habilitado, precisa ter 7 números."
                  />
                </div>
              </section>

              <section id="participant-section-fiscal" className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    3. Dados fiscais opcionais
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Preencha somente se souber. Informação fiscal errada é pior do que informação marcada como NI.
                  </p>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <OptionalSelectField
                    label="Tipo de contribuinte"
                    enabled={optionalFields.taxpayer_type}
                    value={form.taxpayer_type}
                    onToggle={(enabled) =>
                      toggleOptionalField("taxpayer_type", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        taxpayer_type: value,
                      }))
                    }
                    options={[
                      { value: "taxpayer", label: "Contribuinte" },
                      {
                        value: "non_taxpayer",
                        label: "Não contribuinte",
                      },
                      { value: "exempt", label: "Isento" },
                      { value: "unknown", label: "NI — Não informado" },
                    ]}
                  />

                  <OptionalSelectField
                    label="Regime tributário"
                    enabled={optionalFields.tax_regime}
                    value={form.tax_regime}
                    onToggle={(enabled) =>
                      toggleOptionalField("tax_regime", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        tax_regime: value,
                      }))
                    }
                    options={TAX_REGIME_OPTIONS}
                  />

                  <OptionalTextField
                    label="CNAE principal"
                    enabled={optionalFields.main_cnae}
                    value={form.main_cnae}
                    onToggle={(enabled) =>
                      toggleOptionalField("main_cnae", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        main_cnae: value,
                      }))
                    }
                    placeholder="6201501"
                    helperText="Campo técnico. Se habilitado, precisa ter 7 números."
                  />

                  <OptionalTextField
                    label="Inscrição estadual"
                    enabled={optionalFields.state_registration}
                    value={form.state_registration}
                    onToggle={(enabled) =>
                      toggleOptionalField("state_registration", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        state_registration: value,
                      }))
                    }
                  />

                  <OptionalTextField
                    label="Inscrição municipal"
                    enabled={optionalFields.municipal_registration}
                    value={form.municipal_registration}
                    onToggle={(enabled) =>
                      toggleOptionalField("municipal_registration", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        municipal_registration: value,
                      }))
                    }
                  />

                  <OptionalTextField
                    label="Observações fiscais"
                    enabled={optionalFields.fiscal_notes}
                    value={form.fiscal_notes}
                    onToggle={(enabled) =>
                      toggleOptionalField("fiscal_notes", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        fiscal_notes: value,
                      }))
                    }
                  />
                </div>
              </section>

              <section id="participant-section-financial" className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    4. Dados financeiros opcionais
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Use para pagamentos, recebimentos, Pix, limite de crédito e conciliação futura.
                  </p>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <OptionalTextField
                    label="Banco"
                    enabled={optionalFields.bank_name}
                    value={form.bank_name}
                    onToggle={(enabled) =>
                      toggleOptionalField("bank_name", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        bank_name: value,
                      }))
                    }
                  />

                  <OptionalTextField
                    label="Agência"
                    enabled={optionalFields.bank_branch}
                    value={form.bank_branch}
                    onToggle={(enabled) =>
                      toggleOptionalField("bank_branch", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        bank_branch: value,
                      }))
                    }
                  />

                  <OptionalTextField
                    label="Conta"
                    enabled={optionalFields.bank_account}
                    value={form.bank_account}
                    onToggle={(enabled) =>
                      toggleOptionalField("bank_account", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        bank_account: value,
                      }))
                    }
                  />

                  <OptionalTextField
                    label="Chave Pix"
                    enabled={optionalFields.pix_key}
                    value={form.pix_key}
                    onToggle={(enabled) =>
                      toggleOptionalField("pix_key", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        pix_key: value,
                      }))
                    }
                  />

                  <MoneyOptionalTextField
                    label="Limite de crédito"
                    enabled={optionalFields.credit_limit}
                    value={form.credit_limit}
                    onToggle={(enabled) =>
                      toggleOptionalField("credit_limit", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        credit_limit: value,
                      }))
                    }
                    placeholder="1000.00"
                    helperText="Informe o limite financeiro do participante."
                  />

                  <OptionalTextField
                    label="Prioridade de pagamento"
                    enabled={optionalFields.payment_priority}
                    value={form.payment_priority}
                    onToggle={(enabled) =>
                      toggleOptionalField("payment_priority", enabled)
                    }
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        payment_priority: value,
                      }))
                    }
                    placeholder="normal, alta, baixa"
                  />
                </div>
              </section>

              <section id="participant-section-audit" className="scroll-mt-6 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)]/45 p-4">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-[var(--color-text)]">
                    5. Observações e auditoria
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                    Registre observações úteis e acompanhe o histórico gerado pelo backend.
                  </p>
                </div>

                <OptionalTextField
                  label="Observações internas"
                  enabled={optionalFields.notes}
                  value={form.notes}
                  onToggle={(enabled) => toggleOptionalField("notes", enabled)}
                  onChange={(value) =>
                    setForm((current) => ({
                      ...current,
                      notes: value,
                    }))
                  }
                />

                <div className="mt-5 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                  <p className="text-sm font-medium text-[var(--color-text)]">
                    Auditoria
                  </p>

                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                    Eventos carregados de{" "}
                    <code>GET /participants/:id/audit</code>.
                  </p>

                  <div className="mt-4 space-y-3">
                    {auditEvents.length === 0 ? (
                      <p className="text-sm text-[var(--color-text-muted)]">
                        Nenhum evento de auditoria carregado.
                      </p>
                    ) : (
                      auditEvents.map((event) => (
                        <div
                          key={event.id}
                          className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4"
                        >
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <p className="font-medium text-[var(--color-text)]">
                                {event.event_type}
                              </p>
                              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                                {formatDateTimeBR(event.occurred_at)}
                              </p>
                            </div>

                            <span className="w-fit rounded-full bg-[var(--color-primary-soft)] px-2 py-1 text-xs text-[var(--color-primary)]">
                              {event.source}
                            </span>
                          </div>

                          <p className="mt-3 break-all font-mono text-xs text-[var(--color-primary)]">
                            {event.id}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </section>

              <div className="flex flex-col gap-3 border-t border-[var(--color-border-soft)] pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-[var(--color-text-muted)]">
                  Ao salvar, o backend valida os dados e registra auditoria do
                  participante.
                </p>

                <button
                  type="button"
                  onClick={() => void handleSaveParticipant()}
                  disabled={actionState === "loading" || !canWriteParticipants}
                  className="rounded-xl bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {actionState === "loading"
                    ? "Salvando..."
                    : !canWriteParticipants
                      ? "Sem permissão"
                    : selectedParticipantId
                      ? "Salvar alterações"
                      : "Cadastrar participante"}
                </button>
              </div>
            </div>
            </div>
          </SectionCard>
        ) : null}
      </div>
    </section>
  )
}
