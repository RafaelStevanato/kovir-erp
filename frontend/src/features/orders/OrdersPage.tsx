import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Download,
  FileText,
  History,
  Loader2,
  Package,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"

import { SearchableSelect, type SearchableSelectOption } from "../../components/SearchableSelect"
import { dateCell, exportCsv, exportXlsx, moneyCell, type ExportTable } from "../../lib/exportTable"
import { getActiveCompanyId } from "../../config/activeCompany"
import { getAuthSession } from "../../config/authSession"
import { getCatalogItem, getCatalogItems } from "../catalog/catalogApi"
import type { CatalogItem } from "../catalog/types"
import { listReceivableTitles } from "../accountsReceivable/accountsReceivableApi"
import type { ReceivableTitle } from "../accountsReceivable/types"
import { getParticipant, getParticipants } from "../participants/participantsApi"
import type { Participant } from "../participants/types"
import { getSalesPaymentMethods } from "../sales/salesApi"
import type { PaymentMethod } from "../sales/types"
import { getStockItemAvailability, listStockLocations } from "../stock/stockApi"
import type { StockItemAvailability, StockLocation, StockLot } from "../stock/types"
import {
  cancelOrder,
  closeOrder,
  createOrder,
  downloadCommercialInvoicePdf,
  downloadQuotePdf,
  getOrderStatusHistory,
  getOrdersSummary,
  listOrders,
  updateOrder,
} from "./ordersApi"
import type {
  Order,
  OrderCreatePayload,
  OrderStatus,
  OrderStatusHistory,
  PaymentMethodCode,
} from "./types"
import { ReopenOrderModal } from "./ReopenOrderModal"

// ─── Local form types ─────────────────────────────────────────────────────────

type FormItem = {
  local_id: string
  item_id: string
  stock_lot_id: string
  stock_lot_code: string
  stock_lot_expiration_date: string
  quantity: string
  unit_price: string
  discount_amount: string
}

type FormPaymentPlan = {
  local_id: string
  payment_method_code: PaymentMethodCode
  amount: string
  due_date: string
}

type Notice = { type: "success" | "error"; message: string } | null

type ItemAvailabilityState = {
  isLoading: boolean
  data: StockItemAvailability | null
  error: string | null
}

const REMOTE_SEARCH_MIN_CHARS = 2

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [delayMs, value])

  return debounced
}

function userCan(permission: string): boolean {
  const session = getAuthSession()
  return Boolean(session?.roles.includes("admin") || session?.permissions.includes(permission))
}

function toCents(value: string | number | null | undefined): number {
  const normalized = String(value ?? 0).replace(",", ".")
  return Math.round((parseFloat(normalized) || 0) * 100)
}

function centsToMoney(value: number): string {
  return (value / 100).toFixed(2)
}

function sanitizeFilename(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9._-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120)
}

