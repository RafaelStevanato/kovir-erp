import { Suspense, useState, type ReactNode } from "react"
import {
  ArrowRight,
  BarChart3,
  Banknote,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  Database,
  FileText,
  Package,
  Radar,
  ReceiptText,
  ShieldCheck,
  TrendingUp,
  Upload,
  Users,
} from "lucide-react"

import { canAccessView } from "../config/accessControl"
import { getAuthSession } from "../config/authSession"
import { isAppViewEnabled } from "../config/moduleScope"
import { AppShell, type AppView } from "../layouts/AppShell"
import { getLazyView, getViewLoadingLabel, isLazyAppView, preloadAppView } from "../routes/lazyViews"

type DashboardView = AppView

type ModuleItem = { view: AppView; label: string; desc: string; icon: ReactNode }
type ModuleGroup = { group: string; accent: string; items: ModuleItem[] }

const MODULE_GROUPS: ModuleGroup[] = [
  {
    group: "Cadastros",
    accent: "#64748b",
    items: [
      { view: "company",               label: "Empresa",                 desc: "Dados gerais e configurações da empresa",            icon: <Building2 className="h-4 w-4" /> },
      { view: "participants",          label: "Participantes",           desc: "Clientes, fornecedores e contatos",                  icon: <Users className="h-4 w-4" /> },
      { view: "catalog",               label: "Produtos e Serviços",     desc: "Catálogo com preços, custos e controle de estoque",  icon: <Package className="h-4 w-4" /> },
      { view: "fiscalClassification",  label: "Classificação Fiscal",    desc: "Perfis tributários e regras fiscais",                icon: <FileText className="h-4 w-4" /> },
    ],
  },
  {
    group: "Comercial",
    accent: "#38bdf8",
    items: [
      { view: "orders",         label: "Pedidos",          desc: "Pedidos B2B/B2C e pré-venda comercial",           icon: <ClipboardList className="h-4 w-4" /> },
      { view: "stock",          label: "Estoque",           desc: "Saldos, entradas, saídas e movimentos",           icon: <Boxes className="h-4 w-4" /> },
    ],
  },
  {
    group: "Financeiro",
    accent: "#10b981",
    items: [
      { view: "financial",          label: "Financeiro Base",        desc: "Contas, categorias e condições de pagamento",         icon: <Banknote className="h-4 w-4" /> },
      { view: "accountsReceivable", label: "Contas a Receber",       desc: "Títulos e recebíveis gerados por vendas",             icon: <ReceiptText className="h-4 w-4" /> },
      { view: "cash",               label: "Caixa e Baixas",         desc: "Recebimentos e movimentos financeiros internos",      icon: <CreditCard className="h-4 w-4" /> },
      { view: "cashFlow",           label: "Fluxo de Caixa",         desc: "Previsto, realizado e pendências integradas",         icon: <TrendingUp className="h-4 w-4" /> },
      { view: "reconciliation",     label: "Conciliação Bancária",   desc: "Match de extrato e movimentos internos",              icon: <CheckCircle2 className="h-4 w-4" /> },
    ],
  },
  {
    group: "Compras",
    accent: "#f59e0b",
    items: [
      { view: "purchasesPayables", label: "Compras e Contas a Pagar", desc: "Despesas, obrigações financeiras e pagamentos", icon: <FileText className="h-4 w-4" /> },
    ],
  },
  {
    group: "Gestão",
    accent: "#6358d7",
    items: [
      { view: "managementReports",    label: "Relatórios Gerenciais", desc: "Saúde financeira, indicadores e pendências",         icon: <BarChart3 className="h-4 w-4" /> },
      { view: "biAnalytics",          label: "BI / KPIs",              desc: "KPIs executivos, aging, tendências e Power BI Hub",   icon: <TrendingUp className="h-4 w-4" /> },
      { view: "security",             label: "Segurança e Alçadas",   desc: "Usuários, papéis, permissões e aprovações",          icon: <ShieldCheck className="h-4 w-4" /> },
      { view: "technicalRegression",  label: "Regressão Técnica",     desc: "Validação permanente de banco e schemas",            icon: <Radar className="h-4 w-4" /> },
      { view: "stressTests",          label: "Stress Tests",          desc: "Geração de massa de dados sintéticos para testes",   icon: <Database className="h-4 w-4" /> },
      { view: "imports",              label: "Importações",           desc: "Importação de dados e arquivos externos para o sistema", icon: <Upload className="h-4 w-4" /> },
    ],
  },
]

