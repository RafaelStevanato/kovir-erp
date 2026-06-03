import { Home, Menu } from "lucide-react"
import { useState, type ReactNode } from "react"

import { getAuthSession } from "../config/authSession"
import { useActiveCompany } from "../config/useActiveCompany"
import { ThemeToggle } from "../components/ThemeToggle"
import { Sidebar } from "./Sidebar"

export type AppView = "overview" | "company" | "participants" | "catalog" | "fiscalClassification" | "orders" | "productSales" | "marketplaces" | "mercadoPago" | "stock" | "financial" | "accountsReceivable" | "cash" | "reconciliation" | "cashFlow" | "purchasesPayables" | "managementReports" | "biAnalytics" | "easyManagement" | "ai" | "technicalRegression" | "security" | "stressTests" | "imports"

type AppShellProps = {
  children: ReactNode
  activeView: AppView
  onNavigate: (view: AppView) => void
}

export function AppShell({ children, activeView, onNavigate }: AppShellProps) {
  const authSession = getAuthSession()
  const { activeCompanyName, companyId } = useActiveCompany()
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window === "undefined") return true

    return window.matchMedia("(min-width: 1024px)").matches
  })

  function goToOverview() {
    onNavigate("overview")
  }

  return (
    <main className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] transition-colors">
      <div className="flex min-h-screen">
        <Sidebar
          isOpen={isSidebarOpen}
          activeView={activeView}
          onNavigate={onNavigate}
          onClose={() => setIsSidebarOpen(false)}
        />

        <section className="flex-1 p-4 transition-all duration-300 ease-out sm:p-6 lg:p-8">
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setIsSidebarOpen(true)}
              className={`items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-4 py-3 text-sm font-semibold text-[var(--color-text)] shadow-lg shadow-[var(--color-card-shadow)] transition-all duration-200 ease-out hover:-translate-y-0.5 hover:bg-[var(--color-hover)] ${
                isSidebarOpen ? "flex lg:hidden" : "flex"
              }`}
              aria-label="Abrir menu lateral"
              title="Abrir menu lateral"
            >
              <Menu className="h-4 w-4" />
              <span className="hidden sm:inline">Abrir menu</span>
              <span className="sm:hidden">Menu</span>
            </button>

            <button
              type="button"
              onClick={goToOverview}
              className="flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-semibold text-[var(--color-primary)] shadow-lg shadow-[var(--color-card-shadow)] transition-all duration-200 ease-out hover:-translate-y-0.5 hover:bg-[var(--color-hover)]"
              aria-label="Ir para visão geral"
              title="Ir para visão geral"
            >
              <Home className="h-4 w-4" />
              <span className="hidden sm:inline">Visão geral</span>
            </button>

            <div className="ml-auto flex min-w-0 items-center gap-2">
              <div className="hidden rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-xs font-semibold text-[var(--color-text-muted)] sm:block">
                Empresa: {activeCompanyName || "Não identificada"}
              </div>
              <ThemeToggle />
            </div>
          </div>

          <div key={companyId || authSession?.companyId || "sem-empresa-ativa"}>{children}</div>
        </section>
      </div>
    </main>
  )
}
