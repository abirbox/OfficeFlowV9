import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from '@/components/ui/sonner';
import { Download, FileText, FileSpreadsheet, ChevronRight, Trash2, Plus } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { formatPin } from './_shared';
import { todayIso, dhakaDateIso, formatDateTime } from '@/lib/datetime';

const isoToday = () => todayIso();
const isoDaysAgo = (n) => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - n);
  return dhakaDateIso(d);
};

// Dispatch financial values use USD.
const formatCurrency = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return `$${n.toFixed(2)}`;
};

const FINANCIAL_KEYS = new Set([
  'duty_rate',
  'billing_rate',
  'cost_amount',
  'billing_amount',
  'margin',
  'hourly_rate',
  'total',
  'total_amount',
]);

const REPORT_TABS = [
  { key: 'schedules', label: 'Schedules', endpoint: '/dispatch/reports/schedules',
    columns: [
      { key: 'date', label: 'Date' }, { key: 'officer_name', label: 'Officer' },
      { key: 'post_pin_display', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
      { key: 'client_name', label: 'Client' }, { key: 'vendor_name', label: 'Vendor' },
      { key: 'shift_type', label: 'Shift' }, { key: 'start_time', label: 'Start' }, { key: 'end_time', label: 'End' },
      { key: 'duty_hours', label: 'Hours' }, { key: 'completed_hours', label: 'Paid Hrs' },
      { key: 'confirmation_status', label: 'Confirmation' },
      { key: 'shift_status', label: 'Status' },
    ],
    financialColumns: [{ key: 'duty_rate', label: 'Duty Rate' }, { key: 'cost_amount', label: 'Payout' }, { key: 'billing_rate', label: 'Billing' }, { key: 'work_order_number', label: 'W.O.' }] },
  { key: 'by-officer', label: 'By Officer', endpoint: '/dispatch/reports/by-officer',
    columns: [
      { key: 'officer_name', label: 'Officer' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' },
      { key: 'total_hours', label: 'Paid Hrs' }, { key: 'attendance_pct', label: 'Attendance %' },
    ],
    financialColumns: [{ key: 'cost_amount', label: 'Payout' }, { key: 'billing_amount', label: 'Billing' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-post-site', label: 'By Post Site', endpoint: '/dispatch/reports/by-post-site',
    columns: [
      { key: 'post_pin_display', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
      { key: 'required_officers', label: 'Required' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' },
      { key: 'total_hours', label: 'Paid Hrs' },
      { key: 'coverage_pct', label: 'Coverage %' },
    ],
    financialColumns: [{ key: 'cost_amount', label: 'Payout' }, { key: 'billing_amount', label: 'Billing' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-client', label: 'By Client', endpoint: '/dispatch/reports/by-client',
    columns: [
      { key: 'client_name', label: 'Client' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' },
      { key: 'total_hours', label: 'Paid Hrs' },
    ],
    financialColumns: [{ key: 'cost_amount', label: 'Payout' }, { key: 'billing_amount', label: 'Billing' }, { key: 'margin', label: 'Margin' }] },
  { key: 'by-vendor', label: 'By Vendor', endpoint: '/dispatch/reports/by-vendor',
    columns: [
      { key: 'vendor_name', label: 'Vendor' }, { key: 'total_shifts', label: 'Shifts' },
      { key: 'completed', label: 'Completed' },
      { key: 'total_hours', label: 'Paid Hrs' },
    ],
    financialColumns: [{ key: 'cost_amount', label: 'Payout' }, { key: 'billing_amount', label: 'Billing' }, { key: 'margin', label: 'Margin' }] },
];

const SEARCH_PLACEHOLDER = {
  'schedules': 'Search officer, client, vendor, post pin…',
  'by-officer': 'Search officer name, email, phone…',
  'by-post-site': 'Search post pin, site name, address…',
  'by-client': 'Search client name or code…',
  'by-vendor': 'Search vendor name or code…',
};

const DispatchReportsPage = () => {
  const { user } = useAuthStore();
  const canView = hasPermission(user, 'dispatch.reports.view');
  const canExport = hasPermission(user, 'dispatch.reports.export');
  const canFinancial = hasPermission(user, 'dispatch.financial.view');
  const canAdjust = hasPermission(user, 'dispatch.financial.adjust');
  const canDelete = hasPermission(user, 'dispatch.schedule.delete');

  const [active, setActive] = useState('schedules');
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(6));
  const [dateTo, setDateTo] = useState(isoToday());
  const [limit, setLimit] = useState(50);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [data, setData] = useState({ items: [], count: 0 });
  const [loading, setLoading] = useState(false);

  // Debounce the search input so we do not slam the backend on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const cfg = REPORT_TABS.find((t) => t.key === active);

  // Map report tab key → entity_type for the drill-down detail dialog
  const ENTITY_TYPE_BY_TAB = { 'by-officer': 'officer', 'by-post-site': 'post_site', 'by-client': 'client', 'by-vendor': 'vendor' };
  const ENTITY_ID_KEY = { 'by-officer': 'officer_id', 'by-post-site': 'post_site_id', 'by-client': 'client_id', 'by-vendor': 'vendor_id' };
  const ENTITY_NAME_KEY = { 'by-officer': 'officer_name', 'by-post-site': 'post_site_name', 'by-client': 'client_name', 'by-vendor': 'vendor_name' };

  const [detail, setDetail] = useState(null); // { entity_type, entity_id, data }
  const [detailLoading, setDetailLoading] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickedCols, setPickedCols] = useState([]);
  const [clientFilter, setClientFilter] = useState(''); // officer-only: filter shifts by client
  const [advance, setAdvance] = useState({
    entries: [],
    total_advanced: 0,
    total_repaid: 0,
    remaining_balance: 0,
    period_taken: 0,
    period_repaid: 0,
  });
  const [advLoading, setAdvLoading] = useState(false);
  const [advSaving, setAdvSaving] = useState(false);
  const [advDialog, setAdvDialog] = useState(null); // 'advance' | 'repayment'
  const [advAmount, setAdvAmount] = useState('');
  const [advDate, setAdvDate] = useState('');
  const [advNote, setAdvNote] = useState('');
  const [extraRows, setExtraRows] = useState([]); // [{date, purpose, amount}]
  const [deductionRows, setDeductionRows] = useState([]); // [{date, purpose, amount}]
  const [adjSaving, setAdjSaving] = useState(false);
  const [savedRecords, setSavedRecords] = useState([]); // saved payslip PDF records
  const [genLoading, setGenLoading] = useState(false);
  const [editingRecordId, setEditingRecordId] = useState(null); // record being modified
  const [scheduleEdits, setScheduleEdits] = useState({}); // id -> {duty_hours, duty_rate}
  const [savingEdits, setSavingEdits] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null); // { id, date, officer_name, ... }
  const [deleting, setDeleting] = useState(false);

  const confirmDelete = async () => {
    if (!pendingDelete?.id) return;
    setDeleting(true);
    try {
      await api.delete(`/dispatch/schedules/${pendingDelete.id}`);
      toast.success('Dispatch report deleted');
      setPendingDelete(null);
      await load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to delete');
    } finally {
      setDeleting(false);
    }
  };

  const fetchDetail = useCallback(async (entity_type, entity_id, cid) => {
    setDetailLoading(true);
    try {
      const params = { entity_type, entity_id, date_from: dateFrom, date_to: dateTo };
      if (cid) params.client_id = cid;
      const { data } = await api.get('/dispatch/reports/entity-detail', { params });
      setDetail((d) => ({ ...(d || { entity_type, entity_id }), data }));
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setDetailLoading(false); }
  }, [dateFrom, dateTo]);


  const openDetail = async (row) => {
    const entity_type = ENTITY_TYPE_BY_TAB[active];
    const entity_id = row[ENTITY_ID_KEY[active]];

    if (!entity_type || !entity_id) return;

    setDetail({
      entity_type,
      entity_id,
      entity_name: row[ENTITY_NAME_KEY[active]],
    });

    setClientFilter('');

    // Initialize picker with ALL allowed columns
    const allKeys = [
      ...ENTITY_EXPORT_COLS.map(c => c.key),
      ...(canFinancial ? ENTITY_EXPORT_COLS_FIN.map(c => c.key) : []),
    ];

    setPickedCols(allKeys);

    await fetchDetail(entity_type, entity_id, '');
  };

  // Re-fetch when the officer/client filter changes
  useEffect(() => {
    if (detail && detail.entity_type === 'officer') {
      fetchDetail(
        detail.entity_type,
        detail.entity_id,
        clientFilter
      );
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientFilter]);

  const isOfficerPayslip =
    detail?.entity_type === 'officer' &&
    detail?.data?.client_info;

  const paidHoursTotal =
    detail?.data?.summary?.total_duty_hours ?? 0;

  const actualHoursTotal =
    detail?.data?.summary?.total_actual_hours ?? 0;

  const totalAmount =
    detail?.data?.summary?.total_amount ?? 0;

  const payslipClientId =
    detail?.data?.client_info?.id || clientFilter || '';

  const periodTaken = Number(advance.period_taken || 0);
  const periodRepaid = Number(advance.period_repaid || 0);
  const extraTotal = extraRows.reduce((s, r) => s + (Number(r.amount) || 0), 0);
  const deductionTotal = deductionRows.reduce((s, r) => s + (Number(r.amount) || 0), 0);

  const netPayment =
    Number(totalAmount) + extraTotal - deductionTotal;



  const loadAdvance = useCallback(async () => {
    if (detail?.entity_type !== 'officer' || !detail?.entity_id) return;
    const cid = detail?.data?.client_info?.id || clientFilter || '';
    if (!cid) {
      setAdvance({ entries: [], total_advanced: 0, total_repaid: 0, remaining_balance: 0, period_taken: 0, period_repaid: 0 });
      return;
    }
    setAdvLoading(true);
    try {
      const { data } = await api.get('/dispatch/advance-salary', {
        params: { officer_id: detail.entity_id, client_id: cid, date_from: dateFrom, date_to: dateTo },
      });
      setAdvance({
        entries: data?.entries || [],
        total_advanced: Number(data?.total_advanced || 0),
        total_repaid: Number(data?.total_repaid || 0),
        remaining_balance: Number(data?.remaining_balance || 0),
        period_taken: Number(data?.period_taken || 0),
        period_repaid: Number(data?.period_repaid || 0),
      });
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to load advance salary');
    } finally {
      setAdvLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.entity_type, detail?.entity_id, detail?.data?.client_info?.id, clientFilter, dateFrom, dateTo]);

  useEffect(() => {
    if (detail?.entity_type === 'officer') {
      loadAdvance();
    } else {
      setAdvance({ entries: [], total_advanced: 0, total_repaid: 0, remaining_balance: 0, period_taken: 0, period_repaid: 0 });
    }
  }, [detail?.entity_type, detail?.entity_id, loadAdvance]);

  // Fresh payslip open: extra/deduction editors start EMPTY (never persisted
  // unless a PDF record is generated). Schedule edits are seeded from the rows.
  const payslipIdentity = `${detail?.entity_id || ''}|${detail?.data?.client_info?.id || ''}|${dateFrom}|${dateTo}`;
  useEffect(() => {
    setExtraRows([]);
    setDeductionRows([]);
    setEditingRecordId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payslipIdentity]);

  // Seed the editable hours/rate map whenever the payslip rows load.
  useEffect(() => {
    const items = detail?.data?.items || [];
    const map = {};
    items.forEach((r) => {
      map[r.id] = {
        duty_hours: r.duty_hours != null ? String(r.duty_hours) : '',
        duty_rate: r.hourly_rate != null ? String(r.hourly_rate) : (r.duty_rate != null ? String(r.duty_rate) : ''),
      };
    });
    setScheduleEdits(map);
  }, [detail?.data?.items]);

  const openAdvanceDialog = (type) => {
    setAdvDialog(type);
    setAdvAmount('');
    setAdvNote('');
    setAdvDate(isoToday());
  };

  const closeAdvanceDialog = () => {
    if (advSaving) return;
    setAdvDialog(null);
    setAdvAmount('');
    setAdvNote('');
    setAdvDate('');
  };

  const saveAdvance = async () => {
    const amount = Number(advAmount);
    if (!Number.isFinite(amount) || amount <= 0) { toast.error('Enter a valid amount'); return; }
    if (!advDate) { toast.error('Select a date'); return; }
    const cid = payslipClientId;
    if (!cid) { toast.error('Select a client first'); return; }
    if (advDialog === 'repayment' && amount > Number(advance.remaining_balance || 0) + 0.001) {
      toast.error(`Repayment cannot exceed the balance of ${formatCurrency(advance.remaining_balance)}`);
      return;
    }
    setAdvSaving(true);
    try {
      await api.post('/dispatch/advance-salary', {
        officer_id: detail.entity_id,
        client_id: cid,
        type: advDialog,
        amount,
        entry_date: advDate,
        note: advNote.trim(),
      });
      toast.success(advDialog === 'advance' ? 'Advance recorded' : 'Repayment recorded');
      closeAdvanceDialog();
      await loadAdvance();
      await fetchDetail(detail.entity_type, detail.entity_id, clientFilter);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to save entry');
    } finally {
      setAdvSaving(false);
    }
  };

  const deleteAdvanceEntry = async (id) => {
    try {
      await api.delete(`/dispatch/advance-salary/${id}`);
      toast.success('Entry deleted');
      await loadAdvance();
      await fetchDetail(detail.entity_type, detail.entity_id, clientFilter);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to delete entry');
    }
  };

  const addExtraRow = () => setExtraRows((rows) => [...rows, { date: isoToday(), purpose: '', amount: '' }]);
  const updateExtraRow = (idx, field, value) =>
    setExtraRows((rows) => rows.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  const removeExtraRow = (idx) => setExtraRows((rows) => rows.filter((_, i) => i !== idx));

  const addDeductionRow = () => setDeductionRows((rows) => [...rows, { date: isoToday(), purpose: '', amount: '' }]);
  const updateDeductionRow = (idx, field, value) =>
    setDeductionRows((rows) => rows.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  const removeDeductionRow = (idx) => setDeductionRows((rows) => rows.filter((_, i) => i !== idx));

  const collectPayslipPayload = () => {
    const payloadRows = extraRows
      .map((r) => ({ date: r.date || '', purpose: (r.purpose || '').trim(), amount: Number(r.amount) || 0 }))
      .filter((r) => r.amount !== 0 || r.purpose || r.date);
    const payloadDeductions = deductionRows
      .map((r) => ({ date: r.date || '', purpose: (r.purpose || '').trim(), amount: Number(r.amount) || 0 }))
      .filter((r) => r.amount !== 0 || r.purpose || r.date);
    return { payloadRows, payloadDeductions };
  };

  const loadSavedRecords = useCallback(async () => {
    if (detail?.entity_type !== 'officer' || !detail?.entity_id) return;
    const cid = detail?.data?.client_info?.id || clientFilter || '';
    try {
      const params = { officer_id: detail.entity_id };
      if (cid) params.client_id = cid;
      const { data } = await api.get('/dispatch/payslip-records', { params });
      setSavedRecords(Array.isArray(data) ? data : []);
    } catch (e) {
      // Non-fatal; keep list empty
      setSavedRecords([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail?.entity_type, detail?.entity_id, detail?.data?.client_info?.id, clientFilter]);

  useEffect(() => {
    if (detail?.entity_type === 'officer') loadSavedRecords();
    else setSavedRecords([]);
  }, [detail?.entity_type, detail?.entity_id, loadSavedRecords]);

  // Generate the payslip PDF AND save it as a record (extra/deductions baked in).
  const generatePayslip = async () => {
    const cid = payslipClientId;
    if (!cid) { toast.error('Select a client first'); return; }
    const { payloadRows, payloadDeductions } = collectPayslipPayload();
    setGenLoading(true);
    try {
      const { data } = await api.post('/dispatch/payslip-records', {
        officer_id: detail.entity_id,
        client_id: cid,
        date_from: dateFrom,
        date_to: dateTo,
        extra_payments: payloadRows,
        deductions: payloadDeductions,
      });
      toast.success('Payslip generated & saved');
      await loadSavedRecords();
      if (data?.id) {
        window.open(`/api/dispatch/payslip-records/${data.id}/pdf`, '_blank');
      }
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to generate payslip');
    } finally {
      setGenLoading(false);
    }
  };

  // Open a saved record for modification: pre-fill extra/deduction editors.
  const openSavedRecord = async (rec) => {
    try {
      const { data } = await api.get(`/dispatch/payslip-records/${rec.id}`);
      setExtraRows((data.extra_payments || []).map((r) => ({
        date: r.date || '', purpose: r.purpose || '', amount: r.amount != null ? String(r.amount) : '',
      })));
      setDeductionRows((data.deductions || []).map((r) => ({
        date: r.date || '', purpose: r.purpose || '', amount: r.amount != null ? String(r.amount) : '',
      })));
      setEditingRecordId(rec.id);
      toast.success('Loaded saved payslip — edit and regenerate to update');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to open saved payslip');
    }
  };

  const deleteSavedRecord = async (rec) => {
    try {
      await api.delete(`/dispatch/payslip-records/${rec.id}`);
      toast.success('Saved payslip deleted');
      if (editingRecordId === rec.id) setEditingRecordId(null);
      await loadSavedRecords();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to delete');
    }
  };

  const updateScheduleEdit = (id, field, value) =>
    setScheduleEdits((m) => ({ ...m, [id]: { ...(m[id] || {}), [field]: value } }));

  const dirtyScheduleRows = () => {
    const items = detail?.data?.items || [];
    return items.filter((r) => {
      const e = scheduleEdits[r.id] || {};
      const origH = r.duty_hours != null ? String(r.duty_hours) : '';
      const origR = r.hourly_rate != null ? String(r.hourly_rate) : (r.duty_rate != null ? String(r.duty_rate) : '');
      return (e.duty_hours ?? origH) !== origH || (e.duty_rate ?? origR) !== origR;
    });
  };

  const saveScheduleEdits = async () => {
    const dirty = dirtyScheduleRows();
    if (dirty.length === 0) { toast('No changes to save'); return; }
    setSavingEdits(true);
    try {
      for (const r of dirty) {
        const e = scheduleEdits[r.id] || {};
        const body = {};
        if (e.duty_hours !== undefined && e.duty_hours !== '') body.duty_hours = Number(e.duty_hours);
        if (e.duty_rate !== undefined && e.duty_rate !== '') body.duty_rate = Number(e.duty_rate);
        await api.put(`/dispatch/schedules/${r.id}`, body);
      }
      toast.success(`Updated ${dirty.length} shift(s) on the schedule`);
      await fetchDetail(detail.entity_type, detail.entity_id, clientFilter);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || 'Failed to save shift edits');
    } finally {
      setSavingEdits(false);
    }
  };

  const downloadAdvanceStatement = async () => {
    try {
      const params = { officer_id: detail.entity_id };
      if (payslipClientId) params.client_id = payslipClientId;
      const res = await api.get('/dispatch/advance-salary/statement', { params, responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `advance-statement-${detail.entity_name || detail.entity_id}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success('Advance statement downloaded');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || 'Failed to download statement');
    }
  };

  const MIME_BY_FMT = {
  csv: 'text/csv',
  pdf: 'application/pdf',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
};

const downloadEntityDetail = async (fmt, opts = {}) => {
    try {
      const params = {
        entity_type: detail.entity_type,
        entity_id: detail.entity_id,
        date_from: dateFrom,
        date_to: dateTo,
        format: fmt,
      };
      if (detail.entity_type === 'officer' && clientFilter) params.client_id = clientFilter;
      if (opts.template) params.template = opts.template;
      if (opts.columns) params.columns = opts.columns;
      const res = await api.get('/dispatch/reports/export/entity-detail', { params, responseType: 'blob' });
      const blob = new Blob([res.data], { type: MIME_BY_FMT[fmt] || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const label = opts.template === 'payslip' ? 'payslip' : detail.entity_type;
      a.download = `${label}-${detail.entity_name || detail.entity_id}-${dateFrom}-${dateTo}.${fmt}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${fmt === 'xlsx' ? 'Excel' : fmt.toUpperCase()} downloaded`);
    } catch (e) {
      console.error('Payslip/export failed:', e);
      toast.error(
        formatApiErrorDetail(e.response?.data?.detail) ||
        e.message ||
        'Export failed'
      );
    }
  };

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    try {
      const params = { date_from: dateFrom, date_to: dateTo };
      if (active === 'schedules') params.limit = limit;
      if (debouncedQuery) params.q = debouncedQuery;
      const { data } = await api.get(cfg.endpoint, { params });
      setData(data);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [active, dateFrom, dateTo, limit, debouncedQuery, cfg.endpoint, canView]);

  useEffect(() => { load(); }, [load]);

  const download = async (format) => {
    try {
      const params = { type: active, format, date_from: dateFrom, date_to: dateTo };
      if (debouncedQuery) params.q = debouncedQuery;
      const res = await api.get('/dispatch/reports/export', { params, responseType: 'blob' });
      const blob = new Blob([res.data], { type: MIME_BY_FMT[format] || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `dispatch-${active}-${dateFrom}-${dateTo}.${format}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${format === 'xlsx' ? 'Excel' : format.toUpperCase()} downloaded`);
    } catch (e) {
      // blob errors need decoding
      try {
        const text = await e.response?.data?.text?.();
        const detail = text ? JSON.parse(text).detail : null;
        toast.error(detail || 'Export failed');
      } catch { toast.error('Export failed'); }
    }
  };

  if (!canView) return <div className="p-8 text-[#64748B]" data-testid="reports-no-access">You do not have permission to view Dispatch reports.</div>;

  const cols = [...cfg.columns, ...(canFinancial ? cfg.financialColumns : [])];

  return (
    <div className="space-y-6" data-testid="dispatch-reports-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Wage Report</h1>
          <p className="text-sm text-[#64748B] mt-1">
            {data.count} record{data.count !== 1 && 's'} · Financial data {canFinancial ? 'visible' : 'hidden'}
          </p>
        </div>
        {canExport && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => download('xlsx')} data-testid="export-excel">
              <FileSpreadsheet className="w-4 h-4 mr-2" /> Export Excel
            </Button>
            <Button variant="outline" size="sm" onClick={() => download('pdf')} data-testid="export-pdf">
              <FileText className="w-4 h-4 mr-2" /> Export PDF
            </Button>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="md:col-span-2">
          <Label className="text-xs">Search</Label>
          <div className="relative">
            <Input
              type="text"
              placeholder={SEARCH_PLACEHOLDER[active] || 'Search…'}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pr-8"
              data-testid="rf-search"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#FAFAFA] text-lg leading-none"
                aria-label="Clear search"
                data-testid="rf-search-clear"
              >×</button>
            )}
          </div>
        </div>
        <div><Label className="text-xs">Date From</Label><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} data-testid="rf-from" /></div>
        <div><Label className="text-xs">Date To</Label><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} data-testid="rf-to" /></div>
        {active === 'schedules' && (
          <div><Label className="text-xs">Limit</Label>
            <Select value={String(limit)} onValueChange={(v) => setLimit(Number(v))}>
              <SelectTrigger data-testid="rf-limit"><SelectValue /></SelectTrigger>
              <SelectContent>{[50, 100, 250, 500, 1000].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        )}
        <div className="md:col-span-4 flex items-center justify-between text-xs text-[#64748B]">
          <span>Paid hours = shifts once <b>Clocked In</b>. Payout = paid hours × officer duty rate.</span>
          <span>Max 3 months (92 days).</span>
        </div>
      </div>

      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="grid grid-cols-5 max-w-2xl">
          {REPORT_TABS.map((t) => <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`}>{t.label}</TabsTrigger>)}
        </TabsList>
        {REPORT_TABS.map((t) => (
          <TabsContent key={t.key} value={t.key} className="mt-4">
            <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
                  <tr>
                    {cols.map((c) => <th key={c.key} className="px-3 py-3">{c.label}</th>)}
                    {t.key === 'schedules' && canDelete && <th className="px-3 py-3 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                  {loading ? <tr><td colSpan={cols.length + (t.key === 'schedules' && canDelete ? 1 : 0)} className="px-4 py-8 text-center text-[#64748B]">Loading…</td></tr>
                  : (data.items || []).length === 0 ? <tr><td colSpan={cols.length + (t.key === 'schedules' && canDelete ? 1 : 0)} className="px-4 py-8 text-center text-[#64748B]">No data</td></tr>
                  : data.items.map((r, i) => {
                    const clickable = ENTITY_TYPE_BY_TAB[t.key];
                    return (
                    <tr
                      key={r.id || `${r.officer_id || r.client_id || r.vendor_id || r.post_site_id || i}`}
                      data-testid={`report-row-${i}`}
                      className={clickable ? 'hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F11] cursor-pointer' : ''}
                      onClick={
                        clickable
                          ? () => openDetail(r)
                          : undefined
                      }
                    >
                      {cols.map((c, j) => (
                        <td key={c.key} className="px-3 py-2 text-[#334155] dark:text-[#E4E4E7]">
                          {j === 0 && clickable ? (
                            <span className="text-[#4F46E5] hover:underline font-medium inline-flex items-center gap-1">
                              {r[c.key] ?? '—'} <ChevronRight className="w-3 h-3" />
                            </span>
                          ) : FINANCIAL_KEYS.has(c.key)
                            ? formatCurrency(r[c.key])
                            : (r[c.key] ?? '—')}
                        </td>
                      ))}
                      {t.key === 'schedules' && canDelete && (
                        <td className="px-3 py-2 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-[#DC2626] hover:text-[#B91C1C] hover:bg-rose-50 dark:hover:bg-rose-950/30 h-8 px-2"
                            onClick={(e) => { e.stopPropagation(); setPendingDelete(r); }}
                            data-testid={`delete-report-btn-${i}`}
                            aria-label="Delete dispatch report"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </td>
                      )}
                    </tr>
                  );})}
                </tbody>
              </table>
            </div>
          </TabsContent>
        ))}
      </Tabs>

      {/* Entity Detail Dialog — day-by-day breakdown */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) { setDetail(null); setPickerOpen(false); setClientFilter(''); setExtraRows([]); setDeductionRows([]); setEditingRecordId(null); setSavedRecords([]); } }}>
        <DialogContent className="max-w-6xl max-h-[92vh] overflow-y-auto" data-testid="entity-detail-dialog">
          <DialogHeader>
            <DialogTitle>
              {detail?.entity_type === 'officer' ? 'Officer Payslip' : `${detail?.entity_type?.replace('_', ' ')} Detail`} — {detail?.entity_name}
            </DialogTitle>
            <DialogDescription>
              Full day-by-day breakdown between {dateFrom} and {dateTo}. Paid hours & totals count once officers are Clocked In.
            </DialogDescription>
          </DialogHeader>
          {detailLoading ? <p className="text-sm text-[#64748B]">Loading detail…</p>
            : detail?.data && (
              <div className="space-y-4">
                {/* Client filter — officers only */}
                {detail.entity_type === 'officer' && (detail.data.clients_available || []).length > 0 && (
                  <div className="flex flex-wrap items-center gap-3">
                    <Label className="text-xs">Client</Label>
                    <Select value={clientFilter || '__all__'} onValueChange={(v) => setClientFilter(v === '__all__' ? '' : v)}>
                      <SelectTrigger className="w-64" data-testid="detail-client-filter"><SelectValue placeholder="All clients" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__all__">All clients</SelectItem>
                        {detail.data.clients_available.map((c) => (
                          <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-[#64748B]">Filter shifts by the client this officer worked for.</p>
                  </div>
                )}

                {/* Payslip-style header (officer + client selected) */}
                {isOfficerPayslip && (
                  <div className="rounded-xl border border-[#E2E8F0] dark:border-[#27272A] bg-white dark:bg-[#0F0F11] p-4" data-testid="payslip-header">
                    <div className="grid grid-cols-3 items-center gap-4">
                      <div className="flex items-start gap-3">
                        {detail.data.client_info.logo_url ? (
                          <img src={detail.data.client_info.logo_url} alt="client logo" className="w-16 h-16 object-contain rounded border border-[#E2E8F0] dark:border-[#27272A]" />
                        ) : (
                          <div className="w-16 h-16 rounded border border-dashed border-[#CBD5E1] flex items-center justify-center text-[10px] text-[#94A3B8]">Logo</div>
                        )}
                        <div className="space-y-1 text-xs">
                          <div><span className="text-[#64748B]">Security Officer's Name:</span> <span className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]" data-testid="payslip-officer-name">{detail.entity_name}</span></div>
                          <div><span className="text-[#64748B]">Duty Periods:</span> <span className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{dateFrom} to {dateTo}</span></div>
                        </div>
                      </div>
                      <div className="text-center">
                        <h2 className="text-xl md:text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA]" data-testid="payslip-client-name">{detail.data.client_info.name}</h2>
                        {detail.data.client_info.city && (
                          <p className="text-xs text-[#64748B]">{detail.data.client_info.city}</p>
                        )}
                      </div>
                      <div className="flex justify-end">
                        {canExport && (
                          <Button size="sm" onClick={generatePayslip} disabled={genLoading} data-testid="download-payslip-pdf">
                            <FileText className="w-4 h-4 mr-2" /> {genLoading ? 'Generating…' : 'Generate Payslip PDF'}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* Summary tiles */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(detail.data.summary || {}).map(([k, v]) => (
                    <div key={k} className="rounded-lg border border-[#E2E8F0] dark:border-[#27272A] p-3">
                      <p className="text-[10px] uppercase tracking-wider text-[#64748B]">{k.replace(/_/g, ' ')}</p>
                      <p className="text-lg font-bold text-[#0F172A] dark:text-[#FAFAFA]">
                        {FINANCIAL_KEYS.has(k) ? formatCurrency(v) : v}
                      </p>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Shifts ({detail.data.count})</h3>
                  <div className="flex gap-2">
                    {isOfficerPayslip && canFinancial && (
                      <Button size="sm" onClick={saveScheduleEdits} disabled={savingEdits} data-testid="save-shift-edits">
                        {savingEdits ? 'Saving…' : 'Save Shift Edits'}
                      </Button>
                    )}
                    {canExport && (
                      <Button size="sm" variant="outline" onClick={() => setPickerOpen(true)} data-testid="detail-pick-columns">
                        <Download className="w-4 h-4 mr-2" /> Choose columns & export
                      </Button>
                    )}
                  </div>
                </div>

                {/* Advance Salary */}
                {isOfficerPayslip && canFinancial && (
                  <div className="rounded-xl border border-[#E2E8F0] dark:border-[#27272A] bg-white dark:bg-[#0F0F11] p-4" data-testid="advance-salary">
                    <div className="flex items-center justify-between gap-3 mb-4">
                      <div>
                        <h3 className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">Advance Salary</h3>
                        <p className="text-xs text-[#64748B] mt-1">Advances taken and repayments for this officer with this client. Balance carries across payslips.</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {canExport && (
                          <Button type="button" variant="outline" onClick={downloadAdvanceStatement} data-testid="download-advance-statement">
                            <FileText className="w-4 h-4 mr-2" /> Download Statement
                          </Button>
                        )}
                        {canAdjust && (
                          <>
                            <Button type="button" variant="outline" onClick={() => openAdvanceDialog('advance')} data-testid="record-advance-button">Record Advance</Button>
                            <Button type="button" onClick={() => openAdvanceDialog('repayment')} disabled={Number(advance.remaining_balance || 0) <= 0} data-testid="record-repayment-button">Record Repayment</Button>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                      <div className="rounded-lg bg-[#F8FAFC] dark:bg-[#18181B] p-3">
                        <p className="text-[10px] uppercase tracking-wider text-[#64748B]">Total Advanced</p>
                        <p className="text-base font-bold">{formatCurrency(advance.total_advanced)}</p>
                      </div>
                      <div className="rounded-lg bg-[#F8FAFC] dark:bg-[#18181B] p-3">
                        <p className="text-[10px] uppercase tracking-wider text-[#64748B]">Total Repaid</p>
                        <p className="text-base font-bold">{formatCurrency(advance.total_repaid)}</p>
                      </div>
                      <div className="rounded-lg border-2 border-[#0F172A] dark:border-[#FAFAFA] p-3">
                        <p className="text-[10px] uppercase tracking-wider text-[#64748B]">Remaining Advance Balance</p>
                        <p className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]" data-testid="remaining-advance-balance">{formatCurrency(advance.remaining_balance)}</p>
                      </div>
                    </div>

                    <div className="rounded-lg border border-[#E2E8F0] dark:border-[#27272A] overflow-x-auto">
                      <div className="px-3 py-2 border-b border-[#E2E8F0] dark:border-[#27272A]"><h4 className="text-xs font-semibold">Transaction History</h4></div>
                      {advLoading ? (
                        <p className="p-4 text-xs text-[#64748B]">Loading…</p>
                      ) : advance.entries.length === 0 ? (
                        <p className="p-4 text-xs text-[#64748B]">No advance transactions recorded.</p>
                      ) : (
                        <table className="w-full text-xs min-w-[700px]">
                          <thead className="bg-[#F8FAFC] dark:bg-[#18181B]">
                            <tr>
                              <th className="px-3 py-2 text-left">Date</th>
                              <th className="px-3 py-2 text-left">Type</th>
                              <th className="px-3 py-2 text-left">Note</th>
                              <th className="px-3 py-2 text-right">Amount</th>
                              <th className="px-3 py-2 text-right">Balance</th>
                              {canAdjust && <th className="px-3 py-2 text-right">Actions</th>}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                            {advance.entries.map((entry) => (
                              <tr key={entry.id} data-testid={`advance-row-${entry.id}`}>
                                <td className="px-3 py-2">{entry.entry_date || '—'}</td>
                                <td className="px-3 py-2 font-semibold">{entry.type === 'advance' ? 'Advance Taken' : 'Repayment'}</td>
                                <td className="px-3 py-2">{entry.note || '—'}</td>
                                <td className="px-3 py-2 text-right font-semibold">{formatCurrency(entry.amount)}</td>
                                <td className="px-3 py-2 text-right font-semibold">{formatCurrency(entry.balance_after)}</td>
                                {canAdjust && (
                                  <td className="px-3 py-2 text-right">
                                    <Button variant="ghost" size="sm" className="text-[#DC2626] hover:text-[#B91C1C] h-7 px-2" onClick={() => deleteAdvanceEntry(entry.id)} data-testid={`delete-advance-${entry.id}`}><Trash2 className="w-3.5 h-3.5" /></Button>
                                  </td>
                                )}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>

                    {/* Payslip breakdown */}
                    <div className="mt-4 rounded-lg border border-[#E2E8F0] dark:border-[#27272A] p-4" data-testid="payslip-breakdown">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">Payslip Summary{editingRecordId ? ' · editing saved record' : ''}</h4>
                        {canExport && (
                          <Button size="sm" onClick={generatePayslip} disabled={genLoading} data-testid="generate-payslip">
                            <FileText className="w-4 h-4 mr-2" />{genLoading ? 'Generating…' : (editingRecordId ? 'Regenerate & Save' : 'Generate & Save Payslip PDF')}
                          </Button>
                        )}
                      </div>
                      <div className="space-y-2 text-sm max-w-2xl">
                        <div className="flex items-center justify-between"><span className="text-[#64748B]">Gross Pay</span><span className="font-semibold" data-testid="ps-gross">{formatCurrency(totalAmount)}</span></div>

                        {/* Extra payment rows */}
                        <div className="pt-1">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[#64748B]">Extra Payments</span>
                            {canAdjust && (
                              <Button size="sm" variant="outline" onClick={addExtraRow} data-testid="add-extra-field" className="h-7 px-2 text-xs">
                                <Plus className="w-3.5 h-3.5 mr-1" /> Add More Fields
                              </Button>
                            )}
                          </div>
                          {extraRows.length === 0 ? (
                            <p className="text-xs text-[#94A3B8]">No extra payments. {canAdjust ? 'Click “Add More Fields” to add one.' : ''}</p>
                          ) : (
                            <div className="space-y-2" data-testid="extra-payment-rows">
                              {extraRows.map((row, idx) => (
                                <div key={idx} className="flex flex-wrap items-center gap-2" data-testid={`extra-row-${idx}`}>
                                  {canAdjust ? (
                                    <>
                                      <Input type="date" value={row.date} onChange={(e) => updateExtraRow(idx, 'date', e.target.value)} className="h-8 w-40" data-testid={`extra-date-${idx}`} />
                                      <Input type="text" placeholder="Purpose" value={row.purpose} onChange={(e) => updateExtraRow(idx, 'purpose', e.target.value)} className="h-8 flex-1 min-w-[140px]" data-testid={`extra-purpose-${idx}`} />
                                      <Input type="number" min="0" step="0.01" placeholder="0.00" value={row.amount} onChange={(e) => updateExtraRow(idx, 'amount', e.target.value)} className="h-8 w-28 text-right" data-testid={`extra-amount-${idx}`} />
                                      <Button variant="ghost" size="sm" className="text-[#DC2626] hover:text-[#B91C1C] h-8 px-2" onClick={() => removeExtraRow(idx)} data-testid={`extra-remove-${idx}`}><Trash2 className="w-3.5 h-3.5" /></Button>
                                    </>
                                  ) : (
                                    <div className="flex w-full items-center justify-between">
                                      <span className="text-[#64748B]">{row.purpose || 'Extra Payment'}{row.date ? ` (${row.date})` : ''}</span>
                                      <span className="font-semibold">{formatCurrency(Number(row.amount) || 0)}</span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="flex items-center justify-between mt-2 text-xs">
                            <span className="text-[#64748B]">Extra Payments Total</span>
                            <span className="font-semibold" data-testid="ps-extra-total">{formatCurrency(extraTotal)}</span>
                          </div>
                        </div>

                        {/* Manual deduction rows (line items that reduce net pay) */}
                        <div className="pt-1">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[#64748B]">Deductions</span>
                            {canAdjust && (
                              <Button size="sm" variant="outline" onClick={addDeductionRow} data-testid="add-deduction-field" className="h-7 px-2 text-xs">
                                <Plus className="w-3.5 h-3.5 mr-1" /> Add Deduction
                              </Button>
                            )}
                          </div>
                          {deductionRows.length === 0 ? (
                            <p className="text-xs text-[#94A3B8]">No deductions. {canAdjust ? 'Click “Add Deduction” to add one.' : ''}</p>
                          ) : (
                            <div className="space-y-2" data-testid="deduction-rows">
                              {deductionRows.map((row, idx) => (
                                <div key={idx} className="flex flex-wrap items-center gap-2" data-testid={`deduction-row-${idx}`}>
                                  {canAdjust ? (
                                    <>
                                      <Input type="date" value={row.date} onChange={(e) => updateDeductionRow(idx, 'date', e.target.value)} className="h-8 w-40" data-testid={`deduction-date-${idx}`} />
                                      <Input type="text" placeholder="Label (e.g. Uniform, Loan)" value={row.purpose} onChange={(e) => updateDeductionRow(idx, 'purpose', e.target.value)} className="h-8 flex-1 min-w-[140px]" data-testid={`deduction-purpose-${idx}`} />
                                      <Input type="number" min="0" step="0.01" placeholder="0.00" value={row.amount} onChange={(e) => updateDeductionRow(idx, 'amount', e.target.value)} className="h-8 w-28 text-right" data-testid={`deduction-amount-${idx}`} />
                                      <Button variant="ghost" size="sm" className="text-[#DC2626] hover:text-[#B91C1C] h-8 px-2" onClick={() => removeDeductionRow(idx)} data-testid={`deduction-remove-${idx}`}><Trash2 className="w-3.5 h-3.5" /></Button>
                                    </>
                                  ) : (
                                    <div className="flex w-full items-center justify-between">
                                      <span className="text-[#64748B]">{row.purpose || 'Deduction'}{row.date ? ` (${row.date})` : ''}</span>
                                      <span className="font-semibold text-[#DC2626]">-{formatCurrency(Number(row.amount) || 0)}</span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="flex items-center justify-between mt-2 text-xs">
                            <span className="text-[#64748B]">Deductions Total</span>
                            <span className="font-semibold text-[#DC2626]" data-testid="ps-deduction-total">-{formatCurrency(deductionTotal)}</span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between border-t border-[#E2E8F0] dark:border-[#27272A] pt-2 mt-2"><span className="font-bold text-[#0F172A] dark:text-[#FAFAFA]">Net Payment</span><span className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]" data-testid="ps-net-payment">{formatCurrency(netPayment)}</span></div>
                        <div className="flex items-center justify-between"><span className="text-[#64748B]">Remaining Advance Balance</span><span className="font-semibold" data-testid="ps-remaining-balance">{formatCurrency(advance.remaining_balance)}</span></div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Saved payslip PDF records */}
                {isOfficerPayslip && (
                  <div className="rounded-lg border border-[#E2E8F0] dark:border-[#27272A] p-4" data-testid="saved-payslips">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[#64748B] mb-3">Saved Payslips</h4>
                    {savedRecords.length === 0 ? (
                      <p className="text-xs text-[#94A3B8]">No saved payslips yet. Add extra payments / deductions, then click “Generate &amp; Save Payslip PDF”.</p>
                    ) : (
                      <div className="space-y-2">
                        {savedRecords.map((rec) => (
                          <div key={rec.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#E2E8F0] dark:border-[#27272A] px-3 py-2 text-xs" data-testid={`saved-payslip-${rec.id}`}>
                            <div className="flex flex-col">
                              <span className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]">{rec.date_from} → {rec.date_to}</span>
                              <span className="text-[#64748B]">Net {formatCurrency(rec.net_payment)}{rec.generated_at ? ` · ${formatDateTime(rec.generated_at)}` : ''}</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button size="sm" variant="outline" onClick={() => window.open(`/api/dispatch/payslip-records/${rec.id}/pdf`, '_blank')} data-testid={`preview-payslip-${rec.id}`}>
                                <FileText className="w-3.5 h-3.5 mr-1" /> Preview / Download
                              </Button>
                              {canAdjust && (
                                <Button size="sm" variant="outline" onClick={() => openSavedRecord(rec)} data-testid={`modify-payslip-${rec.id}`}>Modify</Button>
                              )}
                              {canExport && (
                                <Button size="sm" variant="ghost" className="text-[#DC2626] hover:text-[#B91C1C]" onClick={() => deleteSavedRecord(rec)} data-testid={`delete-payslip-${rec.id}`}><Trash2 className="w-3.5 h-3.5" /></Button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}


                {/* Payslip-style table when we can identify one client for the officer */}
                {isOfficerPayslip ? (
                  <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg overflow-x-auto">
                    <table className="w-full text-xs min-w-[1100px]" data-testid="payslip-table">
                      <thead className="bg-[#FBE4EA] text-[#0F172A] uppercase tracking-wider">
                        <tr>
                          <th className="px-2 py-2 text-left">Date</th>
                          <th className="px-2 py-2 text-left">Shift</th>
                          <th className="px-2 py-2 text-left">Start Time</th>
                          <th className="px-2 py-2 text-left">End Time</th>
                          <th className="px-2 py-2 text-right">Duty Hours</th>
                          {canFinancial && <th className="px-2 py-2 text-right">Hourly Rate</th>}
                          {canFinancial && <th className="px-2 py-2 text-right">Total</th>}
                          <th className="px-2 py-2 text-left">Post Site Name</th>
                          <th className="px-2 py-2 text-left">City</th>
                          <th className="px-2 py-2 text-left">Post Site Pin</th>
                          <th className="px-2 py-2 text-left">Remarks</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                        {detail.data.items.map((r) => (
                          <tr key={r.id}>
                            <td className="px-2 py-2 bg-[#FBE4EA]/40 font-medium">{r.date}</td>
                            <td className="px-2 py-2">{r.shift_type || '—'}</td>
                            <td className="px-2 py-2 font-mono">{r.start_time || '—'}</td>
                            <td className="px-2 py-2 font-mono">{r.end_time || '—'}</td>
                            <td className="px-2 py-2 text-right">
                              {canFinancial ? (
                                <Input type="number" min="0" step="0.01" value={(scheduleEdits[r.id]?.duty_hours) ?? (r.duty_hours ?? '')} onChange={(e) => updateScheduleEdit(r.id, 'duty_hours', e.target.value)} className="h-7 w-20 text-right ml-auto" data-testid={`edit-hours-${r.id}`} />
                              ) : (r.duty_hours ?? '—')}
                            </td>
                            {canFinancial && (
                              <td className="px-2 py-2 text-right">
                                <Input type="number" min="0" step="0.01" value={(scheduleEdits[r.id]?.duty_rate) ?? (r.hourly_rate ?? '')} onChange={(e) => updateScheduleEdit(r.id, 'duty_rate', e.target.value)} className="h-7 w-24 text-right ml-auto" data-testid={`edit-rate-${r.id}`} />
                              </td>
                            )}
                            {canFinancial && <td className="px-2 py-2 text-right font-semibold" data-testid={`row-total-${r.id}`}>${((Number(scheduleEdits[r.id]?.duty_hours ?? r.duty_hours ?? 0)) * (Number(scheduleEdits[r.id]?.duty_rate ?? r.hourly_rate ?? 0))).toFixed(2)}</td>}
                            <td className="px-2 py-2">{r.post_site_name || '—'}</td>
                            <td className="px-2 py-2">{r.city || '—'}</td>
                            <td className="px-2 py-2 text-[#DC2626] font-semibold">{formatPin(r) || '—'}</td>
                            <td className="px-2 py-2 max-w-[220px] truncate" title={r.remarks || ''}>{r.remarks || '—'}</td>
                          </tr>
                        ))}
                        {detail.data.items.length === 0 && (
                          <tr><td colSpan={canFinancial ? 11 : 9} className="px-4 py-6 text-center text-[#64748B]">No shifts in this range</td></tr>
                        )}
                      </tbody>
                      {detail.data.items.length > 0 && (
                        <tfoot className="bg-[#F8FAFC] font-bold text-[#0F172A]" data-testid="payslip-totals">
                          <tr>
                            <td className="px-2 py-2" colSpan={4}>Totals</td>
                            <td className="px-2 py-2 text-right" data-testid="payslip-total-duty">{paidHoursTotal}</td>
                            {canFinancial && <td className="px-2 py-2" />}
                            {canFinancial && <td className="px-2 py-2 text-right" data-testid="payslip-total-amount">${Number(totalAmount).toFixed(2)}</td>}
                            <td className="px-2 py-2" colSpan={4} />
                          </tr>
                        </tfoot>
                      )}
                    </table>
                  </div>
                ) : (
                  <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg overflow-x-auto">
                    <table className="w-full text-xs min-w-[1200px]">
                      <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] uppercase tracking-wider text-[#64748B]">
                        <tr>
                          <th className="px-2 py-2 text-left">Date</th>
                          <th className="px-2 py-2 text-left">Shift</th>
                          <th className="px-2 py-2 text-left">Scheduled</th>
                          <th className="px-2 py-2 text-left">Clocked In</th>
                          <th className="px-2 py-2 text-left">Clocked Out</th>
                          <th className="px-2 py-2 text-left">Hours</th>
                          <th className="px-2 py-2 text-left">Post</th>
                          <th className="px-2 py-2 text-left">Officer</th>
                          <th className="px-2 py-2 text-left">Client / Vendor</th>
                          <th className="px-2 py-2 text-left">Confirmation</th>
                          <th className="px-2 py-2 text-left">Status</th>
                          <th className="px-2 py-2 text-left">Remarks</th>
                          {canFinancial && <>
                            <th className="px-2 py-2 text-left">Duty Rate</th>
                            <th className="px-2 py-2 text-left">Billing</th>
                            <th className="px-2 py-2 text-left">W.O.</th>
                          </>}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
                        {detail.data.items.map((r) => (
                          <tr key={r.id}>
                            <td className="px-2 py-2">{r.date}</td>
                            <td className="px-2 py-2">{r.shift_type}</td>
                            <td className="px-2 py-2 font-mono">{r.start_time}–{r.end_time}</td>
                            <td className="px-2 py-2 font-mono">{r.actual_check_in || '—'}</td>
                            <td className="px-2 py-2 font-mono">{r.actual_check_out || '—'}</td>
                            <td className="px-2 py-2">{r.duty_hours}h</td>
                            <td className="px-2 py-2">{formatPin(r) || '—'} {r.post_site_name ? `— ${r.post_site_name}` : ''}</td>
                            <td className="px-2 py-2">{r.officer_name}</td>
                            <td className="px-2 py-2">{r.client_name} / {r.vendor_name}</td>
                            <td className="px-2 py-2">{r.confirmation_status}{r.confirmation_method ? ` (${r.confirmation_method})` : ''}</td>
                            <td className="px-2 py-2">{r.shift_status}</td>
                            <td className="px-2 py-2 max-w-[220px] truncate" title={r.remarks || ''}>{r.remarks || '—'}</td>
                            {canFinancial && <>
                              <td className="px-2 py-2">{formatCurrency(r.duty_rate)}</td>
                              <td className="px-2 py-2">{formatCurrency(r.billing_rate)}</td>
                              <td className="px-2 py-2">{r.work_order_number ?? '—'}</td>
                            </>}
                          </tr>
                        ))}
                        {detail.data.items.length === 0 && (
                          <tr><td colSpan={20} className="px-4 py-6 text-center text-[#64748B]">No shifts in this range</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
        </DialogContent>
      </Dialog>

      {/* Column Picker dialog — used for entity-detail export */}
      <ColumnPickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        canFinancial={canFinancial}
        picked={pickedCols}
        onChange={setPickedCols}
        onExport={(fmt) => { downloadEntityDetail(fmt, { columns: pickedCols.join(',') || undefined }); setPickerOpen(false); }}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!pendingDelete} onOpenChange={(o) => !o && !deleting && setPendingDelete(null)}>
        <DialogContent className="max-w-md" data-testid="delete-report-dialog">
          <DialogHeader>
            <DialogTitle>Delete this dispatch report?</DialogTitle>
            <DialogDescription>
              This permanently removes the schedule
              {pendingDelete?.date ? ` on ${pendingDelete.date}` : ''}
              {pendingDelete?.officer_name ? ` for ${pendingDelete.officer_name}` : ''}
              {pendingDelete?.post_site_name ? ` at ${pendingDelete.post_site_name}` : ''}.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setPendingDelete(null)} disabled={deleting} data-testid="delete-report-cancel">
              Cancel
            </Button>
            <Button
              className="bg-[#DC2626] hover:bg-[#B91C1C] text-white"
              onClick={confirmDelete}
              disabled={deleting}
              data-testid="delete-report-confirm"
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Record Advance / Repayment Dialog */}
      <Dialog
        open={!!advDialog}
        onOpenChange={(open) => { if (!open) closeAdvanceDialog(); }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {advDialog === 'advance' ? 'Record Advance' : 'Record Repayment'}
            </DialogTitle>
            <DialogDescription>
              {advDialog === 'advance'
                ? 'Record an advance salary taken by this officer.'
                : "Record a repayment against the officer's outstanding advance balance."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <Label>Date</Label>
              <Input
                type="date"
                value={advDate}
                onChange={(e) => setAdvDate(e.target.value)}
                className="mt-1"
                disabled={advSaving}
                data-testid="advance-date"
              />
            </div>

            <div>
              <Label>Amount</Label>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={advAmount}
                onChange={(e) => setAdvAmount(e.target.value)}
                placeholder="0.00"
                className="mt-1"
                disabled={advSaving}
                data-testid="advance-amount"
              />
            </div>

            <div>
              <Label>Note (optional)</Label>
              <Input
                value={advNote}
                onChange={(e) => setAdvNote(e.target.value)}
                placeholder="e.g. cash advance"
                className="mt-1"
                disabled={advSaving}
                data-testid="advance-note"
              />
            </div>

            {advDialog === 'repayment' && (
              <div className="rounded-lg bg-[#F8FAFC] dark:bg-[#18181B] p-3 text-xs">
                <span className="text-[#64748B]">Remaining balance:</span>{' '}
                <strong>{formatCurrency(advance.remaining_balance)}</strong>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={closeAdvanceDialog}
              disabled={advSaving}
            >
              Cancel
            </Button>

            <Button
              type="button"
              onClick={saveAdvance}
              disabled={advSaving}
              data-testid="save-advance-entry"
            >
              {advSaving
                ? 'Saving…'
                : advDialog === 'advance'
                  ? 'Save Advance'
                  : 'Save Repayment'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const ENTITY_EXPORT_COLS = [
  { key: 'date', label: 'Date' }, { key: 'shift_type', label: 'Shift' },
  { key: 'start_time', label: 'Scheduled Start' }, { key: 'end_time', label: 'Scheduled End' },
  { key: 'actual_check_in', label: 'Actual Check-In' }, { key: 'actual_check_out', label: 'Actual Check-Out' },
  { key: 'duty_hours', label: 'Hours' },
  { key: 'officer_name', label: 'Officer' },
  { key: 'post_pin_display', label: 'Post Pin' }, { key: 'post_site_name', label: 'Post Site' },
  { key: 'client_name', label: 'Client' }, { key: 'vendor_name', label: 'Vendor' },
  { key: 'confirmation_status', label: 'Confirmation' }, { key: 'confirmation_method', label: 'Method' },
  { key: 'shift_status', label: 'Shift Status' }, { key: 'remarks', label: 'Remarks' },
  { key: 'last_modified_by_name', label: 'Last Modified By' },
  { key: 'last_modified_action', label: 'Last Action' },
];
const ENTITY_EXPORT_COLS_FIN = [
  { key: 'duty_rate', label: 'Duty Rate' },
  { key: 'billing_rate', label: 'Billing Rate' },
  { key: 'work_order_number', label: 'Work Order' },
];

const ColumnPickerDialog = ({ open, onClose, canFinancial, picked, onChange, onExport }) => {
  const all = canFinancial ? [...ENTITY_EXPORT_COLS, ...ENTITY_EXPORT_COLS_FIN] : ENTITY_EXPORT_COLS;
  const set = new Set(picked);
  const toggle = (k) => { const n = new Set(set); n.has(k) ? n.delete(k) : n.add(k); onChange(Array.from(n)); };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="column-picker-dialog">
        <DialogHeader>
          <DialogTitle>Choose columns to export</DialogTitle>
          <DialogDescription>
            Tick the columns you want in the file. Order is preserved from top → bottom of this list.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-2">
          {all.map((c) => (
            <label key={c.key} className="flex items-center gap-2 text-sm cursor-pointer" data-testid={`col-${c.key}`}>
              <Checkbox checked={set.has(c.key)} onCheckedChange={() => toggle(c.key)} />
              <span className="text-[#334155] dark:text-[#E4E4E7]">{c.label}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-between pt-2">
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onChange(all.map((c) => c.key))} data-testid="col-select-all">Select all</Button>
            <Button variant="outline" size="sm" onClick={() => onChange([])} data-testid="col-clear-all">Clear</Button>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => onExport('xlsx')} data-testid="detail-export-excel" disabled={picked.length === 0}>
              <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel
            </Button>
            <Button variant="outline" size="sm" onClick={() => onExport('pdf')} data-testid="detail-export-pdf" disabled={picked.length === 0}>
              <FileText className="w-4 h-4 mr-2" /> PDF
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default DispatchReportsPage;
