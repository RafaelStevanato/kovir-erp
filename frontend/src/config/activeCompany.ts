import { getAuthSession } from "./authSession"

export const FALLBACK_ACTIVE_COMPANY_ID = import.meta.env.VITE_ACTIVE_COMPANY_ID ?? ""

export const ACTIVE_COMPANY_STORAGE_KEY = "kovir.activeCompanyId"
export const ACTIVE_COMPANY_CHANGED_EVENT = "kovir:active-company-changed"
const LEGACY_ACTIVE_COMPANY_STORAGE_KEY = ["flu", "xor.activeCompanyId"].join("")
const LEGACY_ACTIVE_COMPANY_CHANGED_EVENT = ["flu", "xor:active-company-changed"].join("")
const LEGACY_DEMO_COMPANY_PREFIX = "DEMO " + ["FLU", "XOR"].join("")

export type ActiveCompanyCandidate = {
  id: string
  legal_name?: string | null
  trade_name?: string | null
  status?: string | null
}

function getSessionCompanyId() {
  const companyId = getAuthSession()?.companyId?.trim() ?? ""
  return companyId
}

export function getActiveCompanyId() {
  const sessionCompanyId = getSessionCompanyId()
  if (sessionCompanyId) {
    return sessionCompanyId
  }

  if (typeof window === "undefined") {
    return FALLBACK_ACTIVE_COMPANY_ID
  }

  return getStoredActiveCompanyId() || FALLBACK_ACTIVE_COMPANY_ID
}

function getStoredActiveCompanyId() {
  const current = window.localStorage.getItem(ACTIVE_COMPANY_STORAGE_KEY)
  if (current) return current

  const legacy = window.localStorage.getItem(LEGACY_ACTIVE_COMPANY_STORAGE_KEY)
  if (!legacy) return ""

  window.localStorage.setItem(ACTIVE_COMPANY_STORAGE_KEY, legacy)
  window.localStorage.removeItem(LEGACY_ACTIVE_COMPANY_STORAGE_KEY)
  return legacy
}

export function setActiveCompanyId(companyId: string) {
  if (typeof window === "undefined") {
    return
  }

  const sessionCompanyId = getSessionCompanyId()
  const normalizedCompanyId = sessionCompanyId || companyId.trim()
  const previousCompanyId =
    window.localStorage.getItem(ACTIVE_COMPANY_STORAGE_KEY) ||
    window.localStorage.getItem(LEGACY_ACTIVE_COMPANY_STORAGE_KEY) ||
    ""

  if (normalizedCompanyId) {
    window.localStorage.setItem(ACTIVE_COMPANY_STORAGE_KEY, normalizedCompanyId)
  } else {
    window.localStorage.removeItem(ACTIVE_COMPANY_STORAGE_KEY)
  }
  window.localStorage.removeItem(LEGACY_ACTIVE_COMPANY_STORAGE_KEY)

  if (previousCompanyId === normalizedCompanyId) {
    return
  }

  window.dispatchEvent(
    new CustomEvent(ACTIVE_COMPANY_CHANGED_EVENT, {
      detail: { companyId: normalizedCompanyId, previousCompanyId },
    }),
  )
}

export function subscribeActiveCompanyChange(
  listener: (companyId: string, previousCompanyId: string) => void,
) {
  if (typeof window === "undefined") {
    return () => undefined
  }

  const handleCustomEvent = (event: Event) => {
    const detail = (event as CustomEvent<{ companyId?: string; previousCompanyId?: string }>).detail
    listener(detail?.companyId ?? getActiveCompanyId(), detail?.previousCompanyId ?? "")
  }

  const handleStorageEvent = (event: StorageEvent) => {
    if (
      event.key !== ACTIVE_COMPANY_STORAGE_KEY &&
      event.key !== LEGACY_ACTIVE_COMPANY_STORAGE_KEY
    ) {
      return
    }
    listener(event.newValue ?? "", event.oldValue ?? "")
  }

  window.addEventListener(ACTIVE_COMPANY_CHANGED_EVENT, handleCustomEvent)
  window.addEventListener(LEGACY_ACTIVE_COMPANY_CHANGED_EVENT, handleCustomEvent)
  window.addEventListener("storage", handleStorageEvent)

  return () => {
    window.removeEventListener(ACTIVE_COMPANY_CHANGED_EVENT, handleCustomEvent)
    window.removeEventListener(LEGACY_ACTIVE_COMPANY_CHANGED_EVENT, handleCustomEvent)
    window.removeEventListener("storage", handleStorageEvent)
  }
}

export function pickActiveCompanyId(
  companies: ActiveCompanyCandidate[],
  preferredCompanyId = getActiveCompanyId(),
) {
  const sessionCompanyId = getSessionCompanyId()
  if (sessionCompanyId) {
    return sessionCompanyId
  }

  if (companies.some((company) => company.id === preferredCompanyId)) {
    return preferredCompanyId
  }

  return (
    companies.find((company) => company.status === "active")?.id ??
    companies[0]?.id ??
    ""
  )
}

export function getCompanyDisplayName(company: ActiveCompanyCandidate | null | undefined) {
  if (!company) {
    return "Nenhuma empresa ativa"
  }

  return company.trade_name || company.legal_name || company.id
}

export function getCompanySelectLabel(company: ActiveCompanyCandidate) {
  const name = getCompanyDisplayName(company)
  return name
}

export function isDemoCompany(company: ActiveCompanyCandidate | null | undefined): boolean {
  if (!company) return false
  const name = (company.trade_name ?? company.legal_name ?? "").toUpperCase()
  return name.startsWith("DEMO KOVIR") || name.startsWith(LEGACY_DEMO_COMPANY_PREFIX)
}
