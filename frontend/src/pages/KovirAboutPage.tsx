import { useEffect, type ReactNode } from "react"
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Banknote,
  BarChart3,
  Boxes,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSpreadsheet,
  HelpCircle,
  Landmark,
  Layers3,
  LockKeyhole,
  Mail,
  Menu,
  PackageCheck,
  ReceiptText,
  ShieldCheck,
  ShoppingCart,
  TrendingUp,
  WalletCards,
} from "lucide-react"

const kovirLogo = "/kovir-logo.png"
const whatsappCta =
  "https://wa.me/5514997656475?text=Ol%C3%A1%2C%20quero%20conhecer%20o%20Kovir%20ERP%20e%20entender%20se%20ele%20faz%20sentido%20para%20minha%20empresa."
const mailtoLink = "mailto:stvnsoftware@outlook.com?subject=Contato%20sobre%20o%20Kovir%20ERP"
const appUrl = "/"

const navItems = [
  { label: "O que é", href: "#o-que-e" },
  { label: "Módulos", href: "#modulos" },
  { label: "Diferenciais", href: "#diferenciais" },
  { label: "Implantação", href: "#implantacao" },
  { label: "FAQ", href: "#faq" },
  { label: "Contato", href: "#contato" },
]

const painPoints = [
  "Planilhas demais para controlar a rotina.",
  "Estoque que não bate.",
  "Falta de rastreabilidade por lote, validade ou local.",
  "Pedidos fechados sem clareza de recebimento.",
  "Contas a receber vencidas sem acompanhamento.",
  "Contas a pagar espalhadas.",
  "Caixa sem separação entre previsto e realizado.",
  "Saldo bancário confundido com controle financeiro.",
  "Dificuldade para fazer conciliação bancária.",
  "Relatórios que não explicam a origem dos números.",
  "Medo de migrar dados de sistema antigo.",
  "Dados duplicados entre setores.",
]

const modules = [
  ["Empresa e multiempresa", "Organização dos dados da empresa e estrutura para operação por contexto, reduzindo risco de mistura de informações.", Building2],
  ["Participantes", "Cadastro de clientes, fornecedores, terceiros e demais envolvidos na operação.", Layers3],
  ["Produtos e serviços", "Catálogo organizado para apoiar pedidos, estoque, compras e relatórios.", PackageCheck],
  ["Classificação fiscal básica", "Organização de dados fiscais básicos, como NCM e informações relacionadas, sem prometer emissão fiscal completa.", ReceiptText],
  ["Estoque", "Controle de locais, entradas, lotes, validade, produtos sem vencimento e movimentações.", Boxes],
  ["Pedidos e vendas", "Fluxo para registrar pedidos, acompanhar status e manter rastreabilidade da venda.", ShoppingCart],
  ["Contas a receber", "Controle de títulos, vencimentos, origem da venda, valores em aberto, baixados e vencidos.", WalletCards],
  ["Compras e contas a pagar", "Controle de obrigações, fornecedores, despesas e pagamentos planejados ou realizados.", ClipboardCheck],
  ["Financeiro base", "Plano de contas, categorias, centros de custo, contas financeiras e condições de pagamento.", FileSpreadsheet],
  ["Caixa e baixas", "Registro de recebimentos, pagamentos e movimentações internas sem confundir baixa com conciliação.", Banknote],
  ["Fluxo de caixa", "Visões de previsto, realizado, pendências, divergências e acompanhamento financeiro operacional.", TrendingUp],
  ["Conciliação bancária", "Comparação entre extrato bancário e controle interno para identificar divergências.", Landmark],
  ["Relatórios operacionais e financeiros", "Relatórios para acompanhar pendências, títulos, ciclo financeiro, fechamento e dados operacionais.", BarChart3],
  ["Importações", "Importação inicial por planilhas-base para apoiar migração de participantes, produtos e classificações.", FileSpreadsheet],
  ["Segurança e alçadas", "Permissões, usuários, auditoria e controle de ações críticas para mais rastreabilidade.", LockKeyhole],
] as const