function mergeById<T extends { id: string }>(current: T[], incoming: T[]): T[] {
  const map = new Map(current.map((item) => [item.id, item]))
  for (const item of incoming) map.set(item.id, item)
  return Array.from(map.values())
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtMoney(v: string | number | null | undefined): string {
  const n = parseFloat(String(v ?? 0)) || 0
  return `R$ ${n.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—"
  const s = String(iso).slice(0, 10)
  const [y, m, d] = s.split("-")
  return `${d}/${m}/${y}`
}

function fmtLotExpiration(iso: string | null | undefined): string {
  if (!iso || iso.startsWith("9999")) return "SV - Sem vencimento"
  return fmtDate(iso)
}

function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—"
  const d = new Date(iso)
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
}

function participantLabel(p: Participant): string {
  const tradeName = p.trade_name && p.trade_name !== "NI" ? p.trade_name : null
  return tradeName || p.name || p.email || p.id
}

function orderClientName(o: Order): string {
  const snap = o.participant_snapshot as Record<string, unknown>
  return String(snap?.name || snap?.trade_name || "—")
}

function itemTracksStock(item: CatalogItem | undefined): boolean {
  return Boolean(item?.inventory_settings?.track_stock)
}

function lotLabel(lot: StockLot): string {
  return `${lot.lot_code} - ${lot.quantity} un - ${fmtLotExpiration(lot.expiration_date)}`
}

async function triggerPdfDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const STATUS_LABEL: Record<OrderStatus, string> = {
  quote: "Orçamento",
  closed: "Fechado",
  paid: "Pago",
  cancelled: "Cancelado",
}

const RECEIVABLE_STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  open: "Em aberto",
  overdue: "Vencido",
  partially_received: "Parcial",
  received: "Recebido",
  cancelled: "Cancelado",
  written_off: "Baixado sem recebimento",
  renegotiated: "Renegociado",
}
const STATUS_COLOR: Record<OrderStatus, { bg: string; border: string; text: string }> = {
  quote: { bg: "rgba(56,189,248,0.12)", border: "rgba(56,189,248,0.35)", text: "#38bdf8" },
  closed: { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.35)", text: "#f59e0b" },
  paid: { bg: "rgba(16,185,129,0.12)", border: "rgba(16,185,129,0.35)", text: "#10b981" },
  cancelled: { bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.35)", text: "#ef4444" },
}

const PAYMENT_METHOD_LABELS: Record<PaymentMethodCode, string> = {
  pix: "Pix",
  credit_card: "Cartão de Crédito",
  debit_card: "Cartão de Débito",
  cash: "Dinheiro",
  boleto: "Boleto",
  bank_transfer: "Transferência",
  store_credit: "Crédito Loja",
  other: "Outro",
}

// ─── Main component ───────────────────────────────────────────────────────────

type Tab = "list" | "create" | "edit" | "detail"

export function OrdersPage() {
  const [tab, setTab] = useState<Tab>("list")
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const canCreateOrder = userCan("sales.create")

  function handleSelectOrder(order: Order) {
    setSelectedOrder(order)
    setTab("detail")
    setNotice(null)
  }

  function handleBack() {
    setSelectedOrder(null)
    setTab("list")
    setNotice(null)
  }

  function handleOrderUpdated(updated: Order) {
    setSelectedOrder(updated)
    setNotice({ type: "success", message: "Pedido atualizado com sucesso." })
  }

  function handleReopenSuccess(updated: Order) {
    setSelectedOrder(updated)
    setNotice({
      type: "success",
      message: "Pedido reaberto. Estoque foi estornado automaticamente.",
    })
  }

  function handleCreateSuccess(order: Order) {
    setSelectedOrder(order)
    setTab("detail")
    setNotice({ type: "success", message: "Orçamento criado com sucesso." })
  }

  function handleEditSuccess(order: Order) {
    setSelectedOrder(order)
    setTab("detail")
    setNotice({ type: "success", message: "Orçamento atualizado com sucesso." })
  }

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────────── */}
      <header
        className="rounded-[2rem] p-6 sm:p-8"
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border-soft)",
          boxShadow: "0 8px 40px var(--color-card-shadow)",
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-widest" style={{ color: "var(--color-primary)" }}>
              Comercial
            </p>
            <h1 className="mt-1 text-3xl font-black sm:text-4xl" style={{ color: "var(--color-text)" }}>
              Pedidos
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
              Orçamentos, pedidos fechados e pagos — fluxo B2B/B2C completo.
            </p>
          </div>
          <span
            className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-black"
            style={{
              background: "var(--color-primary-soft)",
              border: "1px solid var(--color-primary-border)",
              color: "var(--color-primary)",
            }}
          >
            <ClipboardList className="h-4 w-4" />
            QUOTE → CLOSED → PAID
          </span>
        </div>
      </header>

      {/* ── Notice ──────────────────────────────────────────────────── */}
      {notice && (
        <NoticeBox notice={notice} onDismiss={() => setNotice(null)} />
      )}

      {/* ── Tabs ────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {tab === "detail" ? (
          <button
            type="button"
            onClick={handleBack}
            className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-black"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border-soft)",
              color: "var(--color-text-muted)",
            }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Lista
          </button>
        ) : (
          <TabBtn active={tab === "list"} onClick={() => setTab("list")}>
            <ClipboardList className="h-3.5 w-3.5" />
            Lista
          </TabBtn>
        )}
        {canCreateOrder && (
          <TabBtn active={tab === "create"} onClick={() => setTab("create")} highlight>
            <Plus className="h-3.5 w-3.5" />
            Novo Orçamento
          </TabBtn>
        )}
      </div>

      {/* ── Content ─────────────────────────────────────────────────── */}
      {tab === "list" && <ListTab onSelectOrder={handleSelectOrder} />}
      {tab === "create" && canCreateOrder && <CreateTab onSuccess={handleCreateSuccess} />}
      {tab === "edit" && selectedOrder && (
        <CreateTab
          initialOrder={selectedOrder}
          onSuccess={handleEditSuccess}
          onCancel={() => setTab("detail")}
        />
      )}
      {tab === "detail" && selectedOrder && (
        <DetailTab
          order={selectedOrder}
          onOrderUpdated={handleOrderUpdated}
          onReopenSuccess={handleReopenSuccess}
          onEditQuote={() => setTab("edit")}
        />
      )}
    </div>
  )
}

// ─── List Tab ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 10

function ListTab({ onSelectOrder }: { onSelectOrder: (o: Order) => void }) {
  const companyId = getActiveCompanyId() ?? ""
  const [orders, setOrders] = useState<Order[]>([])
  const [totalRows, setTotalRows] = useState(0)
  const [counts, setCounts] = useState<Record<OrderStatus, number>>({ quote: 0, closed: 0, paid: 0, cancelled: 0 })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<OrderStatus | "">("")
  const [filterSearch, setFilterSearch] = useState("")
  const [filterDateFrom, setFilterDateFrom] = useState("")
  const [filterDateTo, setFilterDateTo] = useState("")
  const [page, setPage] = useState(1)

  const loadOrders = useCallback(async () => {
    if (!companyId) return
    setIsLoading(true)
    setError(null)
    try {
      const params = {
        company_id: companyId,
        status: filterStatus || undefined,
        q: filterSearch.trim() || undefined,
        date_from: filterDateFrom || undefined,
        date_to: filterDateTo || undefined,
      }
      const [res, summary] = await Promise.all([
        listOrders({ ...params, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
        getOrdersSummary(params),
      ])
      setOrders(res.data ?? [])
      setTotalRows(summary.data.total ?? 0)
      const statusCounts = summary.data.counts_by_status
      setCounts({
        quote: statusCounts.quote ?? 0,
        closed: statusCounts.closed ?? 0,
        paid: statusCounts.paid ?? 0,
        cancelled: statusCounts.cancelled ?? 0,
      })
    } catch {
      setOrders([])
      setTotalRows(0)
      setCounts({ quote: 0, closed: 0, paid: 0, cancelled: 0 })
      setError("Não foi possível carregar pedidos. Verifique conexão, permissões e filtros.")
    } finally {
      setIsLoading(false)
    }
  }, [companyId, filterDateFrom, filterDateTo, filterSearch, filterStatus, page])

  useEffect(() => { void loadOrders() }, [loadOrders])

  // Reset to page 1 whenever any filter changes
  useEffect(() => { setPage(1) }, [filterStatus, filterSearch, filterDateFrom, filterDateTo])

  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE))
  const hasFilters = !!(filterStatus || filterSearch || filterDateFrom || filterDateTo)

  function buildExportRows(source: Order[]): ExportTable {
    return [
      ["Número", "Status", "Cliente", "Data", "Itens", "Desconto (R$)", "Frete (R$)", "Total (R$)", "Fechado em", "Pago em"],
      ...source.map((o) => [
        o.sale_number_text ?? "RASCUNHO",
        STATUS_LABEL[o.status],
        orderClientName(o),
        dateCell(o.operation_date),
        o.items.length,
        moneyCell(o.discount_amount),
        moneyCell(o.freight_amount),
        moneyCell(o.total_amount),
        dateCell(o.closed_at),
        dateCell(o.paid_at),
      ]),
    ]
  }

  function handleExportCsv() {
    exportCsv(buildExportRows(orders), `${sanitizeFilename(`pedidos_pagina_${page}_${new Date().toISOString().slice(0, 10)}`)}.csv`)
  }

  function handleExportXlsx() {
    exportXlsx(buildExportRows(orders), "Pedidos", `${sanitizeFilename(`pedidos_pagina_${page}_${new Date().toISOString().slice(0, 10)}`)}.xlsx`)
  }

  const btnStyle = {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border-soft)",
    color: "var(--color-text-muted)",
  }

  return (
    <div className="space-y-4">
      {/* Status cards — informational only, not clickable */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(["quote", "closed", "paid", "cancelled"] as OrderStatus[]).map((st) => {
          const color = STATUS_COLOR[st]
          return (
            <div
              key={st}
              className="rounded-2xl p-4"
              style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
            >
              <p className="text-2xl font-black" style={{ color: color.text }}>{counts[st]}</p>
              <p className="mt-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
                {STATUS_LABEL[st]}
              </p>
            </div>
          )
        })}
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Text search */}
        <div
          className="flex min-w-48 flex-1 items-center gap-2 rounded-2xl px-4 py-2.5"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
        >
          <input
            type="text"
            value={filterSearch}
            onChange={(e) => setFilterSearch(e.target.value)}
            placeholder="Buscar por cliente ou número…"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--color-text)" }}
          />
          {filterSearch && (
            <button type="button" onClick={() => setFilterSearch("")}>
              <X className="h-4 w-4" style={{ color: "var(--color-text-weak)" }} />
            </button>
          )}
        </div>

        {/* Status filter */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as OrderStatus | "")}
          className="rounded-2xl px-4 py-2.5 text-sm font-semibold outline-none"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border-soft)",
            color: filterStatus ? "var(--color-text)" : "var(--color-text-muted)",
          }}
        >
          <option value="">Todos os status</option>
          <option value="quote">Orçamento</option>
          <option value="closed">Fechado</option>
          <option value="paid">Pago</option>
          <option value="cancelled">Cancelado</option>
        </select>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>De</label>
          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="rounded-2xl px-3 py-2.5 text-sm outline-none"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)", colorScheme: "dark" }}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>Até</label>
          <input
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="rounded-2xl px-3 py-2.5 text-sm outline-none"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)", colorScheme: "dark" }}
          />
        </div>

        {/* Export buttons */}
        <button
          type="button"
          onClick={handleExportCsv}
          disabled={orders.length === 0}
          className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold disabled:opacity-40"
          style={btnStyle}
          title={`Exportar ${orders.length} pedidos da página atual como CSV`}
        >
          <Download className="h-4 w-4" />
          CSV
        </button>
        <button
          type="button"
          onClick={handleExportXlsx}
          disabled={orders.length === 0}
          className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold disabled:opacity-40"
          style={btnStyle}
          title={`Exportar ${orders.length} pedidos da página atual como XLSX`}
        >
          <Download className="h-4 w-4" />
          XLSX
        </button>

        {/* Refresh */}
        <button
          type="button"
          onClick={() => void loadOrders()}
          disabled={isLoading}
          className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold"
          style={btnStyle}
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Atualizar
        </button>

        {/* Clear filters */}
        {hasFilters && (
          <button
            type="button"
            onClick={() => { setFilterStatus(""); setFilterSearch(""); setFilterDateFrom(""); setFilterDateTo("") }}
            className="rounded-2xl px-4 py-2.5 text-sm font-bold"
            style={btnStyle}
          >
            <X className="mr-1 inline-block h-3.5 w-3.5" />
            Limpar filtros
          </button>
        )}
      </div>

      <p className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
        Exportação CSV/XLSX baixa somente a página atual ({orders.length} de {totalRows} pedido(s)) respeitando os filtros aplicados no backend.
      </p>

      {error && (
        <NoticeBox notice={{ type: "error", message: error }} onDismiss={() => setError(null)} />
      )}

      {/* Order list */}
      <div
        className="overflow-hidden rounded-[2rem]"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
      >
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 p-8" style={{ color: "var(--color-text-muted)" }}>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Carregando pedidos…</span>
          </div>
        ) : orders.length === 0 ? (
          <div className="p-8 text-center">
            <ClipboardList className="mx-auto mb-3 h-8 w-8" style={{ color: "var(--color-text-weak)" }} />
            <p className="text-sm font-bold" style={{ color: "var(--color-text-muted)" }}>
              {hasFilters ? "Nenhum pedido corresponde ao filtro." : "Nenhum pedido encontrado."}
            </p>
          </div>
        ) : (
          <>
            <div className="divide-y" style={{ borderColor: "var(--color-border-soft)" }}>
              {orders.map((o) => {
                const color = STATUS_COLOR[o.status]
                return (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => onSelectOrder(o)}
                    className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors"
                    style={{ color: "var(--color-text)" }}
                    onMouseOver={(e) => (e.currentTarget.style.background = "var(--color-hover)")}
                    onMouseOut={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    {/* Number */}
                    <div className="w-24 shrink-0">
                      <p className="text-sm font-black" style={{ color: "var(--color-primary)", fontVariantNumeric: "tabular-nums" }}>
                        {o.sale_number_text ?? "RASCUNHO"}
                      </p>
                      <p className="text-xs" style={{ color: "var(--color-text-weak)" }}>
                        {fmtDate(o.operation_date)}
                      </p>
                    </div>
                    {/* Client */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold" style={{ color: "var(--color-text)" }}>
                        {orderClientName(o)}
                      </p>
                      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {o.items.length} {o.items.length === 1 ? "item" : "itens"}
                      </p>
                    </div>
                    {/* Total */}
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-black" style={{ color: "var(--color-text)" }}>
                        {fmtMoney(o.total_amount)}
                      </p>
                    </div>
                    {/* Status badge */}
                    <span
                      className="shrink-0 rounded-full px-3 py-1 text-xs font-black"
                      style={{ background: color.bg, border: `1px solid ${color.border}`, color: color.text }}
                    >
                      {STATUS_LABEL[o.status]}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div
                className="flex items-center justify-between border-t px-5 py-3"
                style={{ borderColor: "var(--color-border-soft)" }}
              >
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="flex items-center gap-1 rounded-xl px-3 py-1.5 text-sm font-bold disabled:opacity-30"
                  style={btnStyle}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Anterior
                </button>
                <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  Página <strong style={{ color: "var(--color-text)" }}>{page}</strong> de{" "}
                  <strong style={{ color: "var(--color-text)" }}>{totalPages}</strong>
                  <span className="ml-2 text-xs">({totalRows} pedidos)</span>
                </span>
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="flex items-center gap-1 rounded-xl px-3 py-1.5 text-sm font-bold disabled:opacity-30"
                  style={btnStyle}
                >
                  Próxima
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─── Create Tab ───────────────────────────────────────────────────────────────

function CreateTab({
  initialOrder,
  onSuccess,
  onCancel,
}: {
  initialOrder?: Order
  onSuccess: (o: Order) => void
  onCancel?: () => void
}) {
  const companyId = getActiveCompanyId() ?? ""
  const isEditing = Boolean(initialOrder)

  // Reference data
  const [participants, setParticipants] = useState<Participant[]>([])
  const [catalogItems, setCatalogItems] = useState<CatalogItem[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [stockLocations, setStockLocations] = useState<StockLocation[]>([])
  const [isLoadingRef, setIsLoadingRef] = useState(true)
  const [participantSearch, setParticipantSearch] = useState("")
  const [itemSearch, setItemSearch] = useState("")
  const [isSearchingParticipants, setIsSearchingParticipants] = useState(false)
  const [isSearchingItems, setIsSearchingItems] = useState(false)
  const [participantSearchError, setParticipantSearchError] = useState<string | null>(null)
  const [itemSearchError, setItemSearchError] = useState<string | null>(null)
  const debouncedParticipantSearch = useDebouncedValue(participantSearch, 350)
  const debouncedItemSearch = useDebouncedValue(itemSearch, 350)

  // Form state
  const [participantId, setParticipantId] = useState("")
  const [stockLocationId, setStockLocationId] = useState("")
  const [saleType, setSaleType] = useState<"product" | "service">("product")
  const [formItems, setFormItems] = useState<FormItem[]>([])
  const [itemAvailability, setItemAvailability] = useState<Record<string, ItemAvailabilityState>>({})
  const [formPaymentPlans, setFormPaymentPlans] = useState<FormPaymentPlan[]>([])
  const [discountAmount, setDiscountAmount] = useState("0.00")
  const [freightAmount, setFreightAmount] = useState("0.00")
  const [notes, setNotes] = useState("")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [paymentAutoNotice, setPaymentAutoNotice] = useState<string | null>(null)
  const previousTotalCentsRef = useRef<number | null>(null)

  const loadParticipants = useCallback(async (query: string) => {
    if (!companyId || query.trim().length < REMOTE_SEARCH_MIN_CHARS) {
      setParticipantSearchError(null)
      return
    }
    setIsSearchingParticipants(true)
    setParticipantSearchError(null)
    try {
      const response = await getParticipants({
        company_id: companyId,
        participant_type: "customer",
        status: "active",
        search: query.trim(),
        limit: 25,
        offset: 0,
      })
      setParticipants((current) => mergeById(current.filter((item) => item.id === participantId), response.data ?? []))
    } catch {
      setParticipantSearchError("Não foi possível buscar clientes.")
    } finally {
      setIsSearchingParticipants(false)
    }
  }, [companyId, participantId])

  const loadCatalogItems = useCallback(async (query: string) => {
    if (!companyId || query.trim().length < REMOTE_SEARCH_MIN_CHARS) {
      setItemSearchError(null)
      return
    }
    setIsSearchingItems(true)
    setItemSearchError(null)
    try {
      const response = await getCatalogItems({
        company_id: companyId,
        item_type: saleType,
        status: "active",
        search: query.trim(),
        limit: 25,
        offset: 0,
      })
      setCatalogItems((current) => mergeById(current, response.data ?? []))
    } catch {
      setItemSearchError("Não foi possível buscar produtos/serviços.")
    } finally {
      setIsSearchingItems(false)
    }
  }, [companyId, saleType])

  // Load reference data that is small and stable. Cliente/produto usam busca remota.
  useEffect(() => {
    if (!companyId) return
    setIsLoadingRef(true)
    Promise.all([
      getSalesPaymentMethods({ company_id: companyId }),
      listStockLocations(companyId),
    ])
      .then(([pm, locations]) => {
        setPaymentMethods(pm.data ?? [])
        setStockLocations(locations.data ?? [])
        const defaultLocation = (locations.data ?? []).find((location) => location.is_default) ?? (locations.data ?? [])[0]
        if (defaultLocation) {
          setStockLocationId((current) => current || defaultLocation.id)
        }
      })
      .catch(() => {})
      .finally(() => setIsLoadingRef(false))
  }, [companyId])

  useEffect(() => {
    void loadParticipants(debouncedParticipantSearch)
  }, [debouncedParticipantSearch, loadParticipants])

  useEffect(() => {
    void loadCatalogItems(debouncedItemSearch)
  }, [debouncedItemSearch, loadCatalogItems])

  useEffect(() => {
    if (initialOrder) return
    setFormItems([])
    setItemAvailability({})
  }, [initialOrder, saleType])

  useEffect(() => {
    setItemSearch("")
    setItemSearchError(null)
    setCatalogItems((current) => current.filter((item) => item.item_type === saleType))
  }, [saleType])

  useEffect(() => {
    if (!initialOrder) return
    setParticipantId(initialOrder.participant_id)
    setSaleType(initialOrder.sale_type)
    setDiscountAmount(initialOrder.discount_amount)
    setFreightAmount(initialOrder.freight_amount)
    setNotes(initialOrder.notes ?? "")
    setFormItems(initialOrder.items.map((item) => ({
      local_id: item.id || crypto.randomUUID(),
      item_id: item.item_id,
      stock_lot_id: item.stock_lot_id ?? "",
      stock_lot_code: item.stock_lot_code ?? "",
      stock_lot_expiration_date: item.stock_lot_expiration_date ?? "",
      quantity: item.quantity,
      unit_price: item.unit_price,
      discount_amount: item.discount_amount,
    })))
    setFormPaymentPlans(initialOrder.payment_plans.map((plan) => ({
      local_id: plan.id || crypto.randomUUID(),
      payment_method_code: plan.payment_method_code,
      amount: plan.amount,
      due_date: plan.due_date ?? "",
    })))
  }, [initialOrder])

  useEffect(() => {
    if (!initialOrder) return
    getParticipant(initialOrder.participant_id)
      .then((response) => setParticipants((current) => mergeById(current, [response.data])))
      .catch(() => undefined)

    const itemIds = Array.from(new Set(initialOrder.items.map((item) => item.item_id).filter(Boolean)))
    void Promise.all(itemIds.map((itemId) => getCatalogItem(itemId)))
      .then((responses) => setCatalogItems((current) => mergeById(current, responses.map((response) => response.data))))
      .catch(() => undefined)
  }, [initialOrder])

  const participantOptions: SearchableSelectOption[] = participants.map((p) => ({
    value: p.id,
    label: participantLabel(p),
    description: p.document ? `Doc: ${p.document}` : (p.email ?? undefined),
    keywords: [p.name ?? "", p.trade_name && p.trade_name !== "NI" ? p.trade_name : "", p.document ?? "", p.email ?? ""],
  }))

  const itemOptions: SearchableSelectOption[] = catalogItems
    .filter((c) => c.item_type === saleType)
    .map((c) => ({
    value: c.id,
    label: c.name,
    description: `${c.unit} · ${fmtMoney(c.financial_settings?.default_sale_price)}`,
    keywords: [c.sku ?? "", c.barcode ?? ""],
    }))

  const paymentMethodOptions: SearchableSelectOption[] = paymentMethods.map((pm) => ({
    value: pm.code,
    label: pm.name,
  }))

  const stockLocationOptions: SearchableSelectOption[] = stockLocations.map((location) => ({
    value: location.id,
    label: location.name,
    description: `${location.code}${location.is_default ? " · padrão" : ""}`,
    keywords: [location.code, location.location_type],
  }))

  // Totals
  const subtotal = formItems.reduce((acc, item) => {
    const qty = parseFloat(item.quantity) || 0
    const price = parseFloat(item.unit_price) || 0
    const disc = parseFloat(item.discount_amount) || 0
    return acc + Math.max(0, qty * price - disc)
  }, 0)
  const discount = parseFloat(discountAmount) || 0
  const freight = parseFloat(freightAmount) || 0
  const total = subtotal - discount + freight
  const totalCents = toCents(total)
  const paymentPlansTotalCents = formPaymentPlans.reduce((acc, plan) => acc + toCents(plan.amount), 0)
  const paymentDeltaCents = totalCents - paymentPlansTotalCents
  const paymentPlansBalanced = paymentDeltaCents === 0
  const paymentPlansHaveValidAmounts = formPaymentPlans.length > 0 && formPaymentPlans.every((plan) => toCents(plan.amount) > 0)

  useEffect(() => {
    if (totalCents <= 0) {
      previousTotalCentsRef.current = totalCents
      return
    }

    if (previousTotalCentsRef.current === totalCents) return
    previousTotalCentsRef.current = totalCents

    setFormPaymentPlans((current) => {
      if (current.length === 0) {
        setPaymentAutoNotice("Primeira condição de pagamento criada automaticamente com o total do pedido.")
        return [{
          local_id: crypto.randomUUID(),
          payment_method_code: "pix",
          amount: centsToMoney(totalCents),
          due_date: "",
        }]
      }

      const currentTotal = current.reduce((acc, plan) => acc + toCents(plan.amount), 0)
      const delta = totalCents - currentTotal
      if (delta === 0) return current

      const firstAmount = toCents(current[0].amount) + delta
      if (firstAmount <= 0) return current

      setPaymentAutoNotice("Primeira condição de pagamento ajustada automaticamente para manter a soma igual ao total.")
      return current.map((plan, index) => index === 0 ? { ...plan, amount: centsToMoney(firstAmount) } : plan)
    })
  }, [totalCents])

  async function loadItemAvailability(local_id: string, item_id: string) {
    const catalogItem = catalogItems.find((c) => c.id === item_id)
    if (!companyId || saleType !== "product" || !stockLocationId || !itemTracksStock(catalogItem)) {
      setItemAvailability((prev) => {
        const next = { ...prev }
        delete next[local_id]
        return next
      })
      return
    }

    setItemAvailability((prev) => ({
      ...prev,
      [local_id]: { isLoading: true, data: null, error: null },
    }))

    try {
      const response = await getStockItemAvailability(companyId, item_id, stockLocationId)
      const availability = response.data
      setItemAvailability((prev) => ({
        ...prev,
        [local_id]: { isLoading: false, data: availability, error: null },
      }))

      const lots = availability.lots ?? []
      if (lots.length === 1) {
        const lot = lots[0]
        setFormItems((prev) => prev.map((item) => (
          item.local_id === local_id
            ? {
              ...item,
              stock_lot_id: lot.id,
              stock_lot_code: lot.lot_code,
              stock_lot_expiration_date: lot.expiration_date,
            }
            : item
        )))
      }
    } catch (err: unknown) {
      setItemAvailability((prev) => ({
        ...prev,
        [local_id]: {
          isLoading: false,
          data: null,
          error: err instanceof Error ? err.message : "Não foi possível consultar lotes do item.",
        },
      }))
    }
  }

  function addItem() {
    setFormItems((prev) => [...prev, {
      local_id: crypto.randomUUID(),
      item_id: "",
      stock_lot_id: "",
      stock_lot_code: "",
      stock_lot_expiration_date: "",
      quantity: "1",
      unit_price: "0.00",
      discount_amount: "0.00",
    }])
  }

  function updateItem(local_id: string, field: keyof FormItem, value: string) {
    setFormItems((prev) => prev.map((item) => {
      if (item.local_id !== local_id) return item
      const updated = { ...item, [field]: value }
      if (field === "item_id") {
        const cat = catalogItems.find((c) => c.id === value)
        if (cat) {
          updated.unit_price = cat.financial_settings?.default_sale_price ?? "0.00"
        }
        updated.stock_lot_id = ""
        updated.stock_lot_code = ""
        updated.stock_lot_expiration_date = ""
      }
      return updated
    }))
  }

  function updateItemLot(local_id: string, lot_id: string) {
    const lot = itemAvailability[local_id]?.data?.lots?.find((candidate) => candidate.id === lot_id)
    setFormItems((prev) => prev.map((item) => (
      item.local_id === local_id
        ? {
          ...item,
          stock_lot_id: lot?.id ?? "",
          stock_lot_code: lot?.lot_code ?? "",
          stock_lot_expiration_date: lot?.expiration_date ?? "",
        }
        : item
    )))
  }

  function handleItemSelection(local_id: string, item_id: string) {
    updateItem(local_id, "item_id", item_id)
    if (item_id) {
      void loadItemAvailability(local_id, item_id)
    } else {
      setItemAvailability((prev) => {
        const next = { ...prev }
        delete next[local_id]
        return next
      })
    }
  }

  function handleStockLocationChange(locationId: string) {
    setStockLocationId(locationId)
    setItemAvailability({})
    setFormItems((prev) => prev.map((item) => ({
      ...item,
      stock_lot_id: "",
      stock_lot_code: "",
      stock_lot_expiration_date: "",
    })))
  }

  function removeItem(local_id: string) {
    setFormItems((prev) => prev.filter((i) => i.local_id !== local_id))
    setItemAvailability((prev) => {
      const next = { ...prev }
      delete next[local_id]
      return next
    })
  }

  function addPaymentPlan() {
    const remainingCents = Math.max(0, totalCents - paymentPlansTotalCents)
    setFormPaymentPlans((prev) => [...prev, {
      local_id: crypto.randomUUID(),
      payment_method_code: "pix",
      amount: centsToMoney(remainingCents),
      due_date: "",
    }])
  }

  function updatePlan(local_id: string, field: keyof FormPaymentPlan, value: string) {
    if (field === "amount") setPaymentAutoNotice(null)
    setFormPaymentPlans((prev) =>
      prev.map((p) => p.local_id === local_id ? { ...p, [field]: value } : p),
    )
  }

  function removePlan(local_id: string) {
    setFormPaymentPlans((prev) => prev.filter((p) => p.local_id !== local_id))
  }

  async function handleSave() {
    if (!participantId) { setError("Selecione um cliente."); return }
    if (saleType === "product" && !stockLocationId) { setError("Selecione o local de estoque da venda."); return }
    if (formItems.length === 0) { setError("Adicione pelo menos um item."); return }
    const invalidItem = formItems.find((i) => !i.item_id || !parseFloat(i.quantity))
    if (invalidItem) { setError("Preencha todos os itens corretamente."); return }
    const itemWithoutLot = formItems.find((i) => {
      const catalogItem = catalogItems.find((c) => c.id === i.item_id)
      return saleType === "product" && itemTracksStock(catalogItem) && !i.stock_lot_id
    })
    if (itemWithoutLot) { setError("Selecione o lote dos produtos que controlam estoque."); return }
    if (totalCents <= 0) { setError("O total do pedido deve ser maior que zero."); return }
    if (formPaymentPlans.length === 0) { setError("Informe ao menos uma condição de pagamento."); return }
    if (formPaymentPlans.some((plan) => toCents(plan.amount) <= 0)) { setError("Cada condição de pagamento deve ter valor maior que zero."); return }
    if (!paymentPlansBalanced) {
      setError(`A soma das condições de pagamento deve ser igual ao total. Diferença: ${fmtMoney(Math.abs(paymentDeltaCents) / 100)}.`)
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      const payload: OrderCreatePayload = {
        company_id: companyId,
        participant_id: participantId,
        sale_type: saleType,
        origin: "manual",
        operation_nature: "normal_sale",
        discount_amount: discount.toFixed(2),
        freight_amount: freight.toFixed(2),
        tax_amount: "0.00",
        notes: notes || undefined,
        items: formItems.map((item) => ({
          item_id: item.item_id,
          stock_lot_id: item.stock_lot_id || undefined,
          stock_lot_code: item.stock_lot_code || undefined,
          stock_lot_expiration_date: item.stock_lot_expiration_date || undefined,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_amount: item.discount_amount,
          freight_amount: "0.00",
          tax_amount: "0.00",
        })),
        payment_plans: formPaymentPlans.map((p) => ({
          payment_method_code: p.payment_method_code,
          amount: p.amount,
          due_date: p.due_date || undefined,
        })),
      }
      const res = isEditing && initialOrder ? await updateOrder(initialOrder.id, payload) : await createOrder(payload)
      onSuccess(res.data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : isEditing ? "Erro ao atualizar orçamento." : "Erro ao criar orçamento.")
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoadingRef) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-[2rem] p-10" style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}>
        <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--color-primary)" }} />
        <span className="text-sm" style={{ color: "var(--color-text-muted)" }}>Carregando dados…</span>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div
        className="rounded-[2rem] p-6"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
      >
        <h2 className="mb-5 text-lg font-black" style={{ color: "var(--color-text)" }}>
          Novo Orçamento
        </h2>

        <div className="space-y-5">
          {/* Cliente */}
          <FieldGroup label="Cliente *">
            <SearchableSelect
              value={participantId}
              options={participantOptions}
              placeholder="Digite ao menos 2 letras para buscar cliente..."
              emptyMessage={participantSearch.trim().length < REMOTE_SEARCH_MIN_CHARS ? "Digite ao menos 2 letras para buscar cliente." : "Nenhum cliente encontrado."}
              isLoading={isSearchingParticipants}
              errorMessage={participantSearchError}
              onRetry={() => void loadParticipants(participantSearch)}
              onSearchQueryChange={setParticipantSearch}
              onChange={setParticipantId}
            />
          </FieldGroup>

          {/* Tipo */}
          <FieldGroup label="Tipo de venda">
            <div className="flex gap-3">
              {(["product", "service"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSaleType(t)}
                  className="flex-1 rounded-2xl py-2.5 text-sm font-bold"
                  style={
                    saleType === t
                      ? { background: "var(--color-primary-soft)", border: "1px solid var(--color-primary-border)", color: "var(--color-primary)" }
                      : { background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }
                  }
                >
                  {t === "product" ? "Produto" : "Serviço"}
                </button>
              ))}
            </div>
          </FieldGroup>

          {saleType === "product" && (
            <FieldGroup label="Local de estoque *">
              <SearchableSelect
                value={stockLocationId}
                options={stockLocationOptions}
                placeholder="Selecione o estoque que será usado na venda"
                emptyMessage="Nenhum local de estoque cadastrado."
                onChange={handleStockLocationChange}
              />
              <p className="mt-1 text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                Os lotes serão listados apenas do local selecionado.
              </p>
            </FieldGroup>
          )}

          {/* Itens */}
          <FieldGroup label="Itens">
            <div className="space-y-3">
              {formItems.map((item, idx) => {
                const selectedCatalogItem = catalogItems.find((catalogItem) => catalogItem.id === item.item_id)
                const tracksStock = saleType === "product" && itemTracksStock(selectedCatalogItem)
                const availability = itemAvailability[item.local_id]
                const lotOptions: SearchableSelectOption[] = (availability?.data?.lots ?? []).map((lot) => ({
                  value: lot.id,
                  label: lotLabel(lot),
                  description: `Disponivel: ${lot.quantity}`,
                  keywords: [lot.lot_code, lot.expiration_date],
                }))

                return (
                <div key={item.local_id} className="flex flex-wrap items-end gap-3">
                  <div className="flex-1 min-w-40">
                    <p className="mb-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
                      Item {idx + 1}
                    </p>
                    <SearchableSelect
                      value={item.item_id}
                      options={itemOptions}
                      placeholder="Digite ao menos 2 letras para buscar item..."
                      emptyMessage={itemSearch.trim().length < REMOTE_SEARCH_MIN_CHARS ? "Digite ao menos 2 letras para buscar item." : "Nenhum item encontrado."}
                      isLoading={isSearchingItems}
                      errorMessage={itemSearchError}
                      onRetry={() => void loadCatalogItems(itemSearch)}
                      onSearchQueryChange={setItemSearch}
                      onChange={(v) => handleItemSelection(item.local_id, v)}
                    />
                  </div>
                  {tracksStock && (
                    <div className="min-w-56 flex-1">
                      <p className="mb-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>Lote</p>
                      <SearchableSelect
                        value={item.stock_lot_id}
                        options={lotOptions}
                        placeholder={availability?.isLoading ? "Carregando lotes..." : "Selecionar lote..."}
                        emptyMessage={availability?.error ?? "Nenhum lote disponível para este produto."}
                        disabled={Boolean(availability?.isLoading)}
                        onChange={(v) => updateItemLot(item.local_id, v)}
                      />
                      {availability?.data?.block_reason && (
                        <p className="mt-1 text-xs font-semibold" style={{ color: "#f59e0b" }}>
                          {availability.data.block_reason}
                        </p>
                      )}
                      {item.stock_lot_code && (
                        <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                          Selecionado: {item.stock_lot_code} - {fmtLotExpiration(item.stock_lot_expiration_date)}
                        </p>
                      )}
                    </div>
                  )}
                  <div className="w-20">
                    <p className="mb-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>Qtd</p>
                    <input
                      type="number"
                      min="0.001"
                      step="0.001"
                      value={item.quantity}
                      onChange={(e) => updateItem(item.local_id, "quantity", e.target.value)}
                      className="w-full rounded-2xl px-3 py-2 text-sm outline-none"
                      style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
                    />
                  </div>
                  <div className="w-28">
                    <p className="mb-1 text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>Preço unit.</p>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.unit_price}
                      onChange={(e) => updateItem(item.local_id, "unit_price", e.target.value)}
                      className="w-full rounded-2xl px-3 py-2 text-sm outline-none"
                      style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
                    />
                  </div>
                  <div className="shrink-0 text-sm font-bold" style={{ color: "var(--color-primary)" }}>
                    = {fmtMoney((parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0))}
                  </div>
                  <button type="button" onClick={() => removeItem(item.local_id)}>
                    <Trash2 className="h-4 w-4" style={{ color: "#ef4444" }} />
                  </button>
                </div>
                )
              })}
              <button
                type="button"
                onClick={addItem}
                className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold"
                style={{ background: "var(--color-primary-soft)", border: "1px solid var(--color-primary-border)", color: "var(--color-primary)" }}
              >
                <Plus className="h-4 w-4" /> Adicionar item
              </button>
            </div>
          </FieldGroup>

          {/* Desconto / Frete / Notas */}
          <div className="grid gap-4 sm:grid-cols-2">
            <FieldGroup label="Desconto (R$)">
              <input
                type="number"
                min="0"
                step="0.01"
                value={discountAmount}
                onChange={(e) => setDiscountAmount(e.target.value)}
                className="w-full rounded-2xl px-4 py-2.5 text-sm outline-none"
                style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
              />
            </FieldGroup>
            <FieldGroup label="Frete (R$)">
              <input
                type="number"
                min="0"
                step="0.01"
                value={freightAmount}
                onChange={(e) => setFreightAmount(e.target.value)}
                className="w-full rounded-2xl px-4 py-2.5 text-sm outline-none"
                style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
              />
            </FieldGroup>
          </div>

          <FieldGroup label="Observações">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Condições comerciais, prazo de entrega…"
              className="w-full resize-none rounded-2xl px-4 py-3 text-sm outline-none"
              style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
            />
          </FieldGroup>

          {/* Totais */}
          <div
            className="rounded-2xl p-4 space-y-2"
            style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)" }}
          >
            <TotalRow label="Subtotal" value={fmtMoney(subtotal)} />
            <TotalRow label="Desconto" value={`- ${fmtMoney(discount)}`} />
            <TotalRow label="Frete" value={fmtMoney(freight)} />
            <div className="pt-2" style={{ borderTop: "1px solid var(--color-border-soft)" }}>
              <TotalRow label="TOTAL" value={fmtMoney(total)} bold />
            </div>
          </div>

          {/* Condições de pagamento */}
          <FieldGroup label="Condições de pagamento (opcional)">
            <div className="space-y-3">
              {formPaymentPlans.map((plan) => (
                <div key={plan.local_id} className="flex flex-wrap items-end gap-3">
                  <div className="flex-1 min-w-36">
                    <SearchableSelect
                      value={plan.payment_method_code}
                      options={paymentMethodOptions.length ? paymentMethodOptions : Object.entries(PAYMENT_METHOD_LABELS).map(([code, label]) => ({ value: code, label }))}
                      placeholder="Método…"
                      onChange={(v) => updatePlan(plan.local_id, "payment_method_code", v)}
                    />
                  </div>
                  <div className="w-28">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={plan.amount}
                      placeholder="Valor"
                      onChange={(e) => updatePlan(plan.local_id, "amount", e.target.value)}
                      className="w-full rounded-2xl px-3 py-2 text-sm outline-none"
                      style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
                    />
                  </div>
                  <div className="w-36">
                    <input
                      type="date"
                      value={plan.due_date}
                      onChange={(e) => updatePlan(plan.local_id, "due_date", e.target.value)}
                      className="w-full rounded-2xl px-3 py-2 text-sm outline-none"
                      style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
                    />
                  </div>
                  <button type="button" onClick={() => removePlan(plan.local_id)}>
                    <Trash2 className="h-4 w-4" style={{ color: "#ef4444" }} />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addPaymentPlan}
                className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-bold"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }}
              >
                <Plus className="h-4 w-4" /> Adicionar forma de pagamento
              </button>
              <div
                className="rounded-2xl px-4 py-3 text-sm"
                style={{
                  background: paymentPlansBalanced ? "rgba(16,185,129,0.08)" : "rgba(245,158,11,0.12)",
                  border: paymentPlansBalanced ? "1px solid rgba(16,185,129,0.25)" : "1px solid rgba(245,158,11,0.35)",
                  color: "var(--color-text)",
                }}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 font-bold">
                  <span>Soma das condições: {fmtMoney(paymentPlansTotalCents / 100)}</span>
                  <span>Total do pedido: {fmtMoney(total)}</span>
                </div>
                {!paymentPlansBalanced && (
                  <p className="mt-1 font-semibold" style={{ color: "#f59e0b" }}>
                    Diferença: {fmtMoney(Math.abs(paymentDeltaCents) / 100)}. Ajuste as parcelas antes de salvar.
                  </p>
                )}
                {paymentAutoNotice && (
                  <p className="mt-1 text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                    {paymentAutoNotice}
                  </p>
                )}
                <p className="mt-1 text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
                  Plano de pagamento é previsão/título a receber. Recebimento oficial acontece em Contas a Receber/Caixa.
                </p>
              </div>
            </div>
          </FieldGroup>

          {error && (
            <div className="rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}>
              <AlertTriangle className="mr-2 inline-block h-4 w-4" />
              {error}
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row">
            {onCancel && (
              <button
                type="button"
                onClick={onCancel}
                disabled={isSaving}
                className="flex items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-black"
                style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }}
              >
                Cancelar edição
              </button>
            )}
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isSaving || !paymentPlansBalanced || !paymentPlansHaveValidAmounts || totalCents <= 0}
              className="flex flex-1 items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-black"
              style={
                !isSaving && paymentPlansBalanced && paymentPlansHaveValidAmounts && totalCents > 0
                  ? { background: "var(--color-primary)", color: "#fff", boxShadow: "0 4px 16px rgba(16,185,129,0.3)" }
                  : { background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-weak)" }
              }
            >
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {isSaving ? "Salvando..." : isEditing ? "Atualizar Orçamento" : "Salvar Orçamento"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Detail Tab ───────────────────────────────────────────────────────────────

function DetailTab({
  order,
  onOrderUpdated,
  onReopenSuccess,
  onEditQuote,
}: {
  order: Order
  onOrderUpdated: (o: Order) => void
  onReopenSuccess: (o: Order) => void
  onEditQuote: () => void
}) {
  const companyId = order.company_id || getActiveCompanyId() || ""
  const canCloseOrder = userCan("sales.close")
  const canCancelOrder = userCan("sales.cancel")
  const canEditOrder = userCan("sales.create")
  const canReopenOrder = userCan("sales.unlock_closed")
  const [history, setHistory] = useState<OrderStatusHistory[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [financialTitles, setFinancialTitles] = useState<ReceivableTitle[]>([])
  const [isLoadingFinancialTitles, setIsLoadingFinancialTitles] = useState(false)
  const [financialTitlesError, setFinancialTitlesError] = useState<string | null>(null)

  // Action modal state
  const [actionModal, setActionModal] = useState<"close" | "cancel" | null>(null)
  const [showReopen, setShowReopen] = useState(false)
  const [actionReason, setActionReason] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // PDF downloading
  const [downloadingPdf, setDownloadingPdf] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const loadHistory = useCallback(() => {
    setIsLoadingHistory(true)
    getOrderStatusHistory(order.id)
      .then((res) => setHistory(res.data ?? []))
      .catch(() => setHistory([]))
      .finally(() => setIsLoadingHistory(false))
  }, [order.id])

  const loadFinancialTitles = useCallback(() => {
    if (!companyId) return
    setIsLoadingFinancialTitles(true)
    setFinancialTitlesError(null)
    listReceivableTitles(companyId, { sale_id: order.id, limit: 100, offset: 0 })
      .then((response) => setFinancialTitles(response.data ?? []))
      .catch(() => {
        setFinancialTitles([])
        setFinancialTitlesError("Não foi possível carregar os títulos financeiros deste pedido.")
      })
      .finally(() => setIsLoadingFinancialTitles(false))
  }, [companyId, order.id])

  useEffect(() => {
    loadHistory()
    loadFinancialTitles()
  }, [loadHistory, loadFinancialTitles])

  async function handleAction(action: "close" | "cancel") {
    if (action === "cancel" && !actionReason.trim()) {
      setActionError("Informe o motivo do cancelamento.")
      return
    }
    setIsSubmitting(true)
    setActionError(null)
    try {
      let res
      if (action === "close") res = await closeOrder(order.id, { reason: actionReason || undefined })
      else res = await cancelOrder(order.id, { reason: actionReason || undefined })
      onOrderUpdated(res.data)
      loadHistory()
      loadFinancialTitles()
      setActionModal(null)
      setActionReason("")
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Erro ao executar ação.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDownload(type: "quote" | "closed" | "paid") {
    const key = type
    setDownloadingPdf(key)
    setDownloadError(null)
    try {
      let blob: Blob
      let filename: string
      if (type === "quote") {
        blob = await downloadQuotePdf(order.id)
        filename = `${sanitizeFilename(`orcamento_${order.sale_number_text ?? order.id}`)}.pdf`
      } else {
        blob = await downloadCommercialInvoicePdf(order.id, type)
        filename = type === "paid"
          ? `${sanitizeFilename(`espelho_nfe_${order.paid_number_text ?? order.id}`)}.pdf`
          : `${sanitizeFilename(`pedido_fechado_${order.sale_number_text ?? order.id}`)}.pdf`
      }
      await triggerPdfDownload(blob, filename)
    } catch (err: unknown) {
      setDownloadError(err instanceof Error ? err.message : "Erro ao baixar PDF.")
    } finally {
      setDownloadingPdf(null)
    }
  }

  const { status } = order
  const color = STATUS_COLOR[status]
  const activeFinancialTitles = financialTitles.filter((title) => title.status !== "cancelled")
  const titlesOpenCents = activeFinancialTitles.reduce((acc, title) => acc + toCents(title.open_amount), 0)
  const titlesPaidCents = activeFinancialTitles.reduce((acc, title) => acc + toCents(title.paid_amount), 0)
  const titlesNetCents = activeFinancialTitles.reduce((acc, title) => acc + toCents(title.net_amount), 0)

  return (
    <div className="space-y-5">
      {/* Order header */}
      <div
        className="rounded-[2rem] p-6"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-3xl font-black" style={{ color: "var(--color-primary)", fontVariantNumeric: "tabular-nums" }}>
              {order.sale_number_text ?? "RASCUNHO"}
            </p>
            {order.paid_number_text && (
              <p className="mt-0.5 text-sm font-bold" style={{ color: "#10b981" }}>
                {order.paid_number_text}
              </p>
            )}
            <p className="mt-2 text-base font-semibold" style={{ color: "var(--color-text)" }}>
              {orderClientName(order)}
            </p>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Emissão: {fmtDate(order.operation_date)}
              {order.closed_at ? ` · Fechado: ${fmtDate(order.closed_at)}` : ""}
              {order.paid_at ? ` · Pago: ${fmtDate(order.paid_at)}` : ""}
            </p>
          </div>
          <span
            className="rounded-full px-4 py-1.5 text-sm font-black"
            style={{ background: color.bg, border: `1px solid ${color.border}`, color: color.text }}
          >
            {STATUS_LABEL[status]}
          </span>
        </div>
      </div>

      {/* Items */}
      <SectionCard title="Itens" icon={<Package className="h-4 w-4" />}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-border-soft)" }}>
                {["#", "Descrição", "Qtd", "Preço Unit.", "Total"].map((h) => (
                  <th key={h} className="pb-2 text-left text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {order.items.map((item, idx) => (
                <tr key={item.id} style={{ borderBottom: "1px solid var(--color-border-soft)" }}>
                  <td className="py-2 pr-3 font-mono text-xs" style={{ color: "var(--color-text-muted)" }}>{idx + 1}</td>
                  <td className="py-2 pr-3 font-semibold" style={{ color: "var(--color-text)" }}>
                    {item.description}
                    {item.stock_lot_code && (
                      <span className="mt-1 block text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>
                        Lote {item.stock_lot_code} - {fmtLotExpiration(item.stock_lot_expiration_date)}
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>{item.quantity} {item.unit}</td>
                  <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>{fmtMoney(item.unit_price)}</td>
                  <td className="py-2 font-bold" style={{ color: "var(--color-text)" }}>{fmtMoney(item.total_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Totals */}
        <div className="mt-4 space-y-1.5 border-t pt-3" style={{ borderColor: "var(--color-border-soft)" }}>
          <TotalRow label="Subtotal" value={fmtMoney(order.subtotal_amount)} />
          <TotalRow label="Desconto" value={`- ${fmtMoney(order.discount_amount)}`} />
          <TotalRow label="Frete" value={fmtMoney(order.freight_amount)} />
          <div className="pt-1" style={{ borderTop: "1px solid var(--color-border-soft)" }}>
            <TotalRow label="TOTAL" value={fmtMoney(order.total_amount)} bold />
          </div>
        </div>
      </SectionCard>

      {/* Payment plans */}
      {order.payment_plans.length > 0 && (
        <SectionCard title="Condições de Pagamento" icon={<FileText className="h-4 w-4" />}>
          <div className="space-y-2">
            {order.payment_plans.map((plan) => (
              <div key={plan.id} className="flex items-center justify-between gap-3 rounded-2xl px-3 py-2" style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)" }}>
                <p className="text-sm font-semibold" style={{ color: "var(--color-text)" }}>
                  {plan.payment_method_name}
                </p>
                <div className="text-right">
                  <p className="text-sm font-bold" style={{ color: "var(--color-primary)" }}>{fmtMoney(plan.amount)}</p>
                  {plan.due_date && (
                    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Venc: {fmtDate(plan.due_date)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      <SectionCard title="Situação financeira" icon={<FileText className="h-4 w-4" />}>
        <div className="rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(56,189,248,0.08)", border: "1px solid rgba(56,189,248,0.25)", color: "var(--color-text)" }}>
          Pedido fechado é fato comercial. Título é direito financeiro. Baixa/recebimento acontece em Contas a Receber/Caixa.
        </div>
        {status === "quote" ? (
          <p className="mt-3 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Orçamento ainda não fechado. Nenhum título financeiro deve existir para este pedido.
          </p>
        ) : isLoadingFinancialTitles ? (
          <div className="mt-3 flex items-center gap-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando títulos financeiros...
          </div>
        ) : financialTitlesError ? (
          <div className="mt-3 flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}>
            <span>{financialTitlesError}</span>
            <button type="button" onClick={loadFinancialTitles} className="underline">Tentar novamente</button>
          </div>
        ) : financialTitles.length === 0 ? (
          <p className="mt-3 text-sm" style={{ color: "#f59e0b" }}>
            Nenhum título encontrado para este pedido. Verifique a geração em Contas a Receber.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            <div className="grid gap-3 sm:grid-cols-4">
              <MiniMetric label="Títulos" value={String(activeFinancialTitles.length)} />
              <MiniMetric label="Total líquido" value={fmtMoney(titlesNetCents / 100)} />
              <MiniMetric label="Em aberto" value={fmtMoney(titlesOpenCents / 100)} />
              <MiniMetric label="Baixado" value={fmtMoney(titlesPaidCents / 100)} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border-soft)" }}>
                    {["Título", "Status", "Vencimento", "Líquido", "Aberto", "Baixado"].map((header) => (
                      <th key={header} className="pb-2 pr-3 text-left text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {financialTitles.map((title) => (
                    <tr key={title.id} style={{ borderBottom: "1px solid var(--color-border-soft)" }}>
                      <td className="py-2 pr-3 font-semibold" style={{ color: "var(--color-text)" }}>
                        {title.document_reference || title.id}
                        <span className="block text-xs font-medium" style={{ color: "var(--color-text-muted)" }}>
                          Parcela {title.installment_number}/{title.installment_total}
                        </span>
                      </td>
                      <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>
                        {RECEIVABLE_STATUS_LABEL[title.status] ?? title.status}
                      </td>
                      <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>{fmtDate(title.due_date)}</td>
                      <td className="py-2 pr-3 font-bold" style={{ color: "var(--color-text)" }}>{fmtMoney(title.net_amount)}</td>
                      <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>{fmtMoney(title.open_amount)}</td>
                      <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>{fmtMoney(title.paid_amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
      {/* Actions */}
      <SectionCard title="Ações" icon={<CheckCircle2 className="h-4 w-4" />}>
        <div className="flex flex-wrap gap-3">
          {status === "quote" && (
            <>
              {canEditOrder && (
                <ActionBtn color="#10b981" onClick={onEditQuote}>
                  <FileText className="h-4 w-4" /> Editar Orçamento
                </ActionBtn>
              )}
              {canCloseOrder && (
                <ActionBtn color="#38bdf8" onClick={() => { setActionModal("close"); setActionReason("") }}>
                  <ClipboardList className="h-4 w-4" /> Fechar Pedido
                </ActionBtn>
              )}
              {canCancelOrder && (
                <ActionBtn color="#ef4444" onClick={() => { setActionModal("cancel"); setActionReason("") }}>
                  <Ban className="h-4 w-4" /> Cancelar
                </ActionBtn>
              )}
            </>
          )}
          {status === "closed" && (
            <>
              {canReopenOrder && (
                <ActionBtn color="#f59e0b" onClick={() => setShowReopen(true)}>
                  <X className="h-4 w-4" /> Reabrir (senha mestre)
                </ActionBtn>
              )}
              {canCancelOrder && titlesPaidCents === 0 && (
                <ActionBtn color="#ef4444" onClick={() => { setActionModal("cancel"); setActionReason("") }}>
                  <Ban className="h-4 w-4" /> Cancelar
                </ActionBtn>
              )}
            </>
          )}
          {status === "paid" && (
            <p className="text-sm font-semibold" style={{ color: "#f59e0b" }}>
              Pedido pago legado: trate estorno/baixa no financeiro antes de qualquer cancelamento direto.
            </p>
          )}
          {status === "cancelled" && (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Pedido cancelado — somente leitura.
            </p>
          )}
        </div>
        {status === "closed" && (
          <div className="mt-4 rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.35)", color: "var(--color-text)" }}>
            Recebimento oficial: baixe o título em Caixa e Baixas. Pedido fechado não é dinheiro recebido.
          </div>
        )}
        {status === "closed" && titlesPaidCents > 0 && (
          <div className="mt-3 rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}>
            Há baixa financeira vinculada. Estorne/regularize o recebimento antes de cancelar o pedido.
          </div>
        )}

        {/* PDF Downloads — Step 24 */}
        <div className="mt-4 flex flex-wrap gap-2" style={{ borderTop: "1px solid var(--color-border-soft)", paddingTop: "1rem" }}>
          <p className="w-full text-xs font-black uppercase tracking-wide mb-2" style={{ color: "var(--color-text-muted)" }}>
            Downloads
          </p>
          {(status === "quote" || status === "closed" || status === "paid") && (
            <DownloadBtn loading={downloadingPdf === "quote"} onClick={() => void handleDownload("quote")}>
              <Download className="h-3.5 w-3.5" /> Orçamento
            </DownloadBtn>
          )}
          {(status === "closed" || status === "paid") && (
            <DownloadBtn loading={downloadingPdf === "closed"} onClick={() => void handleDownload("closed")}>
              <Download className="h-3.5 w-3.5" /> Pedido Fechado
            </DownloadBtn>
          )}
          {status === "paid" && (
            <DownloadBtn loading={downloadingPdf === "paid"} onClick={() => void handleDownload("paid")}>
              <Download className="h-3.5 w-3.5" /> Espelho NF-e
            </DownloadBtn>
          )}
          {downloadError && (
            <p className="w-full text-sm font-semibold" style={{ color: "#ef4444" }}>{downloadError}</p>
          )}
        </div>
      </SectionCard>

      {/* Status history — Step 24 */}
      <SectionCard title="Histórico" icon={<History className="h-4 w-4" />}>
        {isLoadingHistory ? (
          <div className="flex items-center gap-2" style={{ color: "var(--color-text-muted)" }}>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Carregando histórico…</span>
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Sem histórico registrado.</p>
        ) : (
          <ol className="relative space-y-4 pl-4" style={{ borderLeft: "2px solid var(--color-border-soft)" }}>
            {[...history].reverse().map((h) => {
              const newColor = h.new_status in STATUS_COLOR ? STATUS_COLOR[h.new_status as OrderStatus] : STATUS_COLOR.quote
              return (
                <li key={h.id} className="relative">
                  <span
                    className="absolute -left-5 flex h-4 w-4 items-center justify-center rounded-full border-2 text-xs"
                    style={{ background: newColor.bg, borderColor: newColor.border }}
                  />
                  <div className="ml-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {h.previous_status && (
                        <>
                          <span className="rounded-full px-2 py-0.5 text-xs font-bold" style={{ background: STATUS_COLOR[h.previous_status as OrderStatus]?.bg, color: STATUS_COLOR[h.previous_status as OrderStatus]?.text }}>
                            {STATUS_LABEL[h.previous_status as OrderStatus] ?? h.previous_status}
                          </span>
                          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>→</span>
                        </>
                      )}
                      <span className="rounded-full px-2 py-0.5 text-xs font-bold" style={{ background: newColor.bg, color: newColor.text }}>
                        {STATUS_LABEL[h.new_status as OrderStatus] ?? h.new_status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {fmtDateTime(h.occurred_at)}
                      {h.reason ? ` · ${h.reason}` : ""}
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </SectionCard>

      {/* Inline action modal */}
      {actionModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setActionModal(null) }}
        >
          <div
            className="w-full max-w-md rounded-[2rem] p-6 shadow-2xl"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
          >
            <h3 className="mb-4 text-lg font-black" style={{ color: "var(--color-text)" }}>
              {actionModal === "close" ? "Fechar Pedido" : "Cancelar Pedido"}
            </h3>
            {actionModal === "close" && (
              <div className="mb-4 rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)", color: "var(--color-text)" }}>
                Ao confirmar, o sistema gera número PED, consome estoque dos lotes selecionados e cria título(s) a receber. Recebimento continua em Caixa e Baixas.
              </div>
            )}
            <label className="block space-y-1.5">
              <span className="text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                {actionModal === "cancel" ? "Motivo do cancelamento (obrigatório)" : "Motivo (opcional)"}
              </span>
              <textarea
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                rows={3}
                className="w-full resize-none rounded-2xl px-4 py-3 text-sm outline-none"
                style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text)" }}
              />
            </label>
            {actionError && (
              <p className="mt-3 text-sm" style={{ color: "#ef4444" }}>{actionError}</p>
            )}
            <div className="mt-4 flex gap-3">
              <button
                type="button"
                onClick={() => setActionModal(null)}
                disabled={isSubmitting}
                className="flex-1 rounded-2xl py-2.5 text-sm font-black"
                style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }}
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={isSubmitting || (actionModal === "cancel" && !actionReason.trim())}
                onClick={() => void handleAction(actionModal)}
                className="flex flex-1 items-center justify-center gap-2 rounded-2xl py-2.5 text-sm font-black"
                style={{ background: actionModal === "cancel" ? "#ef4444" : "var(--color-primary)", color: "#fff" }}
              >
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reopen modal — Step 22 */}
      {showReopen && (
        <ReopenOrderModal
          orderId={order.id}
          onSuccess={(updated) => { setShowReopen(false); onReopenSuccess(updated); loadHistory() }}
          onClose={() => setShowReopen(false)}
        />
      )}
    </div>
  )
}

// ─── Small components ─────────────────────────────────────────────────────────

function TabBtn({
  active,
  highlight,
  onClick,
  children,
}: {
  active: boolean
  highlight?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-black"
      style={
        highlight
          ? { background: "#2563eb", color: "#fff", boxShadow: "0 0 12px rgba(37,99,235,0.45)" }
          : active
            ? { background: "var(--color-primary-soft)", border: "1px solid var(--color-primary-border)", color: "var(--color-primary)" }
            : { background: "var(--color-surface)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }
      }
    >
      {children}
    </button>
  )
}

function SectionCard({ title, icon, children }: { title: string; icon?: ReactNode; children: ReactNode }) {
  return (
    <section
      className="rounded-[2rem] p-5"
      style={{ background: "var(--color-surface)", border: "1px solid var(--color-border-soft)" }}
    >
      <h3 className="mb-4 flex items-center gap-2 text-sm font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
        {icon}{title}
      </h3>
      {children}
    </section>
  )
}

function FieldGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <span className="text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </span>
      {children}
    </div>
  )
}

function TotalRow({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-sm ${bold ? "font-black" : "font-medium"}`} style={{ color: bold ? "var(--color-text)" : "var(--color-text-muted)" }}>
        {label}
      </span>
      <span className={`text-sm ${bold ? "font-black" : "font-medium"}`} style={{ color: bold ? "var(--color-primary)" : "var(--color-text-muted)" }}>
        {value}
      </span>
    </div>
  )
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl px-4 py-3" style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)" }}>
      <p className="text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>{label}</p>
      <p className="mt-1 text-base font-black" style={{ color: "var(--color-text)" }}>{value}</p>
    </div>
  )
}

function ActionBtn({ color, onClick, children }: { color: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-black"
      style={{ background: `${color}1a`, border: `1px solid ${color}55`, color }}
    >
      {children}
    </button>
  )
}

function DownloadBtn({ loading, onClick, children }: { loading: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-bold disabled:opacity-60"
      style={{ background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-muted)" }}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
      {children}
    </button>
  )
}

function NoticeBox({ notice, onDismiss }: { notice: { type: "success" | "error"; message: string }; onDismiss: () => void }) {
  const isSuccess = notice.type === "success"
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-2xl px-4 py-3 text-sm font-semibold"
      style={
        isSuccess
          ? { background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", color: "#10b981" }
          : { background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }
      }
    >
      <span className="flex items-center gap-2">
        {isSuccess ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
        {notice.message}
      </span>
      <button type="button" onClick={onDismiss}>
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
