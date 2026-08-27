# OfficeFlowV7 — PRD

## Original problem statement
Load unchanged the repo https://github.com/abirbox/OfficeFlowV7.git so we can modify it.

## Core requirements
- Preserve V7 exactly as-is; make modifications only when explicitly requested.
- All dates and times displayed or computed for business logic must reflect Asia/Dhaka (UTC+6). Storage remains in UTC in the DB — this is best practice — but every user-visible or "today"-derived value is pinned to Dhaka.

## What's been implemented
- 2026-08-26: Replaced /app contents with `main` branch of `abirbox/OfficeFlowV7` while preserving .git, .emergent, and .env. Verified login page renders.
- 2026-08-27: **Asia/Dhaka timezone rollout across the entire app:**
  - Backend: Added `dhaka_now()`, `dhaka_today()`, `dhaka_today_iso()` helpers in `utils/tz.py`.
  - Backend routes swept — replaced every `date.today()` and `datetime.now(timezone.utc).date()` in user-facing "today"/month logic with Dhaka helpers: admin.py, dispatch.py (dashboard stats + report defaults), shifts.py, attendance.py, reports.py.
  - Backend PDFs: `dispatch_reports.py` footer now shows "Generated YYYY-MM-DD HH:MM (Asia/Dhaka)" (was UTC via `datetime.utcnow()`). `payslip_pdf.py` "Issued" date uses Dhaka.
  - Frontend: New central helper `/app/frontend/src/lib/datetime.js` — `dhakaDateIso`, `todayIso`, `formatDate`, `formatTime`, `formatDateTime`, `dhakaParts`, `firstOfMonthIso`, `lastOfMonthIso`. All pinned via `{ timeZone: 'Asia/Dhaka' }`.
  - Frontend swept — 16 files refactored to use the new helpers instead of raw `.toLocaleString/.toLocaleDateString/.toLocaleTimeString/.toISOString().slice(0,10)`.
  - Regression pass: testing agent iteration 7 confirmed 5/5 backend + 6/6 frontend, with `BDT`-labelled timestamps on the Audit Log matching Asia/Dhaka time (container OS is UTC, proving the pin is in code).

## Prioritized backlog
- P1: `/api/shifts/today` — brief mentioned it, but no such route exists in V7. Either add it (via `dhaka_today_iso()`) or drop from any docs.
- P1: Native `<input type="date">` in filters (Audit Log, Reports) still parses via browser local tz. Consider swapping to the shadcn Calendar bound to `/lib/datetime` helpers so filter round-trips stay in Dhaka.
- P2: Add `data-testid="notification-bell"` on the topbar bell for easier automation.
- P3: Split `routes/dispatch.py` (~3000 lines) into `dispatch_schedules.py`, `dispatch_reports.py`, `dispatch_payslip.py`.

## Test credentials
- Admin (super_admin): admin@example.com / admin123 (see /app/memory/test_credentials.md)
