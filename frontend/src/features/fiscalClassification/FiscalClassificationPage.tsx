import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  ClipboardCheck,
  Copy,
  FileCheck,
  Filter,
  ListFilter,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react"
import { strToU8, zipSync } from "fflate"

import {
  getActiveCompanyId,
  getCompanyDisplayName,
  pickActiveCompanyId,
} from "../../config/activeCompany"
import { getAuthSession } from "../../config/authSession"
import { getCompanies } from "../company/companyApi"
import type { Company } from "../company/types"

import {
  createFiscalClassification,
  getFiscalClassificationAudit,
  getFiscalClassifications,
  getFiscalDiagnostics,
  getFiscalProfiles,
  getFiscalRules,
  updateFiscalClassification,
  type ListFiscalClassificationsParams,
} from "./fiscalClassificationApi"
import type {
  FiscalAppliesTo,
  FiscalAuditEvent,
  FiscalClassification,
  FiscalClassificationCreatePayload,
  FiscalDiagnostics,
  FiscalProfile,
  FiscalRecordStatus,
  FiscalRules,
  FiscalSourceType,
  TaxRegimeScope,
} from "./types"

type FiscalView = "overview" | "list" | "form"

type LoadState = "idle" | "loading" | "success" | "error"
type SaveState = "idle" | "saving" | "success" | "error"
type ExportState = "idle" | "exporting" | "success" | "error"

const PAGE_SIZE = 25
const EXPORT_LIMIT = 5000

type FiscalOverviewMetrics = {
  total: number
  active: number
  products: number
  services: number
  ibsCbs: number
}

type FiscalFormState = {
  company_id: string
  fiscal_profile_id: string
  name: string
  description: string
  item_type: FiscalAppliesTo
  tax_regime: TaxRegimeScope
  ncm: string
  nbs: string
  cest: string
  ex_tipi: string
  origem_mercadoria: string
  cfop_default: string
  cst_icms: string
  cst_pis: string
  cst_cofins: string
  cst_ibs_cbs: string
  cclass_trib: string
  subject_to_icms: boolean
  subject_to_iss: boolean
  subject_to_pis_cofins: boolean
  subject_to_ibs_cbs: boolean
  subject_to_is: boolean
  valid_from: string
  valid_to: string
  status: FiscalRecordStatus
  source: FiscalSourceType
  source_reference: string
  notes: string
}

function getSessionCompanyId() {
  return getAuthSession()?.companyId ?? ""
}


const EMPTY_FORM: FiscalFormState = {
  company_id: getSessionCompanyId() || getActiveCompanyId(),
  fiscal_profile_id: "",
  name: "",
  description: "",
  item_type: "product",
  tax_regime: "simples_nacional",
  ncm: "",
  nbs: "",
  cest: "",
  ex_tipi: "",
  origem_mercadoria: "",
  cfop_default: "",
  cst_icms: "",
  cst_pis: "",
  cst_cofins: "",
  cst_ibs_cbs: "",
  cclass_trib: "",
  subject_to_icms: true,
  subject_to_iss: false,
  subject_to_pis_cofins: true,
  subject_to_ibs_cbs: true,
  subject_to_is: false,
  valid_from: "2026-01-01",
  valid_to: "",
  status: "active",
  source: "manual",
  source_reference: "",
  notes: "",
}

const STATUS_LABELS: Record<FiscalRecordStatus, string> = {
  draft: "Rascunho",
  active: "Ativo",
  inactive: "Inativo",
  blocked: "Bloqueado",
  expired: "Expirado",
}

const APPLIES_TO_LABELS: Record<FiscalAppliesTo, string> = {
  product: "Produto",
  service: "Serviço",
  both: "Ambos",
  operation: "Operação",
}

const TAX_REGIME_LABELS: Record<TaxRegimeScope, string> = {
  simples_nacional: "Simples Nacional",
  lucro_presumido: "Lucro Presumido",
  lucro_real: "Lucro Real",
  mei: "MEI",
  producer: "Produtor",
  foreign: "Exterior",
  unknown: "Não informado",
  not_applicable: "Não aplicável",
}

const SOURCE_LABELS: Record<FiscalSourceType, string> = {
  manual: "Manual",
  accountant: "Contador",
  official_rule: "Regra oficial",
  imported_table: "Tabela importada",
  integration: "Integração",
  legacy: "Legado",
  unknown: "Desconhecida",
}

const ORIGEM_LABELS: Record<string, string> = {
  "0": "0 – Nacional",
  "1": "1 – Estrangeira (importação direta)",
  "2": "2 – Estrangeira (mercado interno)",
  "3": "3 – Nacional (conteúdo importado > 40%)",
  "4": "4 – Nacional (processo produtivo básico)",
  "5": "5 – Nacional (conteúdo importado ≤ 40%)",
  "6": "6 – Estrangeira direta, sem similar nacional (CAMEX)",
  "7": "7 – Estrangeira mercado interno, sem similar nacional (CAMEX)",
  "8": "8 – Nacional (conteúdo importado > 70%)",
}

const STATUS_OPTIONS: FiscalRecordStatus[] = [
  "draft",
  "active",
  "inactive",
  "blocked",
  "expired",
]

const APPLIES_TO_OPTIONS: FiscalAppliesTo[] = [
  "product",
  "service",
  "both",
  "operation",
]

const TAX_REGIME_OPTIONS: TaxRegimeScope[] = [
  "simples_nacional",
  "lucro_presumido",
  "lucro_real",
  "mei",
  "producer",
  "foreign",
  "unknown",
  "not_applicable",
]

const SOURCE_OPTIONS: FiscalSourceType[] = [
  "manual",
  "accountant",
  "official_rule",
  "imported_table",
  "integration",
  "legacy",
  "unknown",
]

const ORIGEM_OPTIONS = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]

const FISCAL_AUDIT_ACTION_LABEL: Record<string, string> = {
  created: "Criado",
  updated: "Atualizado",
  deleted: "Removido",
}

