import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import { Clock, Check, X, TrendingUp, Filter } from 'lucide-react';

const OvertimePage = () => {
  const { user } = useAuthStore();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [busy, setBusy] = useState(null);
  const [notes, setNotes] = useState({});
  const isManager = user && ['super_admin', 'admin', 'hr', 'manager'].includes(user.role);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter === 'all' ? {} : { status: filter };
      const { data } = await api.get('/overtime', { params });
      setItems(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const act = async (id, action) => {
    setBusy(id + action);
    try {
      await api.post(`/overtime/${id}/${action}`, { note: notes[id] || null });
      toast.success(action === 'approve' ? 'Overtime approved' : 'Overtime rejected');
      fetchItems();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setBusy(null);
    }
  };

  const statusBadge = (s) => {
    const map = {
      pending: 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400',
      approved: 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400',
      rejected: 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400',
    };
    return <Badge className={map[s] || 'bg-gray-100 text-gray-700'} data-testid={`ot-status-${s}`}>{s}</Badge>;
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>;

  return (
    <div data-testid="overtime-page">
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2 flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-[#4F46E5]" />
            Overtime {isManager ? 'Approvals' : 'Requests'}
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
            {isManager
              ? 'Check-outs over 8 hours are automatically flagged for payroll approval'
              : 'Your flagged overtime days awaiting manager approval'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[#64748B]" />
          {['pending', 'approved', 'rejected', 'all'].map((s) => (
            <Button
              key={s}
              size="sm"
              variant={filter === s ? 'default' : 'outline'}
              onClick={() => setFilter(s)}
              className={filter === s ? 'bg-[#4F46E5] hover:bg-[#4338CA]' : ''}
              data-testid={`ot-filter-${s}`}
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {items.length === 0 ? (
        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardContent className="p-12 text-center">
            <Clock className="w-16 h-16 text-[#64748B] mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">
              No {filter === 'all' ? '' : filter} overtime requests
            </h3>
            <p className="text-[#64748B] dark:text-[#A1A1AA]">
              {isManager ? 'When employees work past 8 hours, requests will show here.' : 'You haven\'t worked overtime yet.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((r, i) => (
            <motion.div key={r.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}>
              <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid={`ot-row-${r.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between flex-wrap gap-3">
                    <div>
                      <CardTitle className="text-lg flex items-center gap-2">
                        {isManager ? r.user_name : (r.shift_title || 'Overtime')} · {r.date}
                        {statusBadge(r.status)}
                      </CardTitle>
                      {isManager && r.user_email && (
                        <p className="text-sm text-[#64748B] mt-1">{r.user_email}</p>
                      )}
                    </div>
                    <div className="text-right">
                      <p className="text-2xl font-bold text-[#4F46E5]">+{r.overtime_hours}h</p>
                      <p className="text-xs text-[#64748B]">on top of 8h baseline</p>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-4 text-sm">
                    <div><span className="text-[#64748B]">Total worked: </span><span className="font-medium">{r.total_hours}h</span></div>
                    {r.shift_title && <div><span className="text-[#64748B]">Shift: </span><span className="font-medium">{r.shift_title}</span></div>}
                    {r.reviewer_name && (
                      <div><span className="text-[#64748B]">Reviewed by: </span><span className="font-medium">{r.reviewer_name}</span></div>
                    )}
                  </div>
                  {r.review_note && (
                    <div className="text-sm bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg p-3">
                      <span className="text-[#64748B]">Note: </span>{r.review_note}
                    </div>
                  )}
                  {isManager && r.status === 'pending' && (
                    <div className="pt-2 space-y-2 border-t border-[#E2E8F0] dark:border-[#27272A]">
                      <Textarea
                        value={notes[r.id] || ''}
                        onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                        placeholder="Optional note (visible to employee)"
                        className="min-h-[60px]"
                        data-testid={`ot-note-${r.id}`}
                      />
                      <div className="flex gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => act(r.id, 'reject')}
                          disabled={busy === r.id + 'reject'}
                          data-testid={`ot-reject-${r.id}`}
                        >
                          <X className="w-4 h-4 mr-1" /> Reject
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => act(r.id, 'approve')}
                          disabled={busy === r.id + 'approve'}
                          className="bg-green-600 hover:bg-green-700"
                          data-testid={`ot-approve-${r.id}`}
                        >
                          <Check className="w-4 h-4 mr-1" /> Approve
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

export default OvertimePage;
