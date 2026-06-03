import { apiRequest } from "../../lib/api"
import type { CashFlowAccountRow, CashFlowDailyRow, CashFlowDiagnostics, CashFlowOverviewEvidence, CashFlowPending, CashFlowReconciliationStatus, CashFlowSummary } from "./types"

export type CashFlowFilters = {
  start_date?: string
  end_date?: string
  financial_account_id?: string
  limit?: string | number
  offset?: string | number
}

function paramsWithCompany(companyId: string, filters?: CashFlowFilters) {
  const params = new URLSearchParams({ company_id: companyId })
  Object.entries(filters ?? {}).forEach(([key, value]) => {
    if (value) params.set(key, String(value))
  })
  return params.toString()
}

export async function getCashFlowDiagnostics() {
  return apiRequest<CashFlowDiagnostics>("/cash-flow/diagnostics")
}

export async function getCashFlowSummary(companyId: string, filters?: CashFlowFilters) {
  return apiRequest<CashFlowSummary>(`/cash-flow/summary?${paramsWithCompany(companyId, filters)}`)
}

export async function getCashFlowDaily(companyId: string, filters?: CashFlowFilters) {
  return apiRequest<CashFlowDailyRow[]>(`/cash-flow/daily?${paramsWithCompany(companyId, filters)}`)
}

export async function getCashFlowAccounts(companyId: string, filters?: CashFlowFilters) {
  return apiRequest<CashFlowAccountRow[]>(`/cash-flow/accounts?${paramsWithCompany(companyId, filters)}`)
}

export async function getCashFlowPending(companyId: string, filters?: CashFlowFilters & { limit?: string }) {
  return apiRequest<CashFlowPending>(`/cash-flow/pending?${paramsWithCompany(companyId, filters)}`)
}

export async function getCashFlowOverviewEvidence(companyId: string, filters?: CashFlowFilters & { limit?: string }) {
  return apiRequest<CashFlowOverviewEvidence>(`/cash-flow/overview-evidence?${paramsWithCompany(companyId, filters)}`)
}

export async function getCashFlowReconciliationStatus(companyId: string, filters?: CashFlowFilters) {
  return apiRequest<CashFlowReconciliationStatus>(`/cash-flow/reconciliation-status?${paramsWithCompany(companyId, filters)}`)
}
