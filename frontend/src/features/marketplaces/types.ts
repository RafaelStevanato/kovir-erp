export type MarketplaceProviderCode = "mercado_pago" | "shopee"

export type MarketplaceProviderType = "payment_gateway" | "marketplace"

export type MarketplaceAccountStatus = "draft" | "active" | "inactive" | "blocked"

export type MarketplaceConnectionStatus =
  | "not_connected"
  | "configured"
  | "connected"
  | "needs_reauth"
  | "error"
  | "disabled"

export type MarketplaceAccount = {
  id: string
  company_id: string
  participant_id: string | null
  provider_code: MarketplaceProviderCode
  provider_name: string
  provider_type: MarketplaceProviderType
  display_name: string
  environment: "sandbox" | "production" | string
  status: MarketplaceAccountStatus | string
  connection_status: MarketplaceConnectionStatus | string
  external_account_id: string | null
  last_sync_at: string | null
  credential_metadata: Record<string, unknown> | null
  settings: Record<string, unknown> | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type MarketplaceSyncRun = {
  id: string
  company_id: string
  marketplace_account_id: string
  sync_type: string
  status: string
  started_at: string | null
  finished_at: string | null
  external_cursor: string | null
  records_found: number
  records_created: number
  records_updated: number
  records_failed: number
  summary: Record<string, unknown> | null
  error: Record<string, unknown> | null
  created_at: string | null
}

export type MarketplaceProvider = {
  provider_code: MarketplaceProviderCode
  provider_name: string
  provider_type: MarketplaceProviderType
  default_environment: string
  future_scopes: string[]
  notes: string
}

export type MarketplacesDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  database_tables: string[]
  future_integrations: string[]
  total_accounts: number
  accounts_by_connection_status: Record<string, number>
  total_sync_runs: number
  total_external_orders: number
  total_payment_events: number
  total_audit_events: number
  technical_notes: string[]
}

export type MarketplacesRules = {
  module: string
  principles: string[]
  prepared_flow: string[]
  providers: MarketplaceProvider[]
}

export type MarketplaceAccountUpdatePayload = {
  participant_id?: string | null
  display_name?: string | null
  environment?: "sandbox" | "production" | string | null
  status?: MarketplaceAccountStatus | string | null
  connection_status?: MarketplaceConnectionStatus | string | null
  external_account_id?: string | null
  credential_metadata?: Record<string, unknown> | null
  settings?: Record<string, unknown> | null
  notes?: string | null
}
