import { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { PERMISSION_GROUPS, ALL_PERMISSION_CODES } from '@/lib/permissions';

/**
 * Collapsible permission-group UI used inside Add/Edit Employee dialogs.
 * value: string[] of permission codes
 * onChange: (nextCodes: string[]) => void
 */
const PermissionsSection = ({ value = [], onChange }) => {
  const [openGroups, setOpenGroups] = useState({});
  const set = new Set(value);

  const toggle = (code) => {
    const next = new Set(set);
    next.has(code) ? next.delete(code) : next.add(code);
    onChange(Array.from(next));
  };
  const toggleGroup = (group, on) => {
    const next = new Set(set);
    group.perms.forEach((p) => (on ? next.add(p.code) : next.delete(p.code)));
    onChange(Array.from(next));
  };
  const allOn = () => onChange([...ALL_PERMISSION_CODES]);
  const clearAll = () => onChange([]);

  return (
    <div className="space-y-3" data-testid="permissions-section">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-semibold">Permissions</Label>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={allOn} data-testid="perms-select-all">
            Select All
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={clearAll} data-testid="perms-clear-all">
            Clear All
          </Button>
        </div>
      </div>

      <div className="border border-[#E2E8F0] dark:border-[#27272A] rounded-lg divide-y divide-[#E2E8F0] dark:divide-[#27272A] max-h-72 overflow-y-auto">
        {PERMISSION_GROUPS.map((group) => {
          const open = !!openGroups[group.key];
          const groupCodes = group.perms.map((p) => p.code);
          const selectedInGroup = groupCodes.filter((c) => set.has(c)).length;
          const allInGroup = selectedInGroup === groupCodes.length;
          return (
            <div key={group.key} className="p-3">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setOpenGroups((s) => ({ ...s, [group.key]: !open }))}
                  className="flex items-center gap-2 text-sm font-medium text-[#0F172A] dark:text-[#FAFAFA]"
                  data-testid={`perm-group-toggle-${group.key}`}
                >
                  {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  {group.label}
                  <span className="text-xs text-[#64748B] dark:text-[#A1A1AA]">
                    ({selectedInGroup}/{groupCodes.length})
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => toggleGroup(group, !allInGroup)}
                  className="text-xs text-[#4F46E5] hover:underline"
                  data-testid={`perm-group-select-${group.key}`}
                >
                  {allInGroup ? 'Deselect all' : 'Select all'}
                </button>
              </div>
              {open && (
                <div className="mt-2 pl-6 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {group.perms.map((p) => (
                    <label key={p.code} className="flex items-center gap-2 text-sm cursor-pointer"
                           data-testid={`perm-${p.code}`}>
                      <Checkbox checked={set.has(p.code)} onCheckedChange={() => toggle(p.code)} />
                      <span className="text-[#334155] dark:text-[#E4E4E7]">{p.label}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PermissionsSection;
