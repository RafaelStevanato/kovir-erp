import { useEffect, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSpreadsheet,
  Layers3,
  Mail,
  Menu,
  PackageCheck,
  PiggyBank,
  Radar,
  ShieldCheck,
  TrendingUp,
  WalletCards,
} from "lucide-react"

const stvnLogo = "/stvn-software-logo.png"
const kovirErpLogo = "/kovir-logo.png"
const kovirTasksLogo = "/kovir-tasks-logo.png"
const kovirPulseLogo = "/kovir-pulse-logo.png"

const kovirProductPage = "https://stvnsoftware.com.br/erpkovir"
const whatsappBase = "https://wa.me/5514997656475"
const contactWhatsapp =
  "https://wa.me/5514997656475?text=Ol%C3%A1%2C%20quero%20conhecer%20as%20solu%C3%A7%C3%B5es%20da%20STVN%20Software."
const kovirWhatsapp =
  "https://wa.me/5514997656475?text=Ol%C3%A1%2C%20quero%20conhecer%20o%20Kovir%20ERP%20v1.0."
const finalWhatsapp =
  "https://wa.me/5514997656475?text=Ol%C3%A1%2C%20quero%20conversar%20com%20a%20STVN%20Software%20sobre%20solu%C3%A7%C3%B5es%20para%20minha%20empresa."
const mailtoLink =
  "mailto:stvnsoftware@outlook.com?subject=Contato%20pelo%20site%20STVN%20Software"

const navItems = [
  { label: "Empresa", href: "#empresa" },
  { label: "Kovir ERP", href: "#kovir-erp" },
  { label: "Ecossistema", href: "#ecossistema" },
  { label: "Implantação", href: "#implantacao" },
  { label: "Contato", href: "#contato" },
]

const heroCards = [
  { title: "Contas a receber", detail: "Títulos e vencimentos", accent: "text-[#38bdf8]" },
  { title: "Estoque por lote", detail: "Local, validade e rastreio", accent: "text-[#22c55e]" },
  { title: "Pedidos", detail: "Fluxo operacional", accent: "text-[#f59e0b]" },
  { title: "Conciliação", detail: "Banco x controle interno", accent: "text-[#10b981]" },
]

const valueCards = [
  {
    icon: Building2,
    title: "Operação mais clara",
    text: "Cadastros, produtos, pedidos, estoque e financeiro em fluxos mais organizados.",
  },
  {
    icon: Database,
    title: "Dados com contexto",
    text: "Relatórios e registros pensados para mostrar origem, pendências e movimentações.",
  },
  {
    icon: ClipboardCheck,
    title: "Implantação assistida",
    text: "Adoção gradual, com diagnóstico, preparação de dados e acompanhamento inicial.",
  },
  {
    icon: Layers3,
    title: "Evolução contínua",
    text: "Produtos construídos com visão de ecossistema, começando pelo Kovir ERP.",
  },
]

const kovirModules = [
  {
    icon: Building2,
    title: "Cadastros e participantes",
    text: "Clientes, fornecedores, terceiros e dados essenciais da operação em uma base centralizada.",
  },
  {
    icon: PackageCheck,
    title: "Produtos e serviços",
    text: "Catálogo organizado para apoiar pedidos, estoque, compras e relatórios.",
  },
  {
    icon: Boxes,
    title: "Estoque com lote e validade",
    text: "Controle de locais, entradas, lotes, validade e movimentações operacionais.",
  },
  {
    icon: FileSpreadsheet,
    title: "Pedidos e vendas",
    text: "Fluxo para registrar pedidos, acompanhar status e gerar rastreabilidade.",
  },
  {
    icon: WalletCards,
    title: "Contas a receber",
    text: "Visão de títulos, vencimentos, origem da venda e valores em aberto.",
  },
  {
    icon: ClipboardCheck,
    title: "Contas a pagar",
    text: "Controle de obrigações, fornecedores, despesas e pagamentos planejados.",
  },
  {
    icon: PiggyBank,
    title: "Caixa e baixas",
    text: "Registro de recebimentos, pagamentos e movimentações internas sem misturar conceitos.",
  },
  {
    icon: TrendingUp,
    title: "Fluxo de caixa",
    text: "Acompanhamento de previsto, realizado, pendências e visão financeira operacional.",
  },
  {
    icon: ShieldCheck,
    title: "Conciliação bancária",
    text: "Comparação entre extrato e controle interno para identificar divergências.",
  },
  {
    icon: BarChart3,
    title: "Relatórios e importações",
    text: "Relatórios operacionais e apoio à migração inicial por planilhas-base.",
  },
]

