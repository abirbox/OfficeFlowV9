import { useEffect, useMemo, useState, useCallback } from 'react';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { dhakaDateIso, formatMonth, formatDate, todayIso } from '@/lib/datetime';
import { CONFIRM_BADGE, formatPin } from '@/pages/dashboard/dispatch/_shared';
import ClientScheduleForm from './ClientScheduleForm';

const VIEWS = [{ value: 'month', label: 'Month' }, { value: 'week', label: 'Week' }, { value: 'day', label: 'Day' }];
const iso = (d) => dhakaDateIso(d);
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const startOfWeek = (d) => { const x = new Date(d); x.setDate(x.getDate() - x.getDay()); return x; };
const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
const endOfMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0);

const ClientCalendar = () => {
  const [view, setView] = useState('week');
  const [cursor, setCursor] = useState(new Date());
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [addDate, setAddDate] = useState(todayIso());

  const range = useMemo(() => {
    if (view === 'day') return { from: iso(cursor), to: iso(cursor) };
    if (view === 'week') { const s = startOfWeek(cursor); return { from: iso(s), to: iso(addDays(s, 6)) }; }
    return { from: iso(startOfMonth(cursor)), to: iso(endOfMonth(cursor)) };
  }, [view, cursor]);

  const load = useCallback(() => {
    setLoading(true);
    api.get('/portal/schedules', { params: { date_from: range.from, date_to: range.to, limit: 250 } })
      .then(({ data }) => setRows(data.items || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [range.from, range.to]);

  useEffect(() => { load(); }, [load]);

  const byDate = useMemo(() => {
    const m = {};
    rows.forEach((r) => { (m[r.date] ||= []).push(r); });
    Object.values(m).forEach((arr) => arr.sort((a, b) => (a.start_time || '').localeCompare(b.start_time || '')));
    return m;
  }, [rows]);

  const step = view === 'day' ? 1 : view === 'week' ? 7 : 30;
  const prev = () => setCursor(view === 'month' ? new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1) : addDays(cursor, -step));
  const next = () => setCursor(view === 'month' ? new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1) : addDays(cursor, step));

  const label = view === 'month' ? formatMonth(cursor)
    : view === 'week' ? `${iso(startOfWeek(cursor))} → ${iso(addDays(startOfWeek(cursor), 6))}`
      : formatDate(cursor);

  const openAdd = (date) => { setEditing(null); setAddDate(date || todayIso()); setFormOpen(true); };
  const openEdit = (row) => { setEditing(row); setFormOpen(true); };

  return (
    <div className="space-y-6" data-testid="client-calendar">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Dispatch Calendar</h1>
          <p className="text-sm text-[#64748B] mt-1">{rows.length} scheduled shift{rows.length !== 1 && 's'} in view</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button onClick={() => openAdd()} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="client-calendar-add">
            <Plus className="w-4 h-4 mr-2" /> Add Dispatch
          </Button>
          <Select value={view} onValueChange={setView}>
            <SelectTrigger className="w-28" data-testid="client-cal-view"><SelectValue /></SelectTrigger>
            <SelectContent>{VIEWS.map((v) => <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>)}</SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={prev} data-testid="client-cal-prev"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => setCursor(new Date())} data-testid="client-cal-today">Today</Button>
          <Button variant="outline" size="sm" onClick={next} data-testid="client-cal-next"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      <div className="text-lg font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{label}</div>

      {loading ? (
        <div className="p-12 text-center text-[#64748B]">Loading…</div>
      ) : view === 'month' ? (
        <MonthGrid cursor={cursor} byDate={byDate} onSelect={openEdit} onAdd={openAdd} />
      ) : view === 'week' ? (
        <WeekGrid cursor={cursor} byDate={byDate} onSelect={openEdit} onAdd={openAdd} />
      ) : (
        <DayList date={iso(cursor)} events={byDate[iso(cursor)] || []} onSelect={openEdit} />
      )}

      <ClientScheduleForm open={formOpen} onOpenChange={setFormOpen} editing={editing} defaultDate={addDate} onSaved={load} />
    </div>
  );
};

