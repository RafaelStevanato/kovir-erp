import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  Ban,
  CheckCircle2,
  CreditCard,
  Database,
  Eye,
  FileText,
  Loader2,
  Percent,
  Plus,
  RefreshCw,
  ShoppingBag,
  ShoppingCart,
  UserRound,
  X,
} from "lucide-react"
import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react"

import { SearchableSelect, type SearchableSelectOption } from "../../components/SearchableSelect"
import { getActiveCompanyId } from "../../config/activeCompany"
import { getActiveUser } from "../../config/activeSession"
import { getCatalogItems } from "../catalog/catalogApi"
import type { CatalogItem, CatalogItemType } from "../catalog/types"
import { getCompanies } from "../company/companyApi"
import type { Company } from "../company/types"
import { getParticipants } from "../participants/participantsApi"
import type { Participant } from "../participants/types"
import { getStockItemsAvailability } from "../stock/stockApi"
import type { StockItemAvailability } from "../stock/types"
import {
  cancelSale,
  closeSale,
  createSale,
  getCommercialInvoicePdf,
  getFiscalDocumentsForSale,
  getSale,
  getSaleAuditEvents,
  getSaleFiscalPreviewPdf,
  getSaleInvoiceReadiness,
  getSales,
  getSalesDiagnostics,
  getSalesPaymentMethods,
  getSaleStatusHistory,
  getSalesRules,
  getSalesItemReadiness,
  postSaleInvoice,
} from "./salesApi"
import type {
  DiscountCategory,
  DiscountType,
  FiscalDocument,
  FiscalInvoiceReadiness,
  PaymentMethod,
  PaymentMethodCode,
  Sale,
  SaleAuditEvent,
  SaleCreatePayload,
  SaleItemReadiness,
  SaleOperationNature,
  SalesDiagnostics,
  SalesRules,
  SaleStatus,
  SaleStatusHistory,
  SaleType,
} from "./types"

type SalesTab = "overview" | "list" | "create" | "detail"

type FormLineItem = {
  local_id: string
  item_id: string
  quantity: string
  unit: string
  unit_price: string
  discount_amount: string
}


type FormPaymentLine = {
  local_id: string
  payment_method_code: PaymentMethodCode
  amount: string
  due_date: string
  installments: string
  notes: string
}

type StockAvailabilityMap = Record<string, StockItemAvailability>
type SaleItemReadinessMap = Record<string, SaleItemReadiness>

type SaleFormState = {
  company_id: string
  participant_id: string
  sale_type: SaleType
  origin: "manual" | "pdv"
  operation_nature: SaleOperationNature
  operation_nature_reason: string
  issue_date: string
  competency_date: string
  has_discount: boolean
  discount_type: DiscountType
  discount_amount: string
  discount_percentage: string
  discount_category: DiscountCategory | ""
  discount_reason: string
  freight_amount: string
  notes: string
  payment_plans: FormPaymentLine[]
  items: FormLineItem[]
}

type SalesPageProps = {
  saleType: SaleType
}

const saleTypeConfig: Record<
  SaleType,
  {
    title: string
    label: string
    itemLabel: string
    itemPlural: string
    subtitle: string
    badge: string
    icon: ReactNode
  }
> = {
  product: {
    title: "Vendas de Produtos",
    label: "produto",
    itemLabel: "Produto",
    itemPlural: "Produtos",
    subtitle: "Registre clientes, produtos, quantidades, descontos e formas de pagamento.",
    badge: "Bloco 5B — Vendas de Produtos",
    icon: <ShoppingCart className="h-4 w-4" />,
  },
  service: {
    title: "Vendas de Serviços",
    label: "serviço",
    itemLabel: "Serviço",
    itemPlural: "Serviços",
    subtitle: "Registre clientes, serviços, quantidades, descontos e formas de pagamento.",
    badge: "Bloco 5B — Vendas de Serviços",
    icon: <ShoppingBag className="h-4 w-4" />,
  },
}

const operationNatureOptions: Array<{ value: SaleOperationNature; label: string; helper: string }> = [
  { value: "normal_sale", label: "Venda normal", helper: "Operação comercial padrão" },
  { value: "bonus", label: "Bonificação", helper: "Entrega sem cobrança comercial, com motivo obrigatório" },
  { value: "sample", label: "Amostra grátis", helper: "Amostra enviada ao cliente" },
  { value: "exchange", label: "Troca", helper: "Operação vinculada a troca comercial" },
  { value: "courtesy", label: "Cortesia", helper: "Cortesia comercial ou relacionamento" },
  { value: "replacement", label: "Reposição", helper: "Reposição por falha, avaria ou ajuste" },
  { value: "other", label: "Outra natureza", helper: "Natureza não prevista na lista" },
]

const statusLabels: Record<SaleStatus, string> = {
  draft: "Rascunho",
  quote: "Orçamento",
  confirmed: "Confirmada",
  closed: "Fechado",
  paid: "Pago",
  cancelled: "Cancelada",
}

const statusClasses: Record<SaleStatus, string> = {
  draft: "border-amber-300/40 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  quote: "border-sky-300/40 bg-sky-500/10 text-sky-600 dark:text-sky-300",
  confirmed: "border-emerald-300/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  closed: "border-amber-300/40 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  paid: "border-emerald-300/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
  cancelled: "border-rose-300/40 bg-rose-500/10 text-rose-600 dark:text-rose-300",
}

// ─── Feature flag: Faturamento fiscal ───────────────────────────────────────
// Mude para `true` quando o backend de emissão de NF-e estiver pronto.
// Libera o botão "FATURAR" no detalhe da venda e o filtro "Faturadas" na lista.
const INVOICE_FEATURE_ENABLED = false
// ────────────────────────────────────────────────────────────────────────────


const paymentMethodFallbackLabels: Record<PaymentMethodCode, string> = {
  pix: "Pix",
  credit_card: "Cartão de crédito",
  debit_card: "Cartão de débito",
  cash: "Dinheiro",
  boleto: "Boleto",
  bank_transfer: "Transferência bancária",
  store_credit: "Crédito da loja",
  other: "Outra forma",
}

const paymentMethodFallbackOptions: PaymentMethod[] = Object.entries(paymentMethodFallbackLabels).map(([code, name]) => ({
  id: code,
  company_id: "",
  code: code as PaymentMethodCode,
  name,
  method_type: code,
  description: null,
  requires_reference: false,
  default_due_behavior: "same_day",
  status: "active",
  settings: null,
  created_at: "",
  updated_at: "",
}))

const discountCategories: Array<{ value: DiscountCategory; label: string }> = [
  { value: "coupon", label: "Cupom de desconto" },
  { value: "promotion", label: "Promoção/campanha" },
  { value: "commercial_negotiation", label: "Negociação comercial" },
  { value: "customer_loyalty", label: "Fidelidade do cliente" },
  { value: "manager_authorization", label: "Autorização gerencial" },
  { value: "damaged_goods", label: "Produto avariado/condição especial" },
  { value: "other", label: "Outro" },
]

function getOperationNatureLabel(value: SaleOperationNature | string | null | undefined) {
  return operationNatureOptions.find((option) => option.value === value)?.label ?? "Venda normal"
}

function operationNatureRequiresReason(value: SaleOperationNature | string) {
  return value !== "normal_sale"
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10)
}

function createEmptyLine(): FormLineItem {
  return {
    local_id: crypto.randomUUID(),
    item_id: "",
    quantity: "1",
    unit: "UN",
    unit_price: "0",
    discount_amount: "0",
  }
}

function createEmptyPaymentLine(amount = "0", dueDate = todayIsoDate()): FormPaymentLine {
  return {
    local_id: crypto.randomUUID(),
    payment_method_code: "pix",
    amount,
    due_date: dueDate,
    installments: "1",
    notes: "",
  }
}

function createInitialForm(saleType: SaleType, companyId = getActiveCompanyId()): SaleFormState {
  const today = todayIsoDate()

  return {
    company_id: companyId,
    participant_id: "",
    sale_type: saleType,
    origin: "manual",
    operation_nature: "normal_sale",
    operation_nature_reason: "",
    issue_date: today,
    competency_date: today,
    has_discount: false,
    discount_type: "amount",
    discount_amount: "0",
    discount_percentage: "",
    discount_category: "",
    discount_reason: "",
    freight_amount: "0",
    notes: "",
    payment_plans: [createEmptyPaymentLine("0", today)],
    items: [createEmptyLine()],
  }
}

function parseDecimal(value: string | number | null | undefined) {
  const parsed = Number(String(value ?? "0").replace(",", "."))

  if (Number.isNaN(parsed)) {
    return 0
  }

  return parsed
}

function formatCurrency(value: string | number | null | undefined) {
  const parsed = parseDecimal(value)

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(parsed)
}


function formatPercent(value: string | number | null | undefined) {
  const parsed = parseDecimal(value)
  return `${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 }).format(parsed)}%`
}

function formatQuantity(value: string | number | null | undefined) {
  const parsed = parseDecimal(value)
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 4 }).format(parsed)
}

function calculateDiscountAmount(form: SaleFormState, subtotal: number) {
  if (!form.has_discount) return 0

  if (form.discount_type === "percentage") {
    const percentage = parseDecimal(form.discount_percentage)
    return Math.min(subtotal, Math.max(0, subtotal * (percentage / 100)))
  }

  return Math.min(subtotal, Math.max(0, parseDecimal(form.discount_amount)))
}

function buildStockAvailabilityMap(records: StockItemAvailability[]): StockAvailabilityMap {
  return records.reduce<StockAvailabilityMap>((acc, availability) => {
    acc[availability.item_id] = availability
    return acc
  }, {})
}

function buildSaleItemReadinessMap(records: SaleItemReadiness[]): SaleItemReadinessMap {
  return records.reduce<SaleItemReadinessMap>((acc, readiness) => {
    acc[readiness.item_id] = readiness
    return acc
  }, {})
}

function itemTracksStock(item: CatalogItem) {
  return Boolean(item.inventory_settings?.track_stock)
}

function itemAllowsNegativeStock(item: CatalogItem) {
  return Boolean(item.inventory_settings?.allow_negative_stock)
}

function isItemSelectableForSale(
  item: CatalogItem,
  saleType: SaleType,
  stockAvailability: StockAvailabilityMap,
  stockAvailabilityLoaded: boolean,
  itemReadiness: SaleItemReadinessMap,
  itemReadinessLoaded: boolean,
) {
  if (item.status !== "active" || item.item_type !== saleType) return false

  if (itemReadinessLoaded) {
    const readiness = itemReadiness[item.id]
    return Boolean(readiness?.can_select)
  }

  if (saleType !== "product") return true

  if (!itemTracksStock(item)) return true
  if (itemAllowsNegativeStock(item)) return true
  if (!stockAvailabilityLoaded) return false

  const availability = stockAvailability[item.id]
  return Boolean(availability?.can_sell_now) && parseDecimal(availability?.available_quantity) > 0
}

function validateItemReadinessForForm(
  form: SaleFormState,
  catalogItems: CatalogItem[],
  itemReadiness: SaleItemReadinessMap,
  itemReadinessLoaded: boolean,
) {
  if (!itemReadinessLoaded) return "A prontidão fiscal/estoque dos itens ainda está carregando. Aguarde antes de avançar."

  for (const line of form.items) {
    if (!line.item_id) continue

    const item = catalogItems.find((candidate) => candidate.id === line.item_id)
    if (!item) {
      return "Item selecionado não está disponível para venda. Atualize a tela e selecione novamente."
    }

    const readiness = itemReadiness[line.item_id]
    if (!readiness) {
      return `${item.name}: prontidão operacional não encontrada. Atualize a tela antes de confirmar.`
    }

    if (!readiness.can_select) {
      return `${item.name}: ${readiness.blocking_reasons.join(" ") || "item bloqueado para venda."}`
    }
  }

  return null
}

