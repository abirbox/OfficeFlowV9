import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/axios';
import { Bell } from 'lucide-react';
import { toast } from '@/components/ui/sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { formatDateTime } from '@/lib/datetime';

const NotificationBell = () => {
  const [notifs, setNotifs] = useState([]);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const fetchNotifs = async () => {
    try {
      const { data } = await api.get('/notifications');
      setNotifs(data);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => {
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 30000);
    return () => clearInterval(interval);
  }, []);

  // Real-time dispatch events over WebSocket (falls back to polling above)
  useEffect(() => {
    let closedByUs = false;

    const connect = () => {
      try {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${proto}//${window.location.host}/api/ws/dispatch`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.title) {
              toast(msg.title, { description: msg.message });
            }
            fetchNotifs();
          } catch { /* ignore malformed */ }
        };

        ws.onclose = () => {
          if (!closedByUs) {
            reconnectRef.current = setTimeout(connect, 15000);
          }
        };
        ws.onerror = () => { try { ws.close(); } catch { /* noop */ } };
      } catch { /* WS unavailable — polling still active */ }
    };

    connect();
    return () => {
      closedByUs = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) { try { wsRef.current.close(); } catch { /* noop */ } }
    };
  }, []);

  const unread = notifs.filter((n) => !n.read).length;

  const handleMarkAllRead = async () => {
    await api.post('/notifications/read-all');
    fetchNotifs();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" data-testid="notifications-button" className="relative">
          <Bell className="w-5 h-5" />
          {unread > 0 && (
            <Badge className="absolute -top-1 -right-1 h-5 min-w-[20px] px-1 bg-red-500 text-white text-xs flex items-center justify-center">
              {unread > 9 ? '9+' : unread}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-y-auto">
        <DropdownMenuLabel className="flex items-center justify-between">
          Notifications
          {unread > 0 && (
            <button onClick={handleMarkAllRead} className="text-xs text-[#4F46E5] hover:underline">Mark all read</button>
          )}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notifs.length === 0 ? (
          <p className="text-center text-sm text-[#64748B] py-6">No notifications</p>
        ) : (
          notifs.slice(0, 10).map((n) => (
            <DropdownMenuItem key={n.id} className="flex-col items-start py-3">
              <div className="flex items-start gap-2 w-full">
                {!n.read && <div className="w-2 h-2 rounded-full bg-[#4F46E5] mt-1.5"></div>}
                <div className="flex-1">
                  <p className={`text-sm ${!n.read ? 'font-semibold' : ''} text-[#0F172A] dark:text-[#FAFAFA]`}>{n.title}</p>
                  <p className="text-xs text-[#64748B] mt-0.5">{n.message}</p>
                  <p className="text-xs text-[#94a3b8] mt-1">{formatDateTime(n.created_at)}</p>
                </div>
              </div>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default NotificationBell;
