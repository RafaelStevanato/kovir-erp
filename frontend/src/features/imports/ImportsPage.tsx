import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileDown,
  FileSpreadsheet,
  FileUp,
  Loader2,
  PlayCircle,
  RefreshCw,
  ShieldCheck,
  Table2,
  Upload,
  XCircle,
} from "lucide-react"
import { strFromU8, unzipSync } from "fflate"

import { useActiveCompany } from "../../config/useActiveCompany"
import { commitImportRows, listImportTemplates, previewImportRows } from "./importsApi"
import { ACCEPTED_IMPORT_FILE_TYPES, buildTemplateCsv, EXCEL_MIME, getImportStepLabel, IMPORT_TARGETS, isAcceptedImportFile, MAX_IMPORT_FILE_SIZE_BYTES, MAX_IMPORT_ROWS, MAX_VISIBLE_COLUMNS } from "./templates"
import type {
  ImportCellValue,
  ImportCommitResult,
  ImportPreviewResult,
  ImportRawRow,
  ImportRowStatus,
  ImportStep,
  ImportTarget,
  ImportTemplate,
  ParsedImportFile,
} from "./types"

type Notice = { type: "success" | "error" | "warning"; message: string } | null

export function ImportsPage() {
  const { companyId, activeCompanyName, isCompanyLoading, companyError } = useActiveCompany()
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [templates, setTemplates] = useState<ImportTemplate[]>([])
  const [selectedTarget, setSelectedTarget] = useState<ImportTarget>("participants")
  const [parsedFile, setParsedFile] = useState<ParsedImportFile | null>(null)
  const [preview, setPreview] = useState<ImportPreviewResult | null>(null)
  const [commitResult, setCommitResult] = useState<ImportCommitResult | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true)
  const [isParsingFile, setIsParsingFile] = useState(false)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isCommitting, setIsCommitting] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadTemplates() {
      setIsLoadingTemplates(true)
      setNotice(null)
      try {
        const response = await listImportTemplates()
        if (cancelled) return
        setTemplates(response.data)
      } catch (error) {
        if (cancelled) return
        setNotice({ type: "error", message: getErrorMessage(error, "Falha ao carregar modelos de importacao.") })
      } finally {
        if (!cancelled) setIsLoadingTemplates(false)
      }
    }

    void loadTemplates()

    return () => {
      cancelled = true
    }
  }, [])

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.target === selectedTarget) ?? null,
    [selectedTarget, templates],
  )

  const visibleColumns = useMemo(() => {
    if (parsedFile?.headers.length) return parsedFile.headers.slice(0, MAX_VISIBLE_COLUMNS)
    return selectedTemplate?.columns.slice(0, MAX_VISIBLE_COLUMNS).map((column) => column.key) ?? []
  }, [parsedFile, selectedTemplate])

  const currentStep = useMemo<ImportStep>(() => {
    if (commitResult) return "commit"
    if (preview) return "preview"
    if (parsedFile) return "upload"
    return "template"
  }, [commitResult, parsedFile, preview])

  const canPreview = Boolean(companyId && parsedFile && parsedFile.rows.length > 0 && !isPreviewing && !isParsingFile)
  const canCommit = Boolean(preview && preview.valid_rows > 0 && preview.invalid_rows === 0 && !isCommitting)

  function resetImportState() {
    setParsedFile(null)
    setPreview(null)
    setCommitResult(null)
    setNotice(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  function handleSelectTarget(target: ImportTarget) {
    if (target === selectedTarget) return
    setSelectedTarget(target)
    resetImportState()
  }

  function handleDownloadTemplate() {
    if (!selectedTemplate) return
    const csv = buildTemplateCsv(selectedTemplate)
    const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `kovir-importacao-${selectedTemplate.target}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return

    setIsParsingFile(true)
    setNotice(null)
    setPreview(null)
    setCommitResult(null)

    try {
      if (!isAcceptedImportFile(file)) {
        throw new Error("Formato de arquivo nao permitido. Use CSV, TSV, TXT ou XLSX gerado pelo modelo oficial.")
      }
      if (file.size > MAX_IMPORT_FILE_SIZE_BYTES) {
        throw new Error(`Arquivo acima do limite de ${(MAX_IMPORT_FILE_SIZE_BYTES / 1024 / 1024).toFixed(0)} MB.`)
      }

      const parsed = await parseImportFile(file)
      if (parsed.rows.length > MAX_IMPORT_ROWS) {
        throw new Error(`Planilha com ${parsed.rows.length} linhas. O limite por importacao e ${MAX_IMPORT_ROWS} linhas.`)
      }
      if (parsed.rows.length === 0) {
        setParsedFile(parsed)
        setNotice({ type: "warning", message: "Arquivo lido, mas nenhuma linha de dados foi encontrada." })
        return
      }
      setParsedFile(parsed)
      setNotice({ type: "success", message: `${parsed.rows.length} linha(s) carregada(s). Gere a previa para validar no backend.` })
    } catch (error) {
      setParsedFile(null)
      setNotice({ type: "error", message: getErrorMessage(error, "Falha ao ler arquivo de importacao.") })
      if (fileInputRef.current) fileInputRef.current.value = ""
    } finally {
      setIsParsingFile(false)
    }
  }

  async function handlePreview() {
    if (!parsedFile || !companyId) return
    setIsPreviewing(true)
    setNotice(null)
    setPreview(null)
    setCommitResult(null)

    try {
      const response = await previewImportRows(selectedTarget, {
        company_id: companyId,
        rows: parsedFile.rows,
      })
      setPreview(response.data)
      setNotice({
        type: response.data.invalid_rows > 0 ? "warning" : "success",
        message: response.data.invalid_rows > 0
          ? "Previa gerada com inconsistencias. Corrija a planilha antes de confirmar."
          : "Previa validada. A confirmacao vai cadastrar os registros no backend.",
      })
    } catch (error) {
      setNotice({ type: "error", message: getErrorMessage(error, "Falha ao gerar previa de importacao.") })
    } finally {
      setIsPreviewing(false)
    }
  }

  async function handleCommit() {
    if (!parsedFile || !companyId || !preview) return
    setIsCommitting(true)
    setNotice(null)
    setCommitResult(null)

    try {
      const response = await commitImportRows(selectedTarget, {
        company_id: companyId,
        rows: parsedFile.rows,
      })
      setCommitResult(response.data)
      setNotice({
        type: response.data.failed_rows > 0 ? "warning" : "success",
        message: response.data.failed_rows > 0
          ? "Importacao concluida com falhas. Revise o retorno antes de tentar novamente."
          : "Importacao confirmada e cadastros criados.",
      })
    } catch (error) {
      setNotice({ type: "error", message: getErrorMessage(error, "Falha ao confirmar importacao.") })
    } finally {
      setIsCommitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="relative overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[var(--color-primary-soft)] blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-1.5 text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">
              <Upload className="h-4 w-4" />
              Importacoes assistidas
            </span>
            <h1 className="mt-4 text-4xl font-black tracking-tight text-[var(--color-text)] sm:text-5xl">Importacoes</h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--color-text-muted)]">
              Migre cadastros legados para o Kovir ERP usando modelos controlados. A tela le a planilha, lista os dados e envia a validacao final para o backend antes de cadastrar.
            </p>
          </div>

          <div className="grid min-w-[260px] gap-3 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
            <StatusLine label="Empresa ativa" value={isCompanyLoading ? "Carregando..." : activeCompanyName} />
            <StatusLine label="Fluxo atual" value={getImportStepLabel(currentStep)} />
            <StatusLine label="Backend" value="Preview e commit oficiais" />
          </div>
        </div>
      </header>

      {notice && <NoticeBanner notice={notice} />}
      {companyError && <NoticeBanner notice={{ type: "error", message: companyError }} />}
      {!companyId && !isCompanyLoading && (
        <NoticeBanner notice={{ type: "warning", message: "Selecione ou autentique uma empresa antes de importar dados." }} />
      )}

      <section className="grid gap-4 lg:grid-cols-3">
        {IMPORT_TARGETS.map((item) => {
          const active = item.target === selectedTarget
          const template = templates.find((candidate) => candidate.target === item.target)
          return (
            <button
              key={item.target}
              type="button"
              onClick={() => handleSelectTarget(item.target)}
              className={`rounded-3xl border p-5 text-left transition hover:-translate-y-0.5 ${
                active
                  ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)] shadow-xl shadow-[var(--color-card-shadow)]"
                  : "border-[var(--color-border-soft)] bg-[var(--color-surface)] hover:border-[var(--color-primary-border)]"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-lg font-black text-[var(--color-text)]">{item.title}</p>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">{item.subtitle}</p>
                </div>
                <span className={`rounded-2xl px-3 py-1 text-xs font-black ${active ? "bg-[var(--color-primary)] text-white" : "bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)]"}`}>
                  {template?.columns.length ?? 0} campos
                </span>
              </div>
            </button>
          )
        })}
      </section>

      <main className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)]">
        <section className="space-y-6">
          <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <FileDown className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-[var(--color-text)]">1. Baixar modelo</h2>
                <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                  Use o modelo da categoria selecionada. Cabecalhos fora do padrao ainda passam pelo normalizador do backend, mas o modelo reduz retrabalho.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleDownloadTemplate}
              disabled={!selectedTemplate || isLoadingTemplates}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoadingTemplates ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileDown className="h-4 w-4" />}
              Baixar modelo CSV
            </button>
          </div>

          <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <FileUp className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-[var(--color-text)]">2. Anexar planilha</h2>
                <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                  Formatos aceitos: CSV, TSV, TXT e XLSX simples com cabecalho na primeira linha util. Limite: {MAX_IMPORT_ROWS} linhas e {(MAX_IMPORT_FILE_SIZE_BYTES / 1024 / 1024).toFixed(0)} MB.
                </p>
              </div>
            </div>

            <label className="mt-5 flex cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-5 py-8 text-center transition hover:opacity-90">
              <FileSpreadsheet className="h-10 w-10 text-[var(--color-primary)]" />
              <span className="mt-3 text-sm font-black text-[var(--color-primary)]">
                {parsedFile ? parsedFile.fileName : "Selecionar arquivo"}
              </span>
              <span className="mt-1 text-xs text-[var(--color-text-muted)]">A validacao de negocio acontece no backend.</span>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_IMPORT_FILE_TYPES}
                className="sr-only"
                onChange={handleFileChange}
              />
            </label>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handlePreview}
                disabled={!canPreview}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-2xl bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isPreviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                Gerar previa
              </button>
              <button
                type="button"
                onClick={resetImportState}
                disabled={isParsingFile || isPreviewing || isCommitting}
                className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-3 text-sm font-bold text-[var(--color-text)] transition hover:border-[var(--color-primary-border)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw className="h-4 w-4" />
                Limpar
              </button>
            </div>
          </div>

          <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-lg font-black text-[var(--color-text)]">3. Confirmar cadastro</h2>
                <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
                  A confirmacao so fica disponivel quando todas as linhas estiverem validas na previa.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleCommit}
              disabled={!canCommit}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isCommitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
              Confirmar importacao
            </button>
          </div>
        </section>

        <section className="space-y-6">
          {selectedTemplate && <TemplateDetails template={selectedTemplate} />}
          <ImportSummary parsedFile={parsedFile} preview={preview} commitResult={commitResult} />
          <RowsPreview parsedFile={parsedFile} preview={preview} visibleColumns={visibleColumns} />
        </section>
      </main>
    </div>
  )
}

