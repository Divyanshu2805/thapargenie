import { CalendarDays, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { Popover } from 'radix-ui';
import { useState } from 'react';
import { DayPicker } from 'react-day-picker';

import { cn } from '@/lib/utils';

// A themed calendar in place of the browser's date picker.
// The value is the same 'YYYY-MM-DD' string a native date input uses, and onChange gets an
// event-like `{ target: { value } }`, so it drops in where `<Input type="date">` was.

function parse(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : undefined;
}

function format(date) {
  const pad = (number) => String(number).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function CalendarChevron({ orientation }) {
  return orientation === 'left' ? <ChevronLeft className="size-4" /> : <ChevronRight className="size-4" />;
}

const DISPLAY = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

export function DatePicker({ id, value, onChange, placeholder = 'Pick a date', className, disabled, ...aria }) {
  const [open, setOpen] = useState(false);
  const selected = parse(value);
  const [month, setMonth] = useState(selected || new Date());
  const emit = (next) => onChange?.({ target: { value: next } });

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        if (next) setMonth(selected || new Date());
        setOpen(next);
      }}
    >
      <div className={cn('relative', className)}>
        <Popover.Trigger asChild>
          <button
            id={id}
            type="button"
            disabled={disabled}
            {...aria}
            className="flex h-10 w-full items-center gap-2.5 rounded-lg border border-transparent bg-field pr-9 pl-3 text-left text-sm transition-[border-color,box-shadow,background-color] duration-150 outline-none hover:border-primary/40 hover:ring-4 hover:ring-primary/[0.07] focus-visible:border-ring focus-visible:bg-card focus-visible:ring-4 focus-visible:ring-ring/15 disabled:cursor-not-allowed disabled:opacity-50 data-[state=open]:border-ring data-[state=open]:bg-card"
          >
            <CalendarDays className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <span className={cn('truncate tabular-nums', !selected && 'text-muted-foreground/80')}>
              {selected ? DISPLAY.format(selected) : placeholder}
            </span>
          </button>
        </Popover.Trigger>
        {selected && !disabled ? (
          <button
            type="button"
            onClick={() => emit('')}
            className="absolute top-1/2 right-2 flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground"
          >
            <X className="size-3.5" aria-hidden="true" />
            <span className="sr-only">Clear date</span>
          </button>
        ) : null}
      </div>
      <Popover.Portal>
        <Popover.Content
          align="start"
          side="bottom"
          sideOffset={6}
          collisionPadding={12}
          className="z-50 animate-pop-in rounded-2xl border bg-popover p-3 text-popover-foreground shadow-lift outline-none"
        >
          <DayPicker
            mode="single"
            selected={selected}
            month={month}
            onMonthChange={setMonth}
            onSelect={(date) => {
              if (date) emit(format(date));
              setOpen(false);
            }}
            showOutsideDays
            // Always six weeks, so the calendar keeps one size from month to month.
            fixedWeeks
            weekStartsOn={1}
            components={{ Chevron: CalendarChevron }}
            classNames={{
              root: 'relative w-fit',
              months: 'flex flex-col',
              month: 'space-y-3',
              month_caption: 'flex h-8 items-center px-1',
              caption_label: 'text-sm font-semibold',
              nav: 'absolute top-0 right-0 flex h-8 items-center gap-1',
              button_previous:
                'flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground disabled:opacity-40',
              button_next:
                'flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground disabled:opacity-40',
              month_grid: 'border-collapse',
              weekdays: 'flex',
              weekday: 'w-9 pb-1 text-center text-[11px] font-medium tracking-wide text-muted-foreground uppercase',
              week: 'mt-0.5 flex',
              day: 'size-9 p-0 text-center text-sm',
              day_button:
                'size-9 rounded-lg tabular-nums transition-colors outline-none hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring/50',
              today: 'font-semibold text-primary dark:text-accent-foreground',
              selected:
                '[&>button]:bg-primary [&>button]:font-semibold [&>button]:text-primary-foreground [&>button]:shadow-sm [&>button]:hover:bg-primary',
              outside: 'text-muted-foreground/45',
              disabled: 'opacity-40',
            }}
          />
          <div className="mt-2 flex items-center justify-between border-t pt-2">
            <button
              type="button"
              onClick={() => {
                emit('');
                setOpen(false);
              }}
              className="rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-foreground/10 hover:text-foreground"
            >
              Clear
            </button>
            <button
              type="button"
              onClick={() => {
                emit(format(new Date()));
                setOpen(false);
              }}
              className="rounded-md px-2 py-1 text-xs font-semibold text-primary transition-colors hover:bg-primary/10 dark:text-accent-foreground"
            >
              Today
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
