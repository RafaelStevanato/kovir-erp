import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "dark" | "light";

const STORAGE_KEY = "kovir-theme";
const LEGACY_STORAGE_KEY = ["flu", "xor-theme"].join("");

function getInitialTheme(): Theme {
  const storedTheme = localStorage.getItem(STORAGE_KEY);

  if (storedTheme === "dark" || storedTheme === "light") {
    return storedTheme;
  }

  const legacyTheme = localStorage.getItem(LEGACY_STORAGE_KEY);
  if (legacyTheme === "dark" || legacyTheme === "light") {
    localStorage.setItem(STORAGE_KEY, legacyTheme);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    return legacyTheme;
  }

  return "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  }, [theme]);

  const isDark = theme === "dark";

  function toggleTheme() {
    setTheme((currentTheme) => (currentTheme === "dark" ? "light" : "dark"));
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="flex items-center gap-2 rounded-full border border-[var(--color-primary-border)] bg-[var(--color-primary-soft)] px-4 py-2 text-sm text-[var(--color-primary)] transition hover:border-[var(--color-primary)]"
      aria-label="Alternar tema"
    >
      {isDark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      {isDark ? "Modo escuro" : "Modo claro"}
    </button>
  );
}