const differentials = [
  ["Venda não é recebimento", "Pedido fechado não significa dinheiro no caixa. A venda organiza a operação; o financeiro acompanha o recebimento."],
  ["Compra não é pagamento", "Uma obrigação registrada não significa que o dinheiro já saiu. O Kovir separa compromisso de pagamento realizado."],
  ["Título não é dinheiro", "Contas a receber mostra direito de receber. Caixa mostra movimentação realizada."],
  ["Baixa não é conciliação", "Baixar um título e comparar com o extrato bancário são etapas diferentes."],
  ["Extrato não é controle completo", "O banco mostra movimentações. O ERP mostra origem, contexto, pendências e divergências."],
  ["Relatório precisa explicar origem", "Número sem contexto não ajuda a decidir. O Kovir prioriza rastreabilidade."],
] as const

const flowSteps = [
  ["Pedido", "A venda é registrada como operação."],
  ["Título", "O valor a receber é identificado com origem e vencimento."],
  ["Baixa", "O recebimento é registrado quando o valor é realizado."],
  ["Caixa", "O movimento financeiro interno é acompanhado."],
  ["Conciliação", "O controle interno é comparado com o banco."],
  ["Relatório", "A gestão acompanha pendências, divergências e histórico."],
] as const

const stockFeatures = [
  ["Local de estoque", "Organize onde os produtos estão armazenados."],
  ["Lote", "Acompanhe origem e movimentação por lote."],
  ["Validade", "Controle produtos com vencimento e reduza perda operacional."],
  ["Produto sem vencimento", "Trate produtos sem validade de forma explícita."],
  ["Consumo por pedido", "Relacione movimentações de estoque com a operação comercial."],
] as const

const financeFeatures = [
  ["Contas a receber", "Quem deve, quanto deve, quando vence e de onde veio."],
  ["Contas a pagar", "Obrigações, fornecedores, vencimentos e pagamentos."],
  ["Caixa e baixas", "Registro do que foi efetivamente realizado."],
  ["Fluxo de caixa", "Visão de previsto, realizado, aberto, vencido e pendente."],
  ["Conciliação bancária", "Comparação entre extrato e controle interno."],
] as const

const migrationFeatures = [
  ["Participantes", "Clientes, fornecedores e terceiros."],
  ["Produtos e serviços", "Catálogo operacional inicial."],
  ["Classificações básicas", "Dados de apoio para organização cadastral."],
  ["Prévia e validação", "Conferência antes da confirmação definitiva."],
] as const

const securityFeatures = [
  ["Usuários e permissões", "Nem toda pessoa deve acessar ou alterar tudo."],
  ["Ações críticas", "Operações sensíveis podem exigir alçadas e controle."],
  ["Auditoria", "Histórico e rastreabilidade ajudam a entender o que aconteceu."],
  ["Separação por empresa", "Cada empresa opera no seu próprio contexto."],
] as const

const implementationSteps = [
  ["Diagnóstico", "Entendimento dos controles atuais, planilhas, sistemas, dores e prioridades."],
  ["Mapeamento do escopo", "Definição dos módulos e fluxos que farão parte do piloto ou implantação inicial."],
  ["Preparação dos dados", "Organização de participantes, produtos, classificações e informações financeiras básicas."],
  ["Parametrização inicial", "Configuração de cadastros, contas, condições de pagamento, estoque e fluxos principais."],
  ["Piloto acompanhado", "Uso controlado com dados reais, acompanhamento próximo e ajustes."],
  ["Evolução", "Expansão conforme aderência, maturidade operacional e necessidade da empresa."],
] as const

const transparencyItems = [
  "Não é vendido como ERP fiscal completo.",
  "Não promete emissão fiscal homologada sem confirmação.",
  "Não promete IA pronta para gerir a empresa.",
  "Não promete BI avançado completo.",
  "Não promete integrações externas não homologadas.",
  "Não promete disponibilidade 24h garantida sem infraestrutura contratada para isso.",
]

