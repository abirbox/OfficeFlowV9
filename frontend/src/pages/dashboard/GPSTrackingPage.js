import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MapPin, Play, Square, Navigation, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import { formatDate } from '@/lib/datetime';

const GPSTrackingPage = () => {
  const [activeSession, setActiveSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [history, setHistory] = useState([]);
  const watchIdRef = useRef(null);

  useEffect(() => {
    fetchActiveSession();
    fetchHistory();
    return () => {
      if (watchIdRef.current) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchActiveSession = async () => {
    try {
      const { data } = await api.get('/gps/active');
      if (data.active) {
        setActiveSession(data.session);
        startWatchingLocation(data.session.id);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const { data } = await api.get('/gps/history');
      setHistory(data);
    } catch (error) {
      console.error(error);
    }
  };

  const startWatchingLocation = (sessionId) => {
    if (!navigator.geolocation) return;
    watchIdRef.current = navigator.geolocation.watchPosition(
      async (position) => {
        try {
          await api.post(`/gps/${sessionId}/location`, {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          });
        } catch (error) {
          console.error('Failed to update location:', error);
        }
      },
      (error) => console.error('GPS error:', error),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );
  };

  const handleStart = () => {
    if (!navigator.geolocation) {
      toast.error('Geolocation is not supported by your browser');
      return;
    }
    setStarting(true);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { data } = await api.post('/gps/start', {
            initial_latitude: position.coords.latitude,
            initial_longitude: position.coords.longitude,
            notes: 'Started tracking via web',
          });
          setActiveSession(data);
          startWatchingLocation(data.id);
          toast.success('GPS tracking started!');
        } catch (error) {
          toast.error(error.response?.data?.detail || 'Failed to start tracking');
        } finally {
          setStarting(false);
        }
      },
      () => {
        toast.error('Please enable location permission');
        setStarting(false);
      }
    );
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      await api.post(`/gps/${activeSession.id}/stop`);
      if (watchIdRef.current) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      setActiveSession(null);
      fetchHistory();
      toast.success('GPS tracking stopped');
    } catch (error) {
      toast.error('Failed to stop tracking');
    } finally {
      setStopping(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div data-testid="gps-tracking-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
          GPS Tracking
        </h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
          Track work location and travel routes
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Card className="lg:col-span-2 border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Navigation className="w-5 h-5" />
              {activeSession ? 'Active Session' : 'Start Tracking'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!activeSession ? (
              <div className="text-center py-12">
                <MapPin className="w-16 h-16 text-[#64748B] dark:text-[#A1A1AA] mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">
                  Ready to track your work?
                </h3>
                <p className="text-[#64748B] dark:text-[#A1A1AA] mb-6">
                  Start GPS tracking to log your work location and route
                </p>
                <Button
                  onClick={handleStart}
                  disabled={starting}
                  data-testid="start-gps-button"
                  className="bg-[#4F46E5] hover:bg-[#4338CA]"
                >
                  <Play className="w-5 h-5 mr-2" />
                  {starting ? 'Starting...' : 'Start Tracking'}
                </Button>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                  <Badge className="bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400">
                    Tracking Active
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="p-6 bg-[#F8FAFC] dark:bg-[#27272A] rounded-xl">
                    <div className="flex items-center gap-2 text-[#64748B] dark:text-[#A1A1AA] mb-2">
                      <TrendingUp className="w-5 h-5" />
                      <span className="text-sm font-medium">Distance</span>
                    </div>
                    <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">
                      {activeSession.total_distance?.toFixed(2) || 0} km
                    </p>
                  </div>
                  <div className="p-6 bg-[#F8FAFC] dark:bg-[#27272A] rounded-xl">
                    <div className="flex items-center gap-2 text-[#64748B] dark:text-[#A1A1AA] mb-2">
                      <MapPin className="w-5 h-5" />
                      <span className="text-sm font-medium">Points</span>
                    </div>
                    <p className="text-3xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">
                      {activeSession.coordinates?.length || 0}
                    </p>
                  </div>
                </div>

                <Button
                  onClick={handleStop}
                  disabled={stopping}
                  data-testid="stop-gps-button"
                  variant="destructive"
                  className="w-full"
                >
                  <Square className="w-5 h-5 mr-2" />
                  {stopping ? 'Stopping...' : 'Stop Tracking'}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader>
            <CardTitle>Recent Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-center text-[#64748B] dark:text-[#A1A1AA] py-8">
                No previous sessions
              </p>
            ) : (
              <div className="space-y-3">
                {history.slice(0, 5).map((session) => (
                  <div key={session.id} className="p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]">
                        {formatDate(session.started_at)}
                      </span>
                      <Badge variant="secondary" className="text-xs">
                        {session.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-[#64748B] dark:text-[#A1A1AA]">
                      {session.total_distance?.toFixed(2) || 0} km • {session.coordinates?.length || 0} points
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default GPSTrackingPage;
