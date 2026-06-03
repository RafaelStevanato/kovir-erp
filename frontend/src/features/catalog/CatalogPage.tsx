import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import {
  CheckCircle2,
  ListFilter,
  Package,
  Plus,
  Sparkles,
  Wrench,
} from "lucide-react"

import {
  dateCell,
  exportCsv as exportCsvFile,
  exportXlsx as exportXlsxFile,
  moneyCell,
  numberCell,
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
  createCatalogItem,
  getCatalogDiagnostics,
  getCatalogItemAuditEvents,
  getCatalogItemsPage,
  getCatalogRules,
  getCatalogSummary,
  updateCatalogItem,
} from "./catalogApi"
import { getFiscalClassifications } from "../fiscalClassification/fiscalClassificationApi"
import type { FiscalClassification } from "../fiscalClassification/types"

import type {
  CatalogDiagnostics,
  CatalogItem,
  CatalogItemAuditEvent,
  CatalogItemCreatePayload,
  CatalogItemOrigin,
  CatalogItemStatus,
  CatalogSummary,
  CatalogItemType,
  CatalogRules,
} from "./types"

type LoadState = "idle" | "loading" | "success" | "error"
type CatalogView = "overview" | "form" | "list"
type SearchScope = "all" | "name" | "sku" | "barcode" | "id"
type StockFilter = "all" | "tracked" | "not_tracked"
type FiscalFilter = "all" | "with_ncm" | "with_nbs" | "without_classification"
type NcmOption = {
  ncm: string
  classificationId: string
  name: string
  label: string
}

type NbsOption = {
  nbs: string
  classificationId: string
  name: string
  label: string
}


const PAGE_SIZE = 20
const EXPORT_LIMIT = 5000

const UNIT_OPTIONS = [
  { value: "UN", label: "UN — Unidade" },
  { value: "CX", label: "CX — Caixa" },
  { value: "PC", label: "PC — Peça" },
  { value: "PAR", label: "PAR — Par" },
  { value: "KIT", label: "KIT — Kit" },
  { value: "KG", label: "KG — Quilograma" },
  { value: "G", label: "G — Grama" },
  { value: "LT", label: "LT — Litro" },
  { value: "ML", label: "ML — Mililitro" },
  { value: "M", label: "M — Metro" },
  { value: "M2", label: "M² — Metro quadrado" },
  { value: "M3", label: "M³ — Metro cúbico" },
  { value: "HORA", label: "HORA — Hora" },
  { value: "DIA", label: "DIA — Dia" },
  { value: "MES", label: "MÊS — Mês" },
  { value: "SERV", label: "SERV — Serviço" },
]

const statusOptions: CatalogItemStatus[] = [
  "draft",
  "active",
  "inactive",
  "blocked",
]

const originOptions: CatalogItemOrigin[] = [
  "manual",
  "imported",
  "integration",
  "fiscal_document",
  "unknown",
]

type CatalogFormState = {
  company_id: string
  item_type: CatalogItemType
  name: string
  description: string
  sku: string
  barcode: string
  unit: string
  status: CatalogItemStatus
  brand: string
  category: string
  default_sale_price: string
  default_cost_price: string
  ncm: string
  nbs: string
  track_stock: boolean
  stock_unit: string
  minimum_stock: string
  allow_negative_stock: boolean
  notes: string
}

function getSessionCompanyId() {
  return getAuthSession()?.companyId ?? ""
}

function createInitialFormState(companyId = getSessionCompanyId() || getActiveCompanyId()): CatalogFormState {
  return {
    company_id: companyId,
    item_type: "product",
    name: "",
    description: "",
    sku: "",
    barcode: "",
    unit: "UN",
    status: "active",
    brand: "",
    category: "",
    default_sale_price: "",
    default_cost_price: "",
    ncm: "",
    nbs: "",
    track_stock: false,
    stock_unit: "UN",
    minimum_stock: "",
    allow_negative_stock: false,
    notes: "",
  }
}

function cleanOptional(value: string) {
  const cleaned = value.trim()

  return cleaned === "" ? null : cleaned
}

function onlyDigitsOrNull(value: string) {
  const digits = value.replace(/\D/g, "")

  return digits === "" ? null : digits
}

function formatCurrency(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "sem valor"
  }

  const numberValue =
    typeof value === "number" ? value : Number(String(value).replace(",", "."))

  if (Number.isNaN(numberValue)) {
    return "sem valor"
  }

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(numberValue)
}

function parseNumber(value: string) {
  const cleaned = value.trim().replace(",", ".")

  if (cleaned === "") return null

  const parsed = Number(cleaned)

  return Number.isFinite(parsed) ? parsed : null
}

function isValidSearchFilterInput(value: string, scope: SearchScope) {
  if (value === "") return true

  const validators: Record<SearchScope, RegExp> = {
    all: /^[\p{L}\p{N}\s._/@\-&]+$/u,
    name: /^[\p{L}\p{N}\s.'\-&]+$/u,
    sku: /^[A-Za-z0-9._/\-\s]+$/,
    barcode: /^\d+$/,
    id: /^[A-Za-z0-9_-]+$/,
  }

  return validators[scope].test(value)
}



function formatDateTimeBR(value: string | null) {
  if (!value) return "Sem data"

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date)
}

function getItemTypeLabel(value: CatalogItemType) {
  const labels: Record<CatalogItemType, string> = {
    product: "Produto",
    service: "Serviço",
  }

  return labels[value]
}

function getStatusLabel(value: CatalogItemStatus) {
  const labels: Record<CatalogItemStatus, string> = {
    draft: "Rascunho",
    active: "Ativo",
    inactive: "Inativo",
    blocked: "Bloqueado",
  }

  return labels[value]
}

function getOriginLabel(value: CatalogItemOrigin) {
  const labels: Record<CatalogItemOrigin, string> = {
    manual: "Manual",
    imported: "Importado",
    integration: "Integração",
    fiscal_document: "Documento fiscal",
    unknown: "Desconhecido",
  }

  return labels[value]
}

function getStatusClass(value: CatalogItemStatus) {
  if (value === "active") {
    return "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
  }

  if (value === "blocked") {
    return "border-red-500/30 bg-red-500/10 text-red-500"
  }

  if (value === "inactive") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-500"
  }

  return "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)]"
}

function parseIsoDateValue(value: string | null | undefined) {
  if (!value) return 0

  const parsed = Date.parse(value)

  return Number.isFinite(parsed) ? parsed : 0
}

function pickPreferredNcmClassification(
  current: FiscalClassification,
  next: FiscalClassification,
) {
  const statusRank = (value: string) => {
    if (value === "active") return 0
    if (value === "draft") return 1
    return 2
  }

  const currentRank = statusRank(current.status)
  const nextRank = statusRank(next.status)

  if (nextRank < currentRank) return next
  if (nextRank > currentRank) return current

  const currentUpdated = parseIsoDateValue(current.updated_at)
  const nextUpdated = parseIsoDateValue(next.updated_at)

  return nextUpdated > currentUpdated ? next : current
}

function buildNbsOptions(classifications: FiscalClassification[]): NbsOption[] {
  const allowedItemTypes = new Set(["service", "both"])
  const allowedStatuses = new Set(["active", "draft"])
  const groupedByNbs = new Map<string, FiscalClassification>()

  classifications.forEach((classification) => {
    const nbs = classification.nbs?.trim()

    if (!nbs) return
    if (!allowedItemTypes.has(classification.item_type)) return
    if (!allowedStatuses.has(classification.status)) return

    const existing = groupedByNbs.get(nbs)

    if (!existing) {
      groupedByNbs.set(nbs, classification)
      return
    }

    groupedByNbs.set(nbs, pickPreferredNcmClassification(existing, classification))
  })

  return [...groupedByNbs.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([nbs, classification]) => ({
      nbs,
      classificationId: classification.id,
      name: classification.name,
      label: `${nbs} — ${classification.name}`,
    }))
}

