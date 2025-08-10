import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Eye, Megaphone, PenLine, Settings2, SquarePen } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { SectionFields, SectionRow, SectionToggle, SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { DatePicker } from '@/components/ui/date-picker';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { CATEGORIES } from '@/features/admin/constants';
import { MAX_BODY, MAX_TITLE, emptyForm, formFromNotice, toPayload, validateNotice } from '@/features/admin/notice-form';
import Markdown from '@/features/chat/Markdown';
import { createNotice, updateNotice } from '@/lib/api/admin';

function FieldError({ id, children }) {
  return children ? (
    <p id={id} className="text-xs text-destructive">
      {children}
    </p>
  ) : null;
}

/** Create a notice, or edit `notice`. Laid out like "Add knowledge". */
export default function NoticeDialog({ open, onOpenChange, notice }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? <NoticeForm key={notice?.id || 'new'} notice={notice} onOpenChange={onOpenChange} /> : null}
    </Dialog>
  );
}

function NoticeForm({ notice, onOpenChange }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => (notice ? formFromNotice(notice) : emptyForm()));
  const [errors, setErrors] = useState({});
  const [view, setView] = useState('write');
  const [duplicateOf, setDuplicateOf] = useState(null);
  const set = (name) => (value) => setForm((current) => ({ ...current, [name]: value }));
  const setFromEvent = (name) => (event) => set(name)(event.target.value);

  const save = useMutation({
    mutationFn: ({ draft }) => {
      const body = toPayload(form, { draft, original: notice });
      return notice ? updateNotice(notice.id, body) : createNotice(body);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'notices'] });
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      queryClient.invalidateQueries({ queryKey: ['app-config'] });
      const message = { published: 'Notice published', scheduled: 'Notice scheduled', draft: 'Draft saved' }[saved.state];
      toast.success(message || 'Notice saved');
      onOpenChange(false);
    },
    onError: (error) => {
      if (error.code === 'duplicate_document') {
        setDuplicateOf({ message: error.message, existingId: error.existingId });
        return;
      }
      if (error.fields) {
        setErrors(Object.fromEntries(Object.entries(error.fields).map(([key, value]) => [key === 'publish_at' ? 'publish' : key, [value].flat()[0]])));
      }
      toast.error('Couldn’t save the notice', { description: error.message });
    },
  });

  const submit = (draft) => {
    const found = validateNotice(form, new Date(), notice);
    setErrors(found);
    setDuplicateOf(null);
    if (Object.keys(found).length === 0) save.mutate({ draft });
  };

  const wasPublished = notice && notice.state !== 'draft';
  const primaryLabel = form.schedule ? 'Schedule' : wasPublished ? 'Save' : 'Publish';

  return (
    <DialogContent className="flex max-h-[calc(100dvh-2rem)] max-w-5xl flex-col gap-0 overflow-hidden p-0 sm:p-0">
      <DialogHeader className="flex-row items-center gap-3.5 border-b px-5 py-4 sm:px-8">
        <span className="icon-nudge flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Megaphone className="size-[18px]" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <DialogTitle>{notice ? 'Edit notice' : 'New notice'}</DialogTitle>
          <DialogDescription>Shown on the students’ Notices page; important ones also on the chat home.</DialogDescription>
        </div>
      </DialogHeader>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit(false);
        }}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="min-h-0 flex-1 overflow-y-auto bg-background px-5 sm:px-8">
          <SplitSection icon={SquarePen} title="Notice" description="A short title, and the details in Markdown.">
            <SectionFields>
              <div className="grid content-start gap-2">
                <Label htmlFor="notice-title">Title</Label>
                <Input
                  id="notice-title"
                  placeholder="e.g. Hostel fee deadline extended to 15 October"
                  maxLength={MAX_TITLE}
                  value={form.title}
                  onChange={setFromEvent('title')}
                  aria-invalid={Boolean(errors.title)}
                  aria-describedby={errors.title ? 'notice-title-error' : undefined}
                />
                <FieldError id="notice-title-error">{errors.title}</FieldError>
              </div>
              <div className="grid content-start gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="notice-body">Details</Label>
                  <Tabs value={view} onValueChange={setView}>
                    <TabsList aria-label="Details view">
                      <TabsTrigger value="write">
                        <PenLine /> Write
                      </TabsTrigger>
                      <TabsTrigger value="preview">
                        <Eye /> Preview
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
                {view === 'write' ? (
                  <Textarea
                    id="notice-body"
                    className="min-h-40"
                    maxLength={MAX_BODY}
                    placeholder={'What changed, who it affects and what students should do.\n\n**Bold**, lists and links work.'}
                    value={form.body}
                    onChange={setFromEvent('body')}
                    aria-invalid={Boolean(errors.body)}
                  />
                ) : (
                  <div className="min-h-40 rounded-lg border bg-card px-3.5 py-3" data-testid="notice-preview">
                    {form.body.trim() ? <Markdown content={form.body} className="text-sm" /> : <p className="text-sm text-muted-foreground">Nothing to preview yet.</p>}
                  </div>
                )}
                <div className="flex justify-between gap-3 text-xs">
                  <span className={errors.body ? 'text-destructive' : 'text-muted-foreground'}>{errors.body || 'Optional.'}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {form.body.length} / {MAX_BODY}
                  </span>
                </div>
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div className="grid content-start gap-2">
                  <Label htmlFor="notice-category">Topic</Label>
                  <Select id="notice-category" value={form.category} onChange={setFromEvent('category')} options={CATEGORIES} />
                </div>
                <div className="grid content-start gap-2">
                  <Label htmlFor="notice-link">Official notice link (https)</Label>
                  <Input
                    id="notice-link"
                    type="url"
                    placeholder="Optional"
                    value={form.link_url}
                    onChange={setFromEvent('link_url')}
                    aria-invalid={Boolean(errors.link_url)}
                    aria-describedby={errors.link_url ? 'notice-link-error' : undefined}
                  />
                  <FieldError id="notice-link-error">{errors.link_url}</FieldError>
                </div>
              </div>
            </SectionFields>
          </SplitSection>

          <SplitSection icon={Settings2} title="Display" description="How it stands out, and whether the chatbot uses it.">
            <SectionToggle
              id="notice-important"
              title="Important"
              description="Highlighted, and shown on the chat home until a student dismisses it."
              checked={form.important}
              onChange={set('important')}
            />
            <SectionToggle id="notice-pinned" title="Pin to the top" description="Pinned notices come first on the Notices page." checked={form.is_pinned} onChange={set('is_pinned')} />
            <SectionToggle
              id="notice-answerable"
              title="ThaparGenie can answer from this"
              description="Adds it to the knowledge base while it’s published; removed when unpublished."
              checked={form.answerable}
              onChange={set('answerable')}
            />
          </SplitSection>

          <SplitSection icon={CalendarClock} title="Schedule" description="When it appears and when it leaves the students’ list.">
            <SectionToggle
              id="notice-schedule"
              title="Publish later"
              description={wasPublished && !form.schedule ? 'Already published.' : 'Otherwise it’s published as soon as you save.'}
              checked={form.schedule}
              onChange={set('schedule')}
            />
            {form.schedule ? (
              <SectionFields className="sm:grid-cols-2">
                <div className="grid content-start gap-2">
                  <Label htmlFor="notice-publish-date">Date</Label>
                  <DatePicker id="notice-publish-date" value={form.publish_date} onChange={setFromEvent('publish_date')} aria-invalid={Boolean(errors.publish)} />
                </div>
                <div className="grid content-start gap-2">
                  <Label htmlFor="notice-publish-time">Time</Label>
                  <Input id="notice-publish-time" type="time" value={form.publish_time} onChange={setFromEvent('publish_time')} aria-invalid={Boolean(errors.publish)} />
                </div>
                <div className="sm:col-span-2">
                  <FieldError>{errors.publish}</FieldError>
                </div>
              </SectionFields>
            ) : null}
            <SectionRow title="Expires" description="Optional. It leaves the list after this day; admins still see it." htmlFor="notice-expires">
              <div className="grid w-full gap-1 sm:w-52">
                <DatePicker id="notice-expires" value={form.expires_on} onChange={setFromEvent('expires_on')} aria-invalid={Boolean(errors.expires_on)} />
                <FieldError>{errors.expires_on}</FieldError>
              </div>
            </SectionRow>
          </SplitSection>

          {duplicateOf ? (
            <p role="alert" className="mb-6 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
              {duplicateOf.message}{' '}
              {duplicateOf.existingId ? (
                <Link className="font-medium underline underline-offset-4" to={`/admin/documents/${duplicateOf.existingId}`}>
                  Open the existing document
                </Link>
              ) : null}
            </p>
          ) : null}
        </div>

        <DialogFooter className="border-t px-5 py-4 sm:px-8">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="outline" disabled={save.isPending} onClick={() => submit(true)}>
            {wasPublished ? 'Move to drafts' : 'Save draft'}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : primaryLabel}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
