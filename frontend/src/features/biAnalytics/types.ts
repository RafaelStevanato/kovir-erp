export type Period = { start_date: string; end_date: string; days?: number }

export type WorkingCapitalKpis = {
  company_id: string
  company_display_name: string
  period: Period
  kpis: {
    revenue_amount: string
    sales_count: number
    purchases_amount: string
    purchases_count: number
    gross_profit_amount: string
    gross_margin_percent: string | null
    accounts_receivable_open: string
    accounts_receivable_overdue: string
    accounts_payable_open: string
    accounts_payable_overdue: string
    cash_balance_total: string
    working_capital: string
    current_ratio: string | null
    dso_days: string | null
    dpo_days: string | null
    ccc_days: string | null
    realized_inflow: string
    realized_outflow: string
    realized_net: string
    net_burn_rate_daily: string | null
    cash_runway_days: string | null
  }
  interpretation: Record<string, string>
  data_quality: { uses_purchases_as_cogs_proxy: boolean; note: string }
}

export type AgingBucket = {
  code: string
  label: string
  min_days_overdue: number | null
  max_days_overdue: number | null
  count: number
  amount: string
  share_percent: string
}

export type AgingItem = {
  id: string
  title_reference: string
  due_date: string | null
  days_overdue: number
  open_amount: string
  status: string
  participant_id: string | null
  participant_name: string
  category_name: string
}

export type AgingReport = {
  company_id: string
  company_display_name: string
  direction: "receivable" | "payable"
  as_of: string
  total_count: number
  total_amount: string
  overdue_amount: string
  overdue_share_percent: string
  buckets: AgingBucket[]
  items: AgingItem[]
}

export type ConcentrationItem = {
  rank: number
  participant_id: string | null
  participant_name: string
  participant_type: string | null
  transactions: number
  amount: string
  share_percent: string
  cumulative_amount: string
  cumulative_share_percent: string
  abc_class: "A" | "B" | "C"
}

export type ConcentrationReport = {
  company_id: string
  company_display_name: string
  kind: "customer" | "supplier"
  period: Period
  total_amount: string
  total_participants: number
  top: number
  items: ConcentrationItem[]
  others_summary: { count: number; amount: string; share_percent: string }
  interpretation: Record<string, string>
}

export type DreMonthlyRow = {
  month_key: string
  month_label: string
  year: number
  month: number
  revenue_amount: string
  sales_count: number
  purchases_amount: string
  purchases_count: number
  gross_profit_amount: string
  gross_margin_percent: string | null
  realized_inflow_amount: string
  realized_outflow_amount: string
  realized_net_amount: string
  revenue_mom_percent: string | null
  revenue_yoy_percent: string | null
}

export type DreMonthlyReport = {
  company_id: string
  company_display_name: string
  period: Period
  months: number
  series: DreMonthlyRow[]
}

export type CashFlow13wWeek = {
  week_index: number
  week_start: string
  week_end: string
  expected_inflow_amount: string
  expected_inflow_count: number
  expected_outflow_amount: string
  expected_outflow_count: number
  net_amount: string
  projected_balance_amount: string
  includes_overdue: boolean
}

export type CashFlow13wReport = {
  company_id: string
  company_display_name: string
  financial_account_id?: string | null
  weeks: number
  starting_week: string
  ending_week: string
  opening_balance_amount: string
  overdue_inflow_amount: string
  overdue_outflow_amount: string
  overdue_inflow_count: number
  overdue_outflow_count: number
  weekly: CashFlow13wWeek[]
  interpretation: Record<string, string>
}

export type CashFlowCategoryItem = {
  category_id: string
  category_name: string
  inflow_amount: string
  outflow_amount: string
  net_amount: string
  settlement_count: number
}

export type CashFlowCategoryGroup = {
  cash_flow_group: string
  label: string
  inflow_amount: string
  outflow_amount: string
  net_amount: string
  categories: CashFlowCategoryItem[]
}

export type CashFlowByCategoryReport = {
  company_id: string
  company_display_name: string
  financial_account_id?: string | null
  period: Period
  total_inflow_amount: string
  total_outflow_amount: string
  total_net_amount: string
  groups: CashFlowCategoryGroup[]
  interpretation: Record<string, string>
}

export type PaymentMethodMixItem = {
  method_code: string
  method_name: string
  plan_count: number
  amount: string
  share_percent: string
  installments_count: number
}

export type PaymentMethodMixReport = {
  company_id: string
  company_display_name: string
  period: Period
  total_amount: string
  items: PaymentMethodMixItem[]
}

export type PowerBiManifestRelationship = { from: string; to: string }
export type PowerBiManifestEntry = {
  name: string
  endpoint: string
  grain?: string
  key?: string
}
export type PowerBiManifest = {
  version: string
  generated_at: string
  format: Record<string, string>
  auth: { scheme: string; header_name: string; note: string }
  facts: PowerBiManifestEntry[]
  dimensions: PowerBiManifestEntry[]
  relationships: PowerBiManifestRelationship[]
  powerbi_recommendations: string[]
  power_query_template_m: string
}
