import { apiRequest } from "../../lib/api"
import type { ImportCommitResult, ImportPreviewResult, ImportRowsPayload, ImportTarget, ImportTemplate } from "./types"

export function listImportTemplates() {
  return apiRequest<ImportTemplate[]>("/imports/templates")
}

export function getImportTemplate(target: ImportTarget) {
  return apiRequest<ImportTemplate>(`/imports/templates/${target}`)
}

export function previewImportRows(target: ImportTarget, payload: ImportRowsPayload) {
  return apiRequest<ImportPreviewResult>(`/imports/${target}/preview`, {
    method: "POST",
    body: payload,
  })
}

export function commitImportRows(target: ImportTarget, payload: ImportRowsPayload) {
  return apiRequest<ImportCommitResult>(`/imports/${target}/commit`, {
    method: "POST",
    body: payload,
  })
}
