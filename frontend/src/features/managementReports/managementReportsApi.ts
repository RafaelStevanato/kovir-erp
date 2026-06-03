import { apiRequest } from "../../lib/api"
import type {
  AccountantPackReport,
  AvailableCompaniesReport,
  CompanyContextReport,
  FinancialCloseMvpReport,
  FinancialCycleReport,
  HealthIndicatorDetailsReport,
  HealthIndicatorKey,
  ManagementReportRules,
  MvpHealthReport,
  OperationalBacklogReport,
  PreparatoryFiscalDocumentsReport,
  ReportDateFilters,
  TitleReferenceFilters,
  TitleReferencesReport,
} from "./types"

function cleanParams(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return
    query.set(key, String(value))
  })

  const serialized = query.toString()
  return serialized ? `?${serialized}` : ""
}

export async function getManagementReportRules() {
  return apiRequest<ManagementReportRules>("/management-reports/rules")
}

export async function getAvailableReportCompanies(limit = 20) {
  return apiRequest<AvailableCompaniesReport>(`/management-reports/available-companies${cleanParams({ limit })}`)
}

export async function getManagementCompanyContext(companyId: string) {
  return apiRequest<CompanyContextReport>(`/management-reports/company-context${cleanParams({ company_id: companyId })}`)
}

export async function getFinancialCycleReport(companyId: string, filters: ReportDateFilters = {}) {
  return apiRequest<FinancialCycleReport>(
    `/management-reports/financial-cycle${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
    })}`,
  )
}

export async function getMvpHealthReport(companyId: string, filters: ReportDateFilters = {}) {
  return apiRequest<MvpHealthReport>(
    `/management-reports/mvp-health${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
    })}`,
  )
}

export async function getHealthIndicatorDetailsReport(
  companyId: string,
  indicator: HealthIndicatorKey,
  filters: ReportDateFilters = {},
) {
  return apiRequest<HealthIndicatorDetailsReport>(
    `/management-reports/health-indicator-details${cleanParams({
      company_id: companyId,
      indicator,
      start_date: filters.start_date,
      end_date: filters.end_date,
    })}`,
  )
}

export async function getOperationalBacklogReport(
  companyId: string,
  filters: ReportDateFilters & { limit?: number } = {},
) {
  return apiRequest<OperationalBacklogReport>(
    `/management-reports/backlog${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
      limit: filters.limit,
    })}`,
  )
}

export async function getTitleReferencesReport(companyId: string, filters: TitleReferenceFilters = {}) {
  return apiRequest<TitleReferencesReport>(
    `/management-reports/title-references${cleanParams({
      company_id: companyId,
      direction: filters.direction,
      status: filters.status,
      search: filters.search,
      due_from: filters.due_from,
      due_to: filters.due_to,
      limit: filters.limit,
      offset: filters.offset,
      export_all: filters.export_all,
    })}`,
  )
}

export async function getPreparatoryFiscalDocumentsReport(
  companyId: string,
  filters: ReportDateFilters & { limit?: number; export_all?: boolean } = {},
) {
  return apiRequest<PreparatoryFiscalDocumentsReport>(
    `/management-reports/preparatory-fiscal-documents${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
      limit: filters.limit,
      export_all: filters.export_all,
    })}`,
  )
}

export async function getFinancialCloseMvpReport(companyId: string, filters: ReportDateFilters = {}) {
  return apiRequest<FinancialCloseMvpReport>(
    `/management-reports/financial-close-mvp${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
    })}`,
  )
}

export async function getAccountantPackReport(companyId: string, filters: ReportDateFilters & { include_details?: boolean; export_all?: boolean; limit?: number } = {}) {
  return apiRequest<AccountantPackReport>(
    `/management-reports/accountant-pack${cleanParams({
      company_id: companyId,
      start_date: filters.start_date,
      end_date: filters.end_date,
      include_details: filters.include_details,
      export_all: filters.export_all,
      limit: filters.limit,
    })}`,
  )
}
