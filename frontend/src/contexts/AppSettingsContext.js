import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/axios';

const AppSettingsContext = createContext({
  settings: null,
  loading: true,
  refresh: () => {},
});

const DEFAULTS = {
  brand_name: 'OfficeFlow',
  brand_logo_url: null,
  favicon_url: null,
  site_title: null,
  company_address: null,
  support_email: null,
  contact_phone: null,
  footer_text: null,
  login_hero_title: 'OfficeFlow',
  login_hero_subtitle: 'Modern Office Management, HR, Attendance, GPS Tracking & Task Management Platform',
  login_welcome_title: 'Welcome Back',
  login_welcome_subtitle: 'Sign in to your OfficeFlow account',
  currency: 'BDT',
  currency_symbol: '৳',
  timezone: 'Asia/Dhaka',
  tz_offset_hours: 6.0,
  not_found_lottie_enabled: true,
  not_found_lottie_url: null,
};

const applyBranding = (s) => {
  if (!s) return;
  const title = s.site_title || s.brand_name || 'OfficeFlow';
  if (title) document.title = title;
  if (s.favicon_url) {
    let link = document.querySelector("link[rel~='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = s.favicon_url;
  }
};

export const AppSettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(DEFAULTS);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get('/settings/public');
      setSettings({ ...DEFAULTS, ...data });
      applyBranding({ ...DEFAULTS, ...data });
    } catch {
      setSettings(DEFAULTS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <AppSettingsContext.Provider value={{ settings, loading, refresh, setSettings }}>
      {children}
    </AppSettingsContext.Provider>
  );
};

export const useAppSettings = () => useContext(AppSettingsContext);

export const formatMoney = (amount, symbol = '৳') => {
  const n = Number(amount || 0);
  return `${symbol} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