function TemplateDetails({ template }: { template: ImportTemplate }) {
  const requiredColumns = template.columns.filter((column) => column.required)

  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--color-primary-soft)] text-[var(--color-primary)]">
          <Table2 className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-lg font-black text-[var(--color-text)]">Modelo: {template.label}</h2>
          <p className="text-sm text-[var(--color-text-muted)]">{template.description}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <MetricCard label="Campos" value={String(template.columns.length)} />
        <MetricCard label="Obrigatorios" value={String(requiredColumns.length)} />
        <MetricCard label="Formato" value="CSV / XLSX" />
      </div>

      <div className="mt-5 max-h-72 overflow-auto rounded-2xl border border-[var(--color-border-soft)]">
        <table className="min-w-full divide-y divide-[var(--color-border-soft)] text-left text-sm">
          <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3 font-black">Campo</th>
              <th className="px-4 py-3 font-black">Obrigatorio</th>
              <th className="px-4 py-3 font-black">Exemplo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border-soft)]">
            {template.columns.map((column) => (
              <tr key={column.key}>
                <td className="px-4 py-3 align-top">
                  <p className="font-mono text-xs font-black text-[var(--color-primary)]">{column.key}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{column.label}</p>
                </td>
                <td className="px-4 py-3 align-top text-xs font-bold text-[var(--color-text)]">{column.required ? "Sim" : "Nao"}</td>
                <td className="px-4 py-3 align-top text-xs text-[var(--color-text-muted)]">{column.example ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ImportSummary({ parsedFile, preview, commitResult }: { parsedFile: ParsedImportFile | null; preview: ImportPreviewResult | null; commitResult: ImportCommitResult | null }) {
  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Linhas lidas" value={String(parsedFile?.rows.length ?? 0)} />
      <MetricCard label="Validas" value={String(preview?.valid_rows ?? 0)} tone="success" />
      <MetricCard label="Invalidas" value={String(preview?.invalid_rows ?? 0)} tone={preview?.invalid_rows ? "danger" : "default"} />
      <MetricCard label="Criadas" value={String(commitResult?.created_rows ?? 0)} tone="success" />
    </section>
  )
}

function RowsPreview({ parsedFile, preview, visibleColumns }: { parsedFile: ParsedImportFile | null; preview: ImportPreviewResult | null; visibleColumns: string[] }) {
  const rows = preview?.rows ?? parsedFile?.rows.map((row, index) => ({ row_number: index + 2, status: "valid" as ImportRowStatus, raw: row, payload: null, errors: [], warnings: [] })) ?? []

  if (!parsedFile) {
    return (
      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-8 text-center shadow-xl shadow-[var(--color-card-shadow)]">
        <FileSpreadsheet className="mx-auto h-12 w-12 text-[var(--color-text-weak)]" />
        <h2 className="mt-4 text-lg font-black text-[var(--color-text)]">Nenhuma planilha carregada</h2>
        <p className="mt-2 text-sm text-[var(--color-text-muted)]">Baixe o modelo, preencha os dados e anexe o arquivo para visualizar as linhas.</p>
      </section>
    )
  }

  return (
    <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-black text-[var(--color-text)]">Dados da planilha</h2>
          <p className="text-sm text-[var(--color-text-muted)]">{parsedFile.fileName} - {parsedFile.rows.length} linha(s)</p>
        </div>
        <span className="rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-1 text-xs font-black text-[var(--color-primary)]">
          {preview ? "Previa do backend" : "Leitura local"}
        </span>
      </div>

      <div className="mt-5 overflow-auto rounded-2xl border border-[var(--color-border-soft)]">
        <table className="min-w-full divide-y divide-[var(--color-border-soft)] text-left text-sm">
          <thead className="bg-[var(--color-surface-elevated)] text-xs uppercase tracking-wide text-[var(--color-text-muted)]">
            <tr>
              <th className="px-4 py-3 font-black">Linha</th>
              <th className="px-4 py-3 font-black">Status</th>
              {visibleColumns.map((column) => (
                <th key={column} className="px-4 py-3 font-black">{column}</th>
              ))}
              <th className="px-4 py-3 font-black">Retorno</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border-soft)]">
            {rows.slice(0, 80).map((row) => (
              <tr key={row.row_number}>
                <td className="px-4 py-3 align-top font-mono text-xs text-[var(--color-text-muted)]">{row.row_number}</td>
                <td className="px-4 py-3 align-top">
                  <RowStatusBadge status={row.status} />
                </td>
                {visibleColumns.map((column) => (
                  <td key={`${row.row_number}-${column}`} className="max-w-[220px] truncate px-4 py-3 align-top text-xs text-[var(--color-text)]" title={formatCell(row.raw[column])}>
                    {formatCell(row.raw[column]) || "-"}
                  </td>
                ))}
                <td className="min-w-[260px] px-4 py-3 align-top text-xs">
                  {row.errors.length > 0 && <MessageList items={row.errors} tone="danger" />}
                  {row.warnings.length > 0 && <MessageList items={row.warnings} tone="warning" />}
                  {row.errors.length === 0 && row.warnings.length === 0 && <span className="text-[var(--color-text-muted)]">Sem apontamentos</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > 80 && (
        <p className="mt-3 text-xs text-[var(--color-text-muted)]">Exibindo 80 de {rows.length} linha(s). A validacao enviada ao backend usa o arquivo completo.</p>
      )}
    </section>
  )
}

function NoticeBanner({ notice }: { notice: Exclude<Notice, null> }) {
  const Icon = notice.type === "success" ? CheckCircle2 : notice.type === "warning" ? AlertTriangle : XCircle
  const colorClass = notice.type === "success"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
    : notice.type === "warning"
      ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-200"
      : "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-200"

  return (
    <div className={`flex items-start gap-3 rounded-3xl border px-5 py-4 text-sm font-semibold ${colorClass}`}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <span>{notice.message}</span>
    </div>
  )
}

function MetricCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "danger" }) {
  const valueClass = tone === "success" ? "text-[var(--color-success)]" : tone === "danger" ? "text-[var(--color-danger)]" : "text-[var(--color-text)]"
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-lg shadow-[var(--color-card-shadow)]">
      <p className="text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
      <p className={`mt-2 text-2xl font-black ${valueClass}`}>{value}</p>
    </div>
  )
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="font-bold text-[var(--color-text-muted)]">{label}</span>
      <span className="max-w-[170px] truncate text-right font-black text-[var(--color-text)]" title={value}>{value}</span>
    </div>
  )
}

