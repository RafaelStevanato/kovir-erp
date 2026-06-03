import { apiRequest } from "../../lib/api"
import type { BankStatementImport, BankStatementImportPayload, BankStatementLine, OfxStatementImportPayload, MovementCandidate, ReconciliationDiagnostics, ReconciliationMatch, ReconciliationMatchPayload, ReconciliationOverviewEvidence, ReconciliationSummary } from "./types"

type ReconciliationQueryValue = string | number | undefined

function paramsWithCompany(companyId: string, extra?: Record<string, ReconciliationQueryValue>) {
  const params = new URLSearchParams({ company_id: companyId, limit: "200", offset: "0" })
  Object.entries(extra ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value))
  })
  return params.toString()
}

export async function getReconciliationDiagnostics() {
  return apiRequest<ReconciliationDiagnostics>("/reconciliation/diagnostics")
}

export async function getReconciliationSummary(companyId: string, filters?: Record<string, ReconciliationQueryValue>) {
  return apiRequest<ReconciliationSummary>(`/reconciliation/summary?${paramsWithCompany(companyId, filters)}`)
}

export async function getReconciliationOverviewEvidence(companyId: string, filters?: Record<string, ReconciliationQueryValue>) {
  return apiRequest<ReconciliationOverviewEvidence>(
    `/reconciliation/overview-evidence?${paramsWithCompany(companyId, { limit: "5000", ...filters })}`,
  )
}

export async function importBankStatement(payload: BankStatementImportPayload) {
  return apiRequest<{ statement_import: BankStatementImport; lines: BankStatementLine[] }>("/reconciliation/statement-imports", { method: "POST", body: payload })
}

export async function importOfxBankStatement(payload: OfxStatementImportPayload) {
  return apiRequest<{ statement_import: BankStatementImport; lines: BankStatementLine[] }>("/reconciliation/statement-imports/ofx-text", { method: "POST", body: payload })
}

export async function listStatementImports(companyId: string, filters?: Record<string, ReconciliationQueryValue>) {
  return apiRequest<BankStatementImport[]>(`/reconciliation/statement-imports?${paramsWithCompany(companyId, filters)}`)
}

export async function listStatementLines(companyId: string, filters?: Record<string, ReconciliationQueryValue>) {
  return apiRequest<BankStatementLine[]>(`/reconciliation/statement-lines?${paramsWithCompany(companyId, filters)}`)
}

export async function suggestMatches(companyId: string, statementLineId: string) {
  return apiRequest<{ statement_line: BankStatementLine; candidates: MovementCandidate[] }>(`/reconciliation/statement-lines/${encodeURIComponent(statementLineId)}/suggestions?company_id=${encodeURIComponent(companyId)}`)
}

export async function confirmReconciliationMatch(payload: ReconciliationMatchPayload) {
  return apiRequest<{ match: ReconciliationMatch; statement_line: BankStatementLine; financial_movement: MovementCandidate }>("/reconciliation/matches", { method: "POST", body: payload })
}

export async function listReconciliationMatches(companyId: string, filters?: Record<string, ReconciliationQueryValue>) {
  return apiRequest<ReconciliationMatch[]>(`/reconciliation/matches?${paramsWithCompany(companyId, filters)}`)
}

export async function reverseReconciliationMatch(matchId: string, reason: string) {
  return apiRequest<{ match: ReconciliationMatch }>(`/reconciliation/matches/${encodeURIComponent(matchId)}/reverse`, { method: "POST", body: { reason } })
}

export async function ignoreStatementLine(statementLineId: string, reason: string) {
  return apiRequest<BankStatementLine>(`/reconciliation/statement-lines/${encodeURIComponent(statementLineId)}/ignore`, { method: "POST", body: { reason } })
}
