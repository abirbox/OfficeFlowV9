import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Users, Building2, MapPin, Shield, CheckCircle2, Clock, XCircle, AlertTriangle, LogIn, LogOut, HelpCircle } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';

const REFRESH_MS = 10_000; // Live ticker refresh interval

const Card = ({ icon: Icon, label, value, color, testid }) => (
  <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5" data-testid={testid}>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-xs uppercase tracking-wider text-[#64748B]">{label}</p>
        <p className="mt-2 text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{value ?? '—'}</p>
      </div>
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
    </div>
  </div>
);

const TickerCell = ({ icon: Icon, label, value, tone, testid }) => (
  <div
    className={`flex-1 min-w-[160px] rounded-lg p-4 border ${tone.bg} ${tone.border}`}
    data-testid={testid}
  >
    <div className="flex items-center gap-2 text-xs uppercase tracking-wider font-medium">
      <Icon className={`w-4 h-4 ${tone.icon}`} />
      <span className={tone.text}>{label}</span>
    </div>
    <div className={`mt-2 text-3xl font-bold ${tone.value}`}>{value ?? 0}</div>
  </div>
);

const DispatchDashboardPage = () => {
  const { user } = useAuthStore();
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api.get('/dispatch/dashboard/stats').then(({ data }) => { if (!cancelled) setStats(data); })
        .catch(() => { if (!cancelled) setStats({}); })
        .finally(() => { if (!cancelled) setLoading(false); });
    };
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  if (!hasPermission(user, 'dispatch.dashboard.view')) {
    return <div className="p-8 text-[#64748B]">You do not have permission to view the Dispatch dashboard.</div>;
  }

  return (
    <div className="space-y-6" data-testid="dispatch-dashboard">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Dispatch Dashboard</h1>
        <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1">Today's dispatch operations at a glance · live refresh every 10s</p>
      </div>

      {/* Officer Attendance Ticker */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5" data-testid="officer-attendance-ticker">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-[#0F172A] dark:text-[#FAFAFA]">Officer Attendance — Today</h2>
            <p className="text-xs text-[#64748B]">Real-time counters for the officers on shift today</p>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> Live
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          <TickerCell
            icon={LogIn} label="Checked-in" value={stats.checked_in}
            tone={{ bg: 'bg-emerald-50 dark:bg-emerald-950/40', border: 'border-emerald-200 dark:border-emerald-900',
                    icon: 'text-emerald-600', text: 'text-emerald-700 dark:text-emerald-300',
                    value: 'text-emerald-700 dark:text-emerald-300' }}
            testid="ticker-checked-in"
          />
          <TickerCell
            icon={LogOut} label="Checked-out" value={stats.checked_out}
            tone={{ bg: 'bg-sky-50 dark:bg-sky-950/40', border: 'border-sky-200 dark:border-sky-900',
                    icon: 'text-sky-600', text: 'text-sky-700 dark:text-sky-300',
                    value: 'text-sky-700 dark:text-sky-300' }}
            testid="ticker-checked-out"
          />
          <TickerCell
            icon={Clock} label="Pending" value={stats.pending}
            tone={{ bg: 'bg-amber-50 dark:bg-amber-950/40', border: 'border-amber-200 dark:border-amber-900',
                    icon: 'text-amber-600', text: 'text-amber-700 dark:text-amber-300',
                    value: 'text-amber-700 dark:text-amber-300' }}
            testid="ticker-pending"
          />
          <TickerCell
            icon={HelpCircle} label="No Response" value={stats.no_response}
            tone={{ bg: 'bg-slate-50 dark:bg-slate-950/40', border: 'border-slate-200 dark:border-slate-800',
                    icon: 'text-slate-500', text: 'text-slate-600 dark:text-slate-300',
                    value: 'text-slate-700 dark:text-slate-200' }}
            testid="ticker-no-response"
          />
          <TickerCell
            icon={CheckCircle2} label="Clocked In" value={stats.checked_in}
            tone={{ bg: 'bg-emerald-50 dark:bg-emerald-950/40', border: 'border-emerald-200 dark:border-emerald-900',
                    icon: 'text-emerald-600', text: 'text-emerald-700 dark:text-emerald-300',
                    value: 'text-emerald-700 dark:text-emerald-300' }}
            testid="ticker-clocked-in"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card icon={Clock} label="Today's Dispatch" value={loading ? '...' : stats.today_total} color="bg-indigo-600" testid="stat-today" />
        <Card icon={CheckCircle2} label="Confirmed" value={stats.confirmed} color="bg-emerald-600" testid="stat-confirmed" />
        <Card icon={Clock} label="Pending" value={stats.pending} color="bg-amber-500" testid="stat-pending" />
        <Card icon={AlertTriangle} label="No Response" value={stats.no_response} color="bg-slate-500" testid="stat-noresp" />
        <Card icon={XCircle} label="Declined" value={stats.declined} color="bg-rose-600" testid="stat-declined" />
        <Card icon={CheckCircle2} label="Clocked In" value={stats.checked_in} color="bg-emerald-700" testid="stat-clocked-in" />
        <Card icon={CheckCircle2} label="Clocked Out" value={stats.checked_out} color="bg-sky-600" testid="stat-clocked-out" />
        <Card icon={AlertTriangle} label="Open Positions" value={stats.open_positions} color="bg-fuchsia-600" testid="stat-open" />
      </div>

      <h2 className="text-lg font-semibold pt-4">Directory</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card icon={Building2} label="Clients" value={stats.clients} color="bg-sky-600" testid="stat-clients" />
        <Card icon={Building2} label="Vendors" value={stats.vendors} color="bg-teal-600" testid="stat-vendors" />
        <Card icon={Shield} label="Security Officers" value={stats.officers} color="bg-violet-600" testid="stat-officers" />
        <Card icon={MapPin} label="Post Sites" value={stats.post_sites} color="bg-cyan-600" testid="stat-posts" />
      </div>
    </div>
  );
};

export default DispatchDashboardPage;
