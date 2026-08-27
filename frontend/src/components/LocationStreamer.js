import { useEffect, useRef } from 'react';
import { api } from '@/lib/axios';
import useAuthStore from '@/stores/authStore';

/**
 * Silent, always-mounted GPS streamer.
 * When the user has an active gps_session on the backend, this component
 * starts navigator.geolocation.watchPosition and pushes updates every ~30s.
 * Ensures the Live Map shows a marker for any active employee even if they
 * left the Attendance page.
 */
const LocationStreamer = () => {
  const { user } = useAuthStore();
  const watchIdRef = useRef(null);
  const sessionIdRef = useRef(null);
  const lastSentRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const stop = () => {
      if (watchIdRef.current != null && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
      watchIdRef.current = null;
      sessionIdRef.current = null;
    };

    const start = async () => {
      if (!user || cancelled) return;
      if (!navigator.geolocation) return;
      try {
        const { data } = await api.get('/gps/active');
        if (!data.active) {
          stop();
          return;
        }
        if (sessionIdRef.current === data.session.id) return; // already streaming
        stop();
        sessionIdRef.current = data.session.id;
        watchIdRef.current = navigator.geolocation.watchPosition(
          async (position) => {
            const now = Date.now();
            // Throttle to 1 push per 20 seconds to avoid spam
            if (now - lastSentRef.current < 20000) return;
            lastSentRef.current = now;
            try {
              await api.post(`/gps/${sessionIdRef.current}/location`, {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                accuracy: position.coords.accuracy,
              });
            } catch {
              // silent
            }
          },
          () => {},
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }
        );
      } catch {
        // silent
      }
    };

    start();
    const iv = setInterval(start, 45000); // re-check for new sessions
    return () => { cancelled = true; clearInterval(iv); stop(); };
  }, [user]);

  return null;
};

export default LocationStreamer;