export function FiscalClassificationPage() {
  const [view, setView] = useState<FiscalView>("overview")
  const [loadState, setLoadState] = useState<LoadState>("idle")
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [exportState, setExportState] = useState<ExportState>("idle")
  const [modalMessage, setModalMessage] = useState<string | null>(null)

  const [classifications, setClassifications] = useState<FiscalClassification[]>([])
  const [totalClassifications, setTotalClassifications] = useState(0)
  const [currentPage, setCurrentPage] = useState(0)
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [overviewMetrics, setOverviewMetrics] = useState<FiscalOverviewMetrics>({
    total: 0,
    active: 0,
    products: 0,
    services: 0,
    ibsCbs: 0,
  })
  const [profiles, setProfiles] = useState<FiscalProfile[]>([])
  const [companies, setCompanies] = useState<Company[]>([])
  const [, setRules] = useState<FiscalRules | null>(null)
  const [, setDiagnostics] = useState<FiscalDiagnostics | null>(null)
  const [auditEvents, setAuditEvents] = useState<FiscalAuditEvent[]>([])

  const [editingClassificationId, setEditingClassificationId] = useState<
    string | null
  >(null)

  const sessionCompanyId = getSessionCompanyId()
  const session = getAuthSession()
  const canWriteFiscal = Boolean(
    session?.roles.includes("admin") || session?.permissions.includes("fiscal.write"),
  )
  const [activeCompanyId, setActiveCompanyIdState] = useState(() => sessionCompanyId || getActiveCompanyId())
  const [form, setForm] = useState<FiscalFormState>(() => ({
    ...EMPTY_FORM,
    company_id: sessionCompanyId || getActiveCompanyId(),
  }))

  const activeCompany = useMemo(
    () => companies.find((company) => company.id === activeCompanyId) ?? null,
    [activeCompanyId, companies],
  )

  const activeCompanyName = getCompanyDisplayName(activeCompany)

  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<"all" | FiscalRecordStatus>(
    "all",
  )
  const [itemTypeFilter, setItemTypeFilter] = useState<"all" | FiscalAppliesTo>(
    "all",
  )
  const [taxRegimeFilter, setTaxRegimeFilter] = useState<"all" | TaxRegimeScope>(
    "all",
  )
  const [ncmFilter, setNcmFilter] = useState("")
  const [nbsFilter, setNbsFilter] = useState("")
  const [cfopFilter, setCfopFilter] = useState("")
  const [cstIbsCbsFilter, setCstIbsCbsFilter] = useState("")
  const [cclassTribFilter, setCclassTribFilter] = useState("")
  const [validityFilter, setValidityFilter] = useState<
    "all" | "current" | "future" | "expired"
  >("all")
  const [subjectToIbsCbsFilter, setSubjectToIbsCbsFilter] = useState<
    "all" | "yes" | "no"
  >("all")
  const [subjectToIsFilter, setSubjectToIsFilter] = useState<
    "all" | "yes" | "no"
  >("all")

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearch(search.trim())
    }, 350)

    return () => window.clearTimeout(timeoutId)
  }, [search])

  const todayIso = useMemo(() => new Date().toISOString().slice(0, 10), [])

  const classificationQuery = useMemo<ListFiscalClassificationsParams>(() => {
    const params: ListFiscalClassificationsParams = {
      company_id: activeCompanyId,
      limit: PAGE_SIZE,
      offset: currentPage * PAGE_SIZE,
    }

    if (debouncedSearch) params.search = debouncedSearch
    if (statusFilter !== "all") params.status_filter = statusFilter
    if (itemTypeFilter !== "all") params.item_type = itemTypeFilter
    if (taxRegimeFilter !== "all") params.tax_regime = taxRegimeFilter
    if (ncmFilter) params.ncm = ncmFilter
    if (nbsFilter) params.nbs = nbsFilter
    if (cfopFilter) params.cfop = cfopFilter
    if (cstIbsCbsFilter) params.cst_ibs_cbs = cstIbsCbsFilter
    if (cclassTribFilter) params.cclass_trib = cclassTribFilter
    if (subjectToIbsCbsFilter !== "all") {
      params.subject_to_ibs_cbs = subjectToIbsCbsFilter === "yes"
    }
    if (subjectToIsFilter !== "all") {
      params.subject_to_is = subjectToIsFilter === "yes"
    }
    if (validityFilter !== "all") {
      params.validity_filter = validityFilter
      params.valid_on = todayIso
    }

    return params
  }, [
    activeCompanyId,
    cclassTribFilter,
    cfopFilter,
    cstIbsCbsFilter,
    currentPage,
    debouncedSearch,
    itemTypeFilter,
    nbsFilter,
    ncmFilter,
    statusFilter,
    subjectToIbsCbsFilter,
    subjectToIsFilter,
    taxRegimeFilter,
    todayIso,
    validityFilter,
  ])

  const loadOverviewMetrics = useCallback(async (companyId: string) => {
    if (!companyId) {
      setOverviewMetrics({ total: 0, active: 0, products: 0, services: 0, ibsCbs: 0 })
      return
    }

    const [total, active, products, services, ibsCbs] = await Promise.all([
      getFiscalClassifications({ company_id: companyId, limit: 1, offset: 0 }),
      getFiscalClassifications({ company_id: companyId, status_filter: "active", limit: 1, offset: 0 }),
      getFiscalClassifications({ company_id: companyId, item_type: "product", limit: 1, offset: 0 }),
      getFiscalClassifications({ company_id: companyId, item_type: "service", limit: 1, offset: 0 }),
      getFiscalClassifications({ company_id: companyId, subject_to_ibs_cbs: true, limit: 1, offset: 0 }),
    ])

    setOverviewMetrics({
      total: total.data.total,
      active: active.data.total,
      products: products.data.total,
      services: services.data.total,
      ibsCbs: ibsCbs.data.total,
    })
  }, [])

  const loadFiscalData = useCallback(async () => {
    try {
      const [companiesResponse, rulesResponse, diagnosticsResponse] =
        await Promise.all([getCompanies(), getFiscalRules(), getFiscalDiagnostics()])

      const companyList = companiesResponse.data
      const visibleCompanies = sessionCompanyId
        ? companyList.filter((company) => company.id === sessionCompanyId)
        : companyList
      const resolvedCompanyId = pickActiveCompanyId(
        visibleCompanies,
        sessionCompanyId || activeCompanyId,
      )

      setCompanies(visibleCompanies)
      setRules(rulesResponse.data)
      setDiagnostics(diagnosticsResponse.data)

      if (resolvedCompanyId !== activeCompanyId) {
        setActiveCompanyIdState(resolvedCompanyId)
      }

      setForm((current) => ({
        ...current,
        company_id: resolvedCompanyId,
      }))

      if (visibleCompanies.length === 0) {
        setClassifications([])
        setTotalClassifications(0)
        setOverviewMetrics({ total: 0, active: 0, products: 0, services: 0, ibsCbs: 0 })
        setLoadState("success")
        return
      }

      const profilesResponse = await getFiscalProfiles({
        company_id: resolvedCompanyId,
        limit: 5000,
        offset: 0,
      })

      setProfiles(profilesResponse.data.items ?? [])
      await loadOverviewMetrics(resolvedCompanyId)
    } catch (error) {
      setLoadState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar a classificação fiscal.",
      )
    }
  }, [activeCompanyId, loadOverviewMetrics, sessionCompanyId])

  const loadClassifications = useCallback(async () => {
    if (!activeCompanyId) {
      setClassifications([])
      setTotalClassifications(0)
      setLoadState("success")
      return
    }

    setLoadState("loading")

    try {
      const response = await getFiscalClassifications(classificationQuery)
      setClassifications(response.data.items)
      setTotalClassifications(response.data.total)
      setLoadState("success")
    } catch (error) {
      setClassifications([])
      setTotalClassifications(0)
      setLoadState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar a lista fiscal.",
      )
    }
  }, [activeCompanyId, classificationQuery])

  useEffect(() => {
    void loadFiscalData()
  }, [loadFiscalData])

  useEffect(() => {
    void loadClassifications()
  }, [loadClassifications])

  useEffect(() => {
    setCurrentPage(0)
  }, [
    cclassTribFilter,
    cfopFilter,
    cstIbsCbsFilter,
    debouncedSearch,
    itemTypeFilter,
    nbsFilter,
    ncmFilter,
    statusFilter,
    subjectToIbsCbsFilter,
    subjectToIsFilter,
    taxRegimeFilter,
    validityFilter,
  ])

  const activeFiltersCount = [
    search.trim(),
    statusFilter !== "all",
    itemTypeFilter !== "all",
    taxRegimeFilter !== "all",
    ncmFilter,
    nbsFilter,
    cfopFilter,
    cstIbsCbsFilter,
    cclassTribFilter,
    validityFilter !== "all",
    subjectToIbsCbsFilter !== "all",
    subjectToIsFilter !== "all",
  ].filter(Boolean).length

  function updateFormField<K extends keyof FiscalFormState>(
    field: K,
    value: FiscalFormState[K],
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function handleItemTypeChange(nextType: FiscalAppliesTo) {
    setForm((current) => ({
      ...current,
      item_type: nextType,
      ncm: nextType === "service" ? "" : current.ncm,
      nbs: nextType === "product" ? "" : current.nbs,
      subject_to_icms: nextType === "product",
      subject_to_iss: nextType === "service",
    }))
  }

  function openNewClassification(itemType: FiscalAppliesTo = "product") {
    if (!canWriteFiscal) {
      setModalMessage("Usuário sem permissão fiscal.write para criar classificação fiscal.")
      return
    }

    setEditingClassificationId(null)
    setAuditEvents([])
    setForm({
      ...EMPTY_FORM,
      company_id: activeCompanyId,
      item_type: itemType,
      ncm: itemType === "service" ? "" : EMPTY_FORM.ncm,
      nbs: itemType === "product" ? "" : EMPTY_FORM.nbs,
      subject_to_icms: itemType === "product",
      subject_to_iss: itemType === "service",
    })
    setSaveState("idle")
    setView("form")
  }

  async function openEditClassification(classification: FiscalClassification) {
    setEditingClassificationId(classification.id)
    setSaveState("idle")
    setForm(syncFormFromClassification(classification))
    setView("form")

    try {
      const auditResponse = await getFiscalClassificationAudit(classification.id)
      setAuditEvents(auditResponse.data.items)
    } catch {
      setAuditEvents([])
    }
  }

  function openDuplicateClassification(classification: FiscalClassification) {
    if (!canWriteFiscal) {
      setModalMessage("Usuário sem permissão fiscal.write para duplicar classificação fiscal.")
      return
    }

    setEditingClassificationId(null)
    setAuditEvents([])
    const base = syncFormFromClassification(classification)
    setForm({
      ...base,
      name: `${base.name} (cópia)`,
      status: "draft",
    })
    setSaveState("idle")
    setView("form")
  }

  function validateForm() {
    if (!form.company_id.trim()) {
      return "Empresa é obrigatória."
    }

    if (!form.company_id.startsWith("emp_")) {
      return "company_id deve começar com emp_."
    }

    if (!form.name.trim()) {
      return "Nome da classificação fiscal é obrigatório."
    }

    if (form.fiscal_profile_id && !form.fiscal_profile_id.startsWith("fprof_")) {
      return "Perfil fiscal deve começar com fprof_."
    }

    if (form.item_type === "product" && !form.ncm.trim()) {
      return "Classificação de produto deve informar NCM."
    }

    if (form.item_type === "service" && !form.nbs.trim()) {
      return "Classificação de serviço deve informar NBS."
    }

    if (form.ncm && !/^\d{1,8}$/.test(form.ncm)) {
      return "NCM deve conter apenas dígitos e no máximo 8 caracteres."
    }

    if (form.cest && !/^\d{1,7}$/.test(form.cest)) {
      return "CEST deve conter apenas dígitos e no máximo 7 caracteres."
    }

    if (form.ex_tipi && !/^\d{1,3}$/.test(form.ex_tipi)) {
      return "EX TIPI deve conter apenas dígitos e no máximo 3 caracteres."
    }

    if (form.cfop_default && !/^\d{1,4}$/.test(form.cfop_default)) {
      return "CFOP deve conter apenas dígitos e no máximo 4 caracteres."
    }

    if (form.origem_mercadoria && !/^[0-8]$/.test(form.origem_mercadoria)) {
      return "Origem da mercadoria deve ser um dígito entre 0 e 8."
    }

    if (form.valid_from && form.valid_to && form.valid_to < form.valid_from) {
      return "Vigência final não pode ser anterior à vigência inicial."
    }

    return null
  }

  async function handleSave() {
    if (!canWriteFiscal) {
      setModalMessage("Usuário sem permissão fiscal.write para salvar classificação fiscal.")
      return
    }

    const validationError = validateForm()

    if (validationError) {
      setModalMessage(validationError)
      return
    }

    setSaveState("saving")

    try {
      const payload = buildClassificationPayload(form)

      if (editingClassificationId) {
        const response = await updateFiscalClassification(editingClassificationId, payload)
        const auditResponse = await getFiscalClassificationAudit(response.data.id)
        setAuditEvents(auditResponse.data.items)
      } else {
        const response = await createFiscalClassification(payload)
        setEditingClassificationId(response.data.id)
        const auditResponse = await getFiscalClassificationAudit(response.data.id)
        setAuditEvents(auditResponse.data.items)
      }

      await Promise.all([
        loadClassifications(),
        loadOverviewMetrics(activeCompanyId),
      ])
      setSaveState("success")
      setModalMessage("Classificação fiscal salva com sucesso.")
    } catch (error) {
      setSaveState("error")
      setModalMessage(
        error instanceof Error
          ? error.message
          : "Não foi possível salvar a classificação fiscal.",
      )
    }
  }

  function resetFilters() {
    setSearch("")
    setStatusFilter("all")
    setItemTypeFilter("all")
    setTaxRegimeFilter("all")
    setNcmFilter("")
    setNbsFilter("")
    setCfopFilter("")
    setCstIbsCbsFilter("")
    setCclassTribFilter("")
    setValidityFilter("all")
    setSubjectToIbsCbsFilter("all")
    setSubjectToIsFilter("all")
    setCurrentPage(0)
  }

  async function fetchExportClassifications() {
    if (totalClassifications > EXPORT_LIMIT) {
      setModalMessage(
        `Refine os filtros para exportar até ${EXPORT_LIMIT} classificações por arquivo.`,
      )
      return null
    }

    const response = await getFiscalClassifications({
      ...classificationQuery,
      limit: EXPORT_LIMIT,
      offset: 0,
    })

    return response.data.items
  }

  async function handleExportCsv() {
    setExportState("exporting")

    try {
      const exportItems = await fetchExportClassifications()
      if (!exportItems) {
        setExportState("idle")
        return
      }

      const csv = buildCsv(exportItems)
      downloadBlob(
        new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }),
        `kovir-classificacoes-fiscais-${dateStamp()}.csv`,
      )
      setExportState("success")
    } catch {
      setExportState("error")
      setModalMessage("Não foi possível exportar CSV.")
    }
  }

  async function handleExportXlsx() {
    setExportState("exporting")

    try {
      const exportItems = await fetchExportClassifications()
      if (!exportItems) {
        setExportState("idle")
        return
      }

      const xlsxBlob = buildSimpleXlsx(
        "ClassificacoesFiscais",
        exportRows(exportItems),
      )
      downloadBlob(xlsxBlob, `kovir-classificacoes-fiscais-${dateStamp()}.xlsx`)
      setExportState("success")
    } catch {
      setExportState("error")
      setModalMessage("Não foi possível exportar XLSX.")
    }
  }

  return (
    <div className="space-y-6">
      <ValidationModal
        message={modalMessage}
        onClose={() => setModalMessage(null)}
      />

      <section className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--color-text-muted)]">
              Bloco 4
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-[var(--color-text)]">
              Classificação Fiscal
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-muted)]">
              Classificações fiscais parametrizáveis para produtos, serviços e operações.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                void loadFiscalData()
                void loadClassifications()
                void loadOverviewMetrics(activeCompanyId)
              }}
              className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface-elevated)] active:scale-[0.98]"
            >
              <RefreshCw className="h-4 w-4" />
              Recarregar
            </button>
          </div>
        </div>

        <FiscalModuleTabs
          view={view}
          onChange={setView}
          onNewClassification={() => openNewClassification("product")}
          canWrite={canWriteFiscal}
        />
      </section>

      {view === "overview" ? (
        <OverviewPanel
          metrics={overviewMetrics}
          onCreateProduct={() => openNewClassification("product")}
          onCreateService={() => openNewClassification("service")}
          onGoToList={() => setView("list")}
          canWrite={canWriteFiscal}
        />
      ) : null}

      {view === "list" ? (
        <ListPanel
          classifications={classifications}
          total={totalClassifications}
          page={currentPage}
          pageSize={PAGE_SIZE}
          loadState={loadState}
          exportState={exportState}
          search={search}
          statusFilter={statusFilter}
          itemTypeFilter={itemTypeFilter}
          taxRegimeFilter={taxRegimeFilter}
          ncmFilter={ncmFilter}
          nbsFilter={nbsFilter}
          cfopFilter={cfopFilter}
          cstIbsCbsFilter={cstIbsCbsFilter}
          cclassTribFilter={cclassTribFilter}
          validityFilter={validityFilter}
          subjectToIbsCbsFilter={subjectToIbsCbsFilter}
          subjectToIsFilter={subjectToIsFilter}
          activeFiltersCount={activeFiltersCount}
          onSearchChange={setSearch}
          onStatusFilterChange={setStatusFilter}
          onItemTypeFilterChange={setItemTypeFilter}
          onTaxRegimeFilterChange={setTaxRegimeFilter}
          onNcmFilterChange={setNcmFilter}
          onNbsFilterChange={setNbsFilter}
          onCfopFilterChange={setCfopFilter}
          onCstIbsCbsFilterChange={setCstIbsCbsFilter}
          onCclassTribFilterChange={setCclassTribFilter}
          onValidityFilterChange={setValidityFilter}
          onSubjectToIbsCbsFilterChange={setSubjectToIbsCbsFilter}
          onSubjectToIsFilterChange={setSubjectToIsFilter}
          onResetFilters={resetFilters}
          onExportCsv={() => void handleExportCsv()}
          onExportXlsx={() => void handleExportXlsx()}
          onEdit={(classification) => void openEditClassification(classification)}
          onDuplicate={openDuplicateClassification}
          onPageChange={setCurrentPage}
          canWrite={canWriteFiscal}
        />
      ) : null}

      {view === "form" ? (
        <FormPanel
          form={form}
          saveState={saveState}
          editingClassificationId={editingClassificationId}
          auditEvents={auditEvents}
          activeCompanyId={activeCompanyId}
          activeCompanyName={activeCompanyName}
          profiles={profiles}
          canWrite={canWriteFiscal}
          onChange={updateFormField}
          onItemTypeChange={handleItemTypeChange}
          onSave={() => void handleSave()}
        />
      ) : null}
    </div>
  )
}

