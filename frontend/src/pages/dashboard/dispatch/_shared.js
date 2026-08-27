// Shared helpers + hooks for dispatch pages
import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';

export function useList(url, params = {}) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let dead = false;
    setLoading(true);
    api.get(url, { params }).then(({ data }) => {
      if (!dead) setData(Array.isArray(data) ? data : data.items || []);
    }).catch(() => !dead && setData([]))
      .finally(() => !dead && setLoading(false));
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, JSON.stringify(params), reload]);
  return { data, loading, refetch: () => setReload((x) => x + 1) };
}

// Colours use CSS custom properties defined in :root (see index.css) so the
// Settings > Colours panel can change every badge across the app on save.
export const STATUS_BADGE = {
  active:     'bg-[var(--status-clocked-in-bg)] text-[var(--status-clocked-in-fg)] border',
  inactive:   'bg-[var(--status-not-started-bg)] text-[var(--status-not-started-fg)] border',
  suspended:  'bg-[var(--conf-pending-bg)] text-[var(--conf-pending-fg)] border',
  terminated: 'bg-[var(--conf-declined-bg)] text-[var(--conf-declined-fg)] border',
  on_leave:   'bg-[var(--status-clocked-out-bg)] text-[var(--status-clocked-out-fg)] border',
};

export const CONFIRM_BADGE = {
  Confirmed:       'bg-[var(--conf-confirmed-bg)] text-[var(--conf-confirmed-fg)] border-[var(--conf-confirmed-bg)]',
  Pending:         'bg-[var(--conf-pending-bg)] text-[var(--conf-pending-fg)] border-[var(--conf-pending-bg)]',
  Declined:        'bg-[var(--conf-declined-bg)] text-[var(--conf-declined-fg)] border-[var(--conf-declined-bg)]',
  'No Response':   'bg-[var(--conf-no-response-bg)] text-[var(--conf-no-response-fg)] border-[var(--conf-no-response-bg)]',
  'Not Confirmed': 'bg-[var(--conf-not-confirmed-bg)] text-[var(--conf-not-confirmed-fg)] border-[var(--conf-not-confirmed-bg)]',
};


/**
 * Uniform post-pin display: "VENDOR_CODE # PIN". Falls back to "# PIN" when
 * the vendor has no code, or to null when there is no pin at all. Prefers
 * the server-supplied `post_pin_display` when present so the same string
 * used by CSV/PDF exports appears on-screen.
 */
export function formatPin(row) {
  if (!row) return null;
  if (row.post_pin_display) return row.post_pin_display;
  const pin = row.post_pin;
  if (!pin) return null;
  const code = (row.vendor_code || '').trim();
  return code ? `${code} # ${pin}` : `# ${pin}`;
}
