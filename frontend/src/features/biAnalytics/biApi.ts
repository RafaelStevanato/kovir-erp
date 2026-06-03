import { apiDownloadBlob, apiRequest } from "../../lib/api"
import type {
  AgingReport,
  CashFlow13wReport,
  CashFlowByCategoryReport,
  ConcentrationReport,
  DreMonthlyReport,
  PaymentMethodMixReport,
  PowerBiManifest,
  WorkingCapitalKpis,
} from "./types"

function buildQuery(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return
    query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `?${serialized}` : ""
}

export type BiPeriodFilters = { start_date?: string; end_date?: string }

export function getWorkingCapitalKpis(companyId: string, filters: BiPeriodFilters = {}) {
  return apiRequest<WorkingCapitalKpis>(
    `/bi/working-capital-kpis${buildQuery({ company_id: companyId, ...filters })}`,
  )
}

export function getAgingReceivables(companyId: string, asOf?: string) {
  return apiRequest<AgingReport>(`/bi/aging-receivables${buildQuery({ company_id: companyId, as_of: asOf })}`)
}

export function getAgingPayables(companyId: string, asOf?: string) {
  return apiRequest<AgingReport>(`/bi/aging-payables${buildQuery({ company_id: companyId, as_of: asOf })}`)
}

export function getCustomerConcentration(
  companyId: string,
  filters: BiPeriodFilters & { top?: number } = {},
) {
  return apiRequest<ConcentrationReport>(
    `/bi/customer-concentration${buildQuery({ company_id: companyId, ...filters })}`,
  )
}

export function getSupplierConcentration(
  companyId: string,
  filters: BiPeriodFilters & { top?: number } = {},
) {
  return apiRequest<ConcentrationReport>(
    `/bi/supplier-concentration${buildQuery({ company_id: companyId, ...filters })}`,
  )
}

export function getDreMonthly(companyId: string, months = 12) {
  return apiRequest<DreMonthlyReport>(`/bi/dre-monthly${buildQuery({ company_id: companyId, months })}`)
}

export function getCashFlow13w(
  companyId: string,
  filters: { weeks?: number; start_date?: string; financial_account_id?: string } = {},
) {
  return apiRequest<CashFlow13wReport>(`/bi/cash-flow-13w${buildQuery({ company_id: companyId, ...filters })}`)
}

export function getCashFlowByCategory(companyId: string, filters: BiPeriodFilters & { financial_account_id?: string } = {}) {
  return apiRequest<CashFlowByCategoryReport>(
    `/bi/cash-flow-by-category${buildQuery({ company_id: companyId, ...filters })}`,
  )
}

export function getPaymentMethodMix(companyId: string, filters: BiPeriodFilters = {}) {
  return apiRequest<PaymentMethodMixReport>(
    `/bi/payment-method-mix${buildQuery({ company_id: companyId, ...filters })}`,
  )
}

export function getPowerBiManifest() {
  return apiRequest<PowerBiManifest>(`/bi/powerbi-manifest`)
}

export async function downloadBiCsv(path: string, suggestedFileName: string): Promise<void> {
  const blob = await apiDownloadBlob(path, {
    accept: "text/csv",
    errorMessage: "Falha no download",
  })
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = suggestedFileName.endsWith(".csv") ? suggestedFileName : `${suggestedFileName}.csv`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
