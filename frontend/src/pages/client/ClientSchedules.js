import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { formatDate } from '@/lib/datetime';
import { CONFIRM_BADGE, formatPin } from '@/pages/dashboard/dispatch/_shared';

const STATUS_COLOR = {
  'Not Started': 'bg-[var(--status-not-started-bg)] text-[var(--status-not-started-fg)]',
  'Clocked In': 'bg-[var(--status-clocked-in-bg)] text-[var(--status-clocked-in-fg)]',
  'Clocked Out': 'bg-[var(--status-clocked-out-bg)] text-[var(--status-clocked-out-fg)]',
};

const ClientSchedules = () => {
  const [rows, setRows] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ vendor_id: '', shift_status: '', date_from: '', date_to: '' });

  useEffect(() => {
    api.get('/portal/vendors').then((r) => setVendors(r.data || [])).catch(() => setVendors([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { ...filters, limit: 200 };
    Object.keys(params).forEach((k) => { if (!params[k]) delete params[k]; });
    api.get('/portal/schedules', { params })
      .then(({ data }) => setRows(data.items || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [JSON.stringify(filters)]);

  const setF = (k, v) => setFilters((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6" data-testid="client-schedules">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">My Schedules</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">All dispatch schedules for your account.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4">
        <div className="space-y-1">
          <Label className="text-xs">Vendor</Label>
          <Select value={filters.vendor_id || 'all'} onValueChange={(v) => setF('vendor_id', v === 'all' ? '' : v)}>
            <SelectTrigger data-testid="client-filter-vendor"><SelectValue placeholder="All Vendors" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Vendors</SelectItem>
              {vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select value={filters.shift_status || 'all'} onValueChange={(v) => setF('shift_status', v === 'all' ? '' : v)}>
            <SelectTrigger data-testid="client-filter-status"><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="Not Started">Not Started</SelectItem>
              <SelectItem value="Clocked In">Clocked In</SelectItem>
              <SelectItem value="Clocked Out">Clocked Out</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={filters.date_from} onChange={(e) => setF('date_from', e.target.value)} data-testid="client-filter-from" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={filters.date_to} onChange={(e) => setF('date_to', e.target.value)} data-testid="client-filter-to" />
        </div>
        {(filters.vendor_id || filters.shift_status || filters.date_from || filters.date_to) && (
          <div className="lg:col-span-4">
            <Button variant="outline" size="sm" onClick={() => setFilters({ vendor_id: '', shift_status: '', date_from: '', date_to: '' })} data-testid="client-clear-filters">Clear Filters</Button>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Shift</th>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Vendor</th>
              <th className="px-4 py-3">Officer</th>
              <th className="px-4 py-3">Post Site</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Confirmation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-[#64748B]">No schedules found</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id} data-testid={`client-schedule-row-${r.id}`}>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{formatDate(r.date)}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.shift_type}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.start_time}–{r.end_time}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.vendor_name || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.officer_name || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.post_site_name || '—'}{formatPin(r) ? ` · ${formatPin(r)}` : ''}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLOR[r.shift_status] || ''}`}>{r.shift_status}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium border ${CONFIRM_BADGE[r.confirmation_status] || ''}`}>{r.confirmation_status || 'Not Confirmed'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClientSchedules;