const differentiators = [
  {
    title: "Venda não é recebimento",
    text: "Pedido fechado não significa dinheiro no caixa.",
  },
  {
    title: "Compra não é pagamento",
    text: "Obrigação registrada não é saída financeira realizada.",
  },
  {
    title: "Título não é dinheiro",
    text: "Contas a receber mostra direito de receber, não saldo disponível.",
  },
  {
    title: "Baixa não é conciliação",
    text: "Baixar um título e comparar com o banco são processos diferentes.",
  },
  {
    title: "Saldo bancário não é gestão financeira completa",
    text: "O banco mostra movimentação. O ERP precisa mostrar contexto, origem e pendências.",
  },
]

const ecosystemProducts = [
  {
    badge: "v1.0",
    title: "Kovir ERP",
    logoSrc: kovirErpLogo,
    logoAlt: "Kovir ERP",
    phrase: "A base operacional da empresa.",
    description:
      "Centraliza cadastros, produtos, estoque, pedidos, financeiro, caixa, conciliação, relatórios e importações em uma rotina mais clara para pequenas e médias empresas.",
    status: "Produto principal",
    cta: "Visitar página do Kovir",
    href: kovirProductPage,
    icon: Layers3,
    available: true,
  },
  {
    badge: "Em desenvolvimento",
    title: "Kovir Tasks",
    logoSrc: kovirTasksLogo,
    logoAlt: "Kovir Tasks",
    phrase: "A camada de execução da rotina.",
    description:
      "Solução planejada para organizar tarefas recorrentes, checklists, responsáveis, pendências e acompanhamento da execução diária.",
    status: "Projeto em desenvolvimento",
    cta: "Em breve no ecossistema STVN",
    href: "#contato",
    icon: ClipboardCheck,
    available: false,
  },
  {
    badge: "Em desenvolvimento",
    title: "Kovir Pulse",
    logoSrc: kovirPulseLogo,
    logoAlt: "Kovir Pulse",
    phrase: "A camada de monitoramento e decisão.",
    description:
      "Solução planejada para transformar dados e sinais operacionais em indicadores, alertas e prioridades para gestores acompanharem o pulso da empresa.",
    status: "Projeto em desenvolvimento",
    cta: "Em breve no ecossistema STVN",
    href: "#contato",
    icon: Radar,
    available: false,
  },
]

const painPoints = [
  "planilhas demais",
  "estoque que não bate",
  "contas vencidas sem visibilidade",
  "pedidos sem rastreabilidade",
  "financeiro espalhado",
  "dificuldade para migrar de sistema antigo",
  "dados duplicados",
  "falta de clareza entre previsto e realizado",
  "conciliação bancária manual",
  "relatórios que não explicam a origem dos números",
]

const implementationSteps = [
  {
    title: "Diagnóstico",
    text: "Entendimento dos controles atuais, planilhas, sistemas, dores e prioridades.",
  },
  {
    title: "Preparação dos dados",
    text: "Organização de cadastros, produtos, participantes e informações iniciais.",
  },
  {
    title: "Configuração do fluxo",
    text: "Parametrização inicial para pedidos, estoque, contas e financeiro operacional.",
  },
  {
    title: "Piloto assistido",
    text: "Uso controlado com dados reais e acompanhamento próximo.",
  },
  {
    title: "Evolução",
    text: "Ajustes, melhorias e expansão conforme a necessidade real da empresa.",
  },
]

function ensureMeta(name: string, content: string, attribute: "name" | "property" = "name") {
  const selector = `meta[${attribute}="${name}"]`
  let element = document.head.querySelector<HTMLMetaElement>(selector)

  if (!element) {
    element = document.createElement("meta")
    element.setAttribute(attribute, name)
    document.head.appendChild(element)
  }

  element.content = content
}

function ensureCanonical(href: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')

  if (!element) {
    element = document.createElement("link")
    element.rel = "canonical"
    document.head.appendChild(element)
  }

  element.href = href
}

