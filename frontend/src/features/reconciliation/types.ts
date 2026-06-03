export type ReconciliationDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  id_prefixes: Record<string, string>
  tables: string[]
  integrations: string[]
  safety: string[]
}

export type ReconciliationSummary = {
  company_id: string
  financial_account_id?: string | null
  pending_statement_lines: number
  pending_statement_lines_amount: string
  matched_statement_lines: number
  matched_statement_lines_amount: string
  divergent_statement_lines: number
  divergent_statement_lines_amount: string
  ignored_statement_lines: number
  ignored_statement_lines_amount: string
  pending_financial_movements: number
  pending_financial_movements_amount: string
  divergent_financial_movements: number
  divergent_financial_movements_amount: string
  confirmed_matches: number
  confirmed_matches_amount: string
  confirmed_matches_difference_amount: string
}

export type BankStatementImport = {
  id: string
  company_id: string
  financial_account_id: string
  source_type: string
  source_id?: string | null
  file_name?: string | null
  statement_start_date?: string | null
  statement_end_date?: string | null
  opening_balance_amount?: string | null
  closing_balance_amount?: string | null
  line_count: number
  total_inflow_amount: string
  total_outflow_amount: string
  status: string
  notes?: string | null
  created_at: string
  updated_at: string
}

export type BankStatementLine = {
  id: string
  company_id: string
  financial_account_id: string
  statement_import_id?: string | null
  external_id?: string | null
  line_date: string
  direction: "inflow" | "outflow"
  amount: string
  description?: string | null
  document_number?: string | null
  counterparty_name?: string | null
  bank_reference?: string | null
  status: string
  match_confidence?: string | null
  matched_amount: string
  ignored_reason?: string | null
  created_at: string
  updated_at: string
}

export type ReconciliationMatch = {
  id: string
  company_id: string
  financial_account_id: string
  statement_line_id: string
  financial_movement_id: string
  match_type: string
  matched_amount: string
  line_amount: string
  movement_amount: string
  difference_amount: string
  tolerance_amount: string
  status: string
  confirmation_reason?: string | null
  reversed_reason?: string | null
  confirmed_at?: string | null
  reversed_at?: string | null
  created_at: string
  updated_at: string
}

export type MovementCandidate = {
  id: string
  financial_account_id: string
  direction: string
  movement_type: string
  movement_date: string
  amount: string
  source_type: string
  source_id: string
  settlement_id?: string | null
  financial_title_id?: string | null
  participant_id?: string | null
  description?: string | null
  status: string
  reconciliation_status: string
  score?: number
  reason?: string
}

export type StatementLinePayload = {
  external_id?: string | null
  line_date: string
  direction: "inflow" | "outflow"
  amount: string
  description?: string | null
  document_number?: string | null
  counterparty_name?: string | null
  bank_reference?: string | null
}

export type BankStatementImportPayload = {
  company_id: string
  financial_account_id: string
  source_type?: string
  source_id?: string | null
  file_name?: string | null
  statement_start_date?: string | null
  statement_end_date?: string | null
  opening_balance_amount?: string | null
  closing_balance_amount?: string | null
  notes?: string | null
  lines: StatementLinePayload[]
}

export type ReconciliationMatchPayload = {
  company_id: string
  statement_line_id: string
  financial_movement_id: string
  match_type?: "manual" | "exact" | "suggested" | "forced"
  tolerance_amount?: string
  allow_difference?: boolean
  confirmation_reason?: string | null
}

export type OfxStatementImportPayload = {
  company_id: string
  financial_account_id: string
  file_name?: string | null
  source_id?: string | null
  notes?: string | null
  ofx_content: string
}

export type ReconciliationOverviewEvidence = {
  company_id: string
  financial_account_id?: string | null
  summary: ReconciliationSummary
  pending_statement_lines: BankStatementLine[]
  divergent_statement_lines: BankStatementLine[]
  ignored_statement_lines: BankStatementLine[]
  pending_financial_movements: MovementCandidate[]
  divergent_financial_movements: MovementCandidate[]
  confirmed_matches: ReconciliationMatch[]
}
