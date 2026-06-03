import { apiRequest } from "../../lib/api"
import type {
  Company,
  CompanyAuditEvent,
  CompanyCreatePayload,
  CompanyDiagnostics,
  CompanyRules,
  CompanyUpdatePayload,
} from "./types"

export async function getCompanies() {
  return apiRequest<Company[]>("/companies")
}

export async function createCompany(payload: CompanyCreatePayload) {
  return apiRequest<Company>("/companies", {
    method: "POST",
    body: payload,
  })
}

export async function getCompany(companyId: string) {
  return apiRequest<Company>(`/companies/${companyId}`)
}

export async function updateCompany(
  companyId: string,
  payload: CompanyUpdatePayload,
) {
  return apiRequest<Company>(`/companies/${companyId}`, {
    method: "PATCH",
    body: payload,
  })
}

export async function getCompanyAuditEvents(companyId: string) {
  return apiRequest<CompanyAuditEvent[]>(`/companies/${companyId}/audit`)
}

export async function getCompanyRules() {
  return apiRequest<CompanyRules>("/system/company-rules")
}

export async function getCompanyDiagnostics() {
  return apiRequest<CompanyDiagnostics>("/system/company-diagnostics")
}