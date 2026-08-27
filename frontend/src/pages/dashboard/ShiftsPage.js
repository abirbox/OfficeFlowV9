import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Plus, Clock, Building, Home, Play, Square, XCircle, Calendar as CalendarIcon, MessageCircle, Users2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import ShiftCommentsDialog from '@/components/ShiftCommentsDialog';
import BulkAssignShiftDialog from '@/components/BulkAssignShiftDialog';
import { firstOfMonthIso, lastOfMonthIso } from '@/lib/datetime';

const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const ShiftsPage = () => {
  const { user } = useAuthStore();
  const [shifts, setShifts] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const [commentsShift, setCommentsShift] = useState(null);
  const isAdmin = user && ['super_admin', 'admin', 'hr', 'manager'].includes(user.role);

  const firstDayOfMonth = firstOfMonthIso();
  const lastDayOfMonth = lastOfMonthIso();

  const [form, setForm] = useState({
    user_id: '', title: 'Regular Shift', work_location: 'in_office',
    start_time: '09:00', end_time: '17:00',
    days_of_week: [1, 2, 3, 4, 5],
    effective_from: firstDayOfMonth, effective_to: lastDayOfMonth,
  });

  const fetchShifts = useCallback(async () => {
    try {
      const promises = [api.get('/shifts')];
      if (isAdmin) promises.push(api.get('/employees'));
      const [shiftsRes, empsRes] = await Promise.all(promises);
      setShifts(shiftsRes.data);
      if (empsRes) setEmployees(empsRes.data);
    } catch (e) {
      toast.error('Failed to load shifts');
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => { fetchShifts(); }, [fetchShifts]);

  const toggleDay = (d) => {
    setForm({
      ...form,
      days_of_week: form.days_of_week.includes(d)
        ? form.days_of_week.filter((x) => x !== d)
        : [...form.days_of_week, d].sort(),
    });
  };

  const handleCreate = async () => {
    if (!form.user_id) return toast.error('Please select an employee');
    if (form.days_of_week.length === 0) return toast.error('Pick at least one day');
    try {
      await api.post('/shifts', form);
      setDialogOpen(false);
      fetchShifts();
      toast.success('Shift assigned');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  const handleAction = async (shiftId, action) => {
    setBusy(shiftId + action);
    try {
      const { data } = await api.post(`/shifts/${shiftId}/${action}`);
      const msg = action === 'join' ? (data.is_late ? `Joined but you're ${data.late_minutes} min late` : 'Work started! GPS tracking active')
                : action === 'end' ? `Work ended. ${data.overtime_minutes > 0 ? `Overtime: ${data.overtime_minutes} min` : 'On time!'}`
                : 'Shift cancelled - admin notified';
      toast.success(msg);
      fetchShifts();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>;

  return (
    <div data-testid="shifts-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            {isAdmin ? 'Work Shifts' : 'My Shifts'}
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {isAdmin ? 'Assign weekly work routines to employees' : 'Your assigned work shifts — Join to start work'}
          </p>
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setBulkOpen(true)} data-testid="open-bulk-assign">
              <Users2 className="w-4 h-4 mr-2" /> Bulk Assign
            </Button>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="assign-shift-button">
                <Plus className="w-5 h-5 mr-2" /> Assign Shift
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Assign Work Shift</DialogTitle>
                <DialogDescription>Set a weekly routine that repeats across the month</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Employee</Label>
                  <Select value={form.user_id} onValueChange={(v) => setForm({ ...form, user_id: v })}>
                    <SelectTrigger data-testid="shift-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
                    <SelectContent>
                      {employees.map((e) => <SelectItem key={e.id} value={e.id}>{e.name} · {e.role}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Shift Title</Label>
                  <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="shift-title-input" />
                </div>
                <div className="space-y-2">
                  <Label>Work Location</Label>
                  <div className="grid grid-cols-2 gap-3">
                    <button type="button" onClick={() => setForm({ ...form, work_location: 'in_office' })}
                      data-testid="shift-loc-office"
                      className={`p-4 rounded-lg border-2 ${form.work_location === 'in_office' ? 'border-[#4F46E5] bg-[#4F46E5]/5' : 'border-[#E2E8F0] dark:border-[#27272A]'}`}>
                      <Building className={`w-6 h-6 mx-auto mb-2 ${form.work_location === 'in_office' ? 'text-[#4F46E5]' : 'text-[#64748B]'}`} />
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">In Office</p>
                    </button>
                    <button type="button" onClick={() => setForm({ ...form, work_location: 'work_from_home' })}
                      data-testid="shift-loc-wfh"
                      className={`p-4 rounded-lg border-2 ${form.work_location === 'work_from_home' ? 'border-[#4F46E5] bg-[#4F46E5]/5' : 'border-[#E2E8F0] dark:border-[#27272A]'}`}>
                      <Home className={`w-6 h-6 mx-auto mb-2 ${form.work_location === 'work_from_home' ? 'text-[#4F46E5]' : 'text-[#64748B]'}`} />
                      <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">Work from Home</p>
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Start Time</Label>
                    <Input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} data-testid="shift-start-time" />
                  </div>
                  <div className="space-y-2">
                    <Label>End Time</Label>
                    <Input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} data-testid="shift-end-time" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Days of Week (repeats weekly)</Label>
                  <div className="flex gap-2 flex-wrap">
                    {dayLabels.map((d, i) => {
                      const num = i + 1;
                      const active = form.days_of_week.includes(num);
                      return (
                        <button key={d} type="button" onClick={() => toggleDay(num)}
                          data-testid={`shift-day-${d.toLowerCase()}`}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${active ? 'bg-[#4F46E5] text-white border-[#4F46E5]' : 'border-[#E2E8F0] dark:border-[#27272A] text-[#64748B]'}`}>
                          {d}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Effective From</Label>
                    <Input type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label>Effective To</Label>
                    <Input type="date" value={form.effective_to} onChange={(e) => setForm({ ...form, effective_to: e.target.value })} />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleCreate} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="submit-shift-button">Assign Shift</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          </div>
        )}
      </div>

      {shifts.length === 0 ? (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-12 text-center">
            <CalendarIcon className="w-16 h-16 text-[#64748B] mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">No shifts yet</h3>
            <p className="text-[#64748B] dark:text-[#A1A1AA]">{isAdmin ? 'Assign a shift to get started' : 'No shifts have been assigned to you yet'}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {shifts.map((shift, i) => (
            <motion.div key={shift.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card className={`border-[#E2E8F0] dark:border-[#27272A] ${shift.status === 'active' ? 'ring-2 ring-green-500' : shift.status === 'cancelled' ? 'opacity-60' : ''}`} data-testid={`shift-card-${shift.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{shift.title}</CardTitle>
                      {isAdmin && <p className="text-sm text-[#64748B] mt-1">{shift.user_name}</p>}
                    </div>
                    <Badge className={
                      shift.status === 'active' ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 animate-pulse' :
                      shift.status === 'cancelled' ? 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400' :
                      'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
                    }>{shift.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="w-4 h-4 text-[#64748B]" />
                    <span className="text-[#0F172A] dark:text-[#FAFAFA] font-medium">{shift.start_time} - {shift.end_time}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    {shift.work_location === 'in_office' ? (
                      <><Building className="w-4 h-4 text-[#64748B]" /><span className="text-[#0F172A] dark:text-[#FAFAFA]">In Office</span></>
                    ) : (
                      <><Home className="w-4 h-4 text-[#64748B]" /><span className="text-[#0F172A] dark:text-[#FAFAFA]">Work from Home</span></>
                    )}
                  </div>
                  <div className="flex gap-1 flex-wrap">
                    {shift.days_of_week.map((d) => (
                      <Badge key={d} variant="outline" className="text-xs">{dayLabels[d - 1]}</Badge>
                    ))}
                  </div>
                  <p className="text-xs text-[#64748B]">{shift.effective_from} to {shift.effective_to}</p>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setCommentsShift(shift)}
                    className="w-full mt-1"
                    data-testid={`shift-chat-${shift.id}`}
                  >
                    <MessageCircle className="w-4 h-4 mr-2" /> Messages
                  </Button>
                  
                  {!isAdmin && shift.status !== 'cancelled' && (
                    <div className="flex gap-2 pt-2">
                      {shift.status !== 'active' ? (
                        <>
                          <Button size="sm" onClick={() => handleAction(shift.id, 'join')} disabled={busy === shift.id + 'join'}
                            className="flex-1 bg-green-600 hover:bg-green-700" data-testid={`join-shift-${shift.id}`}>
                            <Play className="w-4 h-4 mr-1" /> Join Work
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => handleAction(shift.id, 'cancel')} disabled={busy === shift.id + 'cancel'} data-testid={`cancel-shift-${shift.id}`} title="Cancel Shift" aria-label="Cancel Shift">
                            <XCircle className="w-4 h-4 mr-1" /> Cancel
                          </Button>
                        </>
                      ) : (
                        <Button size="sm" onClick={() => handleAction(shift.id, 'end')} disabled={busy === shift.id + 'end'}
                          className="flex-1 bg-red-600 hover:bg-red-700" data-testid={`end-shift-${shift.id}`}>
                          <Square className="w-4 h-4 mr-1" /> End Work
                        </Button>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      <ShiftCommentsDialog
        open={!!commentsShift}
        onOpenChange={(o) => !o && setCommentsShift(null)}
        shift={commentsShift}
        currentUserId={user?.id}
      />
      <BulkAssignShiftDialog
        open={bulkOpen}
        onOpenChange={setBulkOpen}
        employees={employees}
        onDone={fetchShifts}
      />
    </div>
  );
};

export default ShiftsPage;
