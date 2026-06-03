import { strToU8, zipSync } from "fflate"

export type ExportDateCell = { kind: "date"; value: string | Date | null | undefined }
export type ExportDateTimeCell = { kind: "datetime"; value: string | Date | null | undefined }
export type ExportMoneyCell = { kind: "money"; value: string | number | null | undefined }
export type ExportNumberCell = { kind: "number"; value: string | number | null | undefined }
export type ExportIntegerCell = { kind: "integer"; value: string | number | null | undefined }
export type ExportCell =
  | string
  | number
  | boolean
  | null
  | undefined
  | ExportDateCell
  | ExportDateTimeCell
  | ExportMoneyCell
  | ExportNumberCell
  | ExportIntegerCell
export type ExportTable = Array<Array<ExportCell>>
export type ExportSheet = { name: string; rows: ExportTable }

export function dateCell(value: string | Date | null | undefined): ExportDateCell {
  return { kind: "date", value }
}

export function dateTimeCell(value: string | Date | null | undefined): ExportDateTimeCell {
  return { kind: "datetime", value }
}

export function moneyCell(value: string | number | null | undefined): ExportMoneyCell {
  return { kind: "money", value }
}

export function numberCell(value: string | number | null | undefined): ExportNumberCell {
  return { kind: "number", value }
}

export function integerCell(value: string | number | null | undefined): ExportIntegerCell {
  return { kind: "integer", value }
}

function isExportDateCell(value: ExportCell): value is ExportDateCell {
  return typeof value === "object" && value !== null && "kind" in value && value.kind === "date"
}

function isExportDateTimeCell(value: ExportCell): value is ExportDateTimeCell {
  return typeof value === "object" && value !== null && "kind" in value && value.kind === "datetime"
}

function isExportMoneyCell(value: ExportCell): value is ExportMoneyCell {
  return typeof value === "object" && value !== null && "kind" in value && value.kind === "money"
}

function isExportNumberCell(value: ExportCell): value is ExportNumberCell {
  return typeof value === "object" && value !== null && "kind" in value && value.kind === "number"
}

function isExportIntegerCell(value: ExportCell): value is ExportIntegerCell {
  return typeof value === "object" && value !== null && "kind" in value && value.kind === "integer"
}

function parseDateForExport(value: string | Date | null | undefined) {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number)
    return new Date(year, month - 1, day)
  }
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(value)) {
    const [day, month, year] = value.split("/").map(Number)
    return new Date(year, month - 1, day)
  }
  if (/^\d{2}\/\d{2}\/\d{4}\s\d{2}:\d{2}(:\d{2})?$/.test(value)) {
    const [datePart, timePart] = value.split(" ")
    const [day, month, year] = datePart.split("/").map(Number)
    const [hours, minutes, seconds] = timePart.split(":").map(Number)
    return new Date(year, month - 1, day, hours, minutes, seconds ?? 0)
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed
}

function formatExportDate(value: string | Date | null | undefined) {
  const parsed = parseDateForExport(value)
  if (!parsed) return value ?? ""
  const day = String(parsed.getDate()).padStart(2, "0")
  const month = String(parsed.getMonth() + 1).padStart(2, "0")
  const year = String(parsed.getFullYear()).padStart(4, "0")
  return `${day}/${month}/${year}`
}