const MonthGrid = ({ cursor, byDate, onSelect, onAdd }) => {
  const gridStart = startOfWeek(startOfMonth(cursor));
  const cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const today = todayIso();
  return (
    <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-hidden">
      <div className="grid grid-cols-7 bg-[#F8FAFC] dark:bg-[#0F0F11] text-xs uppercase tracking-wider text-[#64748B]">
        {dayNames.map((d) => <div key={d} className="px-3 py-2 text-center">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 grid-rows-6 divide-x divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
        {cells.map((d) => {
          const dStr = iso(d);
          const inMonth = d.getMonth() === cursor.getMonth();
          const isToday = dStr === today;
          const events = byDate[dStr] || [];
          return (
            <div key={dStr} className={`min-h-[110px] p-2 group ${inMonth ? '' : 'bg-[#FAFAFA] dark:bg-[#0F0F11] opacity-60'}`} data-testid={`client-cal-cell-${dStr}`}>
              <div className="flex items-center justify-between">
                <div className={`text-xs mb-1 font-medium ${isToday ? 'inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#4F46E5] text-white' : 'text-[#334155] dark:text-[#E4E4E7]'}`}>{d.getDate()}</div>
                <button onClick={() => onAdd(dStr)} className="opacity-0 group-hover:opacity-100 text-[#4F46E5] text-xs" title="Add" data-testid={`client-cal-add-${dStr}`}>+</button>
              </div>
              <div className="space-y-1">
                {events.slice(0, 3).map((e) => (
                  <button key={e.id} onClick={() => onSelect(e)} className={`w-full text-left px-1.5 py-1 rounded text-[11px] truncate border ${CONFIRM_BADGE[e.confirmation_status] || 'bg-slate-100 text-slate-700'} hover:opacity-80`} data-testid={`client-cal-event-${e.id}`}>
                    <span className="font-medium">{e.start_time}</span> {e.post_site_name || '—'}
                  </button>
                ))}
                {events.length > 3 && <div className="text-[11px] text-[#64748B]">+{events.length - 3} more</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const WeekGrid = ({ cursor, byDate, onSelect, onAdd }) => {
  const start = startOfWeek(cursor);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const today = todayIso();
  return (
    <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
      <div className="grid grid-cols-7 divide-x divide-[#E2E8F0] dark:divide-[#27272A] min-w-[840px]">
        {days.map((d) => {
          const dStr = iso(d);
          const events = byDate[dStr] || [];
          const isToday = dStr === today;
          return (
            <div key={dStr} className="min-h-[400px] group">
              <div className={`px-3 py-2 border-b border-[#E2E8F0] dark:border-[#27272A] text-xs flex items-center justify-between ${isToday ? 'bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-semibold' : 'bg-[#F8FAFC] dark:bg-[#0F0F11] text-[#64748B]'}`}>
                <span>{formatDate(d)}</span>
                <button onClick={() => onAdd(dStr)} className="opacity-0 group-hover:opacity-100 text-[#4F46E5]" title="Add" data-testid={`client-week-add-${dStr}`}>+</button>
              </div>
              <div className="p-2 space-y-2">
                {events.length === 0 ? <div className="text-xs text-[#94A3B8]">No shifts</div> : events.map((e) => (
                  <button key={e.id} onClick={() => onSelect(e)} className={`w-full text-left p-2 rounded-lg border ${CONFIRM_BADGE[e.confirmation_status] || 'bg-slate-100 text-slate-700'} hover:opacity-80`} data-testid={`client-cal-event-${e.id}`}>
                    <div className="text-[11px] font-mono">{e.start_time}–{e.end_time}</div>
                    <div className="text-xs font-medium mt-0.5">{e.post_site_name || '—'}</div>
                    {formatPin(e) && <div className="text-[10px] font-mono opacity-70">{formatPin(e)}</div>}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const DayList = ({ date, events, onSelect }) => (
  <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
    {events.length === 0 ? (
      <div className="p-8 text-center text-[#64748B]">No schedules on {date}</div>
    ) : events.map((e) => (
      <button key={e.id} onClick={() => onSelect(e)} className="w-full text-left p-4 hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F11] transition" data-testid={`client-cal-event-${e.id}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{e.post_site_name || '—'}</div>
            <div className="text-xs text-[#64748B] mt-1">{e.officer_name} · {e.vendor_name} · Post Pin: {formatPin(e) || '—'}</div>
          </div>
          <div className="text-right">
            <div className="font-mono text-sm">{e.start_time}–{e.end_time}</div>
            <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs border ${CONFIRM_BADGE[e.confirmation_status] || 'bg-slate-100'}`}>{e.confirmation_status}</span>
          </div>
        </div>
      </button>
    ))}
  </div>
);

export default ClientCalendar;
