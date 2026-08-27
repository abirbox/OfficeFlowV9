import { useEffect, useState } from 'react';
import { api, formatApiErrorDetail } from '@/lib/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/components/ui/sonner';
import { Mail, Save, ShieldCheck } from 'lucide-react';

const EmailSettingsTab = () => {
  const [form, setForm] = useState({ smtp_host: '', smtp_port: 587, username: '', password: '', from_email: '' });
  const [hasPassword, setHasPassword] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    api.get('/settings/email')
      .then(({ data }) => {
        setForm({
          smtp_host: data.smtp_host || '',
          smtp_port: data.smtp_port || 587,
          username: data.username || '',
          password: '',
          from_email: data.from_email || '',
        });
        setHasPassword(!!data.has_password);
      })
      .catch((e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const setF = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const save = async () => {
    if (!form.smtp_host || !form.username || !form.from_email) {
      toast.error('SMTP Host, Username and From Email are required');
      return;
    }
    if (!hasPassword && !form.password) {
      toast.error('Password is required for the first save');
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.put('/settings/email', {
        smtp_host: form.smtp_host,
        smtp_port: Number(form.smtp_port) || 587,
        username: form.username,
        from_email: form.from_email,
        password: form.password || undefined,
      });
      setHasPassword(!!data.has_password);
      setForm((p) => ({ ...p, password: '' }));
      toast.success('Email settings saved');
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSaving(false); }
  };

  return (
    <Card className="border-[#E2E8F0] dark:border-[#27272A]" data-testid="email-settings-tab">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="w-5 h-5 text-[#4F46E5]" /> Email Settings (SMTP)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-start gap-2 text-sm text-[#64748B] dark:text-[#A1A1AA] bg-[#F8FAFC] dark:bg-[#0F0F11] border border-[#E2E8F0] dark:border-[#27272A] rounded-lg p-3">
          <ShieldCheck className="w-4 h-4 mt-0.5 text-emerald-600 shrink-0" />
          <span>These SMTP credentials are used by the <b>Forgot Password</b> reset email flow. The password is stored encrypted and never shown again.</span>
        </div>

        {loading ? (
          <div className="text-[#64748B]">Loading…</div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2 sm:col-span-2">
                <Label>SMTP Host</Label>
                <Input value={form.smtp_host} onChange={(e) => setF('smtp_host', e.target.value)} placeholder="smtp.gmail.com" data-testid="smtp-host-input" />
              </div>
              <div className="space-y-2">
                <Label>SMTP Port</Label>
                <Input type="number" value={form.smtp_port} onChange={(e) => setF('smtp_port', e.target.value)} placeholder="587" data-testid="smtp-port-input" />
              </div>
              <div className="space-y-2">
                <Label>From Email</Label>
                <Input type="email" value={form.from_email} onChange={(e) => setF('from_email', e.target.value)} placeholder="no-reply@company.com" data-testid="smtp-from-input" />
              </div>
              <div className="space-y-2">
                <Label>Username</Label>
                <Input value={form.username} onChange={(e) => setF('username', e.target.value)} placeholder="mailer@company.com" autoComplete="off" data-testid="smtp-username-input" />
              </div>
              <div className="space-y-2">
                <Label>Password {hasPassword && <span className="text-xs text-[#94A3B8]">(leave blank to keep current)</span>}</Label>
                <Input type="password" value={form.password} onChange={(e) => setF('password', e.target.value)} placeholder={hasPassword ? '••••••••' : 'SMTP password'} autoComplete="new-password" data-testid="smtp-password-input" />
              </div>
            </div>

            <Button onClick={save} disabled={saving} className="bg-[#4F46E5] hover:bg-[#4338CA]" data-testid="save-email-settings-button">
              <Save className="w-4 h-4 mr-2" /> {saving ? 'Saving…' : 'Save Email Settings'}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default EmailSettingsTab;
