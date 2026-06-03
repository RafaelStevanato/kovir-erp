import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import {
  Boxes,
  CheckCircle2,
  ClipboardList,
  Download,
  FileInput,
  FilePlus2,
  Filter,
  Loader2,
  MapPin,
  PackageCheck,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  UploadCloud,
  Warehouse,
  X,
} from "lucide-react"

import { SearchableSelect, type SearchableSelectOption } from "../../components/SearchableSelect"
import { getActiveCompanyId } from "../../config/activeCompany"
import {
  dateCell,
  exportCsv as exportCsvFile,
  exportXlsx as exportXlsxFile,
  integerCell,
  moneyCell,
  numberCell,
  type ExportTable,
} from "../../lib/exportTable"
import { getCatalogItems } from "../catalog/catalogApi"
import type { CatalogItem } from "../catalog/types"
import { getParticipants } from "../participants/participantsApi"
import type { Participant } from "../participants/types"
import { ApiError } from "../../lib/api"
import {
  createStockMovement,
  createStockLocation,
  createStockPurchaseEntry,
  ensureDefaultStockLocation,
  listStockBalances,
  listStockLots,
  listStockLocations,
  listStockMovements,
  listStockPurchaseEntries,
  parseStockPurchaseXml,
} from "./stockApi"
import type {
  StockBalance,
  StockLocation,
  StockLot,
  StockMovement,
  StockPurchaseEntry,
  StockPurchaseXmlParseResult,
} from "./types"

type StockTab = "balances" | "manual" | "purchase"

type PurchaseDraftItem = {
  item_id: string
  quantity: string
  unit_cost: string
  lot_code: string
  hasExpiration: boolean
  expiration_date: string | null
  description: string
  xml_line?: number | null
  xml_match_status?: string | null
}

const activeTabClass = "border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary)] shadow-lg shadow-[var(--color-card-shadow)]"
const inactiveTabClass = "border-[var(--color-border-soft)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"

function formatNumber(value: string | number | null | undefined, digits = 4) {
  const parsed = Number(value ?? 0)
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number.isFinite(parsed) ? parsed : 0)
}

function formatMoney(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0)
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isFinite(parsed) ? parsed : 0)
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(parsed)
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "Erro inesperado ao carregar estoque."
}

function normalizeText(value: string | null | undefined) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
}

function labelMovementType(value: string) {
  const labels: Record<string, string> = {
    initial_balance: "Saldo inicial",
    adjustment_in: "Ajuste de entrada",
    adjustment_out: "Ajuste de saída",
    sale_out: "Saída por venda",
    sale_out_reversal: "Reversão de venda",
    purchase_in: "Entrada por compra",
    transfer_in: "Transferência entrada",
    transfer_out: "Transferência saída",
  }
  return labels[value] ?? value
}

function sourceLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    manual: "Manual",
    sale: "Venda",
    purchase_entry: "Nota de compra",
  }
  return labels[value ?? ""] ?? (value || "Manual")
}

function itemLabel(item: CatalogItem | undefined, itemId: string) {
  if (!item) return itemId
  return [item.name, item.sku ? `SKU ${item.sku}` : null].filter(Boolean).join(" · ")
}

function locationLabel(location: StockLocation | undefined, locationId: string) {
  if (!location) return locationId
  return `${location.name}${location.is_default ? " · padrão" : ""}`
}

function parseDateForExport(value: string | null | undefined) {
  if (!value) return null
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number)
    return new Date(year, month - 1, day)
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed
}

function formatExportDate(value: string | null | undefined) {
  const parsed = parseDateForExport(value)
  if (!parsed) return value ?? ""
  const day = String(parsed.getDate()).padStart(2, "0")
  const month = String(parsed.getMonth() + 1).padStart(2, "0")
  const year = String(parsed.getFullYear()).slice(-2)
  return `${day}/${month}/${year}`
}

/** Formata data de validade; retorna "SV" para datas sentinela (ano 9999) ou valores nulos. */
function formatExpDate(value: string | null | undefined) {
  if (!value) return "SV"
  if (value.startsWith("9999")) return "SV"
  return formatExportDate(value)
}

function exportCsv(rows: ExportTable, fileName: string) {
  exportCsvFile(rows, fileName)
}

function exportXlsx(rows: ExportTable, sheetName: string, fileName: string) {
  exportXlsxFile(rows, sheetName, fileName)
}

function todayFileSuffix() {
  return new Date().toISOString().slice(0, 10)
}

function matchStatusLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    matched_by_sku: "Produto encontrado por SKU",
    matched_by_barcode: "Produto encontrado por código de barras",
    matched_by_name: "Produto encontrado por nome",
    possible_name_match: "Possível produto encontrado",
    not_matched: "Precisa selecionar o produto",
  }
  return labels[value ?? ""] ?? "Precisa conferir"
}

const PAGE_SIZE = 20

function PaginationControls({ listPage, totalPages, setListPage }: { listPage: number; totalPages: number; setListPage: (page: number) => void }) {
  if (totalPages <= 1) return null
  const pages: (number | "…")[] = []
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= listPage - 1 && i <= listPage + 1)) {
      pages.push(i)
    } else if (pages[pages.length - 1] !== "…") {
      pages.push("…")
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-center gap-2 border-t border-[var(--color-border-soft)] px-4 py-3">
      <button type="button" disabled={listPage === 1} onClick={() => setListPage(Math.max(1, listPage - 1))} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40">← Anterior</button>
      {pages.map((page, idx) =>
        page === "…" ? (
          <span key={`e${idx}`} className="px-2 text-[var(--color-text-weak)]">…</span>
        ) : (
          <button key={page} type="button" onClick={() => setListPage(page)} className={`min-w-[2.5rem] rounded-2xl border px-3 py-2 text-sm font-bold transition ${page === listPage ? "border-emerald-400/60 bg-emerald-500/15 text-emerald-100" : "border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"}`}>{page}</button>
        )
      )}
      <button type="button" disabled={listPage === totalPages} onClick={() => setListPage(Math.min(totalPages, listPage + 1))} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:opacity-40">Próxima →</button>
    </div>
  )
}