function FiscalModuleTabs({
  view,
  onChange,
  onNewClassification,
  canWrite,
}: {
  view: FiscalView
  onChange: (view: FiscalView) => void
  onNewClassification: () => void
  canWrite: boolean
}) {
  const tabs: Array<{
    id: FiscalView
    label: string
  }> = [
    {
      id: "overview",
      label: "Visão geral",
    },
    {
      id: "list",
      label: "Listagem",
    },
  ]

  return (
    <div className="mt-8 flex flex-wrap items-center gap-4">
      {tabs.map((tab) => {
        const active = view === tab.id

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={[
              "min-w-[150px] rounded-3xl border px-8 py-5 text-center text-lg font-extrabold transition duration-200",
              "hover:-translate-y-1 hover:shadow-lg active:scale-[0.97]",
              active
                ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary)] shadow-sm"
                : "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text)] hover:border-[var(--color-primary)] hover:bg-[var(--color-surface-elevated)]",
            ].join(" ")}
          >
            {tab.label}
          </button>
        )
      })}

      {canWrite ? (
        <button
          type="button"
          onClick={onNewClassification}
          className="inline-flex min-w-[175px] items-center justify-center gap-2 rounded-3xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-4 text-center text-base font-extrabold text-white shadow-lg transition duration-200 hover:-translate-y-1 hover:bg-[var(--color-primary-hover)] hover:shadow-xl active:scale-[0.97]"
        >
          <Plus className="h-4 w-4" />
          Nova classificação
        </button>
      ) : null}
    </div>
  )
}