function validateStockForForm(
  form: SaleFormState,
  catalogItems: CatalogItem[],
  stockAvailability: StockAvailabilityMap,
  stockAvailabilityLoaded: boolean,
) {
  if (form.sale_type !== "product") return null
  if (!stockAvailabilityLoaded) return "A disponibilidade do estoque ainda está carregando. Aguarde antes de vender produto."

  const quantitiesByItem = form.items.reduce<Record<string, number>>((acc, line) => {
    if (!line.item_id) return acc
    acc[line.item_id] = (acc[line.item_id] ?? 0) + parseDecimal(line.quantity)
    return acc
  }, {})

  for (const [itemId, requestedQuantity] of Object.entries(quantitiesByItem)) {
    const item = catalogItems.find((candidate) => candidate.id === itemId)
    if (!item) {
      return "Produto selecionado não está disponível para venda. Atualize a tela e selecione novamente."
    }

    if (!itemTracksStock(item) || itemAllowsNegativeStock(item)) {
      continue
    }

    const availability = stockAvailability[itemId]
    if (!availability) {
      return `${item.name}: disponibilidade de estoque não encontrada. Atualize a tela antes de confirmar.`
    }

    const availableQuantity = parseDecimal(availability.available_quantity)
    if (availableQuantity <= 0) {
      return `${item.name}: produto sem estoque efetivo no local ${availability.location_name}.`
    }

    if (requestedQuantity > availableQuantity) {
      return `${item.name}: quantidade solicitada ${formatQuantity(requestedQuantity)} ${availability.unit} excede o saldo disponível ${formatQuantity(availableQuantity)} ${availability.unit}.`
    }
  }

  return null
}

function toMoneyPayload(value: number) {
  return value.toFixed(2)
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—"

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date)
}

function formatDate(value: string | null | undefined) {
  if (!value) return "—"

  const [year, month, day] = value.slice(0, 10).split("-")

  if (!year || !month || !day) {
    return value
  }

  return `${day}/${month}/${year}`
}

function safeString(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "—"
  }

  return String(value)
}

function getSnapshotText(snapshot: Record<string, unknown>, key: string) {
  return safeString(snapshot[key])
}

function normalizeNumericInput(value: string) {
  const normalized = value.replace(",", ".")
  const isValid = /^\d*(\.\d{0,4})?$/.test(normalized)

  return isValid ? normalized : value.replace(/[^\d.]/g, "")
}

function buildCustomerOptions(customers: Participant[]): SearchableSelectOption[] {
  return customers.map((customer) => ({
    value: customer.id,
    label: customer.name,
    description: [customer.document, customer.trade_name, customer.email]
      .filter(Boolean)
      .join(" · "),
    keywords: [
      customer.id,
      customer.name,
      customer.trade_name ?? "",
      customer.document ?? "",
      customer.email ?? "",
      customer.phone ?? "",
    ],
  }))
}

function buildItemOptions(items: CatalogItem[], itemLabel: string, stockAvailability: StockAvailabilityMap = {}, itemReadiness: SaleItemReadinessMap = {}): SearchableSelectOption[] {
  return items.map((item) => {
    const availability = stockAvailability[item.id]
    const readiness = itemReadiness[item.id]
    const stockDescription = readiness?.stock
      ? readiness.stock.track_stock
        ? `Saldo ${formatQuantity(readiness.stock.available_quantity)} ${readiness.stock.unit} em ${readiness.stock.location_name}`
        : "Não controla estoque"
      : availability
        ? itemTracksStock(item)
          ? `Saldo ${formatQuantity(availability.available_quantity)} ${availability.unit} em ${availability.location_name}`
          : "Não controla estoque"
        : null
    const fiscalDescription = readiness
      ? readiness.fiscal_required
        ? readiness.fiscal_ready
          ? `Fiscal OK (${readiness.fiscal_resolution_source})`
          : "Fiscal pendente"
        : "Fiscal não exigido"
      : null

    return {
      value: item.id,
      label: item.name,
      description: [
        itemLabel,
        item.sku ? `SKU ${item.sku}` : null,
        item.barcode ? `Código ${item.barcode}` : null,
        item.unit ? `Un. ${item.unit}` : null,
        fiscalDescription,
        stockDescription,
      ]
        .filter(Boolean)
        .join(" · "),
      keywords: [
        item.id,
        item.name,
        item.description ?? "",
        item.sku ?? "",
        item.barcode ?? "",
        item.unit ?? "",
        item.fiscal_settings?.ncm ?? "",
        item.fiscal_settings?.nbs ?? "",
      ],
    }
  })
}

function buildSalePayload(form: SaleFormState): SaleCreatePayload {
  const subtotal = form.items.reduce((total, item) => {
    return total + parseDecimal(item.quantity) * parseDecimal(item.unit_price)
  }, 0)
  const calculatedDiscount = calculateDiscountAmount(form, subtotal)
  const hasDiscount = form.has_discount && calculatedDiscount > 0

  return {
    company_id: form.company_id,
    participant_id: form.origin === "pdv" ? null : form.participant_id,
    sale_type: form.sale_type,
    origin: form.origin,
    operation_nature: form.operation_nature,
    operation_nature_reason: form.operation_nature === "normal_sale" ? null : form.operation_nature_reason || null,
    issue_date: form.issue_date || null,
    competency_date: form.competency_date || null,
    discount_amount: hasDiscount ? toMoneyPayload(calculatedDiscount) : "0",
    discount_type: hasDiscount ? form.discount_type : "amount",
    discount_percentage: hasDiscount && form.discount_type === "percentage" ? form.discount_percentage || null : null,
    discount_category: hasDiscount ? (form.discount_category as DiscountCategory) : null,
    discount_reason: hasDiscount ? form.discount_reason || null : null,
    freight_amount: toMoneyPayload(parseDecimal(form.freight_amount)),
    tax_amount: "0",
    notes: form.notes || null,
    payment_plans: form.payment_plans
      .filter((plan) => parseDecimal(plan.amount) > 0)
      .map((plan) => ({
        payment_method_code: plan.payment_method_code,
        amount: toMoneyPayload(parseDecimal(plan.amount)),
        due_date: plan.due_date || null,
        installments: Math.max(1, Number.parseInt(plan.installments || "1", 10) || 1),
        notes: plan.notes || null,
        metadata: null,
      })),
    items: form.items.map((item) => ({
      item_id: item.item_id,
      fiscal_classification_id: null,
      quantity: item.quantity || "1",
      unit: item.unit || null,
      unit_price: item.unit_price || null,
      discount_amount: toMoneyPayload(parseDecimal(item.discount_amount)),
      freight_amount: "0",
      tax_amount: "0",
    })),
  }
}

export function ProductSalesPage() {
  return <SalesPage saleType="product" />
}

export function ServiceSalesPage() {
  return <SalesPage saleType="service" />
}