export function StockPage() {
  const activeCompanyId = useMemo(() => getActiveCompanyId(), [])
  const xmlInputRef = useRef<HTMLInputElement | null>(null)
  const [activeTab, setActiveTab] = useState<StockTab>("balances")
  const [selectedLocationId, setSelectedLocationId] = useState("")
  const [hasLoadedStockData, setHasLoadedStockData] = useState(false)
  const [locations, setLocations] = useState<StockLocation[]>([])
  const [balances, setBalances] = useState<StockBalance[]>([])
  const [lots, setLots] = useState<StockLot[]>([])
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [purchaseEntries, setPurchaseEntries] = useState<StockPurchaseEntry[]>([])
  const [products, setProducts] = useState<CatalogItem[]>([])
  const [suppliers, setSuppliers] = useState<Participant[]>([])
  const [isLoadingLocations, setIsLoadingLocations] = useState(true)
  const [isLoadingData, setIsLoadingData] = useState(false)
  const [isCreatingDefault, setIsCreatingDefault] = useState(false)
  const [isCreatingLocation, setIsCreatingLocation] = useState(false)
  const [isSubmittingMovement, setIsSubmittingMovement] = useState(false)
  const [isSubmittingPurchase, setIsSubmittingPurchase] = useState(false)
  const [isReadingXml, setIsReadingXml] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [xmlResult, setXmlResult] = useState<StockPurchaseXmlParseResult | null>(null)
  const [filters, setFilters] = useState({ item_id: "", location_id: "", movement_type: "", search: "" })
  const [locationForm, setLocationForm] = useState({
    code: "",
    name: "",
    location_type: "warehouse",
    is_default: false,
    notes: "",
  })
  const [movementForm, setMovementForm] = useState({
    item_id: "",
    location_id: "",
    movement_type: "initial_balance",
    quantity: "",
    unit_cost: "",
    lot_code: "",
    hasExpiration: true,
    expiration_date: "",
    notes: "",
  })
  const [purchaseForm, setPurchaseForm] = useState({
    supplier_participant_id: "",
    location_id: "",
    document_number: "",
    document_series: "",
    access_key: "",
    issue_date: "",
    notes: "",
    items: [{ item_id: "", quantity: "", unit_cost: "", lot_code: "", hasExpiration: true, expiration_date: "", description: "", xml_line: null, xml_match_status: null }] as PurchaseDraftItem[],
  })

  const productMap = useMemo(() => new Map(products.map((item) => [item.id, item])), [products])
  const locationMap = useMemo(() => new Map(locations.map((location) => [location.id, location])), [locations])
  const selectedLocation = useMemo(() => locationMap.get(selectedLocationId), [locationMap, selectedLocationId])
  const lotsByItemLocation = useMemo(() => {
    const index = new Map<string, StockLot[]>()
    lots.forEach((lot) => {
      const key = `${lot.item_id}::${lot.location_id}`
      const existing = index.get(key) ?? []
      existing.push(lot)
      index.set(key, existing)
    })
    index.forEach((entries) => {
      entries.sort((a, b) => String(a.expiration_date).localeCompare(String(b.expiration_date)) || a.lot_code.localeCompare(b.lot_code))
    })
    return index
  }, [lots])

  const productOptions: SearchableSelectOption[] = useMemo(
    () => products
      .filter((item) => item.item_type === "product" && item.status === "active")
      .map((item) => ({
        value: item.id,
        label: itemLabel(item, item.id),
        description: [item.inventory_settings?.track_stock ? "controla estoque" : "sem controle", item.unit, item.fiscal_settings?.ncm ? `NCM ${item.fiscal_settings.ncm}` : null].filter(Boolean).join(" · "),
        keywords: [item.name, item.sku, item.barcode, item.id, item.fiscal_settings?.ncm].filter(Boolean) as string[],
      })),
    [products],
  )

  const locationOptions: SearchableSelectOption[] = useMemo(
    () => locations.map((location) => ({
      value: location.id,
      label: locationLabel(location, location.id),
      description: `${location.code} · ${location.location_type} · ${location.status}`,
      keywords: [location.code, location.name, location.id],
    })),
    [locations],
  )

  const supplierOptions: SearchableSelectOption[] = useMemo(
    () => suppliers.map((supplier) => ({
      value: supplier.id,
      label: [supplier.name, supplier.trade_name].filter(Boolean).join(" · "),
      description: [supplier.document, supplier.email].filter(Boolean).join(" · "),
      keywords: [supplier.name, supplier.trade_name, supplier.document, supplier.email, supplier.id].filter(Boolean) as string[],
    })),
    [suppliers],
  )

  const filteredBalances = useMemo(() => {
    const query = normalizeText(filters.search)
    return balances.filter((balance) => {
      const item = productMap.get(balance.item_id)
      const location = locationMap.get(balance.location_id)
      const matchesItem = !filters.item_id || balance.item_id === filters.item_id
      const matchesLocation = !filters.location_id || balance.location_id === filters.location_id
      const searchable = normalizeText([item?.name, item?.sku, item?.barcode, item?.id, location?.name, location?.code].filter(Boolean).join(" "))
      return matchesItem && matchesLocation && (!query || searchable.includes(query))
    })
  }, [balances, filters.item_id, filters.location_id, filters.search, locationMap, productMap])

  const filteredMovements = useMemo(() => movements.filter((movement) => {
    const item = productMap.get(movement.item_id)
    const location = locationMap.get(movement.location_id)
    const query = normalizeText(filters.search)
    const searchable = normalizeText([item?.name, item?.sku, location?.name, movement.id, movement.notes].filter(Boolean).join(" "))
    if (filters.item_id && movement.item_id !== filters.item_id) return false
    if (filters.location_id && movement.location_id !== filters.location_id) return false
    if (filters.movement_type && movement.movement_type !== filters.movement_type) return false
    if (query && !searchable.includes(query)) return false
    return true
  }), [filters.item_id, filters.location_id, filters.movement_type, filters.search, locationMap, movements, productMap])

  const filteredPurchaseEntries = useMemo(() => {
    const query = normalizeText(filters.search)
    return purchaseEntries.filter((entry) => {
      const location = locationMap.get(entry.location_id)
      const supplierName = typeof entry.supplier_snapshot?.name === "string" ? entry.supplier_snapshot.name : ""
      const searchable = normalizeText([entry.document_number, entry.access_key, supplierName, location?.name, entry.id].filter(Boolean).join(" "))
      return !query || searchable.includes(query)
    })
  }, [filters.search, locationMap, purchaseEntries])

  const totalQuantity = filteredBalances.reduce((sum, row) => sum + Number(row.quantity || 0), 0)
  const lowStockCount = filteredBalances.filter((row) => {
    const item = productMap.get(row.item_id)
    const minimum = Number(item?.inventory_settings?.minimum_stock ?? 0)
    return minimum > 0 && Number(row.quantity ?? 0) <= minimum
  }).length
  const purchaseTotal = purchaseForm.items.reduce((sum, row) => sum + (Number(row.quantity || 0) * Number(row.unit_cost || 0)), 0)
  const purchaseQuantity = purchaseForm.items.reduce((sum, row) => sum + Number(row.quantity || 0), 0)
  const purchaseReadyCount = purchaseForm.items.filter((row) => row.item_id && Number(row.quantity) > 0 && row.lot_code.trim() && (!row.hasExpiration || row.expiration_date)).length
  const purchasePendingCount = purchaseForm.items.filter((row) => !row.item_id || !row.quantity || !row.lot_code.trim() || (row.hasExpiration && !row.expiration_date)).length

  const clearStockData = useCallback(() => {
    setBalances([])
    setLots([])
    setMovements([])
    setPurchaseEntries([])
    setProducts([])
    setSuppliers([])
    setHasLoadedStockData(false)
  }, [])

  const loadLocations = useCallback(async () => {
    setIsLoadingLocations(true)
    setError(null)
    try {
      const locationsResponse = await listStockLocations(activeCompanyId)
      setLocations(locationsResponse.data)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoadingLocations(false)
    }
  }, [activeCompanyId])

  const loadData = useCallback(async (locationId = selectedLocationId) => {
    if (!locationId) {
      setError("Selecione um local de estoque antes de carregar informações.")
      return
    }
    setIsLoadingData(true)
    setError(null)
    try {
      const [balancesResponse, lotsResponse, movementsResponse, purchasesResponse, productsResponse, suppliersResponse] = await Promise.all([
        listStockBalances(activeCompanyId, { location_id: locationId }),
        listStockLots(activeCompanyId, { location_id: locationId }),
        listStockMovements(activeCompanyId, { location_id: locationId }),
        listStockPurchaseEntries(activeCompanyId, { location_id: locationId, include_items: true }),
        getCatalogItems({ company_id: activeCompanyId, item_type: "product", status: "active", limit: 300, offset: 0 }),
        getParticipants({ company_id: activeCompanyId, participant_type: "supplier", status: "active", limit: 300, offset: 0 }),
      ])
      setBalances(balancesResponse.data)
      setLots(lotsResponse.data)
      setMovements(movementsResponse.data)
      setPurchaseEntries(purchasesResponse.data)
      setProducts(productsResponse.data)
      setSuppliers(suppliersResponse.data)
      setFilters((current) => ({ ...current, location_id: locationId }))
      setMovementForm((current) => ({ ...current, location_id: locationId }))
      setPurchaseForm((current) => ({ ...current, location_id: locationId }))
      setHasLoadedStockData(true)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoadingData(false)
    }
  }, [activeCompanyId, selectedLocationId])

  useEffect(() => {
    void loadLocations()
  }, [loadLocations])

  async function handleRefresh() {
    if (hasLoadedStockData && selectedLocationId) {
      await loadData(selectedLocationId)
      return
    }
    await loadLocations()
  }

  function handleSelectLocation(locationId: string) {
    setError(null)
    setSuccess(null)
    setSelectedLocationId(locationId)
    setFilters({ item_id: "", location_id: locationId, movement_type: "", search: "" })
    setMovementForm((current) => ({ ...current, location_id: locationId }))
    setPurchaseForm((current) => ({ ...current, location_id: locationId }))
    clearStockData()
  }

  async function handleCreateLocation() {
    setIsCreatingLocation(true)
    setError(null)
    setSuccess(null)
    try {
      const code = locationForm.code.trim()
      const name = locationForm.name.trim()
      if (!code || !name) {
        setError("Informe código e nome do novo local de estoque.")
        return
      }
      const response = await createStockLocation({
        company_id: activeCompanyId,
        code,
        name,
        location_type: locationForm.location_type,
        is_default: locationForm.is_default,
        notes: locationForm.notes.trim() || null,
      })
      await loadLocations()
      handleSelectLocation(response.data.id)
      setLocationForm({ code: "", name: "", location_type: "warehouse", is_default: false, notes: "" })
      setSuccess("Local de estoque criado. Clique em carregar informações para consultar este estoque.")
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsCreatingLocation(false)
    }
  }

  async function handleEnsureDefaultLocation() {
    setIsCreatingDefault(true)
    setError(null)
    setSuccess(null)
    try {
      const response = await ensureDefaultStockLocation(activeCompanyId)
      await loadLocations()
      handleSelectLocation(response.data.id)
      setSuccess("Local padrão de estoque disponível. Clique em carregar informações para consultar este estoque.")
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsCreatingDefault(false)
    }
  }

  async function handleCreateMovement() {
    setIsSubmittingMovement(true)
    setError(null)
    setSuccess(null)
    try {
      if (!selectedLocationId) {
        setError("Selecione o local de estoque antes de registrar movimento.")
        return
      }
      await createStockMovement({
        company_id: activeCompanyId,
        item_id: movementForm.item_id.trim(),
        location_id: movementForm.location_id || selectedLocationId,
        movement_type: movementForm.movement_type,
        quantity: movementForm.quantity.trim(),
        unit_cost: movementForm.unit_cost.trim() || null,
        lot_code: movementForm.lot_code.trim(),
        expiration_date: movementForm.hasExpiration ? (movementForm.expiration_date || null) : null,
        notes: movementForm.notes.trim() || null,
      })
      setMovementForm({ item_id: "", location_id: selectedLocationId, movement_type: "initial_balance", quantity: "", unit_cost: "", lot_code: "", hasExpiration: true, expiration_date: "", notes: "" })
      setSuccess("Movimento manual criado. O saldo foi atualizado automaticamente.")
      await loadData()
      setActiveTab("balances")
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsSubmittingMovement(false)
    }
  }

  function updatePurchaseItem(index: number, patch: Partial<PurchaseDraftItem>) {
    setPurchaseForm((current) => ({
      ...current,
      items: current.items.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)),
    }))
  }

  function addPurchaseItem() {
    setPurchaseForm((current) => ({
      ...current,
      items: [...current.items, { item_id: "", quantity: "", unit_cost: "", lot_code: "", hasExpiration: true, expiration_date: "", description: "", xml_line: null, xml_match_status: null }],
    }))
  }

  function removePurchaseItem(index: number) {
    setPurchaseForm((current) => ({
      ...current,
      items: current.items.length === 1 ? current.items : current.items.filter((_, rowIndex) => rowIndex !== index),
    }))
  }

  async function handleXmlFile(file: File | null) {
    if (!file) return
    setIsReadingXml(true)
    setError(null)
    setSuccess(null)
    try {
      const xmlText = await file.text()
      const response = await parseStockPurchaseXml(activeCompanyId, xmlText)
      const result = response.data
      setXmlResult(result)
      setPurchaseForm((current) => ({
        ...current,
        supplier_participant_id: result.supplier.participant_id ?? current.supplier_participant_id,
        document_number: result.document.document_number ?? current.document_number,
        document_series: result.document.document_series ?? current.document_series,
        access_key: result.document.access_key ?? current.access_key,
        issue_date: result.document.issue_date ?? current.issue_date,
        notes: current.notes || `Entrada importada de XML de NF-e. Fornecedor: ${result.supplier.name ?? "não identificado"}.`,
        items: result.items.length > 0
          ? result.items.map((item) => ({
              item_id: item.matched_item_id ?? "",
              quantity: item.quantity ?? "",
              unit_cost: item.unit_cost ?? "",
              lot_code: "",
              hasExpiration: true,
              expiration_date: "",
              description: item.description ?? "",
              xml_line: item.line_number,
              xml_match_status: item.match_status,
            }))
          : current.items,
      }))
      setSuccess(`XML lido. Itens encontrados: ${result.summary.total_items}. Vinculados ao catálogo: ${result.summary.matched_items}.`)
      setActiveTab("purchase")
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsReadingXml(false)
      if (xmlInputRef.current) xmlInputRef.current.value = ""
    }
  }

  async function handleCreatePurchaseEntry() {
    setIsSubmittingPurchase(true)
    setError(null)
    setSuccess(null)
    try {
      if (!selectedLocationId) {
        setError("Selecione o local de estoque antes de registrar entrada.")
        return
      }
      const invalidLine = purchaseForm.items.find((row) => {
        return !row.item_id || !row.quantity || Number(row.quantity) <= 0 || !row.lot_code.trim() || (row.hasExpiration && !row.expiration_date)
      })
      if (invalidLine) {
        setError("Revise todos os itens antes de registrar. Nenhuma linha incompleta pode ser ignorada em entrada de estoque.")
        return
      }
      await createStockPurchaseEntry({
        company_id: activeCompanyId,
        supplier_participant_id: purchaseForm.supplier_participant_id || null,
        location_id: purchaseForm.location_id || selectedLocationId,
        document_type: "purchase_invoice",
        document_number: purchaseForm.document_number.trim() || null,
        document_series: purchaseForm.document_series.trim() || null,
        access_key: purchaseForm.access_key.trim() || null,
        issue_date: purchaseForm.issue_date || null,
        notes: purchaseForm.notes.trim() || null,
        metadata: xmlResult ? { source: "nfe_xml_parser", xml_summary: xmlResult.summary, xml_warnings: xmlResult.warnings } : null,
        items: purchaseForm.items
          .map((row) => ({
            item_id: row.item_id,
            quantity: row.quantity,
            unit_cost: row.unit_cost || null,
            lot_code: row.lot_code.trim(),
            expiration_date: row.hasExpiration ? (row.expiration_date || null) : null,
            description: row.description || null,
          })),
      })
      setPurchaseForm({ supplier_participant_id: "", location_id: selectedLocationId, document_number: "", document_series: "", access_key: "", issue_date: "", notes: "", items: [{ item_id: "", quantity: "", unit_cost: "", lot_code: "", hasExpiration: true, expiration_date: "", description: "", xml_line: null, xml_match_status: null }] })
      setXmlResult(null)
      setSuccess("Entrada por nota de compra registrada. O saldo foi atualizado com movimentos purchase_in.")
      await loadData()
      setActiveTab("balances")
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsSubmittingPurchase(false)
    }
  }

  function balanceExportRows(): ExportTable {
    return [
      ["Produto", "SKU", "Item ID", "Local", "Local ID", "Quantidade", "Custo médio", "Lotes ativos", "Estoque mínimo", "Situação", "Atualizado em"],
      ...filteredBalances.map((row) => {
        const item = productMap.get(row.item_id)
        const location = locationMap.get(row.location_id)
        const minimum = Number(item?.inventory_settings?.minimum_stock ?? 0)
        const quantity = Number(row.quantity ?? 0)
        const status = minimum > 0 && quantity <= minimum ? "Abaixo do mínimo" : "OK"
        const lotsForBalance = lotsByItemLocation.get(`${row.item_id}::${row.location_id}`) ?? []
        const lotsDescription = lotsForBalance.map((lot) => `${lot.lot_code} (${formatExpDate(lot.expiration_date)}) qtd ${lot.quantity}`).join(" | ")
        return [
          item?.name ?? row.item_id,
          item?.sku ?? "",
          row.item_id,
          location?.name ?? row.location_id,
          row.location_id,
          numberCell(row.quantity),
          moneyCell(row.average_cost ?? ""),
          lotsDescription,
          numberCell(item?.inventory_settings?.minimum_stock ?? ""),
          status,
          dateCell(row.updated_at),
        ]
      }),
    ]
  }

  function movementExportRows(): ExportTable {
    return [
      ["ID", "Produto", "SKU", "Local", "Tipo", "Direção", "Quantidade", "Unidade", "Lote", "Validade", "Custo unitário", "Custo total", "Origem", "Data", "Observações"],
      ...filteredMovements.map((row) => {
        const item = productMap.get(row.item_id)
        const location = locationMap.get(row.location_id)
        return [
          row.id,
          item?.name ?? row.item_id,
          item?.sku ?? "",
          location?.name ?? row.location_id,
          labelMovementType(row.movement_type),
          row.direction,
          numberCell(row.quantity),
          row.unit,
          row.lot_code ?? "",
          dateCell(row.expiration_date),
          moneyCell(row.unit_cost ?? ""),
          moneyCell(row.total_cost ?? ""),
          sourceLabel(row.source_type),
          dateCell(row.movement_date),
          row.notes ?? "",
        ]
      }),
    ]
  }

  function purchaseExportRows(): ExportTable {
    return [
      ["ID", "Documento", "Série", "Chave", "Fornecedor", "Local", "Lotes", "Emissão", "Entrada", "Itens", "Quantidade", "Valor", "Status", "Observações"],
      ...filteredPurchaseEntries.map((entry) => {
        const location = locationMap.get(entry.location_id)
        const supplierName = typeof entry.supplier_snapshot?.name === "string" ? entry.supplier_snapshot.name : ""
        const lotsDescription = (entry.items ?? []).map((item) => {
          const expirationLabel = item.expiration_date ? formatExportDate(item.expiration_date) : "-"
          return `${item.lot_code ?? "-"} (${expirationLabel}) qtd ${item.quantity}`
        }).join(" | ")
        return [
          entry.id,
          entry.document_number ?? "",
          entry.document_series ?? "",
          entry.access_key ?? "",
          supplierName,
          location?.name ?? entry.location_id,
          lotsDescription,
          dateCell(entry.issue_date),
          dateCell(entry.entry_date),
          integerCell(entry.total_items),
          numberCell(entry.total_quantity),
          moneyCell(entry.total_amount),
          entry.status,
          entry.notes ?? "",
        ]
      }),
    ]
  }

  const tabs = [
    { id: "balances" as const, label: "Listar e filtrar estoques", icon: Boxes, description: "Saldos, movimentos e exportação" },
    { id: "manual" as const, label: "Movimentação manual", icon: SlidersHorizontal, description: "Saldo inicial e ajustes" },
    { id: "purchase" as const, label: "Entrada por nota de compra", icon: FilePlus2, description: "XML ou digitação assistida" },
  ]

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-300">
              <PackageCheck className="h-4 w-4" /> Estoque operacional
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-[var(--color-text)]">Estoque</h1>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => void handleRefresh()} disabled={isLoadingLocations || isLoadingData} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-5 py-3 text-sm font-bold text-[var(--color-text)] transition hover:bg-[var(--color-hover)] disabled:cursor-wait disabled:opacity-60">
              {isLoadingLocations || isLoadingData ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Atualizar
            </button>
            <button type="button" onClick={handleEnsureDefaultLocation} disabled={isCreatingDefault} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary-soft)] px-5 py-3 text-sm font-bold text-[var(--color-primary)] transition hover:bg-[var(--color-hover)] disabled:cursor-wait disabled:opacity-70">
              {isCreatingDefault ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapPin className="h-4 w-4" />} Garantir local padrão
            </button>
          </div>
        </div>
      </header>

      {error ? <AlertBox tone="danger" icon={<ShieldAlert className="h-5 w-5" />} message={error} /> : null}
      {success ? <AlertBox tone="success" icon={<CheckCircle2 className="h-5 w-5" />} message={success} /> : null}

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-black text-[var(--color-text)]">Novo local de estoque</h2>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">Crie depósitos, lojas, avaria ou trânsito antes de consultar saldos.</p>
          </div>
          <StatusPill status={locationForm.is_default ? "ok" : "warning"} label={locationForm.is_default ? "Será padrão" : "Não padrão"} />
        </div>
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.4fr_1fr_0.8fr_1.5fr_auto] lg:items-end">
          <Field label="Código">
            <input value={locationForm.code} onChange={(event) => setLocationForm((current) => ({ ...current, code: event.target.value.toUpperCase() }))} placeholder="DEP-01" className="field-input" />
          </Field>
          <Field label="Nome">
            <input value={locationForm.name} onChange={(event) => setLocationForm((current) => ({ ...current, name: event.target.value }))} placeholder="Depósito principal" className="field-input" />
          </Field>
          <Field label="Tipo">
            <select value={locationForm.location_type} onChange={(event) => setLocationForm((current) => ({ ...current, location_type: event.target.value }))} className="field-input">
              <option value="main">Principal</option>
              <option value="warehouse">Depósito</option>
              <option value="store">Loja</option>
              <option value="damaged">Avaria</option>
              <option value="transit">Trânsito</option>
              <option value="other">Outro</option>
            </select>
          </Field>
          <label className="flex min-h-[3.25rem] cursor-pointer items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-4 text-sm font-bold text-[var(--color-text-muted)]">
            <input type="checkbox" checked={locationForm.is_default} onChange={(event) => setLocationForm((current) => ({ ...current, is_default: event.target.checked }))} className="h-4 w-4 rounded accent-emerald-500" />
            Padrão
          </label>
          <Field label="Observação">
            <input value={locationForm.notes} onChange={(event) => setLocationForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Uso interno opcional" className="field-input" />
          </Field>
          <button type="button" onClick={handleCreateLocation} disabled={isCreatingLocation} className="inline-flex min-h-[3.25rem] items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white transition hover:bg-[var(--color-primary-hover)] disabled:cursor-wait disabled:opacity-70">
            {isCreatingLocation ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Criar local
          </button>
        </div>
      </section>

      {isLoadingLocations ? (
        <div className="flex items-center gap-3 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 text-[var(--color-text-muted)]"><Loader2 className="h-5 w-5 animate-spin" /> Carregando locais de estoque...</div>
      ) : (
        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
            <Field label="Estoque obrigatório para consulta">
              <SearchableSelect value={selectedLocationId} options={locationOptions} placeholder="Selecione o local de estoque antes de consultar" onChange={handleSelectLocation} />
            </Field>
            <button type="button" onClick={() => void loadData(selectedLocationId)} disabled={!selectedLocationId || isLoadingData} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white transition hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50">
              {isLoadingData ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Carregar informações
            </button>
          </div>
          <p className="mt-3 text-sm text-[var(--color-text-muted)]">
            A tela não carrega saldos, lotes, movimentos ou entradas automaticamente. Primeiro selecione o estoque que deseja consultar.
          </p>
          {selectedLocation ? (
            <p className="mt-2 text-xs font-bold text-[var(--color-primary)]">Selecionado: {selectedLocation.name}{selectedLocation.is_default ? " · padrão" : ""}</p>
          ) : null}
        </section>
      )}

      {!hasLoadedStockData ? (
        <div className="rounded-[2rem] border border-dashed border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 text-sm text-[var(--color-text-muted)]">
          Selecione um local de estoque e clique em <strong className="text-[var(--color-text)]">Carregar informações</strong> para abrir saldos, movimentos, entradas e exportações.
        </div>
      ) : (
        <>
          <section className="grid gap-3 lg:grid-cols-3">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const active = activeTab === tab.id
              return (
                <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`rounded-3xl border p-4 text-left transition ${active ? activeTabClass : inactiveTabClass}`}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-black/10"><Icon className="h-5 w-5" /></span>
                    <div>
                      <p className="font-bold">{tab.label}</p>
                      <p className="mt-1 text-xs opacity-80">{tab.description}</p>
                    </div>
                  </div>
                </button>
              )
            })}
          </section>

          {isLoadingData ? (
            <div className="flex items-center gap-3 rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 text-[var(--color-text-muted)]"><Loader2 className="h-5 w-5 animate-spin" /> Carregando informações do estoque selecionado...</div>
          ) : (
            <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <SummaryCard accent="#2563eb" label="Locais" value={locations.length} helper="depósitos cadastrados" />
            <SummaryCard accent="#16a34a" label="Itens com saldo" value={balances.length} helper="produto × local" />
            <SummaryCard accent="#7c3aed" label="Quantidade total" value={formatNumber(totalQuantity)} helper="soma dos filtros" />
            <SummaryCard accent="#d97706" label="Abaixo do mínimo" value={lowStockCount} helper={lowStockCount > 0 ? "requer atenção" : "estoque OK"} />
            <SummaryCard accent="#0891b2" label="Entradas por nota" value={purchaseEntries.length} helper="notas de compra" />
          </section>

          {activeTab === "balances" ? (
            <section className="space-y-6">
              <FilterPanel
                filters={filters}
                setFilters={setFilters}
                productOptions={productOptions}
                resultCounts={{ balances: filteredBalances.length, movements: filteredMovements.length, purchases: filteredPurchaseEntries.length }}
              />
              <ExportPanel
                balancesCount={filteredBalances.length}
                movementsCount={filteredMovements.length}
                purchasesCount={filteredPurchaseEntries.length}
                onExportBalancesCsv={() => exportCsv(balanceExportRows(), `estoque_saldos_${todayFileSuffix()}.csv`)}
                onExportBalancesXlsx={() => exportXlsx(balanceExportRows(), "Saldos", `estoque_saldos_${todayFileSuffix()}.xlsx`)}
                onExportMovementsCsv={() => exportCsv(movementExportRows(), `estoque_movimentos_${todayFileSuffix()}.csv`)}
                onExportMovementsXlsx={() => exportXlsx(movementExportRows(), "Movimentos", `estoque_movimentos_${todayFileSuffix()}.xlsx`)}
                onExportPurchasesCsv={() => exportCsv(purchaseExportRows(), `estoque_entradas_compra_${todayFileSuffix()}.csv`)}
                onExportPurchasesXlsx={() => exportXlsx(purchaseExportRows(), "Entradas", `estoque_entradas_compra_${todayFileSuffix()}.xlsx`)}
              />
              <BalancesTable rows={filteredBalances} productMap={productMap} locationMap={locationMap} lotsByItemLocation={lotsByItemLocation} />
              <MovementsTable rows={filteredMovements} productMap={productMap} locationMap={locationMap} />
              <PurchaseEntriesTable rows={filteredPurchaseEntries} locationMap={locationMap} />
            </section>
          ) : null}

          {activeTab === "manual" ? (
            <section>
              <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
                <h2 className="text-lg font-bold text-[var(--color-text)]">Novo movimento manual</h2>
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <Field label="Produto">
                    <SearchableSelect value={movementForm.item_id} options={productOptions} placeholder="Digite o nome, SKU ou NCM" onChange={(value) => setMovementForm((current) => ({ ...current, item_id: value }))} />
                  </Field>
                  <Field label="Local">
                    <div className="field-input flex items-center text-[var(--color-text-muted)]">{selectedLocation?.name ?? "Estoque selecionado"}</div>
                  </Field>
                  <Field label="Tipo de movimento">
                    <select value={movementForm.movement_type} onChange={(event) => setMovementForm((current) => ({ ...current, movement_type: event.target.value }))} className="field-input">
                      <option value="initial_balance">Saldo inicial</option>
                      <option value="adjustment_in">Ajuste de entrada</option>
                      <option value="adjustment_out">Ajuste de saída</option>
                    </select>
                  </Field>
                  <Field label="Quantidade">
                    <input value={movementForm.quantity} onChange={(event) => setMovementForm((current) => ({ ...current, quantity: event.target.value }))} placeholder="Ex.: 10" className="field-input" />
                  </Field>
                  <Field label="Lote obrigatório">
                    <input value={movementForm.lot_code} onChange={(event) => setMovementForm((current) => ({ ...current, lot_code: event.target.value.toUpperCase() }))} placeholder="Ex.: L2026A" className="field-input" />
                  </Field>
                  <Field label="Validade">
                    <label className="mb-2 flex cursor-pointer items-center gap-2 text-sm text-[var(--color-text-muted)]">
                      <input
                        type="checkbox"
                        checked={movementForm.hasExpiration}
                        onChange={(e) => setMovementForm((c) => ({ ...c, hasExpiration: e.target.checked, expiration_date: "" }))}
                        className="h-4 w-4 rounded accent-emerald-500"
                      />
                      Produto tem validade?
                    </label>
                    {movementForm.hasExpiration ? (
                      <input type="date" value={movementForm.expiration_date} onChange={(event) => setMovementForm((current) => ({ ...current, expiration_date: event.target.value }))} className="field-input" />
                    ) : (
                      <div className="field-input flex items-center gap-2 text-[var(--color-text-muted)]">
                        <span className="rounded-full bg-[var(--color-border-soft)] px-2 py-0.5 text-xs font-black tracking-wider">SV</span>
                        Sem validade
                      </div>
                    )}
                  </Field>
                  <Field label="Custo unitário opcional">
                    <input value={movementForm.unit_cost} onChange={(event) => setMovementForm((current) => ({ ...current, unit_cost: event.target.value }))} placeholder="Ex.: 55,90" className="field-input" />
                  </Field>
                  <Field label="Observação">
                    <input value={movementForm.notes} onChange={(event) => setMovementForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Motivo do ajuste" className="field-input" />
                  </Field>
                </div>
                <button type="button" onClick={handleCreateMovement} disabled={isSubmittingMovement} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white hover:bg-[var(--color-primary-hover)] disabled:cursor-wait disabled:opacity-70">
                  {isSubmittingMovement ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Registrar movimento e atualizar saldo
                </button>
              </div>
            </section>
          ) : null}

          {activeTab === "purchase" ? (
            <section className="space-y-6">
              <div className="grid gap-4 xl:grid-cols-3">
                <StepCard number="1" title="Importe o XML" text="O XML preenche nota, fornecedor, produtos, quantidades e custos. PDF/DANFE não serve nesta fase." tone="info" />
                <StepCard number="2" title="Confira os produtos" text="Produto sem vínculo precisa ser selecionado manualmente. Nada entra no estoque sem item cadastrado." tone="warning" />
                <StepCard number="3" title="Registre a entrada" text="Ao finalizar, o sistema cria entrada de compra, itens, movimentos purchase_in e atualiza saldos." tone="success" />
              </div>

              <div className="rounded-[2rem] border border-blue-400/30 bg-blue-500/10 p-5 shadow-xl shadow-blue-950/10">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 className="flex items-center gap-2 text-lg font-black text-blue-100"><FileInput className="h-5 w-5" /> Ler XML de NF-e de compra</h2>
                    <p className="mt-1 text-sm text-blue-100/75">Selecione o XML autorizado da NF-e. O sistema não grava nada ainda; ele só puxa os dados para conferência.</p>
                  </div>
                  <input ref={xmlInputRef} type="file" accept=".xml,text/xml,application/xml" onChange={(event) => void handleXmlFile(event.target.files?.[0] ?? null)} className="hidden" />
                  <button type="button" onClick={() => xmlInputRef.current?.click()} disabled={isReadingXml} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-blue-300/60 bg-blue-500/30 px-5 py-3 text-sm font-black text-blue-50 hover:bg-blue-500/40 disabled:cursor-wait disabled:opacity-70">
                    {isReadingXml ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />} Selecionar XML
                  </button>
                </div>
                {xmlResult ? (
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <MiniStatus label="Itens no XML" value={xmlResult.summary.total_items} tone="info" />
                    <MiniStatus label="Vinculados" value={xmlResult.summary.matched_items} tone="success" />
                    <MiniStatus label="Pendentes" value={xmlResult.summary.unmatched_items} tone={xmlResult.summary.unmatched_items > 0 ? "warning" : "success"} />
                  </div>
                ) : null}
                {xmlResult?.warnings?.length ? (
                  <div className="mt-4 rounded-2xl border border-amber-400/50 bg-amber-500/10 p-4 text-sm text-amber-100">
                    <p className="mb-2 font-black">Pontos para conferir antes de lançar:</p>
                    <ul className="list-disc space-y-1 pl-5">{xmlResult.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                  </div>
                ) : null}
              </div>

              <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 className="text-lg font-black text-[var(--color-text)]">Entrada por nota de compra</h2>
                    <p className="mt-1 text-sm text-[var(--color-text-muted)]">Preencha manualmente ou use o XML para pré-preencher. Depois confira e registre.</p>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <MiniStatus label="Itens prontos" value={purchaseReadyCount} tone="success" />
                    <MiniStatus label="Pendências" value={purchasePendingCount} tone={purchasePendingCount > 0 ? "warning" : "success"} />
                    <MiniStatus label="Total" value={formatMoney(purchaseTotal)} tone="info" />
                  </div>
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-3">
                  <Field label="Fornecedor">
                    <SearchableSelect value={purchaseForm.supplier_participant_id} options={supplierOptions} placeholder="Fornecedor da nota" onChange={(value) => setPurchaseForm((current) => ({ ...current, supplier_participant_id: value }))} />
                  </Field>
                  <Field label="Local de entrada">
                    <div className="field-input flex items-center text-[var(--color-text-muted)]">{selectedLocation?.name ?? "Estoque selecionado"}</div>
                  </Field>
                  <Field label="Data de emissão">
                    <input type="date" value={purchaseForm.issue_date} onChange={(event) => setPurchaseForm((current) => ({ ...current, issue_date: event.target.value }))} className="field-input" />
                  </Field>
                  <Field label="Número da nota">
                    <input value={purchaseForm.document_number} onChange={(event) => setPurchaseForm((current) => ({ ...current, document_number: event.target.value }))} placeholder="Ex.: 12345" className="field-input" />
                  </Field>
                  <Field label="Série">
                    <input value={purchaseForm.document_series} onChange={(event) => setPurchaseForm((current) => ({ ...current, document_series: event.target.value }))} placeholder="Ex.: 1" className="field-input" />
                  </Field>
                  <Field label="Chave de acesso">
                    <input value={purchaseForm.access_key} onChange={(event) => setPurchaseForm((current) => ({ ...current, access_key: event.target.value }))} placeholder="44 dígitos" className="field-input" />
                  </Field>
                </div>

                <div className="mt-6 rounded-3xl border border-[var(--color-border-soft)]">
                  <div className="grid grid-cols-[0.5fr_2fr_1fr_1fr_1fr_1.2fr_1fr_0.7fr] gap-3 rounded-t-3xl bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-black uppercase tracking-wide text-[var(--color-text-muted)]">
                    <span>XML</span><span>Produto no catálogo</span><span>Quantidade</span><span>Custo unit.</span><span>Lote</span><span>Validade</span><span>Situação</span><span>Ação</span>
                  </div>
                  <div className="divide-y divide-[var(--color-border-soft)]">
                    {purchaseForm.items.map((row, index) => (
                      <div key={`${row.xml_line ?? "manual"}-${index}`} className="relative grid gap-3 px-4 py-4 lg:grid-cols-[0.5fr_2fr_1fr_1fr_1fr_1.2fr_1fr_0.7fr] lg:items-start">
                        <div className="pt-1 text-sm font-black text-[var(--color-text)]">{row.xml_line ?? index + 1}</div>
                        <div className="relative z-10">
                          <SearchableSelect value={row.item_id} options={productOptions} placeholder={row.description || "Selecione o produto"} onChange={(value) => updatePurchaseItem(index, { item_id: value })} />
                          {row.description ? <p className="mt-2 text-xs text-[var(--color-text-muted)]">XML: {row.description}</p> : null}
                        </div>
                        <input value={row.quantity} onChange={(event) => updatePurchaseItem(index, { quantity: event.target.value })} className="field-input" placeholder="Qtd." />
                        <input value={row.unit_cost} onChange={(event) => updatePurchaseItem(index, { unit_cost: event.target.value })} className="field-input" placeholder="Custo" />
                        <input value={row.lot_code} onChange={(event) => updatePurchaseItem(index, { lot_code: event.target.value.toUpperCase() })} className="field-input" placeholder="Lote" />
                        <div className="flex flex-col gap-1.5">
                          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
                            <input
                              type="checkbox"
                              checked={row.hasExpiration}
                              onChange={(e) => updatePurchaseItem(index, { hasExpiration: e.target.checked, expiration_date: "" })}
                              className="h-3.5 w-3.5 rounded accent-emerald-500"
                            />
                            Tem validade?
                          </label>
                          {row.hasExpiration ? (
                            <input type="date" value={row.expiration_date ?? ""} onChange={(event) => updatePurchaseItem(index, { expiration_date: event.target.value })} className="field-input" />
                          ) : (
                            <div className="field-input flex items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
                              <span className="rounded bg-[var(--color-border-soft)] px-1.5 py-0.5 text-[10px] font-black">SV</span>
                              Sem validade
                            </div>
                          )}
                        </div>
                        <StatusPill status={row.item_id && row.lot_code.trim() && (!row.hasExpiration || row.expiration_date) ? "ok" : "warning"} label={row.item_id && row.lot_code.trim() && (!row.hasExpiration || row.expiration_date) ? matchStatusLabel(row.xml_match_status) : "Item, lote e validade obrigatórios"} />
                        <button type="button" onClick={() => removePurchaseItem(index)} className="inline-flex items-center justify-center rounded-2xl border border-red-400/40 px-3 py-2 text-sm font-bold text-red-200 hover:bg-red-500/10"><X className="h-4 w-4" /></button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <button type="button" onClick={addPurchaseItem} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border-soft)] px-4 py-3 text-sm font-bold text-[var(--color-text)] hover:bg-[var(--color-hover)]"><Plus className="h-4 w-4" /> Adicionar item manual</button>
                  <div className="text-sm text-[var(--color-text-muted)]">Quantidade total: <strong className="text-[var(--color-text)]">{formatNumber(purchaseQuantity)}</strong> · Valor total: <strong className="text-[var(--color-text)]">{formatMoney(purchaseTotal)}</strong></div>
                </div>

                <Field label="Observação da entrada" className="mt-4">
                  <textarea value={purchaseForm.notes} onChange={(event) => setPurchaseForm((current) => ({ ...current, notes: event.target.value }))} rows={3} placeholder="Ex.: entrada via XML, compra de reposição, conferida por..." className="field-input min-h-24" />
                </Field>

                <button type="button" onClick={handleCreatePurchaseEntry} disabled={isSubmittingPurchase} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary)] bg-[var(--color-primary)] px-5 py-3 text-sm font-black text-white hover:bg-[var(--color-primary-hover)] disabled:cursor-wait disabled:opacity-70">
                  {isSubmittingPurchase ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageCheck className="h-4 w-4" />} Registrar entrada e atualizar estoque
                </button>
              </div>
            </section>
          ) : null}
            </>
          )}
        </>
      )}
    </div>
  )
}