function formatExportDateTime(value: string | Date | null | undefined) {
  const parsed = parseDateForExport(value)
  if (!parsed) return value ?? ""
  const day = String(parsed.getDate()).padStart(2, "0")
  const month = String(parsed.getMonth() + 1).padStart(2, "0")
  const year = String(parsed.getFullYear()).padStart(4, "0")
  const hours = String(parsed.getHours()).padStart(2, "0")
  const minutes = String(parsed.getMinutes()).padStart(2, "0")
  const seconds = String(parsed.getSeconds()).padStart(2, "0")
  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`
}

function excelSerialDate(date: Date) {
  const utc = Date.UTC(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    date.getHours(),
    date.getMinutes(),
    date.getSeconds(),
  )
  const excelEpoch = Date.UTC(1899, 11, 30)
  return (utc - excelEpoch) / 86400000
}

function normalizeNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return null
  if (typeof value === "number") return Number.isFinite(value) ? value : null
  const raw = String(value).trim()
  if (!raw) return null
  const cleaned = raw
    .replace(/\s+/g, "")
    .replace(/R\$/gi, "")
    .replace(/[^\d,.-]/g, "")

  if (!cleaned) return null
  let normalized = cleaned
  const hasComma = cleaned.includes(",")
  const hasDot = cleaned.includes(".")
  if (hasComma && hasDot) {
    normalized =
      cleaned.lastIndexOf(",") > cleaned.lastIndexOf(".")
        ? cleaned.replace(/\./g, "").replace(",", ".")
        : cleaned.replace(/,/g, "")
  } else if (hasComma) {
    const parts = cleaned.split(",")
    normalized =
      parts.length === 2 && parts[1].length <= 4
        ? cleaned.replace(",", ".")
        : cleaned.replace(/,/g, "")
  }
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function cellDisplayValue(value: ExportCell) {
  if (isExportDateCell(value)) return formatExportDate(value.value)
  if (isExportDateTimeCell(value)) return formatExportDateTime(value.value)
  if (isExportMoneyCell(value)) {
    const parsed = normalizeNumber(value.value)
    return parsed === null ? "" : String(parsed)
  }
  if (isExportNumberCell(value)) {
    const parsed = normalizeNumber(value.value)
    return parsed === null ? "" : String(parsed)
  }
  if (isExportIntegerCell(value)) {
    const parsed = normalizeNumber(value.value)
    return parsed === null ? "" : String(Math.trunc(parsed))
  }
  return value ?? ""
}

function escapeCsv(value: ExportCell) {
  return `"${String(cellDisplayValue(value)).replace(/"/g, '""')}"`
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function exportCsv(rows: ExportTable, fileName: string) {
  const csv = rows.map((row) => row.map(escapeCsv).join(";")).join("\r\n")
  downloadBlob(new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" }), fileName)
}

function escapeXml(value: unknown) {
  let output = ""
  for (const char of String(value ?? "")) {
    const codePoint = char.codePointAt(0) ?? 0
    if (char === "&") output += "&amp;"
    else if (char === "<") output += "&lt;"
    else if (char === ">") output += "&gt;"
    else if (char === "\"") output += "&quot;"
    else if (char === "'") output += "&apos;"
    else if (codePoint > 126) output += `&#${codePoint};`
    else if (codePoint < 32 && char !== "\t" && char !== "\n" && char !== "\r") output += " "
    else output += char
  }
  return output
}

function getExcelColumnName(index: number) {
  let columnName = ""
  let columnIndex = index
  while (columnIndex > 0) {
    const modulo = (columnIndex - 1) % 26
    columnName = String.fromCharCode(65 + modulo) + columnName
    columnIndex = Math.floor((columnIndex - modulo) / 26)
  }
  return columnName
}

function getWorksheetRef(rows: ExportTable) {
  const rowCount = Math.max(rows.length, 1)
  const columnCount = Math.max(...rows.map((row) => row.length), 1)
  return `A1:${getExcelColumnName(columnCount)}${rowCount}`
}

function buildWorksheetXml(rows: ExportTable) {
  const worksheetRef = getWorksheetRef(rows)
  const canUseAutoFilter = rows.length > 0 && rows[0].length > 0 && rows.every((row) => row.length === rows[0].length)
  const sheetData = rows
    .map((row, rowIndex) => {
      const rowNumber = rowIndex + 1
      const cells = row
        .map((cell, cellIndex) => {
          const cellReference = `${getExcelColumnName(cellIndex + 1)}${rowNumber}`
          if (rowIndex === 0) {
            return `<c r="${cellReference}" t="inlineStr" s="1"><is><t>${escapeXml(cellDisplayValue(cell))}</t></is></c>`
          }
          if (isExportDateCell(cell)) {
            const parsedDate = parseDateForExport(cell.value)
            if (parsedDate) return `<c r="${cellReference}" s="2"><v>${excelSerialDate(parsedDate)}</v></c>`
          }
          if (isExportDateTimeCell(cell)) {
            const parsedDateTime = parseDateForExport(cell.value)
            if (parsedDateTime) return `<c r="${cellReference}" s="3"><v>${excelSerialDate(parsedDateTime)}</v></c>`
          }
          if (isExportMoneyCell(cell)) {
            const parsedMoney = normalizeNumber(cell.value)
            if (parsedMoney !== null) return `<c r="${cellReference}" s="4"><v>${parsedMoney}</v></c>`
          }
          if (isExportNumberCell(cell)) {
            const parsedNumber = normalizeNumber(cell.value)
            if (parsedNumber !== null) return `<c r="${cellReference}" s="5"><v>${parsedNumber}</v></c>`
          }
          if (isExportIntegerCell(cell)) {
            const parsedInteger = normalizeNumber(cell.value)
            if (parsedInteger !== null) return `<c r="${cellReference}" s="6"><v>${Math.trunc(parsedInteger)}</v></c>`
          }
          if (typeof cell === "number" && Number.isFinite(cell)) {
            const style = Number.isInteger(cell) ? "6" : "5"
            return `<c r="${cellReference}" s="${style}"><v>${cell}</v></c>`
          }
          if (typeof cell === "boolean") {
            return `<c r="${cellReference}" t="b"><v>${cell ? 1 : 0}</v></c>`
          }
          return `<c r="${cellReference}" t="inlineStr"><is><t>${escapeXml(cellDisplayValue(cell))}</t></is></c>`
        })
        .join("")
      return `<row r="${rowNumber}">${cells}</row>`
    })
    .join("")

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="${worksheetRef}" />
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
      <selection pane="bottomLeft"/>
    </sheetView>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="15" />
  <sheetData>${sheetData}</sheetData>
  ${canUseAutoFilter ? `<autoFilter ref="${worksheetRef}" />` : ""}
</worksheet>`
}

function safeSheetName(name: string, index: number, usedNames: Set<string>) {
  const fallback = `Planilha ${index + 1}`
  const base = (name.trim() || fallback).slice(0, 31).replace(/[\\/?*:[\]]/g, " ").trim() || fallback
  let candidate = base
  let suffix = 2
  while (usedNames.has(candidate.toLowerCase())) {
    const nextSuffix = ` ${suffix}`
    candidate = `${base.slice(0, 31 - nextSuffix.length)}${nextSuffix}`
    suffix += 1
  }
  usedNames.add(candidate.toLowerCase())
  return candidate
}

export function exportXlsxWorkbook(sheets: ExportSheet[], fileName: string) {
  const normalizedSheets = sheets.length > 0 ? sheets : [{ name: "Relatorio", rows: [] }]
  const usedNames = new Set<string>()
  const safeSheets = normalizedSheets.map((sheet, index) => ({
    name: safeSheetName(sheet.name, index, usedNames),
    rows: sheet.rows,
  }))
  const worksheetOverrides = safeSheets
    .map(
      (_, index) =>
        `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`,
    )
    .join("\n")
  const workbookSheets = safeSheets
    .map((sheet, index) => `<sheet name="${escapeXml(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`)
    .join("")
  const workbookRels = safeSheets
    .map(
      (_, index) =>
        `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`,
    )
    .join("\n")
  const files: Record<string, Uint8Array> = {
    "[Content_Types].xml": strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  ${worksheetOverrides}
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>`),
    "_rels/.rels": strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`),
    "xl/workbook.xml": strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>${workbookSheets}</sheets>
</workbook>`),
    "xl/_rels/workbook.xml.rels": strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  ${workbookRels}
  <Relationship Id="rId${safeSheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`),
    "xl/styles.xml": strToU8(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="5">
    <numFmt numFmtId="165" formatCode="dd/mm/yyyy"/>
    <numFmt numFmtId="166" formatCode="dd/mm/yyyy hh:mm:ss"/>
    <numFmt numFmtId="167" formatCode="&quot;R$&quot; #,##0.00;[Red]-&quot;R$&quot; #,##0.00;&quot;R$&quot; 0.00"/>
    <numFmt numFmtId="168" formatCode="#,##0.0000"/>
    <numFmt numFmtId="169" formatCode="#,##0"/>
  </numFmts>
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="7">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="167" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="168" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="169" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
  </cellXfs>
</styleSheet>`),
  }
  safeSheets.forEach((sheet, index) => {
    files[`xl/worksheets/sheet${index + 1}.xml`] = strToU8(buildWorksheetXml(sheet.rows))
  })

  const zipped = zipSync(files, { level: 6 })
  const arrayBuffer = new ArrayBuffer(zipped.byteLength)
  new Uint8Array(arrayBuffer).set(zipped)
  downloadBlob(new Blob([arrayBuffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), fileName)
}

export function exportXlsx(rows: ExportTable, sheetName: string, fileName: string) {
  exportXlsxWorkbook([{ name: sheetName, rows }], fileName)
}
