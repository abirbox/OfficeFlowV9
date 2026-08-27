import { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { motion } from 'framer-motion';
import { api } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MapPin, RefreshCw, Users, Radio, Search, Crosshair, Building2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { formatTime } from '@/lib/datetime';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const createEmployeeIcon = (status, highlighted) => {
  const color = status === 'working' ? '#22c55e' : status === 'checked_out' ? '#94a3b8' : '#f97316';
  const size = highlighted ? 32 : 24;
  const ring = highlighted ? '4px solid #4F46E5' : '3px solid white';
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="background:${color};width:${size}px;height:${size}px;border-radius:50%;border:${ring};box-shadow:0 2px 12px rgba(0,0,0,0.35);"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

const createOfficeIcon = () => L.divIcon({
  className: 'office-marker',
  html: `<div style="background:#4F46E5;width:30px;height:30px;border-radius:8px;border:3px solid white;box-shadow:0 4px 14px rgba(79,70,229,0.5);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;font-size:16px;">⌂</div>`,
  iconSize: [30, 30],
  iconAnchor: [15, 15],
});

// Helper component to imperatively fly the map to a location
const MapFlyer = ({ target }) => {
  const map = useMap();
  useEffect(() => {
    if (target && Number.isFinite(target.lat) && Number.isFinite(target.lng)) {
      map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), 15), { duration: 1.2 });
    }
  }, [target, map]);
  return null;
};