export function DashboardPage() {
  const authSession = getAuthSession()
  const [activeView, setActiveView] = useState<DashboardView>("overview")
  const firstName = authSession?.fullName?.split(" ")[0] ?? null

  function handleNavigate(view: AppView) {
    if (!canAccessView(view, authSession)) {
      setActiveView("overview")
      return
    }
    void preloadAppView(view)
    setActiveView(view)
  }

  return (
    <AppShell activeView={activeView} onNavigate={handleNavigate}>
      {activeView === "overview" ? (
        <div className="space-y-8">

          {/* ── Hero ─────────────────────────────────────────────────────────── */}
          <div className="relative overflow-hidden rounded-[2rem]" style={{ background: "#020617" }}>
            {/* Ambient orbs */}
            <div className="pointer-events-none absolute inset-0" aria-hidden="true">
              <div
                className="absolute -bottom-32 -left-32 h-80 w-80 rounded-full"
                style={{ background: "radial-gradient(circle, rgba(16,185,129,0.28) 0%, transparent 70%)", filter: "blur(55px)" }}
              />
              <div
                className="absolute -top-32 right-0 h-72 w-72 rounded-full"
                style={{ background: "radial-gradient(circle, rgba(56,189,248,0.2) 0%, transparent 70%)", filter: "blur(55px)" }}
              />
              <div
                className="absolute bottom-0 right-1/3 h-60 w-60 rounded-full"
                style={{ background: "radial-gradient(circle, rgba(99,88,215,0.2) 0%, transparent 70%)", filter: "blur(50px)" }}
              />
              {/* Dot grid */}
              <div
                className="absolute inset-0 opacity-[0.055]"
                style={{ backgroundImage: "radial-gradient(circle, #10b981 1px, transparent 1px)", backgroundSize: "28px 28px" }}
              />
            </div>

            {/* Hero content */}
            <div className="relative flex flex-wrap items-center justify-between gap-5 p-7 sm:p-10">
              <div className="flex items-center gap-5">
                <img
                  src="/kovir-logo.png"
                  alt="Kovir"
                  className="h-16 w-16 shrink-0 object-contain"
                  style={{ filter: "drop-shadow(0 0 18px rgba(16,185,129,0.55))" }}
                />
                <div>
                  {firstName ? (
                    <p className="text-sm font-semibold" style={{ color: "rgba(248,250,252,0.55)" }}>
                      Olá, {firstName}!
                    </p>
                  ) : (
                    <p className="text-sm font-semibold" style={{ color: "rgba(248,250,252,0.55)" }}>
                      Bem-vindo ao Kovir
                    </p>
                  )}
                  <h1 className="mt-0.5 text-3xl font-black sm:text-4xl" style={{ color: "#f8fafc", textShadow: "0 0 40px rgba(16,185,129,0.3)" }}>
                    O que você quer fazer
                  </h1>
                  <p className="mt-1 text-sm" style={{ color: "rgba(248,250,252,0.38)" }}>
                    Escolha um módulo abaixo para ir direto para a tela de trabalho
                  </p>
                </div>
              </div>

              {/* Color accent pills */}
              <div className="flex items-center gap-2">
                {(["#10b981", "#38bdf8", "#6358d7", "#f59e0b"] as const).map((color, i) => (
                  <div key={i} className="h-2 rounded-full" style={{ width: i === 0 ? 32 : i === 1 ? 24 : i === 2 ? 20 : 16, background: color, opacity: 0.65 }} />
                ))}
              </div>
            </div>
          </div>

          {/* ── Module groups ─────────────────────────────────────────────────── */}
          {MODULE_GROUPS.map((grp) => {
            const visible = grp.items.filter((m) => canAccessView(m.view, authSession))
            if (visible.length === 0) return null
            return (
              <section key={grp.group} className="space-y-3">
                {/* Group label */}
                <div className="flex items-center gap-3">
                  <div className="h-px flex-1" style={{ background: `linear-gradient(90deg, ${grp.accent}40, transparent)` }} />
                  <span className="text-[10px] font-black tracking-[0.32em] uppercase" style={{ color: grp.accent }}>
                    {grp.group}
                  </span>
                  <div className="h-px w-6 opacity-0" />
                </div>

                {/* Module cards */}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {visible.map((item) => (
                    <ModuleCard
                      key={item.view}
                      label={item.label}
                      desc={item.desc}
                      icon={item.icon}
                      accent={grp.accent}
                      onClick={() => handleNavigate(item.view)}
                    />
                  ))}
                </div>
              </section>
            )
          })}

        </div>
      ) : (
        <LazyViewRenderer view={activeView} />
      )}
    </AppShell>
  )
}