function RowStatusBadge({ status }: { status: ImportRowStatus }) {
  const valid = status === "valid"
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black ${valid ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-200" : "bg-red-500/10 text-red-700 dark:text-red-200"}`}>
      {valid ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {valid ? "Valida" : "Invalida"}
    </span>
  )
}

function MessageList({ items, tone }: { items: string[]; tone: "warning" | "danger" }) {
  const className = tone === "danger" ? "text-[var(--color-danger)]" : "text-[var(--color-warning)]"
  return (
    <ul className={`space-y-1 ${className}`}>
      {items.map((item) => (
        <li key={item}>- {item}</li>
      ))}
    </ul>
  )
}

async function parseImportFile(file: File): Promise<ParsedImportFile> {
  const lowerName = file.name.toLowerCase()
  if (lowerName.endsWith(".xlsx") || file.type === EXCEL_MIME) {
    return parseXlsxFile(file)
  }
  const text = await file.text()
  return parseDelimitedFile(file.name, text)
}

function parseDelimitedFile(fileName: string, text: string): ParsedImportFile {
  const normalizedText = text.replace(/^\ufeff/, "")
  const delimiter = detectDelimiter(normalizedText)
  const table = parseDelimitedText(normalizedText, delimiter).filter((row) => row.some((cell) => cell.trim() !== ""))
  if (table.length === 0) return { fileName, headers: [], rows: [] }

  const headers = table[0].map((cell, index) => cleanHeader(cell, index))
  const rows = table.slice(1).map((row) => buildRawRow(headers, row)).filter((row) => hasRowValue(row))
  return { fileName, headers, rows }
}

async function parseXlsxFile(file: File): Promise<ParsedImportFile> {
  const buffer = await file.arrayBuffer()
  const archive = unzipSync(new Uint8Array(buffer))
  const workbookXml = readArchiveText(archive, "xl/workbook.xml")
  const relsXml = readArchiveText(archive, "xl/_rels/workbook.xml.rels")
  const sheetPath = resolveFirstWorksheetPath(workbookXml, relsXml)
  const sheetXml = readArchiveText(archive, sheetPath)
  const sharedStrings = readSharedStrings(archive)
  const styles = readWorkbookStyles(archive)
  const table = parseWorksheetTable(sheetXml, sharedStrings, styles).filter((row) => row.some((cell) => cell.trim() !== ""))

  if (table.length === 0) return { fileName: file.name, headers: [], rows: [] }
  const headers = table[0].map((cell, index) => cleanHeader(cell, index))
  const rows = table.slice(1).map((row) => buildRawRow(headers, row)).filter((row) => hasRowValue(row))
  return { fileName: file.name, headers, rows }
}

function readArchiveText(archive: Record<string, Uint8Array>, path: string) {
  const file = archive[path]
  if (!file) throw new Error(`Arquivo interno nao encontrado no XLSX: ${path}`)
  return strFromU8(file)
}

function readOptionalArchiveText(archive: Record<string, Uint8Array>, path: string) {
  const file = archive[path]
  return file ? strFromU8(file) : null
}

function resolveFirstWorksheetPath(workbookXml: string, relsXml: string) {
  const parser = new DOMParser()
  const workbook = parser.parseFromString(workbookXml, "application/xml")
  const rels = parser.parseFromString(relsXml, "application/xml")
  const firstSheet = workbook.getElementsByTagName("sheet")[0]
  const relationId = firstSheet?.getAttribute("r:id")
  if (!relationId) return "xl/worksheets/sheet1.xml"

  const relationships = Array.from(rels.getElementsByTagName("Relationship"))
  const relationship = relationships.find((item) => item.getAttribute("Id") === relationId)
  const target = relationship?.getAttribute("Target") ?? "worksheets/sheet1.xml"
  if (target.startsWith("/")) return target.slice(1)
  return `xl/${target.replace(/^\.\//, "")}`
}

function readSharedStrings(archive: Record<string, Uint8Array>) {
  const sharedStringsFile = archive["xl/sharedStrings.xml"]
  if (!sharedStringsFile) return []

  const parser = new DOMParser()
  const xml = parser.parseFromString(strFromU8(sharedStringsFile), "application/xml")
  return Array.from(xml.getElementsByTagName("si")).map((item) =>
    Array.from(item.getElementsByTagName("t")).map((node) => node.textContent ?? "").join(""),
  )
}

type XlsxStyles = {
  dateStyleIndexes: Set<number>
}

function readWorkbookStyles(archive: Record<string, Uint8Array>): XlsxStyles {
  const stylesXml = readOptionalArchiveText(archive, "xl/styles.xml")
  if (!stylesXml) return { dateStyleIndexes: new Set() }

  const parser = new DOMParser()
  const xml = parser.parseFromString(stylesXml, "application/xml")
  const customFormats = new Map<number, string>()

  Array.from(xml.getElementsByTagName("numFmt")).forEach((format) => {
    const id = Number.parseInt(format.getAttribute("numFmtId") ?? "", 10)
    const code = format.getAttribute("formatCode") ?? ""
    if (Number.isFinite(id) && code) customFormats.set(id, code)
  })

  const dateStyleIndexes = new Set<number>()
  const cellXfs = Array.from(xml.getElementsByTagName("cellXfs")[0]?.getElementsByTagName("xf") ?? [])
  cellXfs.forEach((style, index) => {
    const id = Number.parseInt(style.getAttribute("numFmtId") ?? "", 10)
    const customFormat = customFormats.get(id)
    if (isDateNumberFormat(id, customFormat)) dateStyleIndexes.add(index)
  })

  return { dateStyleIndexes }
}

function isDateNumberFormat(numFmtId: number, customFormat: string | undefined) {
  const builtInDateFormats = new Set([14, 15, 16, 17, 22, 27, 30, 36, 45, 46, 47, 50, 57])
  if (builtInDateFormats.has(numFmtId)) return true
  if (!customFormat) return false

  const normalized = customFormat
    .toLowerCase()
    .replace(/"[^"]*"/g, "")
    .replace(/\[[^\]]*]/g, "")
    .replace(/\\./g, "")

  return /[dy]/.test(normalized)
}

