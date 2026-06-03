export type ReceivableTitle = {
  id: string
  company_id: string
  direction: string
  title_type: string
  source_type: string
  source_id: string
  source_snapshot?: Record<string, unknown> | null
  sale_id?: string | null
  sale_payment_plan_id?: string | null
  participant_id: string
  participant_snapshot: Record<string, unknown>
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

export type ReceivablesSummary = {
  company_id: string
  as_of: string
  by_status: Record<string, { count: number; open_amount: string; net_amount: string; paid_amount: string }>
  total_count: number
  open_count: number
  open_amount: string
  overdue_count: number
  overdue_amount: string
  received_count: number
  received_amount: string
  partially_received_count: number
  partially_received_open_amount: string
  cancelled_count: number
  cancelled_amount: string
  due_next_7_count: number
  due_next_7_amount: string
  due_next_30_count: number
  due_next_30_amount: string
  aging: Record<string, { count: number; amount: string }>
}

export type ReceivablesDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  id_prefix: string
  tables: string[]
  integrations: string[]
  rules: string[]
}

export type ReceivableCreatePayload = {
  company_id: string
  participant_id: string
  title_type?: string
  source_type?: string
  source_id?: string | null
  payment_method_id?: string | null
  payment_method_code?: string | null
  financial_category_id?: string | null
  cost_center_id?: string | null
  expected_financial_account_id?: string | null
  document_reference?: string | null
  installment_number?: number
  installment_total?: number
  issue_date?: string | null
  competency_date?: string | null
  due_date: string
  expected_payment_date?: string | null
  gross_amount: string
  discount_amount?: string
  interest_amount?: string
  penalty_amount?: string
  fee_amount?: string
  fiscal_status?: string
  notes?: string | null
}
