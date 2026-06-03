export type ExportFormat = "csv" | "xlsx"

function normalizePart(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

export function exportDateStamp() {
  return new Date().toISOString().slice(0, 10)
}

export function buildExportFileName(moduleName: string, baseName: string, format: ExportFormat) {
  const modulePart = normalizePart(moduleName) || "kovir"
  const basePart = normalizePart(baseName) || "dados"
  return `${modulePart}_${basePart}_${exportDateStamp()}.${format}`
}

