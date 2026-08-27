import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  Plus, Download, FileSpreadsheet, ArrowLeft, Search, Eye, Pencil, Trash2,
} from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../../components/ui/select';
import api, { formatApiErrorDetail } from '../../../lib/axios';
import { dhakaDateIso } from '../../../lib/datetime';

const money = (v) => `$${Number(v || 0).toFixed(2)}`;

const DATE_PRESETS = [
  { key: 'all', label: 'All Time' },
  { key: '7d', label: 'Last 7 Days' },
  { key: '30d', label: 'Last 30 Days' },
  { key: '3m', label: 'Last 3 Months' },
  { key: '6m', label: 'Last 6 Months' },
  { key: '1y', label: 'Last 1 Year' },
  { key: 'custom', label: 'Custom' },
];

// ISO date pinned to Asia/Dhaka so range presets don't shift by browser zone.
const fmtDate = (d) => dhakaDateIso(d);
function presetRange(key) {
  const to = new Date();
  const from = new Date();
  if (key === '7d') from.setDate(to.getDate() - 7);
  else if (key === '30d') from.setDate(to.getDate() - 30);
  else if (key === '3m') from.setMonth(to.getMonth() - 3);
  else if (key === '6m') from.setMonth(to.getMonth() - 6);
  else if (key === '1y') from.setFullYear(to.getFullYear() - 1);
  else return { date_from: '', date_to: '' };
  return { date_from: fmtDate(from), date_to: fmtDate(to) };
}

