import { apiRequest } from "../../lib/api"
import type {
  StressGeneratePayload,
  StressGenerateResult,
  StressRules,
  StressSummary,
} from "./types"

export function getStressRules() {
  return apiRequest<StressRules>("/stress-tests/rules")
}

export function getStressSummary() {
  return apiRequest<StressSummary>("/stress-tests/summary")
}

export function generateStressData(payload: StressGeneratePayload) {
  return apiRequest<StressGenerateResult>("/stress-tests/generate", {
    method: "POST",
    body: payload,
  })
}

