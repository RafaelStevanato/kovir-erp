export type CompanyStatus = "draft" | "active" | "inactive" | "blocked"

export type TaxRegime =
  | "simples_nacional"
  | "lucro_presumido"
  | "lucro_real"
  | "mei"
  | "unknown"

export type FiscalEnvironment = "production" | "homologation" | "none"
export type CompanyCrt = "1" | "2" | "3"

export type CompanyAddress = {
  street: string | null
  number: string | null
  complement: string | null
  district: string | null
  city: string | null
  state: string | null
  zip_code: string | null
  ibge_municipality_code: string | null
}

export type CompanyFiscalSettings = {
  tax_regime: TaxRegime
  main_cnae: string | null
  state_registration: string | null
  municipal_registration: string | null
  fiscal_environment: FiscalEnvironment
  uses_fiscal_control: boolean
  prepared_for_tax_reform: boolean
  crt: CompanyCrt | null
  nfe_serie: string
  nfce_serie: string
  focus_nfe_token: string | null
  focus_nfe_token_configured?: boolean
}

export type CompanyFinancialSettings = {
  currency: string
  monthly_closing_day: number
  uses_accounts_receivable: boolean
  uses_accounts_payable: boolean
  uses_cash_control: boolean
  uses_cost_center: boolean
  uses_chart_of_accounts: boolean
}

export type CompanyOperationalSettings = {
  timezone: string
  date_format: string
  money_format: string
  allow_manual_entries: boolean
  allow_imports: boolean
}

export type Company = {
  id: string
  legal_name: string
  trade_name: string | null
  cnpj: string | null
  email: string | null
  phone: string | null
  responsible_name: string | null
  status: CompanyStatus
  address: CompanyAddress
  fiscal_settings: CompanyFiscalSettings
  financial_settings: CompanyFinancialSettings
  operational_settings: CompanyOperationalSettings
  created_at: string | null
  updated_at: string | null
}

export type CompanyCreatePayload = {
  legal_name: string
  trade_name?: string | null
  cnpj?: string | null
  email?: string | null
  phone?: string | null
  responsible_name?: string | null
  status?: CompanyStatus
  address?: Partial<CompanyAddress>
  fiscal_settings?: Partial<CompanyFiscalSettings>
  financial_settings?: Partial<CompanyFinancialSettings>
  operational_settings?: Partial<CompanyOperationalSettings>
}

export type CompanyUpdatePayload = Partial<CompanyCreatePayload>

export type CompanyAuditEvent = {
  id: string
  event_type: string
  entity_type: string
  entity_id: string
  occurred_at: string
  actor_id: string | null
  source: string
  request_id: string | null
  correlation_id: string | null
  ip_address: string | null
  user_agent: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  changes: Record<string, unknown>
  metadata: Record<string, unknown>
}

export type CompanyRules = {
  entity: string
  entity_type: string
  id_prefix: string
  id_format: string
  status: CompanyStatus[]
  tax_regimes: TaxRegime[]
  fiscal_environments: FiscalEnvironment[]
  rules: string[]
}

export type CompanyDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  id_prefix: string
  audit_enabled: boolean
  total_companies: number
  total_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}
