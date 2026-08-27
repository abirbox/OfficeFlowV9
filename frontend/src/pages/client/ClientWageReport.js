import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/axios';
import { useAppSettings } from '@/contexts/AppSettingsContext';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/sonner';
import { FileDown } from 'lucide-react';
import { firstOfMonthIso, lastOfMonthIso } from '@/lib/datetime';

const ClientWageReport = () => {
  const { settings } = useAppSettings();
  const cur = settings?.currency_symbol || '$';
  const [range, setRange] = useState({ date_from: firstOfMonthIso(), date_to: lastOfMonthIso() });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api.get('/portal/wage-report', { params: range })
      .then(({ data }) => setData(data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [range]);

  useEffect(() => { load(); }, [load]);

  const money = (n) => `${cur}${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const downloadPayslip = async (officer, fmt) => {
    try {
      const res = await api.get(`/portal/officers/${officer.officer_id}/payslip`, {
        params: { ...range, format: fmt }, responseType: 'blob',
      });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = `Payslip-${(officer.officer_name || 'officer').replace(/\s+/g, '-')}.${fmt}`;
      a.click(); window.URL.revokeObjectURL(url);
    } catch (e) { toast.error('Could not download payslip'); }
  };

  return (
    <div className="space-y-6" data-testid="client-wage-report">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Wage Report</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Wage breakdown for officers assigned to your account.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4">
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={range.date_from} onChange={(e) => setRange((p) => ({ ...p, date_from: e.target.value }))} data-testid="wage-from" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={range.date_to} onChange={(e) => setRange((p) => ({ ...p, date_to: e.target.value }))} data-testid="wage-to" />
        </div>
        <Button variant="outline" onClick={load} data-testid="wage-refresh">Refresh</Button>
        {data && (
          <div className="ml-auto text-sm text-[#64748B]">
            <span className="mr-4">Officers: <b className="text-[#0F172A] dark:text-[#FAFAFA]">{data.totals?.officers ?? 0}</b></span>
            <span className="mr-4">Hours: <b className="text-[#0F172A] dark:text-[#FAFAFA]">{data.totals?.hours ?? 0}</b></span>
            <span>Total Wage: <b className="text-emerald-600">{money(data.totals?.wage)}</b></span>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">Officer</th>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3 text-right">Shifts</th>
              <th className="px-4 py-3 text-right">Completed</th>
              <th className="px-4 py-3 text-right">Hours</th>
              <th className="px-4 py-3 text-right">Wage</th>
              <th className="px-4 py-3 text-right">Payslip</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : !data || data.items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-[#64748B]">No wage data for this period</td></tr>
            ) : data.items.map((r) => (
              <tr key={r.officer_id} data-testid={`wage-row-${r.officer_id}`}>
                <td className="px-4 py-3 font-medium text-[#0F172A] dark:text-[#FAFAFA]">{r.officer_name}</td>
                <td className="px-4 py-3 font-mono text-[#334155] dark:text-[#E4E4E7]">{r.officer_code || '—'}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{r.total_shifts}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{r.completed}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{r.total_hours}</td>
                <td className="px-4 py-3 text-right font-semibold text-emerald-600">{money(r.wage)}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <Button size="sm" variant="outline" onClick={() => downloadPayslip(r, 'pdf')} data-testid={`payslip-pdf-${r.officer_id}`}>
                    <FileDown className="w-3 h-3 mr-1" /> PDF
                  </Button>
                  <Button size="sm" variant="ghost" className="ml-1" onClick={() => downloadPayslip(r, 'xlsx')} data-testid={`payslip-xlsx-${r.officer_id}`}>XLSX</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClientWageReport;
