import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const DEFAULT_API_BASE_URL = "/api"
const SENSITIVE_ENV_KEY_PATTERN = /(secret|password|senha|token|private|credential|database|postgres|aws|access[_-]?key)/i
const SENSITIVE_ENV_VALUE_PATTERN = /(postgres(?:ql)?(?:\+\w+)?:\/\/|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----)/i
const FORBIDDEN_PRODUCTION_URL_TOKENS = [
  "localhost",
  "127.0.0.1",
  "0.0.0.0",
  "[::1]",
  "ngrok",
  "trycloudflare.com",
  "loca.lt",
  "localtunnel",
]

function parseAllowedHosts(value: string | undefined) {
  const hosts = (value ?? "localhost,127.0.0.1")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean)

  return hosts.length > 0 ? hosts : ["localhost", "127.0.0.1"]
}

function normalizeApiBaseUrl(value: string | undefined): string {
  const rawValue = value?.trim()
  return rawValue || DEFAULT_API_BASE_URL
}

function validateNoPublicSecrets(env: Record<string, string>) {
  for (const [key, value] of Object.entries(env)) {
    if (!key.startsWith("VITE_")) continue
    if (SENSITIVE_ENV_KEY_PATTERN.test(key)) {
      throw new Error(`Variavel publica proibida no frontend: ${key}`)
    }
    if (SENSITIVE_ENV_VALUE_PATTERN.test(value)) {
      throw new Error(`Valor sensivel detectado em variavel publica do frontend: ${key}`)
    }
  }
}

function validateProductionApiBaseUrl(apiBaseUrl: string) {
  if (apiBaseUrl === DEFAULT_API_BASE_URL) return

  let parsed: URL
  try {
    parsed = new URL(apiBaseUrl)
  } catch {
    throw new Error("VITE_API_BASE_URL em producao deve ser /api ou uma URL HTTPS absoluta.")
  }

  if (parsed.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL absoluto em producao deve usar HTTPS.")
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("VITE_API_BASE_URL em producao nao pode conter credenciais, query string ou fragmento.")
  }

  const normalizedUrl = apiBaseUrl.toLowerCase()
  if (FORBIDDEN_PRODUCTION_URL_TOKENS.some((token) => normalizedUrl.includes(token))) {
    throw new Error("VITE_API_BASE_URL em producao nao pode apontar para host local, tunel ou ambiente temporario.")
  }
}

function validateProductionBuildEnv(env: Record<string, string>) {
  validateNoPublicSecrets(env)
  validateProductionApiBaseUrl(normalizeApiBaseUrl(env.VITE_API_BASE_URL))

  if (env.VITE_ENABLE_INTERNAL_MODULES === "true") {
    throw new Error("VITE_ENABLE_INTERNAL_MODULES nao pode ser true em build de producao.")
  }
  if ((env.VITE_ACTIVE_COMPANY_ID ?? "").trim()) {
    throw new Error("VITE_ACTIVE_COMPANY_ID deve ficar vazio em build de producao.")
  }
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const isProductionBuild = command === "build" && mode === "production"

  if (isProductionBuild) {
    validateProductionBuildEnv(env)
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: "0.0.0.0",
      allowedHosts: parseAllowedHosts(env.VITE_ALLOWED_HOSTS),

      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  }
})
