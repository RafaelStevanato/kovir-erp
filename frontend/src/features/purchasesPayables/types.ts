export type PurchaseItem = {
  id: string
  company_id: string
  purchase_id: string
  item_id?: string | null
  fiscal_classification_id?: string | null
  description: string
  quantity: string
  unit: string
  unit_cost: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  item_snapshot?: Record<string, unknown> | null
  fiscal_snapshot?: Record<string, unknown> | null
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type Purchase = {
  id: string
  company_id: string
  establishment_id?: string | null
  participant_id: string
  status: string
  purchase_type: string
  origin: string
  operation_nature_id?: string | null
  fiscal_status: string
  issue_date?: string | null
  operation_date?: string | null
  competency_date?: string | null
  subtotal_amount: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  payable_total_amount: string
  invoice_total_amount?: string | null
  financial_category_id?: string | null
  cost_center_id?: string | null
  expected_financial_account_id?: string | null
  document_type?: string | null
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  participant_snapshot?: Record<string, unknown> | null
  document_snapshot?: Record<string, unknown> | null
  metadata?: Record<string, unknown> | null
  notes?: string | null
  created_at: string
  updated_at: string
  confirmed_at?: string | null
  cancelled_at?: string | null
  items?: PurchaseItem[]
}

export type PayableTitle = {
  id: string
  company_id: string
  direction: string
  title_type: string
  source_type: string
  source_id: string
  source_snapshot?: Record<string, unknown> | null
  purchase_id?: string | null
  participant_id: string
  participant_snapshot?: Record<string, unknown> | null
  payment_method_id?: string | null
  payment_method_code?: string | null
  payment_method_name?: string | null
  financial_category_id?: string | null
  cost_center_id?: string | null
  expected_financial_account_id?: string | null
  document_reference?: string | null
  installment_number: number
  installment_total: number
  issue_date?: string | null
  competency_date?: string | null
  due_date: string
  expected_payment_date?: string | null
  gross_amount: string
  discount_amount: string
  interest_amount: string
  penalty_amount: string
  fee_amount: string
  net_amount: string
  paid_amount: string
  open_amount: string
  status: string
  collection_status: string
  fiscal_status: string
  notes?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
  cancelled_at?: string | null
}

export type PurchasesPayablesSummary = {
  company_id: string
  purchases_by_status: Record<string, { count: number; total_amount: string }>
  payables_by_status: Record<string, { count: number; open_amount: string; net_amount: string; paid_amount?: string }>
  open_payable_count: number
  open_payable_amount: string
  overdue_payable_count: number
  overdue_payable_amount: string
  paid_payable_count?: number
  paid_payable_amount?: string
}

export type PurchasesPayablesOverviewEvidence = {
  company_id: string
  summary: PurchasesPayablesSummary
  open_payables: PayableTitle[]
  overdue_payables: PayableTitle[]
  paid_payables: PayableTitle[]
  draft_purchases: Purchase[]
  confirmed_purchases: Purchase[]
}

export type PurchasesPayablesDiagnostics = {
  module: string
  status: string
  storage: string
  tables_created: string[]
  tables_consumed: string[]
  integrations: string[]
  safety: string[]
}

export type PurchaseCreatePayload = {
  company_id: string
  participant_id: string
  purchase_type?: string
  origin?: string
  fiscal_status?: string
  issue_date?: string | null
  competency_date?: string | null
  financial_category_id?: string | null
  cost_center_id?: string | null
  expected_financial_account_id?: string | null
  document_type?: string | null
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  invoice_total_amount?: string | null
  notes?: string | null
  items: Array<{
    item_id?: string | null
    fiscal_classification_id?: string | null
    description: string
    quantity: string
    unit?: string
    unit_cost: string
    discount_amount?: string
    freight_amount?: string
    tax_amount?: string
  }>
}

export type PurchaseConfirmPayload = {
  reason?: string | null
  installments: Array<{
    due_date: string
    amount: string
    expected_payment_date?: string | null
    expected_financial_account_id?: string | null
    payment_method_id?: string | null
    payment_method_code?: string | null
    document_reference?: string | null
    notes?: string | null
  }>
}

export type PurchaseCreateAndConfirmPayload = {
  purchase: PurchaseCreatePayload
  confirmation: PurchaseConfirmPayload
}

export type PayablePaymentPayload = {
  company_id: string
  financial_title_id: string
  financial_account_id: string
  payment_method_id?: string | null
  payment_date: string
  competency_date?: string | null
  paid_amount: string
  discount_amount?: string
  interest_amount?: string
  penalty_amount?: string
  fee_amount?: string
  source_type?: string
  source_id?: string | null
  approval_request_id?: string | null
  evidence_reference?: string | null
  notes?: string | null
}
