import { apiRequest } from "../../lib/api"

import type {
  Participant,
  ParticipantAuditEvent,
  ParticipantCreatePayload,
  ParticipantDiagnostics,
  ParticipantListPage,
  ParticipantRules,
  ParticipantStatus,
  ParticipantSummary,
  ParticipantType,
  ParticipantUpdatePayload,
  PersonType,
} from "./types"

export type ListParticipantsParams = {
  company_id?: string
  participant_type?: ParticipantType
  person_type?: PersonType
  status?: ParticipantStatus
  search?: string
  limit?: number
  offset?: number
}

function buildQueryString(params?: ListParticipantsParams) {
  if (!params) return ""

  const searchParams = new URLSearchParams()

  if (params.company_id) {
    searchParams.set("company_id", params.company_id)
  }

  if (params.participant_type) {
    searchParams.set("participant_type", params.participant_type)
  }

  if (params.person_type) {
    searchParams.set("person_type", params.person_type)
  }

  if (params.status) {
    searchParams.set("status", params.status)
  }

  if (params.search && params.search.trim()) {
    searchParams.set("search", params.search.trim())
  }

  if (params.limit !== undefined) {
    searchParams.set("limit", String(params.limit))
  }

  if (params.offset !== undefined) {
    searchParams.set("offset", String(params.offset))
  }

  const queryString = searchParams.toString()

  return queryString ? `?${queryString}` : ""
}

export function getParticipants(params?: ListParticipantsParams) {
  const queryString = buildQueryString(params)

  return apiRequest<ParticipantListPage>(`/participants${queryString}`).then((response) => ({
    ...response,
    data: response.data.items,
  }))
}

export function getParticipantsPage(params?: ListParticipantsParams) {
  const queryString = buildQueryString(params)

  return apiRequest<ParticipantListPage>(`/participants${queryString}`)
}

export function createParticipant(payload: ParticipantCreatePayload) {
  return apiRequest<Participant>("/participants", {
    method: "POST",
    body: payload,
  })
}

export function getParticipant(participantId: string) {
  return apiRequest<Participant>(`/participants/${participantId}`)
}

export function updateParticipant(
  participantId: string,
  payload: ParticipantUpdatePayload,
) {
  return apiRequest<Participant>(`/participants/${participantId}`, {
    method: "PATCH",
    body: payload,
  })
}

export function getParticipantAuditEvents(participantId: string) {
  return apiRequest<ParticipantAuditEvent[]>(
    `/participants/${participantId}/audit`,
  )
}

export function getParticipantRules() {
  return apiRequest<ParticipantRules>("/system/participant-rules")
}

export function getParticipantSummary(companyId?: string) {
  const queryString = companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""

  return apiRequest<ParticipantSummary>(`/participants/summary${queryString}`)
}

export function getParticipantDiagnostics(companyId?: string) {
  const queryString = companyId ? `?company_id=${encodeURIComponent(companyId)}` : ""

  return apiRequest<ParticipantDiagnostics>(`/system/participant-diagnostics${queryString}`)
}
