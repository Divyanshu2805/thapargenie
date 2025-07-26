import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, Gauge, MessagesSquare, Plus, Radio, Trash2, UserCheck, Workflow } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/PageHeader';
import { SectionFields, SplitSection, SectionToggle } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { ErrorState } from '@/features/admin/components';
import { adminKeys, getSettings, updateSettings } from '@/lib/api/admin';
import { chatKeys } from '@/lib/api/chat';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';

const MAX_STARTERS = 8;
const FIELDS = [
  'daily_question_limit',
  'global_daily_llm_calls',
  'rerank_enabled',
  'cache_enabled',
  'contextualize_default',
  'auto_title_enabled',
  'maintenance_mode',
  'maintenance_message',
  'banner_text',
  'starter_questions',
  'require_approval',
];

/** Only the fields that changed, so the audit log records exactly what the admin did. */
export function settingsChanges(saved, form) {
  const changes = {};
  for (const name of FIELDS) {
    if (JSON.stringify(saved[name]) !== JSON.stringify(form[name])) changes[name] = form[name];
  }
  return changes;
}

export function validateSettings(form) {
  const errors = {};
  const limit = Number(form.daily_question_limit);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000) errors.daily_question_limit = 'Between 1 and 1,000.';
  const budget = Number(form.global_daily_llm_calls);
  if (!Number.isInteger(budget) || budget < 100 || budget > 1_000_000) errors.global_daily_llm_calls = 'Between 100 and 1,000,000.';
  if (form.maintenance_mode && !form.maintenance_message.trim()) errors.maintenance_message = 'Tell students why the service is paused.';
  if (form.starter_questions.some((item) => !item.category.trim() || !item.text.trim())) {
    errors.starter_questions = 'Each starter question needs a category and a question.';
  }
  return errors;
}

