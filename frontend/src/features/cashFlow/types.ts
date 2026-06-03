export type CashFlowDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  tables_consumed: string[]
  tables_created: string[]
  integrations: string[]
  safety: string[]
}

export type CashFlowHealthFlag = {
  level: "ok" | "info" | "warning" | "risk" | string
  code: string
  message: string
}

export type CashFlowSummary = {
  company_id: string
  start_date: string
  end_date: string
  reference_date?: string
  financial_account_id?: string | null
  basis: "realized" | "projected" | "mixed" | string
  internal_balance_total: string
  financial_account_count: number
  expected_inflow_amount: string
  expected_inflow_count: number
  expected_outflow_amount?: string
  expected_outflow_count?: number
  overdue_receivable_amount: string
  overdue_receivable_count: number
  overdue_payable_amount?: string
  overdue_payable_count?: number
  received_amount: string
  paid_amount?: string
  settlement_discount_amount: string
  settlement_fee_amount: string
  realized_inflow_amount: string
  realized_outflow_amount: string
  realized_net_amount: string
  projected_net_amount: string
  matched_movement_count: number
  matched_movement_amount: string
  pending_reconciliation_count: number
  pending_reconciliation_amount: string
  divergent_reconciliation_count: number
  divergent_reconciliation_amount: string
  statement_inflow_amount: string
  statement_outflow_amount: string
  pending_statement_lines: number
  matched_statement_lines: number
  divergent_statement_lines: number
  health_flags: CashFlowHealthFlag[]
}

export type CashFlowDailyRow = {
  date: string
  expected_inflow_amount: string
  expected_inflow_count: number
  expected_outflow_amount?: string
  expected_outflow_count?: number
  received_amount: string
  paid_amount?: string
  movement_inflow_amount: string
  movement_outflow_amount: string
  realized_net_amount: string
  projected_net_amount: string
  statement_inflow_amount: string
  statement_outflow_amount: string
  pending_statement_lines: number
  unreconciled_movements: number
}

export type CashFlowAccountRow = {
  financial_account_id: string
  financial_account_name: string
  account_type: string
  institution_name?: string | null
  currency: string
  opening_balance_amount: string
  current_balance_amount: string
  period_inflow_amount: string
  period_outflow_amount: string
  period_net_amount: string
  reconciliation_by_status: Record<string, { count: number; amount: string }>
  statement_by_status: Record<string, { count: number; amount: string }>
  statement_by_direction: Record<string, string>
  last_balance_update?: string | null
  status: string
}

export type CashFlowPendingTitle = {
  id: string
  participant_id: string
  document_reference?: string | null
  due_date: string
  open_amount: string
  status: string
  collection_status: string
  source_type: string
  source_id: string
}

export type CashFlowPendingMovement = {
  id: string
  financial_account_id: string
  direction: string
  movement_type: string
  movement_date: string
  amount: string
  source_type: string
  source_id: string
  description?: string | null
  reconciliation_status: string
}

export type CashFlowPendingStatementLine = {
  id: string
  financial_account_id: string
  line_date: string
  direction: string
  amount: string
  description?: string | null
  status: string
  bank_reference?: string | null
}

export type CashFlowDivergentMatch = {
  id: string
  financial_account_id: string
  statement_line_id: string
  financial_movement_id: string
  difference_amount: string
  confirmation_reason?: string | null
  created_at: string
}

export type CashFlowPending = {
  overdue_titles: CashFlowPendingTitle[]
  upcoming_titles: CashFlowPendingTitle[]
  overdue_payables?: CashFlowPendingTitle[]
  upcoming_payables?: CashFlowPendingTitle[]
  unreconciled_movements: CashFlowPendingMovement[]
  unmatched_statement_lines: CashFlowPendingStatementLine[]
  divergent_matches: CashFlowDivergentMatch[]
}

export type CashFlowReconciliationStatus = {
  financial_movements: Record<string, { count: number; amount: string }>
  statement_lines: Record<string, { count: number; amount: string }>
  matches: Record<string, { count: number; difference_amount: string }>
}

export type CashFlowEvidenceAccountBalance = {
  financial_account_id: string
  financial_account_name: string
  account_type: string
  institution_name?: string | null
  currency: string
  opening_balance_amount: string
  current_balance_amount: string
  last_balance_update?: string | null
  status: string
}

export type CashFlowEvidenceTitle = CashFlowPendingTitle & {
  direction: string
  participant_name?: string | null
  participant_document?: string | null
  financial_account_name?: string | null
  issue_date?: string | null
  competency_date?: string | null
  expected_payment_date?: string | null
  installment_number: number
  installment_total: number
  gross_amount: string
  net_amount: string
  paid_amount: string
}

export type CashFlowEvidenceSettlement = {
  id: string
  direction: string
  settlement_type: string
  status: string
  settlement_date: string
  competency_date?: string | null
  financial_title_id: string
  title_reference?: string | null
  participant_name?: string | null
  financial_account_name?: string | null
  received_amount: string
  discount_amount: string
  interest_amount: string
  penalty_amount: string
  fee_amount: string
  title_settled_amount: string
  movement_amount: string
  evidence_reference?: string | null
  source_type?: string | null
  source_id?: string | null
}

export type CashFlowEvidenceMovement = CashFlowPendingMovement & {
  financial_account_name?: string | null
  currency: string
  status: string
  settlement_id?: string | null
  financial_title_id?: string | null
  title_reference?: string | null
  participant_name?: string | null
}

export type CashFlowEvidenceStatementLine = CashFlowPendingStatementLine & {
  financial_account_name?: string | null
  statement_import_id?: string | null
  external_id?: string | null
  posted_at?: string | null
  document_number?: string | null
  counterparty_name?: string | null
  counterparty_document?: string | null
  match_confidence?: string | null
  matched_amount: string
}

export type CashFlowEvidenceMatch = CashFlowDivergentMatch & {
  matched_amount: string
  line_amount: string
  movement_amount: string
  tolerance_amount: string
  status: string
}

export type CashFlowEvidenceDivergentMatch = CashFlowEvidenceMatch

export type CashFlowOverviewEvidence = {
  company_id: string
  start_date: string
  end_date: string
  reference_date: string
  financial_account_id?: string | null
  account_balances: CashFlowEvidenceAccountBalance[]
  expected_receivable_titles: CashFlowEvidenceTitle[]
  expected_payable_titles: CashFlowEvidenceTitle[]
  overdue_receivable_titles: CashFlowEvidenceTitle[]
  overdue_payable_titles: CashFlowEvidenceTitle[]
  settlements: CashFlowEvidenceSettlement[]
  movements: CashFlowEvidenceMovement[]
  statement_lines: CashFlowEvidenceStatementLine[]
  matches: CashFlowEvidenceMatch[]
  divergent_matches: CashFlowEvidenceDivergentMatch[]
}
