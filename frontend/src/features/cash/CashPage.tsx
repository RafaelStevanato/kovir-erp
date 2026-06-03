import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, ArrowDownUp, Banknote, CheckCircle2, Download, Landmark, RefreshCw, RotateCcw, WalletCards, X } from "lucide-react"

import { SearchableSelect } from "../../components/SearchableSelect"
import { useActiveCompany } from "../../config/useActiveCompany"
import { ApiError } from "../../lib/api"
import { dateCell, dateTimeCell, exportXlsxWorkbook, moneyCell } from "../../lib/exportTable"
import { listReceivableTitles } from "../accountsReceivable/accountsReceivableApi"
import type { ReceivableTitle } from "../accountsReceivable/types"
import { listFinancialAccounts } from "../financial/financialApi"
import type { FinancialAccount } from "../financial/types"
import { getSalesPaymentMethods } from "../sales/salesApi"
import type { PaymentMethod } from "../sales/types"
import { createManualFinancialMovement, createSettlement, getCashDiagnostics, getCashSummary, listFinancialAccountBalances, listFinancialMovements, listSettlements, reverseManualFinancialMovement, reverseSettlement } from "./cashApi"
import type { CashDiagnostics, CashSummary, FinancialAccountBalance, FinancialMovement, Settlement } from "./types"

type TabKey = "overview" | "receive" | "settlements" | "movements" | "manual"
type ManualMovementType = "adjustment" | "fee" | "tax" | "other"
type CashListFilters = Record<string, string | undefined>
type SettlementFilterState = {
  settlement_from: string
  settlement_to: string
  status: string
  financial_account_id: string
  payment_method_id: string
  q: string
}
type MovementFilterState = {
  movement_from: string
  movement_to: string
  financial_account_id: string
  direction: string
  movement_type: string
  status: string
  reconciliation_status: string
  q: string
}

const PAGE_SIZE = 50
const PAGE_FETCH_LIMIT = PAGE_SIZE + 1
const AUXILIARY_LIMIT = 200
const EXPORT_PAGE_SIZE = 200
const EXPORT_MAX_ROWS = 5000

const EMPTY_SETTLEMENT_FILTERS: SettlementFilterState = {
  settlement_from: "",
  settlement_to: "",
  status: "",
  financial_account_id: "",
  payment_method_id: "",
  q: "",
}

const EMPTY_MOVEMENT_FILTERS: MovementFilterState = {
  movement_from: "",
  movement_to: "",
  financial_account_id: "",
  direction: "",
  movement_type: "",
  status: "",
  reconciliation_status: "",
  q: "",
}

const MOVEMENT_LIST_TYPES = ["receipt", "payment", "reversal", "adjustment", "transfer", "fee", "tax", "opening_balance", "manual", "manual_entry", "other"]

const MOVEMENT_TYPE_OPTIONS: { value: ManualMovementType; label: string }[] = [
  { value: "adjustment", label: "Ajuste operacional" },
  { value: "fee", label: "Tarifa bancária" },
  { value: "tax", label: "Imposto retido" },
  { value: "other", label: "Outro ajuste justificado" },
]

const tabs: { key: TabKey; label: string; icon: ReactNode }[] = [
  { key: "overview", label: "Visão geral", icon: <WalletCards className="h-4 w-4" /> },
  { key: "receive", label: "Receber título", icon: <Banknote className="h-4 w-4" /> },
  { key: "settlements", label: "Baixas", icon: <CheckCircle2 className="h-4 w-4" /> },
  { key: "movements", label: "Movimentos", icon: <ArrowDownUp className="h-4 w-4" /> },
  { key: "manual", label: "Movimento manual", icon: <Landmark className="h-4 w-4" /> },
]

function formatMoney(value?: string | null) {
  const number = Number(value ?? 0)
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isFinite(number) ? number : 0)
}

function parseMoneyInput(value?: string | null) {
  const raw = String(value ?? "0").trim()
  const normalized = raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

function formatMoneyNumber(value: number) {
  return formatMoney(Number.isFinite(value) ? value.toFixed(2) : "0")
}

function formatDate(value?: string | null) {
  if (!value) return "—"
  const [year, month, day] = value.split("-")
  return year && month && day ? `${day}/${month}/${year}` : value
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function directionLabel(d: string) {
  if (d === "inflow") return "Entrada"
  if (d === "outflow") return "Saída"
  return d
}

function reconciliationLabel(s: string) {
  if (s === "pending") return "Pendente"
  if (s === "matched") return "Conciliado"
  if (s === "divergent") return "Divergente"
  if (s === "reconciled") return "Conciliado"
  if (s === "ignored") return "Ignorado"
  if (s === "reversed") return "Revertido"
  return s
}

function movementStatusLabel(s: string) {
  if (s === "posted") return "Postado"
  if (s === "reversed") return "Revertido"
  if (s === "cancelled") return "Cancelado"
  return s
}

function movementTypeLabel(s: string) {
  const labels: Record<string, string> = {
    receipt: "Recebimento",
    payment: "Pagamento",
    reversal: "Estorno",
    adjustment: "Ajuste operacional",
    transfer: "Transferência",
    fee: "Tarifa",
    tax: "Imposto",
    opening_balance: "Saldo inicial",
    manual: "Manual",
    manual_entry: "Manual",
    other: "Outro",
  }
  return labels[s] ?? s
}

function settlementStatusLabel(s: string) {
  if (s === "active") return "Ativa"
  if (s === "reversed") return "Estornada"
  return s
}

function titleStatusLabel(s: string) {
  if (s === "open") return "Aberto"
  if (s === "overdue") return "Vencido"
  if (s === "partially_received") return "Parcial"
  return s
}

function titleParticipantName(title: ReceivableTitle) {
  return String(title.participant_snapshot?.name ?? title.participant_id)
}

function titleReference(title: ReceivableTitle) {
  const snapshotSaleNumber = title.source_snapshot?.sale_number_text
  if (title.document_reference) return title.document_reference
  if (typeof snapshotSaleNumber === "string" && snapshotSaleNumber) return snapshotSaleNumber
  return title.sale_id ?? title.id
}

function cleanApiFilters(filters: CashListFilters): CashListFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== undefined && value !== "")) as CashListFilters
}

function settlementApiFilters(filters: SettlementFilterState, page: number, limit = PAGE_FETCH_LIMIT, offset = page * PAGE_SIZE): CashListFilters {
  return cleanApiFilters({
    settlement_from: filters.settlement_from,
    settlement_to: filters.settlement_to,
    status: filters.status,
    financial_account_id: filters.financial_account_id,
    payment_method_id: filters.payment_method_id,
    q: filters.q.trim(),
    limit: String(limit),
    offset: String(offset),
  })
}

function movementApiFilters(filters: MovementFilterState, page: number, limit = PAGE_FETCH_LIMIT, offset = page * PAGE_SIZE): CashListFilters {
  return cleanApiFilters({
    movement_from: filters.movement_from,
    movement_to: filters.movement_to,
    financial_account_id: filters.financial_account_id,
    direction: filters.direction,
    movement_type: filters.movement_type,
    status: filters.status,
    reconciliation_status: filters.reconciliation_status,
    q: filters.q.trim(),
    limit: String(limit),
    offset: String(offset),
  })
}

