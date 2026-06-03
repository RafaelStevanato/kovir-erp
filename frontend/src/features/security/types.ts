export type LoginResult = {
  access_token: string
  token_type: string
  expires_at: string
  session: {
    id: string
    company_id: string
    issued_at: string
    expires_at: string
  }
  user: {
    id: string
    email: string
    full_name: string
    status: string
    must_change_password: boolean
    last_login_at: string | null
  }
  roles: string[]
  permissions: string[]
  allowed_views: string[]
}

export type SecurityRules = {
  module: string
  purpose: string
  session_duration_minutes: number
  approval_action_key: string
  default_permissions: string[]
  default_roles: string[]
  critical_permissions: Record<string, string>
  all_app_views?: string[]
  financial_app_views?: string[]
}

export type CompanyUserItem = {
  membership: {
    id: string
    company_id: string
    user_id: string
    status: string
    is_primary: boolean
    joined_at: string
  }
  user: {
    id: string
    email: string
    full_name: string
    status: string
    must_change_password: boolean
    last_login_at: string | null
  } | null
  roles: string[]
  permissions: string[]
  allowed_views: string[]
}

export type RoleItem = {
  id: string
  code: string
  name: string
  description: string | null
  is_system: boolean
  permissions?: string[]
  allowed_views?: string[]
}

export type PermissionItem = {
  id: string
  code: string
  name: string
  description: string | null
}

export type ApprovalPolicy = {
  id: string
  company_id: string
  action_key: string
  enabled: boolean
  threshold_amount: string
  currency: string
  required_permission_code: string
  allow_self_approval: boolean
}

export type ApprovalRequest = {
  id: string
  company_id: string
  policy_id: string
  action_key: string
  status: string
  reason: string | null
  requested_by_user_id: string
  requested_amount: string
  currency: string
  target_entity_type: string
  target_entity_id: string
  payload: Record<string, unknown>
  decided_by_user_id: string | null
  decided_at: string | null
  expires_at: string | null
  created_at: string
  updated_at: string
}
