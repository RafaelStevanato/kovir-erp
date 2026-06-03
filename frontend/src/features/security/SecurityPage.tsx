import { useEffect, useMemo, useState, type ReactNode } from "react"
import { AlertTriangle, CheckCircle2, KeyRound, Loader2, LogIn, PencilLine, Save, ShieldCheck, UserPlus, Users, X } from "lucide-react"

import { clearAuthSession, getAuthSession, setAuthSession, type AuthSession } from "../../config/authSession"
import { setActiveCompanyId } from "../../config/activeCompany"
import { useActiveCompany } from "../../config/useActiveCompany"
import {
  createApprovalRequest,
  createCompanyUser,
  decideApprovalRequest,
  getMasterPasswordStatus,
  getPaymentApprovalPolicy,
  getSecurityDiagnostics,
  getSecurityRules,
  listApprovalRequests,
  listAllowedViews,
  listCompanyUsers,
  listPermissions,
  listRoles,
  login,
  logout,
  setMasterPassword,
  updateCompanyUserRoles,
  updatePaymentApprovalPolicy,
} from "./securityApi"
import type { ApprovalPolicy, ApprovalRequest, CompanyUserItem, PermissionItem, RoleItem, SecurityRules } from "./types"

type Notice = { type: "success" | "error"; message: string } | null

type AllowedViewOption = {
  view: string
  label: string
  is_financial_default: boolean
  requires_master: boolean
}

