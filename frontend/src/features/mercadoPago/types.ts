export type MercadoPagoAccount = {
  id: string
  company_id: string
  participant_id: string | null
  marketplace_account_id: string | null
  display_name: string
  environment: "sandbox" | "production" | string
  status: string
  connection_status: string
  external_user_id: string | null
  collector_id: string | null
  application_id: string | null
  public_key_fingerprint: string | null
  credentials_status: string
  webhook_status: string
  last_healthcheck_at: string | null
  last_sync_at: string | null
  credential_metadata: Record<string, unknown> | null
  webhook_settings: Record<string, unknown> | null
  payment_settings: Record<string, unknown> | null
  reconciliation_settings: Record<string, unknown> | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type MercadoPagoDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  integration_status: string
  database_tables: string[]
  total_accounts: number
  accounts_by_connection_status: Record<string, number>
  total_oauth_states: number
  total_webhook_events: number
  total_checkout_preferences: number
  total_payments: number
  total_releases: number
  total_refunds: number
  total_chargebacks: number
  total_audit_events: number
  technical_notes: string[]
}

export type MercadoPagoRules = {
  module: string
  principles: string[]
  prepared_flow: string[]
  future_api_surfaces: string[]
}

export type MercadoPagoGenericRow = Record<string, unknown>
