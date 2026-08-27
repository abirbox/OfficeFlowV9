import { useEffect, useRef, useState, useCallback } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { Send, MessageCircle } from 'lucide-react';
import { formatDateTime } from '@/lib/datetime';

const formatTime = (iso) => formatDateTime(iso);

const roleBadge = (role) => {
  if (!role) return null;
  const isAdmin = ['super_admin', 'admin', 'hr', 'manager'].includes(role);
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded ${isAdmin ? 'bg-[#4F46E5]/10 text-[#4F46E5]' : 'bg-[#64748B]/10 text-[#64748B]'}`}>
      {role}
    </span>
  );
};

const ShiftCommentsDialog = ({ open, onOpenChange, shift, currentUserId }) => {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const load = useCallback(async () => {
    if (!shift?.id) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/shifts/${shift.id}/comments`);
      setComments(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  }, [shift?.id]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [comments.length]);

  const send = async () => {
    const text = body.trim();
    if (!text) return;
    setSending(true);
    try {
      const { data } = await api.post(`/shifts/${shift.id}/comments`, { body: text });
      setComments((c) => [...c, data]);
      setBody('');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="shift-comments-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageCircle className="w-5 h-5" /> {shift?.title || 'Shift'} · Discussion
          </DialogTitle>
          <DialogDescription>
            {shift?.user_name ? `Chat between admin and ${shift.user_name}` : 'Chat thread'}
          </DialogDescription>
        </DialogHeader>

        <div ref={scrollRef} className="h-80 overflow-y-auto pr-2 space-y-3 border-t border-b border-[#E2E8F0] dark:border-[#27272A] py-3" data-testid="shift-comments-list">
          {loading ? (
            <div className="flex items-center justify-center h-full text-sm text-[#64748B]">Loading…</div>
          ) : comments.length === 0 ? (
            <div className="flex items-center justify-center h-full text-sm text-[#64748B]">No messages yet. Say hi!</div>
          ) : (
            comments.map((c) => {
              const mine = c.author_id === currentUserId;
              return (
                <div key={c.id} className={`flex gap-2 ${mine ? 'flex-row-reverse' : ''}`} data-testid={`shift-comment-${c.id}`}>
                  <Avatar className="w-8 h-8 flex-shrink-0">
                    <AvatarImage src={c.author_avatar} />
                    <AvatarFallback className="bg-[#4F46E5] text-white text-xs">
                      {(c.author_name || 'U').charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className={`max-w-[75%] ${mine ? 'items-end' : ''}`}>
                    <div className={`flex items-center gap-2 mb-1 ${mine ? 'justify-end' : ''}`}>
                      <span className="text-xs font-medium text-[#0F172A] dark:text-[#FAFAFA]">
                        {mine ? 'You' : c.author_name}
                      </span>
                      {roleBadge(c.author_role)}
                    </div>
                    <div className={`rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
                      mine
                        ? 'bg-[#4F46E5] text-white rounded-tr-sm'
                        : 'bg-[#F1F5F9] dark:bg-[#27272A] text-[#0F172A] dark:text-[#FAFAFA] rounded-tl-sm'
                    }`}>
                      {c.body}
                    </div>
                    <p className="text-[10px] text-[#64748B] mt-1">{formatTime(c.created_at)}</p>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="flex gap-2 items-end">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Type a message…"
            className="min-h-[60px] resize-none"
            data-testid="shift-comment-input"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                send();
              }
            }}
          />
          <Button
            onClick={send}
            disabled={sending || !body.trim()}
            className="bg-[#4F46E5] hover:bg-[#4338CA] h-[60px] px-4"
            data-testid="shift-comment-send"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ShiftCommentsDialog;
