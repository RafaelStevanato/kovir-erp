export type StressRules = {
  module: string
  purpose: string
  security: {
    requires_auth: boolean
    requires_permission: string
    company_scope: string
  }
  generators: string[]
  limits: {
    max_per_generator: number
  }
}

export type StressSummary = {
  company_id: string
  counts: {
    participants: number
    fiscal_classifications: number
    catalog_items: number
    sales: number
    receivables: number
    purchases: number
    payables: number
  }
  notes: string[]
}

export type StressGeneratePayload = {
  participants: number
  fiscal_classifications: number
  products: number
  services: number
  sales: number
  receivables: number
  purchases: number
  confirm_sales: boolean
  confirm_purchases: boolean
}

export type StressGenerateResult = {
  company_id: string
  requested: StressGeneratePayload
  before: StressSummary["counts"]
  after: StressSummary["counts"]
  delta: StressSummary["counts"]
  created: Record<string, unknown>
  notes: string[]
}

