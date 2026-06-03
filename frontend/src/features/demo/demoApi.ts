import { apiRequest } from "../../lib/api"

export type DemoGeneratePayload = {
  sales: number
  purchases: number
}

export type DemoGenerateResult = {
  company_id: string
  company_name_hint: string | null
  status: "PASS" | "FAIL"
  summary: {
    passed: number
    failed: number
    total: number
    inconsistencies: number
  }
  collections_summary: Record<string, number>
  operational_counts?: Record<string, number>
  cash_flow_summary?: Record<string, string | number | null>
  pending_counts?: Record<string, number>
  opening_summary: {
    demo_company_id?: string
    demo_company_name_hint?: string
    sales_count?: number
    stock_balance_count?: number
    inconsistency_count?: number
    receivable_status_counts?: Record<string, number>
    payable_status_counts?: Record<string, number>
    payables_summary?: {
      open_payable_count?: number
      open_payable_amount?: string
      overdue_payable_count?: number
      overdue_payable_amount?: string
    }
  }
  report: unknown
}

export type DemoCompany = {
  id: string
  legal_name: string
  trade_name: string | null
  status: string
  created_at: string | null
  updated_at: string | null
  deleted_at: string | null
}

export type DemoArchiveResult = {
  archived_count: number
  kept_count: number
  archived: DemoCompany[]
  kept: DemoCompany[]
  mode: string
  note: string
}

export async function generateDemoCompany(payload: DemoGeneratePayload) {
  return apiRequest<DemoGenerateResult>("/demo/generate", {
    method: "POST",
    body: payload,
  })
}

export async function archiveOldDemoCompanies(payload: { keep_latest?: number; keep_company_id?: string | null }) {
  return apiRequest<DemoArchiveResult>("/demo/archive-old", {
    method: "POST",
    body: payload,
  })
}

export async function listDemoCompanies() {
  return apiRequest<DemoCompany[]>("/demo/companies")
}
