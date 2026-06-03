import { Search, X } from "lucide-react"
import { useMemo, useState } from "react"

export type SearchableSelectOption = {
  value: string
  label: string
  description?: string
  keywords?: string[]
}

type SearchableSelectProps = {
  value: string
  options: SearchableSelectOption[]
  placeholder: string
  searchPlaceholder?: string
  emptyMessage?: string
  disabled?: boolean
  required?: boolean
  maxResults?: number
  isLoading?: boolean
  errorMessage?: string | null
  onSearchQueryChange?: (query: string) => void
  onRetry?: () => void
  onChange: (value: string) => void
}

function normalizeSearchText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
}

export function SearchableSelect({
  value,
  options,
  placeholder,
  searchPlaceholder = "Digite para pesquisar...",
  emptyMessage = "Nenhum resultado encontrado.",
  disabled = false,
  required = false,
  maxResults = 8,
  isLoading = false,
  errorMessage = null,
  onSearchQueryChange,
  onRetry,
  onChange,
}: SearchableSelectProps) {
  const [query, setQuery] = useState("")
  const [isOpen, setIsOpen] = useState(false)

  const selectedOption = useMemo(
    () => options.find((option) => option.value === value) ?? null,
    [options, value],
  )

  const filteredOptions = useMemo(() => {
    const normalizedQuery = normalizeSearchText(query)

    if (!normalizedQuery) {
      return options.slice(0, maxResults)
    }

    return options
      .filter((option) => {
        const searchableText = normalizeSearchText(
          [
            option.label,
            option.description,
            option.value,
            ...(option.keywords ?? []),
          ]
            .filter(Boolean)
            .join(" "),
        )

        return searchableText.includes(normalizedQuery)
      })
      .slice(0, maxResults)
  }, [maxResults, options, query])

  const inputValue = isOpen ? query : selectedOption?.label ?? ""
  const inputPaddingRight = selectedOption ? "3rem" : "1rem"

  function handleSelect(option: SearchableSelectOption) {
    onChange(option.value)
    onSearchQueryChange?.("")
    setQuery("")
    setIsOpen(false)
  }

  function handleClear() {
    onChange("")
    onSearchQueryChange?.("")
    setQuery("")
    setIsOpen(false)
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-weak)]" />
        <input
          aria-required={required}
          disabled={disabled}
          value={inputValue}
          onBlur={() => {
            window.setTimeout(() => {
              setIsOpen(false)
              setQuery("")
            }, 120)
          }}
          onChange={(event) => {
            const nextQuery = event.target.value
            setQuery(nextQuery)
            onSearchQueryChange?.(nextQuery)
            setIsOpen(true)
          }}
          onFocus={() => {
            setQuery("")
            onSearchQueryChange?.("")
            setIsOpen(true)
          }}
          placeholder={selectedOption ? searchPlaceholder : placeholder}
          className="field-input"
          style={{ paddingLeft: "3rem", paddingRight: inputPaddingRight }}
          autoComplete="off"
        />
        {selectedOption ? (
          <button
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onClick={handleClear}
            disabled={disabled}
            className="absolute right-3 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Limpar seleção"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {isOpen && !disabled ? (
        <div className="absolute z-30 mt-2 max-h-72 w-full overflow-auto rounded-3xl border border-[var(--color-border-soft)] bg-[var(--color-surface)] p-2 shadow-2xl shadow-[var(--color-card-shadow)]">
          {isLoading ? (
            <div className="rounded-2xl px-4 py-3 text-sm text-[var(--color-text-muted)]">
              Pesquisando...
            </div>
          ) : errorMessage ? (
            <div className="space-y-2 rounded-2xl px-4 py-3 text-sm text-red-500">
              <p>{errorMessage}</p>
              {onRetry ? (
                <button type="button" className="text-xs font-black underline" onMouseDown={(event) => event.preventDefault()} onClick={onRetry}>
                  Tentar novamente
                </button>
              ) : null}
            </div>
          ) : filteredOptions.length === 0 ? (
            <div className="rounded-2xl px-4 py-3 text-sm text-[var(--color-text-muted)]">
              {emptyMessage}
            </div>
          ) : (
            filteredOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => handleSelect(option)}
                className={`w-full rounded-2xl px-4 py-3 text-left transition-all hover:bg-[var(--color-hover)] ${
                  option.value === value
                    ? "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
                    : "text-[var(--color-text)]"
                }`}
              >
                <span className="block text-sm font-bold">{option.label}</span>
                {option.description ? (
                  <span className="mt-1 block text-xs text-[var(--color-text-muted)]">
                    {option.description}
                  </span>
                ) : null}
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