const LiveMapPage = () => {
  const [employees, setEmployees] = useState([]);
  const [offices, setOffices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEmp, setSelectedEmp] = useState(null);
  const [query, setQuery] = useState('');
  const [flyTarget, setFlyTarget] = useState(null);
  const markerRefs = useRef({});

  const fetchStatus = async () => {
    try {
      const [statusRes, officeRes] = await Promise.all([
        api.get('/admin/employee-status'),
        api.get('/office-locations').catch(() => ({ data: [] })),
      ]);
      setEmployees(statusRes.data);
      setOffices(Array.isArray(officeRes.data) ? officeRes.data : []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const employeesWithLocation = useMemo(() => employees.filter((e) => e.current_location), [employees]);
  const workingEmployees = employees.filter((e) => e.status === 'working');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return employees;
    return employees.filter((e) =>
      (e.name || '').toLowerCase().includes(q) ||
      (e.email || '').toLowerCase().includes(q) ||
      (e.role || '').toLowerCase().includes(q)
    );
  }, [employees, query]);

  const defaultCenter = offices.length > 0
    ? [offices[0].latitude, offices[0].longitude]
    : employeesWithLocation.length > 0
      ? [employeesWithLocation[0].current_location.latitude, employeesWithLocation[0].current_location.longitude]
      : [23.8103, 90.4125]; // Dhaka, Bangladesh default

  const focusEmployee = (emp) => {
    setSelectedEmp(emp);
    if (emp?.current_location) {
      setFlyTarget({ lat: emp.current_location.latitude, lng: emp.current_location.longitude, ts: Date.now() });
      // Open the marker popup after fly
      setTimeout(() => {
        const m = markerRefs.current[emp.id];
        if (m && m.openPopup) m.openPopup();
      }, 900);
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
    <div data-testid="live-map-page">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className="text-4xl font-bold text-[#0F172A] dark:text-[#FAFAFA] tracking-tight mb-2">
            Live Location Map
          </h1>
          <p className="text-[#64748B] dark:text-[#A1A1AA] text-lg flex items-center gap-2">
            <Radio className="w-4 h-4 text-green-500 animate-pulse" />
            Auto-refreshing every 15s · {workingEmployees.length} working · {employeesWithLocation.length} on map · {offices.length} office{offices.length === 1 ? '' : 's'}
          </p>
        </div>
        <Button onClick={fetchStatus} variant="outline" data-testid="refresh-map-button">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3 border-[#E2E8F0] dark:border-[#27272A] overflow-hidden">
          <CardContent className="p-0">
            <div style={{ height: '600px', width: '100%' }} data-testid="leaflet-map-container">
              <MapContainer center={defaultCenter} zoom={12} style={{ height: '100%', width: '100%' }}>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <MapFlyer target={flyTarget} />
                {offices.flatMap((o) => [
                  <Marker
                    key={`office-${o.id}`}
                    position={[o.latitude, o.longitude]}
                    icon={createOfficeIcon()}
                  >
                    <Popup>
                      <div className="p-1">
                        <p className="font-semibold flex items-center gap-1">
                          <Building2 className="w-4 h-4" /> {o.name}
                        </p>
                        {o.address && <p className="text-xs text-gray-600">{o.address}</p>}
                        <p className="text-xs mt-1">Geofence: {o.radius_meters}m</p>
                      </div>
                    </Popup>
                  </Marker>,
                  <Circle
                    key={`office-circle-${o.id}`}
                    center={[o.latitude, o.longitude]}
                    radius={o.radius_meters}
                    pathOptions={{ color: '#4F46E5', fillColor: '#4F46E5', fillOpacity: 0.08, weight: 1.5, dashArray: '4 4' }}
                  />,
                ])}
                {employeesWithLocation.map((emp) => (
                  <Marker
                    key={emp.id}
                    ref={(el) => { if (el) markerRefs.current[emp.id] = el; }}
                    position={[emp.current_location.latitude, emp.current_location.longitude]}
                    icon={createEmployeeIcon(emp.status, selectedEmp?.id === emp.id)}
                    eventHandlers={{ click: () => setSelectedEmp(emp) }}
                  >
                    <Popup>
                      <div className="p-1">
                        <p className="font-semibold">{emp.name}</p>
                        <p className="text-xs text-gray-600">{emp.email}</p>
                        <p className="text-xs mt-1">Status: <span className="font-medium capitalize">{emp.status.replace('_', ' ')}</span></p>
                        {emp.check_in && <p className="text-xs">Started: {formatTime(emp.check_in)}</p>}
                      </div>
                    </Popup>
                  </Marker>
                ))}
                {selectedEmp && selectedEmp.coordinates_today && selectedEmp.coordinates_today.length > 1 && (
                  <Polyline
                    positions={selectedEmp.coordinates_today.map((c) => [c.latitude, c.longitude])}
                    color="#4F46E5"
                    weight={3}
                    opacity={0.7}
                  />
                )}
              </MapContainer>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#E2E8F0] dark:border-[#27272A]">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Users className="w-5 h-5" />
              Live Status
            </CardTitle>
            <div className="relative mt-2">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search & zoom to employee…"
                className="pl-9 h-9"
                data-testid="livemap-search-input"
              />
            </div>
          </CardHeader>
          <CardContent className="p-3">
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {filtered.length === 0 ? (
                <p className="text-sm text-[#64748B] p-4 text-center">
                  {employees.length === 0 ? 'No employees yet' : 'No matches — try another search'}
                </p>
              ) : (
                filtered.map((emp) => (
                  <motion.div
                    key={emp.id}
                    onClick={() => focusEmployee(emp)}
                    whileHover={{ scale: 1.02 }}
                    className={`p-3 rounded-lg cursor-pointer border ${
                      selectedEmp?.id === emp.id
                        ? 'bg-[#4F46E5]/10 border-[#4F46E5]'
                        : 'bg-[#F8FAFC] dark:bg-[#27272A] border-transparent'
                    }`}
                    data-testid={`employee-status-${emp.id}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Avatar className="w-8 h-8">
                        <AvatarImage src={emp.avatar_path} />
                        <AvatarFallback className="text-xs bg-[#4F46E5] text-white">
                          {emp.name.charAt(0).toUpperCase()}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate text-[#0F172A] dark:text-[#FAFAFA]">{emp.name}</p>
                        <p className="text-xs text-[#64748B] truncate">{emp.role}</p>
                      </div>
                      <Badge
                        className={`text-xs ${
                          emp.status === 'working'
                            ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                            : emp.status === 'checked_out'
                            ? 'bg-gray-100 dark:bg-gray-900/20 text-gray-700 dark:text-gray-400'
                            : 'bg-orange-100 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400'
                        }`}
                      >
                        {emp.status === 'working' ? 'Working' : emp.status === 'checked_out' ? 'Done' : 'Idle'}
                      </Badge>
                    </div>
                    {emp.current_location ? (
                      <p className="text-xs text-[#4F46E5] flex items-center gap-1 mt-1 font-medium">
                        <Crosshair className="w-3 h-3" />
                        {emp.current_location.latitude.toFixed(4)}, {emp.current_location.longitude.toFixed(4)}
                      </p>
                    ) : (
                      <p className="text-xs text-[#64748B] flex items-center gap-1 mt-1">
                        <MapPin className="w-3 h-3" />
                        {emp.gps_active ? 'GPS starting…' : 'No location yet'}
                      </p>
                    )}
                    {emp.total_hours > 0 && (
                      <p className="text-xs text-[#64748B] mt-1">{emp.total_hours.toFixed(2)} hrs today</p>
                    )}
                  </motion.div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LiveMapPage;
