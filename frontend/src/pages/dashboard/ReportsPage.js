import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  BarChart3, Users, Clock, TrendingUp, DollarSign, FileText,
  Calendar as CalendarIcon, Download, Mail,
} from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import { useAppSettings, formatMoney } from '@/contexts/AppSettingsContext';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const StatCard = ({ icon: Icon, label, value, sub, tone = 'indigo', testId }) => {
  const tones = {
    indigo: 'bg-[#4F46E5]/10 text-[#4F46E5]',
    green: 'bg-green-500/10 text-green-600',
    orange: 'bg-orange-500/10 text-orange-600',
    blue: 'bg-blue-500/10 text-blue-600',
    red: 'bg-red-500/10 text-red-600',
  };
  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid={testId}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${tones[tone]}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
        <p className="text-sm text-[#64748B] mb-1">{label}</p>
        <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{value}</p>
        {sub && <p className="text-xs text-[#64748B] mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
};

const excelDownload = async (filename, rows, sheetName = 'Sheet1') => {
  if (!rows || rows.length === 0) return;
  const ExcelJS = (await import('exceljs')).default;
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet(sheetName, { views: [{ state: 'frozen', ySplit: 1 }] });
  const keys = Object.keys(rows[0]);
  ws.addRow(keys.map((k) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())));
  const header = ws.getRow(1);
  header.height = 24;
  header.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4F46E5' } };
    cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
    cell.border = {
      top: { style: 'thin', color: { argb: 'FFE2E8F0' } },
      left: { style: 'thin', color: { argb: 'FFE2E8F0' } },
      right: { style: 'thin', color: { argb: 'FFE2E8F0' } },
      bottom: { style: 'thin', color: { argb: 'FFE2E8F0' } },
    };
  });
  rows.forEach((r, i) => {
    const values = keys.map((k) => {
      const v = r[k];
      if (v == null) return '';
      return typeof v === 'object' ? JSON.stringify(v) : v;
    });
    const excelRow = ws.addRow(values);
    const bg = i % 2 === 0 ? 'FFFFFFFF' : 'FFF8FAFC';
    excelRow.eachCell((cell) => {
      cell.font = { size: 11, color: { argb: 'FF334155' } };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      cell.border = {
        top: { style: 'thin', color: { argb: 'FFE2E8F0' } },
        left: { style: 'thin', color: { argb: 'FFE2E8F0' } },
        right: { style: 'thin', color: { argb: 'FFE2E8F0' } },
        bottom: { style: 'thin', color: { argb: 'FFE2E8F0' } },
      };
      cell.alignment = { vertical: 'middle' };
    });
  });
  ws.columns.forEach((col) => {
    let max = 12;
    col.eachCell({ includeEmpty: false }, (cell) => {
      const len = String(cell.value ?? '').length;
      if (len > max) max = Math.min(len + 2, 40);
    });
    col.width = max;
  });
  const buf = await wb.xlsx.writeBuffer();
  const blob = new Blob([buf], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
};

