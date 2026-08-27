import { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/axios';
import { useAppSettings } from '@/contexts/AppSettingsContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { Search, FileDown } from 'lucide-react';

const ClientPaymentSO = () => {
  const { settings } = useAppSettings();
  const cur = settings?.currency_symbol || '$';
  const [ctx, setCtx] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);

  const money = (n) => `${cur}${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    if (search) params.search = search;
    api.get('/portal/payments', { params })
      .then(({ data }) => setCtx(data))
      .catch(() => setCtx(null))
      .finally(() => setLoading(false));
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const download = async (url, filename) => {
    try {
      const res = await api.get(url, { responseType: 'blob' });
      const blobUrl = window.URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = blobUrl; a.download = filename; a.click();
      window.URL.revokeObjectURL(blobUrl);
    } catch (e) { toast.error('Download failed'); }
  };

  const openDetail = async (row) => {
    try {
      const { data } = await api.get(`/portal/payments/officer/${row.officer_id}`);
      setDetail(data);
    } catch (e) { toast.error('Could not load officer payments'); }
  };

  const rows = ctx?.rows || [];
  const totals = ctx?.totals;

  return (
    <div className="space-y-6" data-testid="client-payment-so">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Payment (SO)</h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Payment records for your Security Officers.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => download('/portal/payments/report/pdf', 'Payments.pdf')} data-testid="payments-pdf"><FileDown className="w-4 h-4 mr-1" /> PDF</Button>
          <Button variant="outline" onClick={() => download('/portal/payments/report/xlsx', 'Payments.xlsx')} data-testid="payments-xlsx">XLSX</Button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
        <Input placeholder="Search officers..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" data-testid="payment-search" />
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">Officer</th>
              <th className="px-4 py-3 text-right">W2</th>
              <th className="px-4 py-3 text-right">W9 Total</th>
              <th className="px-4 py-3 text-right">Total</th>
              <th className="px-4 py-3 text-right">Entries</th>
              <th className="px-4 py-3 text-right">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">No payment records for your officers yet</td></tr>
            ) : rows.map((r) => (
              <tr key={r.officer_id} data-testid={`payment-row-${r.officer_id}`}>
                <td className="px-4 py-3 font-medium text-[#0F172A] dark:text-[#FAFAFA]">{r.officer_name}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{money(r.w2_amount)}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{money(r.w9_total)}</td>
                <td className="px-4 py-3 text-right font-semibold text-emerald-600">{money(r.total)}</td>
                <td className="px-4 py-3 text-right text-[#334155] dark:text-[#E4E4E7]">{r.entries}</td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => openDetail(r)} data-testid={`payment-view-${r.officer_id}`}>View</Button>
                </td>
              </tr>
            ))}
          </tbody>
          {totals && rows.length > 0 && (
            <tfoot>
              <tr className="bg-[#F8FAFC] dark:bg-[#0F0F11] font-semibold">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right">{money(totals.w2)}</td>
                <td className="px-4 py-3 text-right">{money(totals.w9_total)}</td>
                <td className="px-4 py-3 text-right text-emerald-600">{money(totals.grand_total)}</td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="payment-detail">
          <DialogHeader><DialogTitle>{detail?.officer?.name} — Payment History</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-4">
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => download(`/portal/payments/officer/${detail.officer.id}/report/pdf`, `Payment-${detail.officer.name}.pdf`)} data-testid="payment-officer-pdf"><FileDown className="w-3 h-3 mr-1" /> PDF</Button>
                <Button size="sm" variant="ghost" onClick={() => download(`/portal/payments/officer/${detail.officer.id}/report/xlsx`, `Payment-${detail.officer.name}.xlsx`)} data-testid="payment-officer-xlsx">XLSX</Button>
              </div>
              <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase text-[#64748B]">
                    <tr>
                      <th className="px-3 py-2">Date</th>
                      <th className="px-3 py-2 text-right">W2</th>
                      <th className="px-3 py-2 text-right">W9 DD</th>
                      <th className="px-3 py-2 text-right">W9 Zelle</th>
                      <th className="px-3 py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                    {(detail.records || []).length === 0 ? (
                      <tr><td colSpan={5} className="px-3 py-6 text-center text-[#64748B]">No entries</td></tr>
                    ) : detail.records.map((rec) => (
                      <tr key={rec.id}>
                        <td className="px-3 py-2">{rec.date || '—'}</td>
                        <td className="px-3 py-2 text-right">{money(rec.w2_amount)}</td>
                        <td className="px-3 py-2 text-right">{money(rec.w9_direct_deposit_amount)}</td>
                        <td className="px-3 py-2 text-right">{money(rec.w9_zelle_amount)}</td>
                        <td className="px-3 py-2 text-right font-semibold">{money(rec.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClientPaymentSO;
