import { apiRequest } from "../../lib/api"

import type {
  MarketplaceAccount,
  MarketplaceAccountUpdatePayload,
  MarketplaceProvider,
  MarketplacesDiagnostics,
  MarketplacesRules,
  MarketplaceSyncRun,
} from "./types"

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

export function getMarketplacesDiagnostics(params?: { company_id?: string }) {
  return apiRequest<MarketplacesDiagnostics>(`/marketplaces/diagnostics${buildQueryString(params)}`)
}

export function getMarketplaceProviders() {
  return apiRequest<MarketplaceProvider[]>("/marketplaces/providers")
}

export function getMarketplaceRules() {
  return apiRequest<MarketplacesRules>("/marketplaces/rules")
}

export function getMarketplaceAccounts(params: {
  company_id: string
  provider_code?: string
  provider_type?: string
  status?: string
  limit?: number
  offset?: number
}) {
  return apiRequest<MarketplaceAccount[]>(`/marketplaces/accounts${buildQueryString(params)}`)
}

export function updateMarketplaceAccount(accountId: string, payload: MarketplaceAccountUpdatePayload) {
  return apiRequest<MarketplaceAccount>(`/marketplaces/accounts/${accountId}`, {
    method: "PATCH",
    body: payload,
  })
}

export function getMarketplaceSyncRuns(params: {
  company_id: string
  marketplace_account_id?: string
  limit?: number
  offset?: number
}) {
  return apiRequest<MarketplaceSyncRun[]>(`/marketplaces/sync-runs${buildQueryString(params)}`)
}
