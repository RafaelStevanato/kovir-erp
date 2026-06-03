import type { AppView } from "../layouts/AppShell"

const INTERNAL_MODULES_ENABLED = import.meta.env.VITE_ENABLE_INTERNAL_MODULES === "true"

export const V1_APP_VIEWS: readonly AppView[] = [
  "overview",
  "company",
  "participants",
  "catalog",
  "fiscalClassification",
  "imports",
  "orders",
  "stock",
  "financial",
  "accountsReceivable",
  "cash",
  "reconciliation",
  "cashFlow",
  "purchasesPayables",
  "managementReports",
  "security",
] as const

export const INTERNAL_APP_VIEWS: readonly AppView[] = [
  "biAnalytics",
  "easyManagement",
  "ai",
  "productSales",
  "marketplaces",
  "mercadoPago",
  "technicalRegression",
  "stressTests",
] as const

const V1_APP_VIEW_SET = new Set<AppView>(V1_APP_VIEWS)
const INTERNAL_APP_VIEW_SET = new Set<AppView>(INTERNAL_APP_VIEWS)

export function isInternalModulesEnabled() {
  return INTERNAL_MODULES_ENABLED
}

export function isInternalAppView(view: AppView) {
  return INTERNAL_APP_VIEW_SET.has(view)
}

export function isAppViewEnabled(view: AppView) {
  if (V1_APP_VIEW_SET.has(view)) return true
  return INTERNAL_MODULES_ENABLED && INTERNAL_APP_VIEW_SET.has(view)
}