export function SalesPage({ saleType = "product" }: SalesPageProps) {
  const config = saleTypeConfig[saleType]
  const [activeTab, setActiveTab] = useState<SalesTab>("overview")
  const [companies, setCompanies] = useState<Company[]>([])
  const [customers, setCustomers] = useState<Participant[]>([])
  const [items, setItems] = useState<CatalogItem[]>([])
  const [stockAvailability, setStockAvailability] = useState<StockAvailabilityMap>({})
  const [stockAvailabilityLoaded, setStockAvailabilityLoaded] = useState(saleType !== "product")
  const [itemReadiness, setItemReadiness] = useState<SaleItemReadinessMap>({})
  const [itemReadinessLoaded, setItemReadinessLoaded] = useState(false)
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [sales, setSales] = useState<Sale[]>([])
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null)
  const [statusHistory, setStatusHistory] = useState<SaleStatusHistory[]>([])
  const [auditEvents, setAuditEvents] = useState<SaleAuditEvent[]>([])
  const [, setRules] = useState<SalesRules | null>(null)
  const [, setDiagnostics] = useState<SalesDiagnostics | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<SaleStatus | "all">("all")
  const [pendingStatusAction, setPendingStatusAction] = useState<"confirm" | "cancel" | null>(null)
  const [readiness, setReadiness] = useState<FiscalInvoiceReadiness | null>(null)
  const [readinessLoading, setReadinessLoading] = useState(false)
  const [fiscalDocuments, setFiscalDocuments] = useState<FiscalDocument[]>([])
  const [activeCompanyId] = useState(() => getActiveCompanyId())
  const [form, setForm] = useState<SaleFormState>(() => createInitialForm(saleType, activeCompanyId))

  const activeCompany = useMemo(
    () => companies.find((company) => company.id === activeCompanyId) ?? null,
    [activeCompanyId, companies],
  )

  const activeCustomers = useMemo(
    () => customers.filter((customer) => customer.status === "active"),
    [customers],
  )

  const activeItems = useMemo(
    () => items.filter((item) => isItemSelectableForSale(item, saleType, stockAvailability, stockAvailabilityLoaded, itemReadiness, itemReadinessLoaded)),
    [items, saleType, stockAvailability, stockAvailabilityLoaded, itemReadiness, itemReadinessLoaded],
  )

  const estimatedTotal = useMemo(() => {
    const itemsTotal = form.items.reduce((total, item) => {
      const quantity = parseDecimal(item.quantity)
      const unitPrice = parseDecimal(item.unit_price)
      const itemDiscount = parseDecimal(item.discount_amount)

      return total + Math.max(0, quantity * unitPrice - itemDiscount)
    }, 0)

    const freight = parseDecimal(form.freight_amount)

    return itemsTotal - calculateDiscountAmount(form, itemsTotal) + freight
  }, [form])

  const salesTotals = useMemo(() => {
    return sales.reduce(
      (acc, sale) => {
        const total = parseDecimal(sale.total_amount)

        if (sale.status === "confirmed" || sale.status === "closed" || sale.status === "paid") {
          acc.confirmed += total
        }

        if (sale.status === "draft" || sale.status === "quote") {
          acc.draft += total
        }

        acc.total += total

        return acc
      },
      { confirmed: 0, draft: 0, total: 0 },
    )
  }, [sales])

  async function loadPageData() {
    setIsLoading(true)
    setErrorMessage(null)

    try {
      const [
        companiesResponse,
        customersResponse,
        itemsResponse,
        paymentMethodsResponse,
        salesResponse,
        rulesResponse,
        diagnosticsResponse,
      ] = await Promise.all([
        getCompanies(),
        getParticipants({
          company_id: activeCompanyId,
          participant_type: "customer",
          status: "active",
        }),
        getCatalogItems({
          company_id: activeCompanyId,
          item_type: saleType as CatalogItemType,
          status: "active",
        }),
        getSalesPaymentMethods({ company_id: activeCompanyId }),
        getSales({
          company_id: activeCompanyId,
          sale_type: saleType,
          status: statusFilter === "all" ? undefined : statusFilter,
          limit: 50,
          offset: 0,
        }),
        getSalesRules(),
        getSalesDiagnostics(),
      ])

      const availabilityRecords =
        saleType === "product" && itemsResponse.data.length > 0
          ? (await getStockItemsAvailability(activeCompanyId, itemsResponse.data.map((item) => item.id))).data
          : []

      setCompanies(companiesResponse.data)
      setCustomers(customersResponse.data)
      setItems(itemsResponse.data)
      setStockAvailability(buildStockAvailabilityMap(availabilityRecords))
      setStockAvailabilityLoaded(true)
      setPaymentMethods(paymentMethodsResponse.data)
      setSales(salesResponse.data)
      setRules(rulesResponse.data)
      setDiagnostics(diagnosticsResponse.data)
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : `Não foi possível carregar ${config.title.toLowerCase()}.`,
      )
    } finally {
      setIsLoading(false)
    }
  }

  async function loadItemReadiness() {
    if (!activeCompanyId || items.length === 0) {
      setItemReadiness({})
      setItemReadinessLoaded(true)
      return
    }

    setItemReadinessLoaded(false)

    try {
      const response = await getSalesItemReadiness({
        company_id: activeCompanyId,
        sale_type: saleType,
        operation_nature: form.operation_nature,
        valid_on: form.issue_date || form.competency_date || null,
        limit: 500,
        offset: 0,
      })
      setItemReadiness(buildSaleItemReadinessMap(response.data))
      setItemReadinessLoaded(true)
    } catch (error) {
      setItemReadiness({})
      setItemReadinessLoaded(false)
      setErrorMessage(error instanceof Error ? error.message : "Não foi possível validar prontidão fiscal/estoque dos itens.")
    }
  }

  useEffect(() => {
    setForm(createInitialForm(saleType, activeCompanyId))
    setStockAvailability({})
    setStockAvailabilityLoaded(saleType !== "product")
    setItemReadiness({})
    setItemReadinessLoaded(false)
    setSelectedSale(null)
    setActiveTab("overview")
    void loadPageData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saleType])

  useEffect(() => {
    void loadItemReadiness()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, saleType, form.operation_nature, form.issue_date, form.competency_date])

  async function refreshSales() {
    await loadPageData()
  }

  async function loadSaleDetails(saleId: string) {
    setIsLoading(true)
    setErrorMessage(null)
    setReadiness(null)
    setFiscalDocuments([])

    try {
      const [saleResponse, historyResponse, auditResponse] = await Promise.all([
        getSale(saleId),
        getSaleStatusHistory(saleId),
        getSaleAuditEvents(saleId),
      ])

      setSelectedSale(saleResponse.data)
      setStatusHistory(historyResponse.data)
      setAuditEvents(auditResponse.data)
      setActiveTab("detail")

      // Carrega prontidão fiscal e documentos em background para vendas confirmadas
      if (saleResponse.data.status === "confirmed") {
        void loadReadiness(saleId)
        void loadFiscalDocuments(saleId)
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar a venda.",
      )
    } finally {
      setIsLoading(false)
    }
  }

  async function loadReadiness(saleId: string) {
    setReadinessLoading(true)
    try {
      const response = await getSaleInvoiceReadiness(saleId)
      setReadiness(response.data)
    } catch {
      // Silencia — readiness é informação auxiliar, não bloqueia a tela
    } finally {
      setReadinessLoading(false)
    }
  }

  async function loadFiscalDocuments(saleId: string) {
    try {
      const response = await getFiscalDocumentsForSale(saleId)
      setFiscalDocuments(response.data)
    } catch {
      // Silencia
    }
  }

  async function handleGeneratePdf(saleId: string) {
    try {
      const blob = await getSaleFiscalPreviewPdf(saleId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `previa_fiscal_${saleId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Erro ao gerar prévia PDF.")
    }
  }

  async function handleGenerateEspelhoNFe(saleId: string) {
    try {
      const blob = await getCommercialInvoicePdf(saleId, "paid")
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `espelho_nfe_${saleId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Erro ao gerar Espelho NF-e.")
    }
  }

  async function handleEmitInvoice(saleId: string) {
    setIsSubmitting(true)
    try {
      await postSaleInvoice(saleId)
      setSuccessMessage("NF-e enviada para a Focus NFe com sucesso!")
      void loadFiscalDocuments(saleId)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Erro ao emitir NF-e.")
    } finally {
      setIsSubmitting(false)
    }
  }

  function updateFormField<Field extends keyof SaleFormState>(
    field: Field,
    value: SaleFormState[Field],
  ) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function updateLineItem(localId: string, field: keyof FormLineItem, value: string) {
    setForm((current) => ({
      ...current,
      items: current.items.map((line) => {
        if (line.local_id !== localId) return line

        if (field !== "item_id") {
          return { ...line, [field]: value }
        }

        const selectedItem = items.find((item) => item.id === value)
        const defaultPrice = selectedItem?.financial_settings?.default_sale_price ?? line.unit_price

        return {
          ...line,
          item_id: value,
          unit: selectedItem?.unit ?? line.unit,
          unit_price: defaultPrice ?? "0",
        }
      }),
    }))
  }

  function addLineItem() {
    setForm((current) => ({ ...current, items: [...current.items, createEmptyLine()] }))
  }

  function removeLineItem(localId: string) {
    setForm((current) => ({
      ...current,
      items:
        current.items.length === 1
          ? current.items
          : current.items.filter((item) => item.local_id !== localId),
    }))
  }

  function validateForm() {
    if (!activeCompanyId) return "Empresa ativa não configurada."
    if (form.origin !== "pdv" && !form.participant_id) return "Selecione um cliente ativo."

    const hasInvalidItem = form.items.some(
      (item) => !item.item_id || parseDecimal(item.quantity) <= 0,
    )
    if (hasInvalidItem) {
      return `Cada linha da venda precisa de ${config.label} e quantidade maior que zero.`
    }

    const readinessValidationMessage = validateItemReadinessForForm(form, items, itemReadiness, itemReadinessLoaded)
    if (readinessValidationMessage) return readinessValidationMessage

    const stockValidationMessage = validateStockForForm(form, items, stockAvailability, stockAvailabilityLoaded)
    if (stockValidationMessage) return stockValidationMessage

    if (operationNatureRequiresReason(form.operation_nature) && !form.operation_nature_reason.trim()) {
      return "Informe o motivo da natureza da operação."
    }

    if (form.has_discount) {
      const subtotal = form.items.reduce((total, item) => total + parseDecimal(item.quantity) * parseDecimal(item.unit_price), 0)
      const discountValue = calculateDiscountAmount(form, subtotal)
      if (form.discount_type === "percentage") {
        const percentage = parseDecimal(form.discount_percentage)
        if (percentage <= 0 || percentage > 100) {
          return "Informe um percentual de desconto maior que zero e menor ou igual a 100%."
        }
      } else if (parseDecimal(form.discount_amount) <= 0) {
        return "Informe um valor de desconto maior que zero ou desmarque a opção de desconto."
      }
      if (discountValue <= 0) return "O desconto calculado precisa ser maior que zero."
      if (!form.discount_category) return "Selecione a categoria do desconto."
      if (!form.discount_reason.trim()) return "Informe o motivo do desconto."
    }

    if (estimatedTotal < 0) return "Total estimado não pode ser negativo."
    const expectedReceivableTotal = ["normal_sale", "other"].includes(form.operation_nature)
      ? Math.max(estimatedTotal, 0)
      : 0
    const paymentTotal = form.payment_plans.reduce((total, plan) => total + parseDecimal(plan.amount), 0)

    if (expectedReceivableTotal > 0) {
      if (!form.payment_plans.some((plan) => parseDecimal(plan.amount) > 0)) {
        return "Informe pelo menos uma forma de pagamento."
      }
      if (Math.abs(paymentTotal - expectedReceivableTotal) > 0.009) {
        return `A soma das formas de pagamento (${formatCurrency(paymentTotal)}) precisa ser igual ao total a receber (${formatCurrency(expectedReceivableTotal)}).`
      }
    }

    if (expectedReceivableTotal === 0 && paymentTotal > 0.009) {
      return "Operação sem valor a receber não deve ter forma de pagamento com valor."
    }

    return null
  }

  async function handleCreateSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setSuccessMessage(null)

    const validationMessage = validateForm()
    if (validationMessage) {
      setErrorMessage(validationMessage)
      return
    }

    setIsSubmitting(true)
    try {
      const response = await createSale(buildSalePayload({ ...form, company_id: activeCompanyId }))
      setSuccessMessage("Venda criada em rascunho com sucesso.")
      setForm(createInitialForm(saleType, activeCompanyId))
      await refreshSales()
      await loadSaleDetails(response.data.id)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Erro ao criar venda.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleStatusChange(action: "confirm" | "cancel") {
    if (!selectedSale) return

    setIsSubmitting(true)
    setErrorMessage(null)
    setSuccessMessage(null)

    try {
      const reason =
        action === "confirm"
          ? `Fechamento pela tela de ${config.title}.`
          : `Cancelamento pela tela de ${config.title}.`

      let lastResponse: { data: import("./types").Sale }
      if (action === "confirm") {
        lastResponse = await closeSale(selectedSale.id, { reason })
        setSuccessMessage("Venda fechada com sucesso. Recebimento deve ser baixado em Caixa e Baixas.")
      } else {
        lastResponse = await cancelSale(selectedSale.id, { reason })
        setSuccessMessage("Venda cancelada com sucesso.")
      }
      await refreshSales()
      await loadSaleDetails(lastResponse.data.id)
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Não foi possível alterar o status da venda.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleConfirmedStatusChange() {
    if (!pendingStatusAction) return

    const action = pendingStatusAction
    setPendingStatusAction(null)
    await handleStatusChange(action)
  }

  async function handleStatusFilterChange(value: SaleStatus | "all") {
    setStatusFilter(value)
    setIsLoading(true)
    setErrorMessage(null)

    try {
      const salesResponse = await getSales({
        company_id: activeCompanyId,
        sale_type: saleType,
        status: value === "all" ? undefined : value,
        limit: 50,
        offset: 0,
      })
      setSales(salesResponse.data)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Não foi possível aplicar o filtro.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-start">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)]">
              {config.icon}
              {config.badge}
            </div>

            <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)] sm:text-4xl">
              {config.title}
            </h1>

            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">
              {config.subtitle}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3 xl:min-w-[520px]">
            <MetricCard accent="#7c3aed" label="Vendas" value={String(sales.length)} helper="Carregadas na listagem" />
            <MetricCard accent="#16a34a" label="Fechadas" value={formatCurrency(salesTotals.confirmed)} helper="Títulos a receber gerados" />
            <MetricCard accent="#d97706" label="Rascunhos" value={formatCurrency(salesTotals.draft)} helper="Ainda editáveis" />
          </div>
        </div>
      </header>

      <nav className="flex flex-wrap gap-2 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2 shadow-xl shadow-[var(--color-card-shadow)]">
        <TabButton active={activeTab === "overview"} label="Visão geral" onClick={() => setActiveTab("overview")} />
        <TabButton active={activeTab === "list"} label="Listagem" onClick={() => setActiveTab("list")} />
        <NewSaleButton active={activeTab === "create"} onClick={() => setActiveTab("create")} />
        <TabButton active={activeTab === "detail"} disabled={!selectedSale} label="Detalhe" onClick={() => setActiveTab("detail")} />
        <button type="button" onClick={() => void refreshSales()} className="ml-auto flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition-all hover:bg-[var(--color-hover)]">
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Atualizar
        </button>
      </nav>

      {errorMessage ? <AlertMessage tone="error" message={errorMessage} onClose={() => setErrorMessage(null)} /> : null}
      {successMessage ? <AlertMessage tone="success" message={successMessage} onClose={() => setSuccessMessage(null)} /> : null}

      {activeTab === "overview" ? (
        <OverviewPanel itemPlural={config.itemPlural} activeCustomers={activeCustomers.length} activeItems={activeItems.length} totalSales={sales.length} />
      ) : null}

      {activeTab === "list" ? (
        <ListPanel sales={sales} statusFilter={statusFilter} isLoading={isLoading} onStatusFilterChange={(value) => void handleStatusFilterChange(value)} onOpenSale={(saleId) => void loadSaleDetails(saleId)} />
      ) : null}

      {activeTab === "create" ? (
        <CreatePanel
          saleType={saleType}
          activeCompanyId={activeCompanyId}
          activeCompany={activeCompany}
          customers={activeCustomers}
          items={activeItems}
          stockAvailability={stockAvailability}
          stockAvailabilityLoaded={stockAvailabilityLoaded}
          itemReadiness={itemReadiness}
          itemReadinessLoaded={itemReadinessLoaded}
          paymentMethods={paymentMethods}
          form={form}
          estimatedTotal={estimatedTotal}
          isSubmitting={isSubmitting}
          onSubmit={(event) => void handleCreateSale(event)}
          onFieldChange={updateFormField}
          onLineChange={updateLineItem}
          onAddLine={addLineItem}
          onRemoveLine={removeLineItem}
        />
      ) : null}

      {activeTab === "detail" ? (
        <DetailPanel
          sale={selectedSale}
          statusHistory={statusHistory}
          auditEvents={auditEvents}
          isSubmitting={isSubmitting}
          readiness={readiness}
          readinessLoading={readinessLoading}
          fiscalDocuments={fiscalDocuments}
          onConfirm={() => setPendingStatusAction("confirm")}
          onCancel={() => setPendingStatusAction("cancel")}
          onRevalidateReadiness={() => selectedSale && void loadReadiness(selectedSale.id)}
          onGeneratePdf={() => selectedSale && void handleGeneratePdf(selectedSale.id)}
          onGenerateEspelhoNFe={() => selectedSale && void handleGenerateEspelhoNFe(selectedSale.id)}
          onEmitInvoice={() => selectedSale && void handleEmitInvoice(selectedSale.id)}
        />
      ) : null}

      <StatusConfirmationModal
        action={pendingStatusAction}
        sale={selectedSale}
        isSubmitting={isSubmitting}
        onClose={() => setPendingStatusAction(null)}
        onConfirm={() => void handleConfirmedStatusChange()}
      />
    </div>
  )
}

function MetricCard({ label, value, helper, accent }: { label: string; value: string; helper: string; accent?: string }) {
  if (accent) {
    return (
      <div className="rounded-3xl p-4" style={{ background: accent, border: `1px solid ${accent}` }}>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/75">{label}</p>
        <p className="mt-2 text-xl font-bold text-white">{value}</p>
        <p className="mt-1 text-xs text-white/65">{helper}</p>
      </div>
    )
  }
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-weak)]">{label}</p>
      <p className="mt-2 text-xl font-bold text-[var(--color-text)]">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{helper}</p>
    </div>
  )
}


