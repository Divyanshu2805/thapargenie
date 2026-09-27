import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

// Must match the key read by public/theme-init.js.
export const THEME_STORAGE_KEY = 'thapargenie-theme';
// Only light and dark are user-choosable; the system preference is used once, to seed a
// first-time visitor's theme, then never revisited (no live "system" mode to track).
const THEMES = new Set(['light', 'dark']);

const ThemeContext = createContext(null);

function systemPrefersDark() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function readStoredTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (THEMES.has(stored)) return stored;
  } catch {
    // Storage may be blocked; fall back to the system preference below.
  }
  return systemPrefersDark() ? 'dark' : 'light';
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readStoredTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    root.style.colorScheme = theme;
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (!THEMES.has(next)) return;
    setThemeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage may be blocked; the choice still applies for this visit.
    }
  }, []);

  // resolvedTheme kept for callers that predate the system option's removal; it now always
  // matches theme, since there's no longer an unresolved "system" state.
  const value = useMemo(() => ({ theme, resolvedTheme: theme, setTheme }), [theme, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used inside ThemeProvider.');
  return context;
}
