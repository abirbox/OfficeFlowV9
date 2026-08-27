import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search } from 'lucide-react';
import { STATUS_BADGE } from '@/pages/dashboard/dispatch/_shared';

const Field = ({ label, value }) => (
  <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-[#E2E8F0] dark:border-[#27272A] last:border-0">
    <div className="text-xs uppercase tracking-wider text-[#64748B]">{label}</div>
    <div className="col-span-2 text-sm text-[#334155] dark:text-[#E4E4E7]">{value || '—'}</div>
  </div>
);

const ClientOfficers = () => {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (search) params.search = search;
    api.get('/portal/officers', { params })
      .then(({ data }) => setRows(Array.isArray(data) ? data : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [search]);

  return (
    <div className="space-y-6" data-testid="client-officers">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Security Officers</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Officers assigned to your sites. Tap a row for full details.</p>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
        <Input placeholder="Search officers..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" data-testid="client-officer-search" />
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">Officer Code</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">No officers assigned to your account</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id} data-testid={`client-officer-row-${r.id}`}>
                <td className="px-4 py-3 font-mono text-[#334155] dark:text-[#E4E4E7]">{r.officer_code || '—'}</td>
                <td className="px-4 py-3 font-medium text-[#0F172A] dark:text-[#FAFAFA]">{r.name}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.type || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.contact_number || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE[r.status] || STATUS_BADGE.inactive}`}>{r.status}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => setSelected(r)} data-testid={`client-officer-view-${r.id}`}>View</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-lg" data-testid="client-officer-detail">
          <DialogHeader><DialogTitle>{selected?.name}</DialogTitle></DialogHeader>
          {selected && (
            <div>
              <Field label="Officer Code" value={selected.officer_code} />
              <Field label="Type" value={selected.type} />
              <Field label="Status" value={selected.status} />
              <Field label="Phone" value={selected.contact_number} />
              <Field label="Alt. Phone" value={selected.alternate_contact_number} />
              <Field label="Email" value={selected.email} />
              <Field label="SSC" value={selected.social_security_code} />
              <Field label="Address" value={selected.address} />
              <Field label="Joining Date" value={selected.joining_date} />
              <Field label="Notes" value={selected.notes} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ClientOfficers;
