import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Plus, CalendarClock } from 'lucide-react';
import { formatDate, formatLongDate, todayIso } from '@/lib/datetime';
import { CONFIRM_BADGE, formatPin } from '@/pages/dashboard/dispatch/_shared';
import ClientScheduleForm from './ClientScheduleForm';

const STATUS_COLOR = {
  'Not Started': 'bg-[var(--status-not-started-bg)] text-[var(--status-not-started-fg)]',
  'Clocked In': 'bg-[var(--status-clocked-in-bg)] text-[var(--status-clocked-in-fg)]',
  'Clocked Out': 'bg-[var(--status-clocked-out-bg)] text-[var(--status-clocked-out-fg)]',
};

const ClientToday = () => {
  const today = todayIso();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    api.get('/portal/schedules', { params: { date_from: today, date_to: today, limit: 250 } })
      .then(({ data }) => setRows(data.items || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [today]);

  useEffect(() => { load(); }, [load]);

  const openAdd = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (row) => { setEditing(row); setFormOpen(true); };

  return (
    <div className="space-y-6" data-testid="client-today">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Today's Dispatch</h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">{formatLongDate(new Date())} · {rows.length} dispatch{rows.length !== 1 ? 'es' : ''}</p>
        </div>
        <Button onClick={openAdd} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="client-today-add">
          <Plus className="w-4 h-4 mr-2" /> Add Dispatch
        </Button>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
        {loading ? (
          <div className="p-8 text-center text-[#64748B]">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-[#64748B]">
            <CalendarClock className="w-8 h-8 mx-auto mb-3 opacity-50" />
            No dispatches scheduled for today. Tap “Add Dispatch” to create one.
          </div>
        ) : rows.map((e) => (
          <button key={e.id} onClick={() => openEdit(e)} className="w-full text-left p-4 hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F11] transition" data-testid={`client-today-row-${e.id}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{e.post_site_name || '—'}{formatPin(e) ? ` · ${formatPin(e)}` : ''}</div>
                <div className="text-xs text-[#64748B] mt-1">{e.officer_name || '—'} · {e.vendor_name || '—'} · {e.shift_type}</div>
              </div>
              <div className="text-right">
                <div className="font-mono text-sm text-[#334155] dark:text-[#E4E4E7]">{e.start_time}–{e.end_time}</div>
                <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[e.shift_status] || ''}`}>{e.shift_status}</span>
              </div>
            </div>
          </button>
        ))}
      </div>

      <ClientScheduleForm open={formOpen} onOpenChange={setFormOpen} editing={editing} defaultDate={today} onSaved={load} />
    </div>
  );
};

export default ClientToday;
