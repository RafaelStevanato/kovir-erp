import { useCallback, useEffect, useMemo, useState } from "react"

import {
  getActiveCompanyId,
  getCompanyDisplayName,
  setActiveCompanyId,
  subscribeActiveCompanyChange,
} from "./activeCompany"
import { getAuthSession } from "./authSession"
import { getCompany } from "../features/company/companyApi"
import type { Company } from "../features/company/types"

type UseActiveCompanyOptions = {
  autoLoad?: boolean
}

export type ActiveCompanyState = {
  companyId: string
  companies: Company[]
  activeCompany: Company | null
  activeCompanyName: string
  isCompanyLoading: boolean
  isCompanyResolved: boolean
  companyError: string | null
  reloadCompanies: () => Promise<string>
  selectCompany: (companyId: string) => void
}

export function useActiveCompany(options: UseActiveCompanyOptions = {}): ActiveCompanyState {
  const { autoLoad = true } = options
  const [companyId, setCompanyIdState] = useState(() => getActiveCompanyId())
  const [companies, setCompanies] = useState<Company[]>([])
  const [isCompanyLoading, setIsCompanyLoading] = useState(false)
  const [isCompanyResolved, setIsCompanyResolved] = useState(false)
  const [companyError, setCompanyError] = useState<string | null>(null)

  const activeCompany = useMemo(
    () => companies.find((company) => company.id === companyId) ?? null,
    [companies, companyId],
  )

  const activeCompanyName = useMemo(
    () => getCompanyDisplayName(activeCompany),
    [activeCompany],
  )

  const selectCompany = useCallback((nextCompanyId: string) => {
    const sessionCompanyId = getAuthSession()?.companyId ?? ""
    const lockedCompanyId = sessionCompanyId || nextCompanyId
    setActiveCompanyId(lockedCompanyId)
    setCompanyIdState(lockedCompanyId)
  }, [])

  const reloadCompanies = useCallback(async () => {
    setIsCompanyLoading(true)
    setCompanyError(null)
    try {
      const sessionCompanyId = getAuthSession()?.companyId ?? ""
      if (!sessionCompanyId) {
        setCompanies([])
        setActiveCompanyId("")
        setCompanyIdState("")
        setIsCompanyResolved(false)
        return ""
      }

      const response = await getCompany(sessionCompanyId)
      setCompanies([response.data])
      setActiveCompanyId(sessionCompanyId)
      setCompanyIdState(sessionCompanyId)
      setIsCompanyResolved(true)
      return sessionCompanyId
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao carregar empresas."
      setCompanies([])
      setCompanyIdState("")
      setActiveCompanyId("")
      setCompanyError(message)
      setIsCompanyResolved(false)
      throw error
    } finally {
      setIsCompanyLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!autoLoad) return
    void reloadCompanies()
  }, [autoLoad, reloadCompanies])

  useEffect(() => {
    return subscribeActiveCompanyChange((nextCompanyId) => {
      setCompanyIdState(nextCompanyId)
      setIsCompanyResolved((current) => {
        if (!nextCompanyId) return false
        if (companies.length === 0) return current
        return companies.some((company) => company.id === nextCompanyId)
      })
    })
  }, [companies])

  return {
    companyId,
    companies,
    activeCompany,
    activeCompanyName,
    isCompanyLoading,
    isCompanyResolved,
    companyError,
    reloadCompanies,
    selectCompany,
  }
}
