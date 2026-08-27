import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckSquare, Clock, LogIn, LogOut, Calendar, MapPin, Radio, Building2, Play } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/sonner';
import useAuthStore from '@/stores/authStore';
import { formatTime } from '@/lib/datetime';

const AttendancePage = () => {
  const { user } = useAuthStore();
  const [todayAttendance, setTodayAttendance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkingIn, setCheckingIn] = useState(false);
  const [checkingOut, setCheckingOut] = useState(false);
  const [activeGPS, setActiveGPS] = useState(null);
  const [nearest, setNearest] = useState(null);
  const watchIdRef = useRef(null);
  const currentPositionRef = useRef(null);

  const fetchTodayAttendance = useCallback(async () => {
    try {
      const { data } = await api.get('/attendance/today');
      setTodayAttendance(data.attendance);
      if (data.attendance?.is_working) startGPSStreaming();
    } catch (error) {
      toast.error('Failed to load attendance');
    } finally { setLoading(false); }
  }, []);

  const checkActiveGPS = useCallback(async () => {
    try {
      const { data } = await api.get('/gps/active');
      if (data.active) setActiveGPS(data.session);
    } catch (e) { console.error(e); }
  }, []);

  const computeNearest = useCallback(async (lat, lng) => {
    try {
      const { data } = await api.get(`/office-locations/nearest?lat=${lat}&lng=${lng}`);
      if (data.office) setNearest(data);
    } catch (e) {
      // Endpoint returns 400 when no offices are configured — non-fatal.
      console.warn('AttendancePage: nearest-office lookup failed', e?.response?.status);
    }
  }, []);

  useEffect(() => {
    fetchTodayAttendance();
    checkActiveGPS();
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition((p) => {
        currentPositionRef.current = { lat: p.coords.latitude, lng: p.coords.longitude };
        computeNearest(p.coords.latitude, p.coords.longitude);
      }, () => {});
    }
    return () => {
      if (watchIdRef.current) navigator.geolocation.clearWatch(watchIdRef.current);
    };
  }, [fetchTodayAttendance, checkActiveGPS, computeNearest]);

  const startGPSStreaming = async () => {
    if (!navigator.geolocation) return;
    try {
      const { data } = await api.get('/gps/active');
      if (!data.active) return;
      const sessionId = data.session.id;
      setActiveGPS(data.session);
      if (watchIdRef.current) navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = navigator.geolocation.watchPosition(
        async (position) => {
          try {
            await api.post(`/gps/${sessionId}/location`, {
              latitude: position.coords.latitude,
              longitude: position.coords.longitude,
              accuracy: position.coords.accuracy,
            });
          } catch {}
        },
        () => {},
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
      );
    } catch {}
  };

  const handleCheckIn = () => {
    if (!navigator.geolocation) { toast.error('Location required to check in'); return; }
    setCheckingIn(true);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { data } = await api.post('/attendance/check-in', {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            notes: todayAttendance ? 'Resumed work' : 'Started work',
          });
          setTodayAttendance(data);
          computeNearest(position.coords.latitude, position.coords.longitude);
          toast.success(todayAttendance ? 'Work resumed. GPS tracking active.' : 'Checked in! GPS tracking started.');
          setTimeout(startGPSStreaming, 500);
        } catch (error) {
          toast.error(error.response?.data?.detail || 'Failed to check in');
        } finally { setCheckingIn(false); }
      },
      () => { toast.error('Location permission is required'); setCheckingIn(false); },
      { enableHighAccuracy: true }
    );
  };

  const handleCheckOut = () => {
    setCheckingOut(true);
    const stopWatch = () => {
      if (watchIdRef.current) { navigator.geolocation.clearWatch(watchIdRef.current); watchIdRef.current = null; }
      setActiveGPS(null);
    };
    const doCheckout = async (lat, lng) => {
      try {
        const body = { notes: 'Ended work' };
        if (lat && lng) { body.latitude = lat; body.longitude = lng; }
        const { data } = await api.post('/attendance/check-out', body);
        setTodayAttendance(data);
        stopWatch();
        toast.success('Checked out. Total today: ' + (data.total_hours || 0).toFixed(2) + ' hrs. You can start again anytime.');
      } catch (error) {
        toast.error(error.response?.data?.detail || 'Failed to check out');
      } finally { setCheckingOut(false); }
    };
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (p) => doCheckout(p.coords.latitude, p.coords.longitude),
        () => doCheckout(null, null)
      );
    } else { doCheckout(null, null); }
  };

  if (loading) {
    return (<div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[#4F46E5] border-t-transparent rounded-full animate-spin"></div></div>);
  }

  const isWorking = todayAttendance?.is_working;
  const sessions = todayAttendance?.sessions || [];

  return (
    <div data-testid="attendance-page">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">My Attendance</h1>
        <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg">
          Track your work hours — you can stop and restart work throughout the day; totals accumulate.
        </p>
      </div>

      {nearest?.office && (
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className={`mb-6 p-4 rounded-lg border flex items-start gap-3 ${nearest.within_geofence ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-[#F8FAFC] dark:bg-[#27272A] border-[#E2E8F0] dark:border-[#27272A]'}`}
          data-testid="nearest-office-banner"
        >
          <Building2 className={`w-5 h-5 mt-0.5 ${nearest.within_geofence ? 'text-green-600 dark:text-green-400' : 'text-[#64748B]'}`} />
          <div>
            <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">
              {nearest.within_geofence ? `At office: ${nearest.office.name}` : `${(nearest.distance_meters/1000).toFixed(2)} km from ${nearest.office.name}`}
            </p>
            <p className="text-sm text-[#64748B]">
              {nearest.within_geofence ? 'You are inside the office geofence.' : `Nearest office · geofence ${nearest.office.radius_meters}m`}
            </p>
          </div>
        </motion.div>
      )}

      {isWorking && (
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-3"
          data-testid="gps-tracking-active-banner"
        >
          <div className="relative">
            <Radio className="w-5 h-5 text-green-600 dark:text-green-400" />
            <div className="absolute inset-0 rounded-full bg-green-500/30 animate-ping"></div>
          </div>
          <div>
            <p className="font-medium text-green-900 dark:text-green-100">GPS Tracking Active</p>
            <p className="text-sm text-green-700 dark:text-green-300">
              Your location is being shared. {activeGPS && `${activeGPS.coordinates?.length || 0} points recorded`}
            </p>
          </div>
        </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <Card className="lg:col-span-2 border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Calendar className="w-5 h-5" />Today's Attendance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-[#F8FAFC] dark:bg-[#27272A] rounded-xl">
                <div className="flex items-center gap-2 text-[#64748B] mb-1"><LogIn className="w-4 h-4" /><span className="text-xs font-medium">First In</span></div>
                <p className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{sessions[0] ? formatTime(sessions[0].check_in) : '-'}</p>
              </div>
              <div className="p-4 bg-[#F8FAFC] dark:bg-[#27272A] rounded-xl">
                <div className="flex items-center gap-2 text-[#64748B] mb-1"><LogOut className="w-4 h-4" /><span className="text-xs font-medium">Last Out</span></div>
                <p className="text-xl font-bold text-[#0F172A] dark:text-[#FAFAFA]">{sessions.length && sessions[sessions.length-1].check_out ? formatTime(sessions[sessions.length-1].check_out) : '-'}</p>
              </div>
              <div className="p-4 bg-[#4F46E5]/5 rounded-xl">
                <div className="flex items-center gap-2 text-[#4F46E5] mb-1"><Clock className="w-4 h-4" /><span className="text-xs font-medium">Total Today</span></div>
                <p className="text-xl font-bold text-[#4F46E5]" data-testid="total-hours-today">{(todayAttendance?.total_hours || 0).toFixed(2)} hrs</p>
              </div>
            </div>

            {!isWorking ? (
              <div className="text-center py-6">
                <CheckSquare className="w-12 h-12 text-[#64748B] mx-auto mb-3" />
                <p className="text-[#64748B] mb-4">
                  {todayAttendance ? 'You checked out. Start again anytime — today\'s hours will keep adding up.' : 'Start your workday and we\'ll track your hours and location.'}
                </p>
                <Button onClick={handleCheckIn} disabled={checkingIn} data-testid="check-in-button" className="bg-[#4F46E5] hover:bg-[#4338CA]">
                  <Play className="w-5 h-5 mr-2" /> {checkingIn ? 'Starting…' : (todayAttendance ? 'Start Work Again' : 'Start Work / Check In')}
                </Button>
              </div>
            ) : (
              <Button onClick={handleCheckOut} disabled={checkingOut} data-testid="check-out-button" variant="destructive" className="w-full">
                <LogOut className="w-5 h-5 mr-2" /> {checkingOut ? 'Ending…' : 'Stop Work / Check Out'}
              </Button>
            )}

            {sessions.length > 0 && (
              <div className="mt-6">
                <p className="text-sm font-semibold text-[#0F172A] dark:text-[#FAFAFA] mb-2">Today's Sessions</p>
                <div className="space-y-2" data-testid="attendance-sessions-list">
                  {sessions.map((s, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-[#F8FAFC] dark:bg-[#27272A] text-sm">
                      <div className="flex items-center gap-3">
                        <Badge className="bg-[#4F46E5]/10 text-[#4F46E5]">#{idx + 1}</Badge>
                        <span className="text-[#0F172A] dark:text-[#FAFAFA]">{formatTime(s.check_in)} → {s.check_out ? formatTime(s.check_out) : <span className="text-green-600 font-medium">ongoing</span>}</span>
                      </div>
                      <span className="font-medium text-[#0F172A] dark:text-[#FAFAFA]">{(s.hours || 0).toFixed(2)} hrs</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader><CardTitle>Quick Facts</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg">
              <span className="text-sm text-[#64748B]">Sessions today</span>
              <span className="text-lg font-bold text-[#4F46E5]">{sessions.length}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg">
              <span className="text-sm text-[#64748B]">Status</span>
              <Badge className={isWorking ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}>{isWorking ? 'Working' : (todayAttendance ? 'On Break' : 'Not Started')}</Badge>
            </div>
            {nearest?.office && (
              <div className="flex items-center justify-between p-3 bg-[#F8FAFC] dark:bg-[#27272A] rounded-lg">
                <span className="text-sm text-[#64748B]">From office</span>
                <span className="font-medium">{nearest.distance_meters < 1000 ? `${Math.round(nearest.distance_meters)} m` : `${(nearest.distance_meters/1000).toFixed(2)} km`}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AttendancePage;
