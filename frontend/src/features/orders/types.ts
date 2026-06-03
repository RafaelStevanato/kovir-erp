/** Estados do ciclo de vida de um Pedido (equivale ao Sale no backend). */
export type OrderStatus = "quote" | "closed" | "paid" | "cancelled"

export type OrderSaleType = "product" | "service"

export type OrderOrigin =
  | "manual"
  | "imported"
  | "integration"
  | "marketplace"
  | "unknown"

export type OrderOperationNature =
  | "normal_sale"
  | "bonus"
  | "sample"
  | "exchange"
  | "courtesy"
  | "replacement"
  | "other"

export type PaymentMethodCode =
  | "pix"
  | "credit_card"
  | "debit_card"
  | "cash"
  | "boleto"
  | "bank_transfer"
  | "store_credit"
  | "other"

export type OrderPaymentPlan = {
  id: string
  company_id: string
  sale_id: string
  payment_method_id: string
  payment_method_code: PaymentMethodCode
  payment_method_name: string
  amount: string
  due_date: string | null
  installments: number
  status: "planned" | "generated" | "cancelled"
  notes: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type OrderItem = {
  id: string
  company_id: string
  sale_id: string
  item_id: string
  stock_lot_id: string | null
  stock_lot_code: string | null
  stock_lot_expiration_date: string | null
  fiscal_classification_id: string | null
  description: string
  quantity: string
  unit: string
  unit_price: string
  discount_amount: string
  freight_amount: string
  tax_amount: string
  total_amount: string
  item_snapshot: Record<string, unknown>
  fiscal_snapshot: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export type Order = {
  id: string
  company_id: string
  establishment_id: string | null
  participant_id: string
  status: OrderStatus
  sale_type: OrderSaleType
  origin: OrderOrigin
  operation_nature: OrderOperationNature
  operation_nature_id: string | null
  operation_nature_reason: string | null
  issue_date: string | null
  operation_date: string
  subtotal_amount: string
  discount_amount: string
  discount_type: string
  discount_percentage: string | null
  freight_amount: string
  tax_amount: string
  total_amount: string
  receivable_total_amount: string
  participant_snapshot: Record<string, unknown>
  notes: string | null
  // Campos do ciclo de vida (novos)
  sale_number: number | null
  sale_number_text: string | null
  paid_number_text: string | null
  closed_at: string | null
  paid_at: string | null
  closed_by: string | null
  paid_by: string | null
  unlocked_by: string | null
  unlocked_at: string | null
  // Relações
  items: OrderItem[]
  payment_plans: OrderPaymentPlan[]
  created_at: string
  updated_at: string
  cancelled_at: string | null
}

export type OrderStatusHistory = {
  id: string
  company_id: string
  sale_id: string
  previous_status: OrderStatus | null
  new_status: OrderStatus
  reason: string | null
  source: string
  actor_id: string | null
  occurred_at: string
}

export type OrderStatusChangePayload = {
  reason?: string | null
}

export type ReopenOrderPayload = {
  master_password: string
  reason: string
}

export type OrderItemCreatePayload = {
  item_id: string
  stock_lot_id?: string | null
  stock_lot_code?: string | null
  stock_lot_expiration_date?: string | null
  description?: string | null
  quantity: string
  unit?: string | null
  unit_price?: string | null
  discount_amount: string
  freight_amount: string
  tax_amount: string
}

export type OrderPaymentPlanCreatePayload = {
  payment_method_code?: PaymentMethodCode | null
  amount: string
  due_date?: string | null
  notes?: string | null
}

export type OrderCreatePayload = {
  company_id: string
  participant_id: string
  sale_type: OrderSaleType
  origin: OrderOrigin
  operation_nature: OrderOperationNature
  discount_amount: string
  freight_amount: string
  tax_amount: string
  notes?: string | null
  payment_plans: OrderPaymentPlanCreatePayload[]
  items: OrderItemCreatePayload[]
}
