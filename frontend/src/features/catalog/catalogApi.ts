import { apiRequest } from "../../lib/api"

import type {
  CatalogDiagnostics,
  CatalogFiscalFilter,
  CatalogItem,
  CatalogItemAuditEvent,
  CatalogItemCreatePayload,
  CatalogItemsPage,
  CatalogItemStatus,
  CatalogItemType,
  CatalogItemUpdatePayload,
  CatalogSearchScope,
  CatalogStockFilter,
  CatalogItemOrigin,
  CatalogRules,
  CatalogSummary,
} from "./types"

type ListCatalogItemsParams = {
  company_id?: string
  item_type?: CatalogItemType
  status?: CatalogItemStatus
  origin?: CatalogItemOrigin
  unit?: string
  category?: string
  search?: string
  search_scope?: CatalogSearchScope
  stock_filter?: CatalogStockFilter
  fiscal_filter?: CatalogFiscalFilter
  min_sale_price?: string
  max_sale_price?: string
  min_cost_price?: string
  max_cost_price?: string
  limit?: number
  offset?: number
}

function buildQueryString(params?: ListCatalogItemsParams) {
  if (!params) return ""

  const searchParams = new URLSearchParams()

  if (params.company_id) {
    searchParams.set("company_id", params.company_id)
  }

  if (params.item_type) {
    searchParams.set("item_type", params.item_type)
  }

  if (params.status) {
    searchParams.set("status", params.status)
  }

  if (params.origin) {
    searchParams.set("origin", params.origin)
  }

  if (params.unit && params.unit.trim()) {
    searchParams.set("unit", params.unit.trim())
  }

  if (params.category && params.category.trim()) {
    searchParams.set("category", params.category.trim())
  }

  if (params.search) {
    searchParams.set("search", params.search)
  }

  if (params.search_scope) {
    searchParams.set("search_scope", params.search_scope)
  }

  if (params.stock_filter) {
    searchParams.set("stock_filter", params.stock_filter)
  }

  if (params.fiscal_filter) {
    searchParams.set("fiscal_filter", params.fiscal_filter)
  }

  if (params.min_sale_price) {
    searchParams.set("min_sale_price", params.min_sale_price)
  }

  if (params.max_sale_price) {
    searchParams.set("max_sale_price", params.max_sale_price)
  }

  if (params.min_cost_price) {
    searchParams.set("min_cost_price", params.min_cost_price)
  }

  if (params.max_cost_price) {
    searchParams.set("max_cost_price", params.max_cost_price)
  }

  if (params.limit !== undefined) {
    searchParams.set("limit", String(params.limit))
  }

  if (params.offset !== undefined) {
    searchParams.set("offset", String(params.offset))
  }

  const queryString = searchParams.toString()

  return queryString ? `?${queryString}` : ""
}

export function getCatalogItems(params?: ListCatalogItemsParams) {
  const queryString = buildQueryString(params)

  return apiRequest<CatalogItemsPage>(`/catalog/items${queryString}`).then((response) => ({
    ...response,
    data: response.data.items,
  }))
}

export function getCatalogItemsPage(params?: ListCatalogItemsParams) {
  const queryString = buildQueryString(params)

  return apiRequest<CatalogItemsPage>(`/catalog/items${queryString}`)
}

export function createCatalogItem(payload: CatalogItemCreatePayload) {
  return apiRequest<CatalogItem>("/catalog/items", {
    method: "POST",
    body: payload,
  })
}

export function getCatalogItem(itemId: string) {
  return apiRequest<CatalogItem>(`/catalog/items/${itemId}`)
}

export function updateCatalogItem(
  itemId: string,
  payload: CatalogItemUpdatePayload,
) {
  return apiRequest<CatalogItem>(`/catalog/items/${itemId}`, {
    method: "PATCH",
    body: payload,
  })
}

export function getCatalogItemAuditEvents(itemId: string) {
  return apiRequest<CatalogItemAuditEvent[]>(`/catalog/items/${itemId}/audit`)
}

export function getCatalogRules() {
  return apiRequest<CatalogRules>("/catalog/rules")
}

export function getCatalogSummary(companyId?: string) {
  const queryString = companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""

  return apiRequest<CatalogSummary>(`/catalog/summary${queryString}`)
}

export function getCatalogDiagnostics() {
  return apiRequest<CatalogDiagnostics>("/catalog/diagnostics")
}
