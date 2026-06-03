import { apiDownloadBlob, apiRequest } from "../../lib/api"

import type {
  FiscalDocument,
  FiscalInvoiceReadiness,
  Sale,
  CatalogItemFiscalRule,
  OperationNature,
  PaymentMethod,
  SaleAuditEvent,
  SaleCreatePayload,
  SaleItemReadiness,
  SaleStatus,
  SaleType,
  SaleStatusChangePayload,
  SaleStatusHistory,
  SaleUpdatePayload,
  SalesDiagnostics,
  SalesRules,
} from "./types"

export type ListSalesParams = {
  company_id?: string
  participant_id?: string
  sale_type?: SaleType
  status?: SaleStatus
  limit?: number
  offset?: number
}

function buildQueryString(params?: Record<string, unknown>) {
  if (!params) return ""

  const searchParams = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return
    }

    searchParams.set(key, String(value))
  })

  const queryString = searchParams.toString()

  return queryString ? `?${queryString}` : ""
}

export function getSales(params?: ListSalesParams) {
  return apiRequest<Sale[]>(`/sales${buildQueryString(params)}`)
}

export function createSale(payload: SaleCreatePayload) {
  return apiRequest<Sale>("/sales", {
    method: "POST",
    body: payload,
  })
}

export function getSale(saleId: string) {
  return apiRequest<Sale>(`/sales/${saleId}`)
}

export function updateSale(saleId: string, payload: SaleUpdatePayload) {
  return apiRequest<Sale>(`/sales/${saleId}`, {
    method: "PATCH",
    body: payload,
  })
}

/** @deprecated Use closeSale. Mantido como alias de compatibilidade. */
export function confirmSale(
  saleId: string,
  payload: SaleStatusChangePayload = {},
) {
  return apiRequest<Sale>(`/sales/${saleId}/confirm`, {
    method: "POST",
    body: payload,
  })
}

export function closeSale(
  saleId: string,
  payload: SaleStatusChangePayload = {},
) {
  return apiRequest<Sale>(`/sales/${saleId}/confirm`, {
    method: "POST",
    body: payload,
  })
}

export function cancelSale(
  saleId: string,
  payload: SaleStatusChangePayload = {},
) {
  return apiRequest<Sale>(`/sales/${saleId}/cancel`, {
    method: "POST",
    body: payload,
  })
}

export function getSaleAuditEvents(saleId: string) {
  return apiRequest<SaleAuditEvent[]>(`/sales/${saleId}/audit`)
}

export function getSaleStatusHistory(saleId: string) {
  return apiRequest<SaleStatusHistory[]>(`/sales/${saleId}/status-history`)
}

export function getSalesPaymentMethods(params: { company_id: string }) {
  const query = buildQueryString(params)
  return apiRequest<PaymentMethod[]>(`/sales/payment-methods${query}`)
}

export function getSalesOperationNatures(params: { company_id: string; sale_type?: SaleType }) {
  const query = buildQueryString(params)
  return apiRequest<OperationNature[]>(`/sales/operation-natures${query}`)
}

export function getSalesFiscalRules(params: { company_id: string; catalog_item_id?: string; operation_nature_id?: string }) {
  const query = buildQueryString(params)
  return apiRequest<CatalogItemFiscalRule[]>(`/sales/fiscal-rules${query}`)
}

export function getSalesItemReadiness(params: {
  company_id: string
  sale_type: SaleType
  operation_nature?: string
  operation_nature_id?: string | null
  valid_on?: string | null
  location_id?: string | null
  limit?: number
  offset?: number
}) {
  const query = buildQueryString(params)
  return apiRequest<SaleItemReadiness[]>(`/sales/item-readiness${query}`)
}

export function getSalesRules() {
  return apiRequest<SalesRules>("/sales/rules")
}

export function getSalesDiagnostics() {
  return apiRequest<SalesDiagnostics>("/sales/diagnostics")
}

export function getSaleInvoiceReadiness(saleId: string) {
  return apiRequest<FiscalInvoiceReadiness>(`/sales/${saleId}/invoice-readiness`)
}

export function postSaleInvoice(saleId: string) {
  return apiRequest<FiscalDocument>(`/sales/${saleId}/invoice`, {
    method: "POST",
    body: {},
  })
}

export async function getCommercialInvoicePdf(saleId: string, mode: "closed" | "paid"): Promise<Blob> {
  return apiDownloadBlob(`/sales/${saleId}/commercial-invoice.pdf?mode=${mode}`, {
    accept: "application/pdf",
    errorMessage: "Erro ao gerar PDF",
  })
}

export async function getSaleFiscalPreviewPdf(saleId: string): Promise<Blob> {
  return apiDownloadBlob(`/sales/${saleId}/fiscal-preview.pdf`, {
    accept: "application/pdf",
    errorMessage: "Erro ao gerar PDF",
  })
}

export function getFiscalDocumentsForSale(saleId: string) {
  return apiRequest<FiscalDocument[]>(`/fiscal-documents/sale/${saleId}`)
}
