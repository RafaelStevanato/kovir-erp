import { lazy, type ComponentType, type LazyExoticComponent } from "react"

import { isAppViewEnabled } from "../config/moduleScope"
import type { AppView } from "../layouts/AppShell"

type LazyAppView = Exclude<AppView, "overview">

type LazyModule<T extends ComponentType = ComponentType> = LazyExoticComponent<T> & {
  preload: () => Promise<{ default: T }>
}

function lazyWithPreload<T extends ComponentType>(factory: () => Promise<{ default: T }>): LazyModule<T> {
  let promise: Promise<{ default: T }> | null = null

  const load = () => {
    promise = factory()
    return promise
  }

  const Component = lazy(load) as LazyModule<T>
  Component.preload = load

  return Component
}

const CompanyPage = lazyWithPreload(() =>
  import("../features/company/CompanyPage").then((module) => ({ default: module.CompanyPage })),
)

const ParticipantsPage = lazyWithPreload(() =>
  import("../features/participants/ParticipantsPage").then((module) => ({ default: module.ParticipantsPage })),
)

const CatalogPage = lazyWithPreload(() =>
  import("../features/catalog/CatalogPage").then((module) => ({ default: module.CatalogPage })),
)

const FiscalClassificationPage = lazyWithPreload(() =>
  import("../features/fiscalClassification/FiscalClassificationPage").then((module) => ({ default: module.FiscalClassificationPage })),
)

const OrdersPage = lazyWithPreload(() =>
  import("../features/orders/OrdersPage").then((module) => ({ default: module.OrdersPage })),
)

const ProductSalesPage = lazyWithPreload(() =>
  import("../features/sales/SalesPage").then((module) => ({ default: module.ProductSalesPage })),
)


const MarketplacesPage = lazyWithPreload(() =>
  import("../features/marketplaces/MarketplacesPage").then((module) => ({ default: module.MarketplacesPage })),
)

const MercadoPagoPage = lazyWithPreload(() =>
  import("../features/mercadoPago/MercadoPagoPage").then((module) => ({ default: module.MercadoPagoPage })),
)

const StockPage = lazyWithPreload(() =>
  import("../features/stock/StockPage").then((module) => ({ default: module.StockPage })),
)

const FinancialMasterDataPage = lazyWithPreload(() =>
  import("../features/financial/FinancialMasterDataPage").then((module) => ({ default: module.FinancialMasterDataPage })),
)

const AccountsReceivablePage = lazyWithPreload(() =>
  import("../features/accountsReceivable/AccountsReceivablePage").then((module) => ({ default: module.AccountsReceivablePage })),
)

const CashPage = lazyWithPreload(() =>
  import("../features/cash/CashPage").then((module) => ({ default: module.CashPage })),
)

const ReconciliationPage = lazyWithPreload(() =>
  import("../features/reconciliation/ReconciliationPage").then((module) => ({ default: module.ReconciliationPage })),
)

const CashFlowPage = lazyWithPreload(() =>
  import("../features/cashFlow/CashFlowPage").then((module) => ({ default: module.CashFlowPage })),
)

const PurchasesPayablesPage = lazyWithPreload(() =>
  import("../features/purchasesPayables/PurchasesPayablesPage").then((module) => ({ default: module.PurchasesPayablesPage })),
)

const ManagementReportsPage = lazyWithPreload(() =>
  import("../features/managementReports/ManagementReportsPage").then((module) => ({ default: module.ManagementReportsPage })),
)

const BiAnalyticsPage = lazyWithPreload(() =>
  import("../features/biAnalytics/BiAnalyticsPage").then((module) => ({ default: module.BiAnalyticsPage })),
)

const EasyManagementPage = lazyWithPreload(() =>
  import("../features/easyManagement/EasyManagementPage").then((module) => ({ default: module.EasyManagementPage })),
)

const AiPage = lazyWithPreload(() =>
  import("../features/ai/AiPage").then((module) => ({ default: module.AiPage })),
)

const TechnicalRegressionPage = lazyWithPreload(() =>
  import("../features/technicalRegression/TechnicalRegressionPage").then((module) => ({ default: module.TechnicalRegressionPage })),
)

const SecurityPage = lazyWithPreload(() =>
  import("../features/security/SecurityPage").then((module) => ({ default: module.SecurityPage })),
)

const StressTestsPage = lazyWithPreload(() =>
  import("../features/stressTests/StressTestsPage").then((module) => ({ default: module.StressTestsPage })),
)

const ImportsPage = lazyWithPreload(() =>
  import("../features/imports/ImportsPage").then((module) => ({ default: module.ImportsPage })),
)

const lazyViewRegistry: Record<LazyAppView, LazyModule> = {
  company: CompanyPage,
  participants: ParticipantsPage,
  catalog: CatalogPage,
  fiscalClassification: FiscalClassificationPage,
  orders: OrdersPage,
  productSales: ProductSalesPage,
  marketplaces: MarketplacesPage,
  mercadoPago: MercadoPagoPage,
  stock: StockPage,
  financial: FinancialMasterDataPage,
  accountsReceivable: AccountsReceivablePage,
  cash: CashPage,
  reconciliation: ReconciliationPage,
  cashFlow: CashFlowPage,
  purchasesPayables: PurchasesPayablesPage,
  managementReports: ManagementReportsPage,
  biAnalytics: BiAnalyticsPage,
  easyManagement: EasyManagementPage,
  ai: AiPage,
  technicalRegression: TechnicalRegressionPage,
  security: SecurityPage,
  stressTests: StressTestsPage,
  imports: ImportsPage,
}

export function isLazyAppView(view: AppView): view is LazyAppView {
  return view !== "overview"
}

export function getLazyView(view: LazyAppView): LazyModule {
  return lazyViewRegistry[view]
}

export function preloadAppView(view: AppView) {
  if (!isLazyAppView(view)) return Promise.resolve(null)
  if (!isAppViewEnabled(view)) return Promise.resolve(null)

  return lazyViewRegistry[view].preload()
}

export function getViewLoadingLabel(view: AppView) {
  const labels: Record<AppView, string> = {
    overview: "Visão geral",
    company: "Empresa",
    participants: "Participantes",
    catalog: "Produtos e serviços",
    fiscalClassification: "Fiscal",
    orders: "Pedidos",
    productSales: "Frente de Caixa",
    marketplaces: "Marketplaces",
    mercadoPago: "Mercado Pago",
    stock: "Estoque",
    financial: "Financeiro",
    accountsReceivable: "Contas a Receber",
    cash: "Recebimentos e baixas",
    reconciliation: "Conciliação bancária",
    cashFlow: "Fluxo de Caixa",
    purchasesPayables: "Compras e Contas a Pagar",
    managementReports: "Relatórios gerenciais",
    biAnalytics: "BI / KPIs",
    easyManagement: "Gestão Fácil",
    ai: "Inteligência Artificial",
    technicalRegression: "Regressão técnica",
    security: "Usuários e permissões",
    stressTests: "Stress e Testes",
    imports: "Importações",
  }

  return labels[view]
}
