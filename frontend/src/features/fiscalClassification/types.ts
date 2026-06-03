export type FiscalRecordStatus =
  | "draft"
  | "active"
  | "inactive"
  | "blocked"
  | "expired"

export type FiscalProfileType = "product" | "service" | "operation" | "mixed"

export type FiscalAppliesTo = "product" | "service" | "both" | "operation"

export type TaxRegimeScope =
  | "simples_nacional"
  | "lucro_presumido"
  | "lucro_real"
  | "mei"
  | "producer"
  | "foreign"
  | "unknown"
  | "not_applicable"

export type FiscalSourceType =
  | "manual"
  | "accountant"
  | "official_rule"
  | "imported_table"
  | "integration"
  | "legacy"
  | "unknown"

export type FiscalAuditAction = "created" | "updated"

export type FiscalProfile = {
  id: string
  company_id: string
  name: string
  description: string | null
  profile_type: FiscalProfileType
  applies_to: FiscalAppliesTo
  tax_regime: TaxRegimeScope
  status: FiscalRecordStatus
  valid_from: string | null
  valid_to: string | null
  source: FiscalSourceType
  source_reference: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type FiscalClassification = {
  id: string
  company_id: string
  fiscal_profile_id: string | null
  name: string
  description: string | null
  item_type: FiscalAppliesTo
  tax_regime: TaxRegimeScope
  ncm: string | null
  nbs: string | null
  cest: string | null
  ex_tipi: string | null
  origem_mercadoria: string | null
  cfop_default: string | null
  cst_icms: string | null
  cst_pis: string | null
  cst_cofins: string | null
  cst_ibs_cbs: string | null
  cclass_trib: string | null
  subject_to_icms: boolean
  subject_to_iss: boolean
  subject_to_pis_cofins: boolean
  subject_to_ibs_cbs: boolean
  subject_to_is: boolean
  valid_from: string | null
  valid_to: string | null
  status: FiscalRecordStatus
  source: FiscalSourceType
  source_reference: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type FiscalProfileCreatePayload = {
  company_id: string
  name: string
  description?: string | null
  profile_type?: FiscalProfileType
  applies_to?: FiscalAppliesTo
  tax_regime?: TaxRegimeScope
  status?: FiscalRecordStatus
  valid_from?: string | null
  valid_to?: string | null
  source?: FiscalSourceType
  source_reference?: string | null
  notes?: string | null
}

export type FiscalProfileUpdatePayload = Partial<
  Omit<FiscalProfileCreatePayload, "company_id">
>

export type FiscalClassificationCreatePayload = {
  company_id: string
  fiscal_profile_id?: string | null
  name: string
  description?: string | null
  item_type?: FiscalAppliesTo
  tax_regime?: TaxRegimeScope
  ncm?: string | null
  nbs?: string | null
  cest?: string | null
  ex_tipi?: string | null
  origem_mercadoria?: string | null
  cfop_default?: string | null
  cst_icms?: string | null
  cst_pis?: string | null
  cst_cofins?: string | null
  cst_ibs_cbs?: string | null
  cclass_trib?: string | null
  subject_to_icms?: boolean
  subject_to_iss?: boolean
  subject_to_pis_cofins?: boolean
  subject_to_ibs_cbs?: boolean
  subject_to_is?: boolean
  valid_from?: string | null
  valid_to?: string | null
  status?: FiscalRecordStatus
  source?: FiscalSourceType
  source_reference?: string | null
  notes?: string | null
}

export type FiscalClassificationUpdatePayload = Partial<
  Omit<FiscalClassificationCreatePayload, "company_id">
>

export type FiscalAuditEvent = {
  id: string
  entity_id: string
  entity_type: string
  action: FiscalAuditAction
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  changes: Record<string, unknown>
  source: string
  request_id: string | null
  correlation_id: string | null
  occurred_at: string
}

export type FiscalRules = {
  module: string
  block: string
  scope: string
  not_in_scope: string[]
  id_prefixes: Record<string, string>
  profile_types: FiscalProfileType[]
  applies_to: FiscalAppliesTo[]
  tax_regimes: TaxRegimeScope[]
  statuses: FiscalRecordStatus[]
  sources: FiscalSourceType[]
  classification_fields: {
    current_tax_fields: string[]
    tax_reform_fields: string[]
    validity_fields: string[]
  }
  business_rules: string[]
}

export type FiscalDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  total_profiles: number
  total_classifications: number
  total_profile_audit_events: number
  total_classification_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}

export type ApiListResponse<T> = {
  items: T[]
  total: number
  limit?: number
  offset?: number
}