function AlertBox({ tone, icon, message }: { tone: "danger" | "success"; icon: ReactNode; message: string }) {
  const styles = tone === "danger" ? "border-red-400/50 bg-red-500/10 text-red-200" : "border-emerald-400/50 bg-emerald-500/10 text-emerald-200"
  return <div className={`flex items-start gap-3 rounded-3xl border p-4 text-sm font-semibold ${styles}`}>{icon}<span>{message}</span></div>
}

function SummaryCard({ label, value, helper, accent }: { label: string; value: string | number; helper?: string; accent: string }) {
  return <div className="rounded-3xl p-4 shadow-xl shadow-[var(--color-card-shadow)]" style={{ background: accent, border: `1px solid ${accent}` }}><p className="text-xs font-bold uppercase tracking-wide text-white/75">{label}</p><p className="mt-2 text-2xl font-black text-white">{value}</p>{helper ? <p className="mt-1 text-xs text-white/65">{helper}</p> : null}</div>
}

function MiniStatus({ label, value, tone }: { label: string; value: string | number; tone: "success" | "warning" | "info" }) {
  const toneClass = tone === "success" ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" : tone === "warning" ? "border-amber-400/40 bg-amber-500/10 text-amber-100" : "border-blue-400/40 bg-blue-500/10 text-blue-100"
  return <div className={`rounded-2xl border px-4 py-3 ${toneClass}`}><p className="text-xs font-bold uppercase opacity-75">{label}</p><p className="mt-1 text-base font-black">{value}</p></div>
}