function parseWorksheetTable(sheetXml: string, sharedStrings: string[], styles: XlsxStyles) {
  const parser = new DOMParser()
  const xml = parser.parseFromString(sheetXml, "application/xml")
  const rows = Array.from(xml.getElementsByTagName("row"))

  return rows.map((row) => {
    const cells = Array.from(row.getElementsByTagName("c"))
    const values: string[] = []
    cells.forEach((cell) => {
      const ref = cell.getAttribute("r") ?? ""
      const index = cellRefToIndex(ref)
      values[index] = readCellValue(cell, sharedStrings, styles)
    })
    return values.map((value) => value ?? "")
  })
}

function readCellValue(cell: Element, sharedStrings: string[], styles: XlsxStyles) {
  const type = cell.getAttribute("t")
  if (type === "inlineStr") {
    return Array.from(cell.getElementsByTagName("t")).map((node) => node.textContent ?? "").join("")
  }

  const rawValue = cell.getElementsByTagName("v")[0]?.textContent ?? ""
  if (type === "s") {
    const index = Number.parseInt(rawValue, 10)
    return Number.isFinite(index) ? sharedStrings[index] ?? "" : ""
  }
  if (type === "b") return rawValue === "1" ? "true" : "false"
  if (!type && isDateFormattedCell(cell, styles)) {
    return excelSerialDateToIso(rawValue) ?? rawValue
  }
  return rawValue
}

