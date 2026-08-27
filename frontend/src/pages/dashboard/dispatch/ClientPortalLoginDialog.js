import { useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from '@/components/ui/sonner';
import { KeyRound } from 'lucide-react';

/**
 * Per-client action button + dialog to create / update / remove the client's
 * login credentials for the Client Portal. Rendered from the Clients table.
 */
export default function ClientPortalLoginDialog({ client }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  const openDialog = async () => {
    setOpen(true);
    setPassword('');
    try {
      const { data } = await api.get(`/dispatch/clients/${client.id}/portal`);
      setEnabled(!!data.enabled);
      setEmail(data.email || client.email || '');
    } catch (e) {
      setEnabled(false);
      setEmail(client.email || '');
    }
  };

  const save = async () => {
    if (!email) { toast.error('Email is required'); return; }
    if (!enabled && !password) { toast.error('Password is required to create the login'); return; }
    setLoading(true);
    try {
      const { data } = await api.put(`/dispatch/clients/${client.id}/portal`, {
        email,
        password: password || undefined,
      });
      setEnabled(!!data.enabled);
      setPassword('');
      toast.success('Client portal login saved');
      setOpen(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setLoading(false); }
  };

  const remove = async () => {
    if (!window.confirm(`Remove portal login access for "${client.name}"?`)) return;
    try {
      await api.delete(`/dispatch/clients/${client.id}/portal`);
      setEnabled(false);
      setPassword('');
      toast.success('Portal login removed');
      setOpen(false);
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    }
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={openDialog}
        title="Client Portal Login"
        data-testid={`portal-login-${client.id}`}
      >
        <KeyRound className="w-3 h-3" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Client Portal Login — {client.name}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div className={`text-xs font-medium px-3 py-2 rounded-lg ${enabled ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300' : 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300'}`} data-testid="portal-status">
              {enabled ? 'Portal login is ACTIVE. This client can sign in and view only their own data.' : 'No portal login yet. Set an email and password to grant this client access.'}
            </div>

            <div className="space-y-1">
              <Label>Login Email *</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="client@example.com"
                data-testid="portal-email-input"
              />
            </div>

            <div className="space-y-1">
              <Label>Password {enabled ? '(leave blank to keep current)' : '*'}</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={enabled ? '••••••••' : 'Set a password'}
                data-testid="portal-password-input"
              />
            </div>
          </div>

          <DialogFooter>
            {enabled && (
              <Button variant="ghost" className="text-red-600 mr-auto" onClick={remove} data-testid="portal-remove-btn">
                Remove Access
              </Button>
            )}
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} disabled={loading} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-portal-login">
              {loading ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