function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return <label className={`block text-sm font-semibold text-[var(--color-text-muted)] ${className}`}><span className="mb-2 block">{label}</span>{children}</label>
}


function StepCard({ number, title, text, tone }: { number: string; title: string; text: string; tone: "info" | "warning" | "success" }) {
  const toneClass = tone === "success" ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" : tone === "warning" ? "border-amber-400/40 bg-amber-500/10 text-amber-100" : "border-blue-400/40 bg-blue-500/10 text-blue-100"
  return <div className={`rounded-3xl border p-4 ${toneClass}`}><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-black/15 text-sm font-black">{number}</span><strong>{title}</strong></div><p className="mt-3 text-sm leading-6 opacity-80">{text}</p></div>
}

function StatusPill({ status, label }: { status: "ok" | "warning"; label: string }) {
  const cls = status === "ok" ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" : "border-amber-400/40 bg-amber-500/10 text-amber-100"
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-black ${cls}`}>{label}</span>
}

function FilterPanel({ filters, setFilters, productOptions, resultCounts }: {
  filters: { item_id: string; location_id: string; movement_type: string; search: string }
  setFilters: React.Dispatch<React.SetStateAction<{ item_id: string; location_id: string; movement_type: string; search: string }>>
  productOptions: SearchableSelectOption[]
  resultCounts: { balances: number; movements: number; purchases: number }
}) {
  const hasActiveFilters = filters.search || filters.item_id || filters.movement_type
  return (
    <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2"><Filter className="h-5 w-5 text-[var(--color-primary)]" /><h2 className="text-lg font-bold text-[var(--color-text)]">Filtros</h2></div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-1 text-xs font-black text-[var(--color-text-muted)]">{resultCounts.balances} saldo{resultCounts.balances !== 1 ? "s" : ""}</span>
            <span className="rounded-full border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-1 text-xs font-black text-[var(--color-text-muted)]">{resultCounts.movements} movimento{resultCounts.movements !== 1 ? "s" : ""}</span>
            <span className="rounded-full border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] px-3 py-1 text-xs font-black text-[var(--color-text-muted)]">{resultCounts.purchases} entrada{resultCounts.purchases !== 1 ? "s" : ""}</span>
          </div>
        </div>
        <button type="button" disabled={!hasActiveFilters} onClick={() => setFilters((current) => ({ ...current, item_id: "", movement_type: "", search: "" }))} className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] px-4 py-2 text-sm font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-40"><X className="h-4 w-4" /> Limpar filtros</button>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Field label="Busca livre"><div className="relative"><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" /><input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Produto, SKU, local, nota..." className="w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface-elevated)] py-3 pl-11 pr-4 text-sm text-[var(--color-text)] outline-none focus:border-emerald-400/70" /></div></Field>
        <Field label="Produto"><SearchableSelect value={filters.item_id} options={productOptions} placeholder="Todos os produtos" onChange={(value) => setFilters((current) => ({ ...current, item_id: value }))} /></Field>
        <Field label="Tipo de movimento"><select value={filters.movement_type} onChange={(event) => setFilters((current) => ({ ...current, movement_type: event.target.value }))} className="field-input"><option value="">Todos os tipos</option><option value="initial_balance">Saldo inicial</option><option value="adjustment_in">Ajuste de entrada</option><option value="adjustment_out">Ajuste de saída</option><option value="purchase_in">Entrada por compra</option><option value="sale_out">Saída por venda</option><option value="sale_out_reversal">Reversão de venda</option></select></Field>
      </div>
    </div>
  )
}

function ExportPanel(props: {
  balancesCount: number; movementsCount: number; purchasesCount: number
  onExportBalancesCsv: () => void; onExportBalancesXlsx: () => void; onExportMovementsCsv: () => void; onExportMovementsXlsx: () => void; onExportPurchasesCsv: () => void; onExportPurchasesXlsx: () => void
}) {
  return (
    <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5">
      <div className="flex items-start gap-3"><Download className="mt-1 h-5 w-5 text-[var(--color-primary)]" /><div><h2 className="font-black text-[var(--color-text)]">Exportar listagem filtrada</h2><p className="mt-1 text-sm text-[var(--color-text-muted)]">Exporta todos os registros do filtro atual — não apenas a página visível.</p></div></div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <ExportButtonGroup title="Saldos" count={props.balancesCount} onCsv={props.onExportBalancesCsv} onXlsx={props.onExportBalancesXlsx} />
        <ExportButtonGroup title="Movimentos" count={props.movementsCount} onCsv={props.onExportMovementsCsv} onXlsx={props.onExportMovementsXlsx} />
        <ExportButtonGroup title="Entradas por nota" count={props.purchasesCount} onCsv={props.onExportPurchasesCsv} onXlsx={props.onExportPurchasesXlsx} />
      </div>
    </div>
  )
}

function ExportButtonGroup({ title, count, onCsv, onXlsx }: { title: string; count: number; onCsv: () => void; onXlsx: () => void }) {
  return (
    <div className="rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-4">
      <p className="mb-1 text-sm font-black text-[var(--color-text)]">{title}</p>
      <p className="mb-3 text-xs text-[var(--color-text-muted)]">{count} registro{count !== 1 ? "s" : ""}</p>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" onClick={onCsv} disabled={count === 0} className="rounded-2xl border border-[var(--color-border-soft)] px-3 py-2 text-sm font-bold text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] disabled:opacity-40">CSV</button>
        <button type="button" onClick={onXlsx} disabled={count === 0} className="rounded-2xl border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-sm font-bold text-emerald-100 hover:bg-emerald-500/20 disabled:opacity-40">XLSX</button>
      </div>
    </div>
  )
}

function BalancesTable({
  rows,
  productMap,
  locationMap,
  lotsByItemLocation,
}: {
  rows: StockBalance[]
  productMap: Map<string, CatalogItem>
  locationMap: Map<string, StockLocation>
  lotsByItemLocation: Map<string, StockLot[]>
}) {
  const [listPage, setListPage] = useState(1)
  useEffect(() => { setListPage(1) }, [rows])
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safeListPage = Math.min(listPage, totalPages)
  const pagedRows = rows.slice((safeListPage - 1) * PAGE_SIZE, safeListPage * PAGE_SIZE)

  const subtitle = rows.length > 0
    ? `${rows.length} registro${rows.length !== 1 ? "s" : ""} · página ${safeListPage} de ${totalPages}`
    : undefined

  return (
    <TableCard
      title="Saldos por produto e local"
      subtitle={subtitle}
      icon={<Warehouse className="h-5 w-5" />}
      empty="Nenhum saldo encontrado com os filtros atuais."
      isEmpty={rows.length === 0}
      footer={<PaginationControls listPage={safeListPage} totalPages={totalPages} setListPage={setListPage} />}
    >
      <div className="grid min-w-[1100px] grid-cols-[2fr_1.1fr_1fr_1fr_2fr_1fr_1fr] gap-3 bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-black uppercase text-[var(--color-text-muted)]">
        <span>Produto</span><span>Local</span><span>Quantidade</span><span>Custo médio</span><span>Lotes ativos</span><span>Mínimo</span><span>Situação</span>
      </div>
      <div className="divide-y divide-[var(--color-border-soft)]">
        {pagedRows.map((row) => {
          const item = productMap.get(row.item_id)
          const location = locationMap.get(row.location_id)
          const minimum = Number(item?.inventory_settings?.minimum_stock ?? 0)
          const quantity = Number(row.quantity ?? 0)
          const low = minimum > 0 && quantity <= minimum
          const lots = lotsByItemLocation.get(`${row.item_id}::${row.location_id}`) ?? []
          const lotsLabel = lots.length > 0
            ? lots.map((lot) => `${lot.lot_code} (${formatExpDate(lot.expiration_date)})`).join(" · ")
            : "-"
          return (
            <div key={`${row.item_id}-${row.location_id}`} className="grid min-w-[1100px] grid-cols-[2fr_1.1fr_1fr_1fr_2fr_1fr_1fr] gap-3 px-4 py-4 text-sm text-[var(--color-text)]">
              <span><strong>{item?.name ?? row.item_id}</strong><small className="block text-[var(--color-text-muted)]">{item?.sku ? `SKU ${item.sku}` : row.item_id}</small></span>
              <span>{location?.name ?? row.location_id}</span>
              <span className="font-black">{formatNumber(row.quantity)}</span>
              <span>{row.average_cost ? formatMoney(row.average_cost) : "-"}</span>
              <span className="text-xs">{lotsLabel}</span>
              <span>{item?.inventory_settings?.minimum_stock ?? "-"}</span>
              <span><StatusPill status={low ? "warning" : "ok"} label={low ? "Atenção" : "OK"} /></span>
            </div>
          )
        })}
      </div>
    </TableCard>
  )
}

function MovementsTable({ rows, productMap, locationMap }: { rows: StockMovement[]; productMap: Map<string, CatalogItem>; locationMap: Map<string, StockLocation> }) {
  const [listPage, setListPage] = useState(1)
  useEffect(() => { setListPage(1) }, [rows])
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safeListPage = Math.min(listPage, totalPages)
  const pagedRows = rows.slice((safeListPage - 1) * PAGE_SIZE, safeListPage * PAGE_SIZE)

  const subtitle = rows.length > 0
    ? `${rows.length} movimento${rows.length !== 1 ? "s" : ""} · página ${safeListPage} de ${totalPages}`
    : undefined

  return (
    <TableCard
      title="Movimentos de estoque"
      subtitle={subtitle}
      icon={<ClipboardList className="h-5 w-5" />}
      empty="Nenhum movimento encontrado com os filtros atuais."
      isEmpty={rows.length === 0}
      footer={<PaginationControls listPage={safeListPage} totalPages={totalPages} setListPage={setListPage} />}
    >
      <div className="grid min-w-[1180px] grid-cols-[1.5fr_1fr_1fr_1fr_1fr_1fr_1fr_1.2fr] gap-3 bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-black uppercase text-[var(--color-text-muted)]">
        <span>Produto</span><span>Tipo</span><span>Quantidade</span><span>Lote</span><span>Validade</span><span>Valor</span><span>Origem</span><span>Data</span>
      </div>
      <div className="divide-y divide-[var(--color-border-soft)]">
        {pagedRows.map((row) => {
          const item = productMap.get(row.item_id)
          return (
            <div key={row.id} className="grid min-w-[1180px] grid-cols-[1.5fr_1fr_1fr_1fr_1fr_1fr_1fr_1.2fr] gap-3 px-4 py-4 text-sm text-[var(--color-text)]">
              <span><strong>{item?.name ?? row.item_id}</strong><small className="block text-[var(--color-text-muted)]">{locationMap.get(row.location_id)?.name ?? row.location_id}</small></span>
              <span>{labelMovementType(row.movement_type)}</span>
              <span className={`font-black ${row.direction === "in" ? "text-emerald-400" : "text-rose-400"}`}>{row.direction === "in" ? "+" : "−"}{formatNumber(row.quantity)}</span>
              <span>{row.lot_code ?? "-"}</span>
              <span>{formatExpDate(row.expiration_date)}</span>
              <span>{row.total_cost ? formatMoney(row.total_cost) : "-"}</span>
              <span>{sourceLabel(row.source_type)}</span>
              <span>{formatDateTime(row.movement_date)}</span>
            </div>
          )
        })}
      </div>
    </TableCard>
  )
}

function PurchaseEntriesTable({ rows, locationMap }: { rows: StockPurchaseEntry[]; locationMap: Map<string, StockLocation> }) {
  const [listPage, setListPage] = useState(1)
  useEffect(() => { setListPage(1) }, [rows])
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safeListPage = Math.min(listPage, totalPages)
  const pagedRows = rows.slice((safeListPage - 1) * PAGE_SIZE, safeListPage * PAGE_SIZE)

  const subtitle = rows.length > 0
    ? `${rows.length} entrada${rows.length !== 1 ? "s" : ""} · página ${safeListPage} de ${totalPages}`
    : undefined

  return (
    <TableCard
      title="Entradas por nota de compra"
      subtitle={subtitle}
      icon={<FilePlus2 className="h-5 w-5" />}
      empty="Nenhuma entrada de compra encontrada com os filtros atuais."
      isEmpty={rows.length === 0}
      footer={<PaginationControls listPage={safeListPage} totalPages={totalPages} setListPage={setListPage} />}
    >
      <div className="grid min-w-[1160px] grid-cols-[1fr_1.3fr_1fr_2fr_1fr_1fr_1fr] gap-3 bg-[var(--color-surface-elevated)] px-4 py-3 text-xs font-black uppercase text-[var(--color-text-muted)]">
        <span>Nota</span><span>Fornecedor</span><span>Local</span><span>Lotes</span><span>Itens</span><span>Valor</span><span>Entrada</span>
      </div>
      <div className="divide-y divide-[var(--color-border-soft)]">
        {pagedRows.map((entry) => {
          const supplierName = typeof entry.supplier_snapshot?.name === "string" ? entry.supplier_snapshot.name : "-"
          const lotsLabel = (entry.items ?? []).map((item) => `${item.lot_code ?? "-"} (${formatExpDate(item.expiration_date)})`).join(" · ")
          return (
            <div key={entry.id} className="grid min-w-[1160px] grid-cols-[1fr_1.3fr_1fr_2fr_1fr_1fr_1fr] gap-3 px-4 py-4 text-sm text-[var(--color-text)]">
              <span><strong>{entry.document_number ?? "sem número"}</strong><small className="block text-[var(--color-text-muted)]">Série {entry.document_series ?? "-"}</small></span>
              <span>{supplierName}</span>
              <span>{locationMap.get(entry.location_id)?.name ?? entry.location_id}</span>
              <span className="text-xs">{lotsLabel || "-"}</span>
              <span>{entry.total_items} · {formatNumber(entry.total_quantity)}</span>
              <span>{formatMoney(entry.total_amount)}</span>
              <span>{formatDateTime(entry.entry_date)}</span>
            </div>
          )
        })}
      </div>
    </TableCard>
  )
}

function TableCard({ title, subtitle, icon, empty, isEmpty, children, footer }: { title: string; subtitle?: string; icon: ReactNode; empty: string; isEmpty: boolean; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] shadow-xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border-soft)] px-5 py-4">
        <div className="flex items-center gap-2">
          <span className="text-[var(--color-primary)]">{icon}</span>
          <div>
            <h2 className="font-black text-[var(--color-text)]">{title}</h2>
            {subtitle ? <p className="text-xs text-[var(--color-text-muted)]">{subtitle}</p> : null}
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        {isEmpty ? <div className="p-6 text-sm text-[var(--color-text-muted)]">{empty}</div> : children}
      </div>
      {!isEmpty && footer ? footer : null}
    </div>
  )
}
