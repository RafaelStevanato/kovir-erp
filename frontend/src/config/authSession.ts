const AUTH_STORAGE_KEY = "kovir_auth_session_v1"
const LEGACY_AUTH_STORAGE_KEY = ["flu", "xor_auth_session_v1"].join("")
const AUTH_SESSION_CHANGED_EVENT = "kovir:auth-session-changed"
const LEGACY_AUTH_SESSION_CHANGED_EVENT = ["flu", "xor:auth-session-changed"].join("")

export type AuthSession = {
  accessToken: string
  expiresAt: string
  companyId: string
  userId: string
  fullName: string
  email: string
  roles: string[]
  permissions: string[]
  allowedViews: string[]
}

export function getAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null
  const raw = getStoredAuthSession()
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as AuthSession & { allowedViews?: string[] }
    if (!parsed.accessToken || !parsed.expiresAt) return null
    return {
      ...parsed,
      allowedViews: parsed.allowedViews ?? [],
    }
  } catch {
    return null
  }
}

function getStoredAuthSession() {
  const current = window.sessionStorage.getItem(AUTH_STORAGE_KEY)
  if (current) return current

  const persistedCurrent = window.localStorage.getItem(AUTH_STORAGE_KEY)
  if (persistedCurrent) {
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, persistedCurrent)
    window.localStorage.removeItem(AUTH_STORAGE_KEY)
    return persistedCurrent
  }

  const legacy = window.localStorage.getItem(LEGACY_AUTH_STORAGE_KEY)
  if (!legacy) return null

  window.sessionStorage.setItem(AUTH_STORAGE_KEY, legacy)
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY)
  return legacy
}

function dispatchAuthSessionChanged() {
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_CHANGED_EVENT))
  window.dispatchEvent(new CustomEvent(LEGACY_AUTH_SESSION_CHANGED_EVENT))
}

export function setAuthSession(session: AuthSession) {
  if (typeof window === "undefined") return
  window.sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY)
  dispatchAuthSessionChanged()
}

export function clearAuthSession() {
  if (typeof window === "undefined") return
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY)
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY)
  dispatchAuthSessionChanged()
}

export function getAuthToken(): string | null {
  const session = getAuthSession()
  if (!session) return null
  if (new Date(session.expiresAt).getTime() <= Date.now()) {
    clearAuthSession()
    return null
  }
  return session.accessToken
}

export function subscribeAuthSessionChange(listener: () => void) {
  if (typeof window === "undefined") return () => undefined
  const handler = () => listener()
  window.addEventListener(AUTH_SESSION_CHANGED_EVENT, handler as EventListener)
  window.addEventListener(LEGACY_AUTH_SESSION_CHANGED_EVENT, handler as EventListener)
  return () => {
    window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, handler as EventListener)
    window.removeEventListener(LEGACY_AUTH_SESSION_CHANGED_EVENT, handler as EventListener)
  }
}
