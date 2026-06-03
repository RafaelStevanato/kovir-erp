import { Sparkles } from "lucide-react"

export function AiPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-12 text-center shadow-2xl shadow-[var(--color-card-shadow)]">
      <span className="flex h-20 w-20 items-center justify-center rounded-3xl border border-[#6358d7]/30 bg-[#6358d7]/10 text-[#6358d7]">
        <Sparkles className="h-10 w-10" />
      </span>
      <div>
        <h1 className="text-3xl font-black tracking-tight text-[var(--color-text)]">
          Inteligência Artificial
        </h1>
        <p className="mt-3 max-w-md text-base text-[var(--color-text-muted)]">
          Em breve: análises preditivas, insights automáticos e assistente financeiro integrado ao Kovir.
        </p>
      </div>
      <span className="rounded-full border border-[#6358d7]/30 bg-[#6358d7]/10 px-4 py-1.5 text-xs font-black tracking-widest text-[#6358d7] uppercase">
        Em desenvolvimento
      </span>
    </div>
  )
}
