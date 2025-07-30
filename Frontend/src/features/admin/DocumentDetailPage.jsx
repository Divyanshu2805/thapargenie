import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Cpu,
  Download,
  Eye,
  EyeOff,
  FilePen,
  FileText,
  MoreHorizontal,
  Pencil,
  RefreshCw,
  Rows3,
  Trash2,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';

import { SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { DatePicker } from '@/components/ui/date-picker';
import { validateMeta } from '@/features/admin/AddKnowledgeDialog';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, ValidityTag, useCursorList } from '@/features/admin/components';
import { CATEGORIES, PARSERS, SOURCE_TYPES, isInFlight, validityOf } from '@/features/admin/constants';
import { useRecentAuth } from '@/components/recent-auth';
import { ConfirmDialog } from '@/components/confirm-dialog';
import {
  adminKeys,
  deleteChunk,
  deleteDocument,
  disableDocument,
  enableDocument,
  getDocument,
  getDocumentFileUrl,
  listChunks,
  reprocessDocument,
  updateChunk,
  updateDocument,
} from '@/lib/api/admin';
import { formatBytes, formatDateTime, formatNumber } from '@/lib/format';

const EDITABLE = ['title', 'category', 'department', 'academic_year', 'effective_date', 'valid_until', 'is_current', 'source_url'];
const DATE_FIELDS = new Set(['effective_date', 'valid_until']);

export function changedFields(original, form) {
  const changes = {};
  for (const name of EDITABLE) {
    const before = original[name] ?? '';
    const after = typeof form[name] === 'string' ? form[name].trim() : form[name];
    if (after !== before) changes[name] = DATE_FIELDS.has(name) && after === '' ? null : after;
  }
  return changes;
}

