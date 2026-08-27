import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { Plus, Pencil, Trash2, Search, Image as ImageIcon } from 'lucide-react';
import useAuthStore from '@/stores/authStore';
import { hasPermission } from '@/lib/permissions';
import { STATUS_BADGE } from './_shared';

/**
 * Generic entity CRUD table used by Clients, Vendors, Officers, Post Sites.
 *   props.title, props.endpoint (e.g. '/dispatch/clients'), props.permBase (e.g. 'dispatch.clients')
 *   props.fields — [{key,label,type?,options?,required?,select?:'clients'|'vendors'}]
 *   props.columns — [{key,label}]
 *   props.statuses — [{value,label}]  optional; default active/inactive
 */
const EntityCrudPage = ({ title, endpoint, permBase, fields, columns, statuses, filters = [] }) => {
  const { user } = useAuthStore();
  const canCreate = hasPermission(user, `${permBase}.create`);
  const canEdit = hasPermission(user, `${permBase}.edit`);
  const canDelete = hasPermission(user, `${permBase}.delete`);

  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [filterValues, setFilterValues] = useState({});
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});
  const [clients, setClients] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [uploading, setUploading] = useState(false);

  const uploadLogo = async (key, file) => {
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const { data } = await api.post('/dispatch/upload-logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setForm((prev) => ({ ...prev, [key]: data.url }));
      toast.success('Logo uploaded');
    } catch (e) {
      toast.error('Failed to upload logo');
    } finally { setUploading(false); }
  };

  const load = async () => {
    setLoading(true);
    try {
      const params = { search, ...filterValues };
      Object.keys(params).forEach((key) => {
        if (params[key] === '' || params[key] == null) delete params[key];
      });

      const { data } = await api.get(endpoint, { params });
      setRows(Array.isArray(data) ? data : (data.items || []));
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); }
  };
  useEffect(() => {
    load();
    if (fields.some((f) => f.select === 'clients')) api.get('/dispatch/clients').then(r => setClients(r.data));
    if (fields.some((f) => f.select === 'vendors')) api.get('/dispatch/vendors').then(r => setVendors(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, JSON.stringify(filterValues)]);

  const openCreate = () => { setEditing(null); setForm({ status: 'active', type: 'Unarmed' }); setDialogOpen(true); };
  const openEdit = (row) => { setEditing(row); setForm({ ...row }); setDialogOpen(true); };

  const submit = async () => {
    try {
      if (editing) await api.put(`${endpoint}/${editing.id}`, form);
      else await api.post(endpoint, form);
      toast.success(`${title.slice(0, -1)} ${editing ? 'updated' : 'created'}`);
      setDialogOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const remove = async (row) => {
    if (!window.confirm(`Permanently delete "${row.name || row.post_pin}"? This cannot be undone.`)) return;
    try { await api.delete(`${endpoint}/${row.id}`); toast.success('Deleted'); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const renderField = (f) => {
    if (f.type === 'logo')
      return (
        <div className="flex items-center gap-3">
          {form[f.key] ? (
            <img src={form[f.key]} alt="logo" className="w-12 h-12 rounded-lg object-contain border border-[#E2E8F0] dark:border-[#27272A] bg-white" data-testid={`logo-preview-${f.key}`} />
          ) : (
            <div className="w-12 h-12 rounded-lg border border-dashed border-[#CBD5E1] dark:border-[#3F3F46] flex items-center justify-center">
              <ImageIcon className="w-5 h-5 text-[#94A3B8]" />
            </div>
          )}
          <label className="cursor-pointer">
            <input type="file" accept="image/*" className="hidden" data-testid={`field-${f.key}`}
              onChange={(e) => uploadLogo(f.key, e.target.files?.[0])} />
            <span className={`inline-flex items-center px-3 py-2 rounded-lg text-sm border border-[#E2E8F0] dark:border-[#27272A] ${uploading ? 'opacity-60' : 'hover:bg-[#F8FAFC] dark:hover:bg-[#27272A]'}`}>
              {uploading ? 'Uploading…' : (form[f.key] ? 'Replace Logo' : 'Upload Logo')}
            </span>
          </label>
          {form[f.key] && (
            <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setForm({ ...form, [f.key]: null })}>Remove</Button>
          )}
        </div>
      );
    if (f.select === 'clients')
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue placeholder="Select client" /></SelectTrigger>
          <SelectContent>{clients.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.select === 'vendors')
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue placeholder="Select vendor" /></SelectTrigger>
          <SelectContent>{vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.options)
      return (
        <Select value={form[f.key] || ''} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
          <SelectTrigger data-testid={`field-${f.key}`}><SelectValue /></SelectTrigger>
          <SelectContent>{f.options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
        </Select>
      );
    if (f.type === 'color') {
      const val = form[f.key] || '#D4A017';
      return (
        <div className="flex items-center gap-2">
          <Input type="color" value={val}
            onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            className="w-16 h-10 p-1 cursor-pointer" data-testid={`field-${f.key}`} />
          <Input type="text" value={form[f.key] || ''} placeholder="#D4A017 (default gold)"
            onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
            className="w-32 font-mono uppercase" data-testid={`field-${f.key}-hex`} />
          {form[f.key] && (
            <Button size="sm" variant="ghost" className="text-xs" onClick={() => setForm({ ...form, [f.key]: '' })} data-testid={`field-${f.key}-reset`}>Reset</Button>
          )}
        </div>
      );
    }
    if (f.type === 'textarea')
      return <Textarea value={form[f.key] || ''} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} data-testid={`field-${f.key}`} />;
    return (
      <Input
        type={f.type || 'text'}
        value={form[f.key] ?? ''}
        readOnly={f.readOnly}
        disabled={f.disabled}
        placeholder={f.readOnly ? 'Automatically generated' : undefined}
        onChange={(e) => setForm({
          ...form,
          [f.key]: f.type === 'number' ? Number(e.target.value) : e.target.value
        })}
        className={f.readOnly ? 'bg-[#F8FAFC] dark:bg-[#27272A] cursor-not-allowed' : ''}
        data-testid={`field-${f.key}`}
      />
    );
  };

  return (
    <div className="space-y-6" data-testid={`page-${permBase}`}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{title}</h1>
        {canCreate && (
          <Button onClick={openCreate} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="create-btn">
            <Plus className="w-4 h-4 mr-2" /> Add {title.slice(0, -1)}
          </Button>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
          <Input
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
            data-testid="search-input"
          />
        </div>

        {filters.map((filter) => (
          <Select
            key={filter.key}
            value={filterValues[filter.key] || 'all'}
            onValueChange={(value) =>
              setFilterValues((prev) => ({
                ...prev,
                [filter.key]: value === 'all' ? '' : value
              }))
            }
          >
            <SelectTrigger className="w-[190px]" data-testid={`filter-${filter.key}`}>
              <SelectValue placeholder={filter.label} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All {filter.label}</SelectItem>

              {filter.type === 'clients'
                ? clients.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))
                : filter.options?.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
            </SelectContent>
          </Select>
        ))}

        {filters.length > 0 && Object.values(filterValues).some(Boolean) && (
          <Button
            variant="outline"
            onClick={() => setFilterValues({})}
            data-testid="clear-filters"
          >
            Clear Filters
          </Button>
        )}
      </div>

      <div className="bg-white dark:bg-[#18181B] border border-[#E2E8F0] dark:border-[#27272A] rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#F8FAFC] dark:bg-[#0F0F11] text-left text-xs uppercase tracking-wider text-[#64748B]">
            <tr>
              {columns.map((c) => <th key={c.key} className="px-4 py-3">{c.label}</th>)}
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0] dark:divide-[#27272A]">
            {loading ? (
              <tr><td colSpan={columns.length + 2} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={columns.length + 2} className="px-4 py-8 text-center text-[#64748B]">No records found</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id} data-testid={`row-${r.id}`}>
                {columns.map((c) => (
                  <td key={c.key} className="px-4 py-3 text-[#334155] dark:text-[#E4E4E7]">
                    {c.type === 'logo'
                      ? (r[c.key]
                          ? <img src={r[c.key]} alt="logo" className="w-9 h-9 rounded object-contain border border-[#E2E8F0] dark:border-[#27272A] bg-white" data-testid={`row-logo-${r.id}`} />
                          : <span className="text-[#94A3B8]">—</span>)
                      : (r[c.key] ?? '—')}
                  </td>
                ))}
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGE[r.status] || STATUS_BADGE.inactive}`}>{r.status}</span>
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  {canEdit && <Button size="sm" variant="outline" onClick={() => openEdit(r)} data-testid={`edit-${r.id}`}><Pencil className="w-3 h-3" /></Button>}
                  {canDelete && <Button size="sm" variant="outline" onClick={() => remove(r)} data-testid={`delete-${r.id}`}><Trash2 className="w-3 h-3" /></Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editing ? 'Edit' : 'Add'} {title.slice(0, -1)}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {fields.map((f) => (
              <div key={f.key} className={(f.type === 'textarea' || f.type === 'logo') ? 'sm:col-span-2 space-y-1' : 'space-y-1'}>
                <Label>{f.label}{f.required && ' *'}</Label>
                {renderField(f)}
              </div>
            ))}
            {(statuses || [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]).length > 0 && (
              <div className="space-y-1">
                <Label>Status</Label>
                <Select value={form.status || 'active'} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger data-testid="field-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(statuses || [{ value: 'active', label: 'Active' }, { value: 'inactive', label: 'Inactive' }]).map((s) =>
                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={submit} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-entity">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EntityCrudPage;
