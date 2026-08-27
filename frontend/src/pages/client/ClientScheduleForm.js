import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';

const SHIFT_TYPES = ['Morning', 'Afternoon', 'Evening', 'Night'];

const empty = (date) => ({
  date: date || '',
  shift_type: 'Morning',
  start_time: '09:00',
  end_time: '17:00',
  post_site_id: '',
  officer_id: '',
  vendor_id: '',
  remarks: '',
});

/**
 * Shared create/edit/delete dialog for client dispatch schedules.
 * All options are loaded from client-scoped /portal endpoints, so a client
 * can only ever pick their own post sites, officers and vendors.
 */
export default function ClientScheduleForm({ open, onOpenChange, editing, defaultDate, onSaved }) {
  const [form, setForm] = useState(empty(defaultDate));
  const [postSites, setPostSites] = useState([]);
  const [officers, setOfficers] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    Promise.all([
      api.get('/portal/post-sites').then((r) => r.data).catch(() => []),
      api.get('/portal/officers').then((r) => r.data).catch(() => []),
      api.get('/portal/vendors').then((r) => r.data).catch(() => []),
    ]).then(([ps, of, ve]) => { setPostSites(ps); setOfficers(of); setVendors(ve); });

    if (editing) {
      setForm({
        date: editing.date || '',
        shift_type: editing.shift_type || 'Morning',
        start_time: editing.start_time || '09:00',
        end_time: editing.end_time || '17:00',
        post_site_id: editing.post_site_id || '',
        officer_id: editing.officer_id || '',
        vendor_id: editing.vendor_id || '',
        remarks: editing.remarks || '',
      });
    } else {
      setForm(empty(defaultDate));
    }
  }, [open, editing, defaultDate]);

  const setF = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.date || !form.post_site_id || !form.officer_id || !form.vendor_id) {
      toast.error('Date, Post Site, Officer and Vendor are required');
      return;
    }
    setSaving(true);
    try {
      if (editing) await api.put(`/portal/schedules/${editing.id}`, form);
      else await api.post('/portal/schedules', form);
      toast.success(`Dispatch ${editing ? 'updated' : 'created'}`);
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!editing) return;
    if (!window.confirm('Delete this dispatch? This cannot be undone.')) return;
    try {
      await api.delete(`/portal/schedules/${editing.id}`);
      toast.success('Dispatch deleted');
      onOpenChange(false);
      onSaved && onSaved();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto" data-testid="client-schedule-form">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit Dispatch' : 'Add Dispatch'}</DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label>Date *</Label>
            <Input type="date" value={form.date} onChange={(e) => setF('date', e.target.value)} data-testid="sf-date" />
          </div>
          <div className="space-y-1">
            <Label>Shift Type *</Label>
            <Select value={form.shift_type} onValueChange={(v) => setF('shift_type', v)}>
              <SelectTrigger data-testid="sf-shift-type"><SelectValue /></SelectTrigger>
              <SelectContent>{SHIFT_TYPES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Start Time *</Label>
            <Input type="time" value={form.start_time} onChange={(e) => setF('start_time', e.target.value)} data-testid="sf-start" />
          </div>
          <div className="space-y-1">
            <Label>End Time *</Label>
            <Input type="time" value={form.end_time} onChange={(e) => setF('end_time', e.target.value)} data-testid="sf-end" />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Post Site *</Label>
            <Select value={form.post_site_id} onValueChange={(v) => setF('post_site_id', v)}>
              <SelectTrigger data-testid="sf-post-site"><SelectValue placeholder="Select post site" /></SelectTrigger>
              <SelectContent>
                {postSites.map((p) => <SelectItem key={p.id} value={p.id}>{p.post_pin} — {p.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Officer *</Label>
            <Select value={form.officer_id} onValueChange={(v) => setF('officer_id', v)}>
              <SelectTrigger data-testid="sf-officer"><SelectValue placeholder="Select officer" /></SelectTrigger>
              <SelectContent>
                {officers.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}{o.officer_code ? ` (${o.officer_code})` : ''}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Vendor *</Label>
            <Select value={form.vendor_id} onValueChange={(v) => setF('vendor_id', v)}>
              <SelectTrigger data-testid="sf-vendor"><SelectValue placeholder="Select vendor" /></SelectTrigger>
              <SelectContent>
                {vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label>Remarks</Label>
            <Textarea value={form.remarks} onChange={(e) => setF('remarks', e.target.value)} data-testid="sf-remarks" />
          </div>
        </div>

        <DialogFooter>
          {editing && (
            <Button variant="ghost" className="text-red-600 mr-auto" onClick={remove} data-testid="sf-delete">Delete</Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={submit} disabled={saving} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="sf-save">
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