function MetadataForm({ document }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => Object.fromEntries(EDITABLE.map((name) => [name, document[name] ?? ''])));
  const [errors, setErrors] = useState({});
  const changes = changedFields(document, form);
  const dirty = Object.keys(changes).length > 0;

  const save = useMutation({
    mutationFn: () => updateDocument(document.id, changes),
    onSuccess: (updated) => {
      queryClient.setQueryData(adminKeys.document(document.id), updated);
      // The server may change more than was sent (a past "valid until" clears "current").
      setForm(Object.fromEntries(EDITABLE.map((name) => [name, updated[name] ?? ''])));
      queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] });
      toast.success('Details saved', { description: 'Search uses the new details right away.' });
    },
    onError: (error) => {
      if (error.fields) setErrors(Object.fromEntries(Object.entries(error.fields).map(([key, value]) => [key, [].concat(value)[0]])));
      toast.error('Couldn’t save', { description: error.message });
    },
  });

  const set = (name) => (event) => setForm((current) => ({ ...current, [name]: event.target.value }));

  return (
    <form
      className="grid gap-5 p-5 sm:grid-cols-2 sm:p-6"
      onSubmit={(event) => {
        event.preventDefault();
        const found = validateMeta(form);
        if (!form.title.trim()) found.title = 'A title is required.';
        setErrors(found);
        if (!Object.keys(found).length) save.mutate();
      }}
    >
      <div className="grid gap-2 sm:col-span-2">
        <Label htmlFor="doc-title">Title</Label>
        <Input id="doc-title" maxLength={300} value={form.title} onChange={set('title')} aria-invalid={Boolean(errors.title)} />
        {errors.title ? <p className="text-xs text-destructive">{errors.title}</p> : null}
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="doc-category">Category</Label>
        <Select id="doc-category" value={form.category} onChange={set('category')} options={CATEGORIES} />
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="doc-year">Academic year</Label>
        <Input id="doc-year" placeholder="2026-27" value={form.academic_year} onChange={set('academic_year')} aria-invalid={Boolean(errors.academic_year)} />
        {errors.academic_year ? <p className="text-xs text-destructive">{errors.academic_year}</p> : null}
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="doc-department">Department</Label>
        <Input id="doc-department" maxLength={120} value={form.department} onChange={set('department')} />
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="doc-effective">Effective date</Label>
        <DatePicker id="doc-effective" value={form.effective_date || ''} onChange={set('effective_date')} />
      </div>
      <div className="grid content-start gap-2">
        <Label htmlFor="doc-valid-until">Valid until</Label>
        <DatePicker
          id="doc-valid-until"
          value={form.valid_until || ''}
          onChange={set('valid_until')}
          aria-invalid={Boolean(errors.valid_until)}
          aria-describedby="doc-valid-until-hint"
        />
        <p id="doc-valid-until-hint" className={errors.valid_until ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}>
          {errors.valid_until || 'Optional. After this day it’s marked not current automatically.'}
        </p>
      </div>
      <div className="grid gap-2 sm:col-span-2">
        <Label htmlFor="doc-source">Official page (https)</Label>
        <Input id="doc-source" type="url" value={form.source_url} onChange={set('source_url')} aria-invalid={Boolean(errors.source_url)} />
        {errors.source_url ? <p className="text-xs text-destructive">{errors.source_url}</p> : null}
      </div>
      <label htmlFor="doc-current" className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 sm:col-span-2">
        <span>
          <span className="block text-sm font-medium">Current information</span>
          <span className="block text-xs text-muted-foreground">Superseded documents stay searchable but rank lower.</span>
        </span>
        <Switch id="doc-current" checked={form.is_current} onCheckedChange={(checked) => setForm((current) => ({ ...current, is_current: checked }))} />
      </label>
      {errors.is_current ? <p className="-mt-2 text-xs text-destructive sm:col-span-2">{errors.is_current}</p> : null}
      <div className="flex justify-end gap-2 border-t pt-4 sm:col-span-2">
        <Button type="submit" disabled={!dirty || save.isPending}>
          {save.isPending ? 'Saving…' : 'Save details'}
        </Button>
        {dirty ? (
          <Button variant="ghost" onClick={() => setForm(Object.fromEntries(EDITABLE.map((name) => [name, document[name] ?? ''])))}>
            Discard
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function ChunkItem({ chunk, documentId }) {
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(chunk.content);
  const [heading, setHeading] = useState(chunk.heading_path);
  const [confirming, setConfirming] = useState(false);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: adminKeys.chunks(documentId) });
    queryClient.invalidateQueries({ queryKey: adminKeys.document(documentId) });
  };

  const save = useMutation({
    mutationFn: () => updateChunk(chunk.id, { content: content.trim(), heading_path: heading.trim() }),
    onSuccess: () => {
      setEditing(false);
      refresh();
      toast.success('Passage updated and re-embedded');
    },
    onError: (error) => toast.error('Couldn’t save the passage', { description: error.message }),
  });

  const remove = useMutation({
    mutationFn: () => withRecentAuth(() => deleteChunk(chunk.id)),
    onSuccess: () => {
      setConfirming(false);
      refresh();
      toast.success('Passage deleted');
    },
    onError: (error) => {
      setConfirming(false);
      if (error.code !== 'request_cancelled') toast.error('Couldn’t delete the passage', { description: error.message });
    },
  });

  const pages = chunk.page_start ? (chunk.page_end && chunk.page_end !== chunk.page_start ? `pp. ${chunk.page_start}–${chunk.page_end}` : `p. ${chunk.page_start}`) : null;

  return (
    <li className="group px-5 py-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground tabular-nums">#{chunk.chunk_index + 1}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-muted-foreground">
            {[chunk.heading_path, pages, `${formatNumber(chunk.token_count)} tokens`].filter(Boolean).join(' · ')}
            {chunk.is_searchable ? '' : ' · not searchable'}
          </p>
          {editing ? (
            <form
              className="mt-2 grid gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (content.trim()) save.mutate();
              }}
            >
              <label htmlFor={`heading-${chunk.id}`} className="sr-only">
                Heading path
              </label>
              <Input id={`heading-${chunk.id}`} value={heading} maxLength={500} onChange={(event) => setHeading(event.target.value)} placeholder="Heading path" />
              <label htmlFor={`content-${chunk.id}`} className="sr-only">
                Passage text
              </label>
              <Textarea id={`content-${chunk.id}`} className="min-h-40 font-mono text-[13px]" value={content} onChange={(event) => setContent(event.target.value)} />
              <div className="flex gap-2">
                <Button size="sm" type="submit" disabled={save.isPending || !content.trim()}>
                  {save.isPending ? 'Saving…' : 'Save and re-embed'}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setEditing(false);
                    setContent(chunk.content);
                    setHeading(chunk.heading_path);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <p className="mt-1.5 line-clamp-6 text-sm leading-relaxed whitespace-pre-wrap">{chunk.content}</p>
          )}
        </div>
        {!editing ? (
          <div className="flex shrink-0 gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
            <Button variant="ghost" size="icon-sm" aria-label={`Edit passage ${chunk.chunk_index + 1}`} onClick={() => setEditing(true)}>
              <Pencil />
            </Button>
            <Button variant="ghost" size="icon-sm" aria-label={`Delete passage ${chunk.chunk_index + 1}`} onClick={() => setConfirming(true)}>
              <Trash2 />
            </Button>
          </div>
        ) : null}
      </div>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete this passage?"
        description="It will no longer be used in answers. Reprocessing the document brings it back."
        confirmLabel="Delete passage"
        pendingLabel="Deleting…"
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </li>
  );
}