function useStvnSeo() {
  useEffect(() => {
    document.documentElement.lang = "pt-BR"
    document.title = "STVN Software | Kovir ERP e soluções para pequenas e médias empresas"
    ensureMeta(
      "description",
      "A STVN Software desenvolve soluções B2B para pequenas e médias empresas. Conheça o Kovir ERP v1.0, sistema para organizar operação, estoque, pedidos, financeiro, conciliação e relatórios.",
    )
    ensureMeta("og:title", "STVN Software | Tecnologia para operação, dados e gestão", "property")
    ensureMeta(
      "og:description",
      "Conheça a STVN Software, desenvolvedora do Kovir ERP v1.0 e do ecossistema Kovir para pequenas e médias empresas.",
      "property",
    )
    ensureMeta("og:url", "https://stvnsoftware.com.br", "property")
    ensureMeta("og:type", "website", "property")
    ensureMeta("og:image", "https://stvnsoftware.com.br/stvn-software-logo.png", "property")
    ensureCanonical("https://stvnsoftware.com.br")
  }, [])
}

function SectionShell({
  id,
  eyebrow,
  title,
  description,
  children,
}: {
  id: string
  eyebrow?: string
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-28 px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
      <div className="mx-auto max-w-7xl">
        <div className="max-w-3xl">
          {eyebrow ? (
            <p className="text-sm font-black uppercase tracking-[0.24em] text-[#10b981]">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="mt-4 text-3xl font-black leading-tight text-[#f8fafc] sm:text-4xl lg:text-5xl">
            {title}
          </h2>
          {description ? (
            <p className="mt-5 text-base leading-8 text-[#a7b8b1] sm:text-lg">{description}</p>
          ) : null}
        </div>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  )
}

function ContactButton({
  href,
  children,
  variant = "primary",
}: {
  href: string
  children: ReactNode
  variant?: "primary" | "secondary"
}) {
  const className =
    variant === "primary"
      ? "border-[#10b981] bg-[#10b981] text-[#020617] hover:border-[#047857] hover:bg-[#047857] hover:text-white"
      : "border-emerald-400/25 bg-[#0f1f1a]/88 text-[#f8fafc] hover:border-emerald-300/55 hover:bg-[#122820]"

  return (
    <a
      href={href}
      className={`inline-flex min-h-12 items-center justify-center gap-2 rounded-2xl border px-5 py-3 text-sm font-black shadow-[0_18px_38px_rgba(16,185,129,0.18)] transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] ${className}`}
    >
      {children}
    </a>
  )
}

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-emerald-400/10 bg-[#020617]/82 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8 lg:px-10">
        <a href="#topo" className="group flex items-center gap-3" aria-label="STVN Software">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-400/20 bg-[#020617] p-1 shadow-[0_0_34px_rgba(16,185,129,0.18)]">
            <img
              src={stvnLogo}
              alt=""
              className="h-full w-full object-contain"
              aria-hidden="true"
            />
          </span>
          <span className="leading-tight">
            <span className="block text-base font-black tracking-tight text-[#f8fafc]">
              STVN <span className="text-[#10b981]">Software</span>
            </span>
            <span className="hidden text-xs font-bold text-[#a7b8b1] sm:block">
              Tecnologia para operação, dados e gestão
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-6 lg:flex" aria-label="Navegação principal">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm font-bold text-[#a7b8b1] transition hover:text-[#f8fafc] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8]"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <a
            href={contactWhatsapp}
            className="hidden rounded-2xl bg-[#10b981] px-4 py-3 text-sm font-black text-[#020617] transition hover:bg-[#047857] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] sm:inline-flex"
          >
            Falar com a STVN
          </a>
          <details className="relative lg:hidden">
            <summary className="flex h-11 w-11 list-none items-center justify-center rounded-2xl border border-emerald-400/20 bg-[#0f1f1a] text-[#f8fafc] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] [&::-webkit-details-marker]:hidden">
              <Menu className="h-5 w-5" aria-hidden="true" />
              <span className="sr-only">Abrir menu</span>
            </summary>
            <div className="absolute right-0 mt-3 w-64 rounded-3xl border border-emerald-400/15 bg-[#07130f] p-3 shadow-[0_24px_70px_rgba(0,0,0,0.42)]">
              {navItems.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="block rounded-2xl px-4 py-3 text-sm font-bold text-[#f8fafc] hover:bg-emerald-400/10"
                >
                  {item.label}
                </a>
              ))}
              <a
                href={contactWhatsapp}
                className="mt-2 block rounded-2xl bg-[#10b981] px-4 py-3 text-center text-sm font-black text-[#020617]"
              >
                Falar com a STVN
              </a>
            </div>
          </details>
        </div>
      </div>
    </header>
  )
}

