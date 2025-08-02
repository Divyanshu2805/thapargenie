import { useMutation, useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { DatePicker } from '@/components/ui/date-picker';
import { chunks } from '@/features/admin/bulk';
import { suggestDetails } from '@/lib/api/admin';
import { cn } from '@/lib/utils';

// Review suggested sessions and issue dates before applying them.
// The server suggests; nothing is saved until the admin applies accepted rows.

const ACADEMIC_YEAR = /^\d{4}-\d{2}$/;
export const MAX_AI_DOCUMENTS = 20; // matches knowledge/details.py

const SOURCE_LABELS = { title: 'Title', text: 'Text', ai: 'AI' };

function changesFor(row) {
  const changes = {};
  if (row.academic_year && row.academic_year !== row.current_academic_year) changes.academic_year = row.academic_year;
  if (row.effective_date && row.effective_date !== (row.current_effective_date || '')) changes.effective_date = row.effective_date;
  return changes;
}

/** Editable rows from the API results; a row is ticked when it would change something. */
export function toRows(results) {
  return results.map((result) => {
    const row = { ...result, academic_year: result.academic_year || '', effective_date: result.effective_date || '' };
    return { ...row, accept: Boolean(result.source) && Object.keys(changesFor(row)).length > 0 };
  });
}

/** Fill rows the rules left empty with the AI's answers (never overwrite a rule result). */
export function mergeAi(rows, results) {
  const byId = new Map(results.filter((result) => result.source === 'ai').map((result) => [result.id, result]));
  return rows.map((row) => {
    const ai = !row.source && byId.get(row.id);
    return ai ? { ...row, ...toRows([ai])[0] } : row;
  });
}

export function rowsNeedingAi(rows) {
  return rows.filter((row) => !row.source).slice(0, MAX_AI_DOCUMENTS);
}

export function validateRows(rows) {
  const errors = {};
  for (const row of rows) {
    if (row.accept && row.academic_year && !ACADEMIC_YEAR.test(row.academic_year)) errors[row.id] = 'Use the form 2026-27.';
  }
  return errors;
}

/** {documentId: changes} for the ticked rows that change something. */
export function acceptedChanges(rows) {
  const out = {};
  for (const row of rows) {
    if (!row.accept) continue;
    const changes = changesFor(row);
    if (Object.keys(changes).length) out[row.id] = changes;
  }
  return out;
}

export function SuggestDetailsDialog({ ids, open, onOpenChange, pending, onApply }) {
  const [errors, setErrors] = useState({});
  const suggestions = useQuery({
    queryKey: ['admin', 'suggest-details', ids],
    // The server takes 100 ids per request; "all matching" can be more.
    queryFn: async () => {
      const results = [];
      for (const batch of chunks(ids)) results.push(...(await suggestDetails({ ids: batch })).results);
      return { results };
    },
    staleTime: Infinity,
    gcTime: 0,
  });
  // The rows come from the suggestions until the admin edits them (or asks the AI).
  const suggested = useMemo(() => (suggestions.data ? toRows(suggestions.data.results) : null), [suggestions.data]);
  const [edited, setEdited] = useState(null);
  const rows = edited ?? suggested;
  const setRows = (update) => setEdited((current) => update(current ?? suggested));

  const needingAi = rows ? rowsNeedingAi(rows) : [];
  const askAi = useMutation({
    mutationFn: () => suggestDetails({ ids: needingAi.map((row) => row.id), ai: true }),
    onSuccess: ({ results }) => {
      const before = rows.filter((row) => row.source).length;
      const merged = mergeAi(rows, results);
      setRows(() => merged);
      const found = merged.filter((row) => row.source).length - before;
      toast(found ? `The AI suggested details for ${found} more` : 'The AI found no stated session or date');
    },
    onError: (error) => toast.error('Couldn’t ask the AI', { description: error.message }),
  });

  const update = (id, patch) => setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const changes = rows ? acceptedChanges(rows) : {};
  const count = Object.keys(changes).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Suggest details</DialogTitle>
          <DialogDescription>
            Sessions found in each document’s title or text. Check them, edit if needed, and apply the ticked rows. A new session
            re-processes the document.
          </DialogDescription>
        </DialogHeader>

        {suggestions.isPending || rows === null ? (
          <p className="py-8 text-center text-sm text-muted-foreground">{suggestions.isError ? suggestions.error.message : 'Looking for sessions…'}</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="w-8 p-2" scope="col">
                    <span className="sr-only">Apply</span>
                  </th>
                  <th className="p-2 font-medium" scope="col">Document</th>
                  <th className="p-2 font-medium" scope="col">Session</th>
                  <th className="p-2 font-medium" scope="col">Issued</th>
                  <th className="p-2 font-medium" scope="col">Found in</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className={cn('border-t align-top', !row.accept && 'text-muted-foreground')}>
                    <td className="p-2">
                      <input
                        type="checkbox"
                        className="mt-2 size-4 accent-primary"
                        checked={row.accept}
                        onChange={(event) => update(row.id, { accept: event.target.checked })}
                        aria-label={`Apply to ${row.title}`}
                      />
                    </td>
                    <td className="max-w-[16rem] p-2">
                      <p className="line-clamp-2 font-medium text-foreground">{row.title}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Now: {row.current_academic_year || 'no session'} · {row.current_effective_date || 'no date'}
                      </p>
                    </td>
                    <td className="w-28 p-2">
                      <Input
                        aria-label={`Session for ${row.title}`}
                        placeholder="2026-27"
                        value={row.academic_year}
                        aria-invalid={Boolean(errors[row.id])}
                        onChange={(event) => update(row.id, { academic_year: event.target.value.trim(), accept: true })}
                      />
                      {errors[row.id] ? <p className="mt-1 text-xs text-destructive">{errors[row.id]}</p> : null}
                    </td>
                    <td className="w-40 p-2">
                      <DatePicker
                        aria-label={`Issue date for ${row.title}`}
                        value={row.effective_date}
                        onChange={(event) => update(row.id, { effective_date: event.target.value, accept: true })}
                      />
                    </td>
                    <td className="max-w-[18rem] p-2 text-xs">
                      {row.source ? (
                        <>
                          <span className="mr-1.5 rounded bg-accent px-1.5 py-0.5 font-medium text-accent-foreground">{SOURCE_LABELS[row.source]}</span>
                          <span className="text-muted-foreground">{row.evidence}</span>
                        </>
                      ) : (
                        <span className="text-muted-foreground">{row.evidence || 'Nothing found'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button
            variant="outline"
            disabled={!needingAi.length || askAi.isPending || pending}
            onClick={() => askAi.mutate()}
          >
            <Sparkles />
            {askAi.isPending ? 'Asking the AI…' : `Ask AI for the rest (${needingAi.length})`}
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              disabled={!count || pending}
              onClick={() => {
                const found = validateRows(rows);
                setErrors(found);
                if (!Object.keys(found).length) onApply(changes);
              }}
            >
              {pending ? 'Applying…' : `Apply to ${count} document${count === 1 ? '' : 's'}`}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
