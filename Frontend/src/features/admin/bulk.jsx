import { CalendarSearch, Eye, EyeOff, Pencil, RefreshCw, Trash2, X } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { DatePicker } from '@/components/ui/date-picker';
import { CATEGORIES } from '@/features/admin/constants';
import { cn } from '@/lib/utils';

// Bulk document actions. The server applies one action to up to
// MAX_SELECTION documents, each through the single-document rules.

export const MAX_SELECTION = 100;
// The server takes up to 100 ids per bulk request; bigger runs go in batches.
export const BATCH_SIZE = 100;

export function chunks(items, size = BATCH_SIZE) {
  const out = [];
  for (let start = 0; start < items.length; start += size) out.push(items.slice(start, start + size));
  return out;
}

/**
 * Run `send(batchIds)` for each batch in turn and add up the results. `shouldStop()` is
 * checked between batches; ids never sent are reported as `skipped`.
 */
export async function runInBatches(ids, send, { onProgress = () => {}, shouldStop = () => false } = {}) {
  const total = { succeeded: [], failed: [], skipped: [] };
  const batches = chunks(ids);
  for (const [index, batch] of batches.entries()) {
    if (shouldStop()) {
      total.skipped = batches.slice(index).flat();
      break;
    }
    const result = await send(batch);
    total.succeeded.push(...result.succeeded);
    total.failed.push(...result.failed);
    onProgress(total.succeeded.length + total.failed.length, ids.length);
  }
  return total;
}

// Changing any of these re-processes each ready document (re-embedding costs AI calls).
const REPROCESSING_FIELDS = new Set(['category', 'department', 'academic_year']);
const ACADEMIC_YEAR = /^\d{4}-\d{2}$/;

const FIELDS = [
  { name: 'category', label: 'Category', initial: 'other' },
  { name: 'academic_year', label: 'Academic year', initial: '' },
  { name: 'department', label: 'Department', initial: '' },
  { name: 'effective_date', label: 'Effective date', initial: '' },
  { name: 'valid_until', label: 'Valid until', initial: '' },
  { name: 'is_current', label: 'Current information', initial: true },
];

const emptyForm = () => Object.fromEntries(FIELDS.map((field) => [field.name, { apply: false, value: field.initial }]));

/** Only the ticked fields; an empty date clears it (null), an empty text clears it (''). */
export function bulkChanges(form) {
  const changes = {};
  for (const [name, { apply, value }] of Object.entries(form)) {
    if (!apply) continue;
    if (name === 'effective_date' || name === 'valid_until') changes[name] = value || null;
    else changes[name] = typeof value === 'string' ? value.trim() : value;
  }
  return changes;
}

export function validateBulkChanges(changes) {
  const errors = {};
  if (!Object.keys(changes).length) errors.form = 'Tick at least one field to change.';
  if (changes.academic_year && !ACADEMIC_YEAR.test(changes.academic_year)) errors.academic_year = 'Use the form 2026-27.';
  if (changes.valid_until && changes.effective_date && changes.valid_until < changes.effective_date) {
    errors.valid_until = '“Valid until” can’t be before the effective date.';
  }
  return errors;
}

export const reprocesses = (changes) => Object.keys(changes).some((name) => REPROCESSING_FIELDS.has(name));

const VERBS = {
  update: 'Updated',
  enable: 'Enabled',
  disable: 'Disabled',
  reprocess: 'Queued for reprocessing',
  delete: 'Deleted',
};

/** Toast text for a bulk result: {ok, title, description}. */
export function bulkSummary(action, { succeeded, failed, skipped = [] }) {
  const plural = (count) => `${count} document${count === 1 ? '' : 's'}`;
  const stopped = skipped.length ? `Stopped: ${plural(skipped.length)} not processed.` : null;
  if (!failed.length) {
    return { ok: !skipped.length, title: `${VERBS[action]} ${plural(succeeded.length)}`, description: stopped };
  }
  const title = succeeded.length
    ? `${VERBS[action]} ${plural(succeeded.length)}; ${failed.length} failed`
    : `${plural(failed.length)} failed`;
  return { ok: false, title, description: [failed[0].message, stopped].filter(Boolean).join(' ') };
}

const PROGRESS = {
  update: 'Updating',
  enable: 'Enabling',
  disable: 'Disabling',
  reprocess: 'Queueing',
  delete: 'Deleting',
};