function buildNcmOptions(classifications: FiscalClassification[]): NcmOption[] {
  const allowedItemTypes = new Set(["product", "both"])
  const allowedStatuses = new Set(["active", "draft"])
  const groupedByNcm = new Map<string, FiscalClassification>()

  classifications.forEach((classification) => {
    const ncm = classification.ncm?.trim()

    if (!ncm) return
    if (!allowedItemTypes.has(classification.item_type)) return
    if (!allowedStatuses.has(classification.status)) return

    const existing = groupedByNcm.get(ncm)

    if (!existing) {
      groupedByNcm.set(ncm, classification)
      return
    }

    groupedByNcm.set(ncm, pickPreferredNcmClassification(existing, classification))
  })

  return [...groupedByNcm.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([ncm, classification]) => ({
      ncm,
      classificationId: classification.id,
      name: classification.name,
      label: `${ncm} — ${classification.name}`,
    }))
}

function buildPayload(form: CatalogFormState): CatalogItemCreatePayload {
  const isService = form.item_type === "service"

  return {
    company_id: form.company_id,
    item_type: form.item_type,
    name: form.name.trim(),
    description: cleanOptional(form.description),
    sku: cleanOptional(form.sku),
    barcode: cleanOptional(form.barcode),
    unit: form.unit,
    status: form.status,
    origin: "manual",
    brand: cleanOptional(form.brand),
    category: cleanOptional(form.category),
    financial_settings: {
      default_sale_price: cleanOptional(form.default_sale_price),
      default_cost_price: cleanOptional(form.default_cost_price),
      allow_price_override: true,
      default_revenue_account_id: null,
      default_expense_account_id: null,
      default_cost_center_id: null,
    },
    fiscal_settings: {
      ncm: isService ? null : onlyDigitsOrNull(form.ncm),
      nbs: isService ? onlyDigitsOrNull(form.nbs) : null,
      cest: null,
      cfop_default: null,
      cst_icms: null,
      cst_pis: null,
      cst_cofins: null,
      cst_ibs_cbs: null,
      cclass_trib: null,
      subject_to_tax: true,
      fiscal_notes: null,
    },
    inventory_settings: {
      track_stock: isService ? false : form.track_stock,
      stock_unit: isService ? null : cleanOptional(form.stock_unit),
      minimum_stock: isService ? null : cleanOptional(form.minimum_stock),
      allow_negative_stock: isService ? false : form.allow_negative_stock,
    },
    notes: cleanOptional(form.notes),
  }
}

function formFromItem(item: CatalogItem): CatalogFormState {
  return {
    company_id: item.company_id,
    item_type: item.item_type,
    name: item.name,
    description: item.description ?? "",
    sku: item.sku ?? "",
    barcode: item.barcode ?? "",
    unit: item.unit,
    status: item.status,
    brand: item.brand ?? "",
    category: item.category ?? "",
    default_sale_price: item.financial_settings?.default_sale_price ?? "",
    default_cost_price: item.financial_settings?.default_cost_price ?? "",
    ncm: item.fiscal_settings?.ncm ?? "",
    nbs: item.fiscal_settings?.nbs ?? "",
    track_stock: item.inventory_settings?.track_stock ?? false,
    stock_unit: item.inventory_settings?.stock_unit ?? "UN",
    minimum_stock: item.inventory_settings?.minimum_stock ?? "",
    allow_negative_stock: item.inventory_settings?.allow_negative_stock ?? false,
    notes: item.notes ?? "",
  }
}

function buildExportRows(items: CatalogItem[]): ExportTable {
  return [
    [
      "ID",
      "Empresa",
      "Tipo",
      "Nome",
      "Status",
      "Origem",
      "Marca",
      "Categoria",
      "SKU",
      "Código de barras",
      "Unidade",
      "Preço de venda",
      "Custo padrão",
      "NCM",
      "NBS",
      "Classificação fiscal",
      "CFOP padrão",
      "Controla estoque",
      "Unidade estoque",
      "Estoque mínimo",
      "Criado em",
      "Atualizado em",
    ],
    ...items.map((item) => [
      item.id,
      item.company_id,
      getItemTypeLabel(item.item_type),
      item.name,
      getStatusLabel(item.status),
      getOriginLabel(item.origin),
      item.brand ?? "",
      item.category ?? "",
      item.sku ?? "",
      item.barcode ?? "",
      item.unit,
      moneyCell(item.financial_settings?.default_sale_price ?? ""),
      moneyCell(item.financial_settings?.default_cost_price ?? ""),
      item.fiscal_settings?.ncm ?? "",
      item.fiscal_settings?.nbs ?? "",
      item.fiscal_settings?.fiscal_classification_name ?? "",
      item.fiscal_settings?.cfop_default ?? "",
      item.inventory_settings?.track_stock ? "Sim" : "Não",
      item.inventory_settings?.stock_unit ?? "",
      numberCell(item.inventory_settings?.minimum_stock ?? ""),
      dateCell(item.created_at ?? ""),
      dateCell(item.updated_at ?? ""),
    ]),
  ]
}

function exportCsv(items: CatalogItem[]) {
  const stamp = new Date().toISOString().slice(0, 10)
  exportCsvFile(buildExportRows(items), `catalogo_filtrado_${stamp}.csv`)
}

async function exportXlsx(items: CatalogItem[]) {
  exportXlsxFile(
    buildExportRows(items),
    "Catálogo",
    `catalogo_filtrado_${new Date().toISOString().slice(0, 10)}.xlsx`,
  )
}

function catalogTabClass(active: boolean) {
  return [
    "inline-flex items-center gap-1.5 rounded-2xl border px-5 py-2.5 text-sm font-bold transition duration-200",
    active
      ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
      : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)]",
  ].join(" ")
}

function StatCard({
  accent,
  icon,
  label,
  value,
  hint,
}: {
  accent: string
  icon: ReactNode
  label: string
  value: number
  hint: string
}) {
  return (
    <div
      className="relative overflow-hidden rounded-2xl p-4"
      style={{ background: accent, border: `1px solid ${accent}` }}
    >
      <div className="flex items-center justify-between gap-2">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-xl"
          style={{ background: "rgba(255,255,255,0.18)", border: "1px solid rgba(255,255,255,0.28)", color: "white" }}
        >
          {icon}
        </div>
      </div>
      <p className="mt-3 text-2xl font-black text-white">{value}</p>
      <p className="text-xs uppercase tracking-wide text-white/75">{label}</p>
      {hint && <p className="mt-1 text-xs text-white/65">{hint}</p>}
    </div>
  )
}

