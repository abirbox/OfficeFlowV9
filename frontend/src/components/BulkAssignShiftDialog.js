import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from '@/components/ui/sonner';
import { Users2, Building, Home } from 'lucide-react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { firstOfMonthIso, lastOfMonthIso } from '@/lib/datetime';

const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const BulkAssignShiftDialog = ({ open, onOpenChange, employees, onDone }) => {
  const firstDayOfMonth = firstOfMonthIso();
  const lastDayOfMonth = lastOfMonthIso();

  const [selected, setSelected] = useState([]);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [form, setForm] = useState({
    title: 'Regular Shift',
    work_location: 'in_office',
    start_time: '09:00',
    end_time: '17:00',
    days_of_week: [1,2,3,4,5],
    effective_from: firstDayOfMonth,
    effective_to: lastDayOfMonth,
  });

  useEffect(() => {
    if (!open) { setSelected([]); setSearch(''); }
  }, [open]);

  const filtered = employees.filter((e) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (e.name || '').toLowerCase().includes(q) || (e.email || '').toLowerCase().includes(q);
  });

  const toggleEmp = (id) => {
    setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  };

  const toggleDay = (d) => {
    setForm((f) => ({ ...f, days_of_week: f.days_of_week.includes(d) ? f.days_of_week.filter((x) => x !== d) : [...f.days_of_week, d].sort() }));
  };

  const selectAllVisible = () => {
    const ids = filtered.map((e) => e.id);
    setSelected((s) => Array.from(new Set([...s, ...ids])));
  };
  const clearAll = () => setSelected([]);

  const submit = async () => {
    if (selected.length === 0) return toast.error('Pick at least one employee');
    if (form.days_of_week.length === 0) return toast.error('Pick at least one weekday');
    setBusy(true);
    try {
      const { data } = await api.post('/shifts/bulk', { ...form, user_ids: selected });
      toast.success(`${data.created_count} shift${data.created_count === 1 ? '' : 's'} created${data.skipped.length ? ` · ${data.skipped.length} skipped (overlap)` : ''}`);
      onDone?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto" data-testid="bulk-assign-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Users2 className="w-5 h-5" /> Bulk Assign Shift</DialogTitle>
          <DialogDescription>Pick employees and apply the same weekly shift template to all of them at once.</DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left: employee picker */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Employees ({selected.length} selected)</Label>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={selectAllVisible} data-testid="bulk-select-visible">All visible</Button>
                <Button variant="outline" size="sm" onClick={clearAll} data-testid="bulk-clear">Clear</Button>
              </div>
            </div>
            <Input placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="bulk-employee-search" />
            <div className="max-h-72 overflow-y-auto border border-[#E2E8F0] dark:border-[#27272A] rounded-lg divide-y divide-[#E2E8F0] dark:divide-[#27272A]" data-testid="bulk-employee-list">
              {filtered.length === 0 ? (
                <p className="p-4 text-sm text-[#64748B]">No employees match</p>
              ) : filtered.map((e) => (
                <label key={e.id} className="flex items-center gap-3 p-3 hover:bg-[#F8FAFC] dark:hover:bg-[#27272A] cursor-pointer" data-testid={`bulk-emp-${e.id}`}>
                  <Checkbox checked={selected.includes(e.id)} onCheckedChange={() => toggleEmp(e.id)} />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">{e.name}</p>
                    <p className="text-xs text-[#64748B]">{e.email} · {e.role}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Right: shift template */}
          <div className="space-y-3">
            <div className="space-y-1">
              <Label>Shift Title</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="bulk-title" />
            </div>
            <div className="space-y-1">
              <Label>Work Location</Label>
              <Select value={form.work_location} onValueChange={(v) => setForm({ ...form, work_location: v })}>
                <SelectTrigger data-testid="bulk-location"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="in_office"><Building className="w-4 h-4 inline mr-2" /> In office</SelectItem>
                  <SelectItem value="work_from_home"><Home className="w-4 h-4 inline mr-2" /> Work from home</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label>Start</Label><Input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} data-testid="bulk-start" /></div>
              <div className="space-y-1"><Label>End</Label><Input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} data-testid="bulk-end" /></div>
            </div>
            <div className="space-y-1">
              <Label>Days of the week</Label>
              <div className="flex flex-wrap gap-2">
                {dayLabels.map((d, i) => (
                  <button
                    key={d} type="button"
                    onClick={() => toggleDay(i + 1)}
                    className={`px-3 py-1 rounded-full text-sm border ${form.days_of_week.includes(i + 1) ? 'bg-[#4F46E5] text-white border-[#4F46E5]' : 'border-[#E2E8F0] dark:border-[#27272A] text-[#64748B]'}`}
                    data-testid={`bulk-day-${i + 1}`}
                  >{d}</button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label>Effective from</Label><Input type="date" value={form.effective_from} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} data-testid="bulk-from" /></div>
              <div className="space-y-1"><Label>Effective to</Label><Input type="date" value={form.effective_to} onChange={(e) => setForm({ ...form, effective_to: e.target.value })} data-testid="bulk-to" /></div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={submit} disabled={busy} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="bulk-submit">
            {busy ? 'Assigning…' : `Assign to ${selected.length} employee${selected.length === 1 ? '' : 's'}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default BulkAssignShiftDialog;