function BulkField({ field, state, onChange, error }) {
  const id = `bulk-${field.name}`;
  const setValue = (value) => onChange({ apply: true, value });
  let control;
  if (field.name === 'category') {
    control = <Select id={id} value={state.value} onChange={(event) => setValue(event.target.value)} options={CATEGORIES} />;
  } else if (field.name === 'is_current') {
    control = <Switch id={id} checked={state.value} onCheckedChange={setValue} />;
  } else {
    const isDate = field.name.endsWith('_date') || field.name === 'valid_until';
    control = isDate ? (
      <DatePicker id={id} value={state.value} onChange={(event) => setValue(event.target.value)} aria-invalid={Boolean(error)} />
    ) : (
      <Input
        id={id}
        placeholder={field.name === 'academic_year' ? '2026-27' : 'Leave empty to clear'}
        maxLength={field.name === 'department' ? 120 : undefined}
        value={state.value}
        onChange={(event) => setValue(event.target.value)}
        aria-invalid={Boolean(error)}
      />
    );
  }
  return (
    <div className={cn('grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 rounded-lg border px-3 py-2.5', !state.apply && 'bg-muted/40')}>
      <input
        type="checkbox"
        id={`${id}-apply`}
        checked={state.apply}
        onChange={(event) => onChange({ ...state, apply: event.target.checked })}
        className="size-4 accent-primary"
        aria-label={`Change ${field.label.toLowerCase()}`}
      />
      <label htmlFor={id} className="text-sm font-medium">
        {field.label}
      </label>
      <div className={cn('col-start-2', !state.apply && 'opacity-60')}>{control}</div>
      {error ? <p className="col-start-2 text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

export function BulkEditDialog({ open, onOpenChange, count, pending, onSubmit }) {
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState({});
  const changes = bulkChanges(form);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            const found = validateBulkChanges(changes);
            setErrors(found);
            if (!Object.keys(found).length) onSubmit(changes);
          }}
        >
          <DialogHeader>
            <DialogTitle>
              Edit {count} document{count === 1 ? '' : 's'}
            </DialogTitle>
            <DialogDescription>Tick the fields to change. Unticked fields are left as they are on each document.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2.5">
            {FIELDS.map((field) => (
              <BulkField
                key={field.name}
                field={field}
                state={form[field.name]}
                error={errors[field.name]}
                onChange={(next) => setForm((current) => ({ ...current, [field.name]: next }))}
              />
            ))}
          </div>
          {reprocesses(changes) ? (
            <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-relaxed">
              Changing category, department or academic year re-processes each ready document, which uses AI calls.
            </p>
          ) : null}
          {errors.form ? (
            <p role="alert" className="text-sm text-destructive">
              {errors.form}
            </p>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? 'Saving…' : 'Apply changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function BulkActionBar({ count, allMatching = false, busy, progress, onAction, onClear, onStop }) {
  if (progress) {
    return (
      <div
        role="region"
        aria-label="Bulk actions"
        className="sticky bottom-4 z-20 mx-auto flex w-fit max-w-full animate-pop-in items-center gap-3 rounded-2xl border border-toolbar-border bg-toolbar p-1.5 pl-4 text-foreground shadow-lift [&_button]:text-foreground/85 [&_button:hover]:bg-hover [&_button:hover]:text-accent-foreground [&_button:hover_svg]:text-accent-foreground"
      >
        <span className="text-sm font-medium tabular-nums" role="status">
          {PROGRESS[progress.action]} {progress.done} of {progress.total}…
        </span>
        <Button size="sm" variant="outline" disabled={progress.stopping} onClick={onStop}>
          {progress.stopping ? 'Stopping…' : 'Stop'}
        </Button>
      </div>
    );
  }
  return (
    <div
      role="region"
      aria-label="Bulk actions"
      className="sticky bottom-4 z-20 mx-auto flex w-fit max-w-full animate-pop-in flex-wrap items-center gap-1 rounded-2xl border border-toolbar-border bg-toolbar p-1.5 text-foreground shadow-lift [&_button]:text-foreground/85 [&_button:hover]:bg-hover [&_button:hover]:text-accent-foreground [&_button:hover_svg]:text-accent-foreground"
    >
      <span className="px-2 text-sm font-medium tabular-nums" aria-live="polite">
        {count} selected{allMatching ? ' (all matching)' : ''}
      </span>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction('update')}>
        <Pencil /> Edit details
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction('details')}>
        <CalendarSearch /> Suggest details
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction('enable')}>
        <Eye /> Enable
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction('disable')}>
        <EyeOff /> Disable
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction('reprocess')}>
        <RefreshCw /> Reprocess
      </Button>
      <Button size="sm" variant="ghost" disabled={busy} className="ml-1 bg-destructive! text-white! hover:bg-destructive/85! [&_svg]:text-white!" onClick={() => onAction('delete')}>
        <Trash2 /> Delete
      </Button>
      <Button size="icon-sm" variant="ghost" disabled={busy} onClick={onClear} aria-label="Clear selection">
        <X />
      </Button>
    </div>
  );
}
