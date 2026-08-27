import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { api } from '@/lib/axios';

const PresenceContext = createContext({ onlineIds: new Set(), isOnline: () => false });

const POLL_MS = 20000;

export const PresenceProvider = ({ children }) => {
  const [onlineIds, setOnlineIds] = useState(new Set());
  const timerRef = useRef(null);

  const tick = useCallback(async () => {
    try {
      await api.post('/presence/heartbeat');
      const { data } = await api.get('/presence/online');
      setOnlineIds(new Set(data.online || []));
    } catch {
      // not authenticated yet or network hiccup — keep previous state
    }
  }, []);

  useEffect(() => {
    tick();
    timerRef.current = setInterval(tick, POLL_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') tick(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timerRef.current);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [tick]);

  const isOnline = useCallback((id) => onlineIds.has(String(id)), [onlineIds]);

  return (
    <PresenceContext.Provider value={{ onlineIds, isOnline }}>
      {children}
    </PresenceContext.Provider>
  );
};

export const usePresence = () => useContext(PresenceContext);
