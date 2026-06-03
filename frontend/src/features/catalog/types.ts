export type CatalogItemType = "product" | "service"

export type CatalogItemStatus = "draft" | "active" | "inactive" | "blocked"

export type CatalogItemOrigin =
  | "manual"
  | "imported"
  | "integration"
  | "fiscal_document"
  | "unknown"

export type CatalogSearchScope = "all" | "name" | "sku" | "barcode" | "id"
export type CatalogStockFilter = "tracked" | "not_tracked"
export type CatalogFiscalFilter = "with_ncm" | "with_nbs" | "without_classification"

export type CatalogItemFinancialSettings = {
  default_sale_price: string | null
  default_cost_price: string | null
  allow_price_override: boolean
  default_revenue_account_id: string | null
  default_expense_account_id: string | null
  default_cost_center_id: string | null
}

export type CatalogItemFiscalSettings = {
  ncm: string | null
  nbs: string | null
  cest: string | null
  cfop_default: string | null
  cst_icms: string | null
  cst_pis: string | null
  cst_cofins: string | null
  cst_ibs_cbs: string | null
  cclass_trib: string | null
  fiscal_classification_id?: string | null
  fiscal_classification_name?: string | null
  fiscal_tax_regime?: string | null
  subject_to_tax: boolean
  subject_to_icms?: boolean | null
  subject_to_iss?: boolean | null
  subject_to_pis_cofins?: boolean | null
  subject_to_ibs_cbs?: boolean | null
  subject_to_is?: boolean | null
  fiscal_source?: string | null
  fiscal_source_reference?: string | null
  fiscal_notes: string | null
}

export type CatalogItemInventorySettings = {
  track_stock: boolean
  stock_unit: string | null
  minimum_stock: string | null
  allow_negative_stock: boolean
}

export type CatalogItem = {
  id: string
  company_id: string
  item_type: CatalogItemType
  name: string
  description: string | null
  sku: string | null
  barcode: string | null
  unit: string
  status: CatalogItemStatus
  origin: CatalogItemOrigin
  brand: string | null
  category: string | null
  financial_settings: CatalogItemFinancialSettings | null
  fiscal_settings: CatalogItemFiscalSettings | null
  inventory_settings: CatalogItemInventorySettings | null
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export type CatalogItemsPage = {
  items: CatalogItem[]
  total: number
  limit: number
  offset: number
}

export type CatalogSummary = {
  total_items: number
  product_count: number
  service_count: number
  active_count: number
  without_sale_price: number
  without_cost_price: number
  without_fiscal_code: number
  without_category: number
  stock_tracked: number
  ready_for_operation: number
}

export type CatalogItemCreatePayload = {
  company_id: string
  item_type: CatalogItemType
  name: string
  description: string | null
  sku: string | null
  barcode: string | null
  unit: string
  status: CatalogItemStatus
  origin: CatalogItemOrigin
  brand: string | null
  category: string | null
  financial_settings: CatalogItemFinancialSettings
  fiscal_settings: CatalogItemFiscalSettings
  inventory_settings: CatalogItemInventorySettings
  notes: string | null
}

export type CatalogItemUpdatePayload = Partial<
  Omit<CatalogItemCreatePayload, "company_id">
>

export type CatalogItemAuditEvent = {
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

export type CatalogRules = {
  entity: string
  entity_type: string
  module: string
  id_prefix: string
  id_format: string
  belongs_to: {
    entity: string
    id_prefix: string
    field: string
  }
  item_types: CatalogItemType[]
  statuses: CatalogItemStatus[]
  origins: CatalogItemOrigin[]
  required_on_create: string[]
  rules: string[]
}

export type CatalogDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  id_prefix: string
  company_dependency: string
  audit_enabled: boolean
  total_items: number
  total_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}