export function CatalogPage() {
  const [view, setView] = useState<CatalogView>("overview")
  const [loadState, setLoadState] = useState<LoadState>("idle")
  const [saveState, setSaveState] = useState<LoadState>("idle")
  const [exportState, setExportState] = useState<LoadState>("idle")
  const [modalMessage, setModalMessage] = useState<string | null>(null)
  const [items, setItems] = useState<CatalogItem[]>([])
  const [totalItems, setTotalItems] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [summary, setSummary] = useState<CatalogSummary | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [, setRules] = useState<CatalogRules | null>(null)
  const [, setDiagnostics] = useState<CatalogDiagnostics | null>(null)
  const [auditEvents, setAuditEvents] = useState<CatalogItemAuditEvent[]>([])
  const [ncmOptionsState, setNcmOptionsState] = useState<LoadState>("idle")
  const [ncmOptions, setNcmOptions] = useState<NcmOption[]>([])
  const [nbsOptions, setNbsOptions] = useState<NbsOption[]>([])
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const sessionCompanyId = getSessionCompanyId()
  const [activeCompanyId, setActiveCompanyIdState] = useState(() => sessionCompanyId || getActiveCompanyId())
  const [form, setForm] = useState<CatalogFormState>(() =>
    createInitialFormState(sessionCompanyId || getActiveCompanyId()),
  )

  const [search, setSearch] = useState("")
  const [searchScope, setSearchScope] = useState<SearchScope>("all")
  const [typeFilter, setTypeFilter] = useState<CatalogItemType | "all">("all")
  const [statusFilter, setStatusFilter] = useState<CatalogItemStatus | "all">(
    "all",
  )
  const [originFilter, setOriginFilter] = useState<CatalogItemOrigin | "all">(
    "all",
  )
  const [unitFilter, setUnitFilter] = useState("all")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [stockFilter, setStockFilter] = useState<StockFilter>("all")
  const [fiscalFilter, setFiscalFilter] = useState<FiscalFilter>("all")
  const [minSalePrice, setMinSalePrice] = useState("")
  const [maxSalePrice, setMaxSalePrice] = useState("")
  const [minCostPrice, setMinCostPrice] = useState("")
  const [maxCostPrice, setMaxCostPrice] = useState("")

  const activeCompany = useMemo(
    () => companies.find((company) => company.id === activeCompanyId) ?? null,
    [activeCompanyId, companies],
  )

  const activeCompanyName = getCompanyDisplayName(activeCompany)
  const session = getAuthSession()
  const canWriteCatalog = Boolean(
    session?.roles.includes("admin") || session?.permissions.includes("catalog.write"),
  )

  const filteredItems = items

  const productCount = summary?.product_count ?? 0
  const serviceCount = summary?.service_count ?? 0
  const activeCount = summary?.active_count ?? 0

  const filtersAppliedCount = useMemo(() => {
    return [
      search.trim() !== "",
      searchScope !== "all",
      typeFilter !== "all",
      statusFilter !== "all",
      originFilter !== "all",
      unitFilter !== "all",
      categoryFilter.trim() !== "",
      stockFilter !== "all",
      fiscalFilter !== "all",
      minSalePrice.trim() !== "",
      maxSalePrice.trim() !== "",
      minCostPrice.trim() !== "",
      maxCostPrice.trim() !== "",
    ].filter(Boolean).length
  }, [
    categoryFilter,
    fiscalFilter,
    maxCostPrice,
    maxSalePrice,
    minCostPrice,
    minSalePrice,
    originFilter,
    search,
    searchScope,
    statusFilter,
    stockFilter,
    typeFilter,
    unitFilter,
  ])

  const loadNcmOptions = useCallback(async (companyId: string) => {
    setNcmOptionsState("loading")

    try {
      const validOn = new Date().toISOString().slice(0, 10)
      const withValidityResponse = await getFiscalClassifications({
        company_id: companyId,
        valid_on: validOn,
        limit: 5000,
      })

      let classifications = withValidityResponse.data.items

      if (classifications.length === 0) {
        const fallbackResponse = await getFiscalClassifications({
          company_id: companyId,
          limit: 5000,
        })
        classifications = fallbackResponse.data.items
      }

      setNcmOptions(buildNcmOptions(classifications))
      setNbsOptions(buildNbsOptions(classifications))
      setNcmOptionsState("success")
    } catch {
      setNcmOptions([])
      setNbsOptions([])
      setNcmOptionsState("error")
    }
  }, [])

  const loadCatalogBase = useCallback(async () => {
    try {
      const [companiesResponse, rulesResponse, diagnosticsResponse] =
        await Promise.all([getCompanies(), getCatalogRules(), getCatalogDiagnostics()])

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
      setDiagnostics(diagnosticsResponse.data)

      if (resolvedCompanyId !== activeCompanyId) {
        setActiveCompanyIdState(resolvedCompanyId)
      }

      setForm((current) => ({
        ...current,
        company_id: resolvedCompanyId,
      }))

      if (visibleCompanies.length === 0 || !resolvedCompanyId) {
        setItems([])
        setTotalItems(0)
        setSummary(null)
        setNcmOptions([])
        setNbsOptions([])
        setNcmOptionsState("success")
        setLoadState("success")
        return
      }

      const summaryResponse = await getCatalogSummary(resolvedCompanyId)
      setSummary(summaryResponse.data)
      await loadNcmOptions(resolvedCompanyId)
    } catch (error) {
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro ao carregar dados base do cat?logo.",
      )
      setLoadState("error")
    }
  }, [activeCompanyId, loadNcmOptions, sessionCompanyId])

  const catalogQuery = useMemo(() => ({
    company_id: activeCompanyId,
    item_type: typeFilter === "all" ? undefined : typeFilter,
    status: statusFilter === "all" ? undefined : statusFilter,
    origin: originFilter === "all" ? undefined : originFilter,
    unit: unitFilter === "all" ? undefined : unitFilter,
    category: categoryFilter.trim() || undefined,
    search: debouncedSearch.trim() || undefined,
    search_scope: searchScope,
    stock_filter: stockFilter === "all" ? undefined : stockFilter,
    fiscal_filter: fiscalFilter === "all" ? undefined : fiscalFilter,
    min_sale_price: minSalePrice.trim() || undefined,
    max_sale_price: maxSalePrice.trim() || undefined,
    min_cost_price: minCostPrice.trim() || undefined,
    max_cost_price: maxCostPrice.trim() || undefined,
  }), [
    activeCompanyId,
    categoryFilter,
    debouncedSearch,
    fiscalFilter,
    maxCostPrice,
    maxSalePrice,
    minCostPrice,
    minSalePrice,
    originFilter,
    searchScope,
    statusFilter,
    stockFilter,
    typeFilter,
    unitFilter,
  ])

  const loadCatalogItems = useCallback(async () => {
    if (!activeCompanyId) {
      setItems([])
      setTotalItems(0)
      setLoadState("success")
      return
    }

    setLoadState("loading")

    try {
      const response = await getCatalogItemsPage({
        ...catalogQuery,
        limit: PAGE_SIZE,
        offset: (currentPage - 1) * PAGE_SIZE,
      })

      setItems(response.data.items)
      setTotalItems(response.data.total)
      setLoadState("success")
    } catch (error) {
      setItems([])
      setTotalItems(0)
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Erro ao carregar cat?logo.",
      )
      setLoadState("error")
    }
  }, [activeCompanyId, catalogQuery, currentPage])

  const refreshCatalog = useCallback(async () => {
    await loadCatalogBase()
    await loadCatalogItems()
  }, [loadCatalogBase, loadCatalogItems])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearch(search.trim())
    }, 350)

    return () => window.clearTimeout(timeout)
  }, [search])

  useEffect(() => {
    setCurrentPage(1)
  }, [
    categoryFilter,
    debouncedSearch,
    fiscalFilter,
    maxCostPrice,
    maxSalePrice,
    minCostPrice,
    minSalePrice,
    originFilter,
    searchScope,
    statusFilter,
    stockFilter,
    typeFilter,
    unitFilter,
  ])

  useEffect(() => {
    void loadCatalogBase()
  }, [loadCatalogBase])

  useEffect(() => {
    void loadCatalogItems()
  }, [loadCatalogItems])

  function resetFilters() {
    setCurrentPage(1)
    setSearch("")
    setSearchScope("all")
    setTypeFilter("all")
    setStatusFilter("all")
    setOriginFilter("all")
    setUnitFilter("all")
    setCategoryFilter("")
    setStockFilter("all")
    setFiscalFilter("all")
    setMinSalePrice("")
    setMaxSalePrice("")
    setMinCostPrice("")
    setMaxCostPrice("")
  }

  function openNewItem(itemType: CatalogItemType = "product") {
    if (!canWriteCatalog) {
      setModalMessage("Você não tem permissão catalog.write para criar ou alterar itens.")
      return
    }
    setEditingItemId(null)
    setAuditEvents([])
    setForm({
      ...createInitialFormState(activeCompanyId),
      item_type: itemType,
      unit: itemType === "service" ? "HORA" : "UN",
      track_stock: false,
      stock_unit: itemType === "service" ? "" : "UN",
    })
    setView("form")
  }

  async function openEditItem(item: CatalogItem) {
    setEditingItemId(item.id)
    setForm(formFromItem(item))
    setView("form")

    try {
      const response = await getCatalogItemAuditEvents(item.id)
      setAuditEvents(response.data)
    } catch {
      setAuditEvents([])
    }
  }

  function validateForm() {
    if (form.company_id.trim() === "") {
      return "Informe o ID da empresa."
    }

    if (!form.company_id.startsWith("emp_")) {
      return "O ID da empresa precisa começar com emp_."
    }

    if (form.name.trim().length < 2) {
      return "Informe o nome do item com pelo menos 2 caracteres."
    }

    if (form.unit.trim() === "") {
      return "Selecione a unidade do item."
    }

    if (!UNIT_OPTIONS.some((option) => option.value === form.unit)) {
      return "Selecione uma unidade válida na lista."
    }

    if (form.default_sale_price.trim() !== "" && parseNumber(form.default_sale_price) === null) {
      return "Preço de venda deve ser numérico."
    }

    if (form.default_cost_price.trim() !== "" && parseNumber(form.default_cost_price) === null) {
      return "Custo padrão deve ser numérico."
    }

    if (form.item_type === "product") {
      if (ncmOptions.length === 0) {
        return "Cadastre ao menos um NCM na aba Fiscal antes de criar produto."
      }

      if (form.ncm.trim() === "") {
        return "Selecione um NCM do Fiscal para salvar o produto."
      }

      const selectedNcm = onlyDigitsOrNull(form.ncm)

      if (!selectedNcm || selectedNcm.length !== 8) {
        return "NCM deve conter 8 digitos."
      }

      if (!ncmOptions.some((option) => option.ncm === selectedNcm)) {
        return "NCM invalido para esta empresa. Escolha um NCM cadastrado na aba Fiscal."
      }
    }

    if (form.item_type === "product" && form.ncm.trim() !== "") {
      const ncm = onlyDigitsOrNull(form.ncm)

      if (!ncm || ncm.length !== 8) {
        return "NCM deve conter 8 dígitos."
      }
    }

    if (form.item_type === "service" && form.nbs.trim() !== "") {
      const nbs = onlyDigitsOrNull(form.nbs)

      if (!nbs || nbs.length !== 9) {
        return "NBS deve conter 9 dígitos."
      }
    }

    if (form.item_type === "product" && form.track_stock && form.stock_unit.trim() === "") {
      return "Produto com controle de estoque precisa de unidade de estoque."
    }

    if (
      form.item_type === "product" &&
      form.track_stock &&
      form.minimum_stock.trim() !== "" &&
      parseNumber(form.minimum_stock) === null
    ) {
      return "Estoque mínimo deve ser numérico."
    }

    if (form.item_type === "product" && form.nbs.trim() !== "") {
      return "Produto não deve usar NBS. Use NCM."
    }

    if (form.item_type === "service" && form.ncm.trim() !== "") {
      return "Serviço não deve usar NCM. Use NBS."
    }

    return null
  }

  async function handleSave() {
    if (!canWriteCatalog) {
      setModalMessage("Você não tem permissão catalog.write para salvar itens.")
      return
    }

    const validationError = validateForm()

    if (validationError) {
      setModalMessage(validationError)
      return
    }

    setSaveState("loading")

    try {
      const payload = buildPayload(form)

      if (editingItemId) {
        const { company_id: _companyId, ...updatePayload } = payload
        void _companyId
        await updateCatalogItem(editingItemId, updatePayload)
      } else {
        await createCatalogItem(payload)
      }

      setSaveState("success")
      setView("list")
      await refreshCatalog()
    } catch (error) {
      setModalMessage(
        error instanceof Error ? error.message : "Erro ao salvar item.",
      )
      setSaveState("error")
    }
  }

  async function fetchExportItems() {
    if (totalItems === 0) {
      throw new Error("N?o h? itens filtrados para exportar.")
    }

    if (totalItems > EXPORT_LIMIT) {
      throw new Error(`Refine os filtros para exportar at? ${EXPORT_LIMIT} itens por arquivo.`)
    }

    const response = await getCatalogItemsPage({
      ...catalogQuery,
      limit: EXPORT_LIMIT,
      offset: 0,
    })

    return response.data.items
  }

  async function handleExportCsv() {
    setExportState("loading")

    try {
      exportCsv(await fetchExportItems())
      setExportState("success")
    } catch (error) {
      setModalMessage(
        error instanceof Error ? error.message : "Erro ao exportar CSV.",
      )
      setExportState("error")
    }
  }

  async function handleExportXlsx() {
    setExportState("loading")

    try {
      await exportXlsx(await fetchExportItems())
      setExportState("success")
    } catch (error) {
      setModalMessage(
        error instanceof Error ? error.message : "Erro ao exportar XLSX.",
      )
      setExportState("error")
    }
  }
  return (
    <section className="space-y-5">
      <ValidationModal
        message={modalMessage}
        onClose={() => setModalMessage(null)}
      />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)]">
        {/* Ambient orbs */}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="absolute -bottom-28 -left-28 h-72 w-72 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(16,185,129,0.22) 0%, transparent 70%)", filter: "blur(52px)" }} />
          <div className="absolute -top-24 right-0 h-64 w-64 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(56,189,248,0.14) 0%, transparent 70%)", filter: "blur(52px)" }} />
          <div className="absolute bottom-0 right-1/3 h-48 w-48 rounded-full"
            style={{ background: "radial-gradient(circle, rgba(99,88,215,0.10) 0%, transparent 70%)", filter: "blur(44px)" }} />
          {/* Dot grid */}
          <div className="absolute inset-0 opacity-[0.035]"
            style={{ backgroundImage: "radial-gradient(circle, var(--color-primary) 1px, transparent 1px)", backgroundSize: "28px 28px" }} />
        </div>

        {/* Content */}
        <div className="relative flex flex-wrap items-center justify-between gap-6 p-7 sm:p-10">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-black tracking-[0.28em] uppercase text-[var(--color-text-weak)]">
              Bloco 3 — Cadastros
            </p>
            <h1 className="mt-1.5 text-3xl font-black sm:text-4xl text-[var(--color-text)]">
              Produtos e Serviços
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--color-text-muted)]">
              Cadastre o item uma vez e use em vendas, estoque, fiscal e relatórios.
              O dado certo aqui evita erro em todos os outros módulos.
            </p>
            {/* CTA buttons inside hero */}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => openNewItem("product")}
                disabled={!canWriteCatalog}
                className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-2.5 text-sm font-black text-white shadow-lg shadow-emerald-500/20 transition duration-200 hover:-translate-y-0.5 hover:bg-[var(--color-primary-hover)] active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                Novo produto
              </button>
              <button
                type="button"
                onClick={() => openNewItem("service")}
                disabled={!canWriteCatalog}
                className="inline-flex items-center gap-2 rounded-2xl border border-blue-600 bg-blue-600 px-5 py-2.5 text-sm font-black text-white shadow-lg transition duration-200 hover:-translate-y-0.5 hover:bg-blue-700 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                Novo serviço
              </button>
              <button
                type="button"
                onClick={() => { setView("list"); void refreshCatalog() }}
                className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-2.5 text-sm font-bold text-[var(--color-text-muted)] transition duration-200 hover:-translate-y-0.5 hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
              >
                <ListFilter className="h-4 w-4" />
                Ver listagem
              </button>
            </div>
          </div>

          {/* Accent pills + load state indicator */}
          <div className="flex flex-col items-end gap-3 shrink-0">
            <div className="flex items-center gap-2">
              {(["#10b981", "#38bdf8", "#6358d7"] as const).map((color, i) => (
                <div key={i} className="h-2 rounded-full" style={{ width: i === 0 ? 32 : i === 1 ? 22 : 14, background: color, opacity: 0.5 }} />
              ))}
            </div>
            {loadState === "loading" && (
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-weak)]">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                Carregando...
              </span>
            )}
            {loadState === "success" && (
              <span className="text-xs font-semibold text-[var(--color-text-weak)]">
                {totalItems} itens · {activeCount} ativos
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Summary cards ─────────────────────────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard accent="#16a34a" icon={<ListFilter className="h-4 w-4" />} label="Itens encontrados" value={totalItems} hint={filtersAppliedCount > 0 ? `${filtersAppliedCount} filtro(s) ativo(s)` : "Todos os itens"} />
        <StatCard accent="#d97706" icon={<Package className="h-4 w-4" />} label="Produtos" value={productCount} hint="Itens físicos com estoque" />
        <StatCard accent="#2563eb" icon={<Wrench className="h-4 w-4" />} label="Serviços" value={serviceCount} hint="Sem movimentação de estoque" />
        <StatCard accent="#7c3aed" icon={<CheckCircle2 className="h-4 w-4" />} label="Ativos" value={activeCount} hint="Disponíveis para operação" />
      </div>

      {/* ── Tab navigation ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setView("overview")} className={catalogTabClass(view === "overview")}>
          <Sparkles className="h-3.5 w-3.5" />
          Visão geral
        </button>
        <button type="button" onClick={() => { setView("list"); void refreshCatalog() }} className={catalogTabClass(view === "list")}>
          <ListFilter className="h-3.5 w-3.5" />
          Listagem
        </button>
      </div>

      {view === "overview" ? (
        <OverviewPanel
          summary={summary}
          canWrite={canWriteCatalog}
          onNewProduct={() => openNewItem("product")}
          onNewService={() => openNewItem("service")}
          onOpenList={() => setView("list")}
          onReload={refreshCatalog}
        />
      ) : view === "list" ? (
        <ListPanel
          items={filteredItems}
          allItemsCount={totalItems}
          currentPage={currentPage}
          loadState={loadState}
          search={search}
          searchScope={searchScope}
          typeFilter={typeFilter}
          statusFilter={statusFilter}
          originFilter={originFilter}
          unitFilter={unitFilter}
          stockFilter={stockFilter}
          fiscalFilter={fiscalFilter}
          minSalePrice={minSalePrice}
          maxSalePrice={maxSalePrice}
          minCostPrice={minCostPrice}
          maxCostPrice={maxCostPrice}
          filtersAppliedCount={filtersAppliedCount}
          exportState={exportState}
          onSearchChange={setSearch}
          onSearchScopeChange={setSearchScope}
          onTypeFilterChange={setTypeFilter}
          onStatusFilterChange={setStatusFilter}
          onOriginFilterChange={setOriginFilter}
          onUnitFilterChange={setUnitFilter}
          categoryFilter={categoryFilter}
          onCategoryFilterChange={setCategoryFilter}
          onStockFilterChange={setStockFilter}
          onFiscalFilterChange={setFiscalFilter}
          onMinSalePriceChange={setMinSalePrice}
          onMaxSalePriceChange={setMaxSalePrice}
          onMinCostPriceChange={setMinCostPrice}
          onMaxCostPriceChange={setMaxCostPrice}
          onResetFilters={resetFilters}
          onReload={refreshCatalog}
          onPageChange={setCurrentPage}
          onEdit={openEditItem}
          onExportCsv={handleExportCsv}
          onExportXlsx={handleExportXlsx}
        />
      ) : (
        <FormPanel
          form={form}
          saveState={saveState}
          editingItemId={editingItemId}
          auditEvents={auditEvents}
          ncmOptions={ncmOptions}
          nbsOptions={nbsOptions}
          ncmOptionsState={ncmOptionsState}
          activeCompanyName={activeCompanyName}
          canWrite={canWriteCatalog}
          onChange={setForm}
          onSave={handleSave}
          onCancel={() => setView("list")}
        />
      )}
    </section>
  )
}

function OverviewPanel({
  summary,
  canWrite,
  onNewProduct,
  onNewService,
  onOpenList,
  onReload,
}: {
  summary: CatalogSummary | null
  canWrite: boolean
  onNewProduct: () => void
  onNewService: () => void
  onOpenList: () => void
  onReload: () => Promise<void>
}) {
  const totalItems = summary?.total_items ?? 0
  const productCount = summary?.product_count ?? 0
  const serviceCount = summary?.service_count ?? 0
  const withoutSalePrice = summary?.without_sale_price ?? 0
  const withoutCostPrice = summary?.without_cost_price ?? 0
  const withoutFiscalCode = summary?.without_fiscal_code ?? 0
  const withoutCategory = summary?.without_category ?? 0
  const stockTracked = summary?.stock_tracked ?? 0
  const readyForOperation = summary?.ready_for_operation ?? 0
  const readinessPercent = totalItems > 0
    ? Math.round((readyForOperation / totalItems) * 100)
    : 0

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="overflow-hidden rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
          <div className="border-b border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-6">
            <h2 className="text-xl font-bold text-[var(--color-text)]">
              Produtos e Serviços
            </h2>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              Gerencie o catálogo de itens utilizados em vendas, compras e documentos fiscais.
            </p>
          </div>

          <div className="grid gap-3 p-6 md:grid-cols-2 xl:grid-cols-4">
            <GuidedStepCard step="1" title="Tipo" text="Produto (físico) ou Serviço (não físico)" />
            <GuidedStepCard step="2" title="Identificação" text="Nome, unidade, SKU e código de barras" />
            <GuidedStepCard step="3" title="Preço e custo" text="Preço de venda e custo padrão" />
            <GuidedStepCard step="4" title="Fiscal e estoque" text="NCM (produto) ou NBS (serviço)" />
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-[var(--color-text-weak)]">
                Saúde do cadastro
              </p>
              <h2 className="mt-2 text-xl font-bold text-[var(--color-text)]">
                {readinessPercent}% ativos com preço
              </h2>
            </div>
            <button
              type="button"
              onClick={() => void onReload()}
              className="rounded-2xl border border-[var(--color-border-soft)] px-3 py-2 text-xs font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            >
              Atualizar
            </button>
          </div>

          <div className="mt-5 space-y-3">
            <QualityLine
              label="Ativos com preço"
              value={`${readyForOperation} de ${totalItems}`}
              tone={readyForOperation === totalItems && totalItems > 0 ? "good" : "attention"}
            />
            <QualityLine
              label="Sem preço de venda"
              value={withoutSalePrice}
              tone={withoutSalePrice === 0 ? "good" : "attention"}
            />
            <QualityLine
              label="Sem custo padrão"
              value={withoutCostPrice}
              tone={withoutCostPrice === 0 ? "good" : "attention"}
            />
            <QualityLine
              label="Sem NCM/NBS"
              value={withoutFiscalCode}
              tone={withoutFiscalCode === 0 ? "good" : "attention"}
            />
            <QualityLine
              label="Sem categoria"
              value={withoutCategory}
              tone={withoutCategory === 0 ? "good" : "attention"}
            />
            <QualityLine
              label="Com controle de estoque"
              value={stockTracked}
              tone="neutral"
            />
          </div>

          <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <button
              type="button"
              onClick={onNewProduct}
              disabled={!canWrite}
              className="rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-3 text-sm font-extrabold text-white shadow-lg shadow-emerald-500/10 transition hover:-translate-y-0.5 hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Novo produto
            </button>
            <button
              type="button"
              onClick={onNewService}
              disabled={!canWrite}
              className="rounded-2xl border border-blue-600 bg-blue-600 px-4 py-3 text-sm font-extrabold text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Novo serviço
            </button>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text)]">
              Resumo do catálogo
            </h2>
          </div>
          <button
            type="button"
            onClick={onOpenList}
            className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2.5 text-sm font-semibold text-[var(--color-primary)]"
          >
            Ver listagem
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <MiniMetric label="Total cadastrado" value={totalItems} />
          <MiniMetric label="Produtos" value={productCount} />
          <MiniMetric label="Serviços" value={serviceCount} />
        </div>
      </div>
    </div>
  )
}

function GuidedStepCard({
  step,
  title,
  text,
}: {
  step: string
  title: string
  text: string
}) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-xs font-black text-[var(--color-primary)]">
          {step}
        </div>
        <h3 className="font-semibold text-[var(--color-text)]">{title}</h3>
      </div>
      <p className="mt-2 text-xs text-[var(--color-text-weak)]">{text}</p>
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-[var(--color-text-weak)]">
        {label}
      </p>
      <p className="mt-2 text-2xl font-bold text-[var(--color-text)]">
        {value}
      </p>
    </div>
  )
}

function QualityLine({
  label,
  value,
  tone,
}: {
  label: string
  value: string | number
  tone: "good" | "attention" | "neutral"
}) {
  const toneClass =
    tone === "good"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
      : tone === "attention"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-500"
        : "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text-muted)]"

  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <span className={`rounded-full border px-3 py-1 text-xs font-bold ${toneClass}`}>
        {value}
      </span>
    </div>
  )
}

function ListPanel({
  items,
  allItemsCount,
  currentPage,
  loadState,
  search,
  searchScope,
  typeFilter,
  statusFilter,
  originFilter,
  unitFilter,
  stockFilter,
  fiscalFilter,
  minSalePrice,
  maxSalePrice,
  minCostPrice,
  maxCostPrice,
  filtersAppliedCount,
  exportState,
  onSearchChange,
  onSearchScopeChange,
  onTypeFilterChange,
  onStatusFilterChange,
  onOriginFilterChange,
  onUnitFilterChange,
  categoryFilter,
  onCategoryFilterChange,
  onStockFilterChange,
  onFiscalFilterChange,
  onMinSalePriceChange,
  onMaxSalePriceChange,
  onMinCostPriceChange,
  onMaxCostPriceChange,
  onResetFilters,
  onReload,
  onPageChange,
  onEdit,
  onExportCsv,
  onExportXlsx,
}: {
  items: CatalogItem[]
  allItemsCount: number
  currentPage: number
  loadState: LoadState
  search: string
  searchScope: SearchScope
  typeFilter: CatalogItemType | "all"
  statusFilter: CatalogItemStatus | "all"
  originFilter: CatalogItemOrigin | "all"
  unitFilter: string
  categoryFilter: string
  stockFilter: StockFilter
  fiscalFilter: FiscalFilter
  minSalePrice: string
  maxSalePrice: string
  minCostPrice: string
  maxCostPrice: string
  filtersAppliedCount: number
  exportState: LoadState
  onSearchChange: (value: string) => void
  onSearchScopeChange: (value: SearchScope) => void
  onTypeFilterChange: (value: CatalogItemType | "all") => void
  onStatusFilterChange: (value: CatalogItemStatus | "all") => void
  onOriginFilterChange: (value: CatalogItemOrigin | "all") => void
  onUnitFilterChange: (value: string) => void
  onCategoryFilterChange: (value: string) => void
  onStockFilterChange: (value: StockFilter) => void
  onFiscalFilterChange: (value: FiscalFilter) => void
  onMinSalePriceChange: (value: string) => void
  onMaxSalePriceChange: (value: string) => void
  onMinCostPriceChange: (value: string) => void
  onMaxCostPriceChange: (value: string) => void
  onResetFilters: () => void
  onReload: () => Promise<void>
  onPageChange: (page: number) => void
  onEdit: (item: CatalogItem) => Promise<void>
  onExportCsv: () => Promise<void>
  onExportXlsx: () => Promise<void>
}) {
  function handleSearchInputChange(value: string) {
    

    onSearchChange(value)
  }

  function handleSearchScopeChange(nextScope: SearchScope) {
    onSearchScopeChange(nextScope)

    if (search !== "" && !isValidSearchFilterInput(search, nextScope)) {
      onSearchChange("")
    }
  }

  const totalPages = Math.max(1, Math.ceil(allItemsCount / PAGE_SIZE))
  const safeListPage = Math.min(currentPage, totalPages)
  const pagedItems = items

return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            Listagem de itens
          </h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            {items.length} de {allItemsCount} itens encontrados
            {filtersAppliedCount > 0 ? ` · ${filtersAppliedCount} filtro(s) ativo(s)` : ""}
            {totalPages > 1 ? ` · pág. ${safeListPage}/${totalPages}` : ""}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void onExportCsv()}
            disabled={allItemsCount === 0}
            title={allItemsCount > 0 ? `Exportar todos os ${allItemsCount} itens filtrados` : undefined}
            className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] hover:bg-[var(--color-hover)] disabled:opacity-50"
          >
            Exportar CSV{allItemsCount > 0 ? ` (${allItemsCount})` : ""}
          </button>

          <button
            type="button"
            onClick={() => void onExportXlsx()}
            disabled={exportState === "loading" || allItemsCount === 0}
            title={allItemsCount > 0 ? `Exportar todos os ${allItemsCount} itens filtrados` : undefined}
            className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] disabled:opacity-60"
          >
            {exportState === "loading" ? "Exportando..." : `Exportar XLSX${allItemsCount > 0 ? ` (${allItemsCount})` : ""}`}
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-[1.2fr_180px_180px_180px]">
        <input
          value={search}
          onChange={(event) => handleSearchInputChange(event.target.value)}
          placeholder="Buscar"
          className="input-like"
        />

        <select
          value={searchScope}
          onChange={(event) =>
            handleSearchScopeChange(event.target.value as SearchScope)
          }
          className="input-like"
        >
          <option value="all">Busca geral</option>
          <option value="name">Somente nome</option>
          <option value="sku">Somente SKU</option>
          <option value="barcode">Código de barras</option>
          <option value="id">ID do item</option>
        </select>

        <select
          value={typeFilter}
          onChange={(event) =>
            onTypeFilterChange(event.target.value as CatalogItemType | "all")
          }
          className="input-like"
        >
          <option value="all">Todos os tipos</option>
          <option value="product">Produtos</option>
          <option value="service">Serviços</option>
        </select>

        <select
          value={statusFilter}
          onChange={(event) =>
            onStatusFilterChange(event.target.value as CatalogItemStatus | "all")
          }
          className="input-like"
        >
          <option value="all">Todos os status</option>
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              {getStatusLabel(status)}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <select
          value={originFilter}
          onChange={(event) =>
            onOriginFilterChange(event.target.value as CatalogItemOrigin | "all")
          }
          className="input-like"
        >
          <option value="all">Todas as origens</option>
          {originOptions.map((origin) => (
            <option key={origin} value={origin}>
              {getOriginLabel(origin)}
            </option>
          ))}
        </select>

        <select
          value={unitFilter}
          onChange={(event) => onUnitFilterChange(event.target.value)}
          className="input-like"
        >
          <option value="all">Todas as unidades</option>
          {UNIT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={categoryFilter}
          onChange={(event) => onCategoryFilterChange(event.target.value)}
          className="input-like"
          placeholder="Filtrar por categoria..."
        />

        <select
          value={stockFilter}
          onChange={(event) =>
            onStockFilterChange(event.target.value as StockFilter)
          }
          className="input-like"
        >
          <option value="all">Todos os estoques</option>
          <option value="tracked">Controla estoque</option>
          <option value="not_tracked">Não controla estoque</option>
        </select>

        <select
          value={fiscalFilter}
          onChange={(event) =>
            onFiscalFilterChange(event.target.value as FiscalFilter)
          }
          className="input-like"
        >
          <option value="all">Fiscal: todos</option>
          <option value="with_ncm">Com NCM</option>
          <option value="with_nbs">Com NBS</option>
          <option value="without_classification">Sem classificação</option>
        </select>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MoneyInput
          value={minSalePrice}
          onChange={onMinSalePriceChange}
          placeholder="Venda mínima"
          label="Venda mínima"
        />
        <MoneyInput
          value={maxSalePrice}
          onChange={onMaxSalePriceChange}
          placeholder="Venda máxima"
          label="Venda máxima"
        />
        <MoneyInput
          value={minCostPrice}
          onChange={onMinCostPriceChange}
          placeholder="Custo mínimo"
          label="Custo mínimo"
        />
        <MoneyInput
          value={maxCostPrice}
          onChange={onMaxCostPriceChange}
          placeholder="Custo máximo"
          label="Custo máximo"
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void onReload()}
          className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-primary)]"
        >
          Recarregar API
        </button>

        <button
          type="button"
          onClick={onResetFilters}
          className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
        >
          Limpar filtros
        </button>
      </div>

      <div className="mt-5 overflow-hidden rounded-3xl border border-[var(--color-border-soft)]">
        {loadState === "loading" ? (
          <p className="p-5 text-sm text-[var(--color-text-muted)]">
            Carregando itens...
          </p>
        ) : items.length === 0 ? (
          <div className="p-5">
            <p className="text-sm font-semibold text-[var(--color-text)]">
              Nenhum item encontrado para os filtros atuais.
            </p>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
              Limpe os filtros ou busque por nome/SKU. Se a base estiver vazia, volte para Visão geral e cadastre um produto ou serviço de teste.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border-soft)]">
            {pagedItems.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => void onEdit(item)}
                className="grid w-full gap-3 p-4 text-left transition hover:bg-[var(--color-hover)] md:grid-cols-[1.2fr_120px_120px_120px_140px]"
              >
                <div>
                  <p className="font-semibold text-[var(--color-text)]">
                    {item.name}
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-text-weak)]">
                    SKU: {item.sku ?? "sem SKU"} · Unidade: {item.unit} ·{" "}
                    {item.inventory_settings?.track_stock
                      ? "controla estoque"
                      : "sem estoque"}
                    {item.brand ? ` · ${item.brand}` : ""}
                    {item.category ? ` · ${item.category}` : ""}
                  </p>

                  

        <p className="mt-2 text-xs font-medium text-[var(--color-text-muted)]">
            Venda:{" "}
        <span className="text-[var(--color-text)]">
    {formatCurrency(item.financial_settings?.default_sale_price)}
  </span>{" "}
  · Custo:{" "}
  <span className="text-[var(--color-text)]">
    {formatCurrency(item.financial_settings?.default_cost_price)}
  </span>
</p>
                </div>

                <span className="text-sm text-[var(--color-text-muted)]">
                  {getItemTypeLabel(item.item_type)}
                </span>

                <span
                  className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${getStatusClass(
                    item.status,
                  )}`}
                >
                  {getStatusLabel(item.status)}
                </span>

                <span className="text-xs text-[var(--color-text-weak)]">
                  {item.fiscal_settings?.ncm
                    ? `NCM ${item.fiscal_settings.ncm}`
                    : item.fiscal_settings?.nbs
                      ? `NBS ${item.fiscal_settings.nbs}`
                      : "Sem fiscal"}
                </span>

                <span className="text-xs text-[var(--color-text-weak)]">
                  {formatDateTimeBR(item.updated_at)}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {allItemsCount > 0 && (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[var(--color-text-muted)]">
            Mostrando{" "}
            <strong className="text-[var(--color-text)]">
              {(safeListPage - 1) * PAGE_SIZE + 1}–{Math.min(safeListPage * PAGE_SIZE, allItemsCount)}
            </strong>{" "}
            de{" "}
            <strong className="text-[var(--color-text)]">{allItemsCount}</strong>{" "}
            itens encontrados
            {totalPages > 1 ? ` · página ${safeListPage} de ${totalPages}` : ""}
          </p>

          {totalPages > 1 && (
            <div className="flex flex-wrap items-center gap-1">
              <button
                type="button"
                disabled={safeListPage === 1}
                onClick={() => onPageChange(Math.max(1, safeListPage - 1))}
                className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm font-medium text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
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
                      onClick={() => onPageChange(item as number)}
                      className={`min-w-[2.5rem] rounded-2xl border px-3 py-2 text-sm font-medium transition ${
                        safeListPage === item
                          ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                          : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)] hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)]"
                      }`}
                    >
                      {item}
                    </button>
                  ),
                )}

              <button
                type="button"
                disabled={safeListPage === totalPages}
                onClick={() => onPageChange(Math.min(totalPages, safeListPage + 1))}
                className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-sm font-medium text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Próxima →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── ClassificationCombobox ───────────────────────────────────────────────────
type ComboboxOption = { code: string; id: string; name: string }

function ClassificationCombobox({
  value,
  options,
  disabled,
  placeholder,
  onChange,
}: {
  value: string
  options: ComboboxOption[]
  disabled?: boolean
  placeholder?: string
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    const digits = value.replace(/\D/g, "")
    const text = value.trim().toLowerCase()
    if (!digits && !text) return options.slice(0, 30)
    return options
      .filter(
        (o) =>
          (digits && o.code.includes(digits)) ||
          o.name.toLowerCase().includes(text),
      )
      .slice(0, 30)
  }, [value, options])

  function handleSelect(option: ComboboxOption) {
    onChange(option.code)
    setOpen(false)
  }

  function handleBlur() {
    setTimeout(() => {
      if (!containerRef.current?.contains(document.activeElement)) {
        setOpen(false)
      }
    }, 120)
  }

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        disabled={disabled}
        placeholder={placeholder}
        className="input-like"
      />
      {open && filtered.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            right: 0,
            zIndex: 60,
            background: "var(--color-surface)",
            border: "1px solid var(--color-border-soft)",
            borderRadius: "16px",
            boxShadow: "0 12px 40px rgba(0,0,0,0.30)",
            maxHeight: "260px",
            overflowY: "auto",
            padding: "6px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          {filtered.map((option, idx) => (
            <button
              key={option.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault()
                handleSelect(option)
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                width: "100%",
                padding: "8px 10px",
                textAlign: "left",
                background: "transparent",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                borderBottom:
                  idx < filtered.length - 1
                    ? "1px solid var(--color-border-soft)"
                    : "none",
                transition: "background 0.12s",
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLButtonElement).style.background =
                  "var(--color-hover)"
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLButtonElement).style.background =
                  "transparent"
              }}
            >
              <span
                style={{
                  fontFamily: "monospace",
                  fontWeight: 700,
                  fontSize: "12px",
                  color: "var(--color-primary)",
                  background: "var(--color-primary-soft)",
                  border: "1px solid var(--color-primary-border)",
                  borderRadius: "8px",
                  padding: "2px 8px",
                  flexShrink: 0,
                  letterSpacing: "0.04em",
                }}
              >
                {option.code}
              </span>
              <span
                style={{
                  fontSize: "13px",
                  color: "var(--color-text-muted)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flex: 1,
                }}
              >
                {option.name}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const CATALOG_EVENT_TYPE_LABEL: Record<string, string> = {
  created: "Criado",
  updated: "Atualizado",
  deleted: "Removido",
}

function FormPanel({
  form,
  saveState,
  editingItemId,
  auditEvents,
  ncmOptions,
  nbsOptions,
  ncmOptionsState,
  activeCompanyName,
  canWrite,
  onChange,
  onSave,
  onCancel,
}: {
  form: CatalogFormState
  saveState: LoadState
  editingItemId: string | null
  auditEvents: CatalogItemAuditEvent[]
  ncmOptions: NcmOption[]
  nbsOptions: NbsOption[]
  ncmOptionsState: LoadState
  activeCompanyName: string
  canWrite: boolean
  onChange: (value: CatalogFormState) => void
  onSave: () => Promise<void>
  onCancel: () => void
}) {
  const isService = form.item_type === "service"

  function updateField<Key extends keyof CatalogFormState>(
    key: Key,
    value: CatalogFormState[Key],
  ) {
    onChange({ ...form, [key]: value })
  }

  const ncmComboboxOptions = useMemo<ComboboxOption[]>(
    () => ncmOptions.map((o) => ({ code: o.ncm, id: o.classificationId, name: o.name })),
    [ncmOptions],
  )
  const nbsComboboxOptions = useMemo<ComboboxOption[]>(
    () => nbsOptions.map((o) => ({ code: o.nbs, id: o.classificationId, name: o.name })),
    [nbsOptions],
  )

  return (
    <>
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div>
            <h2 className="text-xl font-bold text-[var(--color-text)]">
              {editingItemId ? "Editar item" : "Novo item"}
            </h2>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void onSave()}
              disabled={saveState === "loading" || !canWrite}
              className="rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[var(--color-primary-hover)] disabled:opacity-60"
            >
              {saveState === "loading" ? "Salvando..." : canWrite ? "Salvar item" : "Sem permissão"}
            </button>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          <FormStep step="1" title="Identificação">
            <div className="grid gap-4 md:grid-cols-2">
                            <Field label="Empresa">
                <div className="input-like">
                  {activeCompanyName || "Empresa não identificada"}
                </div>
              </Field>

              <Field label="Tipo *">
                <select
                  value={form.item_type}
                  onChange={(event) =>
                    onChange({
                      ...form,
                      item_type: event.target.value as CatalogItemType,
                      unit: event.target.value === "service" ? "HORA" : "UN",
                      track_stock: false,
                      stock_unit: event.target.value === "service" ? "" : "UN",
                      ncm: "",
                      nbs: "",
                    })
                  }
                  className="input-like"
                >
                  <option value="product">Produto — item físico</option>
                  <option value="service">Serviço — item não físico</option>
                </select>
              </Field>

              <Field label="Nome *">
                <input
                  value={form.name}
                  onChange={(event) => updateField("name", event.target.value)}
                  className="input-like"
                  placeholder="Ex.: Camiseta básica preta ou Consultoria técnica"
                />
              </Field>

              <Field label="Status">
                <select
                  value={form.status}
                  onChange={(event) =>
                    updateField("status", event.target.value as CatalogItemStatus)
                  }
                  className="input-like"
                >
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {getStatusLabel(status)}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="Unidade *">
                <select
                  value={form.unit}
                  onChange={(event) => updateField("unit", event.target.value)}
                  className="input-like"
                >
                  {UNIT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>

              <Field label="SKU interno">
                <input
                  value={form.sku}
                  onChange={(event) => updateField("sku", event.target.value)}
                  className="input-like"
                  placeholder="Opcional. Ex.: CAM-PRETA-M"
                />
              </Field>

              <Field label="Código de barras">
                <input
                  value={form.barcode}
                  onChange={(event) => updateField("barcode", event.target.value)}
                  className="input-like"
                  placeholder="Opcional. Use quando existir EAN/GTIN."
                />
              </Field>

              <Field label="Marca / Fabricante">
                <input
                  value={form.brand}
                  onChange={(event) => updateField("brand", event.target.value)}
                  className="input-like"
                  placeholder="Ex.: Nike, Samsung, AWS"
                />
              </Field>

              <Field label="Categoria interna">
                <input
                  value={form.category}
                  onChange={(event) => updateField("category", event.target.value)}
                  className="input-like"
                  placeholder="Ex.: Vestuário, Eletrônicos, Consultoria"
                />
              </Field>
            </div>
          </FormStep>

          <FormStep step="2" title="Preço e custo">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Preço de venda">
                <MoneyInput
                  value={form.default_sale_price}
                  onChange={(value) => updateField("default_sale_price", value)}
                  placeholder="99,90"
                  label="Preço de venda"
                />
              </Field>

              <Field label="Custo padrão">
                <MoneyInput
                  value={form.default_cost_price}
                  onChange={(value) => updateField("default_cost_price", value)}
                  placeholder="55,00"
                  label="Custo padrão"
                />
              </Field>
            </div>
          </FormStep>

          <FormStep step="3" title="Classificação fiscal">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={isService ? "NBS do serviço" : "NCM do produto"}>
                <ClassificationCombobox
                  value={isService ? form.nbs : form.ncm}
                  options={isService ? nbsComboboxOptions : ncmComboboxOptions}
                  disabled={
                    !isService &&
                    (ncmOptionsState === "loading" || ncmOptions.length === 0)
                  }
                  placeholder={isService ? "9 dígitos, se aplicável" : "8 dígitos"}
                  onChange={(val) =>
                    isService ? updateField("nbs", val) : updateField("ncm", val)
                  }
                />
                {isService && nbsOptions.length > 0 && (
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {nbsOptions.length} NBS disponível(is) no Fiscal
                  </p>
                )}
              </Field>

              <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4 text-sm text-[var(--color-text-muted)]">
                {isService
                  ? "NBS: 9 dígitos. Aplica-se a serviços sujeitos à classificação fiscal."
                  : "NCM: 8 dígitos. Obrigatório para produtos em documentos fiscais."}
              </div>
            </div>
          </FormStep>

          {!isService ? (
            <FormStep step="4" title="Estoque">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Controlar estoque?">
                  <label className="flex h-full items-center gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)]">
                    <input
                      type="checkbox"
                      checked={form.track_stock}
                      onChange={(event) =>
                        updateField("track_stock", event.target.checked)
                      }
                      className="h-5 w-5 accent-[var(--color-primary)]"
                    />
                    Sim, este produto deve controlar estoque futuramente
                  </label>
                </Field>

                {form.track_stock ? (
                  <Field label="Unidade de estoque *">
                    <select
                      value={form.stock_unit}
                      onChange={(event) =>
                        updateField("stock_unit", event.target.value)
                      }
                      className="input-like"
                    >
                      {UNIT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                ) : (
                  <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-4 text-sm leading-6 text-[var(--color-text-muted)]">
                    Estoque desligado. O item poderá ser vendido/cadastrado sem gerar saldo físico.
                  </div>
                )}

                {form.track_stock ? (
                  <Field label="Estoque mínimo">
                    <input
                      value={form.minimum_stock}
                      onChange={(event) =>
                        updateField("minimum_stock", event.target.value)
                      }
                      className="input-like"
                      placeholder="Ex.: 5"
                    />
                  </Field>
                ) : null}

                {form.track_stock ? (
                  <Field label="Permite estoque negativo?">
                    <label className="flex h-full items-center gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)]">
                      <input
                        type="checkbox"
                        checked={form.allow_negative_stock}
                        onChange={(event) =>
                          updateField("allow_negative_stock", event.target.checked)
                        }
                        className="h-5 w-5 accent-amber-500"
                      />
                      Sim — permitir saldo negativo (⚠️ use com cautela)
                    </label>
                  </Field>
                ) : null}
              </div>
            </FormStep>
          ) : null}

          <FormStep step={isService ? "4" : "5"} title="Descrição e observações">
            <div className="grid gap-4">
              <Field label="Descrição">
                <textarea
                  value={form.description}
                  onChange={(event) =>
                    updateField("description", event.target.value)
                  }
                  className="input-like min-h-24 resize-y"
                  placeholder="Ex.: Produto vendido em loja e marketplace. Serviço cobrado por hora técnica."
                />
              </Field>

              <Field label="Observações internas">
                <textarea
                  value={form.notes}
                  onChange={(event) => updateField("notes", event.target.value)}
                  className="input-like min-h-24 resize-y"
                  placeholder="Ex.: Validar margem antes de vender com desconto. Confirmar classificação fiscal com contador."
                />
              </Field>
            </div>
          </FormStep>
        </div>
      </div>

      <aside className="space-y-4">
        <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="font-semibold text-[var(--color-text)]">
            Checklist rápido
          </h3>
          <div className="mt-4 space-y-3">
            <ChecklistItem checked={form.name.trim().length >= 2} text="Nome claro" />
            <ChecklistItem checked={form.unit.trim().length > 0} text="Unidade escolhida" />
            <ChecklistItem checked={form.default_sale_price.trim().length > 0} text="Preço de venda informado" />
            <ChecklistItem checked={form.default_cost_price.trim().length > 0} text="Custo padrão informado" />
            <ChecklistItem checked={form.category.trim().length > 0} text="Categoria definida" />
            <ChecklistItem
              checked={isService ? form.ncm.trim() === "" : form.nbs.trim() === ""}
              text={isService ? "Sem NCM em serviço" : "Sem NBS em produto"}
            />
          </div>
        </div>

        <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl shadow-[var(--color-card-shadow)]">
          <h3 className="font-semibold text-[var(--color-text)]">
            Auditoria do item
          </h3>

          {editingItemId === null ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              A auditoria será gerada após salvar o item. Isso ajuda a provar quem criou ou alterou o cadastro.
            </p>
          ) : auditEvents.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              Nenhum evento carregado.
            </p>
          ) : (
            <div className="mt-4 space-y-3">
              {auditEvents.map((event) => (
                <div
                  key={event.id}
                  className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3"
                >
                  <p className="text-sm font-semibold text-[var(--color-text)]">
                    {CATALOG_EVENT_TYPE_LABEL[event.event_type] ?? event.event_type}
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-text-weak)]">
                    {formatDateTimeBR(event.occurred_at)} · {event.source}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
    </>
  )
}

function FormStep({
  step,
  title,
  children,
}: {
  step: string
  title: string
  children: ReactNode
}) {
  return (
    <section className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-5">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-sm font-black text-[var(--color-primary)]">
          {step}
        </div>
        <h3 className="font-semibold text-[var(--color-text)]">{title}</h3>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function ChecklistItem({ checked, text }: { checked: boolean; text: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] p-3">
      <span className="text-sm text-[var(--color-text-muted)]">{text}</span>
      <span
        className={[
          "rounded-full border px-3 py-1 text-xs font-bold",
          checked
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
            : "border-amber-500/30 bg-amber-500/10 text-amber-500",
        ].join(" ")}
      >
        {checked ? "OK" : "Pendente"}
      </span>
    </div>
  )
}

function MoneyInput({
  value,
  onChange,
  placeholder,
  label,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  label: string
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

      <div className="currency-input-shell">
        <span className="currency-input-prefix">R$</span>
        <input
          value={value}
          onChange={(event) => handleChange(event.target.value)}
          inputMode="decimal"
          className="input-like currency-input"
          placeholder={placeholder}
          aria-label={label}
        />
      </div>
    </>
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
        className="relative w-full max-w-md rounded-[2rem] border border-red-500/40 bg-[var(--color-surface)] p-6 shadow-2xl shadow-black/40"
        style={{ animation: "kovirModalIn 180ms ease-out" }}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-1 text-sm font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
          aria-label="Fechar aviso"
        >
          ×
        </button>

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

function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-text-weak)]">
        {label}
      </span>
      {children}
    </label>
  )
}