// ─── Lazy view renderer ────────────────────────────────────────────────────────

function LazyViewRenderer({ view }: { view: AppView }) {
  if (!isLazyAppView(view)) return null
  if (!isAppViewEnabled(view)) {
    return <UnavailableModuleNotice />
  }

  const View = getLazyView(view)
  return (
    <Suspense fallback={<ViewLoadingFallback label={getViewLoadingLabel(view)} />}>
      <View />
    </Suspense>
  )
}

function UnavailableModuleNotice() {
  return (
    <div className="rounded-[2rem] border border-amber-300/50 bg-amber-50 p-6 text-amber-950 shadow-xl shadow-[var(--color-card-shadow)]">
      <p className="text-xs font-black uppercase tracking-[0.2em]">Fora do escopo v1.0</p>
      <h2 className="mt-2 text-xl font-black">Modulo interno ou ainda nao homologado</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6">
        Esta area nao esta liberada para clientes comuns nesta versao. O acesso so deve ser habilitado por flag
        interna em ambiente controlado.
      </p>
    </div>
  )
}

function ViewLoadingFallback({ label }: { label: string }) {
  return (
    <div className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)]">
      <div className="flex items-center gap-3">
        <span className="h-3 w-3 animate-pulse rounded-full bg-[var(--color-primary)]" />
        <div>
          <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Carregando módulo</p>
          <p className="mt-1 text-sm font-semibold text-[var(--color-text-muted)]">{label}</p>
        </div>
      </div>
    </div>
  )
}

// ─── Module card ───────────────────────────────────────────────────────────────

function ModuleCard({
  label,
  desc,
  icon,
  accent,
  onClick,
}: {
  label: string
  desc: string
  icon: ReactNode
  accent: string
  onClick: () => void
}) {
  const iconBg     = `${accent}18`
  const iconBorder = `${accent}44`
  const cardBorder = `${accent}44`

  return (
    <button
      type="button"
      onClick={onClick}
      className="group relative flex flex-col overflow-hidden rounded-2xl p-4 text-left transition-all duration-200 hover:-translate-y-0.5 bg-[var(--color-surface)] shadow-sm"
      style={{ border: `1px solid ${cardBorder}` }}
    >
      {/* Hover fill overlay */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{ background: `${accent}12` }}
      />

      {/* Icon + arrow */}
      <div className="relative flex items-start justify-between gap-2">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
          style={{ background: iconBg, border: `1px solid ${iconBorder}`, color: accent, boxShadow: `0 0 12px ${accent}22` }}
        >
          {icon}
        </div>
        <ArrowRight
          className="mt-0.5 h-4 w-4 shrink-0 opacity-0 transition-all duration-200 group-hover:translate-x-0.5 group-hover:opacity-90"
          style={{ color: accent }}
        />
      </div>

      {/* Text */}
      <h3 className="relative mt-3 text-sm font-black text-[var(--color-text)]">
        {label}
      </h3>
      <p className="relative mt-1 text-xs leading-5 text-[var(--color-text-muted)]">
        {desc}
      </p>

      {/* Bottom accent line (aparece no hover) */}
      <div
        className="absolute bottom-0 left-4 right-4 h-[2px] rounded-full opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{ background: `linear-gradient(90deg, transparent, ${accent}88, transparent)` }}
      />
    </button>
  )
}
