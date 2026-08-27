import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/sonner';
import { Building2, MapPin, Trash2, Crosshair, Plus, Search } from 'lucide-react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, DialogTrigger,
} from '@/components/ui/dialog';

const OfficeLocationsTab = () => {
  const [offices, setOffices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [geocoding, setGeocoding] = useState(false);
  const [form, setForm] = useState({ name: '', address: '', latitude: '', longitude: '', radius_meters: 100 });

  const load = async () => {
    try {
      const { data } = await api.get('/office-locations');
      setOffices(data);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const useCurrent = () => {
    if (!navigator.geolocation) return toast.error('Geolocation not supported');
    navigator.geolocation.getCurrentPosition(
      (p) => setForm((f) => ({ ...f, latitude: p.coords.latitude.toFixed(6), longitude: p.coords.longitude.toFixed(6) })),
      () => toast.error('Location permission denied'),
      { enableHighAccuracy: true }
    );
  };

  const findOnMap = async () => {
    if (!form.address || !form.address.trim()) return toast.error('Type an address first');
    setGeocoding(true);
    try {
      const { data } = await api.get('/office-locations/geocode', { params: { address: form.address } });
      if (!data.found) {
        toast.error('Address not found. Try adding city or country.');
      } else {
        setForm((f) => ({ ...f, latitude: data.latitude.toFixed(6), longitude: data.longitude.toFixed(6) }));
        toast.success('Address resolved');
      }
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setGeocoding(false); }
  };

  const submit = async () => {
    if (!form.name) return toast.error('Office name is required');
    const hasLatLng = form.latitude && form.longitude;
    if (!hasLatLng && !form.address) {
      return toast.error('Provide an address (we will geocode it) or latitude/longitude');
    }
    setBusy(true);
    try {
      const payload = {
        name: form.name,
        address: form.address || null,
        radius_meters: Number(form.radius_meters) || 100,
      };
      if (hasLatLng) {
        payload.latitude = Number(form.latitude);
        payload.longitude = Number(form.longitude);
      }
      await api.post('/office-locations', payload);
      setForm({ name: '', address: '', latitude: '', longitude: '', radius_meters: 100 });
      setDialogOpen(false);
      toast.success('Office added');
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  const del = async (id) => {
    if (!window.confirm('Delete this office location?')) return;
    try {
      await api.delete(`/office-locations/${id}`);
      toast.success('Deleted');
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  if (loading) return <div className="p-6 text-sm text-[#64748B]">Loading…</div>;

  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="office-locations-tab">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2"><Building2 className="w-5 h-5" /> Office Locations</CardTitle>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="add-office-button">
              <Plus className="w-4 h-4 mr-1" /> Add Office
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md" data-testid="office-dialog">
            <DialogHeader>
              <DialogTitle>Add Office Location</DialogTitle>
              <DialogDescription>Type an address and we'll auto-find the coordinates. Employees will see their distance from the nearest office.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1"><Label>Name *</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="HQ - Dhaka" data-testid="office-name" /></div>
              <div className="space-y-1">
                <Label>Address (address alone is enough — we'll find the map coordinates)</Label>
                <div className="flex gap-2">
                  <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} placeholder="e.g. Gulshan 2, Dhaka, Bangladesh" data-testid="office-address" />
                  <Button variant="outline" onClick={findOnMap} disabled={geocoding} data-testid="office-find-on-map">
                    <Search className="w-4 h-4 mr-1" /> {geocoding ? '…' : 'Find'}
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Latitude</Label><Input value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} placeholder="auto" data-testid="office-lat" /></div>
                <div className="space-y-1"><Label>Longitude</Label><Input value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} placeholder="auto" data-testid="office-lng" /></div>
              </div>
              <Button variant="outline" size="sm" onClick={useCurrent} data-testid="use-current-location">
                <Crosshair className="w-4 h-4 mr-2" /> Use my current location
              </Button>
              <div className="space-y-1">
                <Label>Geofence radius (metres)</Label>
                <Input type="number" value={form.radius_meters} onChange={(e) => setForm({ ...form, radius_meters: e.target.value })} data-testid="office-radius" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={submit} disabled={busy} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="submit-office">{busy ? 'Saving…' : 'Save'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardHeader>
      <CardContent>
        {offices.length === 0 ? (
          <p className="text-center py-8 text-[#64748B]">No offices yet. Add one to start showing employee distance-from-office.</p>
        ) : (
          <div className="space-y-2">
            {offices.map((o) => (
              <div key={o.id} className="flex items-start justify-between p-4 rounded-lg bg-[#F8FAFC] dark:bg-[#27272A]" data-testid={`office-row-${o.id}`}>
                <div>
                  <p className="font-medium text-[#0F172A] dark:text-[#FAFAFA] flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-[#4F46E5]" /> {o.name}
                  </p>
                  {o.address && <p className="text-sm text-[#64748B]">{o.address}</p>}
                  <p className="text-xs text-[#64748B] mt-1">
                    {o.latitude.toFixed(6)}, {o.longitude.toFixed(6)} · geofence {o.radius_meters}m
                  </p>
                </div>
                <Button size="icon" variant="ghost" onClick={() => del(o.id)} data-testid={`delete-office-${o.id}`}>
                  <Trash2 className="w-4 h-4 text-red-500" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default OfficeLocationsTab;
