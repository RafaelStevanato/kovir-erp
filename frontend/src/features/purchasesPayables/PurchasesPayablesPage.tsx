import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Download,
  FileSpreadsheet,
  FilePlus2,
  Filter,
  ListFilter,
  ReceiptText,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  WalletCards,
  XCircle,
} from "lucide-react"

import { useActiveCompany } from "../../config/useActiveCompany"
import {
  dateCell,
  exportCsv as exportCsvFile,
  exportXlsx as exportXlsxFile,
  moneyCell,
  type ExportTable,
} from "../../lib/exportTable"
import { SearchableSelect, type SearchableSelectOption } from "../../components/SearchableSelect"
import { listFinancialAccounts, listFinancialCategories, listCostCenters } from "../financial/financialApi"
import type { CostCenter, FinancialAccount, FinancialCategory } from "../financial/types"
import { getParticipants } from "../participants/participantsApi"
import type { Participant } from "../participants/types"
import { getSalesPaymentMethods } from "../sales/salesApi"
import type { PaymentMethod } from "../sales/types"
import {
  cancelPayable,
  cancelPurchase,
  confirmPurchase,
  createAndConfirmPurchase,
  exportPayables,
  exportPurchases,
  getPurchasesPayablesDiagnostics,
  getPurchasesPayablesOverviewEvidence,
  getPurchasesPayablesSummary,
  listPayables,
  listPurchases,
  payPayable,
} from "./purchasesPayablesApi"
import type { PayablePaymentPayload, PayableTitle, Purchase, PurchaseCreatePayload, PurchasesPayablesDiagnostics, PurchasesPayablesSummary } from "./types"

type TabKey = "overview" | "purchases" | "payables" | "create" | "pay"
type OverviewExportBlock = "open_payables" | "overdue_payables" | "paid_payables"

const overviewExportLabels: Record<OverviewExportBlock, { sheet: string; file: string }> = {
  open_payables: { sheet: "A pagar em aberto", file: "kovir-compras-a-pagar-em-aberto" },
  overdue_payables: { sheet: "A pagar vencido", file: "kovir-compras-a-pagar-vencido" },
  paid_payables: { sheet: "Titulos quitados", file: "kovir-compras-titulos-quitados" },
}

type PurchaseConfirmFormState = {
  purchase_id: string
  due_date: string
  amount: string
  expected_financial_account_id: string
  document_reference: string
  notes: string
}

const purchaseTypeOptions = [
  { value: "expense", label: "Despesa" },
  { value: "inventory_purchase", label: "Compra de mercadoria" },
  { value: "service", label: "Serviço tomado" },
  { value: "tax", label: "Imposto/guia" },
  { value: "asset", label: "Ativo/imobilizado" },
  { value: "other", label: "Outro" },
]

type PurchaseFormState = {
  participant_id: string
  purchase_type: string
  issue_date: string
  competency_date: string
  description: string
  quantity: string
  unit: string
  unit_cost: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  due_date: string
  financial_category_id: string
  cost_center_id: string
  expected_financial_account_id: string
  document_type: string
  document_number: string
  notes: string
}

type PaymentFormState = {
  financial_title_id: string
  financial_account_id: string
  payment_method_id: string
  payment_date: string
  paid_amount: string
  discount_amount: string
  interest_amount: string
  penalty_amount: string
  fee_amount: string
  approval_request_id: string
  evidence_reference: string
  notes: string
}

const tabs: Array<{ key: TabKey; label: string; icon: ReactNode }> = [
  { key: "overview", label: "Visão geral", icon: <ShieldCheck className="h-4 w-4" /> },
  { key: "purchases", label: "Compras/despesas", icon: <ReceiptText className="h-4 w-4" /> },
  { key: "payables", label: "Títulos a pagar", icon: <WalletCards className="h-4 w-4" /> },
  { key: "create", label: "Nova obrigação", icon: <FilePlus2 className="h-4 w-4" /> },
  { key: "pay", label: "Registrar pagamento", icon: <Banknote className="h-4 w-4" /> },
]

const defaultPurchaseForm = (): PurchaseFormState => ({
  participant_id: "",
  purchase_type: "expense",
  issue_date: today(),
  competency_date: today(),
  description: "",
  quantity: "1",
  unit: "UN",
  unit_cost: "0.00",
  discount_amount: "0.00",
  freight_amount: "0.00",
  tax_amount: "0.00",
  due_date: plusDays(7),
  financial_category_id: "",
  cost_center_id: "",
  expected_financial_account_id: "",
  document_type: "invoice",
  document_number: "",
  notes: "",
})

const defaultPaymentForm = (): PaymentFormState => ({
  financial_title_id: "",
  financial_account_id: "",
  payment_method_id: "",
  payment_date: today(),
  paid_amount: "0.00",
  discount_amount: "0.00",
  interest_amount: "0.00",
  penalty_amount: "0.00",
  fee_amount: "0.00",
  approval_request_id: "",
  evidence_reference: "",
  notes: "",
})

function today() {
  return new Date().toISOString().slice(0, 10)
}

function plusDays(days: number) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

function toNumber(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0
  const parsed = Number(String(value).replace(",", "."))
  return Number.isFinite(parsed) ? parsed : 0
}

function money(value: number) {
  return value.toFixed(2)
}

function isPositiveMoney(value?: string | null) {
  return toNumber(value) > 0
}

function normalizeMoney(value?: string | null) {
  return money(toNumber(value))
}

function formatMoney(value?: string | number | null) {
  const parsed = toNumber(value)
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(parsed)
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const [year, month, day] = value.slice(0, 10).split("-")
  if (!year || !month || !day) return value
  return `${day}/${month}/${year}`
}

function calculatedFormAmount(form: PurchaseFormState) {
  const subtotal = toNumber(form.quantity) * toNumber(form.unit_cost)
  return money(Math.max(0, subtotal - toNumber(form.discount_amount) + toNumber(form.freight_amount) + toNumber(form.tax_amount)))
}

function normalizeText(value?: string | number | null) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
}

function statusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    draft: "Rascunho",
    confirmed: "Confirmada",
    cancelled: "Cancelada",
    open: "Em aberto",
    partially_paid: "Parcial",
    paid: "Pago",
    overdue: "Vencido",
    written_off: "Baixado/estornado",
  }
  return labels[status ?? ""] ?? status ?? "—"
}

function purchaseTypeLabel(type?: string | null) {
  const labels = Object.fromEntries(purchaseTypeOptions.map((option) => [option.value, option.label]))
  return labels[type ?? ""] ?? type ?? "—"
}

function fiscalLabel(status?: string | null) {
  const labels: Record<string, string> = {
    pending_document: "Documento pendente",
    not_required: "Sem documento fiscal",
    linked: "Documento vinculado",
    divergent: "Divergente",
  }
  return labels[status ?? ""] ?? status ?? "—"
}

function participantName(participants: Participant[], id?: string | null) {
  if (!id) return "—"
  const participant = participants.find((item) => item.id === id)
  return participant?.trade_name || participant?.name || id
}

