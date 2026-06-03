import type { ImportStep, ImportTargetOption, ImportTemplate } from "./types"

export const MAX_VISIBLE_COLUMNS = 8
export const MAX_IMPORT_ROWS = 5000
export const MAX_IMPORT_FILE_SIZE_BYTES = 10 * 1024 * 1024
export const EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
export const ALLOWED_IMPORT_FILE_EXTENSIONS = [".csv", ".tsv", ".txt", ".xlsx"] as const
export const ALLOWED_IMPORT_MIME_TYPES = new Set([
  "text/csv",
  "text/plain",
  "text/tab-separated-values",
  EXCEL_MIME,
])
export const ACCEPTED_IMPORT_FILE_TYPES = `${ALLOWED_IMPORT_FILE_EXTENSIONS.join(",")},${Array.from(ALLOWED_IMPORT_MIME_TYPES).join(",")}`

export const IMPORT_TARGETS: ImportTargetOption[] = [
  {
    target: "participants",
    title: "Participantes",
    subtitle: "Clientes, fornecedores, bancos, gateways e terceiros.",
  },
  {
    target: "products",
    title: "Produtos",
    subtitle: "Itens do catalogo com NCM previamente cadastrado.",
  },
  {
    target: "fiscal-classifications",
    title: "Classificacoes fiscais",
    subtitle: "NCM, NBS, CFOP, CST e referencias tributarias.",
  },
]

export function getImportStepLabel(step: ImportStep) {
  const labels: Record<ImportStep, string> = {
    template: "Escolher modelo",
    upload: "Arquivo carregado",
    preview: "Previa gerada",
    commit: "Importacao confirmada",
  }
  return labels[step]
}

export function buildTemplateCsv(template: ImportTemplate) {
  const headers = template.columns.map((column) => column.key)
  const examples = template.columns.map((column) => column.example ?? "")
  return [headers, examples].map((row) => row.map((value) => toCsvCell(value)).join(";")).join("\r\n")
}

export function isAcceptedImportFile(file: File) {
  const lowerName = file.name.toLowerCase()
  const hasAllowedExtension = ALLOWED_IMPORT_FILE_EXTENSIONS.some((extension) => lowerName.endsWith(extension))
  const hasAllowedMime = file.type ? ALLOWED_IMPORT_MIME_TYPES.has(file.type) : true
  return hasAllowedExtension && hasAllowedMime
}

function toCsvCell(value: string) {
  if (!/[;"\r\n]/.test(value)) return value
  return `"${value.replace(/"/g, '""')}"`
}