function isDateFormattedCell(cell: Element, styles: XlsxStyles) {
  const styleIndex = Number.parseInt(cell.getAttribute("s") ?? "", 10)
  return Number.isFinite(styleIndex) && styles.dateStyleIndexes.has(styleIndex)
}

function excelSerialDateToIso(value: string) {
  const serial = Number(value)
  if (!Number.isFinite(serial) || serial < 1 || serial > 100000) return null
  const epoch = Date.UTC(1899, 11, 30)
  const date = new Date(epoch + Math.round(serial) * 86400000)
  return date.toISOString().slice(0, 10)
}

function cellRefToIndex(ref: string) {
  const letters = ref.match(/^[A-Z]+/i)?.[0]?.toUpperCase() ?? "A"
  return letters.split("").reduce((total, char) => total * 26 + char.charCodeAt(0) - 64, 0) - 1
}

function detectDelimiter(text: string) {
  const firstLine = text.split(/\r?\n/).find((line) => line.trim() !== "") ?? ""
  const candidates = [";", "\t", ","]
  return candidates.reduce((best, candidate) => countOccurrences(firstLine, candidate) > countOccurrences(firstLine, best) ? candidate : best, ";")
}

function countOccurrences(value: string, needle: string) {
  return value.split(needle).length - 1
}

