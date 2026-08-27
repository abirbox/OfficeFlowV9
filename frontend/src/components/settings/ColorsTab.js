import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { toast } from '@/components/ui/sonner';
import { RotateCcw, Save } from 'lucide-react';
import { useSiteTheme } from '@/contexts/SiteThemeContext';

/**
 * Groups of colour tokens shown in the Settings > Colours tab. Each token
 * pairs with a friendly label + short hint so admins understand where in
 * the UI each colour applies.
 */
const GROUPS = [
  {
    title: 'Brand',
    hint: 'Primary buttons, links, focused inputs.',
    tokens: [
      { key: 'brand_primary',        label: 'Brand primary' },
      { key: 'brand_primary_hover',  label: 'Brand primary hover' },
      { key: 'brand_primary_fg',     label: 'Brand primary text' },
    ],
  },
  {
    title: 'Tables & tools',
    hint: 'Column headers, delete buttons, post pins.',
    tokens: [
      { key: 'table_header_bg', label: 'Table header background' },
      { key: 'table_header_fg', label: 'Table header text' },
      { key: 'danger',          label: 'Danger / delete' },
      { key: 'success',         label: 'Success' },
    ],
  },
  {
    title: 'Shift status badges',
    hint: 'Not Started · Clocked In · Clocked Out chips.',
    tokens: [
      { key: 'status_not_started_bg', label: 'Not Started · background' },
      { key: 'status_not_started_fg', label: 'Not Started · text' },
      { key: 'status_clocked_in_bg',  label: 'Clocked In · background' },
      { key: 'status_clocked_in_fg',  label: 'Clocked In · text' },
      { key: 'status_clocked_out_bg', label: 'Clocked Out · background' },
      { key: 'status_clocked_out_fg', label: 'Clocked Out · text' },
    ],
  },
  {
    title: 'Confirmation badges',
    hint: 'Confirmed · Pending · No Response · Declined · Not Confirmed.',
    tokens: [
      { key: 'conf_confirmed_bg',     label: 'Confirmed · background' },
      { key: 'conf_confirmed_fg',     label: 'Confirmed · text' },
      { key: 'conf_pending_bg',       label: 'Pending · background' },
      { key: 'conf_pending_fg',       label: 'Pending · text' },
      { key: 'conf_no_response_bg',   label: 'No Response · background' },
      { key: 'conf_no_response_fg',   label: 'No Response · text' },
      { key: 'conf_declined_bg',      label: 'Declined · background' },
      { key: 'conf_declined_fg',      label: 'Declined · text' },
      { key: 'conf_not_confirmed_bg', label: 'Not Confirmed · background' },
      { key: 'conf_not_confirmed_fg', label: 'Not Confirmed · text' },
    ],
  },
];

/** One row: colour swatch + text hex input, both editing the same value. */
const ColorRow = ({ token, label, value, onChange }) => (
  <div className="flex items-center gap-3">
    <input
      type="color"
      value={value || '#000000'}
      onChange={(e) => onChange(e.target.value.toUpperCase())}
      className="h-9 w-12 rounded border border-[#E2E8F0] dark:border-[#27272A] cursor-pointer bg-transparent"
      data-testid={`color-swatch-${token}`}
      aria-label={`${label} colour picker`}
    />
    <Input
      value={value || ''}
      onChange={(e) => onChange(e.target.value.toUpperCase())}
      maxLength={7}
      className="w-28 font-mono text-xs h-9"
      data-testid={`color-input-${token}`}
      spellCheck={false}
    />
    <Label className="text-xs flex-1">{label}</Label>
  </div>
);

