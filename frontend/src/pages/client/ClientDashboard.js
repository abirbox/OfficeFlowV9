import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { useAppSettings } from '@/contexts/AppSettingsContext';
import { motion } from 'framer-motion';
import { CalendarDays, CalendarClock, CheckCircle2, Building2, Shield, MapPin, UserCheck, MapPinned, Wallet } from 'lucide-react';

const StatCard = ({ icon: Icon, label, value, accent, delay, sub }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.35, delay }}
    className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-5"
    data-testid={`stat-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`}
  >
    <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${accent}`}>
      <Icon className="w-5 h-5" />
    </div>
    <div className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{value}</div>
    <div className="text-sm text-[#64748B] dark:text-[#A1A1AA] mt-1">{label}</div>
    {sub && <div className="text-xs text-[#94A3B8] dark:text-[#71717A] mt-1">{sub}</div>}
  </motion.div>
);

const ClientDashboard = () => {
  const [summary, setSummary] = useState(null);
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const { settings } = useAppSettings();
  const currency = settings?.currency_symbol || '$';

  useEffect(() => {
    Promise.all([
      api.get('/portal/summary').then((r) => r.data),
      api.get('/portal/me').then((r) => r.data),
    ]).then(([s, m]) => { setSummary(s); setMe(m); })
      .finally(() => setLoading(false));
  }, []);

  const clientName = me?.client?.name || me?.user?.name || 'Client';
  const payslip = summary?.payslip_7d;
  const payslipValue = `${currency}${(payslip?.total ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div className="space-y-8" data-testid="client-dashboard">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Welcome, {clientName}</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Here is an overview of your dispatch activity.</p>
      </div>

      {loading ? (
        <div className="text-[#64748B]">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard icon={UserCheck} label="Officer Check-ins Today" value={summary?.checkins_today ?? 0} accent="bg-teal-500/10 text-teal-600" delay={0} />
          <StatCard icon={MapPinned} label="Active Post Sites" value={summary?.active_post_sites ?? 0} accent="bg-rose-500/10 text-rose-600" delay={0.05} />
          <StatCard
            icon={Wallet}
            label="Payslip Summary (7 days)"
            value={payslipValue}
            sub={`${payslip?.shifts ?? 0} shifts · ${payslip?.officers ?? 0} officers`}
            accent="bg-emerald-500/10 text-emerald-600"
            delay={0.1}
          />
          <StatCard icon={CalendarDays} label="Total Schedules" value={summary?.total_schedules ?? 0} accent="bg-[#4F46E5]/10 text-[#4F46E5]" delay={0.15} />
          <StatCard icon={CalendarClock} label="Upcoming Schedules" value={summary?.upcoming_schedules ?? 0} accent="bg-amber-500/10 text-amber-600" delay={0.2} />
          <StatCard icon={CheckCircle2} label="Completed Shifts" value={summary?.completed_schedules ?? 0} accent="bg-sky-500/10 text-sky-600" delay={0.25} />
          <StatCard icon={Building2} label="My Vendors" value={summary?.vendors ?? 0} accent="bg-violet-500/10 text-violet-600" delay={0.3} />
          <StatCard icon={Shield} label="Security Officers" value={summary?.officers ?? 0} accent="bg-indigo-500/10 text-indigo-600" delay={0.35} />
          <StatCard icon={MapPin} label="Post Sites" value={summary?.post_sites ?? 0} accent="bg-fuchsia-500/10 text-fuchsia-600" delay={0.4} />
        </div>
      )}
    </div>
  );
};

export default ClientDashboard;
