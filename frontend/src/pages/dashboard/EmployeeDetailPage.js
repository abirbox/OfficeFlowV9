import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ArrowLeft, Clock, Calendar, MapPin, TrendingUp, Shield } from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import { formatTime, formatDateTime } from '@/lib/datetime';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const EmployeeDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [employee, setEmployee] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [roleDialog, setRoleDialog] = useState(false);
  const [newRole, setNewRole] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [empRes, statsRes] = await Promise.all([
          api.get(`/employees/${id}`),
          api.get(`/admin/employee/${id}/stats`),
        ]);
        setEmployee(empRes.data);
        setStats(statsRes.data);
        setNewRole(empRes.data.role);
      } catch (error) {
        toast.error(formatApiErrorDetail(error.response?.data?.detail));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleRoleChange = async () => {
    try {
      await api.put(`/admin/employee/${id}/role?role=${newRole}`);
      setEmployee({ ...employee, role: newRole });
      setRoleDialog(false);
      toast.success(`Role changed to ${newRole}`);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!employee) return <p>Employee not found</p>;

  const canChangeRole = user?.role === 'super_admin';

  return (
    <div data-testid="employee-detail-page">
      <Button variant="ghost" onClick={() => navigate('/dashboard/employees')} className="mb-4" data-testid="back-button">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Employees
      </Button>

      <div className="flex items-start justify-between mb-8">
        <div className="flex items-center gap-6">
          <Avatar className="w-24 h-24">
            <AvatarImage src={employee.avatar_path} />
            <AvatarFallback className="bg-[#4F46E5] text-white text-3xl">
              {employee.name.charAt(0).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div>
            <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight">{employee.name}</h1>
            <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">{employee.email}</p>
            <div className="flex items-center gap-2 mt-2">
              <Badge className="capitalize bg-[#4F46E5] text-white">{employee.role.replace('_', ' ')}</Badge>
              <Badge className={employee.status === 'active' ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400' : 'bg-gray-100 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400'}>
                {employee.status}
              </Badge>
            </div>
          </div>
        </div>
        {canChangeRole && (
          <Button onClick={() => setRoleDialog(true)} data-testid="change-role-button">
            <Shield className="w-4 h-4 mr-2" />
            Change Role
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-6">
            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mb-2">Days Present (Month)</p>
            <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{stats?.monthly?.days_present ?? 0}</p>
          </CardContent>
        </Card>
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-6">
            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mb-2">Total Hours (Month)</p>
            <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{stats?.monthly?.total_hours ?? 0}h</p>
          </CardContent>
        </Card>
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-6">
            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mb-2">Distance Traveled (Month)</p>
            <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{stats?.monthly?.total_distance_km ?? 0} km</p>
          </CardContent>
        </Card>
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-6">
            <p className="text-sm text-[#64748B] dark:text-[#A1A1AA] mb-2">Total Hours (Year)</p>
            <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{stats?.yearly?.total_hours ?? 0}h</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader>
            <CardTitle>Attendance History (This Month)</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.attendance_records?.length ? (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {stats.attendance_records.map((rec) => (
                  <div key={rec.id} className="p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg flex items-center justify-between">
                    <div>
                      <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{rec.date}</p>
                      <p className="text-xs text-[#64748B]">In: {rec.check_in ? formatTime(rec.check_in) : '-'} · Out: {rec.check_out ? formatTime(rec.check_out) : '-'}</p>
                    </div>
                    <Badge>{rec.total_hours?.toFixed(2) || 0}h</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-8 text-[#64748B]">No attendance records this month</p>
            )}
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader>
            <CardTitle>Recent GPS Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.gps_sessions?.length ? (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {stats.gps_sessions.map((s) => (
                  <div key={s.id} className="p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA] text-sm">{formatDateTime(s.started_at)}</p>
                      <Badge variant={s.status === 'active' ? 'default' : 'secondary'}>{s.status}</Badge>
                    </div>
                    <p className="text-xs text-[#64748B] mt-1">
                      {s.total_distance?.toFixed(2) || 0} km · {s.coordinates?.length || 0} points
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-8 text-[#64748B]">No GPS sessions</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={roleDialog} onOpenChange={setRoleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Role for {employee.name}</DialogTitle>
            <DialogDescription>
              Assign a new role. Only Super Admin can promote to Admin or Super Admin.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Select value={newRole} onValueChange={setNewRole}>
              <SelectTrigger data-testid="role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="employee">Employee</SelectItem>
                <SelectItem value="manager">Manager</SelectItem>
                <SelectItem value="hr">HR</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="super_admin">Super Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleDialog(false)}>Cancel</Button>
            <Button onClick={handleRoleChange} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-role-button">
              Save Role
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmployeeDetailPage;