function OverviewPanel({
  metrics,
  onCreateProduct,
  onCreateService,
  onGoToList,
  canWrite,
}: {
  metrics: FiscalOverviewMetrics
  onCreateProduct: () => void
  onCreateService: () => void
  onGoToList: () => void
  canWrite: boolean
}) {
  return (
    <section className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Classificações"
          value={metrics.total}
          helper="Registros fiscais cadastrados"
        />
        <MetricCard
          label="Ativas"
          value={metrics.active}
          helper="Disponíveis para uso"
        />
        <MetricCard
          label="Produtos / Serviços"
          value={`${metrics.products}/${metrics.services}`}
          helper="Separação fiscal"
        />
        <MetricCard
          label="IBS/CBS"
          value={metrics.ibsCbs}
          helper="Marcadas para Reforma Tributária"
        />
      </div>

      <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-[var(--color-primary-soft)] p-3 text-[var(--color-primary)]">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            Nova classificação
          </h2>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <button
            type="button"
            onClick={onCreateProduct}
            disabled={!canWrite}
            className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left transition hover:-translate-y-0.5 hover:shadow-sm active:scale-[0.98]"
          >
            <FileCheck className="h-5 w-5 text-[var(--color-primary)]" />
            <span className="mt-3 block text-sm font-semibold text-[var(--color-text)]">
              Produto
            </span>
            <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
              NCM, CEST, EX TIPI e campos fiscais de mercadoria
            </span>
          </button>

          <button
            type="button"
            onClick={onCreateService}
            disabled={!canWrite}
            className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left transition hover:-translate-y-0.5 hover:shadow-sm active:scale-[0.98]"
          >
            <ClipboardCheck className="h-5 w-5 text-[var(--color-primary)]" />
            <span className="mt-3 block text-sm font-semibold text-[var(--color-text)]">
              Serviço
            </span>
            <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
              NBS, ISS e Reforma Tributária
            </span>
          </button>

          <button
            type="button"
            onClick={onGoToList}
            className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-left transition hover:-translate-y-0.5 hover:shadow-sm active:scale-[0.98]"
          >
            <ListFilter className="h-5 w-5 text-[var(--color-primary)]" />
            <span className="mt-3 block text-sm font-semibold text-[var(--color-text)]">
              Listagem
            </span>
            <span className="mt-1 block text-xs leading-5 text-[var(--color-text-muted)]">
              Consulte, filtre e exporte classificações fiscais
            </span>
          </button>
        </div>
      </div>
    </section>
  )
}

