import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import useAuthStore from '@/stores/authStore';
import { useTheme } from '@/contexts/ThemeContext';
import {
  LayoutDashboard,
  Users,
  Building2,
  MapPin,
  CheckSquare,
  FolderKanban,
  Calendar,
  FileText,
  DollarSign,
  Settings,
  LogOut,
  Menu,
  X,
  Sun,
  Moon,
  Bell,
  Search,
  ChevronDown,
  TrendingUp,
  BarChart3,
  Truck,
  Shield,
  ClipboardList,
  ScrollText,
  User,
  ArrowLeftRight,
  Briefcase,
} from 'lucide-react';
import { hasPermission, hasAnyDispatchPerm } from '@/lib/permissions';
import usePortalStore from '@/stores/portalStore';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import NotificationBell from '@/components/NotificationBell';
import LocationStreamer from '@/components/LocationStreamer';
import { useAppSettings } from '@/contexts/AppSettingsContext';

const allNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
  { name: 'My Shifts', href: '/dashboard/shifts', icon: FolderKanban, roles: ['employee'] },
  { name: 'My Overtime', href: '/dashboard/overtime', icon: TrendingUp, roles: ['employee'] },
  { name: 'My Attendance', href: '/dashboard/attendance', icon: CheckSquare, roles: ['employee'] },
  { name: 'Share Location', href: '/dashboard/gps', icon: MapPin, roles: ['employee'] },
  { name: 'My Payroll', href: '/dashboard/payroll', icon: DollarSign, roles: ['employee'] },
  { name: 'My Leaves', href: '/dashboard/leaves', icon: FileText, roles: ['employee'] },
  { name: 'Employees', href: '/dashboard/employees', icon: Users, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Work Shifts', href: '/dashboard/shifts', icon: FolderKanban, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Overtime', href: '/dashboard/overtime', icon: TrendingUp, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Attendance', href: '/dashboard/attendance', icon: CheckSquare, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Live Map', href: '/dashboard/live-map', icon: MapPin, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Calendar', href: '/dashboard/calendar', icon: Calendar, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
  { name: 'Leaves', href: '/dashboard/leaves', icon: FileText, roles: ['super_admin', 'admin', 'hr'] },
  { name: 'Payroll', href: '/dashboard/payroll', icon: DollarSign, roles: ['super_admin', 'admin', 'hr'] },
  { name: 'Reports', href: '/dashboard/reports', icon: BarChart3, roles: ['super_admin', 'admin', 'hr', 'manager'] },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings, roles: ['super_admin', 'admin', 'hr', 'manager', 'employee'] },
];

const dispatchNavigationOperations = [
  { name: 'Dispatch Dashboard', href: '/dashboard/dispatch', icon: LayoutDashboard, perm: 'dispatch.dashboard.view' },
  { name: "Today's Dispatch", href: '/dashboard/dispatch/today', icon: ClipboardList, perm: 'dispatch.schedule.view' },
  { name: 'Dispatch Schedule', href: '/dashboard/dispatch/schedules', icon: Calendar, perm: 'dispatch.schedule.view' },
  { name: 'Dispatch Calendar', href: '/dashboard/dispatch/calendar', icon: Calendar, perm: 'dispatch.schedule.view' },
  { name: 'Clients', href: '/dashboard/dispatch/clients', icon: Building2, perm: 'dispatch.clients.view' },
  { name: 'Vendors', href: '/dashboard/dispatch/vendors', icon: Building2, perm: 'dispatch.vendors.view' },
  { name: 'Security Officers', href: '/dashboard/dispatch/officers', icon: Shield, perm: 'dispatch.officers.view' },
  { name: 'Post Sites', href: '/dashboard/dispatch/post-sites', icon: MapPin, perm: 'dispatch.post_sites.view' },
  { name: 'Audit Log', href: '/dashboard/dispatch/audit', icon: ScrollText, perm: 'dispatch.audit.view' },
];

const dispatchNavigationFinancial = [
  { name: 'Wage Report', href: '/dashboard/dispatch/reports', icon: BarChart3, perm: 'dispatch.reports.view' },
  { name: 'Invoices', href: '/dashboard/dispatch/invoices', icon: FileText, perm: 'dispatch.reports.view' },
  { name: 'Payment (SO)', href: '/dashboard/dispatch/payment-so', icon: DollarSign, perm: 'dispatch.payment_so.view' },
];

const dispatchNavigation = [...dispatchNavigationOperations, ...dispatchNavigationFinancial];

const DashboardLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const { portal, setPortal, clearPortal } = usePortalStore();
  const { theme, toggleTheme } = useTheme();
  const { settings } = useAppSettings();
  const brandName = settings?.brand_name || 'OfficeFlow';
  const brandLogo = settings?.brand_logo_url || null;
  const navigate = useNavigate();
  const location = useLocation();

  const userRole = user?.role || 'employee';
  const canDispatch = hasAnyDispatchPerm(user);
  // Users without dispatch permission are locked to the Employee Portal.
  const effectivePortal = canDispatch ? portal : 'employee';
  const showPortalPopup = canDispatch && !portal;

  const employeeNav = allNavigation.filter((item) => item.roles.includes(userRole));
  const dispatchNav = canDispatch
    ? dispatchNavigation.filter((item) => hasPermission(user, item.perm))
    : [];
  const navigation = effectivePortal === 'dispatch' ? [] : employeeNav;
  const activeDispatchNav = effectivePortal === 'dispatch' ? dispatchNav : [];
  const activeDispatchOps = effectivePortal === 'dispatch'
    ? dispatchNavigationOperations.filter((item) => hasPermission(user, item.perm))
    : [];
  const activeDispatchFin = effectivePortal === 'dispatch'
    ? dispatchNavigationFinancial.filter((item) => hasPermission(user, item.perm))
    : [];

  const dispatchHome = () => (dispatchNav[0]?.href || '/dashboard/dispatch');
  const choosePortal = (p) => {
    setPortal(p);
    navigate(p === 'dispatch' ? dispatchHome() : '/dashboard');
  };
  const switchPortal = () => {
    const target = effectivePortal === 'dispatch' ? 'employee' : 'dispatch';
    setPortal(target);
    navigate(target === 'dispatch' ? dispatchHome() : '/dashboard');
    setMobileMenuOpen(false);
  };

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogout = async () => {
    clearPortal();
    await logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#09090B]">
      {/* Portal selection popup — shown after login for users with dispatch access */}
      {showPortalPopup && (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" data-testid="portal-select-overlay">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="bg-white dark:bg-[#18181B] rounded-2xl border border-[#E2E8F0] dark:border-[#27272A] shadow-2xl p-8 max-w-lg w-full"
          >
            <h2 className="text-2xl font-bold text-[#0F172A] dark:text-[#FAFAFA] text-center">Choose your workspace</h2>
            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] text-center mt-2 mb-6">
              You have access to both portals. Pick where to start — you can switch anytime.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <button
                onClick={() => choosePortal('employee')}
                data-testid="portal-select-employee"
                className="group flex flex-col items-center gap-3 p-6 rounded-xl border border-[#E2E8F0] dark:border-[#27272A] hover:border-[#4F46E5] hover:bg-[#4F46E5]/5 transition-colors"
              >
                <span className="w-12 h-12 rounded-xl bg-[#4F46E5]/10 text-[#4F46E5] flex items-center justify-center">
                  <Briefcase className="w-6 h-6" />
                </span>
                <span className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]">Go to Employee Portal</span>
                <span className="text-xs text-[#64748B] dark:text-[#A1A1AA] text-center">HR, attendance, shifts, payroll & more</span>
              </button>
              <button
                onClick={() => choosePortal('dispatch')}
                data-testid="portal-select-dispatch"
                className="group flex flex-col items-center gap-3 p-6 rounded-xl border border-[#E2E8F0] dark:border-[#27272A] hover:border-[#4F46E5] hover:bg-[#4F46E5]/5 transition-colors"
              >
                <span className="w-12 h-12 rounded-xl bg-[#4F46E5]/10 text-[#4F46E5] flex items-center justify-center">
                  <Truck className="w-6 h-6" />
                </span>
                <span className="font-semibold text-[#0F172A] dark:text-[#FAFAFA]">Go to Dispatch Portal</span>
                <span className="text-xs text-[#64748B] dark:text-[#A1A1AA] text-center">Schedules, clients, officers & payments</span>
              </button>
            </div>
          </motion.div>
        </div>
      )}
      {/* Desktop Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width: sidebarOpen ? 256 : 64,
        }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
        className="fixed left-0 top-0 h-full bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 hidden lg:block"
        data-testid="dashboard-sidebar"
      >
        <div className="h-full flex flex-col">
          {/* Logo */}
          <div className="h-16 flex items-center justify-between px-4 border-b border-[#E2E8F0] dark:border-[#27272A]">
            <AnimatePresence mode="wait">
              {sidebarOpen && (
                <motion.div
                  key="logo-full"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 min-w-0"
                  data-testid="app-logo"
                >
                  {brandLogo ? (
                    <img
                      src={brandLogo}
                      alt={brandName}
                      className="h-9 max-w-[170px] object-contain"
                      data-testid="app-logo-img"
                    />
                  ) : (
                    <h1 className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight truncate">
                      {brandName}
                    </h1>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-[#64748B] hover:text-[#0F172A] dark:text-[#A1A1AA] dark:hover:text-[#FAFAFA]"
              data-testid="sidebar-toggle"
            >
              <Menu className="w-5 h-5" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-3 space-y-1">
            {sidebarOpen && (
              <div className="mb-2 px-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#94A3B8] dark:text-[#71717A]" data-testid="active-portal-label">
                {effectivePortal === 'dispatch' ? <Truck className="w-3.5 h-3.5" /> : <Briefcase className="w-3.5 h-3.5" />}
                {effectivePortal === 'dispatch' ? 'Dispatch Portal' : 'Employee Portal'}
              </div>
            )}
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <button
                  key={item.name}
                  onClick={() => navigate(item.href)}
                  data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                    active
                      ? 'bg-[#4F46E5] text-white'
                      : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
                  }`}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <AnimatePresence>
                    {sidebarOpen && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-sm font-medium"
                      >
                        {item.name}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              );
            })}
            {activeDispatchOps.length > 0 && (
              <>
                {sidebarOpen && (
                  <div className="pt-3 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-[#4F46E5] dark:text-[#A5B4FC]" data-testid="nav-group-operations">
                    Dispatch Operations
                  </div>
                )}
                {activeDispatchOps.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <button
                      key={item.name}
                      onClick={() => navigate(item.href)}
                      data-testid={`nav-${item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                        active ? 'bg-[#4F46E5] text-white'
                          : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
                      }`}
                    >
                      <Icon className="w-5 h-5 flex-shrink-0" />
                      <AnimatePresence>
                        {sidebarOpen && (
                          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm font-medium">
                            {item.name}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </button>
                  );
                })}
              </>
            )}
            {activeDispatchFin.length > 0 && (
              <>
                {sidebarOpen && (
                  <div className="pt-5 pb-2 px-3 text-[10px] font-bold uppercase tracking-wider text-[#059669] dark:text-[#6EE7B7]" data-testid="nav-group-financial">
                    Dispatch Financial Report
                  </div>
                )}
                {activeDispatchFin.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <button
                      key={item.name}
                      onClick={() => navigate(item.href)}
                      data-testid={`nav-${item.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                        active ? 'bg-[#4F46E5] text-white'
                          : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] hover:text-[#0F172A] dark:hover:text-[#FAFAFA]'
                      }`}
                    >
                      <Icon className="w-5 h-5 flex-shrink-0" />
                      <AnimatePresence>
                        {sidebarOpen && (
                          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm font-medium">
                            {item.name}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </button>
                  );
                })}
              </>
            )}
            {canDispatch && (
              <button
                onClick={switchPortal}
                data-testid="switch-portal-button"
                className="mt-3 w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border border-dashed border-[#4F46E5]/40 text-[#4F46E5] hover:bg-[#4F46E5]/10 transition-colors"
              >
                <ArrowLeftRight className="w-5 h-5 flex-shrink-0" />
                <AnimatePresence>
                  {sidebarOpen && (
                    <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm font-medium">
                      {effectivePortal === 'dispatch' ? 'Switch to Employee Portal' : 'Switch to Dispatch Portal'}
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            )}
          </nav>

          {/* User Profile */}
          <div className="p-3 border-t border-[#E2E8F0] dark:border-[#27272A]">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#F1F5F9] dark:hover:bg-[#27272A] transition-colors"
                  data-testid="user-menu-trigger"
                >
                  <Avatar className="w-8 h-8">
                    <AvatarImage src={user?.avatar_path} />
                    <AvatarFallback className="bg-[#4F46E5] text-white text-sm">
                      {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  {sidebarOpen && (
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA] truncate">
                        {user?.name}
                      </p>
                      <p className="text-xs text-[#64748B] dark:text-[#A1A1AA] truncate">
                        {user?.role}
                      </p>
                    </div>
                  )}
                  {sidebarOpen && <ChevronDown className="w-4 h-4 text-[#64748B] dark:text-[#A1A1AA]" />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate('/dashboard/settings')}>
                  Profile Settings
                </DropdownMenuItem>
                <DropdownMenuItem onClick={toggleTheme}>
                  {theme === 'light' ? <Moon className="w-4 h-4 mr-2" /> : <Sun className="w-4 h-4 mr-2" />}
                  {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} data-testid="logout-button">
                  <LogOut className="w-4 h-4 mr-2" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </motion.aside>

      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-white dark:bg-[#18181B] border-b border-[#E2E8F0] dark:border-[#27272A] z-30 flex items-center justify-between px-4">
        {brandLogo ? (
          <img
            src={brandLogo}
            alt={brandName}
            className="h-9 max-w-[160px] object-contain"
            data-testid="mobile-app-logo-img"
          />
        ) : (
          <h1 className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{brandName}</h1>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          data-testid="mobile-menu-toggle"
        >
          {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </Button>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            exit={{ x: -300 }}
            className="lg:hidden fixed inset-y-0 left-0 w-64 bg-white dark:bg-[#18181B] border-r border-[#E2E8F0] dark:border-[#27272A] z-40 pt-16 flex flex-col"
          >
            <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
              {[...navigation, ...activeDispatchNav].map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);
                return (
                  <button
                    key={item.name}
                    onClick={() => {
                      navigate(item.href);
                      setMobileMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                      active
                        ? 'bg-[var(--brand-primary)] text-[var(--brand-primary-fg)]'
                        : 'text-[#64748B] dark:text-[#A1A1AA] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A]'
                    }`}
                    data-testid={`mobile-nav-${item.name.toLowerCase().replace(/\W+/g, '-')}`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-sm font-medium">{item.name}</span>
                  </button>
                );
              })}
              {canDispatch && (
                <button
                  onClick={switchPortal}
                  data-testid="mobile-switch-portal-button"
                  className="mt-2 w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border border-dashed border-[#4F46E5]/40 text-[#4F46E5] hover:bg-[#4F46E5]/10"
                >
                  <ArrowLeftRight className="w-5 h-5" />
                  <span className="text-sm font-medium">
                    {effectivePortal === 'dispatch' ? 'Switch to Employee Portal' : 'Switch to Dispatch Portal'}
                  </span>
                </button>
              )}
            </nav>

            {/* User footer — profile shortcut, settings and Logout for
                mobile / tablet users who can't reach the top-right avatar
                dropdown that only appears on the desktop sidebar. */}
            <div className="p-3 border-t border-[#E2E8F0] dark:border-[#27272A] space-y-1" data-testid="mobile-user-footer">
              <div className="flex items-center gap-3 px-3 py-2">
                <Avatar className="w-9 h-9">
                  <AvatarImage src={user?.avatar_path} alt={user?.name || 'User'} />
                  <AvatarFallback className="bg-[var(--brand-primary)] text-[var(--brand-primary-fg)] text-xs font-semibold">
                    {(user?.name || 'U').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{user?.name || 'User'}</div>
                  <div className="text-xs text-[#64748B] dark:text-[#A1A1AA] truncate">{user?.email}</div>
                </div>
              </div>
              <button
                onClick={() => { navigate('/dashboard/settings'); setMobileMenuOpen(false); }}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[#334155] dark:text-[#E4E4E7] hover:bg-[#F1F5F9] dark:hover:bg-[#27272A]"
                data-testid="mobile-profile-btn"
              >
                <User className="w-4 h-4" /> Profile
              </button>
              <button
                onClick={() => { setMobileMenuOpen(false); handleLogout(); }}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-semibold text-[var(--danger)] hover:bg-rose-50 dark:hover:bg-rose-950/30"
                data-testid="mobile-logout-btn"
              >
                <LogOut className="w-4 h-4" /> Logout
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main
        className="transition-all duration-300 lg:ml-[--sidebar-width]"
        style={{
          '--sidebar-width': sidebarOpen ? '256px' : '64px',
        }}
      >
        <div className="pt-16 lg:pt-0 min-w-0">
          {/* Top Bar */}
          <div className="h-16 bg-white/70 dark:bg-[#18181B]/70 backdrop-blur-xl border-b border-[#E2E8F0] dark:border-[#27272A] px-3 md:px-6 flex items-center justify-between gap-3">
            <div className="flex-1 min-w-0 max-w-2xl">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#64748B] dark:text-[#A1A1AA]" />
                <Input
                  placeholder="Search..."
                  className="pl-11 bg-[#F8FAFC] dark:bg-[#09090B] border-[#E2E8F0] dark:border-[#27272A]"
                  data-testid="global-search-input"
                />
              </div>
            </div>

            <div className="flex items-center gap-1 md:gap-3 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                data-testid="theme-toggle-button"
              >
                {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              </Button>
              <Button variant="ghost" size="icon" data-testid="notifications-button-old" className="hidden">
                <Bell className="w-5 h-5" />
              </Button>
              <NotificationBell />
            </div>
          </div>

          {/* Page Content */}
          <div className="p-3 md:p-6">
            <Outlet />
          </div>
        </div>
      </main>
      <LocationStreamer />
    </div>
  );
};

export default DashboardLayout;