import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { motion } from 'framer-motion';
import { CalendarDays, Clock } from 'lucide-react';
import { firstOfMonthIso, lastOfMonthIso } from '@/lib/datetime';

const ClientReports = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState({ date_from: firstOfMonthIso(), date_to: lastOfMonthIso() });

  const load = () => {
    setLoading(true);
    const params = {};
    if (range.date_from) params.date_from = range.date_from;
    if (range.date_to) params.date_to = range.date_to;
    api.get('/portal/reports', { params })
      .then(({ data }) => setReport(data))
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [JSON.stringify(range)]);

  const statusEntries = report ? Object.entries(report.by_status || {}) : [];

  return (
    <div className="space-y-6" data-testid="client-reports">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Reports</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Summary of your dispatch activity for the selected period.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4">
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={range.date_from} onChange={(e) => setRange((p) => ({ ...p, date_from: e.target.value }))} data-testid="report-from" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={range.date_to} onChange={(e) => setRange((p) => ({ ...p, date_to: e.target.value }))} data-testid="report-to" />
        </div>
        <Button variant="outline" onClick={load} data-testid="report-refresh">Refresh</Button>
      </div>

      {loading ? (
        <div className="text-[#64748B]">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5" data-testid="report-total-shifts">
              <div className="w-10 h-10 rounded-lg bg-[#4F46E5]/10 text-[#4F46E5] flex items-center justify-center mb-3"><CalendarDays className="w-5 h-5" /></div>
              <div className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{report?.totals?.shifts ?? 0}</div>
              <div className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1">Total Shifts</div>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5" data-testid="report-total-hours">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center mb-3"><Clock className="w-5 h-5" /></div>
              <div className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{report?.totals?.hours ?? 0}</div>
              <div className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1">Total Duty Hours</div>
            </motion.div>
          </div>

          {statusEntries.length > 0 && (
            <div className="flex flex-wrap gap-2" data-testid="report-status-breakdown">
              {statusEntries.map(([status, count]) => (
                <span key={status} className="px-3 py-1.5 rounded-lg text-sm bg-[#F1F5F9] dark:bg-[#27272A] text-[#334155] dark:text-[#E4E4E7]">
                  {status}: <span className="font-semibold">{count}</span>
                </span>
              ))}
            </div>
          )}

          <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
            <div className="px-4 py-3 border-b border-[#E2E8F0] dark:border-[#27272A] text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">By Vendor</div>
            <table className="w-full text-sm">
              <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
                <tr>
                  <th className="px-4 py-3">Vendor</th>
                  <th className="px-4 py-3 text-right">Shifts</th>
                  <th className="px-4 py-3 text-right">Duty Hours</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                {(report?.by_vendor || []).length === 0 ? (
                  <tr><td colSpan={3} className="px-4 py-8 text-center text-[#64748B]">No data for this period</td></tr>
                ) : report.by_vendor.map((v, i) => (
                  <tr key={i} data-testid={`report-vendor-row-${i}`}>
                    <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{v.vendor_name}</td>
                    <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{v.shifts}</td>
                    <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{v.hours}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default ClientReports;
