import { apiDownloadBlob, apiRequest } from "../../lib/api"
import type {
  Order,
  OrderCreatePayload,
  OrderStatus,
  OrderStatusChangePayload,
  OrderStatusHistory,
  ReopenOrderPayload,
} from "./types"

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return ""
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}

export type ListOrdersParams = {
  company_id?: string
  participant_id?: string
  status?: OrderStatus
  q?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export function listOrders(params?: ListOrdersParams) {
  return apiRequest<Order[]>(`/sales${buildQueryString(params)}`)
}

export function getOrdersSummary(params?: Omit<ListOrdersParams, "limit" | "offset">) {
  return apiRequest<{ total: number; counts_by_status: Record<OrderStatus, number> }>(`/sales/summary${buildQueryString(params)}`)
}

export function getOrder(id: string) {
  return apiRequest<Order>(`/sales/${id}`)
}

export function createOrder(payload: OrderCreatePayload) {
  return apiRequest<Order>("/sales", { method: "POST", body: payload })
}

export function updateOrder(id: string, payload: OrderCreatePayload) {
  return apiRequest<Order>(`/sales/${id}`, { method: "PATCH", body: payload })
}

export function closeOrder(id: string, payload: OrderStatusChangePayload = {}) {
  return apiRequest<Order>(`/sales/${id}/confirm`, { method: "POST", body: payload })
}

export function cancelOrder(id: string, payload: OrderStatusChangePayload = {}) {
  return apiRequest<Order>(`/sales/${id}/cancel`, { method: "POST", body: payload })
}

export function reopenOrder(id: string, payload: ReopenOrderPayload) {
  return apiRequest<Order>(`/sales/${id}/reopen`, { method: "POST", body: payload })
}

export function getOrderStatusHistory(id: string) {
  return apiRequest<OrderStatusHistory[]>(`/sales/${id}/status-history`)
}

async function _downloadPdf(path: string): Promise<Blob> {
  return apiDownloadBlob(path, {
    accept: "application/pdf",
    errorMessage: "Erro ao gerar PDF",
  })
}

export function downloadQuotePdf(id: string): Promise<Blob> {
  return _downloadPdf(`/sales/${id}/quote.pdf`)
}

export function downloadCommercialInvoicePdf(id: string, mode: "closed" | "paid"): Promise<Blob> {
  return _downloadPdf(`/sales/${id}/commercial-invoice.pdf?mode=${mode}`)
}

// ── Senha mestre ────────────────────────────────────────────────────────────

export function getMasterPasswordStatus() {
  return apiRequest<{ configured: boolean }>("/security/master-password/status")
}

export function setMasterPassword(password: string) {
  return apiRequest<{ configured: boolean }>("/security/master-password", {
    method: "POST",
    body: { password },
  })
}
