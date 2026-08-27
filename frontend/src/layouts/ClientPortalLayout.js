import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { useTheme } from '@/contexts/ThemeContext';
import { useAppSettings } from '@/contexts/AppSettingsContext';
import { api } from '@/lib/axios';
import {
  LayoutDashboard, Building2, CalendarDays, BarChart3,
  LogOut, Menu, X, Sun, Moon, Shield, Users, CalendarClock,
} from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';

const navItems = [
  { name: 'Dashboard', href: '/client', icon: LayoutDashboard, end: true },
  { name: 'Security Officers', href: '/client/officers', icon: Shield },
  { name: "Today's Dispatch", href: '/client/today', icon: CalendarClock },
  { name: 'Dispatch Calendar', href: '/client/calendar', icon: CalendarDays },
  { name: 'Vendors', href: '/client/vendors', icon: Building2 },
  { name: 'Schedules', href: '/client/schedules', icon: Users },
  { name: 'Reports', href: '/client/reports', icon: BarChart3 },
];

const ClientPortalLayout = () => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [clientName, setClientName] = useState('');
  const { user, logout } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const { settings } = useAppSettings();
  const brandName = settings?.brand_name || 'OfficeFlow';
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api.get('/portal/me').then(({ data }) => {
      setClientName(data?.client?.name || user?.name || '');
    }).catch(() => setClientName(user?.name || ''));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const isActive = (item) => item.end ? location.pathname === item.href : location.pathname.startsWith(item.href);

  const NavList = ({ onNavigate }) => (
    <nav className="p-3 space-y-1 flex-1 overflow-y-auto" data-testid="client-nav">
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = isActive(item);
        return (
          <button
            key={item.name}
            onClick={() => { navigate(item.href); onNavigate && onNavigate(); }}
            data-testid={`client-nav-${item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')}`}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
              active ? 'bg-[#4F46E5] text-white'
                : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
            }`}
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            <span className="text-sm font-medium">{item.name}</span>
          </button>
        );
      })}
    </nav>
  );

  const Brand = () => (
    <div className="flex items-center gap-2 min-w-0">
      <span className="w-9 h-9 rounded-xl bg-[#4F46E5] text-white flex items-center justify-center flex-shrink-0">
        <Shield className="w-5 h-5" />
      </span>
      <div className="min-w-0">
        <div className="text-sm font-bold text-[#0F172A] dark:text-[#FAFAFA] truncate">{brandName}</div>
        <div className="text-[10px] uppercase tracking-wider text-[#4F46E5] dark:text-[#A5B4FC] font-semibold">Client Portal</div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#09090B]">
      {/* Desktop sidebar */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 hidden lg:flex flex-col" data-testid="client-sidebar">
        <div className="h-16 flex items-center px-4 border-b border-[#E2E8F0] dark:border-[#27272A]">
          <Brand />
        </div>
        <NavList />
        <div className="p-3 border-t border-[#E2E8F0] dark:border-[#27272A]">
          <div className="flex items-center gap-3 px-3 py-2 mb-1">
            <Avatar className="w-8 h-8">
              <AvatarFallback className="bg-[#4F46E5] text-white text-sm">
                {(clientName || 'C').charAt(0).toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA] truncate" data-testid="client-name">{clientName}</p>
              <p className="text-xs text-[#64748B] dark:text-[#A1A1AA] truncate">{user?.email}</p>
            </div>
          </div>
          <button onClick={toggleTheme} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[#334155] dark:text-[#E4E4E7] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A]">
            {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
            {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
          </button>
          <button onClick={handleLogout} data-testid="client-logout-button" className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30">
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-white dark:bg-[#18181B] border-b border-[#E2E8F0] dark:border-[#27272A] z-30 flex items-center justify-between px-4">
        <Brand />
        <Button variant="ghost" size="icon" onClick={() => setMobileOpen(!mobileOpen)} data-testid="client-mobile-toggle">
          {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </Button>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }}
            className="lg:hidden fixed inset-y-0 left-0 w-64 bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 pt-16 flex flex-col">
            <NavList onNavigate={() => setMobileOpen(false)} />
            <div className="p-3 border-t border-[#E2E8F0] dark:border-[#27272A]">
              <button onClick={() => { setMobileOpen(false); handleLogout(); }} data-testid="client-mobile-logout" className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-semibold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30">
                <LogOut className="w-4 h-4" /> Logout
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="lg:ml-64">
        <div className="pt-16 lg:pt-0 min-w-0">
          <div className="p-4 md:p-8">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};

export default ClientPortalLayout;
