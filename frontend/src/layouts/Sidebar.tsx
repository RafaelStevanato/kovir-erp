import {
  BarChart3,
  Banknote,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  Database,
  FileText,
  Home,
  LogOut,
  Package,
  Radar,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Upload,
  Users,
  X,
} from "lucide-react"
import { useState } from "react"

import { canAccessView } from "../config/accessControl"
import { clearAuthSession, getAuthSession } from "../config/authSession"
import { useActiveCompany } from "../config/useActiveCompany"
import { logout } from "../features/security/securityApi"
import { preloadAppView } from "../routes/lazyViews"
import type { AppView } from "./AppShell"

type SidebarProps = {
  isOpen: boolean
  activeView: AppView
  onNavigate: (view: AppView) => void
  onClose: () => void
}

type NavItem = { label: string; view: AppView; icon: React.ReactNode }
type NavGroup = { group: string; accent: string; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  {
    group: "Cadastros",
    accent: "#f8fafc",
    items: [
      { label: "Empresa",              view: "company",              icon: <Building2 className="h-4 w-4" /> },
      { label: "Participantes",        view: "participants",         icon: <Users className="h-4 w-4" /> },
      { label: "Produtos e Serviços",  view: "catalog",              icon: <Package className="h-4 w-4" /> },
      { label: "Classificação Fiscal", view: "fiscalClassification", icon: <FileText className="h-4 w-4" /> },
    ],
  },
  {
    group: "Comercial",
    accent: "#38bdf8",
    items: [
      { label: "Pedidos",  view: "orders", icon: <ClipboardList className="h-4 w-4" /> },
      { label: "Estoque",  view: "stock",  icon: <Boxes className="h-4 w-4" /> },
    ],
  },
  {
    group: "Financeiro",
    accent: "#10b981",
    items: [
      { label: "Financeiro Base",      view: "financial",          icon: <Banknote className="h-4 w-4" /> },
      { label: "Contas a Receber",     view: "accountsReceivable", icon: <ReceiptText className="h-4 w-4" /> },
      { label: "Caixa e Baixas",       view: "cash",               icon: <CreditCard className="h-4 w-4" /> },
      { label: "Fluxo de Caixa",       view: "cashFlow",           icon: <TrendingUp className="h-4 w-4" /> },
      { label: "Conciliação Bancária", view: "reconciliation",     icon: <CheckCircle2 className="h-4 w-4" /> },
    ],
  },
  {
    group: "Compras",
    accent: "#f59e0b",
    items: [
      { label: "Compras e Contas a Pagar", view: "purchasesPayables", icon: <FileText className="h-4 w-4" /> },
    ],
  },
  {
    group: "Gestão",
    accent: "#6358d7",
    items: [
      { label: "Relatórios Gerenciais", view: "managementReports",   icon: <BarChart3 className="h-4 w-4" /> },
      { label: "BI / KPIs",              view: "biAnalytics",         icon: <TrendingUp className="h-4 w-4" /> },
      { label: "Gestão Fácil",           view: "easyManagement",      icon: <Sparkles className="h-4 w-4" /> },
      { label: "Inteligência Artificial", view: "ai",                icon: <Sparkles className="h-4 w-4" /> },
      { label: "Segurança e Alçadas",   view: "security",            icon: <ShieldCheck className="h-4 w-4" /> },
      { label: "Regressão Técnica",     view: "technicalRegression", icon: <Radar className="h-4 w-4" /> },
      { label: "Stress Tests",          view: "stressTests",         icon: <Database className="h-4 w-4" /> },
      { label: "Importações",           view: "imports",             icon: <Upload className="h-4 w-4" /> },
    ],
  },
]

