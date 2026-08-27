import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Plus, Download, Trash2 } from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import { useAppSettings, formatMoney } from '@/contexts/AppSettingsContext';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const PayrollPage = () => {
  const { user } = useAuthStore();
  const { settings } = useAppSettings();
  const symbol = settings?.currency_symbol || '৳';
  const isAdmin = ['super_admin', 'admin', 'hr'].includes(user?.role);
  const [payslips, setPayslips] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedEmp, setSelectedEmp] = useState('');
  const [preview, setPreview] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const now = new Date();
  const [form, setForm] = useState({
    month: now.getMonth() + 1, year: now.getFullYear(),
    base_salary: 0, house_rent: 0, medical: 0, transport: 0, communication: 0, mobile_bill: 0,
    allowances: [], bonuses: 0, deductions: 0, notes: '',
  });

  const fetchAll = async () => {
    try {
      const promises = [api.get('/payroll')];
      if (isAdmin) promises.push(api.get('/employees'));
      const [payRes, empRes] = await Promise.all(promises);
      setPayslips(payRes.data);
      if (empRes) setEmployees(empRes.data);
    } catch (e) {
      toast.error('Failed to load payroll');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); /* eslint-disable-next-line */ }, []);

  const loadPreview = async (empId) => {
    setSelectedEmp(empId);
    if (!empId) return setPreview(null);
    try {
      const { data } = await api.get(`/payroll/preview/${empId}?month=${form.month}&year=${form.year}`);
      setPreview(data);
      setForm((f) => ({
        ...f,
        base_salary: data.base_salary || data.current_salary || 0,
        house_rent: data.house_rent || 0,
        medical: data.medical || 0,
        transport: data.transport || 0,
        communication: data.communication || 0,
        mobile_bill: data.mobile_bill || 0,
      }));
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const handleCreate = async () => {
    if (!selectedEmp) return toast.error('Select employee first');
    try {
      const payload = {
        user_id: selectedEmp,
        ...form,
        allowances: (form.allowances || [])
          .filter((a) => a.label && a.label.trim())
          .map((a) => ({ label: a.label.trim(), amount: Number(a.amount || 0) })),
      };
      await api.post('/payroll', payload);
      setDialogOpen(false);
      setSelectedEmp(''); setPreview(null);
      fetchAll();
      toast.success('Payroll created');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const num = (v) => Number(v || 0);
  const allowancesTotal = (form.allowances || []).reduce((s, a) => s + num(a.amount), 0);
  const addAllowance = () => setForm((f) => ({ ...f, allowances: [...(f.allowances || []), { label: '', amount: 0 }] }));
  const updateAllowance = (i, key, val) => setForm((f) => {
    const next = [...f.allowances];
    next[i] = { ...next[i], [key]: val };
    return { ...f, allowances: next };
  });
  const removeAllowance = (i) => setForm((f) => ({ ...f, allowances: f.allowances.filter((_, idx) => idx !== i) }));

  const downloadPdf = async (p) => {
    setDownloading(p.id);
    try {
      const res = await api.get(`/payroll/${p.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      const monthName = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][p.month];
      link.setAttribute('download', `payslip_${monthName}_${p.year}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Payslip downloaded');
    } catch (e) {
      toast.error('Failed to download payslip');
    } finally {
      setDownloading(null);
    }
  };

  const netSalary = num(form.base_salary) + num(form.house_rent) + num(form.medical)
    + num(form.transport) + num(form.communication) + num(form.mobile_bill)
    + allowancesTotal + num(form.bonuses) - num(form.deductions);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>;

  return (
    <div data-testid="payroll-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            {isAdmin ? 'Payroll' : 'My Payroll'}
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {isAdmin ? `Generate payslips with auto-calculated hours & leaves · Currency: ${symbol}` : 'Your salary details and payslip history'}
          </p>
        </div>
        {isAdmin && (
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="create-payroll-button">
                <Plus className="w-5 h-5 mr-2" /> Create Payroll
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Generate Payroll</DialogTitle>
                <DialogDescription>Select an employee — work hours, overtime, and leaves are computed automatically</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Employee</Label>
                  <Select value={selectedEmp} onValueChange={loadPreview}>
                    <SelectTrigger data-testid="payroll-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
                    <SelectContent>
                      {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Month</Label>
                    <Select value={String(form.month)} onValueChange={(v) => { setForm({ ...form, month: Number(v) }); if (selectedEmp) loadPreview(selectedEmp); }}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m, i) => (
                          <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Year</Label>
                    <Input type="number" value={form.year} onChange={(e) => setForm({ ...form, year: Number(e.target.value) })} />
                  </div>
                </div>

                {preview && (
                  <div className="p-4 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg space-y-2" data-testid="payroll-preview">
                    <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">Auto-computed for {preview.user_name}</p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>Work Hours: <span className="font-medium">{preview.total_hours}h</span></div>
                      <div>Overtime: <span className="font-medium text-orange-600">{preview.overtime_hours}h</span></div>
                      <div>Leave Days: <span className="font-medium">{preview.leave_days}</span></div>
                      <div>Late Days: <span className="font-medium text-red-600">{preview.late_days}</span></div>
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <p className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA]">Salary Components ({symbol})</p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Base Salary</Label>
                      <Input type="number" value={form.base_salary} onChange={(e) => setForm({ ...form, base_salary: Number(e.target.value) })} data-testid="payroll-base-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">House Rent</Label>
                      <Input type="number" value={form.house_rent} onChange={(e) => setForm({ ...form, house_rent: Number(e.target.value) })} data-testid="payroll-house-rent-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Medical</Label>
                      <Input type="number" value={form.medical} onChange={(e) => setForm({ ...form, medical: Number(e.target.value) })} data-testid="payroll-medical-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Transport</Label>
                      <Input type="number" value={form.transport} onChange={(e) => setForm({ ...form, transport: Number(e.target.value) })} data-testid="payroll-transport-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Communication</Label>
                      <Input type="number" value={form.communication} onChange={(e) => setForm({ ...form, communication: Number(e.target.value) })} data-testid="payroll-communication-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Mobile Bill</Label>
                      <Input type="number" value={form.mobile_bill} onChange={(e) => setForm({ ...form, mobile_bill: Number(e.target.value) })} data-testid="payroll-mobile-bill-input" />
                    </div>
                  </div>

                  {/* Custom extra allowances */}
                  <div className="space-y-2">
                    {(form.allowances || []).map((a, i) => (
                      <div key={i} className="flex items-center gap-2" data-testid={`allowance-row-${i}`}>
                        <Input placeholder="Field name (e.g. Food)" value={a.label} onChange={(e) => updateAllowance(i, 'label', e.target.value)} data-testid={`allowance-label-${i}`} />
                        <Input type="number" placeholder="0" className="w-32" value={a.amount} onChange={(e) => updateAllowance(i, 'amount', Number(e.target.value))} data-testid={`allowance-amount-${i}`} />
                        <Button type="button" size="sm" variant="ghost" className="text-red-600" onClick={() => removeAllowance(i)} data-testid={`allowance-remove-${i}`}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                    <Button type="button" variant="outline" size="sm" onClick={addAllowance} data-testid="payroll-add-field-button">
                      <Plus className="w-4 h-4 mr-1" /> Add Field
                    </Button>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Bonuses</Label>
                      <Input type="number" value={form.bonuses} onChange={(e) => setForm({ ...form, bonuses: Number(e.target.value) })} data-testid="payroll-bonuses-input" />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Deductions</Label>
                      <Input type="number" value={form.deductions} onChange={(e) => setForm({ ...form, deductions: Number(e.target.value) })} data-testid="payroll-deductions-input" />
                    </div>
                  </div>
                </div>
                <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <p className="text-sm text-[#64748B]">Net Salary</p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-400">{formatMoney(netSalary, symbol)}</p>
                </div>
                <div className="space-y-2">
                  <Label>Notes (optional)</Label>
                  <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="submit-payroll-button">Generate Payroll</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <Card className="border-[#E2E8F0] dark:border-[#27272A]">
        <CardHeader>
          <CardTitle>{isAdmin ? 'All Payslips' : 'Payslip History'}</CardTitle>
        </CardHeader>
        <CardContent>
          {payslips.length === 0 ? (
            <p className="text-center py-8 text-[#64748B]">{isAdmin ? 'No payslips generated yet' : 'No payslips available yet'}</p>
          ) : (
            <div className="space-y-3">
              {payslips.map((p, i) => (
                <motion.div key={p.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  className="p-4 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg" data-testid={`payslip-${p.id}`}>
                  <div className="flex items-center justify-between mb-3 flex-wrap gap-3">
                    <div>
                      <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">
                        {['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][p.month]} {p.year}
                        {isAdmin && <span className="text-sm text-[#64748B] font-normal"> · {p.user_name}</span>}
                      </p>
                      <p className="text-xs text-[#64748B]">Hours: {p.total_hours}h · OT: {p.overtime_hours}h · Leaves: {p.leave_days}d</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <p className="text-2xl font-bold text-green-700 dark:text-green-400">{formatMoney(p.net_salary, symbol)}</p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => downloadPdf(p)}
                        disabled={downloading === p.id}
                        data-testid={`download-payslip-${p.id}`}
                      >
                        <Download className="w-4 h-4 mr-1" />
                        {downloading === p.id ? 'Downloading…' : 'PDF'}
                      </Button>
                    </div>
                  </div>
                  <div className="flex gap-2 text-xs flex-wrap">
                    <Badge variant="outline">Base {formatMoney(p.base_salary, symbol)}</Badge>
                    {p.house_rent > 0 && <Badge variant="outline">HRA {formatMoney(p.house_rent, symbol)}</Badge>}
                    {p.medical > 0 && <Badge variant="outline">Medical {formatMoney(p.medical, symbol)}</Badge>}
                    {p.transport > 0 && <Badge variant="outline">Transport {formatMoney(p.transport, symbol)}</Badge>}
                    {p.communication > 0 && <Badge variant="outline">Comm {formatMoney(p.communication, symbol)}</Badge>}
                    {p.mobile_bill > 0 && <Badge variant="outline">Mobile {formatMoney(p.mobile_bill, symbol)}</Badge>}
                    {(p.allowances || []).map((a, idx) => (
                      <Badge key={idx} variant="outline">{a.label} {formatMoney(a.amount, symbol)}</Badge>
                    ))}
                    {p.bonuses > 0 && <Badge variant="outline" className="text-green-700">+{formatMoney(p.bonuses, symbol)}</Badge>}
                    {p.deductions > 0 && <Badge variant="outline" className="text-red-700">-{formatMoney(p.deductions, symbol)}</Badge>}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PayrollPage;