function ListPanel({
  classifications,
  total,
  page,
  pageSize,
  loadState,
  exportState,
  search,
  statusFilter,
  itemTypeFilter,
  taxRegimeFilter,
  ncmFilter,
  nbsFilter,
  cfopFilter,
  cstIbsCbsFilter,
  cclassTribFilter,
  validityFilter,
  subjectToIbsCbsFilter,
  subjectToIsFilter,
  activeFiltersCount,
  onSearchChange,
  onStatusFilterChange,
  onItemTypeFilterChange,
  onTaxRegimeFilterChange,
  onNcmFilterChange,
  onNbsFilterChange,
  onCfopFilterChange,
  onCstIbsCbsFilterChange,
  onCclassTribFilterChange,
  onValidityFilterChange,
  onSubjectToIbsCbsFilterChange,
  onSubjectToIsFilterChange,
  onResetFilters,
  onExportCsv,
  onExportXlsx,
  onEdit,
  onDuplicate,
  onPageChange,
  canWrite,
}: {
  classifications: FiscalClassification[]
  total: number
  page: number
  pageSize: number
  loadState: LoadState
  exportState: ExportState
  search: string
  statusFilter: "all" | FiscalRecordStatus
  itemTypeFilter: "all" | FiscalAppliesTo
  taxRegimeFilter: "all" | TaxRegimeScope
  ncmFilter: string
  nbsFilter: string
  cfopFilter: string
  cstIbsCbsFilter: string
  cclassTribFilter: string
  validityFilter: "all" | "current" | "future" | "expired"
  subjectToIbsCbsFilter: "all" | "yes" | "no"
  subjectToIsFilter: "all" | "yes" | "no"
  activeFiltersCount: number
  onSearchChange: (value: string) => void
  onStatusFilterChange: (value: "all" | FiscalRecordStatus) => void
  onItemTypeFilterChange: (value: "all" | FiscalAppliesTo) => void
  onTaxRegimeFilterChange: (value: "all" | TaxRegimeScope) => void
  onNcmFilterChange: (value: string) => void
  onNbsFilterChange: (value: string) => void
  onCfopFilterChange: (value: string) => void
  onCstIbsCbsFilterChange: (value: string) => void
  onCclassTribFilterChange: (value: string) => void
  onValidityFilterChange: (value: "all" | "current" | "future" | "expired") => void
  onSubjectToIbsCbsFilterChange: (value: "all" | "yes" | "no") => void
  onSubjectToIsFilterChange: (value: "all" | "yes" | "no") => void
  onResetFilters: () => void
  onExportCsv: () => void
  onExportXlsx: () => void
  onEdit: (classification: FiscalClassification) => void
  onDuplicate: (classification: FiscalClassification) => void
  onPageChange: (page: number) => void
  canWrite: boolean
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const canGoPrevious = page > 0 && loadState !== "loading"
  const canGoNext = page + 1 < pageCount && loadState !== "loading"

  return (
    <section className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-sm">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-[var(--color-primary)]" />
            <h2 className="text-lg font-semibold text-[var(--color-text)]">
              Listagem fiscal
            </h2>
          </div>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            {classifications.length} de {total} classificações exibidas. Filtros
            ativos: {activeFiltersCount}. A exportação respeita os filtros do backend.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onExportCsv}
            disabled={exportState === "exporting" || total === 0}
            className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface-elevated)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Exportar CSV
          </button>

          <button
            type="button"
            onClick={onExportXlsx}
            disabled={exportState === "exporting" || total === 0}
            className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface-elevated)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Exportar XLSX
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-3 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <input
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="input-like w-full"
            placeholder="Buscar por nome, NCM, NBS, CFOP, CST ou classificação tributária..."
          />
        </div>

        <select
          value={statusFilter}
          onChange={(event) =>
            onStatusFilterChange(event.target.value as "all" | FiscalRecordStatus)
          }
          className="input-like"
        >
          <option value="all">Todos os status</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </select>

        <select
          value={itemTypeFilter}
          onChange={(event) =>
            onItemTypeFilterChange(event.target.value as "all" | FiscalAppliesTo)
          }
          className="input-like"
        >
          <option value="all">Todos os tipos</option>
          {APPLIES_TO_OPTIONS.map((type) => (
            <option key={type} value={type}>
              {APPLIES_TO_LABELS[type]}
            </option>
          ))}
        </select>

        <select
          value={taxRegimeFilter}
          onChange={(event) =>
            onTaxRegimeFilterChange(event.target.value as "all" | TaxRegimeScope)
          }
          className="input-like"
        >
          <option value="all">Todos os regimes</option>
          {TAX_REGIME_OPTIONS.map((regime) => (
            <option key={regime} value={regime}>
              {TAX_REGIME_LABELS[regime]}
            </option>
          ))}
        </select>

        <DigitsInput
          value={ncmFilter}
          onChange={onNcmFilterChange}
          maxLength={8}
          placeholder="NCM"
          label="Filtro NCM"
        />

        <input
          value={nbsFilter}
          onChange={(event) => onNbsFilterChange(event.target.value)}
          className="input-like"
          placeholder="NBS"
        />

        <DigitsInput
          value={cfopFilter}
          onChange={onCfopFilterChange}
          maxLength={4}
          placeholder="CFOP"
          label="Filtro CFOP"
        />

        <input
          value={cstIbsCbsFilter}
          onChange={(event) => onCstIbsCbsFilterChange(event.target.value)}
          className="input-like"
          placeholder="CST IBS/CBS"
        />

        <input
          value={cclassTribFilter}
          onChange={(event) => onCclassTribFilterChange(event.target.value)}
          className="input-like"
          placeholder="Classificação tributária"
        />

        <select
          value={validityFilter}
          onChange={(event) =>
            onValidityFilterChange(
              event.target.value as "all" | "current" | "future" | "expired",
            )
          }
          className="input-like"
        >
          <option value="all">Todas as vigências</option>
          <option value="current">Vigentes</option>
          <option value="future">Futuras</option>
          <option value="expired">Expiradas</option>
        </select>

        <select
          value={subjectToIbsCbsFilter}
          onChange={(event) =>
            onSubjectToIbsCbsFilterChange(
              event.target.value as "all" | "yes" | "no",
            )
          }
          className="input-like"
        >
          <option value="all">IBS/CBS: todos</option>
          <option value="yes">Sujeito a IBS/CBS</option>
          <option value="no">Não sujeito</option>
        </select>

        <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
          <select
            value={subjectToIsFilter}
            onChange={(event) =>
              onSubjectToIsFilterChange(event.target.value as "all" | "yes" | "no")
            }
            className="input-like"
          >
            <option value="all">IS: todos</option>
            <option value="yes">Sujeito a IS</option>
            <option value="no">Não sujeito</option>
          </select>

          <button
            type="button"
            onClick={onResetFilters}
            className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-semibold text-[var(--color-text-muted)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-text)] active:scale-[0.98]"
          >
            Limpar filtros
          </button>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {loadState === "loading" ? (
          <div className="flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] p-4 text-sm text-[var(--color-text-muted)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Carregando classificações fiscais...
          </div>
        ) : null}

        {loadState !== "loading" && classifications.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[var(--color-border-soft)] p-6 text-sm text-[var(--color-text-muted)]">
            Nenhuma classificação fiscal encontrada para os filtros atuais.
          </div>
        ) : null}

        {classifications.map((classification) => (
          <div
            key={classification.id}
            className="grid w-full gap-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 xl:grid-cols-[1.2fr_0.6fr_0.7fr_0.9fr_0.9fr_auto]"
          >
            <button
              type="button"
              onClick={() => onEdit(classification)}
              className="col-span-full grid gap-4 text-left xl:col-span-5 xl:grid-cols-[1.2fr_0.6fr_0.7fr_0.9fr_0.9fr] xl:gap-4"
            >
              <div>
                <p className="font-semibold text-[var(--color-text)]">
                  {classification.name}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {classification.description || "Sem descrição"} · {classification.id}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Atualizado {formatDateTime(classification.updated_at)}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                  Tipo
                </p>
                <p className="mt-1 text-sm text-[var(--color-text)]">
                  {APPLIES_TO_LABELS[classification.item_type]}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                  Status
                </p>
                <span className="mt-1 inline-flex rounded-full border border-[var(--color-border-soft)] px-3 py-1 text-xs font-semibold text-[var(--color-text)]">
                  {STATUS_LABELS[classification.status]}
                </span>
                <ValidityBadge
                  validFrom={classification.valid_from}
                  validTo={classification.valid_to}
                />
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                  Fiscal
                </p>
                <p className="mt-1 text-sm text-[var(--color-text)]">
                  {classification.ncm
                    ? `NCM ${classification.ncm}`
                    : classification.nbs
                      ? `NBS ${classification.nbs}`
                      : "Sem NCM/NBS"}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  CFOP {classification.cfop_default || "NI"} · CST IBS/CBS{" "}
                  {classification.cst_ibs_cbs || "NI"}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase text-[var(--color-text-muted)]">
                  Reforma
                </p>
                <p className="mt-1 text-sm text-[var(--color-text)]">
                  Class. tributária {classification.cclass_trib || "NI"}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  IBS/CBS: {classification.subject_to_ibs_cbs ? "sim" : "não"} ·
                  IS: {classification.subject_to_is ? "sim" : "não"}
                </p>
              </div>
            </button>

            <div className="flex items-center justify-end xl:col-span-1">
              <button
                type="button"
                title="Duplicar classificação"
                onClick={() => onDuplicate(classification)}
                disabled={!canWrite}
                className="rounded-2xl border border-[var(--color-border-soft)] p-2 text-[var(--color-text-muted)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface)] hover:text-[var(--color-text)] active:scale-[0.96]"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}

        {total > 0 ? (
          <div className="flex flex-col gap-3 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4 text-sm text-[var(--color-text-muted)] sm:flex-row sm:items-center sm:justify-between">
            <span>
              Página {page + 1} de {pageCount} · {total} registro(s) encontrados.
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onPageChange(page - 1)}
                disabled={!canGoPrevious}
                className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-surface)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Anterior
              </button>
              <button
                type="button"
                onClick={() => onPageChange(page + 1)}
                disabled={!canGoNext}
                className="rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-surface)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Próxima
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function FormPanel({
  form,
  saveState,
  editingClassificationId,
  auditEvents,
  activeCompanyId,
  activeCompanyName,
  profiles,
  canWrite,
  onChange,
  onItemTypeChange,
  onSave,
}: {
  form: FiscalFormState
  saveState: SaveState
  editingClassificationId: string | null
  auditEvents: FiscalAuditEvent[]
  activeCompanyId: string
  activeCompanyName: string
  profiles: FiscalProfile[]
  canWrite: boolean
  onChange: <K extends keyof FiscalFormState>(
    field: K,
    value: FiscalFormState[K],
  ) => void
  onItemTypeChange: (value: FiscalAppliesTo) => void
  onSave: () => void
}) {
  return (
    <section className="grid gap-6 xl:grid-cols-[260px_1fr]">
      <aside className="h-fit rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
          Seções
        </p>

        <nav className="mt-4 space-y-2 text-sm">
          {[
            ["dados-gerais", "Dados gerais"],
            ["aplicacao", "Aplicação"],
            ["classificacao", "Classificação atual"],
            ["nfe", "NF-e / Substituição"],
            ["reforma", "Reforma Tributária"],
            ["vigencia", "Vigência e fonte"],
            ["auditoria", "Auditoria"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={`#${href}`}
              className="block rounded-2xl px-4 py-2 font-medium text-[var(--color-text-muted)] transition hover:-translate-y-0.5 hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-text)] active:scale-[0.98]"
            >
              {label}
            </a>
          ))}
        </nav>
      </aside>

      <div className="space-y-6">
        <FormSection
          id="dados-gerais"
          title="Dados gerais"
        >
          <Field label="Empresa da sessão *">
            <select
              value={form.company_id || activeCompanyId}
              disabled
              className="input-like"
            >
              <option value={form.company_id || activeCompanyId}>
                {activeCompanyName || "Empresa não identificada"} - {form.company_id || activeCompanyId}
              </option>
            </select>
          </Field>

          <Field label="Nome *">
            <input
              value={form.name}
              onChange={(event) => onChange("name", event.target.value)}
              className="input-like"
              placeholder="Classificação fiscal produto padrão"
            />
          </Field>

          <Field label="Descrição">
            <textarea
              value={form.description}
              onChange={(event) => onChange("description", event.target.value)}
              className="input-like min-h-24"
              placeholder="Explique quando esta classificação deve ser usada."
            />
          </Field>

          <Field label="Status">
            <select
              value={form.status}
              onChange={(event) =>
                onChange("status", event.target.value as FiscalRecordStatus)
              }
              className="input-like"
            >
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </Field>
        </FormSection>

        <FormSection
          id="aplicacao"
          title="Aplicação"
        >
          <Field label="Tipo *">
            <select
              value={form.item_type}
              onChange={(event) =>
                onItemTypeChange(event.target.value as FiscalAppliesTo)
              }
              className="input-like"
            >
              {APPLIES_TO_OPTIONS.map((type) => (
                <option key={type} value={type}>
                  {APPLIES_TO_LABELS[type]}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Regime tributário">
            <select
              value={form.tax_regime}
              onChange={(event) =>
                onChange("tax_regime", event.target.value as TaxRegimeScope)
              }
              className="input-like"
            >
              {TAX_REGIME_OPTIONS.map((regime) => (
                <option key={regime} value={regime}>
                  {TAX_REGIME_LABELS[regime]}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Perfil fiscal vinculado">
            <select
              value={form.fiscal_profile_id}
              onChange={(event) => onChange("fiscal_profile_id", event.target.value)}
              className="input-like"
            >
              <option value="">Sem perfil vinculado</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} ({profile.id})
                </option>
              ))}
            </select>
          </Field>
        </FormSection>

        <FormSection
          id="classificacao"
          title="Classificação atual"
        >
          <Field label="NCM">
            <DigitsInput
              value={form.ncm}
              onChange={(value) => onChange("ncm", value)}
              maxLength={8}
              placeholder="21069090"
              label="NCM"
            />
          </Field>

          <Field label="NBS">
            <input
              value={form.nbs}
              onChange={(event) => onChange("nbs", event.target.value)}
              className="input-like"
              placeholder="101"
            />
          </Field>

          <Field label="CFOP padrão">
            <DigitsInput
              value={form.cfop_default}
              onChange={(value) => onChange("cfop_default", value)}
              maxLength={4}
              placeholder="5102"
              label="CFOP padrão"
            />
          </Field>

          <Field label="CST ICMS">
            <input
              value={form.cst_icms}
              onChange={(event) => onChange("cst_icms", event.target.value)}
              className="input-like"
              placeholder="102"
            />
          </Field>

          <Field label="CST PIS">
            <input
              value={form.cst_pis}
              onChange={(event) => onChange("cst_pis", event.target.value)}
              className="input-like"
              placeholder="49"
            />
          </Field>

          <Field label="CST COFINS">
            <input
              value={form.cst_cofins}
              onChange={(event) => onChange("cst_cofins", event.target.value)}
              className="input-like"
              placeholder="49"
            />
          </Field>

          <CheckField
            label="Sujeito a ICMS"
            checked={form.subject_to_icms}
            onChange={(value) => onChange("subject_to_icms", value)}
          />

          <CheckField
            label="Sujeito a PIS/COFINS"
            checked={form.subject_to_pis_cofins}
            onChange={(value) => onChange("subject_to_pis_cofins", value)}
          />

          <CheckField
            label="Sujeito a ISS"
            checked={form.subject_to_iss}
            onChange={(value) => onChange("subject_to_iss", value)}
          />
        </FormSection>

        <FormSection
          id="nfe"
          title="NF-e / Substituição Tributária"
        >
          <Field label="CEST">
            <DigitsInput
              value={form.cest}
              onChange={(value) => onChange("cest", value)}
              maxLength={7}
              placeholder="0100100"
              label="CEST"
            />
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Código Especificador da Substituição Tributária (7 dígitos). Obrigatório quando há ST.
            </p>
          </Field>

          <Field label="EX TIPI">
            <DigitsInput
              value={form.ex_tipi}
              onChange={(value) => onChange("ex_tipi", value)}
              maxLength={3}
              placeholder="001"
              label="EX TIPI"
            />
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Exceção da tabela TIPI vinculada ao NCM (até 3 dígitos).
            </p>
          </Field>

          <Field label="Origem da mercadoria">
            <select
              value={form.origem_mercadoria}
              onChange={(event) => onChange("origem_mercadoria", event.target.value)}
              className="input-like"
            >
              <option value="">Não informada</option>
              {ORIGEM_OPTIONS.map((origem) => (
                <option key={origem} value={origem}>
                  {ORIGEM_LABELS[origem]}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Compõe o CST completo de ICMS na NF-e (posição 1 do CST).
            </p>
          </Field>
        </FormSection>

        <FormSection
          id="reforma"
          title="Reforma Tributária"
        >
          <Field label="CST IBS/CBS">
            <input
              value={form.cst_ibs_cbs}
              onChange={(event) => onChange("cst_ibs_cbs", event.target.value)}
              className="input-like"
              placeholder="000"
            />
          </Field>

          <Field label="Classificação tributária">
            <input
              value={form.cclass_trib}
              onChange={(event) => onChange("cclass_trib", event.target.value)}
              className="input-like"
              placeholder="000001"
            />
          </Field>

          <CheckField
            label="Sujeito a IBS/CBS"
            checked={form.subject_to_ibs_cbs}
            onChange={(value) => onChange("subject_to_ibs_cbs", value)}
          />

          <CheckField
            label="Sujeito a Imposto Seletivo"
            checked={form.subject_to_is}
            onChange={(value) => onChange("subject_to_is", value)}
          />
        </FormSection>

        <FormSection
          id="vigencia"
          title="Vigência e fonte"
        >
          <Field label="Vigência inicial">
            <input
              type="date"
              value={form.valid_from}
              onChange={(event) => onChange("valid_from", event.target.value)}
              className="input-like"
            />
          </Field>

          <Field label="Vigência final">
            <input
              type="date"
              value={form.valid_to}
              onChange={(event) => onChange("valid_to", event.target.value)}
              className="input-like"
            />
          </Field>

          <Field label="Fonte">
            <select
              value={form.source}
              onChange={(event) =>
                onChange("source", event.target.value as FiscalSourceType)
              }
              className="input-like"
            >
              {SOURCE_OPTIONS.map((source) => (
                <option key={source} value={source}>
                  {SOURCE_LABELS[source]}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Referência da fonte">
            <input
              value={form.source_reference}
              onChange={(event) =>
                onChange("source_reference", event.target.value)
              }
              className="input-like"
              placeholder="Orientação contábil, norma, tabela ou referência interna"
            />
          </Field>

          <Field label="Observações">
            <textarea
              value={form.notes}
              onChange={(event) => onChange("notes", event.target.value)}
              className="input-like min-h-24"
              placeholder="Observações fiscais e ressalvas."
            />
          </Field>
        </FormSection>

        <section className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-text)]">
                Salvar classificação
              </h2>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                {editingClassificationId
                  ? `Editando ${editingClassificationId}`
                  : "Criando nova classificação fiscal"}
              </p>
            </div>

            <button
              type="button"
              onClick={onSave}
              disabled={saveState === "saving" || !canWrite}
              className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[var(--color-primary)] px-5 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saveState === "saving" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ShieldCheck className="h-4 w-4" />
              )}
              Salvar classificação
            </button>
          </div>
        </section>

        <FormSection
          id="auditoria"
          title="Auditoria"
        >
          {auditEvents.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">
              Nenhum evento de auditoria carregado.
            </p>
          ) : (
            <div className="space-y-3">
              {auditEvents.map((event) => (
                <div
                  key={event.id}
                  className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4"
                >
                  <p className="text-sm font-semibold text-[var(--color-text)]">
                    {FISCAL_AUDIT_ACTION_LABEL[event.action] ?? event.action} · {formatDateTime(event.occurred_at)}
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    {event.entity_type} · {event.entity_id}
                  </p>
                </div>
              ))}
            </div>
          )}
        </FormSection>
      </div>
    </section>
  )
}

function ValidityBadge({
  validFrom,
  validTo,
}: {
  validFrom: string | null
  validTo: string | null
}) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const from = validFrom ? new Date(validFrom) : null
  const to = validTo ? new Date(validTo) : null

  let label = ""
  let className = ""

  if (to && to < today) {
    label = "Expirado"
    className = "border-red-500/30 bg-red-500/10 text-red-500"
  } else if (from && from > today) {
    label = "Futuro"
    className = "border-amber-500/30 bg-amber-500/10 text-amber-500"
  } else if (from || to) {
    label = "Vigente"
    className = "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
  }

  if (!label) return null

  return (
    <span
      className={`mt-1 inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${className}`}
    >
      {label}
    </span>
  )
}

function MetricCard({
  label,
  value,
  helper,
}: {
  label: string
  value: string | number
  helper: string
}) {
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold text-[var(--color-text)]">
        {value}
      </p>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{helper}</p>
    </div>
  )
}


function FormSection({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      className="scroll-mt-24 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-sm"
    >
      <h2 className="text-lg font-semibold text-[var(--color-text)]">{title}</h2>

      <div className="mt-6 grid gap-4 md:grid-cols-2">{children}</div>
    </section>
  )
}

function Field({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-[var(--color-text)]">{label}</span>
      {children}
    </label>
  )
}

function CheckField({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] p-4">
      <span className="text-sm font-medium text-[var(--color-text)]">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-5 accent-[var(--color-primary)]"
      />
    </label>
  )
}

function DigitsInput({
  value,
  onChange,
  maxLength,
  placeholder,
  label,
}: {
  value: string
  onChange: (value: string) => void
  maxLength: number
  placeholder: string
  label: string
}) {
  const [invalidMessage, setInvalidMessage] = useState<string | null>(null)

  function handleChange(nextValue: string) {
    if (!/^\d*$/.test(nextValue)) {
      setInvalidMessage(`${label} aceita apenas números.`)
      return
    }

    if (nextValue.length > maxLength) {
      setInvalidMessage(`${label} aceita no máximo ${maxLength} dígitos.`)
      return
    }

    onChange(nextValue)
  }

  return (
    <>
      <ValidationModal
        message={invalidMessage}
        onClose={() => setInvalidMessage(null)}
      />

      <input
        value={value}
        onChange={(event) => handleChange(event.target.value)}
        inputMode="numeric"
        className="input-like"
        placeholder={placeholder}
        aria-label={label}
      />
    </>
  )
}

function ValidationModal({
  message,
  onClose,
}: {
  message: string | null
  onClose: () => void
}) {
  if (!message) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl bg-red-500/10 p-2 text-red-500">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[var(--color-text)]">
                Atenção
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-muted)]">
                {message}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-[var(--color-text-muted)] transition hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-text)] active:scale-95"
            aria-label="Fechar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function syncFormFromClassification(c: FiscalClassification): FiscalFormState {
  return {
    company_id: c.company_id,
    fiscal_profile_id: c.fiscal_profile_id ?? "",
    name: c.name,
    description: c.description ?? "",
    item_type: c.item_type,
    tax_regime: c.tax_regime,
    ncm: c.ncm ?? "",
    nbs: c.nbs ?? "",
    cest: c.cest ?? "",
    ex_tipi: c.ex_tipi ?? "",
    origem_mercadoria: c.origem_mercadoria ?? "",
    cfop_default: c.cfop_default ?? "",
    cst_icms: c.cst_icms ?? "",
    cst_pis: c.cst_pis ?? "",
    cst_cofins: c.cst_cofins ?? "",
    cst_ibs_cbs: c.cst_ibs_cbs ?? "",
    cclass_trib: c.cclass_trib ?? "",
    subject_to_icms: c.subject_to_icms,
    subject_to_iss: c.subject_to_iss,
    subject_to_pis_cofins: c.subject_to_pis_cofins,
    subject_to_ibs_cbs: c.subject_to_ibs_cbs,
    subject_to_is: c.subject_to_is,
    valid_from: c.valid_from ?? "",
    valid_to: c.valid_to ?? "",
    status: c.status,
    source: c.source,
    source_reference: c.source_reference ?? "",
    notes: c.notes ?? "",
  }
}