export function Sidebar({ isOpen, activeView, onNavigate, onClose }: SidebarProps) {
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const authSession = getAuthSession()
  const { activeCompanyName } = useActiveCompany()

  function handleNavigate(view: AppView) {
    onNavigate(view)
    onClose()
  }

  function handlePreload(view: AppView) {
    void preloadAppView(view)
  }

  async function handleLogout() {
    if (isLoggingOut) return
    setIsLoggingOut(true)
    try {
      await logout()
    } catch {
      // noop
    } finally {
      clearAuthSession()
      window.location.reload()
    }
  }

  return (
    <>
      {isOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 lg:hidden"
          style={{ background: "rgba(2,6,23,0.7)", backdropFilter: "blur(4px)" }}
          onClick={onClose}
          aria-label="Fechar menu lateral"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 min-h-screen w-72 overflow-hidden transition-all duration-300 ease-out lg:sticky lg:top-0 lg:z-auto lg:block ${
          isOpen ? "translate-x-0 opacity-100 lg:w-72" : "-translate-x-full opacity-0 lg:w-0 lg:-translate-x-4"
        }`}
        style={{
          background: "#020617",
          borderRight: "1px solid rgba(255,255,255,0.13)",
        }}
        aria-hidden={!isOpen}
      >
        {/* Inner scroll container */}
        <div className="flex h-full w-72 flex-col overflow-y-auto">

          {/* ── Header ──────────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between gap-3 p-5 pb-4">
            <div className="flex items-center gap-3">
              <img
                src="/kovir-logo.png"
                alt="Kovir"
                className="h-9 w-9 shrink-0 object-contain"
                style={{ filter: "drop-shadow(0 0 10px rgba(16,185,129,0.55))" }}
              />
              <div>
                <p className="text-sm font-black" style={{ color: "#f8fafc" }}>Kovir</p>
                <p className="text-[11px]" style={{ color: "rgba(248,250,252,0.65)" }}>
                  {activeCompanyName || "Sem sessão"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => { handleNavigate("overview") }}
                className="flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200"
                style={{ background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.25)", color: "#10b981" }}
                aria-label="Visão Geral"
                title="Visão Geral"
              >
                <Home className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200"
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.13)", color: "rgba(248,250,252,0.82)" }}
                aria-label="Recolher menu"
                title="Recolher menu"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Thin separator */}
          <div className="mx-5 mb-4" style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />

          {/* ── Nav ─────────────────────────────────────────────────────────── */}
          <nav className="flex-1 space-y-5 px-3 pb-4">
            {NAV_GROUPS.map((grp) => {
              const visible = grp.items.filter((item) => canAccessView(item.view, authSession))
              if (visible.length === 0) return null

              return (
                <div key={grp.group} className="space-y-1">
                  {/* Group label */}
                  <div className="mb-2 flex items-center gap-2 px-2">
                    <div
                      className="h-px flex-1"
                      style={{ background: `linear-gradient(90deg, ${grp.accent}88, transparent)` }}
                    />
                    <span
                      className="text-[9px] font-black tracking-[0.3em] uppercase"
                      style={{ color: `${grp.accent}EE` }}
                    >
                      {grp.group}
                    </span>
                  </div>

                  {/* Items */}
                  {visible.map((item) => {
                    const active = activeView === item.view
                    return (
                      <button
                        key={item.view}
                        type="button"
                        onClick={() => handleNavigate(item.view)}
                        onMouseEnter={() => handlePreload(item.view)}
                        onFocus={() => handlePreload(item.view)}
                        className="group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-all duration-200"
                        style={
                          active
                            ? {
                                background: `${grp.accent}18`,
                                border: `1px solid ${grp.accent}40`,
                                color: grp.accent,
                              }
                            : {
                                background: "transparent",
                                border: "1px solid transparent",
                                color: "rgba(248,250,252,0.85)",
                              }
                        }
                        onMouseOver={(e) => {
                          if (!active) {
                            ;(e.currentTarget as HTMLButtonElement).style.background = `${grp.accent}18`
                            ;(e.currentTarget as HTMLButtonElement).style.color = "#f8fafc"
                          }
                        }}
                        onMouseOut={(e) => {
                          if (!active) {
                            ;(e.currentTarget as HTMLButtonElement).style.background = "transparent"
                            ;(e.currentTarget as HTMLButtonElement).style.color = "rgba(248,250,252,0.85)"
                          }
                        }}
                      >
                        {/* Icon */}
                        <span
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-all duration-200"
                          style={
                            active
                              ? { background: `${grp.accent}22`, color: grp.accent }
                              : { background: `${grp.accent}18`, color: `${grp.accent}CC` }
                          }
                        >
                          {item.icon}
                        </span>
                        <span className="truncate text-[13px] font-semibold">{item.label}</span>
                        {/* Active dot */}
                        {active && (
                          <span
                            className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full"
                            style={{ background: grp.accent, boxShadow: `0 0 6px ${grp.accent}` }}
                          />
                        )}
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </nav>

          {/* ── Footer / Logout ─────────────────────────────────────────────── */}
          <div className="p-4 pt-0">
            <div className="mb-3" style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />
            <button
              type="button"
              onClick={() => void handleLogout()}
              disabled={isLoggingOut}
              className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-all duration-200 disabled:opacity-60"
              style={{
                background: "rgba(239,68,68,0.08)",
                border: "1px solid rgba(239,68,68,0.2)",
                color: "#fca5a5",
              }}
            >
              <LogOut className="h-4 w-4" />
              {isLoggingOut ? "Saindo…" : "Logout"}
            </button>
          </div>

        </div>

        {/* Ambient glow — purely decorative */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 h-48 w-48 -translate-x-1/2 translate-y-1/4"
          style={{ background: "radial-gradient(circle, rgba(16,185,129,0.12) 0%, transparent 70%)", filter: "blur(40px)" }}
        />
        <div
          className="pointer-events-none absolute right-0 top-1/3 h-32 w-32 translate-x-1/2"
          style={{ background: "radial-gradient(circle, rgba(99,88,215,0.1) 0%, transparent 70%)", filter: "blur(35px)" }}
        />
      </aside>
    </>
  )
}
