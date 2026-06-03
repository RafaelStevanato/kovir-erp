export type ParticipantType =
  | "customer"
  | "supplier"
  | "carrier"
  | "service_provider"
  | "marketplace"
  | "gateway"
  | "bank"
  | "other"

export type PersonType = "individual" | "company" | "foreign" | "unknown"

export type ParticipantStatus = "draft" | "active" | "inactive" | "blocked"

export type TaxpayerType = "taxpayer" | "non_taxpayer" | "exempt" | "unknown"

/** Vocabulário controlado para regime tributário. */
export type TaxRegime =
  | "simples_nacional"
  | "mei"
  | "lucro_presumido"
  | "lucro_real"
  | "lucro_arbitrado"
  | "imune"
  | "isento"
  | "nao_contribuinte"
  | "nao_se_aplica"

/** Origem do cadastro — como o participante entrou no sistema. */
export type ParticipantOrigin =
  | "direct"
  | "marketplace"
  | "referral"
  | "import"
  | "organic"
  | "manual"
  | "other"

export type ParticipantAddress = {
  street: string
  number: string
  complement: string | null
  district: string
  city: string
  state: string
  zip_code: string
  country: string
  ibge_municipality_code: string | null
}

export type ParticipantFiscalSettings = {
  taxpayer_type: TaxpayerType
  tax_regime: string | null
  main_cnae: string | null
  state_registration: string | null
  municipal_registration: string | null
  suframa_registration: string | null
  is_foreign: boolean
  fiscal_notes: string | null
}

export type ParticipantFinancialSettings = {
  default_payment_method: string | null
  default_payment_terms: string | null
  bank_name: string | null
  bank_branch: string | null
  bank_account: string | null
  pix_key: string | null
  credit_limit: string | null
  payment_priority: string | null
}

export type Participant = {
  id: string
  company_id: string
  participant_type: ParticipantType
  person_type: PersonType
  name: string
  trade_name: string | null
  document: string | null
  email: string | null
  phone: string | null
  secondary_phone: string | null
  website: string | null
  contact_name: string | null
  contact_phone: string | null
  contact_email: string | null
  origin: ParticipantOrigin | null
  tags: string[] | null
  status: ParticipantStatus
  address: ParticipantAddress | null
  fiscal_settings: ParticipantFiscalSettings | null
  financial_settings: ParticipantFinancialSettings | null
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export type ParticipantListPage = {
  items: Participant[]
  total: number
  limit: number
  offset: number
}

export type ParticipantSummary = {
  total_participants: number
  status_counts: Record<ParticipantStatus, number>
  type_counts: Record<ParticipantType, number>
  quality_counts: {
    total: number
    with_document: number
    with_address: number
    with_contact: number
    operational: number
  }
  total_audit_events: number
}

export type ParticipantCreatePayload = {
  company_id: string
  participant_type: ParticipantType
  person_type: PersonType
  name: string
  trade_name?: string | null
  document?: string | null
  email?: string | null
  phone?: string | null
  secondary_phone?: string | null
  website?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  contact_email?: string | null
  origin?: ParticipantOrigin | null
  tags?: string[]
  status?: ParticipantStatus
  address?: ParticipantAddress | null
  fiscal_settings?: ParticipantFiscalSettings | null
  financial_settings?: ParticipantFinancialSettings | null
  notes?: string | null
}

export type ParticipantUpdatePayload = Partial<{
  company_id: string
  participant_type: ParticipantType
  person_type: PersonType
  name: string
  trade_name: string | null
  document: string | null
  email: string | null
  phone: string | null
  secondary_phone: string | null
  website: string | null
  contact_name: string | null
  contact_phone: string | null
  contact_email: string | null
  origin: ParticipantOrigin | null
  tags: string[]
  status: ParticipantStatus
  address: ParticipantAddress | null
  fiscal_settings: ParticipantFiscalSettings | null
  financial_settings: ParticipantFinancialSettings | null
  notes: string | null
}>

export type ParticipantAuditEvent = {
  id: string
  event_type: string
  entity_type: "participant"
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
  changes: Record<
    string,
    {
      before: unknown
      after: unknown
    }
  >
  metadata: Record<string, unknown>
}

export type ParticipantRules = {
  entity: "participant"
  entity_type: "participant"
  id_prefix: "part"
  id_format: string
  belongs_to: {
    entity: "company"
    id_prefix: "emp"
    field: "company_id"
  }
  participant_types: ParticipantType[]
  person_types: PersonType[]
  statuses: ParticipantStatus[]
  taxpayer_types: TaxpayerType[]
  required_on_create: string[]
  rules: string[]
}

export type ParticipantDiagnostics = {
  module: "participants"
  status: string
  storage: string
  persistence: string
  id_prefix: "part"
  company_dependency: "emp"
  audit_enabled: boolean
  total_participants: number
  total_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}
