import { apiRequest } from "../../lib/api"
import type { PayablePaymentPayload, PayableTitle, Purchase, PurchaseConfirmPayload, PurchaseCreateAndConfirmPayload, PurchaseCreatePayload, PurchasesPayablesDiagnostics, PurchasesPayablesOverviewEvidence, PurchasesPayablesSummary } from "./types"

export type PurchasesPayablesFilters = Record<string, string | number | undefined>

function paramsWithCompany(companyId: string, extra?: PurchasesPayablesFilters) {
  const params = new URLSearchParams({ company_id: companyId, limit: "200", offset: "0" })
  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value))
  })
  return params.toString()
}

export function getPurchasesPayablesDiagnostics() {
  return apiRequest<PurchasesPayablesDiagnostics>("/purchases-payables/diagnostics")
}

export function getPurchasesPayablesSummary(companyId: string) {
  return apiRequest<PurchasesPayablesSummary>(`/purchases-payables/summary?company_id=${encodeURIComponent(companyId)}`)
}

export function getPurchasesPayablesOverviewEvidence(companyId: string, filters?: { block?: string; limit?: number }) {
  return apiRequest<PurchasesPayablesOverviewEvidence>(`/purchases-payables/overview-evidence?${paramsWithCompany(companyId, filters)}`)
}

export function listPurchases(companyId: string, filters?: Record<string, string | number | undefined>) {
  return apiRequest<Purchase[]>(`/purchases-payables/purchases?${paramsWithCompany(companyId, filters)}`)
}

export function exportPurchases(companyId: string, filters?: Record<string, string | number | undefined>) {
  return apiRequest<Purchase[]>(`/purchases-payables/purchases/export?${paramsWithCompany(companyId, { ...filters, limit: 5000, offset: 0 })}`)
}

export function createPurchase(payload: PurchaseCreatePayload) {
  return apiRequest<Purchase>("/purchases-payables/purchases", { method: "POST", body: payload })
}

export function createAndConfirmPurchase(payload: PurchaseCreateAndConfirmPayload) {
  return apiRequest<{ purchase: Purchase; payables: PayableTitle[] }>("/purchases-payables/purchases/create-and-confirm", { method: "POST", body: payload })
}

export function confirmPurchase(purchaseId: string, payload: PurchaseConfirmPayload) {
  return apiRequest<{ purchase: Purchase; payables: PayableTitle[] }>(`/purchases-payables/purchases/${encodeURIComponent(purchaseId)}/confirm`, { method: "POST", body: payload })
}

export function cancelPurchase(purchaseId: string, reason: string) {
  return apiRequest<Purchase>(`/purchases-payables/purchases/${encodeURIComponent(purchaseId)}/cancel`, { method: "POST", body: { reason } })
}

export function listPayables(companyId: string, filters?: PurchasesPayablesFilters) {
  return apiRequest<PayableTitle[]>(`/purchases-payables/payables?${paramsWithCompany(companyId, filters)}`)
}

export function exportPayables(companyId: string, filters?: PurchasesPayablesFilters) {
  return apiRequest<PayableTitle[]>(`/purchases-payables/payables/export?${paramsWithCompany(companyId, { ...filters, limit: 5000, offset: 0 })}`)
}

export function cancelPayable(titleId: string, reason: string) {
  return apiRequest<PayableTitle>(`/purchases-payables/payables/${encodeURIComponent(titleId)}/cancel`, { method: "POST", body: { reason } })
}

export function payPayable(payload: PayablePaymentPayload) {
  return apiRequest<{ settlement: unknown; movement: unknown; title: PayableTitle; balance: unknown }>("/purchases-payables/payments", { method: "POST", body: payload })
}
