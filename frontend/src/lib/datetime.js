/**
 * Centralized date/time helpers pinned to Asia/Dhaka (UTC+6).
 *
 * The entire app formats and derives "today" through these helpers so
 * users NEVER see a browser-local or UTC-based time, regardless of the
 * device timezone.
 */

export const APP_TZ = 'Asia/Dhaka';
export const APP_TZ_LABEL = 'BDT';

const toDate = (input) => {
  if (input == null || input === '') return null;
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input;
  const d = new Date(input);
  return isNaN(d.getTime()) ? null : d;
};

/** ISO date (YYYY-MM-DD) in Asia/Dhaka. Input defaults to now. */
export const dhakaDateIso = (input) => {
  const d = toDate(input) || new Date();
  // en-CA yields YYYY-MM-DD reliably.
  return d.toLocaleDateString('en-CA', { timeZone: APP_TZ });
};

/** Today's ISO date in Asia/Dhaka. */
export const todayIso = () => dhakaDateIso(new Date());

/** Human-friendly date, e.g. "27 Aug 2026". */
export const formatDate = (input) => {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleDateString('en-GB', {
    timeZone: APP_TZ, day: '2-digit', month: 'short', year: 'numeric',
  });
};

/** Time only (24h), e.g. "14:35". */
export const formatTime = (input, opts = {}) => {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleTimeString('en-GB', {
    timeZone: APP_TZ, hour: '2-digit', minute: '2-digit', hour12: false, ...opts,
  });
};

/** Full date + time in Asia/Dhaka, e.g. "27 Aug 2026, 14:35". */
export const formatDateTime = (input, { withZone = false } = {}) => {
  const d = toDate(input);
  if (!d) return '';
  const s = d.toLocaleString('en-GB', {
    timeZone: APP_TZ,
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
  return withZone ? `${s} ${APP_TZ_LABEL}` : s;
};

/** Long weekday + date, e.g. "Thursday, 27 August 2026". */
export const formatLongDate = (input) => {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleDateString('en-GB', {
    timeZone: APP_TZ, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
};

/** Month + year, e.g. "August 2026". */
export const formatMonth = (input) => {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleDateString('en-GB', {
    timeZone: APP_TZ, month: 'long', year: 'numeric',
  });
};

/**
 * Returns a Date-like `{ y, m, d, hh, mm, ss }` in Asia/Dhaka for use in
 * calendar math that must respect the org timezone (e.g. "which day is
 * this ISO timestamp in Dhaka?" rather than the user's browser zone).
 */
export const dhakaParts = (input) => {
  const d = toDate(input) || new Date();
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: APP_TZ, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).formatToParts(d).reduce((acc, p) => (p.type !== 'literal' ? { ...acc, [p.type]: p.value } : acc), {});
  return {
    y: Number(parts.year), m: Number(parts.month), d: Number(parts.day),
    hh: Number(parts.hour), mm: Number(parts.minute), ss: Number(parts.second),
  };
};

/**
 * First day of the current month in Asia/Dhaka, ISO (YYYY-MM-DD).
 */
export const firstOfMonthIso = (input) => {
  const p = dhakaParts(input);
  return `${p.y}-${String(p.m).padStart(2, '0')}-01`;
};

/**
 * Last day of the current month in Asia/Dhaka, ISO (YYYY-MM-DD).
 */
export const lastOfMonthIso = (input) => {
  const p = dhakaParts(input);
  const daysInMonth = new Date(Date.UTC(p.y, p.m, 0)).getUTCDate();
  return `${p.y}-${String(p.m).padStart(2, '0')}-${String(daysInMonth).padStart(2, '0')}`;
};