function buildClassificationPayload(
  form: FiscalFormState,
): FiscalClassificationCreatePayload {
  return {
    company_id: form.company_id,
    fiscal_profile_id: form.fiscal_profile_id || null,
    name: form.name.trim(),
    description: form.description.trim() || null,
    item_type: form.item_type,
    tax_regime: form.tax_regime,
    ncm: form.ncm || null,
    nbs: form.nbs || null,
    cfop_default: form.cfop_default || null,
    cst_icms: form.cst_icms || null,
    cst_pis: form.cst_pis || null,
    cst_cofins: form.cst_cofins || null,
    cst_ibs_cbs: form.cst_ibs_cbs || null,
    cclass_trib: form.cclass_trib || null,
    subject_to_icms: form.subject_to_icms,
    subject_to_iss: form.subject_to_iss,
    subject_to_pis_cofins: form.subject_to_pis_cofins,
    subject_to_ibs_cbs: form.subject_to_ibs_cbs,
    subject_to_is: form.subject_to_is,
    valid_from: form.valid_from || null,
    valid_to: form.valid_to || null,
    status: form.status,
    source: form.source,
    source_reference: form.source_reference.trim() || null,
    notes: form.notes.trim() || null,
    // novos campos — aceitos pelo backend quando presentes
    ...(form.cest ? { cest: form.cest } : {}),
    ...(form.ex_tipi ? { ex_tipi: form.ex_tipi } : {}),
    ...(form.origem_mercadoria ? { origem_mercadoria: form.origem_mercadoria } : {}),
  } as FiscalClassificationCreatePayload
}