export function SecurityPage() {
  const { companyId: activeCompanyId, activeCompanyName } = useActiveCompany()
  const [session, setSession] = useState<AuthSession | null>(() => getAuthSession())
  const [notice, setNotice] = useState<Notice>(null)

  const [isLoadingData, setIsLoadingData] = useState(false)
  const [isSubmittingLogin, setIsSubmittingLogin] = useState(false)
  const [isSavingPolicy, setIsSavingPolicy] = useState(false)
  const [isCreatingUser, setIsCreatingUser] = useState(false)
  const [isSavingUserAccess, setIsSavingUserAccess] = useState(false)
  const [isCreatingApproval, setIsCreatingApproval] = useState(false)

  const [rules, setRules] = useState<SecurityRules | null>(null)
  const [diagnostics, setDiagnostics] = useState<{
    users: number
    active_sessions: number
    pending_approvals: number
  } | null>(null)
  const [roles, setRoles] = useState<RoleItem[]>([])
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [allowedViews, setAllowedViews] = useState<AllowedViewOption[]>([])
  const [companyUsers, setCompanyUsers] = useState<CompanyUserItem[]>([])
  const [approvalPolicy, setApprovalPolicy] = useState<ApprovalPolicy | null>(null)
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>([])

  const [loginEmail, setLoginEmail] = useState("")
  const [loginPassword, setLoginPassword] = useState("")
  const [loginCompanyId, setLoginCompanyId] = useState(activeCompanyId ?? "")

  const [newUserEmail, setNewUserEmail] = useState("")
  const [newUserName, setNewUserName] = useState("")
  const [newUserPassword, setNewUserPassword] = useState("")
  const [newUserViews, setNewUserViews] = useState<string[]>([
    "overview",
    "financial",
    "accountsReceivable",
    "cash",
    "reconciliation",
    "cashFlow",
    "purchasesPayables",
    "managementReports",
    "biAnalytics",
    "ai",
  ])

  const [policyThreshold, setPolicyThreshold] = useState("1000.00")
  const [policyPermission, setPolicyPermission] = useState("approval.decide")
  const [policyAllowSelf, setPolicyAllowSelf] = useState(false)

  const [newApprovalTitleId, setNewApprovalTitleId] = useState("")
  const [newApprovalAmount, setNewApprovalAmount] = useState("")
  const [newApprovalReason, setNewApprovalReason] = useState("")
  const [editingMembershipId, setEditingMembershipId] = useState<string | null>(null)
  const [editingUserViews, setEditingUserViews] = useState<string[]>([])

  // ── Senha mestre ─────────────────────────────────────────────────────────
  const [mpConfigured, setMpConfigured] = useState<boolean | null>(null)
  const [mpNewPassword, setMpNewPassword] = useState("")
  const [mpConfirmPassword, setMpConfirmPassword] = useState("")
  const [isSavingMp, setIsSavingMp] = useState(false)
  const [mpNotice, setMpNotice] = useState<Notice>(null)

  const isMaster = useMemo(() => session?.roles.includes("admin") ?? false, [session?.roles])

  async function loadSecuredData() {
    if (!session) return
    setIsLoadingData(true)
    setNotice(null)
    try {
      const allowedViewsPromise = isMaster
        ? listAllowedViews()
        : Promise.resolve({ success: true, message: "", data: [] as AllowedViewOption[] })

      const [rulesResponse, diagnosticsResponse, rolesResponse, permissionsResponse, allowedViewsResponse, companyUsersResponse, policyResponse, requestsResponse, mpStatusResponse] =
        await Promise.all([
          getSecurityRules(),
          getSecurityDiagnostics(),
          listRoles(),
          listPermissions(),
          allowedViewsPromise,
          listCompanyUsers(),
          getPaymentApprovalPolicy(),
          listApprovalRequests({ limit: 100 }),
          getMasterPasswordStatus().catch(() => ({ data: { configured: false } })),
        ])

      setRules(rulesResponse.data)
      setDiagnostics({
        users: diagnosticsResponse.data.users,
        active_sessions: diagnosticsResponse.data.active_sessions,
        pending_approvals: diagnosticsResponse.data.pending_approvals,
      })
      setRoles(rolesResponse.data)
      setPermissions(permissionsResponse.data)
      setAllowedViews(allowedViewsResponse.data)
      setCompanyUsers(companyUsersResponse.data)
      setApprovalPolicy(policyResponse.data)
      setApprovalRequests(requestsResponse.data)
      setMpConfigured(mpStatusResponse.data.configured)

      setPolicyThreshold(policyResponse.data.threshold_amount)
      setPolicyPermission(policyResponse.data.required_permission_code)
      setPolicyAllowSelf(policyResponse.data.allow_self_approval)
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao carregar segurança." })
    } finally {
      setIsLoadingData(false)
    }
  }

  useEffect(() => {
    void loadSecuredData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  async function handleLoginSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSubmittingLogin(true)
    setNotice(null)
    try {
      const response = await login({
        email: loginEmail,
        password: loginPassword,
        company_id: loginCompanyId,
      })
      const data = response.data
      const nextSession: AuthSession = {
        accessToken: data.access_token,
        expiresAt: data.expires_at,
        companyId: data.session.company_id,
        userId: data.user.id,
        fullName: data.user.full_name,
        email: data.user.email,
        roles: data.roles,
        permissions: data.permissions,
        allowedViews: data.allowed_views ?? [],
      }
      setAuthSession(nextSession)
      setActiveCompanyId(data.session.company_id)
      setSession(nextSession)
      setNotice({ type: "success", message: "Login realizado com sucesso." })
      setLoginPassword("")
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao realizar login." })
    } finally {
      setIsSubmittingLogin(false)
    }
  }

  async function handleLogout() {
    try {
      await logout()
    } catch {
      // noop
    } finally {
      clearAuthSession()
      setSession(null)
      setRules(null)
      setDiagnostics(null)
      setRoles([])
      setPermissions([])
      setAllowedViews([])
      setCompanyUsers([])
      setApprovalPolicy(null)
      setApprovalRequests([])
      setNotice({ type: "success", message: "Sessão encerrada." })
    }
  }

  async function handleCreateUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session) return
    setIsCreatingUser(true)
    setNotice(null)
    try {
      await createCompanyUser({
        company_id: session.companyId,
        email: newUserEmail,
        full_name: newUserName,
        password: newUserPassword,
        allowed_views: [...new Set([...newUserViews, "overview"])],
      })
      setNotice({ type: "success", message: "Usuário criado/atualizado com sucesso." })
      setNewUserEmail("")
      setNewUserName("")
      setNewUserPassword("")
      setNewUserViews(
        allowedViews.filter((item) => item.is_financial_default).map((item) => item.view),
      )
      await loadSecuredData()
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao salvar usuário." })
    } finally {
      setIsCreatingUser(false)
    }
  }

  async function handleSavePolicy(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsSavingPolicy(true)
    setNotice(null)
    try {
      const response = await updatePaymentApprovalPolicy({
        threshold_amount: policyThreshold,
        required_permission_code: policyPermission,
        allow_self_approval: policyAllowSelf,
      })
      setApprovalPolicy(response.data)
      setNotice({ type: "success", message: "Política de alçada atualizada." })
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao salvar política." })
    } finally {
      setIsSavingPolicy(false)
    }
  }

  function beginEditUser(item: CompanyUserItem) {
    setEditingMembershipId(item.membership.id)
    setEditingUserViews(item.allowed_views?.length ? [...new Set(item.allowed_views)] : ["overview"])
  }

  function cancelEditUser() {
    setEditingMembershipId(null)
    setEditingUserViews([])
  }

  async function handleUpdateUserAccess(item: CompanyUserItem) {
    setIsSavingUserAccess(true)
    setNotice(null)
    try {
      await updateCompanyUserRoles({
        membership_id: item.membership.id,
        allowed_views: [...new Set([...editingUserViews, "overview"])],
      })
      setNotice({ type: "success", message: "Permissões do usuário atualizadas com sucesso." })
      cancelEditUser()
      await loadSecuredData()
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao atualizar permissões." })
    } finally {
      setIsSavingUserAccess(false)
    }
  }

  async function handleCreateApproval(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsCreatingApproval(true)
    setNotice(null)
    try {
      await createApprovalRequest({
        financial_title_id: newApprovalTitleId,
        requested_amount: newApprovalAmount,
        reason: newApprovalReason,
        payload_snapshot: {},
      })
      setNotice({ type: "success", message: "Solicitação de alçada criada." })
      setNewApprovalTitleId("")
      setNewApprovalAmount("")
      setNewApprovalReason("")
      await loadSecuredData()
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao criar alçada." })
    } finally {
      setIsCreatingApproval(false)
    }
  }

  async function handleDecision(approvalRequestId: string, decision: "approved" | "rejected") {
    setNotice(null)
    try {
      await decideApprovalRequest(approvalRequestId, { decision })
      setNotice({ type: "success", message: `Solicitação ${decision === "approved" ? "aprovada" : "rejeitada"}.` })
      await loadSecuredData()
    } catch (error) {
      setNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao decidir alçada." })
    }
  }

  async function handleSaveMasterPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!mpNewPassword) return
    if (mpNewPassword !== mpConfirmPassword) {
      setMpNotice({ type: "error", message: "As senhas não coincidem." })
      return
    }
    if (mpNewPassword.length < 6) {
      setMpNotice({ type: "error", message: "A senha deve ter pelo menos 6 caracteres." })
      return
    }
    setIsSavingMp(true)
    setMpNotice(null)
    try {
      const res = await setMasterPassword(mpNewPassword)
      setMpConfigured(res.data.configured)
      setMpNewPassword("")
      setMpConfirmPassword("")
      setMpNotice({ type: "success", message: "Senha mestre configurada com sucesso." })
    } catch (error) {
      setMpNotice({ type: "error", message: error instanceof Error ? error.message : "Falha ao configurar senha mestre." })
    } finally {
      setIsSavingMp(false)
    }
  }

  if (!session) {
    return (
      <div className="relative min-h-screen overflow-hidden" style={{ background: "#020617" }}>
        {/* ── Ambient glow orbs ── */}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <div className="absolute -bottom-64 -left-64 h-[600px] w-[600px] rounded-full" style={{ background: "radial-gradient(circle, rgba(16,185,129,0.22) 0%, transparent 65%)", filter: "blur(80px)" }} />
          <div className="absolute -top-64 -right-64 h-[600px] w-[600px] rounded-full" style={{ background: "radial-gradient(circle, rgba(56,189,248,0.16) 0%, transparent 65%)", filter: "blur(80px)" }} />
          <div className="absolute bottom-0 right-1/3 h-[400px] w-[400px] rounded-full" style={{ background: "radial-gradient(circle, rgba(99,88,215,0.18) 0%, transparent 65%)", filter: "blur(70px)" }} />
          <div className="absolute top-1/3 left-1/4 h-[300px] w-[300px] rounded-full" style={{ background: "radial-gradient(circle, rgba(16,185,129,0.1) 0%, transparent 65%)", filter: "blur(60px)" }} />
        </div>

        {/* ── Dot grid ── */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.055]"
          aria-hidden="true"
          style={{ backgroundImage: "radial-gradient(circle, #10b981 1px, transparent 1px)", backgroundSize: "34px 34px" }}
        />

        {/* ── Content ── */}
        <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
          <div className="w-full max-w-sm">

            {/* Logo */}
            <div className="mb-8 flex flex-col items-center gap-3">
              <img
                src="/kovir-logo.png"
                alt="Kovir"
                className="h-24 w-24 object-contain drop-shadow-2xl"
                style={{ filter: "drop-shadow(0 0 24px rgba(16,185,129,0.45))" }}
              />
              <div className="text-center">
                <h1
                  className="text-3xl font-black tracking-[0.2em]"
                  style={{ color: "#f8fafc", textShadow: "0 0 40px rgba(16,185,129,0.35)" }}
                >
                  KOVIR
                </h1>
                <p
                  className="mt-1 text-[9px] font-bold tracking-[0.45em] uppercase"
                  style={{ color: "#10b981" }}
                >
                  Enterprise Resource Planning
                </p>
              </div>
            </div>

            {/* Card */}
            <div
              className="rounded-[1.75rem] p-7"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
                backdropFilter: "blur(28px)",
                WebkitBackdropFilter: "blur(28px)",
                boxShadow: "0 32px 64px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.07)",
              }}
            >
              <div className="mb-5">
                <h2 className="text-xl font-black" style={{ color: "#f8fafc" }}>
                  Entrar na plataforma
                </h2>
                <p className="mt-1 text-xs" style={{ color: "rgba(248,250,252,0.38)" }}>
                  Informe suas credenciais para acessar o ERP
                </p>
              </div>

              {notice ? (
                <div className="mb-5">
                  <NoticeBox notice={notice} />
                </div>
              ) : null}

              <form onSubmit={handleLoginSubmit} className="space-y-4">
                <LoginField label="E-mail" value={loginEmail} onChange={setLoginEmail} type="email" placeholder="admin@empresa.com" autoComplete="email" />
                <LoginField label="Senha" value={loginPassword} onChange={setLoginPassword} type="password" placeholder="••••••••" autoComplete="current-password" />
                <LoginField label="ID da empresa" value={loginCompanyId} onChange={setLoginCompanyId} placeholder="company_..." />

                <button
                  type="submit"
                  disabled={isSubmittingLogin}
                  className="mt-2 flex w-full items-center justify-center gap-2.5 rounded-2xl py-3.5 text-sm font-black tracking-wide transition-all duration-200 hover:brightness-110 active:scale-[0.98] disabled:opacity-60"
                  style={{
                    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                    color: "#f8fafc",
                    boxShadow: "0 0 32px rgba(16,185,129,0.4), 0 4px 16px rgba(0,0,0,0.35)",
                  }}
                >
                  {isSubmittingLogin ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                  {isSubmittingLogin ? "Entrando…" : "Entrar"}
                </button>
              </form>

              <div className="mt-6 flex items-center justify-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5" style={{ color: "#10b981" }} />
                <span className="text-[11px] font-medium" style={{ color: "rgba(248,250,252,0.28)" }}>
                  Sessão autenticada e isolada por empresa
                </span>
              </div>
            </div>

            {/* Footer */}
            <p className="mt-6 text-center text-[11px]" style={{ color: "rgba(248,250,252,0.16)" }}>
              © {new Date().getFullYear()} Kovir · ERP modular para PMEs brasileiras
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <header className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-6 shadow-2xl shadow-[var(--color-card-shadow)] sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-[var(--color-primary)]">Sessão autenticada</p>
            <h1 className="mt-2 text-3xl font-black text-[var(--color-text)] sm:text-4xl">Usuários e Permissões</h1>
            <p className="mt-3 text-sm text-[var(--color-text-muted)]">
              Usuário: <span className="font-semibold text-[var(--color-text)]">{session.fullName}</span> ({session.email}) • Empresa:{" "}
              <span className="font-semibold text-[var(--color-text)]">{activeCompanyName || "Empresa da sessão"}</span>
            </p>
          </div>

          <button type="button" onClick={handleLogout} className="rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-2 text-sm font-black text-red-100 hover:bg-red-500/20">
            Sair
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <MetricCard label="Usuários" value={String(diagnostics?.users ?? 0)} helper="cadastros ativos" />
          <MetricCard label="Sessões" value={String(diagnostics?.active_sessions ?? 0)} helper="tokens válidos" />
          <MetricCard label="Alçadas pendentes" value={String(diagnostics?.pending_approvals ?? 0)} helper="decisão necessária" tone={(diagnostics?.pending_approvals ?? 0) > 0 ? "warning" : "success"} />
        </div>
      </header>

      {notice ? <NoticeBox notice={notice} /> : null}

      {isLoadingData ? (
        <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 text-sm text-[var(--color-text-muted)]">
          <span className="inline-flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" />Carregando dados de segurança...</span>
        </section>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <form onSubmit={handleCreateUser} className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="flex items-center gap-2 text-lg font-black text-[var(--color-text)]"><Users className="h-5 w-5" /> Usuários da empresa</h2>
          <Input label="Nome completo" value={newUserName} onChange={setNewUserName} />
          <Input label="E-mail" value={newUserEmail} onChange={setNewUserEmail} />
          <Input label="Senha inicial" value={newUserPassword} onChange={setNewUserPassword} type="password" />

          <label className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Abas permitidas</span>
            <div className="grid gap-2 sm:grid-cols-2">
              {allowedViews.map((item) => (
                <label key={item.view} className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={newUserViews.includes(item.view)}
                    disabled={!isMaster || item.requires_master}
                    onChange={(event) => {
                      setNewUserViews((current) => {
                        if (event.target.checked) return [...new Set([...current, item.view])]
                        return current.filter((view) => view !== item.view)
                      })
                    }}
                  />
                  <span className="text-[var(--color-text)]">
                    {item.label}
                    {item.is_financial_default ? " • financeiro" : ""}
                  </span>
                </label>
              ))}
            </div>
          </label>

          <button type="submit" disabled={isCreatingUser || !isMaster} className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-60">
            {isCreatingUser ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
            {isMaster ? "Salvar usuário" : "Somente master pode criar usuários"}
          </button>

          <div className="space-y-2">
            {companyUsers.map((item) => (
              <div key={item.membership.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2">
                <p className="text-sm font-semibold text-[var(--color-text)]">{item.user?.full_name ?? item.membership.user_id}</p>
                <p className="text-xs text-[var(--color-text-muted)]">{item.user?.email}</p>
                <p className="mt-1 text-xs font-semibold text-[var(--color-primary)]">{item.roles.join(", ") || "sem papel"}</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Abas: {item.allowed_views?.join(", ") || "overview"}
                </p>
                {editingMembershipId === item.membership.id ? (
                  <div className="mt-3 space-y-3 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-3">
                    <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">Editar abas permitidas</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {allowedViews.map((viewOption) => (
                        <label key={`${item.membership.id}-${viewOption.view}`} className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm">
                          <input
                            type="checkbox"
                            checked={editingUserViews.includes(viewOption.view)}
                            disabled={viewOption.requires_master}
                            onChange={(event) => {
                              setEditingUserViews((current) => {
                                if (event.target.checked) return [...new Set([...current, viewOption.view])]
                                return current.filter((view) => view !== viewOption.view)
                              })
                            }}
                          />
                          <span className="text-[var(--color-text)]">{viewOption.label}</span>
                        </label>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void handleUpdateUserAccess(item)}
                        disabled={isSavingUserAccess}
                        className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-black text-[var(--color-primary)] disabled:opacity-60"
                      >
                        {isSavingUserAccess ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                        Salvar permissões
                      </button>
                      <button
                        type="button"
                        onClick={cancelEditUser}
                        disabled={isSavingUserAccess}
                        className="inline-flex items-center gap-2 rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] px-3 py-2 text-xs font-black text-[var(--color-text)] disabled:opacity-60"
                      >
                        <X className="h-3.5 w-3.5" />
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => beginEditUser(item)}
                    disabled={!isMaster || isSavingUserAccess}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs font-black text-[var(--color-primary)] disabled:opacity-60"
                  >
                    <PencilLine className="h-3.5 w-3.5" />
                    Editar permissões
                  </button>
                )}
              </div>
            ))}
          </div>
        </form>

        <form onSubmit={handleSavePolicy} className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-lg font-black text-[var(--color-text)]">Política de alçada (pagamentos)</h2>
          <Input label="Threshold (BRL)" value={policyThreshold} onChange={setPolicyThreshold} />
          <Input label="Permissão para decidir" value={policyPermission} onChange={setPolicyPermission} />
          <label className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
            <input type="checkbox" checked={policyAllowSelf} onChange={(event) => setPolicyAllowSelf(event.target.checked)} />
            Permitir autoaprovação
          </label>
          <button type="submit" disabled={isSavingPolicy} className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-60">
            {isSavingPolicy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            Salvar política
          </button>

          <div className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-3 text-xs text-[var(--color-text-muted)]">
            {approvalPolicy ? (
              <p>
                Configuração atual: acima de <strong>{approvalPolicy.threshold_amount}</strong> {approvalPolicy.currency} exige{" "}
                <strong>{approvalPolicy.required_permission_code}</strong>.
              </p>
            ) : (
              <p>Política ainda não carregada.</p>
            )}
          </div>
        </form>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <form onSubmit={handleCreateApproval} className="space-y-4 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-lg font-black text-[var(--color-text)]">Abrir solicitação de alçada</h2>
          <Input label="Título a pagar (ap_...)" value={newApprovalTitleId} onChange={setNewApprovalTitleId} />
          <Input label="Valor solicitado" value={newApprovalAmount} onChange={setNewApprovalAmount} />
          <Input label="Motivo" value={newApprovalReason} onChange={setNewApprovalReason} />
          <button type="submit" disabled={isCreatingApproval} className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-60">
            {isCreatingApproval ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Solicitar aprovação
          </button>
        </form>

        <div className="space-y-3 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
          <h2 className="text-lg font-black text-[var(--color-text)]">Fila de alçadas</h2>
          {approvalRequests.length === 0 ? (
            <p className="text-sm text-[var(--color-text-muted)]">Sem solicitações no momento.</p>
          ) : (
            approvalRequests.slice(0, 10).map((request) => (
              <article key={request.id} className="rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-bold text-[var(--color-text)]">{request.id}</p>
                  <StatusBadge status={request.status} />
                </div>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  Título: {request.target_entity_id} • Valor: {request.requested_amount} {request.currency}
                </p>
                {request.reason ? <p className="mt-2 text-xs text-[var(--color-text-muted)]">{request.reason}</p> : null}
                {request.status === "pending" ? (
                  <div className="mt-3 flex gap-2">
                    <button type="button" onClick={() => void handleDecision(request.id, "approved")} className="rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-100 hover:bg-emerald-500/20">
                      Aprovar
                    </button>
                    <button type="button" onClick={() => void handleDecision(request.id, "rejected")} className="rounded-xl border border-red-400/40 bg-red-500/10 px-3 py-1 text-xs font-bold text-red-100 hover:bg-red-500/20">
                      Rejeitar
                    </button>
                  </div>
                ) : null}
              </article>
            ))
          )}
        </div>
      </section>

      <section className="grid gap-5">
        <Panel title="Papéis disponíveis">
          {roles.map((role) => (
            <p key={role.code} className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
              <strong>{role.code}</strong> — {role.description || role.name}
            </p>
          ))}
        </Panel>

        <Panel title="Permissões disponíveis">
          {permissions.map((permission) => (
            <p key={permission.code} className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
              <strong>{permission.code}</strong> — {permission.name}
            </p>
          ))}
        </Panel>

        <Panel title="Abas delegáveis">
          {allowedViews.map((item) => (
            <p key={item.view} className="rounded-xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text)]">
              <strong>{item.label}</strong> — {item.view}
            </p>
          ))}
        </Panel>
      </section>

      {/* ── Senha Mestre ────────────────────────────────────────────── */}
      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <h2 className="flex items-center gap-2 text-lg font-black text-[var(--color-text)]">
          <KeyRound className="h-5 w-5" /> Senha Mestre
        </h2>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Usada para reabrir pedidos fechados. Requer permissão <strong>sales.unlock_closed</strong>.
        </p>

        {/* Status badge */}
        <div className="mt-3">
          {mpConfigured === null ? (
            <span className="inline-flex items-center gap-1.5 text-sm text-[var(--color-text-muted)]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verificando…
            </span>
          ) : mpConfigured ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-black text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" /> Configurada
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-xs font-black text-amber-400">
              <AlertTriangle className="h-3.5 w-3.5" /> Não configurada
            </span>
          )}
        </div>

        {mpNotice ? (
          <div className={`mt-3 rounded-2xl border px-4 py-3 text-sm font-semibold ${mpNotice.type === "success" ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100" : "border-red-400/40 bg-red-500/10 text-red-100"}`}>
            {mpNotice.message}
          </div>
        ) : null}

        <form onSubmit={(e) => void handleSaveMasterPassword(e)} className="mt-4 space-y-3">
          <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">
            {mpConfigured ? "Alterar senha mestre" : "Definir senha mestre"}
          </p>
          <Input
            label="Nova senha"
            value={mpNewPassword}
            onChange={setMpNewPassword}
            type="password"
            placeholder="••••••••"
          />
          <Input
            label="Confirmar nova senha"
            value={mpConfirmPassword}
            onChange={setMpConfirmPassword}
            type="password"
            placeholder="••••••••"
          />
          <button
            type="submit"
            disabled={isSavingMp || !isMaster}
            className="inline-flex items-center gap-2 rounded-2xl border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-3 text-sm font-black text-[var(--color-primary)] hover:bg-[var(--color-hover)] disabled:opacity-60"
          >
            {isSavingMp ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            {isMaster ? (mpConfigured ? "Alterar senha mestre" : "Definir senha mestre") : "Somente master pode configurar"}
          </button>
        </form>
      </section>

      <section className="rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
        <h2 className="text-lg font-black text-[var(--color-text)]">Regras ativas do bloco</h2>
        <div className="mt-3 space-y-2">
          {(rules?.default_roles ?? []).map((roleCode) => (
            <p key={roleCode} className="rounded-xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
              Papel padrão: <strong className="text-[var(--color-text)]">{roleCode}</strong>
            </p>
          ))}
          <p className="rounded-xl bg-[var(--color-bg-soft)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
            Sessão expira em: <strong className="text-[var(--color-text)]">{rules?.session_duration_minutes ?? "-"} minutos</strong>.
          </p>
        </div>
      </section>
    </div>
  )
}

function LoginField({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  autoComplete,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
  autoComplete?: string
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div className="space-y-1.5">
      <label className="block text-[10px] font-black tracking-widest uppercase" style={{ color: "rgba(248,250,252,0.42)" }}>
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all duration-200"
        style={{
          background: "rgba(255,255,255,0.07)",
          border: `1px solid ${focused ? "rgba(16,185,129,0.65)" : "rgba(255,255,255,0.1)"}`,
          color: "#f8fafc",
          boxShadow: focused ? "0 0 0 3px rgba(16,185,129,0.13)" : "none",
          caretColor: "#10b981",
        }}
      />
    </div>
  )
}

function Input({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <label className="space-y-1">
      <span className="text-xs font-bold uppercase tracking-wide text-[var(--color-text-muted)]">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-2xl border border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] px-4 py-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)]"
      />
    </label>
  )
}

function MetricCard({ label, value, helper, tone = "normal" }: { label: string; value: string; helper: string; tone?: "normal" | "warning" | "success" }) {
  const toneClass = tone === "success"
    ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
    : tone === "warning"
      ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
      : "border-[var(--color-border-soft)] bg-[var(--color-bg-soft)] text-[var(--color-text)]"

  return (
    <div className={`rounded-3xl border p-4 ${toneClass}`}>
      <p className="text-xs font-black uppercase tracking-wide opacity-80">{label}</p>
      <p className="mt-2 text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs opacity-80">{helper}</p>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "approved"
    ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
    : status === "rejected"
      ? "border-red-400/40 bg-red-500/10 text-red-100"
      : "border-amber-400/40 bg-amber-500/10 text-amber-100"
  return <span className={`rounded-full border px-2 py-1 text-xs font-black ${tone}`}>{status.toUpperCase()}</span>
}

function NoticeBox({ notice }: { notice: { type: "success" | "error"; message: string } }) {
  const style = notice.type === "success"
    ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
    : "border-red-400/40 bg-red-500/10 text-red-100"
  const Icon = notice.type === "success" ? CheckCircle2 : AlertTriangle

  return (
    <section className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${style}`}>
      <span className="inline-flex items-center gap-2">
        <Icon className="h-4 w-4" />
        {notice.message}
      </span>
    </section>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded-[2rem] border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-5 shadow-xl shadow-[var(--color-card-shadow)]">
      <h2 className="text-lg font-black text-[var(--color-text)]">{title}</h2>
      <div className="space-y-2">{children}</div>
    </section>
  )
}



