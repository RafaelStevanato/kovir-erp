import { apiRequest } from "../../lib/api"
import type { ReceivableCreatePayload, ReceivableTitle, ReceivablesDiagnostics, ReceivablesSummary } from "./types"

type ListReceivableTitleFilters = {
  participant_id?: string
  status?: string
  collection_status?: string
  fiscal_status?: string
  sale_id?: string
  source_type?: string
  due_from?: string
  due_to?: string
  q?: string
  limit?: number
  offset?: number
}

function paramsWithCompany(companyId: string, extra?: ListReceivableTitleFilters) {
  const params = new URLSearchParams({ company_id: companyId, limit: "50", offset: "0" })
  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value))
  })
  return params.toString()
}

export async function getAccountsReceivableDiagnostics() {
  return apiRequest<ReceivablesDiagnostics>("/accounts-receivable/diagnostics")
}

export async function getReceivablesSummary(companyId: string) {
  return apiRequest<ReceivablesSummary>(`/accounts-receivable/summary?company_id=${encodeURIComponent(companyId)}`)
}

export async function listReceivableTitles(companyId: string, filters?: ListReceivableTitleFilters) {
  return apiRequest<ReceivableTitle[]>(`/accounts-receivable/titles?${paramsWithCompany(companyId, filters)}`)
}

export async function createReceivableTitle(payload: ReceivableCreatePayload) {
  return apiRequest<ReceivableTitle>("/accounts-receivable/titles", { method: "POST", body: payload })
}

export async function generateReceivablesFromSale(saleId: string) {
  return apiRequest<ReceivableTitle[]>(`/accounts-receivable/from-sale/${encodeURIComponent(saleId)}`, { method: "POST", body: { reason: "Geracao manual de titulos para pedido fechado." } })
}

export async function cancelReceivableTitle(titleId: string, reason: string) {
  return apiRequest<ReceivableTitle>(`/accounts-receivable/titles/${encodeURIComponent(titleId)}/cancel`, { method: "POST", body: { reason } })
}
