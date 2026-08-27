import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { FileText, Plus, CheckCircle2, XCircle } from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const LeavesPage = () => {
  const { user } = useAuthStore();
  const [leaves, setLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newLeave, setNewLeave] = useState({ type: 'annual', start_date: '', end_date: '', reason: '' });
  const isAdmin = ['super_admin', 'admin', 'hr'].includes(user?.role);

  const fetchLeaves = async () => {
    try {
      const { data } = await api.get('/leaves');
      setLeaves(data);
    } catch (error) {
      toast.error('Failed to load leaves');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeaves(); }, []);

  const handleApply = async () => {
    if (!newLeave.start_date || !newLeave.end_date) return toast.error('Please pick dates');
    try {
      await api.post('/leaves', newLeave);
      setNewLeave({ type: 'annual', start_date: '', end_date: '', reason: '' });
      setDialogOpen(false);
      fetchLeaves();
      toast.success('Leave request submitted');
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const handleAction = async (leaveId, status) => {
    try {
      await api.put(`/leaves/${leaveId}`, { status, admin_note: `${status} by ${user.name}` });
      fetchLeaves();
      toast.success(`Leave ${status}`);
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    }
  };

  const pending = leaves.filter((l) => l.status === 'pending');
  const others = leaves.filter((l) => l.status !== 'pending');

  const stats = [
    { label: 'Pending', value: pending.length, color: 'bg-orange-500' },
    { label: 'Approved', value: leaves.filter((l) => l.status === 'approved').length, color: 'bg-green-500' },
    { label: 'Rejected', value: leaves.filter((l) => l.status === 'rejected').length, color: 'bg-red-500' },
    { label: 'Total', value: leaves.length, color: 'bg-blue-500' },
  ];

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>;
  }

  return (
    <div data-testid="leaves-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            {isAdmin ? 'Leave Requests' : 'My Leaves'}
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {isAdmin ? 'Review and approve team leave requests' : 'Track your leave balance and history'}
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="apply-leave-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">
              <Plus className="w-5 h-5 mr-2" />
              Apply for Leave
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Apply for Leave</DialogTitle>
              <DialogDescription>Submit a leave request for approval</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Type</Label>
                <Select value={newLeave.type} onValueChange={(v) => setNewLeave({ ...newLeave, type: v })}>
                  <SelectTrigger data-testid="leave-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="annual">Annual</SelectItem>
                    <SelectItem value="sick">Sick</SelectItem>
                    <SelectItem value="casual">Casual</SelectItem>
                    <SelectItem value="unpaid">Unpaid</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Start Date</Label>
                  <Input type="date" data-testid="leave-start-date" value={newLeave.start_date} onChange={(e) => setNewLeave({ ...newLeave, start_date: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label>End Date</Label>
                  <Input type="date" data-testid="leave-end-date" value={newLeave.end_date} onChange={(e) => setNewLeave({ ...newLeave, end_date: e.target.value })} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Reason</Label>
                <Textarea data-testid="leave-reason-input" rows={3} value={newLeave.reason} onChange={(e) => setNewLeave({ ...newLeave, reason: e.target.value })} placeholder="Why do you need this leave?" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleApply} data-testid="submit-leave-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">Submit Request</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat, i) => (
          <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
            <Card className="border-[#E2E8F0] dark:border-[#27272A]">
              <CardContent className="p-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-[#64748B] dark:text-[#A1A1AA]">{stat.label}</span>
                  <div className={`w-3 h-3 rounded-full ${stat.color}`}></div>
                </div>
                <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{stat.value}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {isAdmin && pending.length > 0 && (
        <Card className="border-[#E2E8F0] dark:border-[#27272A] mb-6" data-testid="pending-leaves-section">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge className="bg-orange-500">{pending.length}</Badge>
              Pending Approval
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {pending.map((leave) => (
                <div key={leave.id} className="p-4 border border-orange-200 dark:border-orange-800 bg-orange-50/50 dark:bg-orange-900/10 rounded-lg" data-testid={`leave-pending-${leave.id}`}>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{leave.user_name} <span className="text-sm text-[#64748B]">({leave.user_email})</span></p>
                      <p className="text-sm text-[#64748B]">{leave.type} · {leave.start_date} to {leave.end_date} · {leave.days} days</p>
                      {leave.reason && <p className="text-sm mt-2 text-[#0F172A] dark:text-[#FAFAFA]">"{leave.reason}"</p>}
                    </div>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" onClick={() => handleAction(leave.id, 'approved')} data-testid={`approve-${leave.id}`} className="bg-green-600 hover:bg-green-700">
                      <CheckCircle2 className="w-4 h-4 mr-1" /> Approve
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => handleAction(leave.id, 'rejected')} data-testid={`reject-${leave.id}`}>
                      <XCircle className="w-4 h-4 mr-1" /> Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-[#E2E8F0] dark:border-[#27272A]">
        <CardHeader>
          <CardTitle>Leave History</CardTitle>
        </CardHeader>
        <CardContent>
          {others.length === 0 && (!isAdmin || pending.length === 0) ? (
            <p className="text-center py-8 text-[#64748B]">No leave records yet</p>
          ) : (
            <div className="space-y-3">
              {(isAdmin ? others : leaves).map((leave) => (
                <div key={leave.id} className="p-4 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg flex items-center justify-between" data-testid={`leave-${leave.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-[#4F46E5] rounded-lg flex items-center justify-center">
                      <FileText className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA] capitalize">{leave.type} {isAdmin && `· ${leave.user_name}`}</p>
                      <p className="text-sm text-[#64748B]">{leave.start_date} to {leave.end_date} ({leave.days} days)</p>
                    </div>
                  </div>
                  <Badge className={
                    leave.status === 'approved' ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : leave.status === 'rejected' ? 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                    : 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400'
                  }>
                    {leave.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default LeavesPage;
