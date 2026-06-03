export type CashDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  id_prefixes: Record<string, string>
  tables: string[]
  integrations: string[]
  safety: string[]
}

export type CashSummary = {
  company_id: string
  received_amount: string
  discount_amount: string
  inflow_amount: string
  outflow_amount: string
  net_internal_balance_delta: string
  pending_reconciliation_count: number
  pending_reconciliation_amount: string
  internal_balance_total: string
  financial_account_count: number
  materialized_balance_count: number
}

export type Settlement = {
  id: string
  company_id: string
  direction: string
  settlement_type: string
  financial_title_id: string
  financial_title_reference?: string | null
  financial_title_status?: string | null
  financial_title_installment_number?: number | null
  financial_title_installment_total?: number | null
  financial_title_open_amount?: string | null
  financial_title_paid_amount?: string | null
  participant_id?: string | null
  participant_name?: string | null
  participant_document?: string | null
  financial_account_id: string
  payment_method_id?: string | null
  settlement_date: string
  competency_date?: string | null
  received_amount: string
  discount_amount: string
  interest_amount: string
  penalty_amount: string
  fee_amount: string
  title_settled_amount: string
  movement_amount: string
  source_type: string
  source_id?: string | null
  evidence_reference?: string | null
  notes?: string | null
  status: string
  reversal_of_settlement_id?: string | null
  reversed_at?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type FinancialMovement = {
  id: string
  company_id: string
  financial_account_id: string
  financial_account_name?: string | null
  financial_account_type?: string | null
  financial_account_institution_name?: string | null
  direction: string
  movement_type: string
  movement_date: string
  amount: string
  currency: string
  source_type: string
  source_id: string
  settlement_id?: string | null
  settlement_status?: string | null
  settlement_type?: string | null
  settlement_date?: string | null
  settlement_evidence_reference?: string | null
  payment_method_id?: string | null
  payment_method_name?: string | null
  payment_method_code?: string | null
  financial_title_id?: string | null
  financial_title_reference?: string | null
  financial_title_direction?: string | null
  financial_title_status?: string | null
  financial_title_installment_number?: number | null
  financial_title_installment_total?: number | null
  financial_title_open_amount?: string | null
  financial_title_paid_amount?: string | null
  participant_id?: string | null
  participant_name?: string | null
  participant_document?: string | null
  description?: string | null
  status: string
  reconciliation_status: string
  reversal_of_movement_id?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type FinancialAccountBalance = {
  id: string
  company_id: string
  financial_account_id: string
  current_balance_amount: string
  last_movement_id?: string | null
  updated_at: string
}

export type SettlementCreatePayload = {
  company_id: string
  financial_title_id: string
  financial_account_id: string
  payment_method_id?: string | null
  settlement_date: string
  competency_date?: string | null
  received_amount: string
  discount_amount?: string
  interest_amount?: string
  penalty_amount?: string
  fee_amount?: string
  source_type?: string
  source_id?: string | null
  evidence_reference?: string | null
  notes?: string | null
}

export type ManualMovementCreatePayload = {
  company_id: string
  financial_account_id: string
  direction: "inflow" | "outflow"
  movement_type: "adjustment" | "fee" | "tax" | "other"
  movement_date: string
  amount: string
  description: string
  source_type?: string
  source_id?: string | null
}
