import { getAuthSession, type AuthSession } from "./authSession"
import { isAppViewEnabled } from "./moduleScope"
import type { AppView } from "../layouts/AppShell"

const FINANCIAL_VIEWS: AppView[] = [
  "overview",
  "financial",
  "accountsReceivable",
  "cash",
  "reconciliation",
  "cashFlow",
  "purchasesPayables",
  "managementReports",
]

export function canAccessView(view: AppView, session: AuthSession | null = getAuthSession()): boolean {
  if (!isAppViewEnabled(view)) return false
  if (!session) return false
  if (session.roles.includes("admin")) return true

  if (session.allowedViews.includes(view)) return true
  if (session.permissions.includes(`view.${view}`)) return true

  if (session.roles.includes("finance_operator") || session.roles.includes("finance_manager")) {
    return FINANCIAL_VIEWS.includes(view)
  }

  if (view === "overview") return true
  if (view === "managementReports" && session.permissions.includes("reports.read")) return true
  if (view === "security" && session.permissions.includes("users.manage")) return true

  return false
}
