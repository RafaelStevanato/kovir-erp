import { AlertTriangle, KeyRound, Loader2, LockOpen, X } from "lucide-react"
import { useEffect, useState } from "react"

import { getMasterPasswordStatus, reopenOrder } from "./ordersApi"
import type { Order } from "./types"

type Props = {
  orderId: string
  onSuccess: (updatedOrder: Order) => void
  onClose: () => void
}

export function ReopenOrderModal({ orderId, onSuccess, onClose }: Props) {
  const [mpConfigured, setMpConfigured] = useState<boolean | null>(null)
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)
  const [password, setPassword] = useState("")
  const [reason, setReason] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setIsCheckingStatus(true)
    getMasterPasswordStatus()
      .then((res) => setMpConfigured(res.data.configured))
      .catch(() => setMpConfigured(false))
      .finally(() => setIsCheckingStatus(false))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!password || reason.trim().length < 10) return
    setIsSubmitting(true)
    setError(null)
    try {
      const res = await reopenOrder(orderId, { master_password: password, reason: reason.trim() })
      onSuccess(res.data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao reabrir pedido."
      // 403 maps to "Senha mestre incorreta."
      const isForbidden =
        typeof err === "object" &&
        err !== null &&
        "status" in err &&
        (err as { status: number }).status === 403
      setError(isForbidden ? "Senha mestre incorreta." : msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const reasonTooShort = reason.trim().length > 0 && reason.trim().length < 10
  const canSubmit = password.length > 0 && reason.trim().length >= 10

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-md rounded-[2rem] p-6 shadow-2xl"
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border-soft)",
        }}
      >
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl"
              style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b" }}
            >
              <LockOpen className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-black" style={{ color: "var(--color-text)" }}>
                Reabrir Pedido
              </h2>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Ação protegida por senha mestre
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 hover:bg-[var(--color-hover)]"
            style={{ color: "var(--color-text-muted)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {isCheckingStatus ? (
          <div className="flex items-center justify-center py-8 gap-2" style={{ color: "var(--color-text-muted)" }}>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Verificando configuração…</span>
          </div>
        ) : !mpConfigured ? (
          <div
            className="rounded-2xl p-4"
            style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.3)" }}
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "#f59e0b" }} />
              <div>
                <p className="text-sm font-bold" style={{ color: "#f59e0b" }}>
                  Senha mestre não configurada
                </p>
                <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Configure a senha mestre na página de <strong>Segurança → Senha Mestre</strong> antes de usar esta funcionalidade.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div
              className="rounded-2xl p-3 text-xs"
              style={{ background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.25)", color: "#d97706" }}
            >
              <strong>Atenção:</strong> reabrir o pedido irá estornar o estoque e cancelar as contas a receber geradas. O pedido voltará ao estado Orçamento.
            </div>

            {/* Password */}
            <label className="space-y-1.5 block">
              <span className="text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Senha Mestre *
              </span>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: "var(--color-text-weak)" }} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  autoFocus
                  className="w-full rounded-2xl py-3 pl-11 pr-4 text-sm outline-none"
                  style={{
                    background: "var(--color-bg-soft)",
                    border: "1px solid var(--color-border-soft)",
                    color: "var(--color-text)",
                  }}
                />
              </div>
            </label>

            {/* Reason */}
            <label className="space-y-1.5 block">
              <span className="text-xs font-black uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Motivo * <span className="font-normal normal-case">(mín. 10 caracteres)</span>
              </span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Ex: Erro na quantidade de itens. Corrigindo antes de reenviar."
                rows={3}
                required
                className="w-full resize-none rounded-2xl px-4 py-3 text-sm outline-none"
                style={{
                  background: "var(--color-bg-soft)",
                  border: `1px solid ${reasonTooShort ? "rgba(239,68,68,0.6)" : "var(--color-border-soft)"}`,
                  color: "var(--color-text)",
                }}
              />
              {reasonTooShort && (
                <p className="text-xs" style={{ color: "#ef4444" }}>
                  Mínimo 10 caracteres ({reason.trim().length} digitados)
                </p>
              )}
            </label>

            {error ? (
              <div className="rounded-2xl px-4 py-3 text-sm font-semibold" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}>
                <AlertTriangle className="mr-2 inline-block h-4 w-4" />
                {error}
              </div>
            ) : null}

            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="flex-1 rounded-2xl py-3 text-sm font-black"
                style={{
                  background: "var(--color-bg-soft)",
                  border: "1px solid var(--color-border-soft)",
                  color: "var(--color-text-muted)",
                }}
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={!canSubmit || isSubmitting}
                className="flex flex-1 items-center justify-center gap-2 rounded-2xl py-3 text-sm font-black transition-all"
                style={
                  canSubmit && !isSubmitting
                    ? { background: "rgba(245,158,11,0.85)", color: "#fff" }
                    : { background: "var(--color-bg-soft)", border: "1px solid var(--color-border-soft)", color: "var(--color-text-weak)", cursor: "not-allowed" }
                }
              >
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockOpen className="h-4 w-4" />}
                {isSubmitting ? "Reabrindo…" : "Confirmar Reabertura"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
