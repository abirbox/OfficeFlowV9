// Frontend permission helper — mirrors backend utils/permissions.py
export const PERMISSION_GROUPS = [
  {
    key: 'dashboard', label: 'Dashboard',
    perms: [{ code: 'dispatch.dashboard.view', label: 'View Dashboard' }],
  },
  {
    key: 'schedule', label: 'Schedule',
    perms: [
      { code: 'dispatch.schedule.view', label: 'View Schedule' },
      { code: 'dispatch.schedule.create', label: 'Create Schedule' },
      { code: 'dispatch.schedule.edit', label: 'Edit Schedule' },
      { code: 'dispatch.schedule.cancel', label: 'Cancel Schedule' },
      { code: 'dispatch.schedule.delete', label: 'Delete Schedule' },
    ],
  },
  {
    key: 'clients', label: 'Clients',
    perms: [
      { code: 'dispatch.clients.view', label: 'View' },
      { code: 'dispatch.clients.create', label: 'Create' },
      { code: 'dispatch.clients.edit', label: 'Edit' },
      { code: 'dispatch.clients.delete', label: 'Delete' },
    ],
  },
  {
    key: 'vendors', label: 'Vendors',
    perms: [
      { code: 'dispatch.vendors.view', label: 'View' },
      { code: 'dispatch.vendors.create', label: 'Create' },
      { code: 'dispatch.vendors.edit', label: 'Edit' },
      { code: 'dispatch.vendors.delete', label: 'Delete' },
    ],
  },
  {
    key: 'officers', label: 'Security Officers',
    perms: [
      { code: 'dispatch.officers.view', label: 'View' },
      { code: 'dispatch.officers.create', label: 'Create' },
      { code: 'dispatch.officers.edit', label: 'Edit' },
      { code: 'dispatch.officers.delete', label: 'Delete' },
    ],
  },
  {
    key: 'post_sites', label: 'Post Sites',
    perms: [
      { code: 'dispatch.post_sites.view', label: 'View' },
      { code: 'dispatch.post_sites.create', label: 'Create' },
      { code: 'dispatch.post_sites.edit', label: 'Edit' },
      { code: 'dispatch.post_sites.delete', label: 'Delete' },
    ],
  },
  {
    key: 'confirmation', label: 'Confirmation',
    perms: [
      { code: 'dispatch.confirmation.view', label: 'View' },
      { code: 'dispatch.confirmation.manage', label: 'Manage' },
      { code: 'dispatch.confirmation.history', label: 'View History' },
    ],
  },
  {
    key: 'reports', label: 'Reports',
    perms: [
      { code: 'dispatch.reports.view', label: 'View' },
      { code: 'dispatch.reports.export', label: 'Export' },
    ],
  },
  {
    key: 'payment_so', label: 'Payment (SO)',
    perms: [
      { code: 'dispatch.payment_so.view', label: 'View Payment (SO)' },
    ],
  },
  {
    key: 'financial', label: 'Financial',
    perms: [
      { code: 'dispatch.financial.view', label: 'View Duty Rate / Billing Rate / Work Order' },
      { code: 'dispatch.financial.adjust', label: 'Adjust Payslip (Advance / Addition / Deduction)' },
      { code: 'dispatch.billing.view', label: 'View Billing Reports' },
    ],
  },
  { key: 'audit', label: 'Audit', perms: [{ code: 'dispatch.audit.view', label: 'View Audit Logs' }] },
];

export const ALL_PERMISSION_CODES = PERMISSION_GROUPS.flatMap((g) => g.perms.map((p) => p.code));

export function hasPermission(user, code) {
  if (!user) return false;
  if (user.role === 'super_admin') return true;
  if (user.role === 'hd' && code.startsWith('dispatch.')) return true;
  return (user.permissions || []).includes(code);
}

export function hasAnyDispatchPerm(user) {
  if (!user) return false;
  if (user.role === 'super_admin' || user.role === 'hd') return true;
  return (user.permissions || []).some((p) => p.startsWith('dispatch.'));
}
