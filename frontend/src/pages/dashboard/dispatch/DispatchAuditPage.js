import { useEffect, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import { ScrollText, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { formatDateTime } from '@/lib/datetime';

const ACTION_BADGE = {
  create: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  update: 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  status: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  confirm: 'bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300',
  cancel: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  delete: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
};

const ENTITY_LABEL = {
  client: 'Client', vendor: 'Vendor', officer: 'Officer',
  post_site: 'Post Site', schedule: 'Schedule',
};

const ALL = '__all__';

const summarizeChanges = (changes) => {
  if (!changes || typeof changes !== 'object') return null;
  const parts = Object.entries(changes).map(([k, v]) => {
    if (v && typeof v === 'object' && ('from' in v || 'to' in v)) {
      return `${k}: ${v.from ?? '—'} → ${v.to ?? '—'}`;
    }
    return `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`;
  });
  return parts.join(' · ');
};

const DispatchAuditPage = () => {
  const { user } = useAuthStore();
  const canView = hasPermission(user, 'dispatch.audit.view');

  const [entityType, setEntityType] = useState(ALL);
  const [action, setAction] = useState(ALL);
  const [actorId, setActorId] = useState(ALL);
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [limit] = useState(50);

  const [data, setData] = useState({ items: [], total: 0 });
  const [actors, setActors] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!canView) return;
    setLoading(true);
    try {
      const params = { page, limit };
      if (entityType !== ALL) params.entity_type = entityType;
      if (action !== ALL) params.action = action;
      if (actorId !== ALL) params.actor_id = actorId;
      if (search) params.search = search;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const { data } = await api.get('/dispatch/audit', { params });
      setData(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [canView, page, limit, entityType, action, actorId, search, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!canView) return;
    api.get('/dispatch/audit/actors').then(({ data }) => setActors(data)).catch(() => {});
  }, [canView]);

  // Reset to page 1 whenever a filter changes
  useEffect(() => { setPage(1); }, [entityType, action, actorId, search, dateFrom, dateTo]);

  const resetFilters = () => {
    setEntityType(ALL); setAction(ALL); setActorId(ALL);
    setSearch(''); setDateFrom(''); setDateTo('');
  };

  if (!canView) {
    return (
      <div className="p-8 text-[#64748B]" data-testid="audit-no-access">
        You do not have permission to view the Dispatch audit log.
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / limit));

  return (
    <div className="space-y-6" data-testid="dispatch-audit-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-[#4F46E5]/10 flex items-center justify-center">
            <ScrollText className="w-6 h-6 text-[#4F46E5]" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">Audit Log</h1>
            <p className="text-sm text-[#64748B] mt-1">
              {data.total} action{data.total !== 1 && 's'} recorded across the Dispatch module
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={resetFilters} data-testid="audit-reset">
          <RotateCcw className="w-4 h-4 mr-2" /> Reset filters
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div>
          <Label className="text-xs">Entity</Label>
          <Select value={entityType} onValueChange={setEntityType}>
            <SelectTrigger data-testid="audit-filter-entity"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All entities</SelectItem>
              {Object.entries(ENTITY_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Action</Label>
          <Select value={action} onValueChange={setAction}>
            <SelectTrigger data-testid="audit-filter-action"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All actions</SelectItem>
              {Object.keys(ACTION_BADGE).map((a) => <SelectItem key={a} value={a} className="capitalize">{a}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Actor</Label>
          <Select value={actorId} onValueChange={setActorId}>
            <SelectTrigger data-testid="audit-filter-actor"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All users</SelectItem>
              {actors.map((a) => <SelectItem key={a.actor_id} value={a.actor_id}>{a.name || a.actor_id}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Date From</Label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} data-testid="audit-filter-from" />
        </div>
        <div>
          <Label className="text-xs">Date To</Label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} data-testid="audit-filter-to" />
        </div>
        <div>
          <Label className="text-xs">Search</Label>
          <Input placeholder="Entity or user…" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="audit-filter-search" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Entity</th>
              <th className="px-4 py-3">Target</th>
              <th className="px-4 py-3">Changes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-[#64748B]">Loading…</td></tr>
            ) : data.items.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-[#64748B]">No audit entries match these filters.</td></tr>
            ) : data.items.map((row, i) => {
              const summary = summarizeChanges(row.changes);
              return (
                <tr key={row.id} data-testid={`audit-row-${i}`} className="hover:bg-[#F8FAFC] dark:hover:bg-[#0F0F11]">
                  <td className="px-4 py-3 whitespace-nowrap text-[#334155] dark:text-[#E4E4E7]">
                    {formatDateTime(row.at, { withZone: true })}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{row.actor_name || '—'}</span>
                    {row.actor_role && <span className="ml-1 text-xs text-[#94A3B8]">({row.actor_role})</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge className={`${ACTION_BADGE[row.action] || 'bg-slate-100 text-slate-600'} capitalize font-medium`}>
                      {row.action}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{ENTITY_LABEL[row.entity_type] || row.entity_type}</td>
                  <td className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">{row.entity_name || '—'}</td>
                  <td className="px-4 py-3 text-xs text-[#64748B] max-w-[360px] truncate" title={summary || ''}>
                    {summary || '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-[#64748B]">Page {page} of {totalPages}</p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} data-testid="audit-prev">
            <ChevronLeft className="w-4 h-4 mr-1" /> Prev
          </Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} data-testid="audit-next">
            Next <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DispatchAuditPage;
