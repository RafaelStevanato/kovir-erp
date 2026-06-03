import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCheck2,
  Mail,
  ShieldCheck,
} from "lucide-react"

const nextSteps = [
  "Confirmação dos dados do contratante",
  "Entendimento do escopo inicial",
  "Organização dos dados de empresa, clientes, fornecedores e produtos",
  "Configuração dos módulos contratados",
  "Orientação de acesso ao ambiente Kovir ERP",
  "Início acompanhado da operação",
]

const preparationItems = [
  "Dados da empresa",
  "Lista de clientes e fornecedores, se houver",
  "Lista de produtos e serviços, se houver",
  "Informações básicas de estoque",
  "Contas a receber e pagar relevantes para implantação",
  "Dúvidas ou fluxos específicos da operação",
]

export function OnboardingPage() {
  return (
    <main className="min-h-screen bg-[#020617] text-[#f8fafc]">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-5 py-6 sm:px-8 lg:px-10">
        <header className="flex items-center justify-between border-b border-emerald-500/15 pb-5">
          <a href="/" className="group flex items-center gap-3" aria-label="Voltar ao site do Kovir">
            <img
              src="/kovir-logo.png"
              alt="Kovir ERP"
              className="h-14 w-14 shrink-0 object-contain drop-shadow-[0_0_18px_rgba(16,185,129,0.38)]"
            />
            <span className="leading-tight">
              <span className="block text-base font-black tracking-[0.08em] text-[#f8fafc] uppercase">
                Kovir ERP
              </span>
              <span className="text-xs font-semibold text-[#a7b8b1]">por STVN Software</span>
            </span>
          </a>
          <img
            src="/stvn-software-logo.png"
            alt="STVN Software"
            className="hidden h-12 w-12 shrink-0 object-contain drop-shadow-[0_0_16px_rgba(16,185,129,0.28)] sm:block"
          />
        </header>

        <section className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[1.12fr_0.88fr] lg:py-16">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-bold text-[#10b981]">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              Pós-compra com implantação assistida
            </div>

            <h1 className="max-w-4xl text-4xl font-black leading-tight tracking-normal text-[#f8fafc] sm:text-5xl lg:text-6xl">
              Obrigado por contratar o Kovir ERP
            </h1>

            <p className="mt-6 max-w-2xl text-lg leading-8 text-[#a7b8b1]">
              Recebemos sua solicitação. A implantação do Kovir ERP é assistida para que sua
              empresa comece com mais clareza, organização e segurança operacional.
            </p>

            <p className="mt-5 max-w-2xl text-base leading-7 text-[#a7b8b1]">
              A STVN Software entrará em contato para validar os dados do contratante, entender
              o escopo inicial e orientar a configuração dos primeiros módulos. O objetivo é
              evitar uma implantação solta, com dados incompletos ou uso incorreto do sistema.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <a
                href="mailto:contato@stvnsoftware.com.br"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#10b981] px-5 py-3 text-sm font-black text-[#020617] shadow-[0_18px_36px_rgba(16,185,129,0.22)] transition hover:bg-[#047857] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#38bdf8]"
              >
                <Mail className="h-4 w-4" aria-hidden="true" />
                Falar com a STVN Software
              </a>
              <a
                href="/"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-emerald-400/25 bg-[#0f1f1a] px-5 py-3 text-sm font-black text-[#f8fafc] transition hover:border-emerald-400/50 hover:bg-[#122820] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#38bdf8]"
              >
                Acessar site do Kovir
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </div>

          <aside
            className="rounded-lg border border-emerald-400/20 bg-[#0f1f1a] p-6 shadow-[0_24px_70px_rgba(0,0,0,0.28)]"
            aria-label="Status da contratação"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-bold text-[#a7b8b1]">Status</p>
                <h2 className="mt-2 text-2xl font-black text-[#f8fafc]">Contratação recebida</h2>
              </div>
              <CheckCircle2 className="h-8 w-8 shrink-0 text-[#10b981]" aria-hidden="true" />
            </div>

            <div className="mt-6 border-t border-emerald-400/15">
              <div className="py-5">
                <p className="text-xs font-black uppercase tracking-[0.12em] text-[#10b981]">
                  Próxima etapa
                </p>
                <p className="mt-2 text-base font-bold text-[#f8fafc]">Onboarding assistido</p>
              </div>
              <div className="border-t border-emerald-400/15 py-5">
                <p className="text-xs font-black uppercase tracking-[0.12em] text-[#38bdf8]">
                  Prazo de contato
                </p>
                <p className="mt-2 text-base leading-7 text-[#f8fafc]">
                  Nossa equipe entrará em contato para orientar os próximos passos.
                </p>
              </div>
            </div>
          </aside>
        </section>

        <section className="border-t border-emerald-500/15 py-12">
          <div className="grid gap-8 lg:grid-cols-[0.82fr_1.18fr]">
            <div>
              <p className="text-sm font-black uppercase tracking-[0.14em] text-[#10b981]">
                Próximas etapas
              </p>
              <h2 className="mt-3 text-3xl font-black text-[#f8fafc]">
                Implantação com sequência clara
              </h2>
            </div>

            <ol className="grid gap-3 sm:grid-cols-2">
              {nextSteps.map((step, index) => (
                <li
                  key={step}
                  className="rounded-lg border border-emerald-400/15 bg-[#0f1f1a] p-4"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-md bg-emerald-400/10 text-sm font-black text-[#10b981]">
                    {index + 1}
                  </span>
                  <p className="mt-4 text-sm font-bold leading-6 text-[#f8fafc]">{step}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="grid gap-8 border-t border-emerald-500/15 py-12 lg:grid-cols-2">
          <div className="rounded-lg border border-emerald-400/15 bg-[#0f1f1a] p-6">
            <div className="flex items-center gap-3">
              <ClipboardList className="h-6 w-6 text-[#10b981]" aria-hidden="true" />
              <h2 className="text-2xl font-black text-[#f8fafc]">O que preparar</h2>
            </div>
            <ul className="mt-6 space-y-3">
              {preparationItems.map((item) => (
                <li key={item} className="flex gap-3 text-sm leading-6 text-[#a7b8b1]">
                  <CheckCircle2
                    className="mt-0.5 h-4 w-4 shrink-0 text-[#10b981]"
                    aria-hidden="true"
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="grid gap-4">
            <div className="rounded-lg border border-emerald-400/15 bg-[#0f1f1a] p-5">
              <Building2 className="h-6 w-6 text-[#38bdf8]" aria-hidden="true" />
              <h3 className="mt-4 text-lg font-black text-[#f8fafc]">Dados e operação</h3>
              <p className="mt-2 text-sm leading-6 text-[#a7b8b1]">
                Cadastros, produtos, estoque, pedidos, contas, caixa e fluxos operacionais são
                organizados conforme o escopo contratado.
              </p>
            </div>
            <div className="rounded-lg border border-emerald-400/15 bg-[#0f1f1a] p-5">
              <Database className="h-6 w-6 text-[#38bdf8]" aria-hidden="true" />
              <h3 className="mt-4 text-lg font-black text-[#f8fafc]">Importação assistida</h3>
              <p className="mt-2 text-sm leading-6 text-[#a7b8b1]">
                Quando houver planilhas, a validação dos dados ajuda a reduzir retrabalho e
                inconsistências no início da operação.
              </p>
            </div>
          </div>
        </section>

        <section className="border-t border-emerald-500/15 py-12">
          <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 p-6">
            <div className="flex flex-col gap-4 sm:flex-row">
              <FileCheck2 className="h-7 w-7 shrink-0 text-[#f59e0b]" aria-hidden="true" />
              <div>
                <h2 className="text-xl font-black text-[#f8fafc]">Importante</h2>
                <p className="mt-3 text-sm leading-7 text-[#f8fafc]">
                  O Kovir ERP não é entregue como curso, e-book ou área de membros. O acesso ao
                  sistema é orientado pela etapa de onboarding e implantação assistida.
                </p>
                <p className="mt-3 text-sm leading-7 text-[#a7b8b1]">
                  A configuração inicial depende da validação dos dados e do escopo contratado.
                </p>
              </div>
            </div>
          </div>
        </section>

        <footer className="flex flex-col gap-4 border-t border-emerald-500/15 py-7 text-sm text-[#a7b8b1] sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/kovir-logo.png"
              alt="Kovir ERP"
              className="h-10 w-10 shrink-0 object-contain"
            />
            <div>
              <p className="font-black text-[#f8fafc]">Kovir ERP — STVN Software</p>
              <p className="mt-2">Organização operacional para pequenas e médias empresas.</p>
            </div>
          </div>
          <img
            src="/stvn-software-logo.png"
            alt="STVN Software"
            className="h-10 w-10 shrink-0 object-contain opacity-90"
          />
        </footer>
      </div>
    </main>
  )
}