const ColorsTab = () => {
  const { colors, defaults, loaded, save, reset } = useSiteTheme();
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => { setDraft(colors); }, [colors, loaded]);

  const dirty = useMemo(() => Object.keys(defaults).some((k) => (draft[k] || '') !== (colors[k] || '')), [draft, colors, defaults]);

  const setToken = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const onSave = async () => {
    // Only send tokens that actually changed to keep the audit trail tight.
    const changed = Object.fromEntries(
      Object.keys(defaults).filter((k) => (draft[k] || '') !== (colors[k] || ''))
        .map((k) => [k, draft[k] || defaults[k]]),
    );
    if (!Object.keys(changed).length) { toast.info('No changes to save'); return; }
    setBusy(true);
    try {
      await save(changed);
      toast.success('Site colours updated for everyone');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not save site colours');
    } finally { setBusy(false); }
  };

  const onReset = async () => {
    if (!window.confirm('Reset every site colour back to defaults?')) return;
    setBusy(true);
    try {
      await reset();
      toast.success('Site colours restored to defaults');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Reset failed');
    } finally { setBusy(false); }
  };

  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="colors-tab">
      <CardHeader className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
        <div className="min-w-0">
          <CardTitle>Site Colours</CardTitle>
          <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1 max-w-2xl">
            Everything you change here applies to every user immediately after saving — brand buttons, table headers, and every status / confirmation badge in the app.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap shrink-0">
          <Button variant="outline" size="sm" onClick={onReset} disabled={busy} data-testid="colors-reset-btn">
            <RotateCcw className="w-4 h-4 mr-2" /> Reset to defaults
          </Button>
          <Button
            onClick={onSave}
            disabled={!dirty || busy}
            size="sm"
            className="bg-[var(--brand-primary)] text-[var(--brand-primary-fg)] hover:bg-[var(--brand-primary-hover)]"
            data-testid="colors-save-btn"
          >
            <Save className="w-4 h-4 mr-2" /> {busy ? 'Saving…' : 'Save colours'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-8">
        {GROUPS.map((g) => (
          <section key={g.title} data-testid={`colors-group-${g.title.toLowerCase().replace(/\W+/g, '-')}`}>
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{g.title}</h3>
              <p className="text-xs text-[#64748B]">{g.hint}</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {g.tokens.map((t) => (
                <ColorRow
                  key={t.key}
                  token={t.key}
                  label={t.label}
                  value={draft[t.key] || defaults[t.key] || ''}
                  onChange={(v) => setToken(t.key, v)}
                />
              ))}
            </div>
          </section>
        ))}

        {/* Live preview so admins see the effect without saving. */}
        <section data-testid="colors-preview">
          <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">Live preview</h3>
          <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className="px-3 py-1 rounded-md text-xs font-semibold"
                style={{ background: draft.brand_primary, color: draft.brand_primary_fg }}
              >Primary button</span>
              <span
                className="px-3 py-1 rounded-md text-xs font-semibold"
                style={{ background: draft.table_header_bg, color: draft.table_header_fg }}
              >Table header</span>
              <span className="px-3 py-1 rounded-md text-xs font-semibold" style={{ background: draft.danger, color: '#fff' }}>Danger</span>
              <span className="px-3 py-1 rounded-md text-xs font-semibold" style={{ background: draft.success, color: '#fff' }}>Success</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.status_not_started_bg, color: draft.status_not_started_fg }}>Not Started</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.status_clocked_in_bg, color: draft.status_clocked_in_fg }}>Clocked In</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.status_clocked_out_bg, color: draft.status_clocked_out_fg }}>Clocked Out</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.conf_confirmed_bg, color: draft.conf_confirmed_fg }}>Confirmed</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.conf_pending_bg, color: draft.conf_pending_fg }}>Pending</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.conf_no_response_bg, color: draft.conf_no_response_fg }}>No Response</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.conf_declined_bg, color: draft.conf_declined_fg }}>Declined</span>
              <span className="px-2 py-1 rounded-full text-xs font-semibold" style={{ background: draft.conf_not_confirmed_bg, color: draft.conf_not_confirmed_fg }}>Not Confirmed</span>
            </div>
          </div>
        </section>
      </CardContent>
    </Card>
  );
};

export default ColorsTab;