function snapshotText(snapshot: Record<string, unknown> | null | undefined, keys: string[]) {
  if (!snapshot) return ""
  for (const key of keys) {
    const value = snapshot[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return ""
}

function payableParticipantName(title: PayableTitle, participants: Participant[]) {
  const participant = participants.find((item) => item.id === title.participant_id)
  if (participant) return participant.trade_name || participant.name
  return snapshotText(title.participant_snapshot, ["trade_name", "name", "legal_name", "display_name"]) || title.participant_id || "—"
}

function purchaseParticipantName(purchase: Purchase, participants: Participant[]) {
  const participant = participants.find((item) => item.id === purchase.participant_id)
  if (participant) return participant.trade_name || participant.name
  return snapshotText(purchase.participant_snapshot, ["trade_name", "name", "legal_name", "display_name"]) || purchase.participant_id || "—"
}
function optionName<T extends { id: string; name: string }>(items: T[], id?: string | null) {
  if (!id) return "—"
  return items.find((item) => item.id === id)?.name ?? id
}

function dueInfo(title: PayableTitle) {
  if (["paid", "cancelled"].includes(title.status)) return { label: statusLabel(title.status), tone: "success" as const }
  const now = new Date(today()).getTime()
  const due = new Date(title.due_date).getTime()
  const diff = Math.ceil((due - now) / 86_400_000)
  if (diff < 0) return { label: `Vencido há ${Math.abs(diff)} dia${Math.abs(diff) === 1 ? "" : "s"}`, tone: "danger" as const }
  if (diff === 0) return { label: "Vence hoje", tone: "warning" as const }
  if (diff <= 3) return { label: `Vence em ${diff} dia${diff === 1 ? "" : "s"}`, tone: "warning" as const }
  return { label: `Vence em ${diff} dias`, tone: "neutral" as const }
}

function dateInRange(value: string | null | undefined, from: string, to: string) {
  const candidate = value?.slice(0, 10)
  if (!candidate) return true
  if (from && candidate < from) return false
  if (to && candidate > to) return false
  return true
}

function amountInRange(value: string | number | null | undefined, min: string, max: string) {
  const parsed = toNumber(value)
  if (min && parsed < toNumber(min)) return false
  if (max && parsed > toNumber(max)) return false
  return true
}

function dateStamp() {
  return new Date().toISOString().slice(0, 10)
}

function exportCsv(rows: ExportTable, fileName: string) {
  exportCsvFile(rows, fileName)
}

function exportXlsx(rows: ExportTable, sheetName: string, fileName: string) {
  exportXlsxFile(rows, sheetName, fileName)
}

export function PurchasesPayablesPage() {
  const { companyId, activeCompanyName, isCompanyLoading, isCompanyResolved, companyError } = useActiveCompany()
  const [activeTab, setActiveTab] = useState<TabKey>("overview")
  const [diagnostics, setDiagnostics] = useState<PurchasesPayablesDiagnostics | null>(null)
  const [summary, setSummary] = useState<PurchasesPayablesSummary | null>(null)
  const [purchases, setPurchases] = useState<Purchase[]>([])
  const [payables, setPayables] = useState<PayableTitle[]>([])
  const [participants, setParticipants] = useState<Participant[]>([])
  const [financialAccounts, setFinancialAccounts] = useState<FinancialAccount[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [categories, setCategories] = useState<FinancialCategory[]>([])
  const [costCenters, setCostCenters] = useState<CostCenter[]>([])
  const [purchaseStatusFilter, setPurchaseStatusFilter] = useState("")
  const [purchaseSearch, setPurchaseSearch] = useState("")
  const [purchaseSupplierFilter, setPurchaseSupplierFilter] = useState("")
  const [purchaseTypeFilter, setPurchaseTypeFilter] = useState("")
  const [purchaseDateFrom, setPurchaseDateFrom] = useState("")
  const [purchaseDateTo, setPurchaseDateTo] = useState("")
  const [payableStatusFilter, setPayableStatusFilter] = useState("")
  const [payableSearch, setPayableSearch] = useState("")
  const [payableSupplierFilter, setPayableSupplierFilter] = useState("")
  const [payableCategoryFilter, setPayableCategoryFilter] = useState("")
  const [payableAccountFilter, setPayableAccountFilter] = useState("")
  const [payableDueFrom, setPayableDueFrom] = useState("")
  const [payableDueTo, setPayableDueTo] = useState("")
  const [payableMinAmount, setPayableMinAmount] = useState("")
  const [payableMaxAmount, setPayableMaxAmount] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [overviewExportingBlock, setOverviewExportingBlock] = useState<OverviewExportBlock | null>(null)
  const [isPurchasesExporting, setIsPurchasesExporting] = useState(false)
  const [isPayablesExporting, setIsPayablesExporting] = useState(false)
  const [purchaseConfirmForm, setPurchaseConfirmForm] = useState<PurchaseConfirmFormState | null>(null)
  const [form, setForm] = useState<PurchaseFormState>(() => defaultPurchaseForm())
  const [paymentForm, setPaymentForm] = useState<PaymentFormState>(() => defaultPaymentForm())

  const supplierOptions = useMemo(
    () => participants.filter((participant) => ["supplier", "service_provider", "carrier", "gateway", "marketplace", "bank", "other"].includes(participant.participant_type)),
    [participants],
  )

  const supplierSelectOptions = useMemo<SearchableSelectOption[]>(
    () => supplierOptions.map((participant) => ({
      value: participant.id,
      label: participant.trade_name || participant.name,
      description: [participant.document, participant.email].filter(Boolean).join(" · ") || participant.participant_type,
      keywords: [
        participant.name,
        participant.trade_name,
        participant.document,
        participant.email,
        participant.phone,
        participant.contact_name,
      ].filter((value): value is string => Boolean(value)),
    })),
    [supplierOptions],
  )

  const payableOptions = useMemo(
    () => payables.filter((title) => !["paid", "cancelled", "written_off"].includes(title.status)),
    [payables],
  )

  const payableSelectOptions = useMemo<SearchableSelectOption[]>(
    () => payableOptions.map((title) => {
      const supplierName = payableParticipantName(title, participants)
      const document = title.document_reference || title.id
      return {
        value: title.id,
        label: `${supplierName} - ${formatMoney(title.open_amount)}`,
        description: [
          document,
          `vence ${formatDate(title.due_date)}`,
          statusLabel(title.status),
          title.payment_method_name || title.payment_method_code,
        ].filter(Boolean).join(" · "),
        keywords: [
          title.id,
          title.document_reference,
          title.source_id,
          title.purchase_id,
          supplierName,
          title.payment_method_name,
          title.payment_method_code,
          title.due_date,
          title.open_amount,
          title.net_amount,
        ].filter((value): value is string => Boolean(value)),
      }
    }),
    [participants, payableOptions],
  )

  const paymentMethodSelectOptions = useMemo<SearchableSelectOption[]>(
    () => paymentMethods.map((method) => ({
      value: method.id,
      label: method.name,
      description: [method.code, method.method_type].filter(Boolean).join(" · "),
      keywords: [method.code, method.method_type, method.description].filter((value): value is string => Boolean(value)),
    })),
    [paymentMethods],
  )

  const selectedPayable = useMemo(
    () => payables.find((title) => title.id === paymentForm.financial_title_id) ?? null,
    [payables, paymentForm.financial_title_id],
  )

  const purchaseApiFilters = useMemo(
    () => ({
      status: purchaseStatusFilter || undefined,
      participant_id: purchaseSupplierFilter || undefined,
      purchase_type: purchaseTypeFilter || undefined,
      date_from: purchaseDateFrom || undefined,
      date_to: purchaseDateTo || undefined,
      q: purchaseSearch.trim() || undefined,
    }),
    [purchaseDateFrom, purchaseDateTo, purchaseSearch, purchaseStatusFilter, purchaseSupplierFilter, purchaseTypeFilter],
  )

  const payableApiFilters = useMemo(
    () => ({
      status: payableStatusFilter || undefined,
      participant_id: payableSupplierFilter || undefined,
      financial_category_id: payableCategoryFilter || undefined,
      expected_financial_account_id: payableAccountFilter || undefined,
      due_from: payableDueFrom || undefined,
      due_to: payableDueTo || undefined,
      open_amount_min: payableMinAmount ? normalizeMoney(payableMinAmount) : undefined,
      open_amount_max: payableMaxAmount ? normalizeMoney(payableMaxAmount) : undefined,
      q: payableSearch.trim() || undefined,
    }),
    [payableAccountFilter, payableCategoryFilter, payableDueFrom, payableDueTo, payableMaxAmount, payableMinAmount, payableSearch, payableStatusFilter, payableSupplierFilter],
  )

  const filteredPurchases = useMemo(() => {
    const normalized = normalizeText(purchaseSearch.trim())
    return purchases.filter((purchase) => {
      const matchesStatus = purchaseStatusFilter ? purchase.status === purchaseStatusFilter : true
      const matchesSupplier = purchaseSupplierFilter ? purchase.participant_id === purchaseSupplierFilter : true
      const matchesType = purchaseTypeFilter ? purchase.purchase_type === purchaseTypeFilter : true
      const matchesDate = dateInRange(purchase.issue_date || purchase.operation_date || purchase.created_at, purchaseDateFrom, purchaseDateTo)
      const matchesSearch = normalized
        ? [purchase.id, purchase.document_number, purchase.notes, purchaseParticipantName(purchase, participants), purchaseTypeLabel(purchase.purchase_type), fiscalLabel(purchase.fiscal_status)]
            .filter(Boolean)
            .some((value) => normalizeText(value).includes(normalized))
        : true
      return matchesStatus && matchesSupplier && matchesType && matchesDate && matchesSearch
    })
  }, [participants, purchaseDateFrom, purchaseDateTo, purchaseSearch, purchaseStatusFilter, purchaseSupplierFilter, purchaseTypeFilter, purchases])

  const filteredPayables = useMemo(() => {
    const normalized = normalizeText(payableSearch.trim())
    return payables.filter((title) => {
      const matchesStatus = payableStatusFilter ? title.status === payableStatusFilter : true
      const matchesSupplier = payableSupplierFilter ? title.participant_id === payableSupplierFilter : true
      const matchesCategory = payableCategoryFilter ? title.financial_category_id === payableCategoryFilter : true
      const matchesAccount = payableAccountFilter ? title.expected_financial_account_id === payableAccountFilter : true
      const matchesDue = dateInRange(title.due_date, payableDueFrom, payableDueTo)
      const matchesAmount = amountInRange(title.open_amount, payableMinAmount, payableMaxAmount)
      const matchesSearch = normalized
        ? [title.id, title.document_reference, title.notes, payableParticipantName(title, participants), optionName(categories, title.financial_category_id), optionName(financialAccounts, title.expected_financial_account_id)]
            .filter(Boolean)
            .some((value) => normalizeText(value).includes(normalized))
        : true
      return matchesStatus && matchesSupplier && matchesCategory && matchesAccount && matchesDue && matchesAmount && matchesSearch
    })
  }, [categories, financialAccounts, participants, payableAccountFilter, payableCategoryFilter, payableDueFrom, payableDueTo, payableMaxAmount, payableMinAmount, payableSearch, payableStatusFilter, payableSupplierFilter, payables])

  const formAmount = useMemo(() => calculatedFormAmount(form), [form])
  const paymentTitleEffect = useMemo(() => money(toNumber(paymentForm.paid_amount) + toNumber(paymentForm.discount_amount)), [paymentForm.discount_amount, paymentForm.paid_amount])
  const paymentCashMovement = useMemo(
    () => money(toNumber(paymentForm.paid_amount) + toNumber(paymentForm.interest_amount) + toNumber(paymentForm.penalty_amount) + toNumber(paymentForm.fee_amount)),
    [paymentForm.fee_amount, paymentForm.interest_amount, paymentForm.paid_amount, paymentForm.penalty_amount],
  )
  const paymentChargesAmount = useMemo(
    () => money(toNumber(paymentForm.interest_amount) + toNumber(paymentForm.penalty_amount) + toNumber(paymentForm.fee_amount)),
    [paymentForm.fee_amount, paymentForm.interest_amount, paymentForm.penalty_amount],
  )
  const paymentRemainingOpenAmount = useMemo(
    () => money(Math.max(0, toNumber(selectedPayable?.open_amount) - toNumber(paymentTitleEffect))),
    [paymentTitleEffect, selectedPayable?.open_amount],
  )
  const paymentExceedsOpenAmount = Boolean(selectedPayable && toNumber(paymentTitleEffect) > toNumber(selectedPayable.open_amount) + 0.0001)
  const overduePayables = useMemo(
    () => payableOptions.filter((title) => title.status === "overdue" || new Date(title.due_date).getTime() < new Date(today()).getTime()),
    [payableOptions],
  )
  const defaultPayableAccount = useMemo(() => financialAccounts.find((account) => account.is_default_payable) ?? financialAccounts[0] ?? null, [financialAccounts])
  const confirmingPurchase = useMemo(
    () => (purchaseConfirmForm ? purchases.find((purchase) => purchase.id === purchaseConfirmForm.purchase_id) ?? null : null),
    [purchaseConfirmForm, purchases],
  )

  function buildPurchaseRowsFrom(rows: Purchase[]): ExportTable {
    return [
      ["Data", "Fornecedor", "Tipo", "Documento", "Categoria", "Centro de custo", "Conta prevista", "Total", "Fiscal", "Status", "ID"],
      ...rows.map((purchase) => [
        dateCell(purchase.issue_date || purchase.operation_date || purchase.created_at),
        purchaseParticipantName(purchase, participants),
        purchaseTypeLabel(purchase.purchase_type),
        purchase.document_number || "",
        optionName(categories, purchase.financial_category_id),
        optionName(costCenters, purchase.cost_center_id),
        optionName(financialAccounts, purchase.expected_financial_account_id),
        moneyCell(purchase.payable_total_amount || purchase.total_amount),
        fiscalLabel(purchase.fiscal_status),
        statusLabel(purchase.status),
        purchase.id,
      ]),
    ]
  }

  function buildPayableRowsFrom(rows: PayableTitle[]): ExportTable {
    return [
      ["Vencimento", "Fornecedor", "Documento", "Categoria", "Centro de custo", "Conta prevista", "Valor líquido", "Pago", "Aberto", "Status", "ID", "Compra origem"],
      ...rows.map((title) => [
        dateCell(title.due_date),
        payableParticipantName(title, participants),
        title.document_reference || "",
        optionName(categories, title.financial_category_id),
        optionName(costCenters, title.cost_center_id),
        optionName(financialAccounts, title.expected_financial_account_id),
        moneyCell(title.net_amount),
        moneyCell(title.paid_amount),
        moneyCell(title.open_amount),
        statusLabel(title.status),
        title.id,
        title.purchase_id || title.source_id,
      ]),
    ]
  }

  const loadData = useCallback(async () => {
    if (!companyId || !isCompanyResolved) return
    setIsLoading(true)
    setError(null)
    try {
      const [diagnosticsResponse, summaryResponse, accountsResponse, categoriesResponse, centersResponse, paymentMethodsResponse] = await Promise.all([
        getPurchasesPayablesDiagnostics(),
        getPurchasesPayablesSummary(companyId),
        listFinancialAccounts(companyId),
        listFinancialCategories(companyId),
        listCostCenters(companyId),
        getSalesPaymentMethods({ company_id: companyId }),
      ])

      setDiagnostics(diagnosticsResponse.data)
      setSummary(summaryResponse.data)
      setFinancialAccounts(accountsResponse.data)
      setCategories(categoriesResponse.data)
      setCostCenters(centersResponse.data)
      setPaymentMethods(paymentMethodsResponse.data)

      if (activeTab === "overview") {
        const evidenceResponse = await getPurchasesPayablesOverviewEvidence(companyId, { block: "overdue_payables", limit: 5 })
        setPurchases([])
        setPayables(evidenceResponse.data.overdue_payables)
        return
      }

      const payablesFilters = activeTab === "pay" ? { limit: 500 } : payableApiFilters
      const [purchasesResponse, payablesResponse, participantsResponse] = await Promise.all([
        listPurchases(companyId, purchaseApiFilters),
        listPayables(companyId, payablesFilters),
        getParticipants({ company_id: companyId, status: "active" }),
      ])
      setPurchases(purchasesResponse.data)
      setPayables(payablesResponse.data)
      setParticipants(participantsResponse.data)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao carregar compras e contas a pagar."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [activeTab, companyId, isCompanyResolved, payableApiFilters, purchaseApiFilters])

  useEffect(() => {
    if (isCompanyResolved) void loadData()
  }, [isCompanyResolved, loadData])

  async function handleOverviewExport(block: OverviewExportBlock) {
    if (!companyId || !isCompanyResolved) return
    setOverviewExportingBlock(block)
    setError(null)
    try {
      const response = await getPurchasesPayablesOverviewEvidence(companyId, { block, limit: 5000 })
      const labels = overviewExportLabels[block]
      const rows = buildPayableRowsFrom(response.data[block])
      exportXlsx(rows, labels.sheet, `${labels.file}-${dateStamp()}.xlsx`)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao exportar evidências da visão geral."
      setError(message)
    } finally {
      setOverviewExportingBlock(null)
    }
  }

  async function handlePurchasesExport(format: "csv" | "xlsx") {
    if (!companyId || !isCompanyResolved) return
    setIsPurchasesExporting(true)
    setError(null)
    try {
      const response = await exportPurchases(companyId, purchaseApiFilters)
      const rows = buildPurchaseRowsFrom(response.data)
      if (format === "csv") exportCsv(rows, `kovir-compras-despesas-${dateStamp()}.csv`)
      else exportXlsx(rows, "Compras", `kovir-compras-despesas-${dateStamp()}.xlsx`)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao exportar compras/despesas."
      setError(message)
    } finally {
      setIsPurchasesExporting(false)
    }
  }

  async function handlePayablesExport(format: "csv" | "xlsx") {
    if (!companyId || !isCompanyResolved) return
    setIsPayablesExporting(true)
    setError(null)
    try {
      const response = await exportPayables(companyId, payableApiFilters)
      const rows = buildPayableRowsFrom(response.data)
      if (format === "csv") exportCsv(rows, `kovir-contas-a-pagar-${dateStamp()}.csv`)
      else exportXlsx(rows, "Contas a pagar", `kovir-contas-a-pagar-${dateStamp()}.xlsx`)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao exportar títulos a pagar."
      setError(message)
    } finally {
      setIsPayablesExporting(false)
    }
  }

  useEffect(() => {
    setForm((current) => ({
      ...current,
      expected_financial_account_id: current.expected_financial_account_id || defaultPayableAccount?.id || "",
    }))
    setPaymentForm((current) => ({
      ...current,
      financial_account_id: current.financial_account_id || defaultPayableAccount?.id || "",
    }))
  }, [defaultPayableAccount])

  function updateForm<K extends keyof PurchaseFormState>(key: K, value: PurchaseFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function updatePaymentForm<K extends keyof PaymentFormState>(key: K, value: PaymentFormState[K]) {
    setPaymentForm((current) => ({ ...current, [key]: value }))
  }

  function validatePurchaseForm() {
    if (!companyId) return "Selecione uma empresa ativa."
    if (!form.participant_id) return "Selecione fornecedor, prestador ou terceiro."
    if (!form.description.trim()) return "Informe a descrição da compra ou despesa."
    if (!isPositiveMoney(form.quantity)) return "A quantidade precisa ser maior que zero."
    if (!isPositiveMoney(form.unit_cost)) return "O valor unitário precisa ser maior que zero."
    if (!isPositiveMoney(formAmount)) return "O total calculado precisa ser maior que zero."
    if (!form.issue_date) return "Informe a data de emissão/operação."
    if (!form.competency_date) return "Informe a competência."
    if (!form.due_date) return "Informe o vencimento do título a pagar."
    if (!form.expected_financial_account_id) return "Selecione a conta financeira prevista para pagamento."
    return null
  }

  async function handleCreateAndConfirm() {
    const validationError = validatePurchaseForm()
    if (validationError) {
      setError(validationError)
      return
    }
    if (!companyId) return
    setIsLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const payload: PurchaseCreatePayload = {
        company_id: companyId,
        participant_id: form.participant_id,
        purchase_type: form.purchase_type,
        origin: "manual",
        fiscal_status: form.document_number.trim() ? "pending_document" : "not_required",
        issue_date: form.issue_date,
        competency_date: form.competency_date,
        financial_category_id: form.financial_category_id || null,
        cost_center_id: form.cost_center_id || null,
        expected_financial_account_id: form.expected_financial_account_id || null,
        document_type: form.document_type || null,
        document_number: form.document_number.trim() || null,
        invoice_total_amount: formAmount,
        notes: form.notes.trim() || null,
        items: [
          {
            description: form.description.trim(),
            quantity: normalizeMoney(form.quantity),
            unit: form.unit.trim() || "UN",
            unit_cost: normalizeMoney(form.unit_cost),
            discount_amount: normalizeMoney(form.discount_amount),
            freight_amount: normalizeMoney(form.freight_amount),
            tax_amount: normalizeMoney(form.tax_amount),
          },
        ],
      }
      await createAndConfirmPurchase({
        purchase: payload,
        confirmation: {
          reason: "Confirmação imediata pelo fluxo guiado de compras e contas a pagar.",
          installments: [
            {
              due_date: form.due_date,
              amount: formAmount,
              expected_financial_account_id: form.expected_financial_account_id || null,
              document_reference: form.document_number.trim() || null,
              notes: form.notes.trim() || null,
            },
          ],
        },
      })
      setSuccess("Compra/despesa registrada e título a pagar gerado com rastreabilidade.")
      setForm(defaultPurchaseForm())
      setActiveTab("payables")
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao criar compra/despesa."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  function openPurchaseConfirmation(purchase: Purchase) {
    if (!purchase.expected_financial_account_id && !defaultPayableAccount?.id) {
      setError("A compra em rascunho não possui conta financeira prevista. Configure uma conta a pagar antes de confirmar.")
      return
    }
    setPurchaseConfirmForm({
      purchase_id: purchase.id,
      due_date: today(),
      amount: normalizeMoney(purchase.payable_total_amount || purchase.total_amount),
      expected_financial_account_id: purchase.expected_financial_account_id || defaultPayableAccount?.id || "",
      document_reference: purchase.document_number || purchase.id,
      notes: "",
    })
  }

  function updatePurchaseConfirmForm<K extends keyof PurchaseConfirmFormState>(key: K, value: PurchaseConfirmFormState[K]) {
    setPurchaseConfirmForm((current) => (current ? { ...current, [key]: value } : current))
  }

  async function handleConfirmDraft() {
    if (!purchaseConfirmForm || !confirmingPurchase) return
    const purchaseTotal = normalizeMoney(confirmingPurchase.payable_total_amount || confirmingPurchase.total_amount)
    if (!purchaseConfirmForm.due_date) {
      setError("Informe o vencimento real da parcela antes de confirmar.")
      return
    }
    if (!purchaseConfirmForm.expected_financial_account_id) {
      setError("Selecione a conta financeira prevista antes de confirmar.")
      return
    }
    if (Math.abs(toNumber(purchaseConfirmForm.amount) - toNumber(purchaseTotal)) > 0.0001) {
      setError("Nesta confirmação rápida, a parcela única deve fechar exatamente o total da compra/despesa.")
      return
    }
    setIsLoading(true)
    setError(null)
    setSuccess(null)
    try {
      await confirmPurchase(confirmingPurchase.id, {
        reason: "Confirmação guiada pela listagem de compras.",
        installments: [
          {
            due_date: purchaseConfirmForm.due_date,
            amount: normalizeMoney(purchaseConfirmForm.amount),
            expected_financial_account_id: purchaseConfirmForm.expected_financial_account_id,
            document_reference: purchaseConfirmForm.document_reference.trim() || confirmingPurchase.document_number || confirmingPurchase.id,
            notes: purchaseConfirmForm.notes.trim() || null,
          },
        ],
      })
      setSuccess("Compra confirmada e título a pagar criado com vencimento conferido.")
      setPurchaseConfirmForm(null)
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao confirmar compra."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleCancelPurchase(purchase: Purchase) {
    const reason = window.prompt("Justificativa obrigatória para cancelar a compra/despesa:")
    if (!reason?.trim()) return
    setIsLoading(true)
    setError(null)
    setSuccess(null)
    try {
      await cancelPurchase(purchase.id, reason.trim())
      setSuccess("Compra/despesa cancelada com histórico preservado.")
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao cancelar compra."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  async function handleCancelPayable(title: PayableTitle) {
    const reason = window.prompt("Justificativa obrigatória para cancelar o título a pagar:")
    if (!reason?.trim()) return
    setIsLoading(true)
    setError(null)
    setSuccess(null)
    try {
      await cancelPayable(title.id, reason.trim())
      setSuccess("Título a pagar cancelado com histórico preservado.")
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao cancelar título."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  function selectPayable(title: PayableTitle) {
    setPaymentForm({
      financial_title_id: title.id,
      financial_account_id: title.expected_financial_account_id || defaultPayableAccount?.id || "",
      payment_method_id: title.payment_method_id || "",
      payment_date: today(),
      paid_amount: title.open_amount,
      discount_amount: "0.00",
      interest_amount: "0.00",
      penalty_amount: "0.00",
      fee_amount: "0.00",
      approval_request_id: "",
      evidence_reference: title.document_reference || "",
      notes: "",
    })
    setActiveTab("pay")
  }

  async function handlePay() {
    if (!companyId) return
    if (!selectedPayable) {
      setError("Selecione um título a pagar.")
      return
    }
    if (!paymentForm.financial_account_id) {
      setError("Selecione a conta financeira de saída.")
      return
    }
    if (!isPositiveMoney(paymentForm.paid_amount)) {
      setError("Informe valor pago maior que zero. Desconto é apenas abatimento junto de pagamento real.")
      return
    }
    if (paymentExceedsOpenAmount) {
      setError("O valor que baixa o título ultrapassa o saldo em aberto. Ajuste pagamento/desconto antes de registrar.")
      return
    }
    if (!paymentForm.evidence_reference.trim()) {
      setError("Informe comprovante, extrato, documento ou justificativa de suporte para a baixa.")
      return
    }
    setIsLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const payload: PayablePaymentPayload = {
        company_id: companyId,
        financial_title_id: paymentForm.financial_title_id,
        financial_account_id: paymentForm.financial_account_id,
        payment_date: paymentForm.payment_date,
        competency_date: paymentForm.payment_date,
        paid_amount: normalizeMoney(paymentForm.paid_amount),
        discount_amount: normalizeMoney(paymentForm.discount_amount),
        interest_amount: normalizeMoney(paymentForm.interest_amount),
        penalty_amount: normalizeMoney(paymentForm.penalty_amount),
        fee_amount: normalizeMoney(paymentForm.fee_amount),
        payment_method_id: paymentForm.payment_method_id || null,
        source_type: "manual",
        source_id: null,
        approval_request_id: paymentForm.approval_request_id.trim() || null,
        evidence_reference: paymentForm.evidence_reference.trim(),
        notes: paymentForm.notes.trim() || null,
      }
      await payPayable(payload)
      setSuccess("Pagamento registrado: título baixado, movimento financeiro gerado e saldo interno atualizado.")
      setPaymentForm(defaultPaymentForm())
      setActiveTab("payables")
      await loadData()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha ao pagar título."
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  function clearPurchaseFilters() {
    setPurchaseSearch("")
    setPurchaseStatusFilter("")
    setPurchaseSupplierFilter("")
    setPurchaseTypeFilter("")
    setPurchaseDateFrom("")
    setPurchaseDateTo("")
  }

  function clearPayableFilters() {
    setPayableSearch("")
    setPayableStatusFilter("")
    setPayableSupplierFilter("")
    setPayableCategoryFilter("")
    setPayableAccountFilter("")
    setPayableDueFrom("")
    setPayableDueTo("")
    setPayableMinAmount("")
    setPayableMaxAmount("")
  }

  if (isCompanyLoading && !isCompanyResolved) {
    return <Notice tone="info" title="Carregando empresas" message="A tela depende da empresa ativa para evitar lançamentos financeiros sem vínculo de tenant." />
  }

  return (
    <div className="space-y-6 pb-8">
      <header className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.22em] text-[var(--color-primary)]">Bloco 13 · Compras, despesas e contas a pagar</p>
            <h1 className="mt-2 text-3xl font-black text-[var(--color-text)]">Controle de obrigações financeiras</h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-[var(--color-text-muted)]">
              A tela separa origem operacional, título financeiro, pagamento, movimento de caixa e conciliação. O visual segue o padrão escuro/elevado do Kovir; a listagem permite filtrar e exportar somente o que está na tela.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <label className="min-w-64 text-xs font-black uppercase tracking-wide text-[var(--color-text-weak)]">
              Empresa da sessão
              <div className="input mt-2">
                {activeCompanyName || "Empresa não identificada"}
              </div>
              <span className="mt-1 block max-w-64 truncate text-[10px] normal-case text-[var(--color-text-muted)]">Escopo travado na empresa da sessão</span>
            </label>
            <button className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm font-bold text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-60" type="button" onClick={() => void loadData()} disabled={isLoading || !isCompanyResolved}>
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
              Atualizar
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <KpiCard title="Empresa ativa" value={activeCompanyName || "—"} description="Todos os registros exigem company_id." icon={<ShieldCheck className="h-5 w-5" />} />
          <KpiCard title="A pagar em aberto" value={formatMoney(summary?.open_payable_amount)} description={`${summary?.open_payable_count ?? 0} título(s) aberto(s).`} tone="info" icon={<WalletCards className="h-5 w-5" />} onExport={() => void handleOverviewExport("open_payables")} isExporting={overviewExportingBlock === "open_payables"} />
          <KpiCard title="Vencidos" value={formatMoney(summary?.overdue_payable_amount)} description={`${summary?.overdue_payable_count ?? 0} título(s) exigem ação.`} tone={summary?.overdue_payable_count ? "warning" : "success"} icon={<AlertTriangle className="h-5 w-5" />} onExport={() => void handleOverviewExport("overdue_payables")} isExporting={overviewExportingBlock === "overdue_payables"} />
          <KpiCard title="Títulos quitados" value={formatMoney(summary?.paid_payable_amount ?? summary?.payables_by_status?.paid?.paid_amount ?? summary?.payables_by_status?.paid?.net_amount)} description={`${summary?.paid_payable_count ?? summary?.payables_by_status?.paid?.count ?? 0} título(s) encerrado(s).`} tone="success" icon={<CheckCircle2 className="h-5 w-5" />} onExport={() => void handleOverviewExport("paid_payables")} isExporting={overviewExportingBlock === "paid_payables"} />
        </div>
      </header>

      {companyError ? <Notice tone="error" title="Empresa ativa não resolvida" message={companyError} /> : null}
      {error ? <Notice tone="error" title="Ação bloqueada" message={error} onClose={() => setError(null)} /> : null}
      {success ? <Notice tone="success" title="Operação registrada" message={success} onClose={() => setSuccess(null)} /> : null}

      <nav className="flex flex-wrap gap-2 rounded-[1.5rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2 shadow-xl shadow-[var(--color-card-shadow)]">
        {tabs.map((tab) => (
          <TabButton key={tab.key} active={activeTab === tab.key} onClick={() => setActiveTab(tab.key)} icon={tab.icon}>{tab.label}</TabButton>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <Panel title="Caminho financeiro protegido" description="O usuário opera em etapas claras, mas os efeitos críticos continuam transacionais no backend." icon={<ShieldCheck className="h-5 w-5" />}>
            <div className="grid gap-3 md:grid-cols-5">
              <FlowStep icon={<FilePlus2 className="h-5 w-5" />} title="Compra/despesa" description="Origem operacional com fornecedor, documento, categoria e centro." />
              <FlowArrow />
              <FlowStep icon={<ClipboardList className="h-5 w-5" />} title="Título" description="Obrigação financeira com vencimento e saldo em aberto." />
              <FlowArrow />
              <FlowStep icon={<Banknote className="h-5 w-5" />} title="Pagamento" description="Baixa, movimento financeiro e saldo interno." />
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <ActionCard title="Registrar obrigação" description="Cria compra/despesa e gera título a pagar na sequência guiada." onClick={() => setActiveTab("create")} />
              <ActionCard title="Filtrar títulos" description="Use filtros por fornecedor, vencimento, categoria, conta e faixa de valor." onClick={() => setActiveTab("payables")} />
              <ActionCard title="Revisar vencidos" description="Aplica filtro de vencidos para priorizar risco de caixa." onClick={() => { setPayableStatusFilter("overdue"); setActiveTab("payables") }} />
            </div>
          </Panel>

          <Panel title="Pendências críticas" description="Títulos vencidos aparecem primeiro para ação rápida." icon={<AlertTriangle className="h-5 w-5" />}>
            <div className="space-y-3">
              {overduePayables.slice(0, 5).map((title) => (
                <button key={title.id} type="button" className="w-full rounded-2xl border border-amber-500/30 bg-amber-500/10 p-3 text-left hover:bg-amber-500/20" onClick={() => selectPayable(title)}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-black text-[var(--color-text)]">{payableParticipantName(title, participants)}</p>
                      <p className="text-sm text-[var(--color-text-muted)]">Vencimento {formatDate(title.due_date)} · {title.document_reference || title.id}</p>
                    </div>
                    <strong className="text-sm text-amber-700">{formatMoney(title.open_amount)}</strong>
                  </div>
                </button>
              ))}
              {overduePayables.length === 0 ? <p className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700">Nenhum título vencido carregado para a empresa ativa.</p> : null}
            </div>
          </Panel>

          <Panel title="Checklist de integridade" description="Regras que a tela antecipa sem substituir validação final do backend." icon={<ListFilter className="h-5 w-5" />}>
            <div className="grid gap-3 md:grid-cols-2">
              <ChecklistItem ok label="Fornecedor vem de Participantes; nada de fornecedor como texto solto." />
              <ChecklistItem ok label="Conta financeira define onde o dinheiro sai; forma de pagamento não substitui conta." />
              <ChecklistItem ok label="Compra confirmada gera título; pagamento gera settlement e movimento financeiro." />
              <ChecklistItem ok label="Comprovante/justificativa é exigido antes da baixa manual." />
              <ChecklistItem ok={Boolean(diagnostics)} label={`Diagnóstico backend: ${diagnostics?.status ?? "não carregado"}.`} />
              <ChecklistItem ok={financialAccounts.length > 0} label={`${financialAccounts.length} conta(s) financeira(s) disponíveis.`} />
            </div>
          </Panel>
        </div>
      ) : null}

      {activeTab === "purchases" ? (
        <Panel title="Compras e despesas" description="Origem operacional da obrigação. Compra confirmada não é pagamento; ela gera ou vincula títulos a pagar." icon={<ReceiptText className="h-5 w-5" />}>
          <PurchaseFilters
            search={purchaseSearch}
            setSearch={setPurchaseSearch}
            status={purchaseStatusFilter}
            setStatus={setPurchaseStatusFilter}
            supplier={purchaseSupplierFilter}
            setSupplier={setPurchaseSupplierFilter}
            type={purchaseTypeFilter}
            setType={setPurchaseTypeFilter}
            from={purchaseDateFrom}
            setFrom={setPurchaseDateFrom}
            to={purchaseDateTo}
            setTo={setPurchaseDateTo}
            suppliers={supplierOptions}
            onClear={clearPurchaseFilters}
          />
          <ExportBar
            count={filteredPurchases.length}
            label="compras/despesas filtradas"
            note="A tabela mostra até 200 registros filtrados; a exportação consulta o backend e retorna até 5000 registros filtrados."
            isExporting={isPurchasesExporting}
            onCsv={() => void handlePurchasesExport("csv")}
            onXlsx={() => void handlePurchasesExport("xlsx")}
          />
          <DataTable headers={["Data", "Fornecedor", "Tipo", "Documento", "Total", "Fiscal", "Status", "Ações"]}>
            {filteredPurchases.map((purchase) => (
              <tr key={purchase.id} className="align-top odd:bg-[var(--color-surface)] even:bg-[var(--color-surface-elevated)]">
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{formatDate(purchase.issue_date || purchase.operation_date || purchase.created_at)}</td>
                <td className="px-4 py-3 font-black text-[var(--color-text)]">{purchaseParticipantName(purchase, participants)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{purchaseTypeLabel(purchase.purchase_type)}</td>
                <td className="px-4 py-3 text-[var(--color-text-muted)]">{purchase.document_number || "—"}</td>
                <td className="px-4 py-3 font-black text-[var(--color-text)]">{formatMoney(purchase.payable_total_amount || purchase.total_amount)}</td>
                <td className="px-4 py-3"><StatusBadge status={purchase.fiscal_status} label={fiscalLabel(purchase.fiscal_status)} /></td>
                <td className="px-4 py-3"><StatusBadge status={purchase.status} label={statusLabel(purchase.status)} /></td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    {purchase.status === "draft" ? <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50 text-xs" type="button" onClick={() => openPurchaseConfirmation(purchase)}>Confirmar</button> : null}
                    {purchase.status === "confirmed" ? <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 font-black text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-50 text-xs" type="button" onClick={() => { setPayableSearch(purchase.id); setActiveTab("payables") }}>Ver títulos</button> : null}
                    {purchase.status !== "cancelled" ? <button className="inline-flex items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-2 font-black text-red-700 hover:bg-red-500/20 disabled:opacity-50 text-xs" type="button" onClick={() => void handleCancelPurchase(purchase)}>Cancelar</button> : null}
                  </div>
                </td>
              </tr>
            ))}
            {filteredPurchases.length === 0 ? <EmptyRow colspan={8} message="Nenhuma compra/despesa encontrada para os filtros atuais." /> : null}
          </DataTable>
          {purchaseConfirmForm && confirmingPurchase ? (
            <div className="mt-5 rounded-3xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-5">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Confirmação guiada</p>
                  <h3 className="text-lg font-black text-[var(--color-text)]">{purchaseParticipantName(confirmingPurchase, participants)}</h3>
                  <p className="mt-1 text-sm text-[var(--color-text-muted)]">Conferir vencimento e conta antes de gerar o título. Compra não é pagamento.</p>
                </div>
                <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 font-black text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]" type="button" onClick={() => setPurchaseConfirmForm(null)}>Cancelar confirmação</button>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field label="Vencimento real" required>
                  <input className="field-input" type="date" value={purchaseConfirmForm.due_date} onChange={(event) => updatePurchaseConfirmForm("due_date", event.target.value)} />
                </Field>
                <Field label="Valor da parcela única" required>
                  <input className="field-input" inputMode="decimal" value={purchaseConfirmForm.amount} onChange={(event) => updatePurchaseConfirmForm("amount", event.target.value)} onBlur={() => updatePurchaseConfirmForm("amount", normalizeMoney(purchaseConfirmForm.amount))} />
                </Field>
                <Field label="Conta financeira prevista" required>
                  <select className="field-input" value={purchaseConfirmForm.expected_financial_account_id} onChange={(event) => updatePurchaseConfirmForm("expected_financial_account_id", event.target.value)}>
                    <option value="">Selecione</option>
                    {financialAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                  </select>
                </Field>
                <Field label="Documento / referência">
                  <input className="field-input" value={purchaseConfirmForm.document_reference} onChange={(event) => updatePurchaseConfirmForm("document_reference", event.target.value)} />
                </Field>
                <Field label="Observações">
                  <input className="field-input" value={purchaseConfirmForm.notes} onChange={(event) => updatePurchaseConfirmForm("notes", event.target.value)} placeholder="Opcional" />
                </Field>
                <MiniMetric label="Total da compra" value={formatMoney(confirmingPurchase.payable_total_amount || confirmingPurchase.total_amount)} highlight />
              </div>
              <div className="mt-4 flex justify-end">
                <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary)] px-5 py-3 font-black text-slate-950 hover:bg-[var(--color-primary-hover)] disabled:opacity-50" type="button" onClick={() => void handleConfirmDraft()} disabled={isLoading}>Gerar título a pagar</button>
              </div>
            </div>
          ) : null}
        </Panel>
      ) : null}

      {activeTab === "payables" ? (
        <Panel title="Títulos a pagar" description="O título representa obrigação. Só o pagamento/baixa movimenta saldo interno; conciliação continua separada." icon={<WalletCards className="h-5 w-5" />}>
          <PayableFilters
            search={payableSearch}
            setSearch={setPayableSearch}
            status={payableStatusFilter}
            setStatus={setPayableStatusFilter}
            supplier={payableSupplierFilter}
            setSupplier={setPayableSupplierFilter}
            category={payableCategoryFilter}
            setCategory={setPayableCategoryFilter}
            account={payableAccountFilter}
            setAccount={setPayableAccountFilter}
            from={payableDueFrom}
            setFrom={setPayableDueFrom}
            to={payableDueTo}
            setTo={setPayableDueTo}
            minAmount={payableMinAmount}
            setMinAmount={setPayableMinAmount}
            maxAmount={payableMaxAmount}
            setMaxAmount={setPayableMaxAmount}
            suppliers={supplierOptions}
            categories={categories}
            accounts={financialAccounts}
            onClear={clearPayableFilters}
          />
          <ExportBar
            count={filteredPayables.length}
            label="títulos filtrados"
            note="A tabela mostra até 200 títulos filtrados; a exportação consulta o backend e retorna até 5000 títulos filtrados."
            isExporting={isPayablesExporting}
            onCsv={() => void handlePayablesExport("csv")}
            onXlsx={() => void handlePayablesExport("xlsx")}
          />
          <DataTable headers={["Vencimento", "Fornecedor", "Documento", "Categoria", "Conta prevista", "Aberto", "Status", "Ações"]}>
            {filteredPayables.map((title) => {
              const due = dueInfo(title)
              const canPay = !["paid", "cancelled", "written_off"].includes(title.status)
              const canCancel = ["open", "overdue"].includes(title.status)
              return (
                <tr key={title.id} className="align-top odd:bg-[var(--color-surface)] even:bg-[var(--color-surface-elevated)]">
                  <td className="px-4 py-3"><StatusBadge status={due.tone} label={`${formatDate(title.due_date)} · ${due.label}`} /></td>
                  <td className="px-4 py-3 font-black text-[var(--color-text)]">{payableParticipantName(title, participants)}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{title.document_reference || title.id}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{optionName(categories, title.financial_category_id)}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{optionName(financialAccounts, title.expected_financial_account_id)}</td>
                  <td className="px-4 py-3 font-black text-[var(--color-text)]">{formatMoney(title.open_amount)}</td>
                  <td className="px-4 py-3"><StatusBadge status={title.status} label={statusLabel(title.status)} /></td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {canPay ? <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50 text-xs" type="button" onClick={() => selectPayable(title)}>Pagar</button> : null}
                      {canCancel ? <button className="inline-flex items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-2 font-black text-red-700 hover:bg-red-500/20 disabled:opacity-50 text-xs" type="button" onClick={() => void handleCancelPayable(title)}>Cancelar</button> : null}
                      {title.status === "partially_paid" ? <span className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-black text-amber-700">Estorno necessário</span> : null}
                    </div>
                  </td>
                </tr>
              )
            })}
            {filteredPayables.length === 0 ? <EmptyRow colspan={8} message="Nenhum título a pagar encontrado para os filtros atuais." /> : null}
          </DataTable>
        </Panel>
      ) : null}

      {activeTab === "create" ? (
        <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
          <Panel title="Nova compra/despesa" description="Fluxo rápido para registrar obrigação e gerar título a pagar com origem, classificação e vencimento." icon={<FilePlus2 className="h-5 w-5" />}>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Fornecedor / prestador / terceiro" required>
                <SearchableSelect
                  value={form.participant_id}
                  options={supplierSelectOptions}
                  placeholder="Digite nome, documento, e-mail ou telefone"
                  searchPlaceholder="Pesquisar fornecedor ativo..."
                  emptyMessage="Nenhum fornecedor ativo encontrado."
                  maxResults={12}
                  required
                  onChange={(value) => updateForm("participant_id", value)}
                />
              </Field>
              <Field label="Tipo da obrigação">
                <select className="field-input" value={form.purchase_type} onChange={(event) => updateForm("purchase_type", event.target.value)}>
                  {purchaseTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </Field>
              <Field label="Descrição" required>
                <input className="field-input" value={form.description} onChange={(event) => updateForm("description", event.target.value)} placeholder="Ex.: Energia elétrica, fornecedor X, serviço contábil..." />
              </Field>
              <Field label="Emissão / operação" required>
                <input className="field-input" type="date" value={form.issue_date} onChange={(event) => updateForm("issue_date", event.target.value)} />
              </Field>
              <Field label="Competência" required>
                <input className="field-input" type="date" value={form.competency_date} onChange={(event) => updateForm("competency_date", event.target.value)} />
              </Field>
              <Field label="Vencimento" required>
                <input className="field-input" type="date" value={form.due_date} onChange={(event) => updateForm("due_date", event.target.value)} />
              </Field>
              <Field label="Quantidade" required>
                <input className="field-input" inputMode="decimal" value={form.quantity} onChange={(event) => updateForm("quantity", event.target.value)} onBlur={() => updateForm("quantity", normalizeMoney(form.quantity))} />
              </Field>
              <Field label="Unidade">
                <input className="field-input" value={form.unit} onChange={(event) => updateForm("unit", event.target.value.toUpperCase())} />
              </Field>
              <Field label="Valor unitário" required>
                <input className="field-input" inputMode="decimal" value={form.unit_cost} onChange={(event) => updateForm("unit_cost", event.target.value)} onBlur={() => updateForm("unit_cost", normalizeMoney(form.unit_cost))} />
              </Field>
              <Field label="Desconto">
                <input className="field-input" inputMode="decimal" value={form.discount_amount} onChange={(event) => updateForm("discount_amount", event.target.value)} onBlur={() => updateForm("discount_amount", normalizeMoney(form.discount_amount))} />
              </Field>
              <Field label="Frete/acréscimos">
                <input className="field-input" inputMode="decimal" value={form.freight_amount} onChange={(event) => updateForm("freight_amount", event.target.value)} onBlur={() => updateForm("freight_amount", normalizeMoney(form.freight_amount))} />
              </Field>
              <Field label="Tributos destacados">
                <input className="field-input" inputMode="decimal" value={form.tax_amount} onChange={(event) => updateForm("tax_amount", event.target.value)} onBlur={() => updateForm("tax_amount", normalizeMoney(form.tax_amount))} />
              </Field>
              <Field label="Categoria financeira">
                <select className="field-input" value={form.financial_category_id} onChange={(event) => updateForm("financial_category_id", event.target.value)}>
                  <option value="">Sem categoria</option>
                  {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </Field>
              <Field label="Centro de custo">
                <select className="field-input" value={form.cost_center_id} onChange={(event) => updateForm("cost_center_id", event.target.value)}>
                  <option value="">Sem centro</option>
                  {costCenters.map((center) => <option key={center.id} value={center.id}>{center.name}</option>)}
                </select>
              </Field>
              <Field label="Conta financeira prevista" required>
                <select className="field-input" value={form.expected_financial_account_id} onChange={(event) => updateForm("expected_financial_account_id", event.target.value)}>
                  <option value="">Selecione</option>
                  {financialAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
              </Field>
              <Field label="Documento / referência">
                <div className="grid grid-cols-[140px_1fr] gap-2">
                  <select className="field-input" value={form.document_type} onChange={(event) => updateForm("document_type", event.target.value)}>
                    <option value="invoice">NF/Fatura</option>
                    <option value="receipt">Recibo</option>
                    <option value="contract">Contrato</option>
                    <option value="other">Outro</option>
                  </select>
                  <input className="field-input" value={form.document_number} onChange={(event) => updateForm("document_number", event.target.value)} placeholder="Número, chave ou referência" />
                </div>
              </Field>
              <Field label="Observações">
                <input className="field-input" value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} placeholder="Observação opcional" />
              </Field>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50" type="button" onClick={() => setForm(defaultPurchaseForm())}>Limpar</button>
              <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary)] px-5 py-3 font-black text-slate-950 hover:bg-[var(--color-primary-hover)] disabled:opacity-50" type="button" onClick={() => void handleCreateAndConfirm()} disabled={isLoading}>Registrar e gerar título</button>
            </div>
          </Panel>

          <Panel title="Prévia da obrigação" description="Conferência antes de gravar. O backend recalcula e valida novamente." icon={<ClipboardList className="h-5 w-5" />}>
            <div className="space-y-3">
              <MiniMetric label="Fornecedor" value={participantName(participants, form.participant_id)} />
              <MiniMetric label="Emissão / operação" value={formatDate(form.issue_date)} />
              <MiniMetric label="Competência" value={formatDate(form.competency_date)} />
              <MiniMetric label="Total calculado" value={formatMoney(formAmount)} highlight />
              <MiniMetric label="Subtotal" value={formatMoney(toNumber(form.quantity) * toNumber(form.unit_cost))} />
              <MiniMetric label="Desconto" value={formatMoney(form.discount_amount)} />
              <MiniMetric label="Frete/acréscimos" value={formatMoney(form.freight_amount)} />
              <MiniMetric label="Tributos" value={formatMoney(form.tax_amount)} />
              <MiniMetric label="Vencimento" value={formatDate(form.due_date)} />
              <MiniMetric label="Categoria" value={optionName(categories, form.financial_category_id)} />
              <MiniMetric label="Centro de custo" value={optionName(costCenters, form.cost_center_id)} />
              <MiniMetric label="Conta prevista" value={optionName(financialAccounts, form.expected_financial_account_id)} />
            </div>
            <div className="mt-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 text-sm text-[var(--color-text-muted)]">
              Esta ação cria a origem operacional e confirma uma parcela única a pagar. Pagamento e conciliação permanecem separados.
            </div>
          </Panel>
        </div>
      ) : null}

      {activeTab === "pay" ? (
        <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
          <Panel title="Registrar pagamento de título" description="Baixa manual com conta financeira, evidência e composição separada de desconto, juros, multa e tarifa." icon={<Banknote className="h-5 w-5" />}>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Título a pagar" required>
                <SearchableSelect
                  value={paymentForm.financial_title_id}
                  options={payableSelectOptions}
                  placeholder="Digite fornecedor, documento, vencimento, valor ou ID"
                  searchPlaceholder="Pesquisar título a pagar..."
                  emptyMessage="Nenhum título aberto encontrado."
                  maxResults={12}
                  required
                  onChange={(value) => {
                    const title = payables.find((item) => item.id === value)
                    if (title) selectPayable(title)
                    else setPaymentForm((current) => ({ ...current, financial_title_id: "", paid_amount: "0.00", evidence_reference: "" }))
                  }}
                />
              </Field>
              <Field label="Conta financeira de saída" required>
                <select className="field-input" value={paymentForm.financial_account_id} onChange={(event) => updatePaymentForm("financial_account_id", event.target.value)}>
                  <option value="">Selecione</option>
                  {financialAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
              </Field>
              <Field label="Forma de pagamento">
                <SearchableSelect
                  value={paymentForm.payment_method_id}
                  options={paymentMethodSelectOptions}
                  placeholder="Sem forma definida"
                  searchPlaceholder="Pesquisar forma de pagamento..."
                  emptyMessage="Nenhuma forma de pagamento ativa encontrada."
                  maxResults={8}
                  onChange={(value) => updatePaymentForm("payment_method_id", value)}
                />
              </Field>
              <Field label="Data do pagamento" required>
                <input className="field-input" type="date" value={paymentForm.payment_date} onChange={(event) => updatePaymentForm("payment_date", event.target.value)} />
              </Field>
              <Field label="Valor pago" required>
                <input className="field-input" inputMode="decimal" value={paymentForm.paid_amount} onChange={(event) => updatePaymentForm("paid_amount", event.target.value)} onBlur={() => updatePaymentForm("paid_amount", normalizeMoney(paymentForm.paid_amount))} />
              </Field>
              <Field label="Desconto / abatimento">
                <input className="field-input" inputMode="decimal" value={paymentForm.discount_amount} onChange={(event) => updatePaymentForm("discount_amount", event.target.value)} onBlur={() => updatePaymentForm("discount_amount", normalizeMoney(paymentForm.discount_amount))} />
              </Field>
              <Field label="Juros">
                <input className="field-input" inputMode="decimal" value={paymentForm.interest_amount} onChange={(event) => updatePaymentForm("interest_amount", event.target.value)} onBlur={() => updatePaymentForm("interest_amount", normalizeMoney(paymentForm.interest_amount))} />
              </Field>
              <Field label="Multa">
                <input className="field-input" inputMode="decimal" value={paymentForm.penalty_amount} onChange={(event) => updatePaymentForm("penalty_amount", event.target.value)} onBlur={() => updatePaymentForm("penalty_amount", normalizeMoney(paymentForm.penalty_amount))} />
              </Field>
              <Field label="Tarifa bancária">
                <input className="field-input" inputMode="decimal" value={paymentForm.fee_amount} onChange={(event) => updatePaymentForm("fee_amount", event.target.value)} onBlur={() => updatePaymentForm("fee_amount", normalizeMoney(paymentForm.fee_amount))} />
              </Field>
              <Field label="Solicitação de alçada (apreq_...)">
                <input className="field-input" value={paymentForm.approval_request_id} onChange={(event) => updatePaymentForm("approval_request_id", event.target.value)} placeholder="Obrigatório quando o pagamento exceder o limite da política" />
              </Field>
              <Field label="Comprovante / evidência" required>
                <input className="field-input" value={paymentForm.evidence_reference} onChange={(event) => updatePaymentForm("evidence_reference", event.target.value)} placeholder="ID do comprovante, extrato, DOC, Pix, boleto ou justificativa" />
              </Field>
              <Field label="Observações">
                <input className="field-input" value={paymentForm.notes} onChange={(event) => updatePaymentForm("notes", event.target.value)} placeholder="Observação opcional" />
              </Field>
            </div>
            <div className="mt-5 flex justify-end">
              <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary)] px-5 py-3 font-black text-slate-950 hover:bg-[var(--color-primary-hover)] disabled:opacity-50" type="button" onClick={() => void handlePay()} disabled={isLoading || paymentExceedsOpenAmount}>Registrar pagamento</button>
            </div>
          </Panel>

          <Panel title="Prévia da baixa" description="Confirme o efeito sobre título e caixa antes de gravar." icon={<SlidersHorizontal className="h-5 w-5" />}>
            {selectedPayable ? (
              <div className="space-y-3">
                <MiniMetric label="Fornecedor" value={payableParticipantName(selectedPayable, participants)} />
                <MiniMetric label="Documento" value={selectedPayable.document_reference || selectedPayable.id} />
                <MiniMetric label="Saldo em aberto" value={formatMoney(selectedPayable.open_amount)} highlight />
                <MiniMetric label="Valor pago" value={formatMoney(paymentForm.paid_amount)} />
                <MiniMetric label="Desconto / abatimento" value={formatMoney(paymentForm.discount_amount)} />
                <MiniMetric label="Juros + multa + tarifa" value={formatMoney(paymentChargesAmount)} />
                <MiniMetric label="Efeito no título" value={formatMoney(paymentTitleEffect)} />
                <MiniMetric label="Saldo após baixa" value={formatMoney(paymentRemainingOpenAmount)} />
                <MiniMetric label="Saída real de caixa" value={formatMoney(paymentCashMovement)} highlight />
                <MiniMetric label="Conta" value={optionName(financialAccounts, paymentForm.financial_account_id)} />
                <MiniMetric label="Forma" value={optionName(paymentMethods, paymentForm.payment_method_id)} />
                {paymentExceedsOpenAmount ? <Notice tone="error" title="Excede saldo" message="Pagamento + desconto não podem superar o saldo aberto do título." /> : null}
                {!isPositiveMoney(paymentForm.paid_amount) ? <Notice tone="warning" title="Pagamento pendente" message="Informe valor pago maior que zero. Desconto sem saída financeira não é baixa de pagamento na v1.0." /> : null}
                {!paymentForm.evidence_reference.trim() ? <Notice tone="warning" title="Evidência pendente" message="Informe comprovante ou justificativa antes da baixa." /> : null}
              </div>
            ) : (
              <p className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-sm text-[var(--color-text-muted)]">Selecione um título a pagar para visualizar a baixa.</p>
            )}
          </Panel>
        </div>
      ) : null}
    </div>
  )
}

function TabButton({ active, children, onClick, icon }: { active: boolean; children: ReactNode; onClick: () => void; icon: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-black transition ${active ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"}`}
    >
      {icon}{children}
    </button>
  )
}

function Panel({ title, description, icon, children }: { title: string; description?: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-2xl shadow-[var(--color-card-shadow)]">
      <div className="mb-5 flex items-start gap-3">
        <span className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-2 text-[var(--color-primary)]">{icon}</span>
        <div>
          <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
          {description ? <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

function KpiCard({
  title,
  value,
  description,
  icon,
  tone = "normal",
  onExport,
  isExporting,
}: {
  title: string
  value: string
  description: string
  icon: ReactNode
  tone?: "normal" | "info" | "warning" | "success"
  onExport?: () => void
  isExporting?: boolean
}) {
  const tones = {
    normal: "text-[var(--color-text)]",
    info: "text-sky-700",
    warning: "text-amber-700",
    success: "text-emerald-700",
  }
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <div className="flex items-center gap-3">
        <span className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-2 text-[var(--color-primary)]">{icon}</span>
        <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-weak)]">{title}</p>
        {onExport ? (
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting}
            className="ml-auto inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50"
            title={`Baixar XLSX - ${title}`}
          >
            {isExporting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
          </button>
        ) : null}
      </div>
      <p className={`mt-4 text-xl font-black ${tones[tone]}`}>{value}</p>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{description}</p>
    </div>
  )
}

function Notice({ tone, title, message, onClose }: { tone: "error" | "success" | "info" | "warning"; title: string; message: string; onClose?: () => void }) {
  const toneMap = {
    error: { box: "border-red-500/30 bg-red-500/10 text-red-700", icon: <XCircle className="h-5 w-5 text-red-600" /> },
    success: { box: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700", icon: <CheckCircle2 className="h-5 w-5 text-emerald-600" /> },
    info: { box: "border-sky-500/30 bg-sky-500/10 text-sky-700", icon: <ShieldCheck className="h-5 w-5 text-sky-600" /> },
    warning: { box: "border-amber-500/30 bg-amber-500/10 text-amber-700", icon: <AlertTriangle className="h-5 w-5 text-amber-600" /> },
  }
  const style = toneMap[tone]
  return (
    <div className={`flex gap-3 rounded-2xl border p-4 text-sm ${style.box}`}>
      <div className="mt-0.5">{style.icon}</div>
      <div className="flex-1">
        <p className="font-black">{title}</p>
        <p className="mt-1 leading-6">{message}</p>
      </div>
      {onClose ? <button className="font-black" type="button" onClick={onClose}>Fechar</button> : null}
    </div>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block space-y-1.5 text-sm font-bold text-[var(--color-text-muted)]">
      <span>{label}{required ? <span className="text-red-300"> *</span> : null}</span>
      {children}
    </label>
  )
}

function DataTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-3xl border border-[var(--color-border-soft)]">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-[var(--color-border-soft)] text-sm">
          <thead className="bg-[var(--color-surface-elevated)] text-left text-xs uppercase tracking-wide text-[var(--color-text-weak)]">
            <tr>{headers.map((header) => <th key={header} className="px-4 py-3 font-black">{header}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border-soft)]">{children}</tbody>
        </table>
      </div>
    </div>
  )
}

function EmptyRow({ colspan, message }: { colspan: number; message: string }) {
  return (
    <tr className="bg-[var(--color-surface)]">
      <td className="px-4 py-8 text-center text-sm text-[var(--color-text-muted)]" colSpan={colspan}>{message}</td>
    </tr>
  )
}

function StatusBadge({ status, label }: { status?: string | null; label?: string }) {
  const resolved = status ?? "neutral"
  const styles = resolved.includes("cancel") || resolved === "danger"
    ? "border-red-500/30 bg-red-500/10 text-red-700"
    : resolved.includes("paid") || resolved.includes("confirmed") || resolved === "success"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700"
      : resolved.includes("overdue") || resolved.includes("pending") || resolved === "warning"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-700"
        : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)]"
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-black ${styles}`}>{label ?? statusLabel(status)}</span>
}

function PurchaseFilters({
  search,
  setSearch,
  status,
  setStatus,
  supplier,
  setSupplier,
  type,
  setType,
  from,
  setFrom,
  to,
  setTo,
  suppliers,
  onClear,
}: {
  search: string
  setSearch: (value: string) => void
  status: string
  setStatus: (value: string) => void
  supplier: string
  setSupplier: (value: string) => void
  type: string
  setType: (value: string) => void
  from: string
  setFrom: (value: string) => void
  to: string
  setTo: (value: string) => void
  suppliers: Participant[]
  onClear: () => void
}) {
  return (
    <FilterShell>
      <SearchField value={search} onChange={setSearch} placeholder="Buscar por fornecedor, documento, ID, tipo ou observação" />
      <select className="field-input" value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">Todos os status</option>
        {['draft', 'confirmed', 'cancelled'].map((option) => <option key={option} value={option}>{statusLabel(option)}</option>)}
      </select>
      <select className="field-input" value={supplier} onChange={(event) => setSupplier(event.target.value)}>
        <option value="">Todos os fornecedores</option>
        {suppliers.map((item) => <option key={item.id} value={item.id}>{item.trade_name || item.name}</option>)}
      </select>
      <select className="field-input" value={type} onChange={(event) => setType(event.target.value)}>
        <option value="">Todos os tipos</option>
        {purchaseTypeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <DateField label="De" value={from} onChange={setFrom} />
      <DateField label="Até" value={to} onChange={setTo} />
      <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50" type="button" onClick={onClear}>Limpar filtros</button>
    </FilterShell>
  )
}

function PayableFilters({
  search,
  setSearch,
  status,
  setStatus,
  supplier,
  setSupplier,
  category,
  setCategory,
  account,
  setAccount,
  from,
  setFrom,
  to,
  setTo,
  minAmount,
  setMinAmount,
  maxAmount,
  setMaxAmount,
  suppliers,
  categories,
  accounts,
  onClear,
}: {
  search: string
  setSearch: (value: string) => void
  status: string
  setStatus: (value: string) => void
  supplier: string
  setSupplier: (value: string) => void
  category: string
  setCategory: (value: string) => void
  account: string
  setAccount: (value: string) => void
  from: string
  setFrom: (value: string) => void
  to: string
  setTo: (value: string) => void
  minAmount: string
  setMinAmount: (value: string) => void
  maxAmount: string
  setMaxAmount: (value: string) => void
  suppliers: Participant[]
  categories: FinancialCategory[]
  accounts: FinancialAccount[]
  onClear: () => void
}) {
  return (
    <FilterShell>
      <SearchField value={search} onChange={setSearch} placeholder="Buscar por fornecedor, documento, categoria, conta, ID ou observação" />
      <select className="field-input" value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">Todos os status</option>
        {['open', 'partially_paid', 'overdue', 'paid', 'cancelled', 'written_off'].map((option) => <option key={option} value={option}>{statusLabel(option)}</option>)}
      </select>
      <select className="field-input" value={supplier} onChange={(event) => setSupplier(event.target.value)}>
        <option value="">Todos os fornecedores</option>
        {suppliers.map((item) => <option key={item.id} value={item.id}>{item.trade_name || item.name}</option>)}
      </select>
      <select className="field-input" value={category} onChange={(event) => setCategory(event.target.value)}>
        <option value="">Todas as categorias</option>
        {categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <select className="field-input" value={account} onChange={(event) => setAccount(event.target.value)}>
        <option value="">Todas as contas</option>
        {accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <DateField label="Venc. de" value={from} onChange={setFrom} />
      <DateField label="Venc. até" value={to} onChange={setTo} />
      <input className="field-input" inputMode="decimal" value={minAmount} onChange={(event) => setMinAmount(event.target.value)} placeholder="Valor mín." />
      <input className="field-input" inputMode="decimal" value={maxAmount} onChange={(event) => setMaxAmount(event.target.value)} placeholder="Valor máx." />
      <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50" type="button" onClick={onClear}>Limpar filtros</button>
    </FilterShell>
  )
}

function FilterShell({ children }: { children: ReactNode }) {
  return (
    <div className="mb-4 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">
        <Filter className="h-4 w-4" /> Filtros da listagem
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{children}</div>
    </div>
  )
}

function SearchField({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="relative block md:col-span-2">
      <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
      <input className="field-input pl-11" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  )
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="relative block">
      <CalendarDays className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
      <input aria-label={label} className="field-input pl-11" type="date" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function ExportBar({
  count,
  label,
  onCsv,
  onXlsx,
  note,
  isExporting,
}: {
  count: number
  label: string
  onCsv: () => void
  onXlsx: () => void
  note?: string
  isExporting?: boolean
}) {
  return (
    <div className="mb-4 flex flex-col gap-3 rounded-3xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3 text-[var(--color-primary)]">
        <Download className="mt-0.5 h-5 w-5" />
        <div>
          <p className="font-black">Exportação da listagem filtrada</p>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">{count} {label}. O CSV/XLSX respeita busca, status, datas, fornecedor, conta e demais filtros aplicados.</p>
          {note ? <p className="mt-1 text-xs font-bold text-[var(--color-text-muted)]">{note}</p> : null}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50" type="button" onClick={onCsv} disabled={count === 0 || isExporting}>{isExporting ? "Exportando..." : "Exportar CSV"}</button>
        <button className="inline-flex items-center justify-center rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary)] px-5 py-3 font-black text-slate-950 hover:bg-[var(--color-primary-hover)] disabled:opacity-50" type="button" onClick={onXlsx} disabled={count === 0 || isExporting}>{isExporting ? "Exportando..." : "Exportar XLSX"}</button>
      </div>
    </div>
  )
}

function ActionCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left shadow-sm transition hover:border-[var(--color-primary-border)] hover:bg-[var(--color-hover)]">
      <p className="font-black text-[var(--color-text)]">{title}</p>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{description}</p>
    </button>
  )
}

function FlowStep({ icon, title, description }: { icon: ReactNode; title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <div className="mb-3 inline-flex rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-2 text-[var(--color-primary)]">{icon}</div>
      <p className="font-black text-[var(--color-text)]">{title}</p>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">{description}</p>
    </div>
  )
}

function FlowArrow() {
  return <div className="hidden items-center justify-center text-[var(--color-primary)] md:flex"><ArrowRight className="h-5 w-5" /></div>
}

function ChecklistItem({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-3 text-sm text-[var(--color-text-muted)]">
      {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" /> : <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" />}
      <span>{label}</span>
    </div>
  )
}

function MiniMetric({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`rounded-2xl border p-3 ${highlight ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text)]"}`}>
      <p className={`text-xs font-black uppercase tracking-wide ${highlight ? "text-[var(--color-primary)]" : "text-[var(--color-text-weak)]"}`}>{label}</p>
      <p className="mt-1 font-black">{value || "—"}</p>
    </div>
  )
}

export default PurchasesPayablesPage