export function CashPage() {
  const { companyId, activeCompanyName, isCompanyResolved, companyError } = useActiveCompany()
  const [activeTab, setActiveTab] = useState<TabKey>("overview")
  const [diagnostics, setDiagnostics] = useState<CashDiagnostics | null>(null)
  const [summary, setSummary] = useState<CashSummary | null>(null)
  const [titles, setTitles] = useState<ReceivableTitle[]>([])
  const [accounts, setAccounts] = useState<FinancialAccount[]>([])
  const [balances, setBalances] = useState<FinancialAccountBalance[]>([])
  const [settlements, setSettlements] = useState<Settlement[]>([])
  const [movements, setMovements] = useState<FinancialMovement[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reversalModal, setReversalModal] = useState<{ settlement: Settlement } | null>(null)
  const [reversalReason, setReversalReason] = useState("")
  const [manualReversalModal, setManualReversalModal] = useState<{ movement: FinancialMovement } | null>(null)
  const [manualReversalReason, setManualReversalReason] = useState("")
  const [settlementsDateFrom, setSettlementsDateFrom] = useState("")
  const [settlementsDateTo, setSettlementsDateTo] = useState("")
  const [settlementsStatusFilter, setSettlementsStatusFilter] = useState("")
  const [settlementsAccountFilter, setSettlementsAccountFilter] = useState("")
  const [settlementsPaymentMethodFilter, setSettlementsPaymentMethodFilter] = useState("")
  const [settlementsSearch, setSettlementsSearch] = useState("")
  const [appliedSettlementFilters, setAppliedSettlementFilters] = useState<SettlementFilterState>(EMPTY_SETTLEMENT_FILTERS)
  const [settlementsPage, setSettlementsPage] = useState(0)
  const [hasNextSettlementsPage, setHasNextSettlementsPage] = useState(false)
  const [exportingSettlements, setExportingSettlements] = useState(false)
  const [movementsDateFrom, setMovementsDateFrom] = useState("")
  const [movementsDateTo, setMovementsDateTo] = useState("")
  const [movementsAccountFilter, setMovementsAccountFilter] = useState("")
  const [movementsDirectionFilter, setMovementsDirectionFilter] = useState("")
  const [movementsTypeFilter, setMovementsTypeFilter] = useState("")
  const [movementsStatusFilter, setMovementsStatusFilter] = useState("")
  const [movementsReconciliationFilter, setMovementsReconciliationFilter] = useState("")
  const [movementsSearch, setMovementsSearch] = useState("")
  const [appliedMovementFilters, setAppliedMovementFilters] = useState<MovementFilterState>(EMPTY_MOVEMENT_FILTERS)
  const [movementsPage, setMovementsPage] = useState(0)
  const [hasNextMovementsPage, setHasNextMovementsPage] = useState(false)
  const [exportingMovements, setExportingMovements] = useState(false)
  const [receiptForm, setReceiptForm] = useState({
    financial_title_id: "",
    financial_account_id: "",
    payment_method_id: "",
    competency_date: "",
    settlement_date: today(),
    received_amount: "0",
    discount_amount: "0",
    interest_amount: "0",
    penalty_amount: "0",
    fee_amount: "0",
    evidence_reference: "",
    notes: "",
  })
  const [manualForm, setManualForm] = useState({
    financial_account_id: "",
    direction: "inflow" as "inflow" | "outflow",
    movement_type: "adjustment" as ManualMovementType,
    movement_date: today(),
    amount: "0",
    description: "",
  })

  const loadData = useCallback(async () => {
    if (!companyId || !isCompanyResolved) return
    setLoading(true)
    setError(null)
    try {
      const [diagRes, summaryRes, openTitlesRes, overdueTitlesRes, partialTitlesRes, accountsRes, balancesRes, settlementsRes, movementsRes, paymentMethodsRes] = await Promise.all([
        getCashDiagnostics(),
        getCashSummary(companyId),
        listReceivableTitles(companyId, { status: "open", limit: AUXILIARY_LIMIT, offset: 0 }),
        listReceivableTitles(companyId, { status: "overdue", limit: AUXILIARY_LIMIT, offset: 0 }),
        listReceivableTitles(companyId, { status: "partially_received", limit: AUXILIARY_LIMIT, offset: 0 }),
        listFinancialAccounts(companyId, { status: "active", limit: AUXILIARY_LIMIT, offset: 0 }),
        listFinancialAccountBalances(companyId),
        listSettlements(companyId, settlementApiFilters(appliedSettlementFilters, settlementsPage)),
        listFinancialMovements(companyId, movementApiFilters(appliedMovementFilters, movementsPage)),
        getSalesPaymentMethods({ company_id: companyId }),
      ])
      const receivableTitles = new Map<string, ReceivableTitle>()
      for (const title of [...openTitlesRes.data, ...overdueTitlesRes.data, ...partialTitlesRes.data]) {
        receivableTitles.set(title.id, title)
      }
      setDiagnostics(diagRes.data)
      setSummary(summaryRes.data)
      setTitles([...receivableTitles.values()].filter((title) => Number(title.open_amount) > 0 && ["open", "overdue", "partially_received"].includes(title.status)))
      setAccounts(accountsRes.data.filter((account) => account.status === "active"))
      setBalances(balancesRes.data)
      setSettlements(settlementsRes.data.slice(0, PAGE_SIZE))
      setHasNextSettlementsPage(settlementsRes.data.length > PAGE_SIZE)
      setMovements(movementsRes.data.slice(0, PAGE_SIZE))
      setHasNextMovementsPage(movementsRes.data.length > PAGE_SIZE)
      setPaymentMethods(paymentMethodsRes.data)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao carregar recebimentos e movimentos financeiros.")
    } finally {
      setLoading(false)
    }
  }, [appliedMovementFilters, appliedSettlementFilters, companyId, isCompanyResolved, movementsPage, settlementsPage])

  useEffect(() => {
    if (!isCompanyResolved) return
    void loadData()
  }, [isCompanyResolved, loadData])

  const selectedTitle = useMemo(() => titles.find((title) => title.id === receiptForm.financial_title_id), [titles, receiptForm.financial_title_id])

  const receivePreview = useMemo(() => {
    const received = parseMoneyInput(receiptForm.received_amount)
    const discount = parseMoneyInput(receiptForm.discount_amount)
    const interest = parseMoneyInput(receiptForm.interest_amount)
    const penalty = parseMoneyInput(receiptForm.penalty_amount)
    const fee = parseMoneyInput(receiptForm.fee_amount)
    const openAmount = parseMoneyInput(selectedTitle?.open_amount)
    const titleEffect = received + discount
    const movementAmount = received + interest + penalty - fee
    const remainingOpenAmount = openAmount - titleEffect
    const errors: string[] = []

    if (!selectedTitle) errors.push("Selecione um título a receber.")
    if (!receiptForm.financial_account_id) errors.push("Selecione a conta financeira de entrada.")
    if (!receiptForm.settlement_date) errors.push("Informe a data da baixa.")
    if ([received, discount, interest, penalty, fee].some((value) => !Number.isFinite(value))) errors.push("Informe valores monetários válidos.")
    if (errors.length === 0) {
      if (titleEffect <= 0) errors.push("A baixa precisa reduzir o saldo do título.")
      if (movementAmount < 0) errors.push("O impacto no caixa não pode ficar negativo.")
      if (titleEffect - openAmount > 0.0001) errors.push("A baixa não pode exceder o saldo aberto do título.")
    }

    return { received, discount, interest, penalty, fee, titleEffect, movementAmount, remainingOpenAmount, errors, canSubmit: errors.length === 0 }
  }, [receiptForm, selectedTitle])

  const selectedManualAccount = useMemo(
    () => accounts.find((account) => account.id === manualForm.financial_account_id),
    [accounts, manualForm.financial_account_id],
  )

  const selectedManualBalance = useMemo(
    () => balances.find((balance) => balance.financial_account_id === manualForm.financial_account_id),
    [balances, manualForm.financial_account_id],
  )

  const manualPreview = useMemo(() => {
    const amount = parseMoneyInput(manualForm.amount)
    const currentBalance = parseMoneyInput(selectedManualBalance?.current_balance_amount ?? selectedManualAccount?.opening_balance_amount ?? "0")
    const delta = manualForm.direction === "inflow" ? amount : -amount
    const projectedBalance = currentBalance + delta
    const description = manualForm.description.trim()
    const movementTypeIsAllowed = MOVEMENT_TYPE_OPTIONS.some((option) => option.value === manualForm.movement_type)
    const errors: string[] = []

    if (!selectedManualAccount) errors.push("Selecione a conta financeira.")
    if (!manualForm.movement_date) errors.push("Informe a data do movimento.")
    if (!movementTypeIsAllowed) errors.push("Selecione um tipo de movimento manual válido.")
    if (!Number.isFinite(amount) || amount <= 0) errors.push("Informe valor maior que zero.")
    if (description.length < 5) errors.push("Informe uma justificativa operacional com pelo menos 5 caracteres.")

    return {
      amount,
      currentBalance,
      delta,
      projectedBalance,
      description,
      canSubmit: errors.length === 0,
      errors,
    }
  }, [manualForm, selectedManualAccount, selectedManualBalance])

  function fillTitleAmount(titleId: string) {
    const title = titles.find((item) => item.id === titleId)
    setReceiptForm((current) => ({
      ...current,
      financial_title_id: titleId,
      financial_account_id: title?.expected_financial_account_id || current.financial_account_id,
      payment_method_id: title?.payment_method_id || current.payment_method_id,
      competency_date: title?.competency_date ?? current.competency_date,
      received_amount: title?.open_amount ?? current.received_amount,
    }))
  }

  async function handleReceive() {
    setError(null)
    setMessage(null)
    if (!receivePreview.canSubmit) {
      setError(receivePreview.errors[0] ?? "Revise os dados da baixa.")
      return
    }
    setSaving(true)
    try {
      await createSettlement({
        company_id: companyId,
        financial_title_id: receiptForm.financial_title_id,
        financial_account_id: receiptForm.financial_account_id,
        payment_method_id: receiptForm.payment_method_id || null,
        competency_date: receiptForm.competency_date || null,
        settlement_date: receiptForm.settlement_date,
        received_amount: receiptForm.received_amount,
        discount_amount: receiptForm.discount_amount,
        interest_amount: receiptForm.interest_amount,
        penalty_amount: receiptForm.penalty_amount,
        fee_amount: receiptForm.fee_amount,
        evidence_reference: receiptForm.evidence_reference || null,
        notes: receiptForm.notes || null,
      })
      setMessage("Recebimento registrado. O título foi baixado e o movimento financeiro interno ficou pendente de conciliação.")
      setReceiptForm((current) => ({ ...current, financial_title_id: "", payment_method_id: "", competency_date: "", received_amount: "0", discount_amount: "0", interest_amount: "0", penalty_amount: "0", fee_amount: "0", evidence_reference: "", notes: "" }))
      await loadData()
      setActiveTab("settlements")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao registrar recebimento.")
    } finally {
      setSaving(false)
    }
  }

  async function handleManualMovement() {
    setError(null)
    setMessage(null)
    if (!manualPreview.canSubmit) {
      setError(manualPreview.errors[0] ?? "Revise os dados do movimento manual.")
      return
    }
    setSaving(true)
    try {
      await createManualFinancialMovement({ company_id: companyId, ...manualForm, description: manualPreview.description })
      setMessage("Movimento financeiro manual registrado com saldo interno atualizado.")
      setManualForm((current) => ({ ...current, amount: "0", description: "" }))
      await loadData()
      setActiveTab("movements")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao registrar movimento manual.")
    } finally {
      setSaving(false)
    }
  }

  function openReversalModal(settlement: Settlement) {
    setReversalReason("")
    setReversalModal({ settlement })
  }

  async function confirmReversal() {
    if (!reversalModal || !reversalReason.trim()) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      await reverseSettlement(reversalModal.settlement.id, reversalReason.trim())
      setMessage("Baixa estornada. O título foi reaberto/ajustado e o movimento financeiro vinculado foi removido.")
      setReversalModal(null)
      setReversalReason("")
      await loadData()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao estornar baixa.")
    } finally {
      setSaving(false)
    }
  }

  function canReverseManualMovement(movement: FinancialMovement) {
    return (
      movement.source_type === "manual"
      && !movement.settlement_id
      && !movement.financial_title_id
      && movement.status === "posted"
      && !movement.reversal_of_movement_id
      && !["matched", "divergent", "reversed"].includes(movement.reconciliation_status)
    )
  }

  function openManualReversalModal(movement: FinancialMovement) {
    setManualReversalReason("")
    setManualReversalModal({ movement })
  }

  async function confirmManualReversal() {
    if (!manualReversalModal || !manualReversalReason.trim()) return
    setSaving(true)
    setError(null)
    setMessage(null)
    try {
      await reverseManualFinancialMovement(manualReversalModal.movement.id, manualReversalReason.trim())
      setMessage("Movimento manual estornado. Uma contrapartida financeira foi registrada e o saldo interno foi ajustado.")
      setManualReversalModal(null)
      setManualReversalReason("")
      await loadData()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao estornar movimento manual.")
    } finally {
      setSaving(false)
    }
  }

  const accountsById = useMemo(() => new Map(accounts.map((account) => [account.id, account])), [accounts])
  const paymentMethodsById = useMemo(() => new Map(paymentMethods.map((method) => [method.id, method])), [paymentMethods])

  function settlementTitleLabel(settlement: Settlement) {
    return settlement.financial_title_reference || settlement.financial_title_id
  }

  function settlementParticipantLabel(settlement: Settlement) {
    return settlement.participant_name || settlement.participant_id || "Sem participante"
  }

  const settlementAccountLabel = useCallback((settlement: Settlement) => {
    return accountsById.get(settlement.financial_account_id)?.name || settlement.financial_account_id
  }, [accountsById])

  const settlementPaymentMethodLabel = useCallback((settlement: Settlement) => {
    if (!settlement.payment_method_id) return "Sem forma informada"
    return paymentMethodsById.get(settlement.payment_method_id)?.name || settlement.payment_method_id
  }, [paymentMethodsById])

  function settlementInstallmentLabel(settlement: Settlement) {
    if (!settlement.financial_title_installment_number || !settlement.financial_title_installment_total) return "Parcela não informada"
    return `${settlement.financial_title_installment_number}/${settlement.financial_title_installment_total}`
  }

  const movementAccountLabel = useCallback((movement: FinancialMovement) => {
    return movement.financial_account_name || accountsById.get(movement.financial_account_id)?.name || movement.financial_account_id
  }, [accountsById])

  function movementParticipantLabel(movement: FinancialMovement) {
    return movement.participant_name || movement.participant_id || "Sem participante"
  }

  function movementTitleLabel(movement: FinancialMovement) {
    return movement.financial_title_reference || movement.financial_title_id || "Sem título vinculado"
  }

  function movementInstallmentLabel(movement: FinancialMovement) {
    if (!movement.financial_title_installment_number || !movement.financial_title_installment_total) return "Parcela não informada"
    return `${movement.financial_title_installment_number}/${movement.financial_title_installment_total}`
  }

  function movementOriginLabel(movement: FinancialMovement) {
    if (movement.settlement_id) return `Baixa ${movement.settlement_id.slice(-8)}`
    if (movement.source_type === "settlement_reversal") return `Estorno da baixa ${movement.source_id.slice(-8)}`
    return `${movement.source_type}:${movement.source_id}`
  }

  function signedMovementAmount(movement: FinancialMovement) {
    const amount = Number(movement.amount ?? 0)
    if (!Number.isFinite(amount)) return 0
    return movement.direction === "outflow" ? -amount : amount
  }

  function isActiveMovement(movement: FinancialMovement) {
    return movement.status === "posted" && movement.reconciliation_status !== "reversed" && !movement.reversal_of_movement_id
  }

  const filteredSettlements = settlements

  const hasSettlementFilters = Boolean(settlementsDateFrom || settlementsDateTo || settlementsStatusFilter || settlementsAccountFilter || settlementsPaymentMethodFilter || settlementsSearch.trim())

  function currentSettlementFilters(): SettlementFilterState {
    return {
      settlement_from: settlementsDateFrom,
      settlement_to: settlementsDateTo,
      status: settlementsStatusFilter,
      financial_account_id: settlementsAccountFilter,
      payment_method_id: settlementsPaymentMethodFilter,
      q: settlementsSearch,
    }
  }

  function applySettlementFilters() {
    setAppliedSettlementFilters(currentSettlementFilters())
    setSettlementsPage(0)
  }

  function clearSettlementFilters() {
    setSettlementsDateFrom("")
    setSettlementsDateTo("")
    setSettlementsStatusFilter("")
    setSettlementsAccountFilter("")
    setSettlementsPaymentMethodFilter("")
    setSettlementsSearch("")
    setAppliedSettlementFilters(EMPTY_SETTLEMENT_FILTERS)
    setSettlementsPage(0)
  }

  const movementTypeOptions = MOVEMENT_LIST_TYPES

  const filteredMovements = movements

  const movementSummary = useMemo(() => {
    return filteredMovements.reduce(
      (acc, movement) => {
        const amount = Number(movement.amount ?? 0)
        const safeAmount = Number.isFinite(amount) ? amount : 0
        const active = isActiveMovement(movement)
        if (active && movement.direction === "inflow") acc.inflow += safeAmount
        if (active && movement.direction === "outflow") acc.outflow += safeAmount
        if (active && movement.reconciliation_status === "pending") acc.pending += 1
        if (active && movement.reconciliation_status === "matched") acc.matched += 1
        if (active && movement.reconciliation_status === "divergent") acc.divergent += 1
        if (movement.reconciliation_status === "reversed") acc.reversed += 1
        if (movement.reversal_of_movement_id) acc.reversal += 1
        return acc
      },
      { inflow: 0, outflow: 0, pending: 0, matched: 0, divergent: 0, reversed: 0, reversal: 0 },
    )
  }, [filteredMovements])

  const hasMovementFilters = Boolean(movementsDateFrom || movementsDateTo || movementsAccountFilter || movementsDirectionFilter || movementsTypeFilter || movementsStatusFilter || movementsReconciliationFilter || movementsSearch.trim())

  function currentMovementFilters(): MovementFilterState {
    return {
      movement_from: movementsDateFrom,
      movement_to: movementsDateTo,
      financial_account_id: movementsAccountFilter,
      direction: movementsDirectionFilter,
      movement_type: movementsTypeFilter,
      status: movementsStatusFilter,
      reconciliation_status: movementsReconciliationFilter,
      q: movementsSearch,
    }
  }

  function applyMovementFilters() {
    setAppliedMovementFilters(currentMovementFilters())
    setMovementsPage(0)
  }

  function clearMovementFilters() {
    setMovementsDateFrom("")
    setMovementsDateTo("")
    setMovementsAccountFilter("")
    setMovementsDirectionFilter("")
    setMovementsTypeFilter("")
    setMovementsStatusFilter("")
    setMovementsReconciliationFilter("")
    setMovementsSearch("")
    setAppliedMovementFilters(EMPTY_MOVEMENT_FILTERS)
    setMovementsPage(0)
  }

  const accountBalanceCards = useMemo(() => {
    return accounts.map((account) => {
      const balance = balances.find((item) => item.financial_account_id === account.id)
      return {
        account,
        balance,
        amount: balance?.current_balance_amount ?? account.opening_balance_amount,
        isMaterialized: Boolean(balance),
      }
    })
  }, [accounts, balances])

  async function loadSettlementsForExport() {
    if (!companyId) return []
    const rows: Settlement[] = []
    for (let offset = 0; offset < EXPORT_MAX_ROWS; offset += EXPORT_PAGE_SIZE) {
      const response = await listSettlements(companyId, settlementApiFilters(appliedSettlementFilters, 0, EXPORT_PAGE_SIZE, offset))
      rows.push(...response.data)
      if (response.data.length < EXPORT_PAGE_SIZE) break
    }
    return rows.slice(0, EXPORT_MAX_ROWS)
  }

  async function exportSettlementsXLSX() {
    setExportingSettlements(true)
    setError(null)
    try {
      const exportRows = await loadSettlementsForExport()
      if (exportRows.length === 0) return
    const header = [
      "Data da baixa",
      "Competência",
      "Status da baixa",
      "Referência do título",
      "Status do título",
      "Parcela",
      "Participante",
      "Documento participante",
      "Conta financeira",
      "Forma de pagamento",
      "Valor recebido",
      "Desconto",
      "Juros",
      "Multa",
      "Taxa",
      "Baixado no título",
      "Movimentado no caixa",
      "Origem",
      "ID da origem",
      "Comprovante",
      "Observação",
      "ID da baixa",
      "ID do título",
    ]
      const rows = exportRows.map((s) => [
      dateCell(s.settlement_date),
      dateCell(s.competency_date),
      settlementStatusLabel(s.status),
      settlementTitleLabel(s),
      s.financial_title_status ?? "",
      settlementInstallmentLabel(s),
      settlementParticipantLabel(s),
      s.participant_document ?? "",
      settlementAccountLabel(s),
      settlementPaymentMethodLabel(s),
      moneyCell(s.received_amount),
      moneyCell(s.discount_amount),
      moneyCell(s.interest_amount),
      moneyCell(s.penalty_amount),
      moneyCell(s.fee_amount),
      moneyCell(s.title_settled_amount),
      moneyCell(s.movement_amount),
      s.source_type,
      s.source_id ?? "",
      s.evidence_reference ?? "",
      s.notes ?? "",
      s.id,
      s.financial_title_id,
    ])
      exportXlsxWorkbook([{ name: "Baixas", rows: [header, ...rows] }], `baixas_${today()}.xlsx`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao exportar baixas.")
    } finally {
      setExportingSettlements(false)
    }
  }

  async function loadMovementsForExport() {
    if (!companyId) return []
    const rows: FinancialMovement[] = []
    for (let offset = 0; offset < EXPORT_MAX_ROWS; offset += EXPORT_PAGE_SIZE) {
      const response = await listFinancialMovements(companyId, movementApiFilters(appliedMovementFilters, 0, EXPORT_PAGE_SIZE, offset))
      rows.push(...response.data)
      if (response.data.length < EXPORT_PAGE_SIZE) break
    }
    return rows.slice(0, EXPORT_MAX_ROWS)
  }

  async function exportMovementsXLSX() {
    setExportingMovements(true)
    setError(null)
    try {
      const exportRows = await loadMovementsForExport()
      if (exportRows.length === 0) return
    const header = [
      "Data do movimento",
      "Conta financeira",
      "Instituição",
      "Direção",
      "Tipo",
      "Status",
      "Conciliação",
      "Valor absoluto",
      "Valor com sinal",
      "Moeda",
      "Título",
      "Status do título",
      "Parcela",
      "Participante",
      "Documento participante",
      "Baixa vinculada",
      "Status da baixa",
      "Forma de pagamento",
      "Origem",
      "ID da origem",
      "Descrição",
      "Comprovante",
      "ID do movimento",
      "ID da conta",
      "ID do título",
      "ID do participante",
      "Movimento original estornado",
      "Criado em",
      "Atualizado em",
    ]
      const rows = exportRows.map((movement) => [
      dateCell(movement.movement_date),
      movementAccountLabel(movement),
      movement.financial_account_institution_name ?? "",
      directionLabel(movement.direction),
      movementTypeLabel(movement.movement_type),
      movementStatusLabel(movement.status),
      reconciliationLabel(movement.reconciliation_status),
      moneyCell(movement.amount),
      moneyCell(signedMovementAmount(movement)),
      movement.currency,
      movementTitleLabel(movement),
      movement.financial_title_status ?? "",
      movementInstallmentLabel(movement),
      movementParticipantLabel(movement),
      movement.participant_document ?? "",
      movement.settlement_id ?? "",
      movement.settlement_status ?? "",
      movement.payment_method_name ?? "",
      movement.source_type,
      movement.source_id,
      movement.description ?? "",
      movement.settlement_evidence_reference ?? "",
      movement.id,
      movement.financial_account_id,
      movement.financial_title_id ?? "",
      movement.participant_id ?? "",
      movement.reversal_of_movement_id ?? "",
      dateTimeCell(movement.created_at),
      dateTimeCell(movement.updated_at),
    ])
      exportXlsxWorkbook([{ name: "Movimentos", rows: [header, ...rows] }], `movimentos_financeiros_${today()}.xlsx`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Falha ao exportar movimentos.")
    } finally {
      setExportingMovements(false)
    }
  }

  const titleOptions = useMemo(() =>
    titles.map((title) => ({
      value: title.id,
      label: `${titleReference(title)} · ${titleParticipantName(title)}`,
      description: `${titleStatusLabel(title.status)} · ${formatMoney(title.open_amount)} aberto · vence ${formatDate(title.due_date)}`,
      keywords: [
        titleReference(title),
        titleParticipantName(title),
        titleStatusLabel(title.status),
        title.status,
        title.document_reference ?? "",
        title.sale_id ?? "",
        title.source_id ?? "",
        title.open_amount,
        title.due_date,
      ],
    })),
    [titles],
  )

  return (
    <div className="space-y-6">

      {reversalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-black text-[var(--color-text)]">Estornar baixa</h3>
              <button type="button" onClick={() => setReversalModal(null)} className="rounded-xl p-1 hover:bg-[var(--color-hover)]"><X className="h-4 w-4 text-[var(--color-text-muted)]" /></button>
            </div>
            <p className="mb-4 text-sm text-[var(--color-text-muted)]">Baixa de <strong className="text-[var(--color-text)]">{formatMoney(reversalModal.settlement.movement_amount)}</strong> em <strong className="text-[var(--color-text)]">{formatDate(reversalModal.settlement.settlement_date)}</strong>. O título será reaberto e o movimento financeiro removido.</p>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[var(--color-text-muted)]">Motivo do estorno *</span>
              <input value={reversalReason} onChange={(e) => setReversalReason(e.target.value)} placeholder="Informe o motivo obrigatório" className="field-input w-full" />
            </label>
            <div className="mt-5 flex gap-3">
              <button type="button" onClick={() => setReversalModal(null)} className="flex-1 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]">Cancelar</button>
              <button type="button" onClick={confirmReversal} disabled={saving || !reversalReason.trim()} className="flex-1 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-black text-red-600 disabled:opacity-60 hover:bg-red-500/20"><RotateCcw className="mr-1 inline h-3 w-3" /> Confirmar estorno</button>
            </div>
          </div>
        </div>
      )}

      {manualReversalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-black text-[var(--color-text)]">Estornar movimento manual</h3>
              <button type="button" onClick={() => setManualReversalModal(null)} className="rounded-xl p-1 hover:bg-[var(--color-hover)]"><X className="h-4 w-4 text-[var(--color-text-muted)]" /></button>
            </div>
            <p className="mb-4 text-sm text-[var(--color-text-muted)]">
              Movimento de <strong className="text-[var(--color-text)]">{formatMoney(manualReversalModal.movement.amount)}</strong> em <strong className="text-[var(--color-text)]">{formatDate(manualReversalModal.movement.movement_date)}</strong>. O Kovir criará uma contrapartida e ajustará o saldo interno.
            </p>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-[var(--color-text-muted)]">Motivo do estorno *</span>
              <input value={manualReversalReason} onChange={(e) => setManualReversalReason(e.target.value)} placeholder="Informe o motivo obrigatório" className="field-input w-full" />
            </label>
            <div className="mt-5 flex gap-3">
              <button type="button" onClick={() => setManualReversalModal(null)} className="flex-1 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]">Cancelar</button>
              <button type="button" onClick={confirmManualReversal} disabled={saving || !manualReversalReason.trim()} className="flex-1 rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-black text-red-600 disabled:opacity-60 hover:bg-red-500/20"><RotateCcw className="mr-1 inline h-3 w-3" /> Confirmar estorno</button>
            </div>
          </div>
        </div>
      )}

      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">Bloco 9</p>
            <h1 className="mt-2 text-4xl font-black text-[var(--color-text)]">Caixa e Baixas</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-muted)]">
              Registre recebimentos, baixas de títulos e movimentos financeiros internos. Dinheiro realizado não é documento fiscal e baixa não é conciliação.
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3 text-sm text-[var(--color-text)]">
              {activeCompanyName ?? "Empresa não identificada"}
            </div>
            <button type="button" onClick={loadData} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-2.5 text-sm font-semibold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-60">
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Atualizar dados
            </button>
          </div>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric accent="#0f766e" icon={<WalletCards className="h-5 w-5" />} title="Saldo interno total" value={formatMoney(summary?.internal_balance_total)} helper={`${summary?.materialized_balance_count ?? 0}/${summary?.financial_account_count ?? 0} contas materializadas`} />
        <Metric accent="#16a34a" icon={<Banknote className="h-5 w-5" />} title="Recebido" value={formatMoney(summary?.received_amount)} helper="baixas ativas" />
        <Metric accent="#65a30d" icon={<CheckCircle2 className="h-5 w-5" />} title="Descontos" value={formatMoney(summary?.discount_amount)} helper="abatimento no título" />
        <Metric accent="#2563eb" icon={<ArrowDownUp className="h-5 w-5" />} title="Entradas internas" value={formatMoney(summary?.inflow_amount)} helper="movimentos ativos" />
        <Metric accent="#dc2626" icon={<ArrowDownUp className="h-5 w-5" />} title="Saídas internas" value={formatMoney(summary?.outflow_amount)} helper="movimentos ativos" />
        <Metric accent="#7c3aed" icon={<WalletCards className="h-5 w-5" />} title="Variação líquida" value={formatMoney(summary?.net_internal_balance_delta)} helper="entradas - saídas" />
        <Metric accent="#d97706" icon={<AlertTriangle className="h-5 w-5" />} title="Pendentes conciliação" value={summary?.pending_reconciliation_count ?? 0} helper={`${formatMoney(summary?.pending_reconciliation_amount)} sem match`} />
      </section>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)} className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-black ${activeTab === tab.key ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)]"}`}>{tab.icon}{tab.label}</button>
        ))}
      </div>

      {companyError && <Notice tone="error" message={companyError} />}
      {error && <Notice tone="error" message={error} />}
      {message && <Notice tone="success" message={message} />}

      {activeTab === "overview" && (
        <section className="grid gap-6 xl:grid-cols-[1fr_1fr]">
          <Panel title="Saldos internos por conta" icon={<WalletCards className="h-5 w-5" />}>
            <div className="space-y-3">
              {accountBalanceCards.length === 0 ? <EmptyState text="Nenhuma conta financeira ativa cadastrada." /> : accountBalanceCards.map(({ account, balance, amount, isMaterialized }) => {
                return (
                  <div key={account.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-black text-[var(--color-text)]">{account.name}</p>
                        <p className="text-xs text-[var(--color-text-muted)]">{account.institution_name ?? "Sem instituição"} · {account.account_type}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wide ${isMaterialized ? "bg-emerald-500/10 text-emerald-600" : "bg-amber-500/10 text-amber-600"}`}>
                        {isMaterialized ? "Materializado" : "Saldo inicial"}
                      </span>
                    </div>
                    <p className="mt-3 text-xl font-black text-[var(--color-primary)]">{formatMoney(amount)}</p>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                      {isMaterialized
                        ? `Saldo interno atualizado pelo movimento ${balance?.last_movement_id ?? "não identificado"}. Ainda não é saldo bancário conciliado.`
                        : "Conta sem movimento materializado; exibindo saldo inicial cadastrado. Ainda não é saldo bancário conciliado."}
                    </p>
                  </div>
                )
              })}
            </div>
          </Panel>
          <Panel title="Regras de segurança" icon={<CheckCircle2 className="h-5 w-5" />}>
            {(diagnostics?.safety ?? []).length === 0 ? (
              <EmptyState text="Nenhuma regra de segurança registrada." />
            ) : (
              <ul className="space-y-3 text-sm leading-6 text-[var(--color-text-muted)]">
                {(diagnostics?.safety ?? []).map((rule) => (
                  <li key={rule} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-3">{rule}</li>
                ))}
              </ul>
            )}
          </Panel>
        </section>
      )}

      {activeTab === "receive" && (
        <Panel title="Registrar recebimento e baixa" icon={<Banknote className="h-5 w-5" />}>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Título a receber">
              <SearchableSelect
                value={receiptForm.financial_title_id}
                onChange={fillTitleAmount}
                placeholder="Buscar por participante, valor ou vencimento..."
                options={titleOptions}
                maxResults={10}
              />
            </Field>
            <Field label="Conta financeira">
              <select value={receiptForm.financial_account_id} onChange={(event) => setReceiptForm((current) => ({ ...current, financial_account_id: event.target.value }))} className="field-input">
                <option value="">Selecione a conta de entrada</option>
                {accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.account_type}</option>)}
              </select>
            </Field>
            <Field label="Forma de pagamento">
              <select value={receiptForm.payment_method_id} onChange={(event) => setReceiptForm((current) => ({ ...current, payment_method_id: event.target.value }))} className="field-input">
                <option value="">Selecione a forma de pagamento</option>
                {paymentMethods.map((method) => <option key={method.id} value={method.id}>{method.name}</option>)}
              </select>
            </Field>
            <Field label="Data da baixa"><input type="date" value={receiptForm.settlement_date} onChange={(event) => setReceiptForm((current) => ({ ...current, settlement_date: event.target.value }))} className="field-input" /></Field>
            <Field label="Data de competência">
              <input type="date" value={receiptForm.competency_date} onChange={(event) => setReceiptForm((current) => ({ ...current, competency_date: event.target.value }))} className="field-input" />
              <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">Período de competência do recebimento (para relatórios por competência)</span>
            </Field>
            <Field label="Valor recebido"><input value={receiptForm.received_amount} onChange={(event) => setReceiptForm((current) => ({ ...current, received_amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <Field label="Desconto/abatimento"><input value={receiptForm.discount_amount} onChange={(event) => setReceiptForm((current) => ({ ...current, discount_amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <Field label="Juros"><input value={receiptForm.interest_amount} onChange={(event) => setReceiptForm((current) => ({ ...current, interest_amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <Field label="Multa"><input value={receiptForm.penalty_amount} onChange={(event) => setReceiptForm((current) => ({ ...current, penalty_amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <Field label="Taxa descontada"><input value={receiptForm.fee_amount} onChange={(event) => setReceiptForm((current) => ({ ...current, fee_amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <Field label="Comprovante/referência"><input value={receiptForm.evidence_reference} onChange={(event) => setReceiptForm((current) => ({ ...current, evidence_reference: event.target.value }))} className="field-input" /></Field>
            <Field label="Observação"><input value={receiptForm.notes} onChange={(event) => setReceiptForm((current) => ({ ...current, notes: event.target.value }))} className="field-input" /></Field>
          </div>
          {selectedTitle && (
            <div className="mt-4 space-y-3 rounded-3xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-4">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-sm font-black text-[var(--color-primary)]">{titleReference(selectedTitle)} · {titleParticipantName(selectedTitle)}</p>
                  <p className="mt-1 text-xs font-semibold text-[var(--color-text-muted)]">
                    {titleStatusLabel(selectedTitle.status)} · vence {formatDate(selectedTitle.due_date)} · parcela {selectedTitle.installment_number}/{selectedTitle.installment_total}
                  </p>
                </div>
                <span className="rounded-full bg-[var(--color-surface)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">
                  Saldo aberto {formatMoney(selectedTitle.open_amount)}
                </span>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <MiniBox label="Valor original" value={formatMoney(selectedTitle.net_amount)} />
                <MiniBox label="Já recebido" value={formatMoney(selectedTitle.paid_amount)} />
                <MiniBox label="Saldo após baixa" value={formatMoneyNumber(receivePreview.remainingOpenAmount)} />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <MiniBox label="Redução no título" value={formatMoneyNumber(receivePreview.titleEffect)} helper="valor recebido + desconto" />
                <MiniBox label="Impacto no caixa" value={formatMoneyNumber(receivePreview.movementAmount)} helper="recebido + juros + multa - taxa" />
              </div>
              {receivePreview.errors.length > 0 ? (
                <div className="rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-600">
                  {receivePreview.errors[0]}
                </div>
              ) : (
                <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-600">
                  Baixa pronta para registrar. O movimento financeiro ficará pendente de conciliação.
                </div>
              )}
            </div>
          )}
          <button type="button" onClick={handleReceive} disabled={saving || !receivePreview.canSubmit} className="mt-5 rounded-2xl bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white disabled:opacity-60 hover:bg-[var(--color-primary-hover)]">
            Registrar recebimento
          </button>
        </Panel>
      )}

      {activeTab === "settlements" && (
        <Panel title="Baixas registradas" icon={<CheckCircle2 className="h-5 w-5" />}>
          <div className="mb-4 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
            <div className="grid gap-3 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
              <Field label="Buscar">
                <input value={settlementsSearch} onChange={(event) => setSettlementsSearch(event.target.value)} placeholder="Título, participante, comprovante, conta..." className="field-input" />
              </Field>
              <Field label="Status">
                <select value={settlementsStatusFilter} onChange={(event) => setSettlementsStatusFilter(event.target.value)} className="field-input">
                  <option value="">Todos</option>
                  <option value="active">Ativas</option>
                  <option value="reversed">Estornadas</option>
                </select>
              </Field>
              <Field label="Conta">
                <select value={settlementsAccountFilter} onChange={(event) => setSettlementsAccountFilter(event.target.value)} className="field-input">
                  <option value="">Todas</option>
                  {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
              </Field>
              <Field label="Forma de pagamento">
                <select value={settlementsPaymentMethodFilter} onChange={(event) => setSettlementsPaymentMethodFilter(event.target.value)} className="field-input">
                  <option value="">Todas</option>
                  <option value="__none__">Sem forma informada</option>
                  {paymentMethods.map((method) => <option key={method.id} value={method.id}>{method.name}</option>)}
                </select>
              </Field>
              <Field label="De">
                <input type="date" value={settlementsDateFrom} onChange={(event) => setSettlementsDateFrom(event.target.value)} className="field-input" />
              </Field>
              <Field label="Até">
                <input type="date" value={settlementsDateTo} onChange={(event) => setSettlementsDateTo(event.target.value)} className="field-input" />
              </Field>
              <div className="flex items-end gap-3 lg:col-span-2">
                <button type="button" onClick={applySettlementFilters} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl bg-[var(--color-primary)] px-4 py-3 text-xs font-black text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50">
                  Aplicar filtros
                </button>
                <button type="button" onClick={exportSettlementsXLSX} disabled={exportingSettlements || filteredSettlements.length === 0} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-xs font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50">
                  <Download className="h-3 w-3" /> {exportingSettlements ? "Exportando..." : "Exportar XLSX"}
                </button>
                {hasSettlementFilters && (
                  <button type="button" onClick={clearSettlementFilters} className="text-xs text-[var(--color-text-muted)] underline hover:text-[var(--color-text)]">
                    Limpar filtros
                  </button>
                )}
                <span className="ml-auto text-xs text-[var(--color-text-muted)]">Pagina {settlementsPage + 1} - {filteredSettlements.length} baixa{filteredSettlements.length !== 1 ? "s" : ""}</span>
              </div>
            </div>
            <p className="mt-3 text-xs leading-5 text-[var(--color-text-muted)]">
              Baixa reduz saldo do título e cria movimento financeiro interno. Conciliação bancária é etapa separada; se o movimento já estiver conciliado/divergente, o estorno é bloqueado pelo backend.
            </p>
          </div>
          {filteredSettlements.length === 0 ? (
            <EmptyState text="Nenhuma baixa no período filtrado." />
          ) : (
            <div className="space-y-3">
              {filteredSettlements.map((settlement) => (
                <article key={settlement.id} className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <p className="break-words text-base font-black text-[var(--color-text)]">{settlementTitleLabel(settlement)}</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--color-text-muted)]">
                        {settlementParticipantLabel(settlement)} · {settlementInstallmentLabel(settlement)} · {formatDate(settlement.settlement_date)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wide ${settlement.status === "active" ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-600"}`}>
                        {settlementStatusLabel(settlement.status)}
                      </span>
                      {settlement.status === "active" ? (
                        <button type="button" onClick={() => openReversalModal(settlement)} className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-black text-red-600 hover:bg-red-500/20">
                          <RotateCcw className="mr-1 inline h-3 w-3" /> Estornar
                        </button>
                      ) : (
                        <span className="text-xs text-[var(--color-text-weak)]">Estornada</span>
                      )}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <MiniBox label="Valor recebido" value={formatMoney(settlement.received_amount)} />
                    <MiniBox label="Desconto" value={formatMoney(settlement.discount_amount)} />
                    <MiniBox label="Baixado no título" value={formatMoney(settlement.title_settled_amount)} helper="recebido + desconto" />
                    <MiniBox label="Movimentado no caixa" value={formatMoney(settlement.movement_amount)} helper="recebido + juros + multa - taxa" />
                  </div>
                  <div className="mt-4 grid gap-2 text-xs text-[var(--color-text-muted)] md:grid-cols-2">
                    <p><strong className="text-[var(--color-text)]">Conta:</strong> {settlementAccountLabel(settlement)}</p>
                    <p><strong className="text-[var(--color-text)]">Forma:</strong> {settlementPaymentMethodLabel(settlement)}</p>
                    <p><strong className="text-[var(--color-text)]">Competência:</strong> {formatDate(settlement.competency_date)}</p>
                    <p><strong className="text-[var(--color-text)]">Título:</strong> {settlement.financial_title_id}</p>
                    <p><strong className="text-[var(--color-text)]">Origem:</strong> {settlement.source_type}{settlement.source_id ? ` · ${settlement.source_id}` : ""}</p>
                    <p><strong className="text-[var(--color-text)]">Comprovante:</strong> {settlement.evidence_reference || "Não informado"}</p>
                    {settlement.notes ? <p className="md:col-span-2"><strong className="text-[var(--color-text)]">Observação:</strong> {settlement.notes}</p> : null}
                  </div>
                </article>
              ))}
              <PaginationControls
                page={settlementsPage}
                hasNextPage={hasNextSettlementsPage}
                loading={loading}
                onPrevious={() => setSettlementsPage((current) => Math.max(current - 1, 0))}
                onNext={() => setSettlementsPage((current) => current + 1)}
              />
            </div>
          )}
        </Panel>
      )}

      {activeTab === "movements" && (
        <Panel title="Movimentos financeiros internos" icon={<ArrowDownUp className="h-5 w-5" />}>
          <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <MiniBox label="Entradas ativas" value={formatMoney(movementSummary.inflow.toFixed(2))} helper="postadas, não revertidas" />
            <MiniBox label="Saídas ativas" value={formatMoney(movementSummary.outflow.toFixed(2))} helper="postadas, não revertidas" />
            <MiniBox label="Líquido ativo" value={formatMoney((movementSummary.inflow - movementSummary.outflow).toFixed(2))} helper="entradas - saídas" />
            <MiniBox label="Pendentes conciliação" value={String(movementSummary.pending)} helper={`${movementSummary.matched} conciliado(s) · ${movementSummary.divergent} divergente(s)`} />
            <MiniBox label="Movimentos revertidos" value={String(movementSummary.reversed)} helper="originais marcados como revertidos" />
            <MiniBox label="Reversões geradas" value={String(movementSummary.reversal)} helper="movimentos de contrapartida" />
          </div>
          <div className="mb-4 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
            <div className="grid gap-3 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
              <Field label="Buscar">
                <input value={movementsSearch} onChange={(event) => setMovementsSearch(event.target.value)} placeholder="Descrição, título, conta, participante, origem..." className="field-input" />
              </Field>
              <Field label="Conta">
                <select value={movementsAccountFilter} onChange={(event) => setMovementsAccountFilter(event.target.value)} className="field-input">
                  <option value="">Todas</option>
                  {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
              </Field>
              <Field label="Direção">
                <select value={movementsDirectionFilter} onChange={(event) => setMovementsDirectionFilter(event.target.value)} className="field-input">
                  <option value="">Todas</option>
                  <option value="inflow">Entrada</option>
                  <option value="outflow">Saída</option>
                </select>
              </Field>
              <Field label="Tipo">
                <select value={movementsTypeFilter} onChange={(event) => setMovementsTypeFilter(event.target.value)} className="field-input">
                  <option value="">Todos</option>
                  {movementTypeOptions.map((type) => <option key={type} value={type}>{movementTypeLabel(type)}</option>)}
                </select>
              </Field>
              <Field label="Status">
                <select value={movementsStatusFilter} onChange={(event) => setMovementsStatusFilter(event.target.value)} className="field-input">
                  <option value="">Todos</option>
                  <option value="posted">Postado</option>
                  <option value="reversed">Revertido</option>
                  <option value="cancelled">Cancelado</option>
                </select>
              </Field>
              <Field label="Conciliação">
                <select value={movementsReconciliationFilter} onChange={(event) => setMovementsReconciliationFilter(event.target.value)} className="field-input">
                  <option value="">Todas</option>
                  <option value="pending">Pendente</option>
                  <option value="matched">Conciliado</option>
                  <option value="divergent">Divergente</option>
                  <option value="ignored">Ignorado</option>
                  <option value="reversed">Revertido</option>
                </select>
              </Field>
              <Field label="De">
                <input type="date" value={movementsDateFrom} onChange={(event) => setMovementsDateFrom(event.target.value)} className="field-input" />
              </Field>
              <Field label="Até">
                <input type="date" value={movementsDateTo} onChange={(event) => setMovementsDateTo(event.target.value)} className="field-input" />
              </Field>
              <div className="flex items-end gap-3 lg:col-span-4">
                <button type="button" onClick={applyMovementFilters} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl bg-[var(--color-primary)] px-4 py-3 text-xs font-black text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50">
                  Aplicar filtros
                </button>
                <button type="button" onClick={exportMovementsXLSX} disabled={exportingMovements || filteredMovements.length === 0} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-xs font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50">
                  <Download className="h-3 w-3" /> {exportingMovements ? "Exportando..." : "Exportar XLSX"}
                </button>
                {hasMovementFilters && (
                  <button type="button" onClick={clearMovementFilters} className="text-xs text-[var(--color-text-muted)] underline hover:text-[var(--color-text)]">
                    Limpar filtros
                  </button>
                )}
                <span className="ml-auto text-xs text-[var(--color-text-muted)]">Pagina {movementsPage + 1} - {filteredMovements.length} movimento{filteredMovements.length !== 1 ? "s" : ""}</span>
              </div>
            </div>
            <p className="mt-3 text-xs leading-5 text-[var(--color-text-muted)]">
              Movimento financeiro interno altera saldo materializado do Kovir. Ele não é extrato bancário e não prova conciliação; o match bancário é controlado pela aba Conciliação Bancária.
            </p>
          </div>
          {filteredMovements.length === 0 ? (
            <EmptyState text="Nenhum movimento financeiro no filtro atual." />
          ) : (
            <div className="space-y-3">
              {filteredMovements.map((movement) => {
                const active = isActiveMovement(movement)
                return (
                  <article key={movement.id} className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <p className="break-words text-base font-black text-[var(--color-text)]">{movement.description || movementOriginLabel(movement)}</p>
                        <p className="mt-1 text-sm font-semibold text-[var(--color-text-muted)]">
                          {formatDate(movement.movement_date)} · {movementAccountLabel(movement)} · {movementTypeLabel(movement.movement_type)}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wide ${movement.direction === "inflow" ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-600"}`}>
                          {directionLabel(movement.direction)}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wide ${active ? "bg-emerald-500/10 text-emerald-600" : "bg-slate-500/10 text-slate-600"}`}>
                          {movementStatusLabel(movement.status)}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-wide ${
                          movement.reconciliation_status === "matched"
                            ? "bg-emerald-500/10 text-emerald-600"
                            : movement.reconciliation_status === "divergent"
                              ? "bg-amber-500/10 text-amber-600"
                              : movement.reconciliation_status === "reversed"
                                ? "bg-slate-500/10 text-slate-600"
                                : "bg-blue-500/10 text-blue-600"
                        }`}>
                          {reconciliationLabel(movement.reconciliation_status)}
                        </span>
                        {canReverseManualMovement(movement) ? (
                          <button type="button" onClick={() => openManualReversalModal(movement)} className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-black text-red-600 hover:bg-red-500/20">
                            <RotateCcw className="mr-1 inline h-3 w-3" /> Estornar manual
                          </button>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <MiniBox label="Valor absoluto" value={formatMoney(movement.amount)} />
                      <MiniBox label="Valor com sinal" value={formatMoney(signedMovementAmount(movement).toFixed(2))} helper="entrada positiva, saída negativa" />
                      <MiniBox label="Título" value={movementTitleLabel(movement)} helper={movementInstallmentLabel(movement)} />
                      <MiniBox label="Participante" value={movementParticipantLabel(movement)} helper={movement.participant_document ?? "documento não informado"} />
                    </div>
                    <div className="mt-4 grid gap-2 text-xs text-[var(--color-text-muted)] md:grid-cols-2">
                      <p><strong className="text-[var(--color-text)]">Origem:</strong> {movementOriginLabel(movement)}</p>
                      <p><strong className="text-[var(--color-text)]">Forma:</strong> {movement.payment_method_name || "Não informada"}</p>
                      <p><strong className="text-[var(--color-text)]">Conta:</strong> {movementAccountLabel(movement)}{movement.financial_account_institution_name ? ` · ${movement.financial_account_institution_name}` : ""}</p>
                      <p><strong className="text-[var(--color-text)]">Comprovante:</strong> {movement.settlement_evidence_reference || "Não informado"}</p>
                      <p><strong className="text-[var(--color-text)]">ID movimento:</strong> {movement.id}</p>
                      <p><strong className="text-[var(--color-text)]">ID título:</strong> {movement.financial_title_id || "Sem título"}</p>
                      {movement.reversal_of_movement_id ? <p className="md:col-span-2"><strong className="text-[var(--color-text)]">Reverte movimento:</strong> {movement.reversal_of_movement_id}</p> : null}
                    </div>
                  </article>
                )
              })}
              <PaginationControls
                page={movementsPage}
                hasNextPage={hasNextMovementsPage}
                loading={loading}
                onPrevious={() => setMovementsPage((current) => Math.max(current - 1, 0))}
                onNext={() => setMovementsPage((current) => current + 1)}
              />
            </div>
          )}
        </Panel>
      )}

      {activeTab === "manual" && (
        <Panel title="Movimento financeiro manual" icon={<Landmark className="h-5 w-5" />}>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Conta financeira">
              <select value={manualForm.financial_account_id} onChange={(event) => setManualForm((current) => ({ ...current, financial_account_id: event.target.value }))} className="field-input">
                <option value="">Selecione a conta</option>
                {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
              </select>
            </Field>
            <Field label="Direção">
              <select value={manualForm.direction} onChange={(event) => setManualForm((current) => ({ ...current, direction: event.target.value as "inflow" | "outflow" }))} className="field-input">
                <option value="inflow">Entrada</option>
                <option value="outflow">Saída</option>
              </select>
            </Field>
            <Field label="Tipo de movimento">
              <select value={manualForm.movement_type} onChange={(event) => setManualForm((current) => ({ ...current, movement_type: event.target.value as ManualMovementType }))} className="field-input">
                {MOVEMENT_TYPE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </Field>
            <Field label="Data"><input type="date" value={manualForm.movement_date} onChange={(event) => setManualForm((current) => ({ ...current, movement_date: event.target.value }))} className="field-input" /></Field>
            <Field label="Valor"><input value={manualForm.amount} onChange={(event) => setManualForm((current) => ({ ...current, amount: event.target.value }))} className="field-input" inputMode="decimal" /></Field>
            <div className="lg:col-span-2">
              <Field label="Justificativa operacional *">
                <textarea value={manualForm.description} onChange={(event) => setManualForm((current) => ({ ...current, description: event.target.value }))} className="field-input min-h-28 resize-y" placeholder="Ex.: ajuste de tarifa bancária não vinculada a título, com referência do extrato/comprovante." />
              </Field>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <MiniBox label="Saldo atual interno" value={formatMoneyNumber(manualPreview.currentBalance)} helper={selectedManualBalance ? "saldo materializado" : "saldo inicial da conta"} />
            <MiniBox label="Impacto do movimento" value={formatMoneyNumber(manualPreview.delta)} helper={manualForm.direction === "inflow" ? "entrada manual" : "saída manual"} />
            <MiniBox label="Saldo após lançamento" value={formatMoneyNumber(manualPreview.projectedBalance)} helper="prévia antes de salvar" />
          </div>
          {manualPreview.errors.length > 0 ? (
            <div className="mt-4 rounded-2xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-600">
              {manualPreview.errors[0]}
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-semibold text-emerald-600">
              Movimento pronto para registrar. Ele alterará o saldo interno e ficará pendente de conciliação.
            </div>
          )}
          <p className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-700">
            Use movimento manual apenas para ajustes operacionais justificados. Ele não cria título, não baixa venda, não emite documento fiscal e não concilia extrato. Transferência entre contas e saldo inicial ficam fora desta rotina na v1.0.
          </p>
          <button type="button" onClick={handleManualMovement} disabled={saving || !manualPreview.canSubmit} className="mt-5 rounded-2xl bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white disabled:opacity-60 hover:bg-[var(--color-primary-hover)]">
            Registrar movimento
          </button>
        </Panel>
      )}
    </div>
  )
}

function Metric({ title, value, helper, accent, icon }: { title: string; value: string | number; helper: string; accent: string; icon?: ReactNode }) {
  return (
    <article className="min-w-0 rounded-3xl p-5 shadow-xl shadow-[var(--color-card-shadow)]" style={{ background: accent, border: `1px solid ${accent}` }}>
      {icon && <span className="text-white/60">{icon}</span>}
      <p className="mt-3 text-xs font-bold uppercase tracking-wide text-white/75">{title}</p>
      <p className="mt-2 break-words text-2xl font-black leading-tight text-white 2xl:text-3xl">{value}</p>
      <p className="mt-1 text-xs text-white/65">{helper}</p>
    </article>
  )
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="mb-4 flex items-center gap-3">
        <span className="rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] p-2 text-[var(--color-primary)]">{icon}</span>
        <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function Notice({ tone, message }: { tone: "error" | "success"; message: string }) {
  const cls = tone === "success"
    ? "border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
    : "border-red-500/50 bg-red-500/10 text-red-600"
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${cls}`}>{message}</div>
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-[var(--color-text-muted)]">{label}</span>
      {children}
    </label>
  )
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">{text}</div>
}

function PaginationControls({ page, hasNextPage, loading, onPrevious, onNext }: { page: number; hasNextPage: boolean; loading: boolean; onPrevious: () => void; onNext: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-3 text-xs text-[var(--color-text-muted)] sm:flex-row sm:items-center sm:justify-between">
      <span>Pagina {page + 1} com ate {PAGE_SIZE} registros. Exportacao busca ate {EXPORT_MAX_ROWS} linhas filtradas.</span>
      <div className="flex gap-2">
        <button type="button" onClick={onPrevious} disabled={loading || page === 0} className="rounded-xl border border-[var(--color-border-soft)] px-3 py-2 font-black text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-50">Anterior</button>
        <button type="button" onClick={onNext} disabled={loading || !hasNextPage} className="rounded-xl border border-[var(--color-border-soft)] px-3 py-2 font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-50">Proxima</button>
      </div>
    </div>
  )
}

function MiniBox({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-3">
      <p className="text-[10px] font-black uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-1 text-lg font-black text-[var(--color-text)]">{value}</p>
      {helper ? <p className="mt-1 text-[10px] font-semibold text-[var(--color-text-muted)]">{helper}</p> : null}
    </div>
  )
}