const faqItems = [
  ["O Kovir ERP é para qual tipo de empresa?", "Para pequenas e médias empresas brasileiras que precisam organizar cadastros, estoque, pedidos, financeiro, caixa, conciliação e relatórios em uma rotina mais clara."],
  ["O Kovir substitui planilhas?", "O Kovir reduz a dependência de planilhas para os fluxos operacionais principais. A implantação pode começar justamente pela organização dos dados que hoje estão em planilhas ou sistemas antigos."],
  ["O Kovir ERP emite nota fiscal?", "O Kovir pode apoiar a organização de dados fiscais básicos, mas esta página não promete emissão fiscal completa homologada sem confirmação técnica e comercial específica."],
  ["O Kovir tem implantação?", "Sim. A proposta recomendada é implantação assistida, com diagnóstico, preparação de dados, parametrização, piloto acompanhado e evolução por escopo."],
  ["O Kovir é um sistema 100% self-service?", "O foco inicial é implantação assistida. Isso ajuda a evitar abandono, dados bagunçados e uso incorreto dos fluxos."],
  ["O Kovir integra com bancos automaticamente?", "A conciliação bancária compara extrato e controle interno. Não há promessa de integração bancária automática completa sem confirmação de homologação."],
  ["O Kovir é indicado para empresas maiores ou operações muito complexas?", "O foco inicial é pequenas e médias empresas com necessidade de organizar backoffice operacional e financeiro. Operações muito complexas devem passar por diagnóstico antes."],
  ["Como começo?", "O primeiro passo é conversar com a STVN Software para entender a operação atual, as dores e o escopo ideal de demonstração ou piloto."],
] as const

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

