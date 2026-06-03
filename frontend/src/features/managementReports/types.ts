export type ReportPeriod = {
  start_date: string
  end_date: string
}

export type ManagementReportRules = {
  module: string
  name: string
  version: string
  goal: string
  critical_distinctions: string[]
  backend_guarantees: string[]
  endpoints: string[]
}

export type AvailableReportCompany = {
  id: string
  legal_name: string | null
  trade_name: string | null
  cnpj: string | null
  status: string
  tax_regime: string | null
  fiscal_environment: string | null
  created_at: string
  updated_at: string
  display_name: string
}

export type AvailableCompaniesReport = {
  total_returned: number
  items: AvailableReportCompany[]
  notes: string[]
}

export type CompanyContextReport = {
  id: string
  legal_name: string | null
  trade_name: string | null
  cnpj: string | null
  status: string
  tax_regime: string | null
  fiscal_environment: string | null
  uses_accounts_receivable: boolean
  uses_accounts_payable: boolean
  uses_cash_control: boolean
  uses_cost_center: boolean
  uses_chart_of_accounts: boolean
  prepared_for_tax_reform: boolean
  created_at: string
  updated_at: string
  display_name: string
}

export type DirectionSummary = {
  direction: string
  total_titles?: number
  gross_amount?: string
  net_amount?: string
  paid_amount?: string
  open_amount?: string
  active_open_amount?: string
  active_titles?: number
  overdue_titles?: number
  overdue_amount?: string
  titles_without_participant?: number
  titles_without_clear_origin?: number
  total_movements?: number
  amount?: string
  reconciled_amount?: string
  unreconciled_amount?: string
  reconciled_movements?: number
  unreconciled_movements?: number
  total_settlements?: number
  received_amount?: string
  title_settled_amount?: string
  movement_amount?: string
}

export type FinancialAccountBalanceReport = {
  financial_account_id: string
  financial_account_name: string
  account_type: string
  currency: string
  balance_amount: string
}

export type FinancialCycleReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  titles_by_direction: DirectionSummary[]
  settlements_by_direction: DirectionSummary[]
  movements_by_direction: DirectionSummary[]
  financial_account_balances: FinancialAccountBalanceReport[]
  interpretation_rules: string[]
}

export type MvpHealthStatus = "healthy" | "attention" | "blocked" | string

export type MvpHealthReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  reference_date: string
  status: MvpHealthStatus
  score: number
  counts: Record<string, number>
  pendencies: Record<string, number | string>
  score_components: Record<string, number>
  blockers: string[]
  warnings: string[]
  next_backend_priorities: string[]
  calculation_notes: string[]
}

export type HealthIndicatorKey =
  | "participants"
  | "titles"
  | "movements"
  | "sales"
  | "purchases"
  | "reconciliation_matches"
  | "overdue_titles"
  | "titles_without_clear_origin"
  | "titles_without_participant"
  | "unreconciled_movements"
  | "unmatched_bank_statement_lines"

export type HealthIndicatorCell = string | number | boolean | null

export type HealthIndicatorDetailsReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  reference_date: string
  indicator: HealthIndicatorKey
  label: string
  total: number
  columns: string[]
  rows: Array<Record<string, HealthIndicatorCell>>
}

export type BacklogTitleItem = {
  id: string
  direction: string
  title_reference: string
  due_date: string
  status: string
  net_amount?: string
  paid_amount?: string
  open_amount?: string
  participant_name?: string | null
}

export type BacklogMovementItem = {
  id: string
  direction: string
  movement_date: string
  amount: string
  reconciliation_status: string
  description?: string | null
  financial_account_name?: string | null
  participant_name?: string | null
}

export type BacklogStatementLineItem = {
  id: string
  statement_date: string
  description?: string | null
  amount: string
  direction: string
  status: string
  financial_account_name?: string | null
}

