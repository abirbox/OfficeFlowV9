import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/axios';

/**
 * SiteThemeContext — fetches the admin-editable colour palette from
 * `/api/settings/theme` and pushes each token to `document.documentElement`
 * as a CSS variable (e.g. `--brand-primary: #4F46E5`). Any component that
 * uses `bg-[var(--brand-primary)]` or inline `style={{ backgroundColor: 'var(--brand-primary)' }}`
 * automatically re-renders when an admin saves a new colour.
 *
 * Public GET so even the login screen renders with the current brand colour.
 * PUT / reset are super_admin / admin only (enforced server-side).
 */

const SiteThemeContext = createContext({
  colors: {},
  defaults: {},
  loaded: false,
  refresh: async () => {},
  save: async () => {},
  reset: async () => {},
});

const cssVarName = (token) => `--${token.replace(/_/g, '-')}`;

const applyToRoot = (colors) => {
  const root = document.documentElement;
  Object.entries(colors || {}).forEach(([k, v]) => {
    if (typeof v === 'string' && v) root.style.setProperty(cssVarName(k), v);
  });
};

export function SiteThemeProvider({ children }) {
  const [colors, setColors] = useState({});
  const [defaults, setDefaults] = useState({});
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/settings/theme');
      setColors(data.values || {});
      setDefaults(data.defaults || {});
      applyToRoot(data.values || {});
    } catch (_) {
      // Silent fallback — CSS defaults in index.css keep the site usable.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = useCallback(async (nextValues) => {
    const { data } = await api.put('/settings/theme', { values: nextValues });
    setColors(data.values || {});
    setDefaults(data.defaults || {});
    applyToRoot(data.values || {});
    return data;
  }, []);

  const reset = useCallback(async () => {
    const { data } = await api.post('/settings/theme/reset');
    setColors(data.values || {});
    setDefaults(data.defaults || {});
    applyToRoot(data.values || {});
    return data;
  }, []);

  const value = useMemo(
    () => ({ colors, defaults, loaded, refresh: load, save, reset }),
    [colors, defaults, loaded, load, save, reset],
  );

  return <SiteThemeContext.Provider value={value}>{children}</SiteThemeContext.Provider>;
}

export const useSiteTheme = () => useContext(SiteThemeContext);
