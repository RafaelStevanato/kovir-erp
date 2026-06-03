import { apiRequest } from "../../lib/api"
import type {
  ApprovalPolicy,
  ApprovalRequest,
  CompanyUserItem,
  LoginResult,
  PermissionItem,
  RoleItem,
  SecurityRules,
} from "./types"

export function bootstrapAdmin(payload: {
  company_id: string
  email: string
  full_name: string
  password: string
}) {
  return apiRequest<{
    user: { id: string; email: string; full_name: string }
    company_user: { id: string; company_id: string; user_id: string }
    role_codes: string[]
  }>("/auth/bootstrap-admin", {
    method: "POST",
    body: payload,
  })
}

export function login(payload: { email: string; password: string; company_id: string }) {
  return apiRequest<LoginResult>("/auth/login", {
    method: "POST",
    body: payload,
  })
}

export function logout() {
  return apiRequest<{ revoked: boolean }>("/auth/logout", { method: "POST" })
}

export function getAuthenticatedSession() {
  return apiRequest<{
    user_id: string
    email: string
    full_name: string
    company_id: string
    session_id: string
    roles: string[]
    permissions: string[]
    allowed_views: string[]
  }>("/auth/me")
}

export function getSecurityRules() {
  return apiRequest<SecurityRules>("/security/rules")
}

export function getSecurityDiagnostics() {
  return apiRequest<{
    module: string
    status: string
    users: number
    active_sessions: number
    pending_approvals: number
    actor_company_id: string
    tables: string[]
  }>("/security/diagnostics")
}

export function listRoles() {
  return apiRequest<RoleItem[]>("/security/roles")
}

export function listPermissions() {
  return apiRequest<PermissionItem[]>("/security/permissions")
}

export function listAllowedViews() {
  return apiRequest<Array<{
    view: string
    label: string
    is_financial_default: boolean
    requires_master: boolean
  }>>("/security/allowed-views")
}

export function listCompanyUsers() {
  return apiRequest<CompanyUserItem[]>("/security/company-users")
}

export function createCompanyUser(payload: {
  company_id: string
  email: string
  full_name: string
  password: string
  role_codes?: string[]
  allowed_views?: string[]
}) {
  return apiRequest<{
    user: CompanyUserItem["user"]
    company_user: CompanyUserItem["membership"]
    roles: string[]
    allowed_views: string[]
  }>("/security/company-users", {
    method: "POST",
    body: payload,
  })
}

export function updateCompanyUserRoles(payload: {
  membership_id: string
  role_codes?: string[]
  allowed_views?: string[]
}) {
  return apiRequest<{
    company_user: CompanyUserItem["membership"]
    roles: string[]
    allowed_views: string[]
  }>(`/security/company-users/${payload.membership_id}/roles`, {
    method: "PATCH",
    body: {
      role_codes: payload.role_codes,
      allowed_views: payload.allowed_views,
    },
  })
}

export function getPaymentApprovalPolicy() {
  return apiRequest<ApprovalPolicy>("/security/approval-policy/payment")
}

export function updatePaymentApprovalPolicy(payload: {
  threshold_amount: string
  required_permission_code: string
  allow_self_approval: boolean
}) {
  return apiRequest<ApprovalPolicy>("/security/approval-policy/payment", {
    method: "PUT",
    body: payload,
  })
}

export function listApprovalRequests(params?: { status?: string; limit?: number }) {
  const search = new URLSearchParams()
  if (params?.status) search.set("status", params.status)
  if (params?.limit) search.set("limit", String(params.limit))
  const query = search.toString()
  return apiRequest<ApprovalRequest[]>(`/security/approval-requests${query ? `?${query}` : ""}`)
}

export function createApprovalRequest(payload: {
  financial_title_id: string
  requested_amount: string
  reason: string
  payload_snapshot?: Record<string, unknown>
}) {
  return apiRequest<ApprovalRequest>("/security/approval-requests", {
    method: "POST",
    body: payload,
  })
}

export function decideApprovalRequest(
  approvalRequestId: string,
  payload: { decision: "approved" | "rejected"; reason?: string },
) {
  return apiRequest<ApprovalRequest>(`/security/approval-requests/${approvalRequestId}/decision`, {
    method: "POST",
    body: payload,
  })
}

// ── Senha mestre ────────────────────────────────────────────────────────────

export function getMasterPasswordStatus() {
  return apiRequest<{ configured: boolean }>("/security/master-password/status")
}

export function setMasterPassword(password: string) {
  return apiRequest<{ configured: boolean }>("/security/master-password", {
    method: "POST",
    body: { password },
  })
}
