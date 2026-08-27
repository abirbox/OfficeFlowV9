import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Users, CheckSquare, FolderKanban, TrendingUp, Clock, MapPin, FileText, Radio } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '@/stores/authStore';

const DashboardHome = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const isAdmin = ['super_admin', 'admin'].includes(user?.role);

  useEffect(() => {
    (async () => {
      try {
        const promises = [api.get('/admin/dashboard-stats')];
        if (isAdmin) promises.push(api.get('/admin/employee-status'));
        const results = await Promise.all(promises);
        setStats(results[0].data);
        if (isAdmin && results[1]) setEmployees(results[1].data);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    })();
  }, [isAdmin]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  const statCards = [
    { title: 'Total Employees', value: stats?.total_employees ?? 0, icon: Users, color: 'bg-blue-500' },
    { title: 'Present Today', value: stats?.present_today ?? 0, icon: CheckSquare, color: 'bg-green-500' },
    { title: 'Active Shifts', value: stats?.active_shifts ?? 0, icon: FolderKanban, color: 'bg-purple-500' },
    { title: 'On Field (GPS)', value: stats?.active_on_field ?? 0, icon: MapPin, color: 'bg-orange-500' },
  ];

  const workingEmployees = employees.filter((e) => e.status === 'working');

  return (
    <div data-testid="dashboard-home">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
          Welcome back, {user?.name?.split(' ')[0] || 'User'}!
        </h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
          {isAdmin
            ? `Real-time overview of your organization`
            : `Here's a snapshot of your workspace`}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="border-[#E2E8F0] dark:border-[#27272A] hover:shadow-lg transition-shadow" data-testid={`stat-card-${index}`}>
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-[#64748B] dark:text-[#A1A1AA]">{stat.title}</p>
                      <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight">{stat.value}</p>
                    </div>
                    <div className={`${stat.color} p-3 rounded-xl`}>
                      <Icon className="w-6 h-6 text-white" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <Card className="lg:col-span-2 border-[#E2E8F0] dark:border-[#27272A]" data-testid="employee-status-panel">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Radio className="w-5 h-5 text-green-500 animate-pulse" />
                  Live Employee Status
                </CardTitle>
                <Button variant="outline" size="sm" onClick={() => navigate('/dashboard/live-map')} data-testid="open-live-map-button">
                  <MapPin className="w-4 h-4 mr-2" />
                  Open Live Map
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {employees.length === 0 ? (
                <p className="text-center py-8 text-[#64748B]">No employees added yet</p>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {employees.slice(0, 10).map((emp, i) => (
                    <motion.div
                      key={emp.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      onClick={() => navigate(`/dashboard/employees/${emp.id}`)}
                      className="flex items-center gap-3 p-3 rounded-lg hover:bg-[#F8FAFC] dark:hover:bg-[#27272A] cursor-pointer transition-colors"
                      data-testid={`employee-row-${emp.id}`}
                    >
                      <Avatar>
                        <AvatarImage src={emp.avatar_path} />
                        <AvatarFallback className="bg-[#4F46E5] text-white">
                          {emp.name.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA] truncate">{emp.name}</p>
                        <p className="text-xs text-[#64748B] truncate">{emp.role} · {emp.total_hours.toFixed(2)} hrs today</p>
                      </div>
                      <Badge
                        className={
                          emp.status === 'working'
                            ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : emp.status === 'checked_out'
                            ? 'bg-gray-100 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400'
                            : 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400'
                        }
                      >
                        {emp.status === 'working' ? 'Working' : emp.status === 'checked_out' ? 'Done' : 'Not Started'}
                      </Badge>
                      {emp.gps_active && <Radio className="w-4 h-4 text-green-500 animate-pulse" />}
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-[#E2E8F0] dark:border-[#27272A]">
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <button
                  onClick={() => navigate('/dashboard/employees')}
                  className="w-full p-4 bg-[#4F46E5] hover:bg-[#4338CA] text-white rounded-lg transition-colors text-left"
                  data-testid="manage-employees-button"
                >
                  <p className="font-medium">Manage Employees</p>
                  <p className="text-sm text-indigo-100">Add, edit, change roles</p>
                </button>
                <button
                  onClick={() => navigate('/dashboard/shifts')}
                  className="w-full p-4 bg-[#F1F5F9] dark:bg-[#27272A] hover:bg-[#E2E8F0] dark:hover:bg-[#3F3F46] rounded-lg transition-colors text-left"
                  data-testid="assign-shift-button"
                >
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Assign Shift</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">In office or work from home</p>
                </button>
                <button
                  onClick={() => navigate('/dashboard/leaves')}
                  className="w-full p-4 bg-[#F1F5F9] dark:bg-[#27272A] hover:bg-[#E2E8F0] dark:hover:bg-[#3F3F46] rounded-lg transition-colors text-left relative"
                  data-testid="approve-leaves-button"
                >
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Approve Leaves</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">{stats?.pending_leaves || 0} pending</p>
                  {stats?.pending_leaves > 0 && (
                    <Badge className="absolute top-2 right-2 bg-orange-500 text-white">{stats.pending_leaves}</Badge>
                  )}
                </button>
                <button
                  onClick={() => navigate('/dashboard/live-map')}
                  className="w-full p-4 bg-[#F1F5F9] dark:bg-[#27272A] hover:bg-[#E2E8F0] dark:hover:bg-[#3F3F46] rounded-lg transition-colors text-left"
                >
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">Live Location Map</p>
                  <p className="text-sm text-[#64748B] dark:text-[#A1A1AA]">See who's where in real-time</p>
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default DashboardHome;
