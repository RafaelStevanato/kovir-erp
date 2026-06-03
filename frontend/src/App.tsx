import { Suspense, lazy, useEffect, useState } from "react"

import { getAuthSession, getAuthToken, subscribeAuthSessionChange } from "./config/authSession"
import { DashboardPage } from "./pages/DashboardPage"
import { getLazyView } from "./routes/lazyViews"

const SecurityPage = getLazyView("security")
const OnboardingPage = lazy(() =>
  import("./pages/OnboardingPage").then((module) => ({ default: module.OnboardingPage })),
)
const KovirAboutPage = lazy(() =>
  import("./pages/KovirAboutPage").then((module) => ({ default: module.KovirAboutPage })),
)
const StvnSoftwarePage = lazy(() =>
  import("./pages/StvnSoftwarePage").then((module) => ({ default: module.StvnSoftwarePage })),
)

function PublicPageFallback() {
  return <div className="min-h-screen bg-[#020617]" />
}

function checkAuth() {
  const session = getAuthSession()
  return Boolean(session && getAuthToken())
}

function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title
  }, [title])
}

function AuthenticatedApp() {
  const [hasValidSession, setHasValidSession] = useState(checkAuth)

  useDocumentTitle("Kovir ERP")

  useEffect(() => {
    const unsubscribe = subscribeAuthSessionChange(() => {
      setHasValidSession(checkAuth())
    })

    const interval = window.setInterval(() => {
      if (!getAuthToken()) setHasValidSession(false)
    }, 15_000)

    return () => {
      unsubscribe()
      window.clearInterval(interval)
    }
  }, [])

  if (!hasValidSession) {
    return (
      <Suspense fallback={<div className="min-h-screen bg-[var(--color-bg)]" />}>
        <SecurityPage />
      </Suspense>
    )
  }

  return <DashboardPage />
}

function OnboardingRoute() {
  useDocumentTitle("Onboarding Kovir ERP | STVN Software")

  return (
    <Suspense fallback={<PublicPageFallback />}>
      <OnboardingPage />
    </Suspense>
  )
}

function KovirAboutRoute() {
  return (
    <Suspense fallback={<PublicPageFallback />}>
      <KovirAboutPage />
    </Suspense>
  )
}

function App() {
  const normalizedPath = window.location.pathname.replace(/\/+$/, "") || "/"
  const hostname = window.location.hostname.toLowerCase()
  const isOnboardingPath = normalizedPath === "/onboarding"
  const isKovirAboutPath = normalizedPath === "/sobre" || normalizedPath === "/erpkovir"
  const isStvnHost = hostname === "stvnsoftware.com.br" || hostname === "www.stvnsoftware.com.br"
  const isStvnPreviewPath = normalizedPath === "/stvn" || normalizedPath === "/stvnsoftware"

  if (isKovirAboutPath) {
    return <KovirAboutRoute />
  }

  if (isStvnHost || isStvnPreviewPath) {
    return (
      <Suspense fallback={<PublicPageFallback />}>
        <StvnSoftwarePage />
      </Suspense>
    )
  }

  if (isOnboardingPath) {
    return <OnboardingRoute />
  }

  return <AuthenticatedApp />
}

export default App