const ReportsPage = () => {
  const { settings } = useAppSettings();
  const symbol = settings?.currency_symbol || '৳';
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [tab, setTab] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [attendance, setAttendance] = useState({ rows: [], total: 0 });
  const [payroll, setPayroll] = useState({ rows: [], total: 0 });
  const [overtime, setOvertime] = useState({ rows: [], total: 0 });
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, a, p, o] = await Promise.all([
        api.get(`/reports/summary?month=${month}&year=${year}`),
        api.get(`/reports/attendance?month=${month}&year=${year}`),
        api.get(`/reports/payroll?month=${month}&year=${year}`),
        api.get(`/reports/overtime?month=${month}&year=${year}`),
      ]);
      setSummary(s.data); setAttendance(a.data); setPayroll(p.data); setOvertime(o.data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); }
  }, [month, year]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading || !summary) return (
    <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>
  );

  return (
    <div data-testid="reports-page">
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2 flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-[#4F46E5]" /> Reports
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {MONTHS[month-1]} {year} · consolidated view of attendance, payroll, overtime, leaves and shifts
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
            <SelectTrigger className="w-32" data-testid="report-month"><SelectValue /></SelectTrigger>
            <SelectContent>
              {MONTHS.map((m, i) => <SelectItem key={m} value={String(i+1)}>{m}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-24" data-testid="report-year"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[year-2, year-1, year, year+1].map((y) => <SelectItem key={y} value={String(y)}>{y}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex gap-2 mb-6 flex-wrap">
        {[
          { id: 'overview', label: 'Overview', icon: BarChart3 },
          { id: 'attendance', label: `Attendance (${attendance.total})`, icon: Clock },
          { id: 'payroll', label: `Payroll (${payroll.total})`, icon: DollarSign },
          { id: 'overtime', label: `Overtime (${overtime.total})`, icon: TrendingUp },
        ].map((t) => (
          <Button key={t.id} variant={tab === t.id ? 'default' : 'outline'} onClick={() => setTab(t.id)}
            className={tab === t.id ? 'bg-[#4F46E5] hover:bg-[#4338CA]' : ''}
            data-testid={`report-tab-${t.id}`}>
            <t.icon className="w-4 h-4 mr-2" /> {t.label}
          </Button>
        ))}
      </div>

      {tab === 'overview' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard icon={Users} label="Active Employees" value={summary.employees.total_active} sub={`${summary.employees.suspended} suspended`} tone="indigo" testId="stat-employees" />
            <StatCard icon={Clock} label="Attendance Records" value={summary.attendance.records} sub={`${summary.attendance.total_work_hours}h worked · ${summary.attendance.late_days} late`} tone="blue" testId="stat-attendance" />
            <StatCard icon={FileText} label="Leaves Approved" value={summary.leaves.approved_this_month} sub={`${summary.leaves.pending} pending`} tone="orange" testId="stat-leaves" />
            <StatCard icon={TrendingUp} label="Overtime Hours" value={summary.overtime.approved_hours} sub={`${summary.overtime.pending} pending approval`} tone="red" testId="stat-overtime" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="payroll-summary-card">
              <CardHeader><CardTitle className="flex items-center gap-2"><DollarSign className="w-5 h-5" /> Payroll {MONTHS[month-1]} {year}</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between"><span className="text-[#64748B]">Payslips generated</span><span className="font-semibold">{summary.payroll.payslips_generated}</span></div>
                <div className="flex justify-between"><span className="text-[#64748B]">Total gross</span><span className="font-semibold">{formatMoney(summary.payroll.total_gross, symbol)}</span></div>
                <div className="flex justify-between"><span className="text-[#64748B]">Total net</span><span className="font-semibold text-green-600">{formatMoney(summary.payroll.total_net, symbol)}</span></div>
                <div className="flex justify-between items-center"><span className="text-[#64748B] flex items-center gap-1"><Mail className="w-4 h-4" /> Emails delivered</span>
                  <Badge className={summary.payroll.emails_sent === summary.payroll.payslips_generated ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}>
                    {summary.payroll.emails_sent} / {summary.payroll.payslips_generated}
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="shifts-summary-card">
              <CardHeader><CardTitle className="flex items-center gap-2"><CalendarIcon className="w-5 h-5" /> Shifts</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between"><span className="text-[#64748B]">Shift templates</span><span className="font-semibold">{summary.shifts.defined}</span></div>
                <div className="flex justify-between"><span className="text-[#64748B]">Sessions this month</span><span className="font-semibold">{summary.shifts.sessions_this_month}</span></div>
                <div className="flex justify-between"><span className="text-[#64748B]">Absent days</span><span className="font-semibold text-red-600">{summary.attendance.absent_days}</span></div>
              </CardContent>
            </Card>
          </div>
        </motion.div>
      )}

      {tab === 'attendance' && (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="report-attendance-card">
          <CardHeader className="flex flex-row justify-between items-center">
            <CardTitle>Attendance Detail</CardTitle>
            <Button variant="outline" onClick={() => excelDownload(`attendance_${year}_${month}.xlsx`, attendance.rows, 'Attendance')} data-testid="download-attendance-excel"><Download className="w-4 h-4 mr-1" /> Excel</Button>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F8FAFC] dark:bg-[#18181B] text-[#64748B]">
                <tr>{['Date','Employee','Email','Sessions','Hours','Status','OT (min)'].map((h) => <th key={h} className="text-left p-3 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {attendance.rows.length === 0 ? (
                  <tr><td colSpan={7} className="p-6 text-center text-[#64748B]">No attendance records</td></tr>
                ) : attendance.rows.map((r, i) => (
                  <tr key={i} className="border-t border-[#E2E8F0] dark:border-[#27272A]" data-testid={`att-row-${i}`}>
                    <td className="p-3">{r.date}</td>
                    <td className="p-3 font-medium">{r.user_name}</td>
                    <td className="p-3 text-[#64748B]">{r.email}</td>
                    <td className="p-3">{r.sessions_count}</td>
                    <td className="p-3">{r.total_hours}h</td>
                    <td className="p-3"><Badge className="capitalize">{r.status}</Badge></td>
                    <td className="p-3">{r.overtime_minutes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {tab === 'payroll' && (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="report-payroll-card">
          <CardHeader className="flex flex-row justify-between items-center">
            <CardTitle>Payroll Detail</CardTitle>
            <Button variant="outline" onClick={() => excelDownload(`payroll_${year}_${month}.xlsx`, payroll.rows, 'Payroll')} data-testid="download-payroll-excel"><Download className="w-4 h-4 mr-1" /> Excel</Button>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F8FAFC] dark:bg-[#18181B] text-[#64748B]">
                <tr>{['Employee','Base','Bonuses','Deductions','Net','Hours','OT','Emailed'].map((h) => <th key={h} className="text-left p-3 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {payroll.rows.length === 0 ? (
                  <tr><td colSpan={8} className="p-6 text-center text-[#64748B]">No payslips generated</td></tr>
                ) : payroll.rows.map((r) => (
                  <tr key={r.id} className="border-t border-[#E2E8F0] dark:border-[#27272A]" data-testid={`pay-row-${r.id}`}>
                    <td className="p-3 font-medium">{r.user_name}</td>
                    <td className="p-3">{formatMoney(r.base_salary, symbol)}</td>
                    <td className="p-3 text-green-600">+{formatMoney(r.bonuses, symbol)}</td>
                    <td className="p-3 text-red-600">-{formatMoney(r.deductions, symbol)}</td>
                    <td className="p-3 font-semibold">{formatMoney(r.net_salary, symbol)}</td>
                    <td className="p-3">{r.total_hours}h</td>
                    <td className="p-3">{r.overtime_hours}h</td>
                    <td className="p-3">{r.email_sent ? <Badge className="bg-green-100 text-green-700">Sent</Badge> : <Badge className="bg-orange-100 text-orange-700">Not sent</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {tab === 'overtime' && (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="report-overtime-card">
          <CardHeader className="flex flex-row justify-between items-center">
            <CardTitle>Overtime Requests</CardTitle>
            <Button variant="outline" onClick={() => excelDownload(`overtime_${year}_${month}.xlsx`, overtime.rows, 'Overtime')} data-testid="download-overtime-excel"><Download className="w-4 h-4 mr-1" /> Excel</Button>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#F8FAFC] dark:bg-[#18181B] text-[#64748B]">
                <tr>{['Date','Employee','Total Hrs','OT Hrs','Status','Reviewer','Note'].map((h) => <th key={h} className="text-left p-3 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {overtime.rows.length === 0 ? (
                  <tr><td colSpan={7} className="p-6 text-center text-[#64748B]">No overtime requests</td></tr>
                ) : overtime.rows.map((r) => (
                  <tr key={r.id} className="border-t border-[#E2E8F0] dark:border-[#27272A]" data-testid={`ot-row-${r.id}`}>
                    <td className="p-3">{r.date}</td>
                    <td className="p-3 font-medium">{r.user_id.slice(0,8)}…</td>
                    <td className="p-3">{r.total_hours}h</td>
                    <td className="p-3 text-orange-600 font-semibold">+{r.overtime_hours}h</td>
                    <td className="p-3"><Badge className="capitalize">{r.status}</Badge></td>
                    <td className="p-3">{r.reviewer_name || '-'}</td>
                    <td className="p-3 text-[#64748B]">{r.review_note || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ReportsPage;