function useKovirAboutSeo() {
  useEffect(() => {
    document.documentElement.lang = "pt-BR"
    document.title = "Kovir ERP | ERP operacional para pequenas e médias empresas"
    ensureMeta(
      "description",
      "Conheça o Kovir ERP, sistema de gestão operacional da STVN Software para pequenas e médias empresas organizarem cadastros, estoque, pedidos, financeiro, caixa, conciliação e relatórios.",
    )
    ensureCanonical("https://stvnsoftware.com.br/erpkovir")
    ensureMeta("og:title", "Kovir ERP | Organize operação, estoque e financeiro", "property")
    ensureMeta(
      "og:description",
      "O Kovir ERP ajuda pequenas e médias empresas a sair da bagunça de planilhas e controlar cadastros, pedidos, estoque, financeiro, caixa, conciliação e relatórios.",
      "property",
    )
    ensureMeta("og:url", "https://stvnsoftware.com.br/erpkovir", "property")
    ensureMeta("og:type", "website", "property")
    ensureMeta("og:site_name", "Kovir ERP", "property")
    ensureMeta("og:image", "https://stvnsoftware.com.br/kovir-logo.png", "property")

    const scriptId = "kovir-about-jsonld"
    document.getElementById(scriptId)?.remove()
    const script = document.createElement("script")
    script.id = scriptId
    script.type = "application/ld+json"
    script.text = JSON.stringify({
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      name: "Kovir ERP",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      creator: { "@type": "Organization", name: "STVN Software" },
      url: "https://stvnsoftware.com.br/erpkovir",
      description: "ERP operacional para pequenas e médias empresas brasileiras.",
    })
    document.head.appendChild(script)
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
        <div className="max-w-4xl">
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
    <header className="sticky top-0 z-40 border-b border-emerald-400/10 bg-[#020617]/84 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8 lg:px-10">
        <a href="#topo" className="group flex items-center gap-3" aria-label="Kovir ERP">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-400/20 bg-[#020617] p-1.5 shadow-[0_0_34px_rgba(16,185,129,0.18)]">
            <img src={kovirLogo} alt="" className="h-full w-full object-contain" aria-hidden="true" />
          </span>
          <span className="leading-tight">
            <span className="block text-base font-black tracking-tight text-[#f8fafc]">
              Kovir <span className="text-[#10b981]">ERP</span>
            </span>
            <span className="hidden text-xs font-bold text-[#a7b8b1] sm:block">
              Produto da STVN Software
            </span>
          </span>
        </a>

        <nav className="hidden items-center gap-6 xl:flex" aria-label="Navegação principal">
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
            href={appUrl}
            className="hidden rounded-2xl border border-emerald-400/25 bg-[#0f1f1a] px-4 py-3 text-sm font-black text-[#f8fafc] transition hover:bg-[#122820] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] lg:inline-flex"
          >
            Entrar no sistema
          </a>
          <a
            href={whatsappCta}
            className="hidden rounded-2xl bg-[#10b981] px-4 py-3 text-sm font-black text-[#020617] transition hover:bg-[#047857] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] sm:inline-flex"
          >
            Agendar diagnóstico
          </a>
          <details className="relative xl:hidden">
            <summary className="flex h-11 w-11 list-none items-center justify-center rounded-2xl border border-emerald-400/20 bg-[#0f1f1a] text-[#f8fafc] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#38bdf8] [&::-webkit-details-marker]:hidden">
              <Menu className="h-5 w-5" aria-hidden="true" />
              <span className="sr-only">Abrir menu</span>
            </summary>
            <div className="absolute right-0 mt-3 w-72 rounded-3xl border border-emerald-400/15 bg-[#07130f] p-3 shadow-[0_24px_70px_rgba(0,0,0,0.42)]">
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
                href={appUrl}
                className="mt-2 block rounded-2xl border border-emerald-400/20 px-4 py-3 text-center text-sm font-black text-[#f8fafc]"
              >
                Entrar no sistema
              </a>
              <a
                href={whatsappCta}
                className="mt-2 block rounded-2xl bg-[#10b981] px-4 py-3 text-center text-sm font-black text-[#020617]"
              >
                Agendar diagnóstico
              </a>
            </div>
          </details>
        </div>
      </div>
    </header>
  )
}

function DashboardMockup() {
  return (
    <div className="relative mx-auto w-full max-w-xl">
      <div className="absolute -inset-8 rounded-[3rem] bg-[#10b981]/12 blur-3xl" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-[2rem] border border-emerald-300/16 bg-[#0f1f1a]/94 p-5 shadow-[0_30px_90px_rgba(0,0,0,0.45)]">
        <div className="flex items-start justify-between gap-5 border-b border-emerald-400/12 pb-5">
          <div>
            <span className="inline-flex rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-black text-[#10b981]">
              Demonstração visual
            </span>
            <h2 className="mt-4 text-2xl font-black text-[#f8fafc]">Kovir ERP v1.0</h2>
            <p className="mt-2 text-sm leading-6 text-[#a7b8b1]">
              Operação, estoque e financeiro com origem rastreável.
            </p>
          </div>
          <img src={kovirLogo} alt="Kovir ERP" className="h-20 w-20 object-contain" />
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {[
            ["Pedidos", "Pedido fechado não é dinheiro recebido", ShoppingCart],
            ["Contas a receber", "Títulos, vencimentos e baixas", WalletCards],
            ["Estoque", "Local, lote e validade", Boxes],
            ["Conciliação", "Banco x controle interno", Landmark],
          ].map(([title, detail, Icon]) => (
            <article key={title as string} className="rounded-2xl border border-emerald-400/12 bg-[#122820]/78 p-4">
              <Icon className="h-5 w-5 text-[#10b981]" aria-hidden="true" />
              <h3 className="mt-3 text-base font-black text-[#f8fafc]">{title as string}</h3>
              <p className="mt-2 text-sm leading-6 text-[#a7b8b1]">{detail as string}</p>
            </article>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-emerald-400/12 bg-[#07130f] p-4">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-[#a7b8b1]">
            Pedido → Título → Baixa → Conciliação
          </p>
          <div className="mt-4 grid gap-2 text-center text-xs font-black text-[#f8fafc] sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-center">
            {["PED-000050", "→", "RECEBER-PED000050", "→", "Em aberto", "→", "Pendente"].map(
              (item) => (
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
              ),
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function HeroSection() {
  return (
    <section id="topo" className="relative overflow-hidden px-5 pb-16 pt-12 sm:px-8 lg:px-10 lg:pb-24 lg:pt-20">
      <div
        className="absolute inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(16,185,129,0.2),transparent_34rem),radial-gradient(circle_at_85%_20%,rgba(56,189,248,0.12),transparent_30rem),linear-gradient(135deg,#020617_0%,#07130f_46%,#020617_100%)]"
        aria-hidden="true"
      />
      <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-emerald-400/30 to-transparent" />

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-black text-[#10b981]">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Kovir ERP v1.0
          </div>
          <h1 className="max-w-5xl text-4xl font-black leading-[1.02] tracking-tight text-[#f8fafc] sm:text-5xl lg:text-7xl">
            ERP operacional para pequenas e médias empresas que precisam sair da bagunça e enxergar o negócio.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-[#a7b8b1] sm:text-lg">
            O Kovir ERP centraliza cadastros, produtos, estoque, pedidos, financeiro, caixa, conciliação e relatórios em uma rotina mais clara, segura e rastreável para PMEs brasileiras.
          </p>
          <p className="mt-4 max-w-3xl text-base leading-8 text-[#a7b8b1]">
            Criado pela STVN Software, o Kovir foi pensado para empresas que cresceram além da planilha e precisam organizar a operação antes de escalar.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <ContactButton href={whatsappCta}>
              Agendar diagnóstico
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </ContactButton>
            <ContactButton href="#modulos" variant="secondary">
              Ver módulos do Kovir
            </ContactButton>
          </div>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-[#a7b8b1]">
            Demonstração controlada, piloto acompanhado e implantação assistida com escopo claro.
          </p>
        </div>
        <DashboardMockup />
      </div>
    </section>
  )
}

function WhatIsSection() {
  return (
    <SectionShell id="o-que-e" eyebrow="O que é" title="O que é o Kovir ERP?">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div className="rounded-[2rem] border border-emerald-400/14 bg-[#0f1f1a] p-6 sm:p-8">
          <p className="text-lg leading-8 text-[#a7b8b1]">
            O Kovir ERP é um sistema de gestão operacional para pequenas e médias empresas que precisam organizar o backoffice sem depender de planilhas soltas, controles manuais ou sistemas desconectados.
          </p>
          <p className="mt-5 text-lg leading-8 text-[#a7b8b1]">
            Ele atua como a base oficial da operação: registra cadastros, produtos, estoque, pedidos, contas, movimentações, baixas, conciliações e relatórios em um fluxo mais organizado.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
          {[
            ["Base operacional", "Centraliza informações essenciais da empresa para reduzir retrabalho, duplicidade e perda de contexto.", Database],
            ["Controle financeiro com clareza", "Ajuda a separar previsto, realizado, aberto, vencido, baixado e conciliado.", Banknote],
            ["Implantação assistida", "Adoção com diagnóstico, preparação de dados, escopo controlado e acompanhamento inicial.", ClipboardCheck],
          ].map(([title, text, Icon]) => (
            <article key={title as string} className="rounded-[1.5rem] border border-emerald-400/12 bg-[#122820] p-5">
              <Icon className="h-6 w-6 text-[#10b981]" aria-hidden="true" />
              <h3 className="mt-4 text-lg font-black text-[#f8fafc]">{title as string}</h3>
              <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{text as string}</p>
            </article>
          ))}
        </div>
      </div>
    </SectionShell>
  )
}

function AudienceSection() {
  return (
    <SectionShell
      id="para-quem"
      eyebrow="Para quem é"
      title="Para empresas que cresceram além da planilha."
      description="O Kovir ERP faz sentido para pequenas e médias empresas que já sentem que planilhas, cadernos ou sistemas antigos não acompanham mais a operação."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {painPoints.map((pain) => (
          <div key={pain} className="rounded-2xl border border-emerald-400/12 bg-[#0f1f1a] p-4 text-sm font-bold leading-6 text-[#f8fafc]">
            <AlertTriangle className="mb-3 h-5 w-5 text-[#f59e0b]" aria-hidden="true" />
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

function ComparisonCard({ title, items, tone }: { title: string; items: string[]; tone: "danger" | "success" }) {
  const toneClass = tone === "success" ? "text-[#10b981] border-emerald-400/16" : "text-[#f59e0b] border-amber-400/16"
  return (
    <article className={`rounded-[2rem] border bg-[#0f1f1a] p-6 ${toneClass}`}>
      <h3 className="text-2xl font-black text-[#f8fafc]">{title}</h3>
      <ul className="mt-6 space-y-4">
        {items.map((item) => (
          <li key={item} className="flex gap-3 text-sm font-bold leading-7 text-[#a7b8b1]">
            <CheckCircle2 className={`mt-1 h-4 w-4 shrink-0 ${toneClass}`} aria-hidden="true" />
            {item}
          </li>
        ))}
      </ul>
    </article>
  )
}

function ProblemsSection() {
  return (
    <SectionShell
      id="problema"
      eyebrow="Problema resolvido"
      title="O problema não é só ter informação. É saber qual informação é confiável."
      description="Quando venda, recebimento, baixa, caixa e banco ficam misturados, a empresa passa a decidir com base em números sem contexto. O Kovir ERP foi construído para organizar essas etapas e mostrar a origem das movimentações."
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <ComparisonCard title="Na operação desorganizada" items={["Pedido vira promessa de dinheiro.", "Saldo do banco vira financeiro inteiro.", "Planilha vira fonte de verdade.", "Título vencido passa despercebido.", "Estoque vira número manual.", "Relatório não explica origem."]} tone="danger" />
        <ComparisonCard title="Com o Kovir ERP" items={["Pedido organiza a venda.", "Título mostra o direito de receber.", "Baixa registra o realizado.", "Conciliação compara banco e controle interno.", "Estoque considera local, lote e validade.", "Relatório mostra contexto operacional."]} tone="success" />
      </div>
    </SectionShell>
  )
}

function ModulesSection() {
  return (
    <SectionShell
      id="modulos"
      eyebrow="Módulos"
      title="Módulos para organizar a operação de ponta a ponta."
      description="O Kovir ERP reúne os módulos operacionais e financeiros do Kovir ERP v1.0 para pequenas e médias empresas controlarem cadastros, vendas, estoque e financeiro operacional em uma base mais clara."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {modules.map(([title, text, Icon]) => (
          <article key={title} className="rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-4 transition hover:-translate-y-1 hover:border-emerald-300/30 hover:bg-[#122820]">
            <Icon className="h-5 w-5 text-[#10b981]" aria-hidden="true" />
            <h3 className="mt-4 text-base font-black text-[#f8fafc]">{title}</h3>
            <p className="mt-3 text-sm leading-6 text-[#a7b8b1]">{text}</p>
          </article>
        ))}
      </div>
    </SectionShell>
  )
}

function DifferentialsSection() {
  return (
    <SectionShell
      id="diferenciais"
      eyebrow="Diferencial conceitual"
      title="O Kovir não mistura conceitos que precisam estar separados."
      description="Essa separação é o que permite enxergar a operação com mais clareza."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {differentials.map(([title, text]) => (
          <article key={title} className="rounded-[1.5rem] border border-emerald-400/14 bg-[#0f1f1a] p-5">
            <BadgeCheck className="h-6 w-6 text-[#10b981]" aria-hidden="true" />
            <h3 className="mt-4 text-xl font-black leading-7 text-[#10b981]">{title}</h3>
            <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{text}</p>
          </article>
        ))}
      </div>
      <div className="mt-8 rounded-[1.5rem] border border-emerald-400/14 bg-[#07130f] p-5 text-sm font-black text-[#f8fafc]">
        Pedido → Título → Baixa → Movimento → Conciliação → Relatório
      </div>
    </SectionShell>
  )
}

function FlowSection() {
  return (
    <SectionShell id="fluxo" eyebrow="Fluxo" title="Da venda ao controle financeiro, cada etapa tem seu lugar.">
      <ol className="grid gap-4 lg:grid-cols-6">
        {flowSteps.map(([title, text], index) => (
          <li key={title} className="rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-400/10 text-sm font-black text-[#10b981]">
              {index + 1}
            </span>
            <h3 className="mt-5 text-lg font-black text-[#f8fafc]">{title}</h3>
            <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-8 text-lg font-black text-[#f8fafc]">
        Esse fluxo reduz a confusão entre vender, receber, baixar, conciliar e analisar.
      </p>
    </SectionShell>
  )
}

function FeatureGridSection({
  id,
  eyebrow,
  title,
  description,
  items,
}: {
  id: string
  eyebrow: string
  title: string
  description: string
  items: readonly (readonly [string, string])[]
}) {
  return (
    <SectionShell id={id} eyebrow={eyebrow} title={title} description={description}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {items.map(([itemTitle, itemText]) => (
          <article key={itemTitle} className="rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-5">
            <CheckCircle2 className="h-5 w-5 text-[#10b981]" aria-hidden="true" />
            <h3 className="mt-4 text-lg font-black text-[#f8fafc]">{itemTitle}</h3>
            <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{itemText}</p>
          </article>
        ))}
      </div>
    </SectionShell>
  )
}

function ImplementationSection() {
  return (
    <SectionShell
      id="implantacao"
      eyebrow="Implantação assistida"
      title="Implantação assistida, com escopo claro."
      description="O Kovir ERP não precisa começar por tudo. O ideal é validar os fluxos essenciais com acompanhamento e dados reais controlados."
    >
      <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {implementationSteps.map(([title, text], index) => (
          <li key={title} className="rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-400/10 text-sm font-black text-[#10b981]">
              {index + 1}
            </span>
            <h3 className="mt-5 text-lg font-black text-[#f8fafc]">{title}</h3>
            <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">{text}</p>
          </li>
        ))}
      </ol>
      <div className="mt-8">
        <ContactButton href={whatsappCta}>Quero agendar um diagnóstico</ContactButton>
      </div>
    </SectionShell>
  )
}

function TransparencySection() {
  return (
    <SectionShell
      id="transparencia"
      eyebrow="Transparência"
      title="Transparência também faz parte do produto."
      description="O Kovir ERP v1.0 é focado em organização operacional e financeira. Para preservar a clareza comercial, algumas frentes não devem ser tratadas como prontas sem validação específica."
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {transparencyItems.map((item) => (
          <div key={item} className="rounded-2xl border border-amber-400/14 bg-amber-400/8 p-5 text-sm font-bold leading-7 text-[#f8fafc]">
            <AlertTriangle className="mb-3 h-5 w-5 text-[#f59e0b]" aria-hidden="true" />
            {item}
          </div>
        ))}
      </div>
    </SectionShell>
  )
}

function FAQSection() {
  return (
    <SectionShell id="faq" eyebrow="FAQ" title="Perguntas frequentes">
      <div className="grid gap-4 lg:grid-cols-2">
        {faqItems.map(([question, answer]) => (
          <details key={question} className="group rounded-[1.5rem] border border-emerald-400/12 bg-[#0f1f1a] p-5">
            <summary className="flex cursor-pointer list-none items-start gap-3 text-lg font-black text-[#f8fafc] [&::-webkit-details-marker]:hidden">
              <HelpCircle className="mt-1 h-5 w-5 shrink-0 text-[#10b981]" aria-hidden="true" />
              {question}
            </summary>
            <p className="mt-4 text-sm leading-7 text-[#a7b8b1]">{answer}</p>
          </details>
        ))}
      </div>
    </SectionShell>
  )
}

function FinalCTA() {
  return (
    <section id="contato" className="px-5 py-16 sm:px-8 lg:px-10 lg:py-24">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-[2.5rem] border border-emerald-300/20 bg-[radial-gradient(circle_at_10%_10%,rgba(16,185,129,0.18),transparent_30rem),linear-gradient(135deg,#122820,#07130f)] p-7 shadow-[0_28px_90px_rgba(0,0,0,0.34)] sm:p-10 lg:p-14">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-black leading-tight text-[#f8fafc] sm:text-5xl">
            Quer entender se o Kovir ERP faz sentido para sua empresa?
          </h2>
          <p className="mt-5 text-base leading-8 text-[#a7b8b1] sm:text-lg">
            Converse com a STVN Software e veja como organizar cadastros, estoque, pedidos, financeiro e conciliação com uma implantação assistida e escopo claro.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <ContactButton href={whatsappCta}>
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
            <dd className="mt-2 text-[#f8fafc]">stvnsoftware.com.br/erpkovir</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-emerald-400/10 bg-[#020617] px-5 py-10 sm:px-8 lg:px-10">
      <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.2fr_0.8fr_0.8fr]">
        <div>
          <img src={kovirLogo} alt="Kovir ERP" className="h-24 w-auto object-contain" />
          <p className="mt-3 max-w-sm text-sm leading-7 text-[#a7b8b1]">
            ERP operacional para pequenas e médias empresas que precisam transformar rotina em controle.
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
          <h2 className="text-sm font-black uppercase tracking-[0.16em] text-[#10b981]">Contato</h2>
          <ul className="mt-4 space-y-3 text-sm text-[#a7b8b1]">
            <li>
              <a href={mailtoLink} className="break-words hover:text-[#f8fafc]">
                stvnsoftware@outlook.com
              </a>
            </li>
            <li>
              <a href={whatsappCta} className="hover:text-[#f8fafc]">
                (14) 99765-6475
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-10 max-w-7xl border-t border-emerald-400/10 pt-6 text-sm text-[#a7b8b1]">
        © 2026 STVN Software. Todos os direitos reservados. Kovir ERP é um produto da STVN Software.
      </div>
    </footer>
  )
}

export function KovirAboutPage() {
  useKovirAboutSeo()

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#020617] text-[#f8fafc] antialiased">
      <Header />
      <HeroSection />
      <WhatIsSection />
      <AudienceSection />
      <ProblemsSection />
      <ModulesSection />
      <DifferentialsSection />
      <FlowSection />
      <FeatureGridSection
        id="estoque"
        eyebrow="Estoque"
        title="Estoque não é só quantidade."
        description="Para muitas empresas, saber que existem unidades disponíveis não basta. É preciso saber onde o produto está, de qual lote veio, se tem validade e como se movimentou na operação."
        items={stockFeatures}
      />
      <FeatureGridSection
        id="financeiro"
        eyebrow="Financeiro operacional"
        title="Financeiro com contexto, não apenas saldo."
        description="O Kovir ERP ajuda a empresa a acompanhar contas a receber, contas a pagar, caixa, baixas, fluxo de caixa e conciliação sem tratar tudo como a mesma coisa."
        items={financeFeatures}
      />
      <FeatureGridSection
        id="migracao"
        eyebrow="Importação e migração"
        title="Migração assistida para empresas que já têm dados."
        description="O Kovir ERP foi pensado para apoiar empresas que vêm de planilhas ou sistemas antigos. A implantação pode começar com organização, validação e importação inicial de dados essenciais. A migração precisa de acompanhamento para reduzir entrada de dados duplicados ou inconsistentes."
        items={migrationFeatures}
      />
      <FeatureGridSection
        id="seguranca"
        eyebrow="Segurança e rastreabilidade"
        title="Controle operacional também exige responsabilidade com dados."
        description="O Kovir ERP considera permissões, usuários, auditoria e separação por empresa como parte da base do produto."
        items={securityFeatures}
      />
      <ImplementationSection />
      <TransparencySection />
      <FAQSection />
      <FinalCTA />
      <Footer />
    </main>
  )
}