export type OperationalBacklogReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  limit: number
  totals: {
    overdue_titles: number
    overdue_titles_amount: string
    titles_without_clear_origin: number
    titles_without_clear_origin_amount: string
    unreconciled_movements: number
    unreconciled_movements_amount: string
    unmatched_bank_statement_lines: number
    unmatched_bank_statement_amount: string
    total_pendencies: number
    is_limited: boolean
  }
  overdue_titles: BacklogTitleItem[]
  titles_without_clear_origin: BacklogTitleItem[]
  unreconciled_movements: BacklogMovementItem[]
  unmatched_bank_statement_lines: BacklogStatementLineItem[]
}

export type TitleReference = {
  id: string
  direction: string
  human_reference: string
  title_name?: string | null
  title_type?: string | null
  document_reference?: string | null
  installment_number?: number | null
  installment_total?: number | null
  status: string
  collection_status?: string | null
  fiscal_status?: string | null
  issue_date?: string | null
  competency_date?: string | null
  due_date: string
  expected_payment_date?: string | null
  net_amount: string
  paid_amount: string
  open_amount: string
  source_type?: string | null
  source_id?: string | null
  sale_id?: string | null
  sale_number_text?: string | null
  payment_method_name?: string | null
  expected_financial_account_name?: string | null
  participant_name?: string | null
  participant_document?: string | null
  participant_type?: string | null
  company_display_name: string
}

export type TitleReferencesReport = {
  company_id: string
  company_display_name: string
  filters: {
    direction?: string | null
    status?: string | null
    search?: string | null
    due_from?: string | null
    due_to?: string | null
    limit: number
    offset: number
    export_all?: boolean
  }
  total: number
  summary: {
    total_count: number
    total_net_amount: string
    total_paid_amount: string
    total_open_amount: string
    active_count: number
    active_open_amount: string
    overdue_count: number
    overdue_open_amount: string
    page_count: number
    has_previous: boolean
    has_next: boolean
    is_export_limited: boolean
  }
  items: TitleReference[]
  notes: string[]
}

export type ReportDateFilters = {
  start_date?: string
  end_date?: string
}

export type TitleReferenceFilters = {
  direction?: string
  status?: string
  search?: string
  due_from?: string
  due_to?: string
  limit?: number
  offset?: number
  export_all?: boolean
}

export type PreparatoryFiscalSaleDocument = {
  sale_id: string
  sale_number_text?: string | null
  status: string
  sale_type: string
  operation_nature: string
  fiscal_status: string
  issue_date?: string | null
  operation_date: string
  participant_name?: string | null
  total_amount: string
  missing_issue_date: boolean
  pending_fiscal_status: boolean
  blocked_fiscal_status: boolean
  cancelled_fiscal_document_status: boolean
}

export type PreparatoryFiscalPurchaseDocument = {
  purchase_id: string
  status: string
  purchase_type: string
  fiscal_status: string
  issue_date?: string | null
  operation_date: string
  participant_name?: string | null
  total_amount: string
  document_type?: string | null
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  missing_issue_date: boolean
  missing_document_number: boolean
  pending_fiscal_status: boolean
  divergent_fiscal_status: boolean
}

export type PreparatoryFiscalTitleDocument = {
  id: string
  direction: string
  title_type?: string | null
  status: string
  fiscal_status: string
  issue_date?: string | null
  due_date: string
  document_reference?: string | null
  source_type?: string | null
  source_id?: string | null
  sale_id?: string | null
  sale_number_text?: string | null
  participant_name?: string | null
  participant_document?: string | null
  net_amount: string
  open_amount: string
  installment_number: number
  installment_total: number
}

export type FiscalDocumentReportItem = {
  id: string
  sale_id: string
  sale_number_text?: string | null
  participant_name?: string | null
  sale_total_amount?: string | null
  document_type: string
  model?: string | null
  serie?: string | null
  number?: string | null
  reference: string
  status: string
  focus_status?: string | null
  access_key?: string | null
  protocol?: string | null
  error_code?: string | null
  error_message?: string | null
  danfe_url?: string | null
  xml_url?: string | null
  issued_at?: string | null
  authorized_at?: string | null
  cancelled_at?: string | null
  created_at: string
  updated_at: string
}

export type PreparatoryFiscalDocumentsReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  limit: number
  export_all: boolean
  summary: {
    pending_sales_documents: number
    pending_purchase_documents: number
    pending_fiscal_titles: number
    pending_sales_amount: string
    pending_purchase_amount: string
    pending_fiscal_open_amount: string
    fiscal_documents_total: number
    fiscal_documents_authorized: number
    fiscal_documents_pending: number
    fiscal_documents_error: number
    fiscal_documents_cancelled: number
    blocking_items: number
    status: "READY" | "ATTENTION" | string
  }
  sales_documents: PreparatoryFiscalSaleDocument[]
  purchase_documents: PreparatoryFiscalPurchaseDocument[]
  title_documents: PreparatoryFiscalTitleDocument[]
  fiscal_documents: FiscalDocumentReportItem[]
  title_fiscal_status: {
    total_titles: number
    pending_fiscal_titles: number
    pending_fiscal_open_amount: string
    pending_fiscal_net_amount: string
  }
  returned_rows: {
    sales_documents: number
    purchase_documents: number
    title_documents: number
    fiscal_documents: number
  }
  required_fields_by_flow: Record<string, string[]>
  notes: string[]
}

export type FinancialCloseChecklistItem = {
  code: string
  label: string
  status: "PASS" | "WARN" | "FAIL" | string
  blocking: boolean
  evidence: Record<string, unknown>
}

export type FinancialCloseMvpReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  generated_at?: string
  reference_date?: string
  close_status: "READY" | "ATTENTION" | "BLOCKED" | string
  can_close_mvp: boolean
  can_close_with_warnings?: boolean
  snapshot: {
    open_receivable_count: number
    open_receivable_amount: string
    open_payable_count: number
    open_payable_amount: string
    overdue_count: number
    overdue_amount: string
    unreconciled_movements: number
    unreconciled_amount: string
    pending_statement_lines: number
    divergent_items: number
    duplicate_balance_rows?: number
    fiscal_preparatory_pending?: number
    fiscal_documents_pending?: number
    fiscal_documents_error?: number
  }
  checklist: FinancialCloseChecklistItem[]
  blocking_issues: string[]
  recommended_actions: string[]
  notes: string[]
}

export type AccountantTitleDetail = {
  id: string
  direction: string
  title_type?: string | null
  status: string
  collection_status: string
  fiscal_status: string
  document_reference?: string | null
  source_type?: string | null
  source_id?: string | null
  sale_id?: string | null
  sale_number_text?: string | null
  participant_name?: string | null
  participant_document?: string | null
  payment_method_name?: string | null
  financial_account_name?: string | null
  issue_date?: string | null
  competency_date?: string | null
  due_date: string
  expected_payment_date?: string | null
  installment_number: number
  installment_total: number
  gross_amount: string
  net_amount: string
  paid_amount: string
  open_amount: string
}

export type AccountantSettlementDetail = {
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
  payment_method_name?: string | null
  received_amount: string
  discount_amount: string
  interest_amount: string
  penalty_amount: string
  fee_amount: string
  title_settled_amount: string
  movement_amount: string
  linked_movement_count: number
  linked_movement_amount: string
  evidence_reference?: string | null
  source_type?: string | null
  source_id?: string | null
}

export type AccountantMovementDetail = {
  id: string
  direction: string
  movement_type: string
  movement_date: string
  amount: string
  currency: string
  status: string
  reconciliation_status: string
  financial_account_name?: string | null
  settlement_id?: string | null
  financial_title_id?: string | null
  title_reference?: string | null
  participant_name?: string | null
  source_type?: string | null
  source_id?: string | null
  description?: string | null
}

export type AccountantStatementLineDetail = {
  id: string
  financial_account_name?: string | null
  statement_import_id?: string | null
  external_id?: string | null
  line_date: string
  posted_at?: string | null
  direction: string
  amount: string
  description?: string | null
  document_number?: string | null
  counterparty_name?: string | null
  counterparty_document?: string | null
  bank_reference?: string | null
  status: string
  match_confidence?: string | null
  matched_amount: string
}

