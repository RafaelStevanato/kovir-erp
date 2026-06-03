export type SaleStatus = "draft" | "confirmed" | "cancelled" | "quote" | "closed" | "paid"

export type SaleType = "product" | "service"

export type SaleOrigin =
  | "manual"
  | "imported"
  | "integration"
  | "marketplace"
  | "unknown"
  | "pdv"

export type SaleOperationNature =
  | "normal_sale"
  | "bonus"
  | "sample"
  | "exchange"
  | "courtesy"
  | "replacement"
  | "other"

export type SaleFiscalStatus =
  | "not_required"
  | "pending_classification"
  | "fiscal_ready"
  | "missing_required_data"
  | "pending_document"
  | "document_generated"
  | "document_cancelled"
  | "blocked"

export type DiscountType = "amount" | "percentage"

export type DiscountCategory =
  | "coupon"
  | "promotion"
  | "commercial_negotiation"
  | "customer_loyalty"
  | "manager_authorization"
  | "damaged_goods"
  | "other"

export type OperationNature = {
  id: string
  company_id: string
  code: SaleOperationNature
  name: string
  sale_type: "both" | SaleType
  description: string | null
  requires_reason: boolean
  affects_revenue: boolean
  affects_accounts_receivable: boolean
  affects_stock: boolean
  requires_fiscal_document: boolean
  default_receivable_behavior: "full" | "zero" | "manual" | string
  default_invoice_behavior: "full" | "zero" | "manual" | string
  status: string
  created_at: string
  updated_at: string
}

export type CatalogItemFiscalRule = {
  id: string
  company_id: string
  catalog_item_id: string
  fiscal_classification_id: string
  operation_nature_id: string
  sale_type: "both" | SaleType
  valid_from: string | null
  valid_to: string | null
  priority: number
  status: string
  notes: string | null
  created_at: string
  updated_at: string
}


export type SaleItemReadiness = {
  company_id: string
  item_id: string
  item_name: string
  item_type: SaleType
  sale_type: SaleType
  can_select: boolean
  blocking_reasons: string[]
  price_ready: boolean
  default_sale_price: string | null
  fiscal_required: boolean
  fiscal_ready: boolean
  fiscal_classification_id: string | null
  fiscal_resolution_source: string
  fiscal_block_reason: string | null
  stock_required: boolean
  stock_ready: boolean
  stock: {
    item_id: string
    item_name: string
    track_stock: boolean
    allow_negative_stock: boolean
    unit: string
    location_id: string
    location_name: string
    available_quantity: string
    total_quantity: string
    can_sell_now: boolean
    availability_status: string
    block_reason: string | null
  } | null
}


