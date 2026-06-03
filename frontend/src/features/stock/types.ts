export type StockLocation = {
  id: string
  company_id: string
  establishment_id?: string | null
  code: string
  name: string
  location_type: string
  is_default: boolean
  status: string
  settings?: Record<string, unknown> | null
  notes?: string | null
  created_at: string
  updated_at: string
}

export type StockLocationCreatePayload = {
  company_id: string
  code: string
  name: string
  location_type: string
  is_default: boolean
  notes?: string | null
}

export type StockMovement = {
  id: string
  company_id: string
  item_id: string
  location_id: string
  movement_type: string
  direction: string
  movement_date: string
  quantity: string
  unit: string
  unit_cost?: string | null
  total_cost?: string | null
  source_type?: string | null
  source_id?: string | null
  lot_id?: string | null
  lot_code?: string | null
  expiration_date?: string | null
  sale_id?: string | null
  sale_item_id?: string | null
  status: string
  notes?: string | null
  created_at: string
}

export type StockBalance = {
  company_id: string
  item_id: string
  location_id: string
  quantity: string
  average_cost?: string | null
  updated_at: string
}

export type StockLot = {
  id: string
  company_id: string
  item_id: string
  location_id: string
  lot_code: string
  expiration_date: string
  quantity: string
  average_cost?: string | null
  status: string
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
  is_expired?: boolean
}


export type StockItemAvailability = {
  company_id: string
  item_id: string
  item_name?: string | null
  track_stock: boolean
  allow_negative_stock: boolean
  unit: string
  location_id: string
  location_name: string
  default_location_id: string
  default_location_name: string
  location_quantity: string
  available_quantity: string
  total_quantity: string
  lot_balance_quantity?: string
  has_required_lot_data?: boolean
  can_sell_now: boolean
  availability_status: string
  block_reason?: string | null
  balances: StockBalance[]
  lots?: StockLot[]
}

export type StockDiagnostics = {
  module: string
  company_id: string
  status: string
  storage: string
  persistence: string
  tables: string[]
  total_locations: number
  total_movements: number
  total_purchase_entries?: number
  total_audit_events: number
  available_operations: string[]
  technical_notes: string[]
}

export type StockMovementCreatePayload = {
  company_id: string
  item_id: string
  location_id?: string | null
  movement_type: string
  quantity: string
  unit?: string | null
  unit_cost?: string | null
  lot_code: string
  expiration_date: string | null
  notes?: string | null
  metadata?: Record<string, unknown> | null
}

export type StockPurchaseEntryItem = {
  id: string
  company_id: string
  purchase_entry_id: string
  item_id: string
  lot_id?: string | null
  lot_code?: string | null
  expiration_date?: string | null
  stock_movement_id: string
  description: string
  quantity: string
  unit: string
  unit_cost?: string | null
  total_cost?: string | null
  item_snapshot?: Record<string, unknown> | null
  created_at: string
}

export type StockPurchaseEntry = {
  id: string
  company_id: string
  supplier_participant_id?: string | null
  location_id: string
  document_type: string
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  issue_date?: string | null
  entry_date: string
  status: string
  total_items: number
  total_quantity: string
  total_amount: string
  supplier_snapshot?: Record<string, unknown> | null
  document_snapshot?: Record<string, unknown> | null
  metadata?: Record<string, unknown> | null
  notes?: string | null
  created_at: string
  updated_at: string
  items?: StockPurchaseEntryItem[] | null
}

export type StockPurchaseEntryItemCreatePayload = {
  item_id: string
  quantity: string
  unit_cost?: string | null
  unit?: string | null
  lot_code: string
  expiration_date: string | null
  description?: string | null
}

export type StockPurchaseEntryCreatePayload = {
  company_id: string
  supplier_participant_id?: string | null
  location_id?: string | null
  document_type: string
  document_number?: string | null
  document_series?: string | null
  access_key?: string | null
  issue_date?: string | null
  notes?: string | null
  metadata?: Record<string, unknown> | null
  items: StockPurchaseEntryItemCreatePayload[]
}

export type StockPurchaseXmlParsedItem = {
  line_number: number
  external_code?: string | null
  barcode?: string | null
  barcode_tax?: string | null
  description?: string | null
  ncm?: string | null
  cfop?: string | null
  unit: string
  quantity: string
  unit_cost: string
  total_cost: string
  matched_item_id?: string | null
  matched_item_label?: string | null
  match_status: string
  match_confidence: string
}

export type StockPurchaseXmlParseResult = {
  document: {
    document_type: string
    document_number?: string | null
    document_series?: string | null
    access_key?: string | null
    issue_date?: string | null
    total_amount?: string | null
  }
  supplier: {
    name?: string | null
    trade_name?: string | null
    document?: string | null
    participant_id?: string | null
    match_status: string
  }
  items: StockPurchaseXmlParsedItem[]
  summary: {
    total_items: number
    matched_items: number
    unmatched_items: number
  }
  warnings: string[]
}
