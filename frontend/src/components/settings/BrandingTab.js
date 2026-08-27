import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/sonner';
import { Building2, Image as ImageIcon, Globe, DollarSign, Save } from 'lucide-react';
import { useAppSettings } from '@/contexts/AppSettingsContext';

const BrandingTab = () => {
  const { settings, refresh } = useAppSettings();
  const [form, setForm] = useState(null);
  const [currencies, setCurrencies] = useState([]);
  const [timezones, setTimezones] = useState([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingFav, setUploadingFav] = useState(false);

  useEffect(() => { if (settings) setForm({ ...settings }); }, [settings]);

  useEffect(() => {
    (async () => {
      try {
        const [c, t] = await Promise.all([
          api.get('/settings/currencies'),
          api.get('/settings/timezones'),
        ]);
        setCurrencies(c.data);
        setTimezones(t.data);
      } catch { /* silent */ }
    })();
  }, []);

  if (!form) return <div className="p-6 text-sm text-[#64748B]">Loading…</div>;

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        brand_name: form.brand_name,
        site_title: form.site_title,
        company_address: form.company_address,
        support_email: form.support_email,
        contact_phone: form.contact_phone,
        footer_text: form.footer_text,
        login_hero_title: form.login_hero_title,
        login_hero_subtitle: form.login_hero_subtitle,
        login_welcome_title: form.login_welcome_title,
        login_welcome_subtitle: form.login_welcome_subtitle,
        not_found_lottie_enabled: !!form.not_found_lottie_enabled,
        not_found_lottie_url: form.not_found_lottie_url || null,
        currency: form.currency,
        currency_symbol: form.currency_symbol,
        timezone: form.timezone,
      };
      await api.put('/settings', payload);
      await refresh();
      toast.success('Settings saved. Changes visible everywhere.');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post('/settings/logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      await refresh();
      toast.success('Logo uploaded');
    } catch (err) {
      toast.error('Failed to upload logo');
    } finally {
      setUploading(false);
    }
  };

  const uploadFavicon = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFav(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await api.post('/settings/favicon', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      await refresh();
      toast.success('Icon uploaded');
    } catch (err) {
      toast.error('Failed to upload icon');
    } finally {
      setUploadingFav(false);
    }
  };

  const onCurrencyChange = (code) => {
    const c = currencies.find((x) => x.code === code);
    setForm({ ...form, currency: code, currency_symbol: c?.symbol || form.currency_symbol });
  };

  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="branding-tab-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="w-5 h-5" /> Branding & Localization
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Brand identity */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Brand Identity</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Website / App Name</Label>
              <Input
                value={form.brand_name || ''}
                onChange={(e) => setForm({ ...form, brand_name: e.target.value })}
                placeholder="OfficeFlow"
                data-testid="settings-brand-name"
              />
            </div>
            <div className="space-y-2">
              <Label>Browser Tab Title</Label>
              <Input
                value={form.site_title || ''}
                onChange={(e) => setForm({ ...form, site_title: e.target.value })}
                placeholder="Defaults to Website Name"
                data-testid="settings-site-title"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><ImageIcon className="w-4 h-4" /> Logo</Label>
              <div className="flex items-center gap-3">
                {form.brand_logo_url && (
                  <img src={form.brand_logo_url} alt="logo" className="w-10 h-10 rounded object-contain border border-[#E2E8F0]" />
                )}
                <label className="cursor-pointer">
                  <input type="file" accept="image/*" onChange={uploadLogo} className="hidden" data-testid="settings-logo-input" />
                  <span className={`inline-flex items-center px-3 py-2 rounded-lg text-sm border ${uploading ? 'opacity-60' : 'hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]'} border-[#E2E8F0] dark:border-[#27272A]`}>
                    {uploading ? 'Uploading…' : (form.brand_logo_url ? 'Replace Logo' : 'Upload Logo')}
                  </span>
                </label>
              </div>
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><ImageIcon className="w-4 h-4" /> Favicon / Icon</Label>
              <div className="flex items-center gap-3">
                {form.favicon_url && (
                  <img src={form.favicon_url} alt="favicon" className="w-10 h-10 rounded object-contain border border-[#E2E8F0]" />
                )}
                <label className="cursor-pointer">
                  <input type="file" accept="image/*" onChange={uploadFavicon} className="hidden" data-testid="settings-favicon-input" />
                  <span className={`inline-flex items-center px-3 py-2 rounded-lg text-sm border ${uploadingFav ? 'opacity-60' : 'hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]'} border-[#E2E8F0] dark:border-[#27272A]`}>
                    {uploadingFav ? 'Uploading…' : (form.favicon_url ? 'Replace Icon' : 'Upload Icon')}
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Site information */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Company Information</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Support Email</Label>
              <Input value={form.support_email || ''} onChange={(e) => setForm({ ...form, support_email: e.target.value })} placeholder="support@company.com" data-testid="settings-support-email" />
            </div>
            <div className="space-y-2">
              <Label>Contact Phone</Label>
              <Input value={form.contact_phone || ''} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} placeholder="+8801XXXXXXXXX" data-testid="settings-contact-phone" />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Company Address</Label>
            <Textarea value={form.company_address || ''} onChange={(e) => setForm({ ...form, company_address: e.target.value })} rows={2} placeholder="Street, City, Country" data-testid="settings-company-address" />
          </div>
          <div className="space-y-2">
            <Label>Footer Text</Label>
            <Input value={form.footer_text || ''} onChange={(e) => setForm({ ...form, footer_text: e.target.value })} placeholder="© 2026 Your Company. All rights reserved." data-testid="settings-footer-text" />
          </div>
        </div>

        {/* Login page content */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Login Page Content</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Welcome Title</Label>
              <Input
                value={form.login_welcome_title || ''}
                onChange={(e) => setForm({ ...form, login_welcome_title: e.target.value })}
                placeholder="Welcome Back"
                data-testid="settings-welcome-title"
              />
            </div>
            <div className="space-y-2">
              <Label>Welcome Subtitle</Label>
              <Input
                value={form.login_welcome_subtitle || ''}
                onChange={(e) => setForm({ ...form, login_welcome_subtitle: e.target.value })}
                placeholder="Sign in to your account"
                data-testid="settings-welcome-subtitle"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Hero Title (large right-side text)</Label>
            <Input
              value={form.login_hero_title || ''}
              onChange={(e) => setForm({ ...form, login_hero_title: e.target.value })}
              placeholder="OfficeFlow"
              data-testid="settings-hero-title"
            />
          </div>
          <div className="space-y-2">
            <Label>Hero Subtitle / Tagline</Label>
            <Textarea
              value={form.login_hero_subtitle || ''}
              onChange={(e) => setForm({ ...form, login_hero_subtitle: e.target.value })}
              placeholder="Modern Office Management, HR, Attendance, GPS Tracking & Task Management Platform"
              rows={3}
              data-testid="settings-hero-subtitle"
            />
          </div>
        </div>

        {/* 404 Page */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">
            404 Page
          </h3>

          <div className="rounded-lg border border-[#E2E8F0] dark:border-[#27272A] p-4 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label className="text-sm font-medium">Lottie Animation</Label>
                <p className="text-xs text-[#64748B] mt-1">
                  Show a Lottie animation when someone opens a page that does not exist.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  setForm({
                    ...form,
                    not_found_lottie_enabled: !form.not_found_lottie_enabled,
                  })
                }
                className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
                  form.not_found_lottie_enabled
                    ? 'bg-[#4F46E5]'
                    : 'bg-[#CBD5E1] dark:bg-[#3F3F46]'
                }`}
                aria-label="Toggle 404 Lottie animation"
                aria-pressed={!!form.not_found_lottie_enabled}
                data-testid="settings-404-lottie-toggle"
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 mt-0.5 rounded-full bg-white shadow-sm transform transition-transform ${
                    form.not_found_lottie_enabled ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>

            <div className="space-y-2">
              <Label>Lottie JSON URL</Label>
              <Input
                value={form.not_found_lottie_url || ''}
                onChange={(e) =>
                  setForm({
                    ...form,
                    not_found_lottie_url: e.target.value,
                  })
                }
                placeholder="https://example.com/404-animation.json"
                disabled={!form.not_found_lottie_enabled}
                data-testid="settings-404-lottie-url"
              />
              <p className="text-xs text-[#64748B]">
                Paste the direct URL to a Lottie JSON animation file.
              </p>
            </div>
          </div>
        </div>

        {/* Localization */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] uppercase tracking-wide">Localization</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><DollarSign className="w-4 h-4" /> Currency</Label>
              <Select value={form.currency} onValueChange={onCurrencyChange}>
                <SelectTrigger data-testid="settings-currency"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {currencies.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.symbol} · {c.code} — {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Currency Symbol</Label>
              <Input
                value={form.currency_symbol || ''}
                onChange={(e) => setForm({ ...form, currency_symbol: e.target.value })}
                placeholder="৳"
              />
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2"><Globe className="w-4 h-4" /> Timezone</Label>
              <Select value={form.timezone} onValueChange={(v) => setForm({ ...form, timezone: v })}>
                <SelectTrigger data-testid="settings-timezone"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {timezones.map((t) => (
                    <SelectItem key={t.code} value={t.code}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button onClick={save} disabled={saving} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-branding-button">
            <Save className="w-4 h-4 mr-2" /> {saving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default BrandingTab;