function buildCsv(items: FiscalClassification[]): string {
  const header = [
    "id",
    "name",
    "item_type",
    "tax_regime",
    "status",
    "ncm",
    "nbs",
    "cfop_default",
    "cst_icms",
    "cst_pis",
    "cst_cofins",
    "cst_ibs_cbs",
    "cclass_trib",
    "subject_to_icms",
    "subject_to_iss",
    "subject_to_pis_cofins",
    "subject_to_ibs_cbs",
    "subject_to_is",
    "valid_from",
    "valid_to",
    "source",
    "created_at",
    "updated_at",
  ]

  const rows = items.map((item) =>
    [
      item.id,
      item.name,
      item.item_type,
      item.tax_regime,
      item.status,
      item.ncm ?? "",
      item.nbs ?? "",
      item.cfop_default ?? "",
      item.cst_icms ?? "",
      item.cst_pis ?? "",
      item.cst_cofins ?? "",
      item.cst_ibs_cbs ?? "",
      item.cclass_trib ?? "",
      item.subject_to_icms ? "1" : "0",
      item.subject_to_iss ? "1" : "0",
      item.subject_to_pis_cofins ? "1" : "0",
      item.subject_to_ibs_cbs ? "1" : "0",
      item.subject_to_is ? "1" : "0",
      item.valid_from ?? "",
      item.valid_to ?? "",
      item.source,
      item.created_at,
      item.updated_at,
    ]
      .map((v) => `"${String(v).replace(/"/g, '""')}"`)
      .join(","),
  )

  return [header.join(","), ...rows].join("\n")
}

