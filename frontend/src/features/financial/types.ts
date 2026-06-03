export type FinancialStatus = "draft" | "active" | "inactive" | "blocked" | "archived"

export type ChartAccount = {
  id: string
  company_id: string
  code: string
  name: string
  account_type: string
  parent_id?: string | null
  is_analytical: boolean
  normal_balance?: string | null
  accepts_entries: boolean
  status: FinancialStatus | string
  notes?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type FinancialCategory = {
  id: string
  company_id: string
  code?: string | null
  name: string
  category_type: string
  parent_id?: string | null
  chart_account_id?: string | null
  cash_flow_group?: string | null
  affects_cash_flow: boolean
  requires_cost_center: boolean
  status: FinancialStatus | string
  notes?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type CostCenter = {
  id: string
  company_id: string
  code: string
  name: string
  center_type: string
  parent_id?: string | null
  is_analytical: boolean
  responsible_name?: string | null
  monthly_budget_amount?: string | null
  status: FinancialStatus | string
  notes?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type FinancialAccount = {
  id: string
  company_id: string
  name: string
  account_type: string
  institution_name?: string | null
  branch_number?: string | null
  account_number?: string | null
  account_digit?: string | null
  pix_key?: string | null
  pix_key_type?: string | null
  currency: string
  opening_balance_amount: string
  is_default_receivable: boolean
  is_default_payable: boolean
  status: FinancialStatus | string
  notes?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PaymentTerm = {
  id: string
  company_id: string
  name: string
  term_type: string
  installments: number
  first_due_days: number
  interval_days: number
  generate_on_sale: boolean
  status: FinancialStatus | string
  notes?: string | null
  metadata?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type FinancialDiagnostics = {
  module: string
  status: string
  storage: string
  persistence: string
  tables: string[]
  integration_role: string
  records_count?: Record<string, number>
  active_records_count?: Record<string, number>
}

export type FinancialPeriodClosure = {
  id: string
  company_id: string
  start_date: string
  end_date: string
  status: string
  reason?: string | null
  metadata?: Record<string, unknown>
  created_by_user_id?: string | null
  deactivated_by_user_id?: string | null
  deactivated_at?: string | null
  created_at: string
  updated_at: string
}

export type ChartAccountCreatePayload = {
  company_id: string
  code: string
  name: string
  account_type: string
  parent_id?: string | null
  is_analytical?: boolean
  normal_balance?: string | null
  accepts_entries?: boolean
  status?: string
  notes?: string | null
}

export type ChartAccountUpdatePayload = {
  code?: string
  name?: string
  account_type?: string
  parent_id?: string | null
  is_analytical?: boolean
  normal_balance?: string | null
  accepts_entries?: boolean
  status?: string
  notes?: string | null
}

export type FinancialCategoryCreatePayload = {
  company_id: string
  code?: string | null
  name: string
  category_type: string
  parent_id?: string | null
  chart_account_id?: string | null
  cash_flow_group?: string | null
  affects_cash_flow?: boolean
  requires_cost_center?: boolean
  status?: string
  notes?: string | null
}

export type FinancialCategoryUpdatePayload = {
  code?: string | null
  name?: string
  category_type?: string
  parent_id?: string | null
  chart_account_id?: string | null
  cash_flow_group?: string | null
  affects_cash_flow?: boolean
  requires_cost_center?: boolean
  status?: string
  notes?: string | null
}

export type CostCenterCreatePayload = {
  company_id: string
  code: string
  name: string
  center_type: string
  parent_id?: string | null
  is_analytical?: boolean
  responsible_name?: string | null
  monthly_budget_amount?: string | null
  status?: string
  notes?: string | null
}

export type CostCenterUpdatePayload = {
  code?: string
  name?: string
  center_type?: string
  parent_id?: string | null
  is_analytical?: boolean
  responsible_name?: string | null
  monthly_budget_amount?: string | null
  status?: string
  notes?: string | null
}

export type FinancialAccountCreatePayload = {
  company_id: string
  name: string
  account_type: string
  institution_name?: string | null
  branch_number?: string | null
  account_number?: string | null
  account_digit?: string | null
  pix_key?: string | null
  pix_key_type?: string | null
  currency?: string
  opening_balance_amount?: string
  is_default_receivable?: boolean
  is_default_payable?: boolean
  status?: string
  notes?: string | null
}

export type FinancialAccountUpdatePayload = {
  name?: string
  account_type?: string
  institution_name?: string | null
  branch_number?: string | null
  account_number?: string | null
  account_digit?: string | null
  pix_key?: string | null
  pix_key_type?: string | null
  currency?: string
  opening_balance_amount?: string
  is_default_receivable?: boolean
  is_default_payable?: boolean
  status?: string
  notes?: string | null
}

export type PaymentTermCreatePayload = {
  company_id: string
  name: string
  term_type: string
  installments: number
  first_due_days: number
  interval_days: number
  generate_on_sale?: boolean
  status?: string
  notes?: string | null
}

export type PaymentTermUpdatePayload = {
  name?: string
  term_type?: string
  installments?: number
  first_due_days?: number
  interval_days?: number
  generate_on_sale?: boolean
  status?: string
  notes?: string | null
}
