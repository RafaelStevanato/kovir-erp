import { apiRequest } from "../../lib/api"
import type { CashDiagnostics, CashSummary, FinancialAccountBalance, FinancialMovement, ManualMovementCreatePayload, Settlement, SettlementCreatePayload } from "./types"

function paramsWithCompany(companyId: string, extra?: Record<string, string | undefined>) {
  const params = new URLSearchParams({ company_id: companyId, limit: "200", offset: "0" })
  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value) params.set(key, value)
  })
  return params.toString()
}

export async function getCashDiagnostics() {
  return apiRequest<CashDiagnostics>("/cash/diagnostics")
}

export async function getCashSummary(companyId: string) {
  return apiRequest<CashSummary>(`/cash/summary?company_id=${encodeURIComponent(companyId)}`)
}

export async function listSettlements(companyId: string, filters?: Record<string, string | undefined>) {
  return apiRequest<Settlement[]>(`/cash/settlements?${paramsWithCompany(companyId, filters)}`)
}

export async function createSettlement(payload: SettlementCreatePayload) {
  return apiRequest<{ settlement: Settlement; movement: FinancialMovement; title: unknown; balance: FinancialAccountBalance }>("/cash/settlements", { method: "POST", body: payload })
}

export async function reverseSettlement(settlementId: string, reason: string) {
  return apiRequest<{ settlement: Settlement; reversed_movement_id: string; reversal_movement: FinancialMovement; title: unknown; balance: FinancialAccountBalance }>(`/cash/settlements/${encodeURIComponent(settlementId)}/reverse`, { method: "POST", body: { reason } })
}

export async function listFinancialMovements(companyId: string, filters?: Record<string, string | undefined>) {
  return apiRequest<FinancialMovement[]>(`/cash/movements?${paramsWithCompany(companyId, filters)}`)
}

export async function createManualFinancialMovement(payload: ManualMovementCreatePayload) {
  return apiRequest<{ movement: FinancialMovement; balance: FinancialAccountBalance }>("/cash/movements", { method: "POST", body: payload })
}

export async function reverseManualFinancialMovement(movementId: string, reason: string) {
  return apiRequest<{ movement: FinancialMovement; reversed_movement_id: string; reversal_movement: FinancialMovement; balance: FinancialAccountBalance }>(`/cash/movements/${encodeURIComponent(movementId)}/reverse`, { method: "POST", body: { reason } })
}

export async function listFinancialAccountBalances(companyId: string, financialAccountId?: string) {
  const extra = financialAccountId ? { financial_account_id: financialAccountId } : undefined
  return apiRequest<FinancialAccountBalance[]>(`/cash/balances?${paramsWithCompany(companyId, extra)}`)
}