function exportRows(items: FiscalClassification[]): string[][] {
  const header = [
    "ID",
    "Nome",
    "Tipo",
    "Regime",
    "Status",
    "NCM",
    "NBS",
    "CFOP",
    "CST ICMS",
    "CST PIS",
    "CST COFINS",
    "CST IBS/CBS",
    "Class. Trib.",
    "ICMS",
    "ISS",
    "PIS/COFINS",
    "IBS/CBS",
    "IS",
    "Vigência inicial",
    "Vigência final",
    "Fonte",
    "Criado em",
    "Atualizado em",
  ]

  const rows = items.map((item) => [
    item.id,
    item.name,
    item.item_type,
    item.tax_regime,
    item.status,
    item.ncm ?? "",
    item.nbs ?? "",
    item.cfop_default ?? "",
    item.cst_icms ?? "",
    item.cst_pis ?? "",
    item.cst_cofins ?? "",
    item.cst_ibs_cbs ?? "",
    item.cclass_trib ?? "",
    item.subject_to_icms ? "Sim" : "Não",
    item.subject_to_iss ? "Sim" : "Não",
    item.subject_to_pis_cofins ? "Sim" : "Não",
    item.subject_to_ibs_cbs ? "Sim" : "Não",
    item.subject_to_is ? "Sim" : "Não",
    item.valid_from ?? "",
    item.valid_to ?? "",
    item.source,
    item.created_at,
    item.updated_at,
  ])

  return [header, ...rows]
}

function buildSimpleXlsx(sheetName: string, rows: string[][]): Blob {
  const xmlRows = rows
    .map(
      (row) =>
        `<row>${row
          .map((cell) => `<c t="inlineStr"><is><t>${escapeXml(String(cell))}</t></is></c>`)
          .join("")}</row>`,
    )
    .join("")

  const sheet = `<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${xmlRows}</sheetData></worksheet>`
  const wb = `<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="${escapeXml(sheetName)}" sheetId="1" r:id="rId1"/></sheets></workbook>`
  const rel = `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>`
  const ct = `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>`

  const zip = zipSync({
    "[Content_Types].xml": strToU8(ct),
    "xl/workbook.xml": strToU8(wb),
    "xl/_rels/workbook.xml.rels": strToU8(rel),
    "xl/worksheets/sheet1.xml": strToU8(sheet),
  })

  return new Blob([zip.buffer as ArrayBuffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  })
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;")
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function dateStamp(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatDateTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso))
  } catch {
    return iso
  }
}
