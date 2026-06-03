import { apiRequest } from "../../lib/api"

import type { MercadoPagoAccount, MercadoPagoDiagnostics, MercadoPagoGenericRow, MercadoPagoRules } from "./types"

function buildQueryString(params?: Record<string, unknown>) {
  if (!params) return ""
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return
    searchParams.set(key, String(value))
  })
  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ""
}

export function getMercadoPagoDiagnostics(params?: { company_id?: string }) {
  return apiRequest<MercadoPagoDiagnostics>(`/mercado-pago/diagnostics${buildQueryString(params)}`)
}

export function getMercadoPagoRules() {
  return apiRequest<MercadoPagoRules>("/mercado-pago/rules")
}

export function getMercadoPagoAccount(params: { company_id: string }) {
  return apiRequest<MercadoPagoAccount>(`/mercado-pago/account${buildQueryString(params)}`)
}

export function preconfigureMercadoPagoAccount(params: { company_id: string }) {
  return apiRequest<MercadoPagoAccount>(`/mercado-pago/account/preconfigure${buildQueryString(params)}`, {
    method: "POST",
  })
}

export function getMercadoPagoPayments(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/payments${buildQueryString(params)}`)
}

export function getMercadoPagoReleases(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/releases${buildQueryString(params)}`)
}

export function getMercadoPagoWebhooks(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/webhooks${buildQueryString(params)}`)
}

export function getMercadoPagoRefunds(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/refunds${buildQueryString(params)}`)
}

export function getMercadoPagoChargebacks(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/chargebacks${buildQueryString(params)}`)
}

export function getMercadoPagoCheckoutPreferences(params: { company_id: string; limit?: number; offset?: number }) {
  return apiRequest<MercadoPagoGenericRow[]>(`/mercado-pago/checkout-preferences${buildQueryString(params)}`)
}
