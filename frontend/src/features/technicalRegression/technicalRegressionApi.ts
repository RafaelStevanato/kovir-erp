import { apiRequest } from "../../lib/api"
import type {
  TechnicalRegressionAvailableCompanies,
  TechnicalRegressionDatabaseHealth,
  TechnicalRegressionFinancialIntegrity,
  TechnicalRegressionRules,
  TechnicalRegressionRun,
  TechnicalRegressionSchemaContract,
} from "./types"

function cleanParams(params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return
    query.set(key, String(value))
  })

  const serialized = query.toString()
  return serialized ? `?${serialized}` : ""
}

export async function getTechnicalRegressionRules() {
  return apiRequest<TechnicalRegressionRules>("/technical-regression/rules")
}

export async function getTechnicalRegressionAvailableCompanies(limit = 20) {
  return apiRequest<TechnicalRegressionAvailableCompanies>(
    `/technical-regression/available-companies${cleanParams({ limit })}`,
  )
}

export async function getTechnicalRegressionDatabaseHealth() {
  return apiRequest<TechnicalRegressionDatabaseHealth>("/technical-regression/database-health")
}

export async function getTechnicalRegressionSchemaContract() {
  return apiRequest<TechnicalRegressionSchemaContract>("/technical-regression/schema-contract")
}

export async function getTechnicalRegressionFinancialIntegrity(companyId?: string) {
  return apiRequest<TechnicalRegressionFinancialIntegrity>(
    `/technical-regression/financial-integrity${cleanParams({ company_id: companyId })}`,
  )
}

export async function runTechnicalRegression(params: { companyId?: string; profile?: "quick" | "full" } = {}) {
  return apiRequest<TechnicalRegressionRun>(
    `/technical-regression/run${cleanParams({
      company_id: params.companyId,
      profile: params.profile ?? "quick",
    })}`,
  )
}

