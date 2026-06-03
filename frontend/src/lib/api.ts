import { getAuthToken } from "../config/authSession"

export type ApiResponse<T> = {
  success: boolean
  message: string
  data: T
}

export type ApiErrorResponse = {
  success: false
  message: string
  data: null
  errors?: unknown
}

const DEFAULT_API_BASE_URL = "/api"

function normalizeApiBaseUrl(value: unknown): string {
  const rawValue = typeof value === "string" ? value.trim() : ""
  const baseUrl = rawValue || DEFAULT_API_BASE_URL
  if (baseUrl === "/") return ""
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl
}

function normalizeApiPath(path: string): string {
  const cleanPath = path.trim()
  if (!cleanPath) return ""
  return cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL)

export function buildApiUrl(path: string): string {
  const apiPath = normalizeApiPath(path)
  return `${API_BASE_URL}${apiPath}`
}

type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE"

type ApiRequestOptions = {
  method?: HttpMethod
  body?: unknown
  headers?: Record<string, string>
}

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.data = data
  }
}

function buildAuthenticatedHeaders(headers: Record<string, string>): Record<string, string> {
  const authToken = getAuthToken()
  const requestHeaders: Record<string, string> = {
    "x-request-id": crypto.randomUUID(),
    "x-correlation-id": crypto.randomUUID(),
    ...headers,
  }
  if (authToken && !requestHeaders.Authorization) {
    requestHeaders.Authorization = `Bearer ${authToken}`
  }
  return requestHeaders
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<T>> {
  const method = options.method ?? "GET"
  const headers = buildAuthenticatedHeaders({
    "Content-Type": "application/json",
    ...options.headers,
  })

  const response = await fetch(buildApiUrl(path), {
    method,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  let payload: unknown = null

  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) {
    const message = (() => {
      if (typeof payload !== "object" || payload === null) return `Erro HTTP ${response.status}`
      if ("message" in payload && typeof payload.message === "string") return payload.message
      if ("detail" in payload) {
        const detail = (payload as Record<string, unknown>).detail
        if (typeof detail === "string") return detail
        // FastAPI 422: detail is a Pydantic error array.
        if (Array.isArray(detail)) {
          const msgs = detail
            .map((err: unknown) => {
              if (typeof err === "object" && err !== null && "msg" in err) {
                const msg = (err as Record<string, unknown>).msg
                if (typeof msg === "string") {
                  // Pydantic v2 may prefix validation messages with "Value error, ".
                  return msg.replace(/^Value error,\s*/i, "")
                }
              }
              return null
            })
            .filter(Boolean)
          if (msgs.length > 0) return msgs.join(" | ")
        }
      }
      return `Erro HTTP ${response.status}`
    })()

    throw new ApiError(message, response.status, payload)
  }

  return payload as ApiResponse<T>
}

export async function apiDownloadBlob(
  path: string,
  options: { accept?: string; headers?: Record<string, string>; errorMessage?: string } = {},
): Promise<Blob> {
  const response = await fetch(buildApiUrl(path), {
    method: "GET",
    headers: buildAuthenticatedHeaders({
      Accept: options.accept ?? "application/octet-stream",
      ...(options.headers ?? {}),
    }),
  })

  if (!response.ok) {
    throw new Error(`${options.errorMessage ?? "Falha no download"}: ${response.status}`)
  }

  return response.blob()
}