function parseDelimitedText(text: string, delimiter: string) {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ""
  let inQuotes = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    const nextChar = text[index + 1]

    if (char === "\"") {
      if (inQuotes && nextChar === "\"") {
        cell += "\""
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (!inQuotes && char === delimiter) {
      row.push(cell)
      cell = ""
      continue
    }

    if (!inQuotes && (char === "\n" || char === "\r")) {
      if (char === "\r" && nextChar === "\n") index += 1
      row.push(cell)
      rows.push(row)
      row = []
      cell = ""
      continue
    }

    cell += char
  }

  row.push(cell)
  rows.push(row)
  return rows
}

function cleanHeader(value: string, index: number) {
  const cleaned = value.trim()
  return cleaned || `coluna_${index + 1}`
}

function buildRawRow(headers: string[], row: string[]) {
  return headers.reduce<ImportRawRow>((result, header, index) => {
    const value = normalizeCellValue(row[index] ?? "")
    if (value !== null) result[header] = value
    return result
  }, {})
}

function normalizeCellValue(value: string): ImportCellValue {
  const cleaned = value.trim()
  if (!cleaned) return null
  return cleaned
}

function hasRowValue(row: ImportRawRow) {
  return Object.values(row).some((value) => value !== null && String(value).trim() !== "")
}

function formatCell(value: ImportCellValue | undefined) {
  if (value === undefined || value === null) return ""
  return String(value)
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) return error.message
  return fallback
}