function HeroMockup() {
  return (
    <div className="relative mx-auto w-full max-w-xl">
      <div className="absolute -inset-8 rounded-[3rem] bg-[#10b981]/12 blur-3xl" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-[2rem] border border-emerald-300/16 bg-[#0f1f1a]/92 p-5 shadow-[0_30px_90px_rgba(0,0,0,0.45)]">
        <div className="flex items-start justify-between gap-5 border-b border-emerald-400/12 pb-5">
          <div>
            <img
              src={kovirErpLogo}
              alt="Kovir ERP"
              className="h-20 w-auto max-w-[13rem] object-contain drop-shadow-[0_0_28px_rgba(16,185,129,0.24)]"
            />
            <span className="mt-4 inline-flex rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-black text-[#10b981]">
              Kovir ERP v1.0
            </span>
            <h2 className="mt-4 text-2xl font-black text-[#f8fafc]">
              Operação, financeiro e estoque em uma base mais clara.
            </h2>
          </div>
          <div className="hidden rounded-2xl border border-sky-300/20 bg-sky-400/10 p-3 sm:block">
            <BarChart3 className="h-7 w-7 text-[#38bdf8]" aria-hidden="true" />
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {heroCards.map((card) => (
            <div
              key={card.title}
              className="rounded-2xl border border-emerald-400/12 bg-[#122820]/78 p-4"
            >
              <p className={`text-xs font-black uppercase tracking-[0.16em] ${card.accent}`}>
                {card.title}
              </p>
              <p className="mt-2 text-sm font-bold text-[#f8fafc]">{card.detail}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-emerald-400/12 bg-[#07130f] p-4">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-[#a7b8b1]">
            Fluxo conceitual
          </p>
          <div className="mt-4 grid gap-2 text-center text-xs font-black text-[#f8fafc] sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-center">
            {["Pedido", "→", "Título", "→", "Baixa", "→", "Conciliação"].map((item) => (
              <span
                key={item}
                className={
                  item === "→"
                    ? "hidden text-[#10b981] sm:inline"
                    : "rounded-xl border border-emerald-400/12 bg-[#0f1f1a] px-3 py-2"
                }
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function HeroSection() {
  return (
    <section
      id="topo"
      className="relative overflow-hidden px-5 pb-16 pt-12 sm:px-8 lg:px-10 lg:pb-24 lg:pt-20"
    >
      <div
        className="absolute inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(16,185,129,0.2),transparent_34rem),radial-gradient(circle_at_85%_20%,rgba(56,189,248,0.12),transparent_30rem),linear-gradient(135deg,#020617_0%,#07130f_46%,#020617_100%)]"
        aria-hidden="true"
      />
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-emerald-400/30 to-transparent" />

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <img
            src={stvnLogo}
            alt="STVN Software"
            className="mb-7 h-24 w-auto max-w-[16rem] object-contain drop-shadow-[0_0_34px_rgba(16,185,129,0.22)] sm:h-28"
          />
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-black text-[#10b981]">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Software B2B para PMEs brasileiras
          </div>
          <h1 className="max-w-5xl text-4xl font-black leading-[1.02] tracking-tight text-[#f8fafc] sm:text-5xl lg:text-7xl">
            Software para pequenas e médias empresas que precisam transformar operação em controle.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-[#a7b8b1] sm:text-lg">
            A STVN Software desenvolve soluções B2B para organizar cadastros, estoque, pedidos,
            financeiro, rotinas e dados gerenciais. O primeiro produto do ecossistema é o Kovir ERP
            v1.0, criado para dar mais clareza à operação de PMEs brasileiras.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <ContactButton href={contactWhatsapp}>
              Falar com a STVN
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </ContactButton>
            <ContactButton href={kovirProductPage} variant="secondary">
              Ver página do Kovir ERP
            </ContactButton>
          </div>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-[#a7b8b1]">
            Diagnóstico, demonstração e implantação assistida para empresas que querem sair da
            bagunça de planilhas e sistemas soltos.
          </p>
        </div>

        <HeroMockup />
      </div>
    </section>
  )
}

function CompanySection() {
  return (
    <SectionShell
      id="empresa"
      eyebrow="Sobre a STVN Software"
      title="Tecnologia feita para organizar a operação antes de escalar."
      description="A STVN Software é uma empresa de software B2B focada em soluções práticas para pequenas e médias empresas brasileiras. Nosso trabalho é transformar processos espalhados, planilhas manuais e controles soltos em sistemas mais claros, rastreáveis e seguros."
    >
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {valueCards.map((card) => {
          const Icon = card.icon
          return (
            <article
              key={card.title}
              className="rounded-[1.7rem] border border-emerald-400/12 bg-[#0f1f1a] p-5 shadow-[0_18px_48px_rgba(0,0,0,0.2)] transition hover:-translate-y-1 hover:border-emerald-300/30 hover:bg-[#122820]"
            >
              <Icon className="h-6 w-6 text-[#10b981]" aria-hidden="true" />
              <h3 className="mt-5 text-lg font-black text-[#f8fafc]">{card.title}</h3>
              <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{card.text}</p>
            </article>
          )
        })}
      </div>
    </SectionShell>
  )
}

function KovirProductSection() {
  return (
    <SectionShell
      id="kovir-erp"
      eyebrow="Produto principal"
      title="Kovir ERP v1.0: a base operacional da empresa."
      description="O Kovir ERP é o produto principal da STVN Software. Ele foi criado para pequenas e médias empresas que precisam organizar a rotina operacional e financeira sem confundir venda com recebimento, compra com pagamento ou saldo bancário com controle financeiro completo."
    >
      <div className="rounded-[2rem] border border-emerald-400/14 bg-[#07130f] p-5 sm:p-7">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex w-fit items-center justify-center rounded-[1.5rem] border border-emerald-400/14 bg-[#020617] p-4">
              <img
                src={kovirErpLogo}
                alt="Kovir ERP"
                className="h-24 w-auto max-w-[14rem] object-contain"
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-black text-[#10b981]">
                Kovir ERP v1.0
              </span>
              <span className="rounded-full border border-sky-400/20 bg-sky-400/10 px-4 py-2 text-sm font-black text-[#38bdf8]">
                Produto principal
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ContactButton href={kovirProductPage}>Visitar página do Kovir</ContactButton>
            <ContactButton href={kovirWhatsapp} variant="secondary">
              Quero falar sobre o Kovir
            </ContactButton>
          </div>
        </div>

        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {kovirModules.map((module) => {
            const Icon = module.icon
            return (
              <article
                key={module.title}
                className="rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-4 transition hover:-translate-y-1 hover:border-emerald-300/30 hover:bg-[#122820]"
              >
                <Icon className="h-5 w-5 text-[#10b981]" aria-hidden="true" />
                <h3 className="mt-4 text-base font-black text-[#f8fafc]">{module.title}</h3>
                <p className="mt-3 text-sm leading-6 text-[#a7b8b1]">{module.text}</p>
              </article>
            )
          })}
        </div>
      </div>
    </SectionShell>
  )
}

function DifferentiatorsSection() {
  return (
    <SectionShell
      id="controle-real"
      eyebrow="Controle real"
      title="O Kovir não mistura conceitos que deveriam estar separados."
      description="Na gestão de uma empresa, confundir etapas diferentes gera decisões ruins. O Kovir ERP foi pensado para separar o que é operação, o que é financeiro e o que é conciliação."
    >
      <div className="grid gap-4 lg:grid-cols-5">
        {differentiators.map((item) => (
          <article
            key={item.title}
            className="rounded-[1.5rem] border border-emerald-400/14 bg-[#0f1f1a] p-5"
          >
            <CheckCircle2 className="h-5 w-5 text-[#10b981]" aria-hidden="true" />
            <h3 className="mt-4 text-lg font-black leading-7 text-[#10b981]">{item.title}</h3>
            <p className="mt-3 text-sm leading-6 text-[#a7b8b1]">{item.text}</p>
          </article>
        ))}
      </div>
    </SectionShell>
  )
}

function EcosystemSection() {
  return (
    <SectionShell
      id="ecossistema"
      eyebrow="Ecossistema Kovir"
      title="Um ecossistema em construção para operação, rotina e gestão."
      description="A STVN está construindo o ecossistema Kovir para apoiar diferentes camadas da gestão empresarial: registro operacional, execução da rotina e leitura gerencial."
    >
      <div className="grid gap-5 lg:grid-cols-3">
        {ecosystemProducts.map((product) => {
          return (
            <article
              key={product.title}
              className={`rounded-[2rem] border p-6 shadow-[0_24px_70px_rgba(0,0,0,0.22)] ${
                product.available
                  ? "border-emerald-300/24 bg-[#122820]"
                  : "border-amber-300/18 bg-[#0f1f1a]"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex h-24 w-32 items-center justify-center rounded-2xl border border-emerald-400/12 bg-[#020617] p-3">
                  <img
                    src={product.logoSrc}
                    alt={product.logoAlt}
                    className="max-h-full max-w-full object-contain drop-shadow-[0_0_22px_rgba(16,185,129,0.16)]"
                  />
                </div>
                <span
                  className={`rounded-full border px-3 py-1 text-xs font-black ${
                    product.available
                      ? "border-emerald-400/25 bg-emerald-400/10 text-[#10b981]"
                      : "border-amber-400/25 bg-amber-400/10 text-[#f59e0b]"
                  }`}
                >
                  {product.badge}
                </span>
              </div>
              <h3 className="mt-7 text-2xl font-black text-[#f8fafc]">{product.title}</h3>
              <p className="mt-2 text-base font-black text-[#10b981]">{product.phrase}</p>
              <p className="mt-4 text-sm leading-7 text-[#a7b8b1]">{product.description}</p>
              <p className="mt-5 text-sm font-black text-[#f8fafc]">{product.status}</p>
              <a
                href={product.href}
                className={`mt-6 inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-black transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] ${
                  product.available
                    ? "border-emerald-400/25 bg-[#10b981] text-[#020617] hover:bg-[#047857] hover:text-white"
                    : "border-amber-400/20 bg-amber-400/10 text-[#f8fafc] hover:border-amber-300/40"
                }`}
              >
                {product.cta}
                {product.available ? <ArrowRight className="h-4 w-4" aria-hidden="true" /> : null}
              </a>
            </article>
          )
        })}
      </div>
    </SectionShell>
  )
}

function AudienceSection() {
  return (
    <SectionShell
      id="publico"
      eyebrow="Para quem desenvolvemos"
      title="Para pequenas e médias empresas que cresceram além da planilha."
      description="A STVN atende negócios que precisam de mais organização, mas não querem uma implantação confusa, cara e distante da realidade operacional."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {painPoints.map((pain) => (
          <div
            key={pain}
            className="rounded-2xl border border-emerald-400/12 bg-[#0f1f1a] p-4 text-sm font-bold leading-6 text-[#f8fafc]"
          >
            <span className="mb-3 flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-400/10 text-[#10b981]">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            </span>
            {pain}
          </div>
        ))}
      </div>
      <p className="mt-8 rounded-[1.5rem] border border-emerald-400/18 bg-[#122820] p-6 text-2xl font-black leading-tight text-[#f8fafc]">
        Antes de automatizar, organize. Antes de escalar, enxergue.
      </p>
    </SectionShell>
  )
}

function ImplementationSection() {
  return (
    <SectionShell
      id="implantacao"
      eyebrow="Implantação assistida"
      title="Implantação assistida, com escopo claro."
      description="O Kovir ERP v1.0 pode ser apresentado em diagnóstico, demonstração e piloto acompanhado, com foco em validar aderência antes de ampliar o uso."
    >
      <ol className="grid gap-4 lg:grid-cols-5">
        {implementationSteps.map((step, index) => (
          <li
            key={step.title}
            className="relative rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-5"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-400/10 text-sm font-black text-[#10b981]">
              {index + 1}
            </span>
            <h3 className="mt-5 text-lg font-black text-[#f8fafc]">{step.title}</h3>
            <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{step.text}</p>
          </li>
        ))}
      </ol>
    </SectionShell>
  )
}

function FinalCTA() {
  return (
    <section id="contato" className="px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-[2.5rem] border border-emerald-300/20 bg-[radial-gradient(circle_at_10%_10%,rgba(16,185,129,0.18),transparent_30rem),linear-gradient(135deg,#122820,#07130f)] p-7 shadow-[0_28px_90px_rgba(0,0,0,0.34)] sm:p-10 lg:p-14">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-black leading-tight text-[#f8fafc] sm:text-5xl">
            Quer entender se a STVN pode ajudar sua empresa?
          </h2>
          <p className="mt-5 text-base leading-8 text-[#a7b8b1] sm:text-lg">
            Converse com a STVN Software e veja como organizar operação, dados e processos com uma
            solução pensada para pequenas e médias empresas brasileiras.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <ContactButton href={finalWhatsapp}>
              Chamar no WhatsApp
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </ContactButton>
            <ContactButton href={mailtoLink} variant="secondary">
              <Mail className="h-4 w-4" aria-hidden="true" />
              Enviar e-mail
            </ContactButton>
          </div>
        </div>
        <dl className="mt-10 grid gap-4 text-sm sm:grid-cols-3">
          <div className="rounded-2xl border border-emerald-400/12 bg-[#020617]/34 p-4">
            <dt className="font-black text-[#10b981]">WhatsApp</dt>
            <dd className="mt-2 text-[#f8fafc]">(14) 99765-6475</dd>
          </div>
          <div className="rounded-2xl border border-emerald-400/12 bg-[#020617]/34 p-4">
            <dt className="font-black text-[#10b981]">E-mail</dt>
            <dd className="mt-2 break-words text-[#f8fafc]">stvnsoftware@outlook.com</dd>
          </div>
          <div className="rounded-2xl border border-emerald-400/12 bg-[#020617]/34 p-4">
            <dt className="font-black text-[#10b981]">Site</dt>
            <dd className="mt-2 text-[#f8fafc]">stvnsoftware.com.br</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-emerald-400/10 bg-[#020617] px-5 py-10 sm:px-8 lg:px-10">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.3fr_0.7fr_0.7fr_0.8fr]">
        <div>
          <img src={stvnLogo} alt="STVN Software" className="h-24 w-auto object-contain" />
          <p className="mt-3 max-w-sm text-sm leading-7 text-[#a7b8b1]">
            Tecnologia para operação, dados e gestão.
          </p>
          <p className="mt-5 text-sm text-[#a7b8b1]">Kovir ERP é um produto da STVN Software.</p>
        </div>
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.16em] text-[#10b981]">Links</h2>
          <ul className="mt-4 space-y-3 text-sm text-[#a7b8b1]">
            {navItems.map((item) => (
              <li key={item.href}>
                <a href={item.href} className="hover:text-[#f8fafc]">
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.16em] text-[#10b981]">
            Produtos
          </h2>
          <ul className="mt-4 space-y-3 text-sm text-[#a7b8b1]">
            <li>Kovir ERP v1.0</li>
            <li>Kovir Tasks — em desenvolvimento</li>
            <li>Kovir Pulse — em desenvolvimento</li>
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.16em] text-[#10b981]">
            Contato
          </h2>
          <ul className="mt-4 space-y-3 text-sm text-[#a7b8b1]">
            <li>
              <a href={mailtoLink} className="break-words hover:text-[#f8fafc]">
                stvnsoftware@outlook.com
              </a>
            </li>
            <li>
              <a href={whatsappBase} className="hover:text-[#f8fafc]">
                (14) 99765-6475
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-10 max-w-7xl border-t border-emerald-400/10 pt-6 text-sm text-[#a7b8b1]">
        © 2026 STVN Software. Todos os direitos reservados.
      </div>
    </footer>
  )
}

export function StvnSoftwarePage() {
  useStvnSeo()

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#020617] text-[#f8fafc] antialiased">
      <Header />
      <HeroSection />
      <CompanySection />
      <KovirProductSection />
      <DifferentiatorsSection />
      <EcosystemSection />
      <AudienceSection />
      <ImplementationSection />
      <FinalCTA />
      <Footer />
    </main>
  )
}