function StarterEditor({ items, onChange, error }) {
  const update = (index, patch) => onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  const move = (index, delta) => {
    const next = [...items];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    onChange(next);
  };
  return (
    <div className="space-y-3 p-5 sm:p-6">
      <ol className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className="grid gap-2 rounded-lg border p-2 sm:grid-cols-[9rem_1fr_auto] sm:items-center">
            <label className="sr-only" htmlFor={`starter-category-${index}`}>
              Category {index + 1}
            </label>
            <Input
              id={`starter-category-${index}`}
              placeholder="Category"
              maxLength={40}
              value={item.category}
              onChange={(event) => update(index, { category: event.target.value })}
            />
            <label className="sr-only" htmlFor={`starter-text-${index}`}>
              Question {index + 1}
            </label>
            <Input
              id={`starter-text-${index}`}
              placeholder="Question students can tap"
              maxLength={200}
              value={item.text}
              onChange={(event) => update(index, { text: event.target.value })}
            />
            <div className="flex justify-end gap-1">
              <Button variant="ghost" size="icon-sm" aria-label={`Move question ${index + 1} up`} disabled={index === 0} onClick={() => move(index, -1)}>
                <ArrowUp />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Move question ${index + 1} down`}
                disabled={index === items.length - 1}
                onClick={() => move(index, 1)}
              >
                <ArrowDown />
              </Button>
              <Button variant="ghost" size="icon-sm" aria-label={`Remove question ${index + 1}`} onClick={() => onChange(items.filter((_, i) => i !== index))}>
                <Trash2 />
              </Button>
            </div>
          </li>
        ))}
      </ol>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <Button
        variant="outline"
        size="sm"
        disabled={items.length >= MAX_STARTERS}
        onClick={() => onChange([...items, { category: '', text: '' }])}
      >
        <Plus /> Add question {items.length >= MAX_STARTERS ? `(max ${MAX_STARTERS})` : ''}
      </Button>
      <p className="text-xs text-muted-foreground">The first four appear on the student home screen.</p>
    </div>
  );
}

function SettingsForm({ saved }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => structuredClone(saved));
  const [errors, setErrors] = useState({});
  const changes = settingsChanges(saved, form);
  const dirty = Object.keys(changes).length > 0;
  const set = (name, value) => setForm((current) => ({ ...current, [name]: value }));

  const save = useMutation({
    mutationFn: () =>
      updateSettings({
        ...changes,
        ...('daily_question_limit' in changes ? { daily_question_limit: Number(changes.daily_question_limit) } : {}),
        ...('global_daily_llm_calls' in changes ? { global_daily_llm_calls: Number(changes.global_daily_llm_calls) } : {}),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(adminKeys.settings, updated);
      queryClient.invalidateQueries({ queryKey: chatKeys.appConfig });
      setForm(structuredClone(updated));
      toast.success('Settings saved', { description: 'Students see the change within a minute.' });
    },
    onError: (error) => {
      if (error.fields) setErrors(Object.fromEntries(Object.entries(error.fields).map(([key, value]) => [key, [].concat(value)[0]])));
      toast.error('Couldn’t save settings', { description: error.message });
    },
  });

  const submit = (event) => {
    event.preventDefault();
    const found = validateSettings(form);
    setErrors(found);
    if (!Object.keys(found).length) save.mutate();
  };

  return (
    <form onSubmit={submit} className="pb-24">
      <SplitSection icon={UserCheck} title="Access" description="Who can use ThaparGenie after signing in.">
        <SectionToggle
          id="require-approval"
          title="Require admin approval for new users"
          description="On: new users wait on the Users page until an admin approves them. Off: anyone who signs in with a verified email can ask questions."
          checked={form.require_approval}
          onChange={(value) => set('require_approval', value)}
        />
        {!form.require_approval ? (
          <p className="bg-warning/5 px-5 py-3 text-xs leading-relaxed text-muted-foreground sm:px-6">
            Users waiting for approval get in on their next visit. Denied and suspended users stay blocked, and the daily question limit and AI
            budget still apply. Turning approval back on doesn’t remove anyone already approved; suspend them on the Users page.
          </p>
        ) : null}
      </SplitSection>

      <SplitSection icon={Radio} title="Service status" description="Pause asking, or show a notice on every student screen.">
        <SectionToggle
          id="maintenance"
          title="Maintenance mode"
          description="Students can read their chats but can’t ask new questions."
          checked={form.maintenance_mode}
          onChange={(value) => set('maintenance_mode', value)}
        />
        <SectionFields>
          <div className="grid content-start gap-2">
            <Label htmlFor="maintenance-message">Maintenance message</Label>
            <Textarea
              id="maintenance-message"
              className="min-h-16"
              maxLength={300}
              placeholder="ThaparGenie is being updated and will be back by 6 pm."
              value={form.maintenance_message}
              onChange={(event) => set('maintenance_message', event.target.value)}
              aria-invalid={Boolean(errors.maintenance_message)}
            />
            {errors.maintenance_message ? <p className="text-xs text-destructive">{errors.maintenance_message}</p> : null}
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="banner">Banner</Label>
            <Input
              id="banner"
              maxLength={300}
              placeholder="e.g. The fee portal is down until 5 pm."
              value={form.banner_text}
              onChange={(event) => set('banner_text', event.target.value)}
            />
            <p className="text-xs text-muted-foreground">Shown at the top of every student screen. Leave empty to hide it.</p>
          </div>
        </SectionFields>
      </SplitSection>

      <SplitSection icon={Gauge} title="Limits" description="Protect the AI budget.">
        <SectionFields className="sm:grid-cols-2">
          <div className="grid content-start gap-2">
            <Label htmlFor="daily-limit">Questions per student per day</Label>
            <Input
              id="daily-limit"
              type="number"
              min={1}
              max={1000}
              inputMode="numeric"
              value={form.daily_question_limit}
              onChange={(event) => set('daily_question_limit', event.target.value === '' ? '' : Number(event.target.value))}
              aria-invalid={Boolean(errors.daily_question_limit)}
            />
            {errors.daily_question_limit ? <p className="text-xs text-destructive">{errors.daily_question_limit}</p> : null}
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="global-budget">AI calls per day (all students)</Label>
            <Input
              id="global-budget"
              type="number"
              min={100}
              max={1000000}
              inputMode="numeric"
              value={form.global_daily_llm_calls}
              onChange={(event) => set('global_daily_llm_calls', event.target.value === '' ? '' : Number(event.target.value))}
              aria-invalid={Boolean(errors.global_daily_llm_calls)}
            />
            {errors.global_daily_llm_calls ? <p className="text-xs text-destructive">{errors.global_daily_llm_calls}</p> : null}
            <p className="text-xs text-muted-foreground">When reached, asking pauses for everyone until midnight.</p>
          </div>
        </SectionFields>
      </SplitSection>

      <SplitSection icon={Workflow} title="Answer pipeline" description="Quality and cost trade-offs for every answer.">
        <SectionToggle
          id="rerank"
          title="Rerank search results"
          description="An extra AI pass to reorder passages. More precise, about 2 s slower."
          checked={form.rerank_enabled}
          onChange={(value) => set('rerank_enabled', value)}
        />
        <SectionToggle
          id="cache"
          title="Answer cache"
          description="Reuse answers to repeated first questions. Cleared whenever the knowledge base changes."
          checked={form.cache_enabled}
          onChange={(value) => set('cache_enabled', value)}
        />
        <SectionToggle
          id="contextualize"
          title="Contextual passages for new documents"
          description="Adds a short summary to each passage before embedding. Better search, more AI calls while processing."
          checked={form.contextualize_default}
          onChange={(value) => set('contextualize_default', value)}
        />
        <SectionToggle
          id="auto-title"
          title="Automatic chat titles"
          description="Name new chats from their first question with a short AI call."
          checked={form.auto_title_enabled}
          onChange={(value) => set('auto_title_enabled', value)}
        />
      </SplitSection>

      <SplitSection icon={MessagesSquare} title="Starter questions" description="Suggestions on an empty chat, also typed into the empty question box.">
        <StarterEditor
          items={form.starter_questions}
          onChange={(value) => set('starter_questions', value)}
          error={errors.starter_questions}
        />
      </SplitSection>

      <div
        className={cn(
          'sticky bottom-4 z-10 flex items-center justify-between gap-3 rounded-2xl border bg-card/95 px-4 py-3 shadow-lift backdrop-blur transition-[border-color,box-shadow] duration-200 sm:px-5',
          dirty && 'border-primary/40 ring-4 ring-primary/10',
        )}
      >
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <span className={cn('size-2 rounded-full', dirty ? 'animate-pulse bg-warning' : 'bg-success')} aria-hidden="true" />
          {dirty ? `${Object.keys(changes).length} unsaved change${Object.keys(changes).length === 1 ? '' : 's'}` : `Saved ${formatDateTime(saved.updated_at)}`}
        </p>
        <div className="flex gap-2">
          {dirty ? (
            <Button
              variant="ghost"
              onClick={() => {
                setForm(structuredClone(saved));
                setErrors({});
              }}
            >
              Discard
            </Button>
          ) : null}
          <Button type="submit" disabled={!dirty || save.isPending}>
            {save.isPending ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </div>
    </form>
  );
}

export default function SettingsAdminPage() {
  const settings = useQuery({ queryKey: adminKeys.settings, queryFn: getSettings });
  return (
    <div className="page-wide space-y-6">
      <PageHeader title="Settings" description="Changes apply within a minute and are recorded in the audit log." />
      {settings.isPending ? (
        <div className="space-y-6" aria-busy="true" aria-label="Loading settings">
          <Skeleton className="h-48 rounded-xl" />
          <Skeleton className="h-40 rounded-xl" />
        </div>
      ) : settings.isError ? (
        <ErrorState error={settings.error} onRetry={() => settings.refetch()} />
      ) : (
        <SettingsForm key={settings.data.updated_at} saved={settings.data} />
      )}
    </div>
  );
}
