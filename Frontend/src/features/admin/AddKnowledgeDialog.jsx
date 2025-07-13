import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BookPlus, CalendarClock, FileText, FileUp, Globe, Tags, Upload, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { SectionFields, SectionRow, SectionToggle, SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { CATEGORIES, PARSERS } from '@/features/admin/constants';
import { addDocumentFromText, addDocumentFromUrl, uploadDocuments } from '@/lib/api/admin';
import { formatBytes } from '@/lib/format';
import { cn } from '@/lib/utils';

const MAX_FILES = 10;
const MAX_FILE_MB = 25;
const ACCEPT = '.pdf,.docx,.xlsx,.csv,.html,.htm';
const ACADEMIC_YEAR = /^\d{4}-\d{2}$/;

const EMPTY_META = { category: 'other', academic_year: '', department: '', is_current: true, source_url: '' };

/** Metadata the API accepts, without empty strings (the API treats a missing field as "default"). */
export function cleanMeta(meta) {
  const out = {};
  for (const [key, value] of Object.entries(meta)) {
    if (value === '' || value === null || value === undefined) continue;
    out[key] = typeof value === 'string' ? value.trim() : value;
  }
  return out;
}

export function validateMeta(meta) {
  const errors = {};
  if (meta.academic_year && !ACADEMIC_YEAR.test(meta.academic_year.trim())) errors.academic_year = 'Use the form 2026-27.';
  if (meta.source_url && !meta.source_url.trim().startsWith('https://')) errors.source_url = 'Only https links are allowed.';
  return errors;
}

function FieldError({ id, children }) {
  return children ? (
    <p id={id} className="text-xs text-destructive">
      {children}
    </p>
  ) : null;
}

function DetailsFields({ meta, setMeta, errors, showSourceUrl = true }) {
  const set = (name) => (event) => setMeta((current) => ({ ...current, [name]: event.target.value }));
  return (
    <SectionFields className="sm:grid-cols-2">
      <div className="grid content-start gap-2">
        <Label htmlFor="meta-category">Category</Label>
        <Select id="meta-category" value={meta.category} onChange={set('category')} options={CATEGORIES} />
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="meta-year">Academic year</Label>
        <Input
          id="meta-year"
          placeholder="2026-27"
          value={meta.academic_year}
          onChange={set('academic_year')}
          aria-invalid={Boolean(errors.academic_year)}
          aria-describedby={errors.academic_year ? 'meta-year-error' : undefined}
        />
        <FieldError id="meta-year-error">{errors.academic_year}</FieldError>
      </div>
      <div className={cn('grid content-start gap-2', !showSourceUrl && 'sm:col-span-2')}>
        <Label htmlFor="meta-department">Department</Label>
        <Input id="meta-department" placeholder="Optional" maxLength={120} value={meta.department} onChange={set('department')} />
      </div>
      {showSourceUrl ? (
        <div className="grid content-start gap-2">
          <Label htmlFor="meta-source">Official page (https)</Label>
          <Input
            id="meta-source"
            type="url"
            placeholder="https://www.thapar.edu/…"
            value={meta.source_url}
            onChange={set('source_url')}
            aria-invalid={Boolean(errors.source_url)}
            aria-describedby={errors.source_url ? 'meta-source-error' : undefined}
          />
          <FieldError id="meta-source-error">{errors.source_url}</FieldError>
        </div>
      ) : null}
    </SectionFields>
  );
}

function ValidityFields({ meta, setMeta }) {
  return (
    <>
      <SectionToggle
        id="meta-current"
        title="Current information"
        description="Turn off for superseded documents. They stay searchable but rank lower."
        checked={meta.is_current}
        onChange={(checked) => setMeta((current) => ({ ...current, is_current: checked }))}
      />
    </>
  );
}

function Dropzone({ files, setFiles }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const add = (list) => {
    const incoming = [...list];
    setFiles((current) => {
      const names = new Set(current.map((file) => file.name + file.size));
      return [...current, ...incoming.filter((file) => !names.has(file.name + file.size))].slice(0, MAX_FILES);
    });
  };

  return (
    <div className="grid gap-3">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          add(event.dataTransfer.files);
        }}
        className={cn(
          'flex flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors outline-none hover:border-primary/40 hover:bg-hover focus-visible:ring-[3px] focus-visible:ring-ring/30',
          dragging && 'border-primary bg-accent/50',
        )}
      >
        <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Upload className="size-5" aria-hidden="true" />
        </span>
        <span className="text-sm font-medium">Drop files here or click to choose</span>
        <span className="text-xs text-muted-foreground">
          PDF, Word, Excel, CSV or HTML · up to {MAX_FILES} files, {MAX_FILE_MB} MB each
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose files"
        onChange={(event) => {
          add(event.target.files);
          event.target.value = '';
        }}
      />
      {files.length ? (
        <ul className="divide-y rounded-lg border">
          {files.map((file) => {
            const tooLarge = file.size > MAX_FILE_MB * 1024 * 1024;
            return (
              <li key={file.name + file.size} className="flex items-center gap-3 px-3 py-2 text-sm">
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{file.name}</span>
                <span className={cn('text-xs text-muted-foreground tabular-nums', tooLarge && 'text-destructive')}>
                  {tooLarge ? `Over ${MAX_FILE_MB} MB` : formatBytes(file.size)}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => setFiles((current) => current.filter((item) => item !== file))}
                  className="rounded p-1 text-muted-foreground hover:bg-hover hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * `initial` prefills the FAQ tab: {tab: 'text', title, text}. `onCreated(documents)` runs after success.
 */
export default function AddKnowledgeDialog({ open, onOpenChange, initial, onCreated }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState(initial?.tab || 'upload');
  const [meta, setMeta] = useState({ ...EMPTY_META, ...(initial?.meta || {}) });
  const [errors, setErrors] = useState({});
  const [files, setFiles] = useState([]);
  const [title, setTitle] = useState(initial?.title || '');
  const [parser, setParser] = useState('auto');
  const [url, setUrl] = useState('');
  const [text, setText] = useState(initial?.text || '');
  const [duplicateOf, setDuplicateOf] = useState(null);

  const finish = (created) => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] });
    queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
    onCreated?.(created);
    onOpenChange(false);
  };

  const mutation = useMutation({
    mutationFn: () => {
      const base = cleanMeta(meta);
      if (tab === 'upload') {
        const single = files.length === 1 && title.trim() ? { title: title.trim() } : {};
        return uploadDocuments(files, { ...base, ...single, parser });
      }
      if (tab === 'url') {
        // A web page is its own source; the URL endpoint takes no separate source_url.
        const rest = { ...base };
        delete rest.source_url;
        return addDocumentFromUrl({ ...rest, url: url.trim(), ...(title.trim() ? { title: title.trim() } : {}) });
      }
      return addDocumentFromText({ ...base, title: title.trim(), text: text.trim() });
    },
    onSuccess: (result) => {
      if (tab === 'upload') {
        const created = result.created || [];
        const rejected = result.rejected || [];
        toast.success(`${created.length} file${created.length === 1 ? '' : 's'} queued for processing`);
        for (const item of rejected) toast.error(`${item.filename} was skipped`, { description: item.message });
        finish(created);
      } else {
        toast.success(tab === 'url' ? 'Page queued for processing' : 'Entry queued for processing');
        finish([result]);
      }
    },
    onError: (error) => {
      if (error.code === 'duplicate_document') setDuplicateOf(error);
      if (error.fields) setErrors(Object.fromEntries(Object.entries(error.fields).map(([key, value]) => [key, [].concat(value)[0]])));
      toast.error('Couldn’t add the knowledge', { description: error.message });
    },
  });

  const submit = (event) => {
    event.preventDefault();
    setDuplicateOf(null);
    const found = validateMeta(tab === 'url' ? { ...meta, source_url: '' } : meta);
    if (tab === 'url' && !url.trim().startsWith('https://')) found.url = 'Enter an https:// link on a college domain.';
    if (tab === 'text' && !title.trim()) found.title = 'Add a title.';
    if (tab === 'text' && !text.trim()) found.text = 'Write the content.';
    setErrors(found);
    if (Object.keys(found).length === 0) mutation.mutate();
  };

  const tooLarge = files.some((file) => file.size > MAX_FILE_MB * 1024 * 1024);
  const canSubmit =
    !mutation.isPending && (tab === 'upload' ? files.length > 0 && !tooLarge : tab === 'url' ? url.trim() : title.trim() && text.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] max-w-5xl flex-col gap-0 overflow-hidden p-0 sm:p-0">
        <DialogHeader className="flex-row items-center gap-3.5 border-b px-5 py-4 sm:px-8">
          <span className="icon-nudge flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <BookPlus className="size-[18px]" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <DialogTitle>Add knowledge</DialogTitle>
            <DialogDescription>Processed in the background; answerable within minutes.</DialogDescription>
          </div>
        </DialogHeader>
        <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
          {/* Laid out like the settings pages: what a section is on the left, its card on the right. */}
          <div className="min-h-0 flex-1 overflow-y-auto bg-background px-5 sm:px-8">
            <SplitSection icon={FileUp} title="Source" description="A file, an official web page, or text you write.">
              <Tabs value={tab} onValueChange={(value) => { setTab(value); setErrors({}); }} className="gap-0">
                <div className="px-5 pt-5 sm:px-6">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="upload">
                      <FileUp /> Files
                    </TabsTrigger>
                    <TabsTrigger value="url">
                      <Globe /> Web page
                    </TabsTrigger>
                    <TabsTrigger value="text">
                      <FileText /> FAQ / text
                    </TabsTrigger>
                  </TabsList>
                </div>

                <TabsContent value="upload">
                  <SectionFields>
                    <Dropzone files={files} setFiles={setFiles} />
                    {files.length === 1 ? (
                      <div className="grid content-start gap-2">
                        <Label htmlFor="upload-title">Title</Label>
                        <Input id="upload-title" placeholder={files[0].name} maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} />
                      </div>
                    ) : null}
                  </SectionFields>
                  <SectionRow
                    className="border-t"
                    title="Parsing"
                    description="Smart parsing reads scans and complex tables; Auto chooses per file."
                    htmlFor="upload-parser"
                  >
                    <Select id="upload-parser" className="w-full sm:w-52" value={parser} onChange={(event) => setParser(event.target.value)} options={PARSERS} />
                  </SectionRow>
                </TabsContent>

                <TabsContent value="url">
                  <SectionFields>
                    <div className="grid content-start gap-2">
                      <Label htmlFor="add-url">Page URL</Label>
                      <Input
                        id="add-url"
                        type="url"
                        placeholder="https://www.thapar.edu/…"
                        value={url}
                        onChange={(event) => setUrl(event.target.value)}
                        aria-invalid={Boolean(errors.url)}
                        aria-describedby={errors.url ? 'add-url-error' : 'add-url-hint'}
                      />
                      <FieldError id="add-url-error">{errors.url}</FieldError>
                      <p id="add-url-hint" className="text-xs text-muted-foreground">Only official college domains are allowed.</p>
                    </div>
                    <div className="grid content-start gap-2">
                      <Label htmlFor="url-title">Title (optional)</Label>
                      <Input id="url-title" placeholder="Taken from the page" maxLength={300} value={title} onChange={(event) => setTitle(event.target.value)} />
                    </div>
                  </SectionFields>
                </TabsContent>

                <TabsContent value="text">
                  <SectionFields>
                    <div className="grid content-start gap-2">
                      <Label htmlFor="text-title">Title</Label>
                      <Input
                        id="text-title"
                        placeholder="e.g. Hostel fee refund rules"
                        maxLength={300}
                        value={title}
                        onChange={(event) => setTitle(event.target.value)}
                        aria-invalid={Boolean(errors.title)}
                      />
                      <FieldError>{errors.title}</FieldError>
                    </div>
                    <div className="grid content-start gap-2">
                      <Label htmlFor="text-body">Content</Label>
                      <Textarea
                        id="text-body"
                        className="min-h-40"
                        maxLength={100_000}
                        placeholder={'Q: …\nA: …'}
                        value={text}
                        onChange={(event) => setText(event.target.value)}
                        aria-invalid={Boolean(errors.text)}
                      />
                      <FieldError>{errors.text}</FieldError>
                    </div>
                  </SectionFields>
                </TabsContent>
              </Tabs>
            </SplitSection>

            <SplitSection icon={Tags} title="Details" description="Used to filter and rank search results.">
              <DetailsFields meta={meta} setMeta={setMeta} errors={errors} showSourceUrl={tab !== 'url'} />
            </SplitSection>

            <SplitSection icon={CalendarClock} title="Validity" description="When this stops being the current answer.">
              <ValidityFields meta={meta} setMeta={setMeta} />
            </SplitSection>

            {duplicateOf ? (
              <p role="alert" className="mb-6 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm">
                This content is already in the knowledge base.{' '}
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
            <Button type="submit" disabled={!canSubmit}>
              {mutation.isPending ? 'Adding…' : 'Add to knowledge base'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
