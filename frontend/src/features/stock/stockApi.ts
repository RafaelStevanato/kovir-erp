import { apiRequest, type ApiResponse } from "../../lib/api"
import type {
  StockBalance,
  StockDiagnostics,
  StockLocation,
  StockLocationCreatePayload,
  StockLot,
  StockMovement,
  StockItemAvailability,
  StockMovementCreatePayload,
  StockPurchaseEntry,
  StockPurchaseEntryCreatePayload,
  StockPurchaseXmlParseResult,
} from "./types"

export async function getStockDiagnostics(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId })
  return apiRequest<StockDiagnostics>(`/stock/diagnostics?${params.toString()}`)
}

export async function getStockRules() {
  return apiRequest<Record<string, unknown>>("/stock/rules")
}

export async function listStockLocations(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId, limit: "200", offset: "0" })
  return apiRequest<StockLocation[]>(`/stock/locations?${params.toString()}`)
}

export async function ensureDefaultStockLocation(companyId: string) {
  const params = new URLSearchParams({ company_id: companyId })
  return apiRequest<StockLocation>(`/stock/locations/default?${params.toString()}`, { method: "POST" })
}

export async function createStockLocation(payload: StockLocationCreatePayload) {
  return apiRequest<StockLocation>("/stock/locations", { method: "POST", body: payload })
}

export async function listStockBalances(companyId: string, filters?: { item_id?: string; location_id?: string }) {
  const params = new URLSearchParams({ company_id: companyId, limit: "500", offset: "0" })
  if (filters?.item_id) params.set("item_id", filters.item_id)
  if (filters?.location_id) params.set("location_id", filters.location_id)
  return apiRequest<StockBalance[]>(`/stock/balances?${params.toString()}`)
}

export async function listStockLots(
  companyId: string,
  filters?: { item_id?: string; location_id?: string; only_positive?: boolean },
) {
  const params = new URLSearchParams({ company_id: companyId, limit: "500", offset: "0" })
  if (filters?.item_id) params.set("item_id", filters.item_id)
  if (filters?.location_id) params.set("location_id", filters.location_id)
  if (filters?.only_positive) params.set("only_positive", "true")
  return apiRequest<StockLot[]>(`/stock/lots?${params.toString()}`)
}

export async function getStockItemAvailability(companyId: string, itemId: string, locationId?: string): Promise<ApiResponse<StockItemAvailability>> {
  const params = new URLSearchParams({ company_id: companyId })
  if (locationId) params.set("location_id", locationId)
  return apiRequest<StockItemAvailability>(`/stock/items/${itemId}/availability?${params.toString()}`)
}

export async function getStockItemsAvailability(companyId: string, itemIds: string[], locationId?: string): Promise<ApiResponse<StockItemAvailability[]>> {
  const uniqueItemIds = Array.from(new Set(itemIds.filter(Boolean)))
  if (uniqueItemIds.length === 0) {
    return { success: true, message: "Nenhum item para consultar.", data: [] as StockItemAvailability[] }
  }
  const params = new URLSearchParams({ company_id: companyId, item_ids: uniqueItemIds.join(",") })
  if (locationId) params.set("location_id", locationId)
  return apiRequest<StockItemAvailability[]>(`/stock/items/availability?${params.toString()}`)
}

export async function listStockMovements(companyId: string, filters?: { item_id?: string; location_id?: string; movement_type?: string; source_type?: string }) {
  const params = new URLSearchParams({ company_id: companyId, limit: "300", offset: "0" })
  if (filters?.item_id) params.set("item_id", filters.item_id)
  if (filters?.location_id) params.set("location_id", filters.location_id)
  if (filters?.movement_type) params.set("movement_type", filters.movement_type)
  if (filters?.source_type) params.set("source_type", filters.source_type)
  return apiRequest<StockMovement[]>(`/stock/movements?${params.toString()}`)
}

export async function createStockMovement(payload: StockMovementCreatePayload) {
  return apiRequest<StockMovement>("/stock/movements", { method: "POST", body: payload })
}

export async function listStockPurchaseEntries(companyId: string, filters?: { document_number?: string; supplier_participant_id?: string; location_id?: string; include_items?: boolean }) {
  const params = new URLSearchParams({ company_id: companyId, limit: "300", offset: "0" })
  if (filters?.document_number) params.set("document_number", filters.document_number)
  if (filters?.supplier_participant_id) params.set("supplier_participant_id", filters.supplier_participant_id)
  if (filters?.location_id) params.set("location_id", filters.location_id)
  if (filters?.include_items) params.set("include_items", "true")
  return apiRequest<StockPurchaseEntry[]>(`/stock/purchase-entries?${params.toString()}`)
}

export async function createStockPurchaseEntry(payload: StockPurchaseEntryCreatePayload) {
  return apiRequest<StockPurchaseEntry>("/stock/purchase-entries", { method: "POST", body: payload })
}


export async function parseStockPurchaseXml(companyId: string, xmlText: string) {
  return apiRequest<StockPurchaseXmlParseResult>("/stock/purchase-entries/parse-xml", {
    method: "POST",
    body: { company_id: companyId, xml_text: xmlText },
  })
}
