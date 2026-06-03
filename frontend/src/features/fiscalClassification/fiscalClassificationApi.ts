import { apiRequest } from "../../lib/api"
import type {
  ApiListResponse,
  FiscalAppliesTo,
  FiscalAuditEvent,
  FiscalClassification,
  FiscalClassificationCreatePayload,
  FiscalClassificationUpdatePayload,
  FiscalDiagnostics,
  FiscalProfile,
  FiscalProfileCreatePayload,
  FiscalProfileType,
  FiscalProfileUpdatePayload,
  FiscalRecordStatus,
  FiscalRules,
  TaxRegimeScope,
} from "./types"

export type ListFiscalProfilesParams = {
  company_id?: string
  status_filter?: FiscalRecordStatus
  profile_type?: FiscalProfileType
  applies_to?: FiscalAppliesTo
  tax_regime?: TaxRegimeScope
  search?: string
  limit?: number
  offset?: number
}

export type ListFiscalClassificationsParams = {
  company_id?: string
  status_filter?: FiscalRecordStatus
  item_type?: FiscalAppliesTo
  tax_regime?: TaxRegimeScope
  ncm?: string
  nbs?: string
  cfop?: string
  cst_ibs_cbs?: string
  cclass_trib?: string
  subject_to_ibs_cbs?: boolean
  subject_to_is?: boolean
  valid_on?: string
  validity_filter?: "current" | "future" | "expired"
  search?: string
  limit?: number
  offset?: number
}

function buildQueryString(params?: Record<string, unknown>) {
  if (!params) {
    return ""
  }

  const searchParams = new URLSearchParams()

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return
    }

    searchParams.set(key, String(value))
  })

  const queryString = searchParams.toString()

  return queryString ? `?${queryString}` : ""
}

export function getFiscalProfiles(params?: ListFiscalProfilesParams) {
  return apiRequest<ApiListResponse<FiscalProfile>>(
    `/fiscal/profiles${buildQueryString(params)}`,
  )
}

export function createFiscalProfile(payload: FiscalProfileCreatePayload) {
  return apiRequest<FiscalProfile>("/fiscal/profiles", {
    method: "POST",
    body: payload,
  })
}

export function getFiscalProfile(profileId: string) {
  return apiRequest<FiscalProfile>(`/fiscal/profiles/${profileId}`)
}

export function updateFiscalProfile(
  profileId: string,
  payload: FiscalProfileUpdatePayload,
) {
  return apiRequest<FiscalProfile>(`/fiscal/profiles/${profileId}`, {
    method: "PATCH",
    body: payload,
  })
}

export function getFiscalProfileAudit(profileId: string) {
  return apiRequest<ApiListResponse<FiscalAuditEvent>>(
    `/fiscal/profiles/${profileId}/audit`,
  )
}

export function getFiscalClassifications(
  params?: ListFiscalClassificationsParams,
) {
  return apiRequest<ApiListResponse<FiscalClassification>>(
    `/fiscal/classifications${buildQueryString(params)}`,
  )
}

export function createFiscalClassification(
  payload: FiscalClassificationCreatePayload,
) {
  return apiRequest<FiscalClassification>("/fiscal/classifications", {
    method: "POST",
    body: payload,
  })
}

export function getFiscalClassification(classificationId: string) {
  return apiRequest<FiscalClassification>(
    `/fiscal/classifications/${classificationId}`,
  )
}

export function updateFiscalClassification(
  classificationId: string,
  payload: FiscalClassificationUpdatePayload,
) {
  return apiRequest<FiscalClassification>(
    `/fiscal/classifications/${classificationId}`,
    {
      method: "PATCH",
      body: payload,
    },
  )
}

export function getFiscalClassificationAudit(classificationId: string) {
  return apiRequest<ApiListResponse<FiscalAuditEvent>>(
    `/fiscal/classifications/${classificationId}/audit`,
  )
}

export function getFiscalRules() {
  return apiRequest<FiscalRules>("/fiscal/rules")
}

export function getFiscalDiagnostics() {
  return apiRequest<FiscalDiagnostics>("/fiscal/diagnostics")
}
