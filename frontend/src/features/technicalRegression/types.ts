export type TechnicalRegressionRules = {
  module: string
  block: string
  name: string
  version: string
  goal: string
  principles: string[]
  profiles: Record<string, string>
  endpoints: string[]
  required_table_groups: Record<string, string[]>
}

export type TechnicalRegressionCompany = {
  id: string
  legal_name: string | null
  trade_name: string | null
  cnpj: string | null
  status: string
  created_at: string
  updated_at: string
  display_name: string
}

export type TechnicalRegressionAvailableCompanies = {
  total_returned: number
  items: TechnicalRegressionCompany[]
  notes: string[]
}

export type TechnicalRegressionDatabaseHealth = {
  status: "PASS" | "FAIL" | "WARN" | string
  database_online: boolean
  database_name: string | null
  schema_name: string | null
  alembic_version: string | null
  table_count: number
  generated_at: string
}

export type TechnicalRegressionSchemaSummary = {
  required_tables: number
  present_required_tables: number
  missing_required_tables: number
  groups_with_missing_tables: string[]
  tables_with_missing_columns: number
}

export type TechnicalRegressionSchemaContract = {
  status: "PASS" | "FAIL" | "WARN" | string
  summary: TechnicalRegressionSchemaSummary
  present_by_group: Record<string, string[]>
  missing_by_group: Record<string, string[]>
  missing_columns: Record<string, string[]>
  notes: string[]
}

export type TechnicalRegressionCheck = {
  code: string
  label: string
  status: "PASS" | "FAIL" | "SKIP" | "WARN" | string
  severity: "critical" | "warning" | string
  count: number
  details: Record<string, unknown>
}

export type TechnicalRegressionSummary = {
  total_checks: number
  passed: number
  failed: number
  skipped: number
}

export type TechnicalRegressionFinancialIntegrity = {
  status: "PASS" | "FAIL" | "WARN" | string
  company: TechnicalRegressionCompany | null
  summary: TechnicalRegressionSummary
  checks: TechnicalRegressionCheck[]
  notes: string[]
}

export type TechnicalRegressionRun = {
  overall_status: "PASS" | "FAIL" | "WARN" | string
  profile: "quick" | "full" | string
  generated_at: string
  company: TechnicalRegressionCompany | null
  database_health: TechnicalRegressionDatabaseHealth
  schema_contract_summary: TechnicalRegressionSchemaSummary
  financial_integrity_summary: TechnicalRegressionSummary
  recommended_gate: {
    can_advance_backend: boolean
    can_start_frontend: boolean
    reason: string
  }
  details: {
    schema_contract: TechnicalRegressionSchemaContract
    financial_integrity: TechnicalRegressionFinancialIntegrity
  }
  next_steps: string[]
}