export type AccountantSaleDetail = {
  id: string
  sale_number_text?: string | null
  status: string
  sale_type: string
  origin: string
  operation_nature?: string | null
  fiscal_status: string
  issue_date?: string | null
  operation_date: string
  competency_date?: string | null
  participant_name?: string | null
  participant_document?: string | null
  subtotal_amount: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  receivable_total_amount: string
  invoice_total_amount?: string | null
}

export type AccountantPurchaseDetail = {
  id: string
  status: string
  purchase_type: string
  origin: string
  fiscal_status: string
  issue_date?: string | null
  operation_date: string
  competency_date?: string | null
  participant_name?: string | null
  participant_document?: string | null
  document_type?: string | null
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  subtotal_amount: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  payable_total_amount: string
  invoice_total_amount?: string | null
}

export type AccountantPackReport = {
  company_id: string
  company_display_name: string
  period: ReportPeriod
  snapshot: {
    version: string
    generated_at: string
    snapshot_key: string
    calculation_mode: string
  }
  filters_used: {
    company_id: string
    start_date: string
    end_date: string
    reference_date?: string
    include_details?: boolean
    export_all?: boolean
    limit?: number
  }
  indicators: {
    accounts_receivable_open: { count: number; amount: string; scope?: string }
    accounts_receivable_overdue: { count: number; amount: string; scope?: string }
    accounts_payable_open: { count: number; amount: string; scope?: string }
    accounts_payable_overdue: { count: number; amount: string; scope?: string }
    cash_flow_projected: { inflow_amount: string; outflow_amount: string; net_amount: string; scope?: string }
    cash_flow_realized: { inflow_amount: string; outflow_amount: string; net_amount: string; scope?: string }
    reconciliation_pendencies: { unreconciled_movements: number; unmatched_statement_lines: number }
    fiscal_document_pendencies: {
      pending_sales_documents: number
      pending_purchase_documents: number
      pending_fiscal_titles: number
      pending_fiscal_open_amount: string
      fiscal_documents_pending?: number
      fiscal_documents_error?: number
    }
  }
  operational_ignored: {
    sale_quotes_ignored_count: number
    sale_quotes_ignored_amount: string
    purchase_drafts_ignored_count: number
    purchase_drafts_ignored_amount: string
  }
  consistency_checks: {
    active_settlements: number
    settlement_movement_amount: string
    posted_movement_amount: string
    difference_amount: string
    settlements_without_movement_count: number
    settlements_without_movement_amount: string
    settlements_with_multiple_movements: number
  }
  detail_limits: {
    include_details: boolean
    export_all: boolean
    limit: number
    max_export_rows: number
    is_limited: boolean
    returned_rows: Record<string, number>
  }
  balances_by_account: Array<{
    financial_account_id: string
    financial_account_name: string
    account_type: string
    currency?: string
    balance_amount: string
  }>
  movements_by_period: Array<{
    direction: string
    total_movements: number
    amount: string
    reconciled_amount?: string
    unreconciled_amount?: string
    reconciled_movements: number
    unreconciled_movements: number
  }>
  sales_by_period: Array<{
    sale_type: string
    total_sales: number
    total_amount: string
    receivable_total_amount?: string
    invoice_total_amount?: string
  }>
  purchases_by_period: Array<{
    purchase_type: string
    total_purchases: number
    total_amount: string
    payable_total_amount?: string
    invoice_total_amount?: string
  }>
  open_title_details: AccountantTitleDetail[]
  period_title_details: AccountantTitleDetail[]
  settlement_details: AccountantSettlementDetail[]
  movement_details: AccountantMovementDetail[]
  statement_line_details: AccountantStatementLineDetail[]
  sales_details: AccountantSaleDetail[]
  purchase_details: AccountantPurchaseDetail[]
  ignored_sale_details: AccountantSaleDetail[]
  ignored_purchase_details: AccountantPurchaseDetail[]
  fiscal_pending_details: {
    sales_documents: PreparatoryFiscalSaleDocument[]
    purchase_documents: PreparatoryFiscalPurchaseDocument[]
    title_documents: PreparatoryFiscalTitleDocument[]
    fiscal_documents: FiscalDocumentReportItem[]
  }
  indicator_formulas: Record<string, string>
  notes: string[]
}
