import { useState, useMemo } from 'react';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Check, ChevronsUpDown, X } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * Type-ahead single-select combobox used across the scheduling section.
 *
 * Renders a shadcn/ui Popover with a Command palette so users can filter
 * long option lists (officers, clients, vendors, post sites) by typing.
 *
 * Props:
 *   value        - currently selected option id (string)
 *   onChange     - (newValue: string | '') => void; called with '' when cleared
 *   options      - array of objects containing at minimum { id, label }
 *   getLabel     - fn(option) -> string (label used in the trigger + list). Defaults to `option.label`
 *   getSearch    - fn(option) -> string (extra searchable text, e.g. code, email). Defaults to label
 *   placeholder  - shown when nothing is selected
 *   searchPlaceholder - placeholder shown inside the search box
 *   emptyText    - shown when the search matches nothing
 *   disabled     - when true, the trigger is disabled
 *   testid       - passed through to the trigger button's data-testid
 *   allowClear   - shows an X button in the trigger when a value is chosen
 *   className    - forwarded to the trigger for width/etc.
 */
export function SearchableSelect({
  value,
  onChange,
  options = [],
  getLabel = (o) => o?.label ?? '',
  getSearch = (o) => o?.label ?? '',
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyText = 'No matches',
  disabled = false,
  testid,
  allowClear = false,
  className = '',
}) {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => options.find((o) => String(o.id) === String(value)), [options, value]);

  return (
    <Popover open={open} onOpenChange={disabled ? undefined : setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          data-testid={testid}
          className={cn(
            'w-full justify-between font-normal',
            !selected && 'text-[#64748B]',
            className,
          )}
        >
          <span className="truncate text-left">
            {selected ? getLabel(selected) : placeholder}
          </span>
          <span className="flex items-center gap-1 shrink-0">
            {allowClear && selected && (
              <X
                className="h-3.5 w-3.5 opacity-60 hover:opacity-100"
                onClick={(e) => { e.stopPropagation(); onChange(''); }}
                data-testid={testid ? `${testid}-clear` : undefined}
              />
            )}
            <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 w-[--radix-popover-trigger-width] max-h-[320px]" align="start">
        <Command
          filter={(itemValue, search) => {
            // itemValue is the option's id (see CommandItem below). We wire the
            // real haystack through the `data-search` attribute on each item.
            const el = document.querySelector(`[data-cmd-value="${itemValue}"]`);
            const hay = (el?.getAttribute('data-search') || '').toLowerCase();
            return hay.includes(search.toLowerCase()) ? 1 : 0;
          }}
        >
          <CommandInput placeholder={searchPlaceholder} data-testid={testid ? `${testid}-search` : undefined} />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {options.map((o) => {
                const label = getLabel(o);
                const search = getSearch(o);
                const isSel = String(o.id) === String(value);
                return (
                  <CommandItem
                    key={o.id}
                    value={String(o.id)}
                    data-cmd-value={String(o.id)}
                    data-search={`${label} ${search}`}
                    onSelect={(v) => { onChange(v === value ? '' : v); setOpen(false); }}
                    data-testid={testid ? `${testid}-option-${o.id}` : undefined}
                  >
                    <Check className={cn('mr-2 h-4 w-4', isSel ? 'opacity-100' : 'opacity-0')} />
                    <span className="truncate">{label}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default SearchableSelect;
