export type ImportTarget = "participants" | "products" | "fiscal-classifications"
export type ImportRowStatus = "valid" | "invalid"
export type ImportCellValue = string | number | boolean | null
export type ImportRawRow = Record<string, ImportCellValue>
export type ImportStep = "template" | "upload" | "preview" | "commit"

export type ImportTargetOption = {
  target: ImportTarget
  title: string
  subtitle: string
}

export type ImportTemplateColumn = {
  key: string
  label: string
  required: boolean
  description: string
  example: string | null
}

export type ImportTemplate = {
  target: ImportTarget
  label: string
  description: string
  columns: ImportTemplateColumn[]
}

export type ImportRowPreview = {
  row_number: number
  status: ImportRowStatus
  raw: ImportRawRow
  payload: Record<string, unknown> | null
  errors: string[]
  warnings: string[]
}

export type ImportRowsPayload = {
  company_id: string
  rows: ImportRawRow[]
}

export type ImportPreviewResult = {
  target: ImportTarget
  company_id: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  rows: ImportRowPreview[]
}

export type ImportCommitResult = {
  target: ImportTarget
  company_id: string
  total_rows: number
  created_rows: number
  failed_rows: number
  skipped_rows: number
  created: Array<{ row_number: number; id: string | null; payload: Record<string, unknown>; result: Record<string, unknown> }>
  failures: Array<{ row_number: number; payload: Record<string, unknown> | null; errors: string[] }>
}

export type ParsedImportFile = {
  fileName: string
  headers: string[]
  rows: ImportRawRow[]
}