function Chunks({ document }) {
  const list = useCursorList({
    queryKey: adminKeys.chunks(document.id),
    fetchPage: (cursor) => listChunks(document.id, cursor),
  });
  return (
    <SplitSection
      icon={Rows3}
      title="Passages"
      description={`${formatNumber(document.chunk_count)} searchable pieces this document was split into. Edit one to fix its text; it is re-embedded.`}
      flush
    >
      {list.isPending ? (
        <TableSkeleton rows={4} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : list.rows.length === 0 ? (
        <EmptyState icon={FileText} title={isInFlight(document) ? 'Still processing' : 'No passages'}>
          {isInFlight(document) ? 'Passages appear here once processing finishes.' : 'Reprocess the document to extract its text again.'}
        </EmptyState>
      ) : (
        <>
          <ul className="divide-y">
            {list.rows.map((chunk) => (
              <ChunkItem key={chunk.id} chunk={chunk} documentId={document.id} />
            ))}
          </ul>
          <LoadMoreButton query={list} />
        </>
      )}
    </SplitSection>
  );
}

function Actions({ document }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const withRecentAuth = useRecentAuth();
  const [confirming, setConfirming] = useState(false);

  const onUpdated = (updated, message) => {
    queryClient.setQueryData(adminKeys.document(document.id), updated);
    queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] });
    queryClient.invalidateQueries({ queryKey: adminKeys.chunks(document.id) });
    toast.success(message);
  };

  const toggle = useMutation({
    mutationFn: () => (document.status === 'disabled' ? enableDocument(document.id) : disableDocument(document.id)),
    onSuccess: (updated) => onUpdated(updated, updated.status === 'disabled' ? 'Document disabled' : 'Document enabled'),
    onError: (error) => toast.error('Couldn’t change the document', { description: error.message }),
  });

  const reprocess = useMutation({
    mutationFn: (parser) => reprocessDocument(document.id, parser ? { parser } : {}),
    onSuccess: (updated) => onUpdated(updated, 'Reprocessing started'),
    onError: (error) => toast.error('Couldn’t reprocess', { description: error.message }),
  });

  const remove = useMutation({
    mutationFn: () => withRecentAuth(() => deleteDocument(document.id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] });
      queryClient.removeQueries({ queryKey: adminKeys.document(document.id) });
      toast.success('Document deleted');
      navigate('/admin/documents', { replace: true });
    },
    onError: (error) => {
      setConfirming(false);
      if (error.code !== 'request_cancelled') toast.error('Couldn’t delete the document', { description: error.message });
    },
  });

  const openOriginal = async () => {
    const tab = window.open('about:blank', '_blank');
    if (tab) tab.opener = null;
    try {
      const { url } = await getDocumentFileUrl(document.id);
      if (!/^https?:\/\//.test(url)) throw new Error('Unexpected link.');
      if (tab) tab.location.href = url;
    } catch (error) {
      tab?.close();
      toast.error('Couldn’t open the original', { description: error.message });
    }
  };

  const busy = isInFlight(document);
  return (
    <div className="flex items-center gap-2">
      {document.original_filename || document.source_url ? (
        <Button variant="outline" onClick={openOriginal}>
          <Download /> Original
        </Button>
      ) : null}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="icon" aria-label="More actions">
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          <DropdownMenuItem disabled={busy || toggle.isPending} onSelect={() => toggle.mutate()}>
            {document.status === 'disabled' ? (
              <>
                <Eye /> Enable in answers
              </>
            ) : (
              <>
                <EyeOff /> Disable in answers
              </>
            )}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuLabel>Reprocess with</DropdownMenuLabel>
          {PARSERS.map((parser) => (
            <DropdownMenuItem key={parser.value} disabled={busy || reprocess.isPending} onSelect={() => reprocess.mutate(parser.value)}>
              <RefreshCw /> {parser.label}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirming(true)}>
            <Trash2 /> Delete document
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete this document?"
        description={`“${document.title}”, its passages and its stored file will be permanently deleted. Past answers keep their citation text.`}
        confirmLabel="Delete document"
        pendingLabel="Deleting…"
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

export default function DocumentDetailPage() {
  const { documentId } = useParams();
  const document = useQuery({
    queryKey: adminKeys.document(documentId),
    queryFn: () => getDocument(documentId),
    refetchInterval: (query) => (isInFlight(query.state.data) ? 2500 : false),
  });

  const back = (
    <Link to="/admin/documents" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" aria-hidden="true" /> Documents
    </Link>
  );

  if (document.isPending) {
    return (
      <div className="page-wide space-y-6">
        {back}
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (document.isError) {
    return (
      <div className="page-wide space-y-6">
        {back}
        <ErrorState error={document.error} onRetry={() => document.refetch()} />
      </div>
    );
  }

  const doc = document.data;
  const validity = validityOf(doc);
  const facts = [
    ['Source', SOURCE_TYPES[doc.source_type] || doc.source_type],
    ['File', doc.original_filename ? `${doc.original_filename} · ${formatBytes(doc.file_size)}` : '—'],
    ['Pages', doc.page_count ? formatNumber(doc.page_count) : '—'],
    ['Parser', PARSERS.find((parser) => parser.value === doc.parser)?.label || doc.parser],
    ['Passages', formatNumber(doc.chunk_count)],
    ['Tokens', formatNumber(doc.token_count)],
    ['Added', formatDateTime(doc.created_at)],
    ['Processed', formatDateTime(doc.processed_at)],
  ];

  return (
    <div className="page-wide space-y-6">
      {back}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-title break-words">{doc.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <StatusBadge status={doc.status} />
            {doc.status_detail && isInFlight(doc) ? <span>{doc.status_detail}</span> : null}
            {!doc.is_current ? <span>Superseded</span> : null}
            {validity ? <ValidityTag validity={validity} /> : null}
          </div>
        </div>
        <Actions document={doc} />
      </div>

      {doc.status === 'failed' && doc.error ? (
        <div role="alert" className="rounded-xl border border-destructive/25 bg-destructive/5 px-4 py-3 text-sm">
          <p className="font-medium">Processing failed</p>
          <p className="mt-1 text-muted-foreground">{doc.error}</p>
          <p className="mt-2 text-muted-foreground">Try reprocessing with Smart parsing for scans or complex tables.</p>
        </div>
      ) : null}

      <div>
        <SplitSection icon={FilePen} title="Details" description="Used to filter and rank search results. Changing them re-processes the document." flush>
          <MetadataForm key={doc.id} document={doc} />
        </SplitSection>
        <SplitSection icon={Cpu} title="Processing" description="Where the text came from and how it was split." flush>
          <dl className="grid divide-y text-sm sm:grid-cols-2 sm:divide-y-0 [&>*]:border-border sm:[&>*]:border-b sm:[&>*:nth-child(odd)]:border-r">
            {facts.map(([label, value]) => (
              <div key={label} className="flex justify-between gap-3 px-5 py-3 transition-colors hover:bg-hover sm:px-6">
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="truncate text-right font-medium" title={typeof value === 'string' ? value : undefined}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </SplitSection>
        <Chunks document={doc} />
      </div>
    </div>
  );
}