const DateRangeFilter = ({ onChange, testid }) => {
  const [preset, setPreset] = useState('all');
  const [custom, setCustom] = useState({ from: '', to: '' });

  const applyPreset = (key) => {
    setPreset(key);
    if (key === 'custom') { onChange({ date_from: custom.from, date_to: custom.to }); return; }
    onChange(presetRange(key));
  };
  const applyCustom = (patch) => {
    const c = { ...custom, ...patch };
    setCustom(c);
    onChange({ date_from: c.from, date_to: c.to });
  };

  return (
    <div className="flex items-end gap-2" data-testid={testid}>
      <div>
        <Label className="text-xs">Date Filter</Label>
        <Select value={preset} onValueChange={applyPreset}>
          <SelectTrigger className="w-[150px]" data-testid={`${testid}-preset`}><SelectValue /></SelectTrigger>
          <SelectContent>
            {DATE_PRESETS.map((p) => (
              <SelectItem key={p.key} value={p.key} data-testid={`${testid}-preset-${p.key}`}>{p.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {preset === 'custom' && (
        <>
          <div>
            <Label className="text-xs">From</Label>
            <Input type="date" value={custom.from} onChange={(e) => applyCustom({ from: e.target.value })}
              className="h-10" data-testid={`${testid}-from`} />
          </div>
          <div>
            <Label className="text-xs">To</Label>
            <Input type="date" value={custom.to} onChange={(e) => applyCustom({ to: e.target.value })}
              className="h-10" data-testid={`${testid}-to`} />
          </div>
        </>
      )}
    </div>
  );
};

const emptyComponent = () => ({ date: '', amount: '' });
const emptyPayForm = () => ({
  officer: null,
  w2: emptyComponent(),
  w9_direct_deposit: emptyComponent(),
  w9_zelle: emptyComponent(),
});

const PaymentSOPage = () => {
  const [selectedClient, setSelectedClient] = useState(null);
  const [selectedOfficer, setSelectedOfficer] = useState(null);

  if (selectedOfficer) {
    return <OfficerDetail officer={selectedOfficer} onBack={() => setSelectedOfficer(null)} />;
  }
  if (selectedClient) {
    return (
      <ClientView
        client={selectedClient}
        onBack={() => setSelectedClient(null)}
        onOpenOfficer={setSelectedOfficer}
      />
    );
  }
  return <ClientList onOpen={setSelectedClient} />;
};

/* ----------------------------- Landing: Client list ---------------------- */
const ClientList = ({ onOpen }) => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');

  const load = useCallback(async (q) => {
    setLoading(true);
    try {
      const { data } = await api.get('/so-payments/clients', { params: q ? { search: q } : {} });
      setClients(data || []);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load(search), search ? 300 : 0);
    return () => clearTimeout(t);
  }, [search, load]);

  return (
    <div className="space-y-6" data-testid="payment-so-page">
      <div>
        <h1 className="text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Payment (SO)</h1>
        <p className="text-sm text-[#64748B]">Select a client to manage Security Officer payment records.</p>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search client name or code..." className="pl-9" data-testid="so-client-search" />
        </div>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3 text-left">Client Name</th>
              <th className="px-4 py-3 text-left">Client Code</th>
              <th className="px-4 py-3 text-center">Security Officers</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading && <tr><td colSpan={4} className="px-4 py-6 text-center text-[#64748B]">Loading…</td></tr>}
            {!loading && clients.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-[#64748B]">No clients found.</td></tr>
            )}
            {clients.map((c) => (
              <tr key={c.id} className="hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]" data-testid={`so-client-row-${c.id}`}>
                <td className="px-4 py-3">
                  <button onClick={() => onOpen(c)} className="font-medium text-[#4F46E5] hover:underline" data-testid={`so-client-name-${c.id}`}>
                    {c.name || '—'}
                  </button>
                </td>
                <td className="px-4 py-3 font-mono">{c.code || '—'}</td>
                <td className="px-4 py-3 text-center">{c.officer_count}</td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => onOpen(c)} data-testid={`so-client-view-${c.id}`}>
                    <Eye className="w-4 h-4 mr-1" /> View
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ----------------------------- Client view ------------------------------- */
const ClientView = ({ client, onBack, onOpenOfficer }) => {
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [range, setRange] = useState({ date_from: '', date_to: '' });
  const [dialogOpen, setDialogOpen] = useState(false);

  const load = useCallback(async (q, r) => {
    setLoading(true);
    try {
      const params = { client_id: client.id };
      if (q) params.search = q;
      if (r?.date_from) params.date_from = r.date_from;
      if (r?.date_to) params.date_to = r.date_to;
      const { data } = await api.get('/so-payments/records', { params });
      setCtx(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [client.id]);

  useEffect(() => {
    const t = setTimeout(() => load(search, range), 300);
    return () => clearTimeout(t);
  }, [search, range, load]);

  const rows = ctx?.rows || [];
  const totals = ctx?.totals || {};

  const download = async (kind) => {
    try {
      const params = { client_id: client.id };
      if (search) params.search = search;
      if (range.date_from) params.date_from = range.date_from;
      if (range.date_to) params.date_to = range.date_to;
      const res = await api.get(`/so-payments/records/report/${kind}`, { params, responseType: 'blob' });
      const type = kind === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      _saveBlob(res.data, `Payment-${client.name || 'client'}.${kind === 'pdf' ? 'pdf' : 'xlsx'}`, type);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || `${kind.toUpperCase()} download failed`);
    }
  };

  const openOfficer = (r) => onOpenOfficer({
    id: r.officer_id, name: r.officer_name, officer_code: r.officer_code,
    address: r.officer_address, social_security_code: r.social_security_code,
    client,
  });

  return (
    <div className="space-y-6" data-testid="so-client-view">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={onBack} data-testid="so-client-back">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{client.name}</h1>
            <p className="text-sm text-[#64748B]">Client Code: <span className="font-mono">{client.code || '—'}</span></p>
          </div>
        </div>
        <Button className="bg-[#4F46E5] hover:bg-[#4338CA]" onClick={() => setDialogOpen(true)} data-testid="so-add-new-payment">
          <Plus className="w-4 h-4 mr-2" /> Add New Payment
        </Button>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative w-full max-w-xs">
            <Label className="text-xs">Search</Label>
            <Search className="absolute left-3 top-[34px] w-4 h-4 text-[#94A3B8]" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Officer name, address or SSC..." className="pl-9" data-testid="so-record-search" />
          </div>
          <DateRangeFilter testid="so-client-date-filter" onChange={setRange} />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => download('pdf')} data-testid="so-download-pdf">
            <Download className="w-4 h-4 mr-2" /> PDF
          </Button>
          <Button variant="outline" onClick={() => download('xlsx')} data-testid="so-download-excel">
            <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel
          </Button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm" data-testid="so-records-table">
          <thead className="bg-[#F2C4CE] text-xs uppercase tracking-wider text-[#0F172A]">
            <tr>
              <th className="px-3 py-2 text-left" rowSpan={2}>SL</th>
              <th className="px-3 py-2 text-left" rowSpan={2}>Security Officer Name</th>
              <th className="px-3 py-2 text-left" rowSpan={2}>Address</th>
              <th className="px-3 py-2 text-left" rowSpan={2}>Social Security</th>
              <th className="px-3 py-2 text-right" rowSpan={2}>W2</th>
              <th className="px-3 py-2 text-center border-l border-[#0F172A]/20" colSpan={3}>W9</th>
              <th className="px-3 py-2 text-right border-l border-[#0F172A]/20" rowSpan={2}>Total (W2+W9)</th>
              <th className="px-3 py-2 text-right" rowSpan={2}>Action</th>
            </tr>
            <tr>
              <th className="px-3 py-2 text-right border-l border-[#0F172A]/20">Direct Deposit</th>
              <th className="px-3 py-2 text-right">Zelle Transfer</th>
              <th className="px-3 py-2 text-right">W9 Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading && <tr><td colSpan={10} className="px-4 py-6 text-center text-[#64748B]">Loading…</td></tr>}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-[#64748B]">No payment records yet. Click <b>Add New Payment</b>.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.officer_id} data-testid={`so-record-row-${r.officer_id}`}>
                <td className="px-3 py-2.5">{r.sl}</td>
                <td className="px-3 py-2.5">
                  <button onClick={() => openOfficer(r)} className="font-medium text-[#4F46E5] hover:underline" data-testid={`so-officer-name-${r.officer_id}`}>
                    {r.officer_name || '—'}
                  </button>
                </td>
                <td className="px-3 py-2.5">{r.officer_address || '—'}</td>
                <td className="px-3 py-2.5 font-mono">{r.social_security_code || '—'}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w2_amount)}</td>
                <td className="px-3 py-2.5 text-right border-l border-[#E2E8F0] dark:border-[#27272A]">{money(r.w9_direct_deposit_amount)}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w9_zelle_amount)}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w9_total)}</td>
                <td className="px-3 py-2.5 text-right font-semibold border-l border-[#E2E8F0] dark:border-[#27272A]">{money(r.total)}</td>
                <td className="px-3 py-2.5 text-right">
                  <Button size="sm" variant="outline" onClick={() => openOfficer(r)} data-testid={`so-record-view-${r.officer_id}`}>
                    <Eye className="w-4 h-4 mr-1" /> View
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-[#F8FAFC] dark:bg-[#0F0F11] font-bold border-t-2 border-[#0F172A]">
              <tr data-testid="so-records-totals">
                <td className="px-3 py-3" colSpan={4}>Grand Total</td>
                <td className="px-3 py-3 text-right" data-testid="so-total-w2">{money(totals.w2)}</td>
                <td className="px-3 py-3 text-right border-l border-[#E2E8F0] dark:border-[#27272A]" data-testid="so-total-dd">{money(totals.w9_direct_deposit)}</td>
                <td className="px-3 py-3 text-right" data-testid="so-total-zelle">{money(totals.w9_zelle)}</td>
                <td className="px-3 py-3 text-right" data-testid="so-total-w9">{money(totals.w9_total)}</td>
                <td className="px-3 py-3 text-right border-l border-[#E2E8F0] dark:border-[#27272A]" data-testid="so-grand-total">{money(totals.grand_total)}</td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {dialogOpen && (
        <PaymentDialog
          open={dialogOpen} setOpen={setDialogOpen}
          client={client}
          onSaved={() => { setDialogOpen(false); load(search, range); }}
        />
      )}
    </div>
  );
};

/* --------------------------- Officer detail view ------------------------- */
const OfficerDetail = ({ officer, onBack }) => {
  const [ctx, setCtx] = useState(null);
  const [loading, setLoading] = useState(false);
  const [range, setRange] = useState({ date_from: '', date_to: '' });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);

  const load = useCallback(async (r) => {
    setLoading(true);
    try {
      const params = { officer_id: officer.id };
      if (r?.date_from) params.date_from = r.date_from;
      if (r?.date_to) params.date_to = r.date_to;
      const { data } = await api.get('/so-payments/records/officer', { params });
      setCtx(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [officer.id]);

  useEffect(() => {
    const t = setTimeout(() => load(range), 300);
    return () => clearTimeout(t);
  }, [load, range]);

  const records = ctx?.records || [];
  const totals = ctx?.totals || {};
  const period = ctx?.period || {};

  const download = async (kind) => {
    try {
      const params = { officer_id: officer.id };
      if (range.date_from) params.date_from = range.date_from;
      if (range.date_to) params.date_to = range.date_to;
      const res = await api.get(`/so-payments/records/officer/report/${kind}`,
        { params, responseType: 'blob' });
      const type = kind === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      _saveBlob(res.data, `Payment-${officer.name || 'officer'}.${kind === 'pdf' ? 'pdf' : 'xlsx'}`, type);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || `${kind.toUpperCase()} download failed`);
    }
  };

  const removeRecord = async (r) => {
    if (!window.confirm(`Delete this payment entry (${r.date || 'no date'})?`)) return;
    try {
      await api.delete(`/so-payments/records/${r.id}`);
      toast.success('Entry deleted');
      load(range);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-6" data-testid="so-officer-detail">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={onBack} data-testid="so-officer-back">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{officer.name}</h1>
            <p className="text-sm text-[#64748B]">
              {officer.client?.name || ''} · <span className="font-mono">{officer.officer_code || '—'}</span>
              {' · '}SSC: <span className="font-mono">{officer.social_security_code || '—'}</span>
            </p>
            <p className="text-xs text-[#94A3B8]">
              Statement Period: {period.from || '—'} to {period.to || '—'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => download('pdf')} data-testid="so-officer-download-pdf">
            <Download className="w-4 h-4 mr-2" /> PDF
          </Button>
          <Button variant="outline" onClick={() => download('xlsx')} data-testid="so-officer-download-excel">
            <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel
          </Button>
          <Button className="bg-[#4F46E5] hover:bg-[#4338CA]" onClick={() => { setEditingRecord(null); setDialogOpen(true); }} data-testid="so-officer-add-payment">
            <Plus className="w-4 h-4 mr-2" /> Add Payment
          </Button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4">
        <DateRangeFilter testid="so-officer-date-filter" onChange={setRange} />
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm" data-testid="so-officer-table">
          <thead className="bg-[#F2C4CE] text-xs uppercase tracking-wider text-[#0F172A]">
            <tr>
              <th className="px-3 py-2 text-left" rowSpan={2}>Date</th>
              <th className="px-3 py-2 text-right" rowSpan={2}>W2</th>
              <th className="px-3 py-2 text-center border-l border-[#0F172A]/20" colSpan={3}>W9</th>
              <th className="px-3 py-2 text-right border-l border-[#0F172A]/20" rowSpan={2}>Total (W2+W9)</th>
              <th className="px-3 py-2 text-right" rowSpan={2}>Action</th>
            </tr>
            <tr>
              <th className="px-3 py-2 text-right border-l border-[#0F172A]/20">Direct Deposit</th>
              <th className="px-3 py-2 text-right">Zelle Transfer</th>
              <th className="px-3 py-2 text-right">W9 Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading && <tr><td colSpan={7} className="px-4 py-6 text-center text-[#64748B]">Loading…</td></tr>}
            {!loading && records.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-[#64748B]">No payment entries yet. Click <b>Add Payment</b>.</td></tr>
            )}
            {records.map((r) => (
              <tr key={r.id} data-testid={`so-entry-row-${r.id}`}>
                <td className="px-3 py-2.5 bg-[#FBE4EA]/60">{r.date || '—'}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w2_amount)}</td>
                <td className="px-3 py-2.5 text-right border-l border-[#E2E8F0] dark:border-[#27272A]">{money(r.w9_direct_deposit_amount)}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w9_zelle_amount)}</td>
                <td className="px-3 py-2.5 text-right">{money(r.w9_total)}</td>
                <td className="px-3 py-2.5 text-right font-semibold border-l border-[#E2E8F0] dark:border-[#27272A]">{money(r.total)}</td>
                <td className="px-3 py-2.5 text-right whitespace-nowrap">
                  <Button size="sm" variant="outline" onClick={() => { setEditingRecord(r); setDialogOpen(true); }} data-testid={`so-entry-edit-${r.id}`}>
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => removeRecord(r)}
                    className="ml-2 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20" data-testid={`so-entry-delete-${r.id}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
          {records.length > 0 && (
            <tfoot className="bg-[#F8FAFC] dark:bg-[#0F0F11] font-bold border-t-2 border-[#0F172A]">
              <tr data-testid="so-officer-totals">
                <td className="px-3 py-3">Total</td>
                <td className="px-3 py-3 text-right" data-testid="so-officer-total-w2">{money(totals.w2)}</td>
                <td className="px-3 py-3 text-right border-l border-[#E2E8F0] dark:border-[#27272A]" data-testid="so-officer-total-dd">{money(totals.w9_direct_deposit)}</td>
                <td className="px-3 py-3 text-right" data-testid="so-officer-total-zelle">{money(totals.w9_zelle)}</td>
                <td className="px-3 py-3 text-right" data-testid="so-officer-total-w9">{money(totals.w9_total)}</td>
                <td className="px-3 py-3 text-right border-l border-[#E2E8F0] dark:border-[#27272A]" data-testid="so-officer-grand-total">{money(totals.grand_total)}</td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {dialogOpen && (
        <PaymentDialog
          open={dialogOpen} setOpen={setDialogOpen}
          client={officer.client}
          fixedOfficer={officer}
          editingRecord={editingRecord}
          onSaved={() => { setDialogOpen(false); load(range); }}
        />
      )}
    </div>
  );
};

/* --------------------------- Add / Edit dialog --------------------------- */
const PaymentDialog = ({ open, setOpen, client, fixedOfficer, editingRecord, onSaved }) => {
  const [form, setForm] = useState(emptyPayForm());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (editingRecord) {
      setForm({
        officer: fixedOfficer,
        w2: normComp(editingRecord.w2),
        w9_direct_deposit: normComp(editingRecord.w9_direct_deposit),
        w9_zelle: normComp(editingRecord.w9_zelle),
      });
    } else {
      setForm({ ...emptyPayForm(), officer: fixedOfficer || null });
    }
  }, [editingRecord, fixedOfficer, open]);

  const setComp = (row, patch) => setForm((prev) => ({ ...prev, [row]: { ...prev[row], ...patch } }));

  const save = async () => {
    if (!form.officer) { toast.error('Select a Security Officer'); return; }
    const amounts = [form.w2.amount, form.w9_direct_deposit.amount, form.w9_zelle.amount]
      .map((a) => Number(a) || 0);
    if (amounts.every((a) => a <= 0)) {
      toast.error('Enter an amount for at least one payment type');
      return;
    }
    setSaving(true);
    try {
      const body = {
        officer_id: form.officer.id,
        w2: toPayload(form.w2),
        w9_direct_deposit: toPayload(form.w9_direct_deposit),
        w9_zelle: toPayload(form.w9_zelle),
      };
      if (editingRecord) await api.put(`/so-payments/records/${editingRecord.id}`, body);
      else await api.post('/so-payments/records', body);
      toast.success(editingRecord ? 'Payment updated' : 'Payment saved');
      onSaved();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="so-payment-dialog">
        <DialogHeader>
          <DialogTitle>{editingRecord ? 'Update Payment' : 'Add New Payment'}</DialogTitle>
          <DialogDescription>Client: {client?.name} · Record the W2 and W9 payments for a Security Officer.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label>Security Officer *</Label>
            {fixedOfficer ? (
              <div className="mt-1 px-3 py-2 rounded-md border border-[#E2E8F0] dark:border-[#27272A] bg-[#F8FAFC] dark:bg-[#27272A] text-sm" data-testid="so-officer-fixed">
                {form.officer?.name} · <span className="font-mono">{form.officer?.officer_code || '—'}</span>
              </div>
            ) : (
              <OfficerSearch
                clientId={client?.id}
                selected={form.officer}
                onSelect={(o) => setForm((prev) => ({ ...prev, officer: o }))}
              />
            )}
          </div>

          <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg overflow-hidden">
            <table className="w-full text-sm" data-testid="so-payment-rows">
              <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-xs uppercase tracking-wider text-[#64748B]">
                <tr>
                  <th className="px-3 py-2 text-left">Payment Type</th>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                <PayRow label="W2" testid="w2" comp={form.w2} onChange={(p) => setComp('w2', p)} />
                <PayRow label="W9 — Direct Deposit" testid="dd" comp={form.w9_direct_deposit} onChange={(p) => setComp('w9_direct_deposit', p)} />
                <PayRow label="W9 — Zelle Transfer" testid="zelle" comp={form.w9_zelle} onChange={(p) => setComp('w9_zelle', p)} />
              </tbody>
            </table>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="so-payment-submit">
            {saving ? 'Saving…' : (editingRecord ? 'Update' : 'Submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const PayRow = ({ label, testid, comp, onChange }) => (
  <tr>
    <td className="px-3 py-2 font-medium text-[#0F172A] dark:text-[#FAFAFA] whitespace-nowrap">{label}</td>
    <td className="px-3 py-2">
      <Input type="date" value={comp.date || ''} onChange={(e) => onChange({ date: e.target.value })}
        className="h-9" data-testid={`so-${testid}-date`} />
    </td>
    <td className="px-3 py-2">
      <Input type="number" step="0.01" min="0" value={comp.amount ?? ''} onChange={(e) => onChange({ amount: e.target.value })}
        placeholder="0.00" className="h-9 text-right" data-testid={`so-${testid}-amount`} />
    </td>
  </tr>
);

/* Searchable officer picker (by name, code, email, phone, SSC) */
const OfficerSearch = ({ clientId, selected, onSelect }) => {
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let dead = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get('/so-payments/officers/search', { params: { client_id: clientId, q } });
        if (!dead) setResults(data || []);
      } catch (e) { if (!dead) setResults([]); }
      finally { if (!dead) setLoading(false); }
    }, 250);
    return () => { dead = true; clearTimeout(t); };
  }, [q, open, clientId]);

  return (
    <div className="relative">
      <Input
        value={selected ? `${selected.name} · ${selected.officer_code || ''}` : q}
        onChange={(e) => { onSelect(null); setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="Search by name, code, email or phone..."
        data-testid="so-officer-search-input"
        autoComplete="off"
      />
      {open && !selected && (
        <div className="absolute z-50 mt-1 w-full max-h-64 overflow-y-auto rounded-md border border-[#E2E8F0] dark:border-[#27272A] bg-white dark:bg-[#18181B] shadow-lg"
          data-testid="so-officer-results">
          {loading && <div className="px-3 py-2 text-sm text-[#64748B]">Searching…</div>}
          {!loading && results.length === 0 && <div className="px-3 py-2 text-sm text-[#64748B]">No officers found.</div>}
          {results.map((o) => (
            <button key={o.id} type="button"
              onClick={() => { onSelect(o); setOpen(false); }}
              className="w-full text-left px-3 py-2 hover:bg-[#F8FAFC] dark:hover:bg-[#27272A] text-sm"
              data-testid={`so-officer-option-${o.id}`}>
              <div className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{o.name} <span className="font-mono text-xs text-[#64748B]">{o.officer_code}</span></div>
              <div className="text-xs text-[#64748B]">
                {[o.email, o.contact_number, o.social_security_code].filter(Boolean).join(' · ') || '—'}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

function normComp(c) {
  c = c || {};
  return {
    date: c.date || '',
    amount: (c.amount ?? '') === '' ? '' : String(c.amount),
  };
}
function toPayload(c) {
  return { date: c.date || null, amount: Number(c.amount) || 0 };
}

function _saveBlob(blob, filename, type) {
  const url = URL.createObjectURL(new Blob([blob], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default PaymentSOPage;
