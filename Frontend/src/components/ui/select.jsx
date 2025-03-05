import { Check, ChevronDown } from 'lucide-react';
import { Select as SelectPrimitive } from 'radix-ui';
import { useRef, useState } from 'react';

import { cn } from '@/lib/utils';

// Radix items can't use '' as a value, but "no filter" options do.
const EMPTY = '__empty__';
const toItemValue = (value) => (value === '' || value === null || value === undefined ? EMPTY : String(value));

// Below this much room under the field, the list opens above it instead.
const MIN_ROOM_BELOW = 200;

/**
 * A themed listbox with a native-select API: `options` is [{value, label}], `onChange`
 * receives `{target: {value}}` and `placeholder` adds an empty "any" option first.
 * The list always opens scrolled to the top, so it reads and scrolls downwards.
 */
function Select({ className, options, placeholder, value, onChange, id, name, disabled, ...props }) {
  const items = placeholder !== undefined ? [{ value: '', label: placeholder }, ...options] : options;
  const triggerRef = useRef(null);
  const viewportRef = useRef(null);
  const justOpened = useRef(false);
  const [side, setSide] = useState('bottom');

  const onOpenChange = (open) => {
    if (!open) return;
    justOpened.current = true;
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) {
      const below = window.innerHeight - rect.bottom;
      setSide(below < MIN_ROOM_BELOW && rect.top > below ? 'top' : 'bottom');
    }
  };

  return (
    <SelectPrimitive.Root
      value={toItemValue(value)}
      onValueChange={(next) => onChange?.({ target: { value: next === EMPTY ? '' : next, name, id } })}
      onOpenChange={onOpenChange}
      disabled={disabled}
      name={name}
    >
      <SelectPrimitive.Trigger
        ref={triggerRef}
        id={id}
        data-slot="select"
        className={cn(
          'flex h-10 w-full cursor-pointer items-center justify-between gap-2 rounded-lg border border-transparent bg-field pr-3 pl-3 text-left text-sm transition-[border-color,box-shadow,background-color] duration-150 outline-none hover:border-primary/40 hover:ring-4 hover:ring-primary/[0.07] focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/15 disabled:cursor-not-allowed disabled:opacity-50 data-[placeholder]:text-muted-foreground data-[state=open]:border-ring data-[state=open]:bg-card [&>span]:truncate',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Value />
        <SelectPrimitive.Icon asChild>
          <ChevronDown
            className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 [[data-state=open]>&]:rotate-180"
            aria-hidden="true"
          />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          side={side}
          sideOffset={6}
          collisionPadding={12}
          avoidCollisions={false}
          // Radix scrolls the chosen option into view as it opens; start from the top instead.
          onFocusCapture={() => {
            if (!justOpened.current) return;
            justOpened.current = false;
            requestAnimationFrame(() => {
              if (viewportRef.current) viewportRef.current.scrollTop = 0;
            });
          }}
          className="z-50 flex max-h-[min(20rem,var(--radix-select-content-available-height))] min-w-[var(--radix-select-trigger-width)] animate-rise flex-col overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lift"
        >
          <SelectPrimitive.Viewport ref={viewportRef} data-slot="select-viewport" className="p-1.5">
            {items.map((item) => (
              <SelectPrimitive.Item
                key={toItemValue(item.value)}
                value={toItemValue(item.value)}
                className="relative flex cursor-pointer items-center gap-2 rounded-md py-2 pr-8 pl-2.5 text-sm outline-none select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-primary/10 data-[state=checked]:bg-primary/15 data-[state=checked]:font-semibold data-[state=checked]:text-primary dark:data-[state=checked]:text-accent-foreground"
              >
                <SelectPrimitive.ItemText>{item.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-2.5 flex items-center">
                  <Check className="size-4" aria-hidden="true" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export { Select };