function TabButton({ active, disabled = false, label, onClick }: { active: boolean; disabled?: boolean; label: string; onClick: () => void }) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className={`rounded-2xl px-4 py-2 text-sm font-semibold transition-all ${active ? "border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : disabled ? "cursor-not-allowed text-[var(--color-text-weak)] opacity-50" : "text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"}`}>
      {label}
    </button>
  )
}

function NewSaleButton({ active, onClick }: { active: boolean; onClick: () => void }) {
  const className = active
    ? "inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-bold text-[var(--color-primary)] shadow-lg shadow-[var(--color-card-shadow)]"
    : "inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-2 text-sm font-black text-white shadow-md transition-all hover:-translate-y-0.5 hover:bg-[var(--color-primary-hover)]"

  return (
    <button type="button" onClick={onClick} className={className}>
      <Plus className="h-4 w-4" />
      Nova venda
    </button>
  )
}

function AlertMessage({ tone, message, onClose }: { tone: "error" | "success"; message: string; onClose: () => void }) {
  const toneClass = tone === "error"
    ? "border-rose-400/80 bg-rose-500/15 text-rose-800 shadow-lg shadow-rose-950/10 dark:text-rose-100"
    : "border-emerald-400/80 bg-emerald-500/15 text-emerald-800 shadow-lg shadow-emerald-950/10 dark:text-emerald-100"

  return (
    <div className={`flex items-start justify-between gap-3 rounded-3xl border p-4 ${toneClass}`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 rounded-2xl p-2 ${tone === "error" ? "bg-rose-600 text-white" : "bg-emerald-600 text-white"}`}>
          {tone === "error" ? <AlertCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
        </div>
        <p className="pt-1 text-sm font-bold">{message}</p>
      </div>
      <button type="button" onClick={onClose} aria-label="Fechar mensagem" className="rounded-full p-1 hover:bg-black/10"><X className="h-4 w-4" /></button>
    </div>
  )
}

function StatusBadge({ status }: { status: SaleStatus }) {
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${statusClasses[status]}`}>{statusLabels[status]}</span>
}

function StatusConfirmationModal({
  action,
  sale,
  isSubmitting,
  onClose,
  onConfirm,
}: {
  action: "confirm" | "cancel" | null
  sale: Sale | null
  isSubmitting: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  if (!action || !sale) return null

  const isConfirm = action === "confirm"
  const title = isConfirm ? "Fechar venda?" : "Cancelar venda?"
  const description = isConfirm
    ? "A venda será fechada, o estoque será baixado quando aplicável e os títulos a receber serão gerados. O recebimento deve ser baixado em Caixa e Baixas."
    : "O cancelamento altera o status da venda e fica registrado no histórico e na auditoria. Use apenas quando a operação não deve seguir."
  const primaryLabel = isConfirm ? "Sim, fechar venda" : "Sim, cancelar venda"
  const toneClass = isConfirm
    ? "border-emerald-400/70 bg-emerald-600 text-white hover:bg-emerald-700"
    : "border-rose-400/70 bg-rose-600 text-white hover:bg-rose-700"
  const iconBoxClass = isConfirm
    ? "border-emerald-300/70 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200"
    : "border-rose-300/70 bg-rose-500/15 text-rose-700 dark:text-rose-200"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="sale-status-confirmation-title">
      <div className="w-full max-w-lg rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-2xl shadow-slate-950/30">
        <div className="flex items-start gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border ${iconBoxClass}`}>
            {isConfirm ? <BadgeCheck className="h-6 w-6" /> : <Ban className="h-6 w-6" />}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-[var(--color-text-weak)]">
              Confirmação obrigatória
            </p>
            <h3 id="sale-status-confirmation-title" className="mt-1 text-xl font-black text-[var(--color-text)]">
              {title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
              {description}
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">Venda selecionada</p>
          <p className="mt-2 break-all font-mono text-xs text-[var(--color-text-muted)]">{sale.id}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-xs font-semibold text-[var(--color-text-weak)]">Cliente</p>
              <p className="text-sm font-bold text-[var(--color-text)]">{getSnapshotText(sale.participant_snapshot, "name")}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-[var(--color-text-weak)]">Total</p>
              <p className="text-sm font-bold text-[var(--color-text)]">{formatCurrency(sale.total_amount)}</p>
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-3 text-sm font-bold text-[var(--color-text)] transition-all hover:bg-[var(--color-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Voltar e revisar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className={`inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-black transition-all disabled:cursor-not-allowed disabled:opacity-60 ${toneClass}`}
          >
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : isConfirm ? <BadgeCheck className="h-4 w-4" /> : <Ban className="h-4 w-4" />}
            {primaryLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

function OverviewPanel({ itemPlural, activeCustomers, activeItems, totalSales }: { itemPlural: string; activeCustomers: number; activeItems: number; totalSales: number }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
      <h2 className="text-xl font-bold text-[var(--color-text)]">Visão geral</h2>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <MetricCard accent="#16a34a" label="Clientes ativos" value={String(activeCustomers)} helper="Disponíveis para seleção" />
        <MetricCard accent="#2563eb" label={`${itemPlural} ativos`} value={String(activeItems)} helper="Com preço e cadastro" />
        <MetricCard accent="#7c3aed" label="Vendas carregadas" value={String(totalSales)} helper="Exibidas na listagem" />
      </div>
    </section>
  )
}


function StockAvailabilityNotice({ isLoaded, totalProducts, stockValidationMessage }: { isLoaded: boolean; totalProducts: number; stockValidationMessage: string | null }) {
  if (!isLoaded) {
    return (
      <div className="flex items-start gap-3 rounded-3xl border border-sky-300/60 bg-sky-500/10 p-4 text-sm text-sky-800 dark:text-sky-100">
        <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
        <div>
          <p className="font-bold">Consultando estoque efetivo...</p>
          <p className="mt-1 text-xs opacity-80">A venda de produto só libera seleção depois de consultar o saldo do local padrão.</p>
        </div>
      </div>
    )
  }

  if (stockValidationMessage) {
    return (
      <div className="flex items-start gap-3 rounded-3xl border border-amber-300/70 bg-amber-500/10 p-4 text-sm text-amber-800 dark:text-amber-100">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-bold">Estoque impede avanço da venda</p>
          <p className="mt-1 text-xs opacity-90">{stockValidationMessage}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 rounded-3xl border border-emerald-300/60 bg-emerald-500/10 p-4 text-sm text-emerald-800 dark:text-emerald-100">
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-bold">Seleção limitada a produtos vendáveis</p>
        <p className="mt-1 text-xs opacity-90">{totalProducts} produto(s) disponível(is) para seleção. Produtos sem saldo efetivo ficam fora da busca.</p>
      </div>
    </div>
  )
}

function StockLineStatus({ item, requestedQuantity, availability }: { item: CatalogItem; requestedQuantity: number; availability?: StockItemAvailability }) {
  if (!itemTracksStock(item)) {
    return (
      <div className="mt-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-2 text-xs font-semibold text-[var(--color-text-muted)]">
        Este produto não controla estoque no cadastro.
      </div>
    )
  }

  if (itemAllowsNegativeStock(item)) {
    return (
      <div className="mt-3 rounded-2xl border border-amber-300/60 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-800 dark:text-amber-100">
        Produto permite estoque negativo. Saldo atual: {availability ? `${formatQuantity(availability.available_quantity)} ${availability.unit}` : "não carregado"}.
      </div>
    )
  }

  if (!availability) {
    return (
      <div className="mt-3 rounded-2xl border border-rose-300/60 bg-rose-500/10 px-3 py-2 text-xs font-semibold text-rose-800 dark:text-rose-100">
        Disponibilidade de estoque não carregada para este produto.
      </div>
    )
  }

  const availableQuantity = parseDecimal(availability.available_quantity)
  const exceedsStock = requestedQuantity > availableQuantity

  return (
    <div className={`mt-3 rounded-2xl border px-3 py-2 text-xs font-semibold ${exceedsStock ? "border-rose-300/60 bg-rose-500/10 text-rose-800 dark:text-rose-100" : "border-emerald-300/60 bg-emerald-500/10 text-emerald-800 dark:text-emerald-100"}`}>
      Saldo efetivo: {formatQuantity(availableQuantity)} {availability.unit} em {availability.location_name}.
      {exceedsStock ? ` Quantidade solicitada: ${formatQuantity(requestedQuantity)} ${availability.unit}.` : ""}
    </div>
  )
}

function ListPanel({ sales, statusFilter, isLoading, onStatusFilterChange, onOpenSale }: { sales: Sale[]; statusFilter: SaleStatus | "all"; isLoading: boolean; onStatusFilterChange: (value: SaleStatus | "all") => void; onOpenSale: (saleId: string) => void }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
      <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h2 className="text-xl font-bold text-[var(--color-text)]">Listagem de vendas</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">Resumo leve, filtrado por tipo de venda e status.</p>
        </div>
        <select value={statusFilter} onChange={(event) => onStatusFilterChange(event.target.value as SaleStatus | "all")} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm text-[var(--color-text)] outline-none">
          <option value="all">Todos os status</option>
          <option value="quote">Orçamento</option>
          <option value="closed">Fechado</option>
          <option value="paid">Pago</option>
          <option value="cancelled">Cancelada</option>
          <option value="draft">Rascunho (legado)</option>
          <option value="confirmed">Confirmada (legado)</option>
        </select>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center rounded-3xl border border-[var(--color-border-soft)] p-10 text-[var(--color-text-muted)]"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Carregando vendas...</div>
      ) : sales.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-[var(--color-border-soft)] p-10 text-center text-sm text-[var(--color-text-muted)]">Nenhuma venda encontrada para o filtro atual.</div>
      ) : (
        <div className="overflow-hidden rounded-3xl border border-[var(--color-border-soft)]">
          <div className="hidden grid-cols-[1.2fr_1fr_1fr_1fr_0.8fr] gap-3 bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)] lg:grid">
            <span>ID</span><span>Cliente</span><span>Status</span><span>Total</span><span>Ações</span>
          </div>
          <div className="divide-y divide-[var(--color-border-soft)]">
            {sales.map((sale) => (
              <article key={sale.id} className="grid gap-3 px-4 py-4 lg:grid-cols-[1.2fr_1fr_1fr_1fr_0.8fr] lg:items-center">
                <div><p className="font-mono text-xs text-[var(--color-text-muted)]">{sale.id}</p><p className="mt-1 text-xs text-[var(--color-text-weak)]">Criada em {formatDateTime(sale.created_at)}</p></div>
                <div><p className="text-sm font-semibold text-[var(--color-text)]">{getSnapshotText(sale.participant_snapshot, "name")}</p><p className="text-xs text-[var(--color-text-muted)]">{getSnapshotText(sale.participant_snapshot, "document")}</p></div>
                <StatusBadge status={sale.status} />
                <p className="text-sm font-bold text-[var(--color-text)]">{formatCurrency(sale.total_amount)}</p>
                <button type="button" onClick={() => onOpenSale(sale.id)} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] hover:bg-[var(--color-hover)]"><Eye className="h-4 w-4" />Abrir</button>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

type SaleWizardStep = "operation" | "items" | "review"

type CreatePanelProps = {
  saleType: SaleType
  activeCompanyId: string
  activeCompany: Company | null
  customers: Participant[]
  items: CatalogItem[]
  stockAvailability: StockAvailabilityMap
  stockAvailabilityLoaded: boolean
  itemReadiness: SaleItemReadinessMap
  itemReadinessLoaded: boolean
  paymentMethods: PaymentMethod[]
  form: SaleFormState
  estimatedTotal: number
  isSubmitting: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onFieldChange: <Field extends keyof SaleFormState>(field: Field, value: SaleFormState[Field]) => void
  onLineChange: (localId: string, field: keyof FormLineItem, value: string) => void
  onAddLine: () => void
  onRemoveLine: (localId: string) => void
}

function CreatePanel({ saleType, activeCompanyId, activeCompany, customers, items, stockAvailability, stockAvailabilityLoaded, itemReadiness, itemReadinessLoaded, paymentMethods, form, estimatedTotal, isSubmitting, onSubmit, onFieldChange, onLineChange, onAddLine, onRemoveLine }: CreatePanelProps) {
  const config = saleTypeConfig[saleType]
  const activeUser = getActiveUser()
  const [currentStep, setCurrentStep] = useState<SaleWizardStep>("operation")
  const operationNature = operationNatureOptions.find((option) => option.value === form.operation_nature) ?? operationNatureOptions[0]
  const lineSummaries = form.items.map((line) => {
    const selectedItem = items.find((item) => item.id === line.item_id)
    const quantity = parseDecimal(line.quantity)
    const unitPrice = parseDecimal(line.unit_price)
    const grossAmount = quantity * unitPrice
    const discountAmount = parseDecimal(line.discount_amount)
    const lineTotal = Math.max(0, grossAmount - discountAmount)

    return {
      local_id: line.local_id,
      name: selectedItem?.name ?? config.itemLabel + " não selecionado",
      code: selectedItem?.sku || selectedItem?.barcode || selectedItem?.id || "—",
      quantity,
      unit: line.unit || selectedItem?.unit || "UN",
      unitPrice,
      grossAmount,
      discountAmount,
      lineTotal,
      selected: Boolean(line.item_id),
    }
  })
  const selectedLineSummaries = lineSummaries.filter((line) => line.selected)
  const subtotal = lineSummaries.reduce((total, line) => total + line.lineTotal, 0)
  const discount = calculateDiscountAmount(form, subtotal)
  const discountInputLabel = form.discount_type === "percentage" ? "Percentual do desconto" : "Valor do desconto"
  const discountInputHelper = form.discount_type === "percentage"
    ? `Calculado agora: ${formatCurrency(discount)} sobre ${formatCurrency(subtotal)}.`
    : "Valor fixo abatido do total comercial."
  const totalToInvoice = Math.max(estimatedTotal, 0)
  const totalToReceive = ["normal_sale", "other"].includes(form.operation_nature) ? totalToInvoice : 0
  const fiscalStatusPreview = selectedLineSummaries.length > 0 ? "Pré-validação fiscal no backend" : "Selecione itens para validar"
  const selectedItemsCount = selectedLineSummaries.length
  const readinessValidationMessage = validateItemReadinessForForm(form, items, itemReadiness, itemReadinessLoaded)
  const stockValidationMessage = readinessValidationMessage ?? validateStockForForm(form, items, stockAvailability, stockAvailabilityLoaded)
  const canContinueOperation = !operationNatureRequiresReason(form.operation_nature) || Boolean(form.operation_nature_reason.trim())
  const hasParticipant = form.origin === "pdv" || Boolean(form.participant_id)
  const canContinueItems = hasParticipant && form.items.some((item) => item.item_id && parseDecimal(item.quantity) > 0) && !stockValidationMessage
  const paymentTotal = form.payment_plans.reduce((total, plan) => total + parseDecimal(plan.amount), 0)
  const paymentRemaining = totalToReceive - paymentTotal
  const paymentIsBalanced = Math.abs(paymentRemaining) <= 0.009

  function updatePaymentLine(localId: string, field: keyof FormPaymentLine, value: string) {
    onFieldChange(
      "payment_plans",
      form.payment_plans.map((plan) => {
        if (plan.local_id !== localId) return plan

        if (field === "payment_method_code") {
          return { ...plan, payment_method_code: value as PaymentMethodCode }
        }

        if (field === "amount") return { ...plan, amount: value }
        if (field === "due_date") return { ...plan, due_date: value }
        if (field === "installments") return { ...plan, installments: value }
        if (field === "notes") return { ...plan, notes: value }

        return plan
      }),
    )
  }

  function addPaymentLine() {
    const remaining = Math.max(paymentRemaining, 0)
    onFieldChange("payment_plans", [...form.payment_plans, createEmptyPaymentLine(toMoneyPayload(remaining), form.issue_date)])
  }

  function removePaymentLine(localId: string) {
    onFieldChange(
      "payment_plans",
      form.payment_plans.length === 1
        ? form.payment_plans
        : form.payment_plans.filter((plan) => plan.local_id !== localId),
    )
  }

  function goToItems() {
    if (canContinueOperation) {
      setCurrentStep("items")
    }
  }

  function goToReview() {
    if (canContinueItems) {
      setCurrentStep("review")
    }
  }

  useEffect(() => {
    if (currentStep !== "review") return
    if (totalToReceive <= 0) return
    if (form.payment_plans.length !== 1) return
    const onlyPlan = form.payment_plans[0]
    if (parseDecimal(onlyPlan.amount) > 0) return
    onFieldChange("payment_plans", [{ ...onlyPlan, amount: toMoneyPayload(totalToReceive), due_date: onlyPlan.due_date || form.issue_date }])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, totalToReceive])

  return (
    <form onSubmit={onSubmit} className="space-y-5 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-6">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-xl font-bold text-[var(--color-text)]">Nova venda de {config.label}</h2>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">Preencha operação, {config.itemPlural.toLowerCase()} e revisão de pagamento.</p>
        </div>
        <div className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm text-[var(--color-primary)]">
          <strong>{formatCurrency(totalToInvoice)}</strong>
          <span className="ml-2 text-xs opacity-80">Total previsto para documento</span>
        </div>
      </div>

      <WizardStepper currentStep={currentStep} />

      {currentStep === "operation" ? (
        <section className="space-y-4 rounded-[1.75rem] border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
          <div className="grid gap-3 lg:grid-cols-3">
            <SessionCard icon={<UserRound className="h-5 w-5" />} label="Usuário conectado" title={activeUser.name} helper={activeUser.role} />
            <SessionCard icon={<Database className="h-5 w-5" />} label="Empresa ativa" title={activeCompany?.trade_name || activeCompany?.legal_name || "Empresa teste Kovir"} helper={activeCompanyId} />
            <SessionCard icon={config.icon} label="Tipo de operação" title={saleType === "product" ? "Venda de produto" : "Venda de serviço"} helper={saleType === "product" ? "Produtos físicos com estoque" : "Prestação de serviços"} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            <Field label="Natureza da operação">
              <select value={form.operation_nature} onChange={(event) => onFieldChange("operation_nature", event.target.value as SaleOperationNature)} className="field-input">
                {operationNatureOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </Field>
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-3 text-sm text-[var(--color-text-muted)]">
              <strong className="block text-[var(--color-text)]">{operationNature.label}</strong>
              <span>{operationNature.helper}</span>
            </div>
          </div>

          {operationNatureRequiresReason(form.operation_nature) ? (
            <Field label="Motivo da natureza da operação">
              <input value={form.operation_nature_reason} onChange={(event) => onFieldChange("operation_nature_reason", event.target.value)} className="field-input" placeholder="Ex.: bonificação autorizada para cliente estratégico" />
            </Field>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Emissão"><input type="date" value={form.issue_date} onChange={(event) => onFieldChange("issue_date", event.target.value)} className="field-input" /></Field>
            <Field label="Competência"><input type="date" value={form.competency_date} onChange={(event) => onFieldChange("competency_date", event.target.value)} className="field-input" /></Field>
          </div>

          <WizardActions canGoNext={canContinueOperation} nextLabel="Continuar para cliente e itens" nextHelper={canContinueOperation ? "Operação definida." : "Informe o motivo para continuar."} onNext={goToItems} />
        </section>
      ) : null}

      {currentStep === "items" ? (
        <section className="space-y-4 rounded-[1.75rem] border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
          <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
            <div>
              <h3 className="text-lg font-bold text-[var(--color-text)]">Cliente e {config.itemPlural.toLowerCase()}</h3>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">Selecione o cliente e ao menos um {config.label}.</p>
            </div>
            <button type="button" onClick={onAddLine} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-primary)] hover:bg-[var(--color-hover)]"><Plus className="h-4 w-4" />Adicionar {config.label}</button>
          </div>

          {saleType === "product" ? (
            <StockAvailabilityNotice
              isLoaded={stockAvailabilityLoaded && itemReadinessLoaded}
              totalProducts={items.length}
              stockValidationMessage={stockValidationMessage}
            />
          ) : null}

          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3">
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                checked={form.origin === "pdv"}
                onChange={(e) => {
                  onFieldChange("origin", e.target.checked ? "pdv" : "manual")
                  if (e.target.checked) onFieldChange("participant_id", "")
                }}
                className="h-5 w-5 accent-sky-500"
              />
              <div>
                <span className="text-sm font-bold text-[var(--color-text)]">Consumidor Final</span>
                <span className="ml-2 text-xs text-[var(--color-text-muted)]">PDV — venda sem identificar cliente</span>
              </div>
            </label>
          </div>

          {form.origin !== "pdv" ? (
            <Field label="Para qual cliente estou vendendo?">
              <SearchableSelect value={form.participant_id} options={buildCustomerOptions(customers)} placeholder="Digite nome, documento ou e-mail" searchPlaceholder="Pesquisar cliente ativo..." emptyMessage="Nenhum cliente ativo encontrado." required onChange={(value) => onFieldChange("participant_id", value)} />
            </Field>
          ) : null}

          <div className="space-y-3">
            {form.items.map((line, index) => {
              const selectedItem = items.find((item) => item.id === line.item_id)
              const lockedPrice = selectedItem?.financial_settings?.default_sale_price ?? line.unit_price ?? "0"

              const lineQty = parseDecimal(line.quantity)
              const lineGross = lineQty * parseDecimal(lockedPrice)
              const lineDisc = parseDecimal(line.discount_amount)
              const lineNet = Math.max(0, lineGross - lineDisc)

              return (
                <div key={line.local_id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-3">
                  <div className="grid gap-3 xl:grid-cols-[minmax(220px,1.7fr)_90px_110px_130px_130px_44px] xl:items-end">
                    <Field label={config.itemLabel + " " + (index + 1)}><SearchableSelect value={line.item_id} options={buildItemOptions(items, config.itemLabel, stockAvailability, itemReadiness)} placeholder="Digite o nome, SKU ou código" searchPlaceholder={"Pesquisar " + config.label + "..."} emptyMessage={"Nenhum " + config.label + " ativo encontrado."} required onChange={(value) => onLineChange(line.local_id, "item_id", value)} /></Field>
                    <Field label="Qtd."><input value={line.quantity} onChange={(event) => onLineChange(line.local_id, "quantity", normalizeNumericInput(event.target.value))} className="field-input" inputMode="decimal" /></Field>
                    <Field label="Unidade"><input value={line.unit} readOnly className="field-input cursor-not-allowed opacity-80" /></Field>
                    <Field label="Preço unitário"><input value={lockedPrice} readOnly className="field-input cursor-not-allowed opacity-80" aria-readonly="true" /></Field>
                    <Field label="Desc. por item (R$)"><input value={line.discount_amount} onChange={(event) => onLineChange(line.local_id, "discount_amount", normalizeNumericInput(event.target.value))} className="field-input" inputMode="decimal" placeholder="0,00" /></Field>
                    <button type="button" onClick={() => onRemoveLine(line.local_id)} className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-border-soft)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]" aria-label="Remover item"><X className="h-4 w-4" /></button>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-4">
                    <p className="text-xs text-[var(--color-text-muted)]">
                      {selectedItem ? <>Preço carregado do cadastro: {formatCurrency(lockedPrice)}.</> : <>Selecione um {config.label} para carregar unidade e preço.</>}
                    </p>
                    {selectedItem && lineQty > 0 ? (
                      <p className="shrink-0 text-sm font-bold text-[var(--color-text)]">
                        Total: {formatCurrency(lineNet)}{lineDisc > 0 ? <span className="ml-1 text-xs font-normal text-amber-600">−{formatCurrency(lineDisc)}</span> : null}
                      </p>
                    ) : null}
                  </div>
                  {saleType === "product" && selectedItem ? (
                    <StockLineStatus
                      item={selectedItem}
                      requestedQuantity={parseDecimal(line.quantity)}
                      availability={stockAvailability[selectedItem.id]}
                    />
                  ) : null}
                </div>
              )
            })}
          </div>

          <WizardActions canGoNext={canContinueItems} nextLabel="Revisar valores e criar venda" nextHelper={canContinueItems ? (form.origin === "pdv" ? "Consumidor Final, item e estoque validados." : "Cliente, item e estoque validados.") : stockValidationMessage ?? (form.origin === "pdv" ? "Selecione ao menos um " + config.label + "." : "Selecione cliente e ao menos um " + config.label + ".")} onBack={() => setCurrentStep("operation")} onNext={goToReview} />
        </section>
      ) : null}

      {currentStep === "review" ? (
        <section className="space-y-4 rounded-[1.75rem] border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
          <div>
            <h3 className="text-lg font-bold text-[var(--color-text)]">Revisão da venda</h3>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">Confira descontos, observações e totais antes de criar o rascunho da venda.</p>
          </div>

          <div className={`rounded-3xl border p-4 transition-all ${form.has_discount ? "border-amber-300/70 bg-amber-500/10" : "border-[var(--color-border-soft)] bg-[var(--color-surface)]"}`}>
            <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
              <label className="flex items-center gap-3 text-sm font-bold text-[var(--color-text)]"><input type="checkbox" checked={form.has_discount} onChange={(event) => onFieldChange("has_discount", event.target.checked)} className="h-5 w-5 accent-amber-500" />Tem desconto?</label>
              <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${form.has_discount ? "border-amber-300/70 bg-amber-500/20 text-amber-800 dark:text-amber-100" : "border-[var(--color-border-soft)] text-[var(--color-text-muted)]"}`}>
                {form.has_discount ? `Desconto aplicado: ${formatCurrency(discount)}` : "Sem desconto nesta venda"}
              </span>
            </div>
            {form.has_discount ? (
              <div className="mt-4 space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <DiscountTypeButton active={form.discount_type === "amount"} title="Valor em R$" helper="Desconto fixo" onClick={() => { onFieldChange("discount_type", "amount"); onFieldChange("discount_percentage", "") }} />
                  <DiscountTypeButton active={form.discount_type === "percentage"} title="Porcentagem %" helper="Calculado sobre o subtotal" onClick={() => { onFieldChange("discount_type", "percentage"); onFieldChange("discount_amount", "0") }} />
                </div>

                <div className="grid gap-4 lg:grid-cols-[0.8fr_1fr_1.2fr]">
                  <Field label={discountInputLabel}>
                    <div className="relative">
                      {form.discount_type === "percentage" ? <Percent className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-amber-600" /> : <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-black text-amber-700">R$</span>}
                      <input
                        value={form.discount_type === "percentage" ? form.discount_percentage : form.discount_amount}
                        onChange={(event) => form.discount_type === "percentage" ? onFieldChange("discount_percentage", normalizeNumericInput(event.target.value)) : onFieldChange("discount_amount", normalizeNumericInput(event.target.value))}
                        className="field-input"
                        style={{ paddingLeft: "3rem" }}
                        inputMode="decimal"
                        placeholder={form.discount_type === "percentage" ? "Ex.: 10" : "Ex.: 25,00"}
                      />
                    </div>
                    <p className="mt-1 text-xs font-semibold text-amber-700 dark:text-amber-200">{discountInputHelper}</p>
                  </Field>
                  <Field label="Categoria do desconto"><select value={form.discount_category} onChange={(event) => onFieldChange("discount_category", event.target.value as DiscountCategory | "")} className="field-input"><option value="">Selecione...</option>{discountCategories.map((category) => <option key={category.value} value={category.value}>{category.label}</option>)}</select></Field>
                  <Field label="Motivo do desconto"><input value={form.discount_reason} onChange={(event) => onFieldChange("discount_reason", event.target.value)} className="field-input" placeholder="Ex.: cupom do cliente, negociação autorizada..." /></Field>
                </div>
              </div>
            ) : null}
          </div>

          <PaymentPlanPanel
            paymentMethods={paymentMethods}
            paymentPlans={form.payment_plans}
            totalToReceive={totalToReceive}
            paymentTotal={paymentTotal}
            paymentRemaining={paymentRemaining}
            paymentIsBalanced={paymentIsBalanced}
            onPaymentChange={updatePaymentLine}
            onAddPayment={addPaymentLine}
            onRemovePayment={removePaymentLine}
          />

          <SaleSummaryCard saleType={saleType} operationNatureLabel={operationNature.label} lineSummaries={selectedLineSummaries.length ? selectedLineSummaries : lineSummaries} selectedItemsCount={selectedItemsCount} subtotal={subtotal} discount={discount} discountType={form.discount_type} discountPercentage={form.discount_percentage} totalToInvoice={totalToInvoice} totalToReceive={totalToReceive} fiscalStatusPreview={fiscalStatusPreview} />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Frete (R$)">
              <input
                value={form.freight_amount}
                onChange={(event) => onFieldChange("freight_amount", normalizeNumericInput(event.target.value))}
                className="field-input"
                inputMode="decimal"
                placeholder="0,00"
              />
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">Frete cobrado no pedido.</p>
            </Field>
            <Field label="Observações"><textarea value={form.notes} onChange={(event) => onFieldChange("notes", event.target.value)} className="field-input min-h-20" /></Field>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <button type="button" onClick={() => setCurrentStep("items")} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-5 py-3 text-sm font-bold text-[var(--color-text)] transition-all hover:bg-[var(--color-hover)]"><ArrowLeft className="h-4 w-4" />Voltar para itens</button>
            <button type="submit" disabled={isSubmitting || Boolean(stockValidationMessage)} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-bold text-white transition-all hover:-translate-y-0.5 hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-60">{isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Criar venda em rascunho</button>
          </div>
        </section>
      ) : null}
    </form>
  )
}

function getPaymentMethodName(methods: PaymentMethod[], code: PaymentMethodCode) {
  return methods.find((method) => method.code === code)?.name ?? paymentMethodFallbackLabels[code] ?? code
}

function PaymentPlanPanel({
  paymentMethods,
  paymentPlans,
  totalToReceive,
  paymentTotal,
  paymentRemaining,
  paymentIsBalanced,
  onPaymentChange,
  onAddPayment,
  onRemovePayment,
}: {
  paymentMethods: PaymentMethod[]
  paymentPlans: FormPaymentLine[]
  totalToReceive: number
  paymentTotal: number
  paymentRemaining: number
  paymentIsBalanced: boolean
  onPaymentChange: (localId: string, field: keyof FormPaymentLine, value: string) => void
  onAddPayment: () => void
  onRemovePayment: (localId: string) => void
}) {
  const hasReceivable = totalToReceive > 0
  const methodOptions = paymentMethods.length > 0 ? paymentMethods : paymentMethodFallbackOptions
  const paymentTone = !hasReceivable
    ? "border-sky-300/60 bg-sky-500/10 text-sky-800 dark:text-sky-100"
    : paymentIsBalanced
      ? "border-emerald-300/60 bg-emerald-500/10 text-emerald-800 dark:text-emerald-100"
      : "border-amber-300/70 bg-amber-500/10 text-amber-900 dark:text-amber-100"

  return (
    <section className="rounded-[1.75rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-sky-300/60 bg-sky-500/10 px-3 py-1 text-xs font-black uppercase tracking-[0.14em] text-sky-700 dark:text-sky-200">
            <CreditCard className="h-4 w-4" />
            Formas de pagamento
          </div>
          <h3 className="text-lg font-black text-[var(--color-text)]">Como o cliente vai pagar?</h3>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Use uma ou mais formas de pagamento para esta venda.
          </p>
        </div>
        <div className={`rounded-2xl border px-4 py-3 text-sm font-bold ${paymentTone}`}>
          {hasReceivable ? (
            paymentIsBalanced ? "Plano financeiro fechado" : `Falta/Excede: ${formatCurrency(paymentRemaining)}`
          ) : "Sem valor a receber"}
        </div>
      </div>

      {hasReceivable ? (
        <div className="mt-4 space-y-3">
          {paymentPlans.map((plan, index) => (
            <div key={plan.local_id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3">
              <div className="grid gap-3 xl:grid-cols-[1.2fr_130px_150px_120px_44px] xl:items-end">
                <Field label={`Forma ${index + 1}`}>
                  <select
                    value={plan.payment_method_code}
                    onChange={(event) => onPaymentChange(plan.local_id, "payment_method_code", event.target.value)}
                    className="field-input"
                  >
                    {methodOptions.map((method) => (
                      <option key={method.id} value={method.code}>{method.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Valor">
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-xs font-black text-emerald-700">R$</span>
                    <input value={plan.amount} onChange={(event) => onPaymentChange(plan.local_id, "amount", normalizeNumericInput(event.target.value))} className="field-input" style={{ paddingLeft: "3rem" }} inputMode="decimal" />
                  </div>
                </Field>
                <Field label="Vencimento previsto"><input type="date" value={plan.due_date} onChange={(event) => onPaymentChange(plan.local_id, "due_date", event.target.value)} className="field-input" /></Field>
                <Field label="Parcelas"><input value={plan.installments} onChange={(event) => onPaymentChange(plan.local_id, "installments", normalizeNumericInput(event.target.value))} className="field-input" inputMode="numeric" /></Field>
                <button type="button" onClick={() => onRemovePayment(plan.local_id)} className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-border-soft)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]" aria-label="Remover forma de pagamento"><X className="h-4 w-4" /></button>
              </div>
              <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                {getPaymentMethodName(methodOptions, plan.payment_method_code)}
              </p>
            </div>
          ))}

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <button type="button" onClick={onAddPayment} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-sky-300/60 bg-sky-500/10 px-4 py-2 text-sm font-bold text-sky-700 hover:bg-sky-500/20 dark:text-sky-200">
              <Plus className="h-4 w-4" />
              Adicionar outra forma
            </button>
            <div className="grid gap-2 text-sm sm:grid-cols-3">
              <span className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 font-bold text-[var(--color-text)]">A receber: {formatCurrency(totalToReceive)}</span>
              <span className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 font-bold text-[var(--color-text)]">Informado: {formatCurrency(paymentTotal)}</span>
              <span className={`rounded-2xl border px-3 py-2 font-bold ${paymentIsBalanced ? "border-emerald-300/60 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200" : "border-amber-300/60 bg-amber-500/10 text-amber-800 dark:text-amber-100"}`}>Diferença: {formatCurrency(paymentRemaining)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-sky-300/60 bg-sky-500/10 p-4 text-sm font-semibold text-sky-800 dark:text-sky-100">
          Esta natureza de operação está sem valor a receber. O financeiro não deve receber plano de pagamento nesta venda.
        </div>
      )}
    </section>
  )
}

function DiscountTypeButton({ active, title, helper, onClick }: { active: boolean; title: string; helper: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border px-4 py-3 text-left transition-all ${active ? "border-amber-400/80 bg-amber-500/20 text-amber-900 shadow-md shadow-amber-950/10 dark:text-amber-50" : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"}`}
    >
      <span className="block text-sm font-black">{title}</span>
      <span className="mt-1 block text-xs font-semibold opacity-80">{helper}</span>
    </button>
  )
}

function SaleSummaryCard({ saleType, operationNatureLabel, lineSummaries, selectedItemsCount, subtotal, discount, discountType, discountPercentage, totalToInvoice, totalToReceive, fiscalStatusPreview }: { saleType: SaleType; operationNatureLabel: string; lineSummaries: Array<{ local_id: string; name: string; code: string; quantity: number; unit: string; unitPrice: number; grossAmount: number; selected: boolean }>; selectedItemsCount: number; subtotal: number; discount: number; discountType: DiscountType; discountPercentage: string; totalToInvoice: number; totalToReceive: number; fiscalStatusPreview: string }) {
  return (
    <section className="rounded-[1.75rem] border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--color-primary)]">Ficha de resumo da operação</p>
          <h3 className="mt-1 text-lg font-bold text-[var(--color-text)]">Resumo comercial, financeiro e fiscal</h3>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">Confira valores antes de confirmar a venda.</p>
        </div>
        <div className="rounded-2xl border border-emerald-300/60 bg-emerald-500/10 px-5 py-4 text-right">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">Total previsto para documento</p>
          <p className="mt-1 text-2xl font-black text-[var(--color-text)]">{formatCurrency(totalToInvoice)}</p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-6">
        <SummaryMetric label={saleType === "product" ? "Produtos" : "Serviços"} value={String(selectedItemsCount)} helper="Selecionados" />
        <SummaryMetric label="Subtotal" value={formatCurrency(subtotal)} helper="Antes dos descontos" />
        <SummaryMetric label="Descontos" value={formatCurrency(discount)} helper={discount > 0 ? (discountType === "percentage" ? `${formatPercent(discountPercentage)} sobre subtotal` : "Valor fixo") : "Sem desconto"} tone={discount > 0 ? "warning" : "neutral"} />
        <SummaryMetric label="A receber" value={formatCurrency(totalToReceive)} helper="Financeiro futuro" tone="success" />
        <SummaryMetric label="Natureza" value={operationNatureLabel} helper="Operação escolhida" />
        <SummaryMetric label="Fiscal" value={fiscalStatusPreview} helper="Pré-validação" tone="info" />
      </div>

      <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)]">
        {lineSummaries.map((line) => (
          <div key={line.local_id} className="grid gap-2 border-b border-[var(--color-border-soft)] px-4 py-3 text-sm last:border-b-0 md:grid-cols-[1fr_110px_130px_130px] md:items-center">
            <div>
              <p className="font-semibold text-[var(--color-text)]">{line.name}</p>
              <p className="text-xs text-[var(--color-text-muted)]">{line.code}</p>
            </div>
            <p className="text-[var(--color-text-muted)]">{line.quantity || 0} {line.unit}</p>
            <p className="text-[var(--color-text-muted)]">{formatCurrency(line.unitPrice)}</p>
            <p className="font-bold text-[var(--color-text)]">{formatCurrency(line.grossAmount)}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function SummaryMetric({ label, value, helper, tone = "neutral" }: { label: string; value: string; helper: string; tone?: "neutral" | "success" | "warning" | "info" }) {
  const toneClass = tone === "success"
    ? "border-emerald-300/60 bg-emerald-500/10"
    : tone === "warning"
      ? "border-amber-300/70 bg-amber-500/10"
      : tone === "info"
        ? "border-sky-300/60 bg-sky-500/10"
        : "border-[var(--color-border-soft)] bg-[var(--color-surface)]"
  return (
    <div className={`rounded-2xl border p-3 ${toneClass}`}>
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">{label}</p>
      <p className="mt-1 text-base font-bold text-[var(--color-text)]">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-text-muted)]">{helper}</p>
    </div>
  )
}

function WizardStepper({ currentStep }: { currentStep: SaleWizardStep }) {
  const steps: Array<{ key: SaleWizardStep; label: string; helper: string }> = [
    { key: "operation", label: "1. Operação", helper: "Usuário, empresa e natureza" },
    { key: "items", label: "2. Cliente e itens", helper: "Produtos/serviços e quantidades" },
    { key: "review", label: "3. Pagamento e revisão", helper: "Desconto, pagamento e totais" },
  ]
  const currentIndex = steps.findIndex((step) => step.key === currentStep)

  return (
    <div className="grid gap-3 rounded-[1.75rem] border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 md:grid-cols-3">
      {steps.map((step, index) => {
        const isActive = step.key === currentStep
        const isDone = index < currentIndex
        return (
          <div key={step.key} className={`rounded-2xl border p-3 transition-all ${isActive ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)]" : isDone ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)]" : "border-[var(--color-border-soft)] bg-[var(--color-surface)]"}`}>
            <p className={`text-sm font-bold ${isActive ? "text-[var(--color-primary)]" : "text-[var(--color-text)]"}`}>{step.label}</p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{step.helper}</p>
          </div>
        )
      })}
    </div>
  )
}

function SessionCard({ icon, label, title, helper }: { icon: ReactNode; label: string; title: string; helper: string }) {
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]">{icon}</div>
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">{label}</p>
      <p className="mt-2 text-sm font-bold text-[var(--color-text)]">{title}</p>
      <p className="mt-1 truncate text-xs text-[var(--color-text-muted)]">{helper}</p>
    </div>
  )
}

function WizardActions({ canGoNext, nextLabel, nextHelper, onNext, onBack }: { canGoNext: boolean; nextLabel: string; nextHelper: string; onNext: () => void; onBack?: () => void }) {
  return (
    <div className={`flex flex-col gap-3 rounded-3xl border p-3 md:flex-row md:items-center md:justify-between ${canGoNext ? "border-emerald-300/60 bg-emerald-500/10" : "border-amber-300/60 bg-amber-500/10"}`}>
      <p className={`text-sm font-bold ${canGoNext ? "text-emerald-700 dark:text-emerald-200" : "text-amber-800 dark:text-amber-100"}`}>{nextHelper}</p>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {onBack ? (
          <button type="button" onClick={onBack} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]">
            <ArrowLeft className="h-4 w-4" />
            Voltar
          </button>
        ) : null}
        <button type="button" onClick={onNext} disabled={!canGoNext} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-4 py-2 text-sm font-bold text-white transition-all hover:-translate-y-0.5 hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50">
          {nextLabel}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return <label className="space-y-2"><span className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">{label}</span>{children}</label>
}

function DetailPanel({ sale, statusHistory, auditEvents, isSubmitting, readiness, readinessLoading, fiscalDocuments, onConfirm, onCancel, onRevalidateReadiness, onGeneratePdf, onGenerateEspelhoNFe, onEmitInvoice }: { sale: Sale | null; statusHistory: SaleStatusHistory[]; auditEvents: SaleAuditEvent[]; isSubmitting: boolean; readiness: FiscalInvoiceReadiness | null; readinessLoading: boolean; fiscalDocuments: FiscalDocument[]; onConfirm: () => void; onCancel: () => void; onRevalidateReadiness: () => void; onGeneratePdf: () => void; onGenerateEspelhoNFe: () => void; onEmitInvoice: () => void }) {
  if (!sale) return <section className="rounded-[2rem] border border-dashed border-[var(--color-border-soft)] p-10 text-center text-sm text-[var(--color-text-muted)]">Abra uma venda pela listagem para ver detalhes.</section>
  return (
    <section className="space-y-6">
      <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <p className="font-mono text-xs text-[var(--color-text-muted)]">{sale.id}</p>
            {sale.sale_number_text && <p className="mt-1 text-sm font-bold text-[var(--color-text)]">{sale.sale_number_text}{sale.paid_number_text ? ` · ${sale.paid_number_text}` : ""}</p>}
            <h2 className="mt-2 text-2xl font-bold text-[var(--color-text)]">Venda para {getSnapshotText(sale.participant_snapshot, "name")}</h2>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">Emissão: {formatDate(sale.issue_date)} · Competência: {formatDate(sale.competency_date)}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={sale.status} />
            {INVOICE_FEATURE_ENABLED ? (
              <button type="button" onClick={onEmitInvoice} disabled={sale.status !== "confirmed" || isSubmitting} className="inline-flex items-center gap-2 rounded-2xl border border-blue-400/50 bg-blue-600 px-5 py-2 text-sm font-black tracking-wide text-white shadow-md shadow-blue-950/20 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">{isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}FATURAR</button>
            ) : (
              <button type="button" disabled title="Emissão de NF-e disponível em breve." className="inline-flex cursor-not-allowed items-center gap-2 rounded-2xl border border-blue-400/30 bg-blue-500/10 px-5 py-2 text-sm font-black tracking-wide text-blue-400 opacity-60 dark:text-blue-300"><BadgeCheck className="h-4 w-4" />FATURAR <span className="rounded-full bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest">em breve</span></button>
            )}
            {(sale.status === "confirmed" || sale.status === "closed") && (
              <button type="button" onClick={onGeneratePdf} className="inline-flex items-center gap-2 rounded-2xl border border-slate-300/40 bg-slate-500/10 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-500/20 dark:text-slate-200"><FileText className="h-4 w-4" />Prévia PDF</button>
            )}
            {sale.status === "paid" && (
              <button type="button" onClick={onGenerateEspelhoNFe} className="inline-flex items-center gap-2 rounded-2xl border border-emerald-300/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-500/20 dark:text-emerald-200"><FileText className="h-4 w-4" />Imprimir Espelho NF-e</button>
            )}
            <button type="button" onClick={onConfirm} disabled={(sale.status !== "draft" && sale.status !== "quote") || isSubmitting} className="inline-flex items-center gap-2 rounded-2xl border border-emerald-300/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:text-emerald-200"><BadgeCheck className="h-4 w-4" />PDV: Fechar e Pagar</button>
            <button type="button" onClick={onCancel} disabled={(sale.status === "cancelled" || sale.status === "paid") || isSubmitting} className="inline-flex items-center gap-2 rounded-2xl border border-rose-300/40 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50 dark:text-rose-200"><Ban className="h-4 w-4" />Cancelar</button>
          </div>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-5"><MetricCard label="Subtotal" value={formatCurrency(sale.subtotal_amount)} helper="Itens" /><MetricCard label="Descontos" value={formatCurrency(sale.discount_amount)} helper={parseDecimal(sale.discount_amount) > 0 ? `${sale.discount_type === "percentage" ? formatPercent(sale.discount_percentage) : "Valor fixo"} · ${sale.discount_category || "sem categoria"}` : "Sem desconto"} /><MetricCard label="A receber" value={formatCurrency(sale.receivable_total_amount)} helper="Financeiro futuro" /><MetricCard label="Documento" value={formatCurrency(sale.invoice_total_amount)} helper={sale.fiscal_status} /><MetricCard label="Tipo" value={sale.sale_type === "product" ? "Produto" : "Serviço"} helper={getOperationNatureLabel(sale.operation_nature)} /></div>
        {sale.payment_plans.length > 0 ? (
          <div className="mt-4 rounded-3xl border border-sky-300/60 bg-sky-500/10 p-4">
            <p className="text-xs font-black uppercase tracking-[0.14em] text-sky-700 dark:text-sky-200">Plano de pagamento previsto</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {sale.payment_plans.map((plan) => (
                <div key={plan.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-3">
                  <p className="text-sm font-black text-[var(--color-text)]">{plan.payment_method_name}</p>
                  <p className="mt-1 text-lg font-black text-[var(--color-text)]">{formatCurrency(plan.amount)}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">Venc.: {formatDate(plan.due_date)} · {plan.installments} parcela(s)</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <div className="mt-4 grid gap-4 md:grid-cols-2">{sale.operation_nature !== "normal_sale" ? <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4"><p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-text-weak)]">Motivo da natureza</p><p className="mt-2 text-sm text-[var(--color-text)]">{sale.operation_nature_reason || "—"}</p></div> : null}{parseDecimal(sale.discount_amount) > 0 ? <div className="rounded-3xl border border-amber-300/60 bg-amber-500/10 p-4"><p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-700 dark:text-amber-200">Justificativa do desconto</p><p className="mt-2 text-sm font-semibold text-[var(--color-text)]">{sale.discount_type === "percentage" ? `${formatPercent(sale.discount_percentage)} · ` : "Valor fixo · "}{sale.discount_reason || "—"}</p></div> : null}</div>
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]"><div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]"><h3 className="text-lg font-bold text-[var(--color-text)]">Itens</h3><div className="mt-4 space-y-3">{sale.items.map((item) => <div key={item.id} className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4"><p className="font-semibold text-[var(--color-text)]">{getSnapshotText(item.item_snapshot, "name")}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{item.quantity} {item.unit} × {formatCurrency(item.unit_price)}</p><p className="mt-3 text-sm font-bold text-[var(--color-text)]">Total: {formatCurrency(item.total_amount)}</p></div>)}</div></div><div className="space-y-6"><TimelinePanel statusHistory={statusHistory} /><AuditPanel auditEvents={auditEvents} /></div></div>
      {sale.status === "confirmed" && (
        <FiscalReadinessPanel
          readiness={readiness}
          readinessLoading={readinessLoading}
          fiscalDocuments={fiscalDocuments}
          onRevalidate={onRevalidateReadiness}
        />
      )}
    </section>
  )
}

function FiscalReadinessPanel({
  readiness,
  readinessLoading,
  fiscalDocuments,
  onRevalidate,
}: {
  readiness: FiscalInvoiceReadiness | null
  readinessLoading: boolean
  fiscalDocuments: FiscalDocument[]
  onRevalidate: () => void
}) {
  const scopeLabels: Record<string, string> = {
    company: "Empresa",
    participant: "Destinatário",
    item: "Itens",
    operation: "Operação",
    payment: "Pagamento",
    totals: "Totais",
    stock: "Estoque",
  }

  const docStatusLabels: Record<string, string> = {
    pending: "Pendente",
    processing: "Processando",
    authorized: "Autorizada",
    cancelled: "Cancelada",
    denied: "Denegada",
    error: "Erro",
    contingency: "Contingência",
  }

  const docStatusColors: Record<string, string> = {
    authorized: "text-emerald-700 dark:text-emerald-300",
    cancelled: "text-rose-700 dark:text-rose-300",
    denied: "text-rose-700 dark:text-rose-300",
    error: "text-rose-700 dark:text-rose-300",
    processing: "text-amber-700 dark:text-amber-300",
    pending: "text-slate-600 dark:text-slate-300",
    contingency: "text-amber-700 dark:text-amber-300",
  }

  return (
    <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BadgeCheck className="h-5 w-5 text-blue-500" />
          <h3 className="text-lg font-bold text-[var(--color-text)]">Prontidão Fiscal (NF-e)</h3>
        </div>
        <button
          type="button"
          onClick={onRevalidate}
          disabled={readinessLoading}
          className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-weak)] hover:bg-[var(--color-hover)] disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${readinessLoading ? "animate-spin" : ""}`} />
          Revalidar
        </button>
      </div>

      {readinessLoading && !readiness && (
        <div className="mt-4 flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Avaliando prontidão fiscal…
        </div>
      )}

      {readiness && (
        <div className="mt-4 space-y-3">
          {/* Status geral */}
          <div className={`rounded-2xl border px-4 py-3 ${
            readiness.fiscal_status === "fiscal_ready"
              ? "border-emerald-300/60 bg-emerald-500/10"
              : readiness.blocking_count === 0
              ? "border-amber-300/60 bg-amber-500/10"
              : "border-rose-300/60 bg-rose-500/10"
          }`}>
            <p className={`text-sm font-bold ${
              readiness.fiscal_status === "fiscal_ready"
                ? "text-emerald-700 dark:text-emerald-200"
                : readiness.blocking_count === 0
                ? "text-amber-800 dark:text-amber-100"
                : "text-rose-700 dark:text-rose-200"
            }`}>
              {readiness.fiscal_status === "fiscal_ready"
                ? "✓ Pronto para faturar"
                : readiness.blocking_count === 0
                ? `⚠ ${readiness.warning_count} aviso(s) — revisão recomendada`
                : `✗ ${readiness.blocking_count} bloqueio(s) impedem o faturamento`}
            </p>
            <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
              Avaliado em {new Date(readiness.evaluated_at).toLocaleString("pt-BR")}
            </p>
          </div>

          {/* Issues agrupadas por escopo */}
          {readiness.issues.length > 0 && (
            <div className="space-y-2">
              {(["company", "participant", "item", "operation", "payment", "totals", "stock"] as const).map((scope) => {
                const scopeIssues = readiness.issues.filter((i) => i.scope === scope)
                if (scopeIssues.length === 0) return null
                return (
                  <div key={scope} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--color-text-weak)]">{scopeLabels[scope] ?? scope}</p>
                    <div className="mt-2 space-y-1.5">
                      {scopeIssues.map((issue, idx) => (
                        <div key={idx} className="flex flex-col gap-0.5">
                          <p className={`text-sm ${issue.severity === "blocking" ? "font-bold text-rose-700 dark:text-rose-300" : "text-amber-700 dark:text-amber-200"}`}>
                            {issue.severity === "blocking" ? "✗" : "⚠"}{issue.item_index !== null ? ` (Item ${issue.item_index + 1})` : ""} {issue.message}
                          </p>
                          {issue.fix_hint && (
                            <p className="pl-4 text-xs text-[var(--color-text-muted)]">→ {issue.fix_hint}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Documentos emitidos */}
      {fiscalDocuments.length > 0 && (
        <div className="mt-6">
          <h4 className="text-sm font-bold text-[var(--color-text-weak)] uppercase tracking-[0.12em]">Documentos Emitidos</h4>
          <div className="mt-3 space-y-2">
            {fiscalDocuments.map((doc) => (
              <div key={doc.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-bold text-[var(--color-text)]">
                      {doc.document_type.toUpperCase()} {doc.serie && `Série ${doc.serie}`} {doc.number && `Nº ${doc.number}`}
                    </p>
                    <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">Ref: {doc.reference}</p>
                    {doc.access_key && (
                      <p className="mt-0.5 font-mono text-xs text-[var(--color-text-muted)]">{doc.access_key}</p>
                    )}
                  </div>
                  <span className={`text-xs font-bold ${docStatusColors[doc.status] ?? "text-[var(--color-text-weak)]"}`}>
                    {docStatusLabels[doc.status] ?? doc.status}
                  </span>
                </div>
                {doc.error_message && (
                  <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{doc.error_message}</p>
                )}
                {(doc.danfe_url || doc.xml_url) && (
                  <div className="mt-2 flex gap-2">
                    {doc.danfe_url && (
                      <a href={doc.danfe_url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400">DANFE</a>
                    )}
                    {doc.xml_url && (
                      <a href={doc.xml_url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400">XML</a>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TimelinePanel({ statusHistory }: { statusHistory: SaleStatusHistory[] }) {
  return <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]"><h3 className="text-lg font-bold text-[var(--color-text)]">Histórico de status</h3><div className="mt-4 space-y-3">{statusHistory.map((event) => <div key={event.id} className="rounded-2xl bg-[var(--color-surface-elevated)] p-3"><p className="text-sm font-semibold text-[var(--color-text)]">{event.previous_status ? statusLabels[event.previous_status] : "Início"} → {statusLabels[event.new_status]}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{event.reason || "Sem justificativa"}</p><p className="mt-1 text-xs text-[var(--color-text-weak)]">{formatDateTime(event.occurred_at)}</p></div>)}</div></div>
}

function AuditPanel({ auditEvents }: { auditEvents: SaleAuditEvent[] }) {
  return <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]"><h3 className="text-lg font-bold text-[var(--color-text)]">Auditoria</h3><div className="mt-4 space-y-3">{auditEvents.map((event) => <div key={event.id} className="rounded-2xl bg-[var(--color-surface-elevated)] p-3"><p className="text-sm font-semibold text-[var(--color-text)]">{event.event_type}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{event.source} · {formatDateTime(event.occurred_at)}</p></div>)}</div></div>
}
