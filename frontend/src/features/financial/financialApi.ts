import { apiRequest } from "../../lib/api"
import type {
  ChartAccount,
  ChartAccountCreatePayload,
  ChartAccountUpdatePayload,
  CostCenter,
  CostCenterCreatePayload,
  CostCenterUpdatePayload,
  FinancialAccount,
  FinancialAccountCreatePayload,
  FinancialAccountUpdatePayload,
  FinancialCategory,
  FinancialCategoryCreatePayload,
  FinancialCategoryUpdatePayload,
  FinancialDiagnostics,
  FinancialPeriodClosure,
  PaymentTerm,
  PaymentTermCreatePayload,
  PaymentTermUpdatePayload,
} from "./types"

function paramsWithCompany(companyId: string, extra?: Record<string, string | number | undefined>) {
  const params = new URLSearchParams({ company_id: companyId, limit: "200", offset: "0" })
  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value))
  })
  return params.toString()
}

type BaseListFilters = {
  status?: string
  search?: string
  limit?: number
  offset?: number
}

export async function getFinancialDiagnostics(companyId: string) {
  return apiRequest<FinancialDiagnostics>(`/financial/diagnostics?company_id=${encodeURIComponent(companyId)}`)
}

export async function listFinancialPeriodClosures(companyId: string) {
  return apiRequest<FinancialPeriodClosure[]>(`/financial/period-closures?${paramsWithCompany(companyId, { status: "active" })}`)
}

export async function createFinancialDefaults(companyId: string) {
  return apiRequest<Record<string, unknown>>(`/financial/defaults?company_id=${encodeURIComponent(companyId)}`, { method: "POST" })
}

export async function listChartAccounts(companyId: string, filters?: BaseListFilters & { account_type?: string }) {
  return apiRequest<ChartAccount[]>(`/financial/chart-accounts?${paramsWithCompany(companyId, filters)}`)
}

export async function createChartAccount(payload: ChartAccountCreatePayload) {
  return apiRequest<ChartAccount>("/financial/chart-accounts", { method: "POST", body: payload })
}

export async function updateChartAccount(accountId: string, payload: ChartAccountUpdatePayload) {
  return apiRequest<ChartAccount>(`/financial/chart-accounts/${encodeURIComponent(accountId)}`, { method: "PATCH", body: payload })
}

export async function listFinancialCategories(companyId: string, filters?: BaseListFilters & { category_type?: string; cash_flow_group?: string }) {
  return apiRequest<FinancialCategory[]>(`/financial/categories?${paramsWithCompany(companyId, filters)}`)
}

export async function createFinancialCategory(payload: FinancialCategoryCreatePayload) {
  return apiRequest<FinancialCategory>("/financial/categories", { method: "POST", body: payload })
}

export async function updateFinancialCategory(categoryId: string, payload: FinancialCategoryUpdatePayload) {
  return apiRequest<FinancialCategory>(`/financial/categories/${encodeURIComponent(categoryId)}`, { method: "PATCH", body: payload })
}

export async function listCostCenters(companyId: string, filters?: BaseListFilters & { center_type?: string }) {
  return apiRequest<CostCenter[]>(`/financial/cost-centers?${paramsWithCompany(companyId, filters)}`)
}

export async function createCostCenter(payload: CostCenterCreatePayload) {
  return apiRequest<CostCenter>("/financial/cost-centers", { method: "POST", body: payload })
}

export async function updateCostCenter(costCenterId: string, payload: CostCenterUpdatePayload) {
  return apiRequest<CostCenter>(`/financial/cost-centers/${encodeURIComponent(costCenterId)}`, { method: "PATCH", body: payload })
}

export async function listFinancialAccounts(companyId: string, filters?: BaseListFilters & { account_type?: string }) {
  return apiRequest<FinancialAccount[]>(`/financial/accounts?${paramsWithCompany(companyId, filters)}`)
}

export async function createFinancialAccount(payload: FinancialAccountCreatePayload) {
  return apiRequest<FinancialAccount>("/financial/accounts", { method: "POST", body: payload })
}

export async function updateFinancialAccount(accountId: string, payload: FinancialAccountUpdatePayload) {
  return apiRequest<FinancialAccount>(`/financial/accounts/${encodeURIComponent(accountId)}`, { method: "PATCH", body: payload })
}

export async function listPaymentTerms(companyId: string, filters?: BaseListFilters & { term_type?: string }) {
  return apiRequest<PaymentTerm[]>(`/financial/payment-terms?${paramsWithCompany(companyId, filters)}`)
}

export async function createPaymentTerm(payload: PaymentTermCreatePayload) {
  return apiRequest<PaymentTerm>("/financial/payment-terms", { method: "POST", body: payload })
}

export async function updatePaymentTerm(termId: string, payload: PaymentTermUpdatePayload) {
  return apiRequest<PaymentTerm>(`/financial/payment-terms/${encodeURIComponent(termId)}`, { method: "PATCH", body: payload })
}
