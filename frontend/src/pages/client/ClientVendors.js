import { useEffect, useState } from 'react';
import { api } from '@/lib/axios';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { STATUS_BADGE } from '@/pages/dashboard/dispatch/_shared';

const ClientVendors = () => {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (search) params.search = search;
    api.get('/portal/vendors', { params })
      .then(({ data }) => setRows(Array.isArray(data) ? data : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [search]);

  return (
    <div className="space-y-6" data-testid="client-vendors">
      <div>
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">My Vendors</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] mt-1">Vendors assigned to serve your account.</p>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
        <Input placeholder="Search vendors..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" data-testid="client-vendor-search" />
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Contact</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">City</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-[#64748B]">No vendors assigned to your account yet</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id} data-testid={`client-vendor-row-${r.id}`}>
                <td className="px-4 py-3 font-medium text-[#0F172A] dark:text-[#FAFAFA]">{r.name}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.code || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.contact_person || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.contact_number || '—'}</td>
                <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{r.city || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE[r.status] || STATUS_BADGE.inactive}`}>{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ClientVendors;