export type PaymentMethod = {
  id: string
  company_id: string
  code: PaymentMethodCode
  name: string
  method_type: string
  description: string | null
  requires_reference: boolean
  default_due_behavior: string
  status: string
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type PaymentMethodCode =
  | "pix"
  | "credit_card"
  | "debit_card"
  | "cash"
  | "boleto"
  | "bank_transfer"
  | "store_credit"
  | "other"

export type SalePaymentPlanCreatePayload = {
  payment_method_id?: string | null
  payment_method_code?: PaymentMethodCode | null
  amount: string
  due_date?: string | null
  installments?: number
  notes?: string | null
  metadata?: Record<string, unknown> | null
}

export type SaleItemCreatePayload = {
  item_id: string
  fiscal_classification_id?: string | null
  description?: string | null
  quantity: string
  unit?: string | null
  unit_price?: string | null
  discount_amount: string
  freight_amount: string
  tax_amount: string
}

export type SaleCreatePayload = {
  company_id: string
  establishment_id?: string | null
  participant_id: string | null
  sale_type: SaleType
  origin: SaleOrigin
  operation_nature: SaleOperationNature
  operation_nature_id?: string | null
  operation_nature_reason?: string | null
  issue_date?: string | null
  operation_date?: string | null
  competency_date?: string | null
  discount_amount: string
  discount_type?: DiscountType | null
  discount_percentage?: string | null
  discount_category?: DiscountCategory | null
  discount_reason?: string | null
  freight_amount: string
  tax_amount: string
  notes?: string | null
  payment_plans: SalePaymentPlanCreatePayload[]
  items: SaleItemCreatePayload[]
}

export type SaleUpdatePayload = Partial<Omit<SaleCreatePayload, "company_id">>

export type SaleStatusChangePayload = {
  reason?: string | null
}


export type SalePaymentPlan = {
  id: string
  company_id: string
  sale_id: string
  payment_method_id: string
  payment_method_code: PaymentMethodCode
  payment_method_name: string
  amount: string
  due_date: string | null
  installments: number
  status: "planned" | "generated" | "cancelled"
  notes: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type SaleItem = {
  id: string
  company_id: string
  sale_id: string
  item_id: string
  fiscal_classification_id: string | null
  description: string
  quantity: string
  unit: string
  unit_price: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  item_snapshot: Record<string, unknown>
  fiscal_snapshot: Record<string, unknown> | null
  operation_nature_snapshot: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type Sale = {
  id: string
  company_id: string
  establishment_id: string | null
  participant_id: string | null
  status: SaleStatus
  sale_number_text?: string | null
  paid_number_text?: string | null
  sale_type: SaleType
  origin: SaleOrigin
  operation_nature: SaleOperationNature
  operation_nature_id: string | null
  operation_nature_reason: string | null
  operation_nature_snapshot: Record<string, unknown> | null
  fiscal_status: SaleFiscalStatus
  issue_date: string | null
  operation_date: string
  competency_date: string | null
  subtotal_amount: string
  discount_amount: string
  discount_type: DiscountType
  discount_percentage: string | null
  discount_category: DiscountCategory | null
  discount_reason: string | null
  freight_amount: string
  tax_amount: string
  total_amount: string
  receivable_total_amount: string
  invoice_total_amount: string
  participant_snapshot: Record<string, unknown>
  notes: string | null
  created_at: string
  updated_at: string
  cancelled_at: string | null
  items: SaleItem[]
  payment_plans: SalePaymentPlan[]
}

export type SaleAuditEvent = {
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

export type SaleStatusHistory = {
  id: string
  company_id: string
  sale_id: string
  previous_status: SaleStatus | null
  new_status: SaleStatus
  reason: string | null
  source: string
  actor_id: string | null
  occurred_at: string
}

export type SalesRules = {
  module: string
  entity: string
  id_prefix: string
  item_id_prefix: string
  operation_nature_prefix: string
  fiscal_rule_prefix: string
  status_history_prefix: string
  tables: string[]
  relationships: Record<string, string>
  statuses: SaleStatus[]
  fiscal_statuses: SaleFiscalStatus[]
  sale_types: SaleType[]
  operation_natures: SaleOperationNature[]
  discount_types: DiscountType[]
  discount_categories: DiscountCategory[]
  payment_methods: PaymentMethodCode[]
  origins: SaleOrigin[]
  rules: string[]
}

export type FiscalReadinessIssue = {
  severity: "blocking" | "warning"
  scope: "company" | "participant" | "item" | "operation" | "payment" | "totals" | "stock"
  field: string | null
  message: string
  fix_hint: string | null
  item_index: number | null
}

export type FiscalInvoiceReadiness = {
  sale_id: string
  fiscal_status: "fiscal_ready" | "missing_required_data"
  blocking_count: number
  warning_count: number
  issues: FiscalReadinessIssue[]
  scopes_with_blocking: string[]
  scopes_with_warnings: string[]
  evaluated_at: string
}

export type FiscalDocument = {
  id: string
  company_id: string
  sale_id: string
  document_type: "nfe" | "nfce"
  model: string | null
  serie: string | null
  number: string | null
  reference: string
  status: "pending" | "processing" | "authorized" | "cancelled" | "denied" | "error" | "contingency"
  focus_status: string | null
  access_key: string | null
  protocol: string | null
  error_code: string | null
  error_message: string | null
  danfe_url: string | null
  xml_url: string | null
  issued_at: string | null
  authorized_at: string | null
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

export type SalesDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  tables: string[]
  id_prefix: string
  item_id_prefix: string
  operation_nature_prefix: string
  fiscal_rule_prefix: string
  status_history_prefix: string
  audit_enabled: boolean
  audit_persistence: string
  total_sales: number
  total_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}
