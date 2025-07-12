import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Cpu,
  Download,
  Eye,
  EyeOff,
  FilePen,
  MoreHorizontal,
  RefreshCw,
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
import { DatePicker } from '@/components/ui/date-picker';
import { validateMeta } from '@/features/admin/AddKnowledgeDialog';
import { ErrorState, StatusBadge } from '@/features/admin/components';
import { CATEGORIES, PARSERS, SOURCE_TYPES, isInFlight } from '@/features/admin/constants';
import { useRecentAuth } from '@/components/recent-auth';
import { ConfirmDialog } from '@/components/confirm-dialog';
import {
  adminKeys,
  deleteDocument,
  disableDocument,
  enableDocument,
  getDocument,
  getDocumentFileUrl,
  reprocessDocument,
  updateDocument,
} from '@/lib/api/admin';
import { formatBytes, formatDateTime, formatNumber } from '@/lib/format';

const EDITABLE = ['title', 'category', 'department', 'academic_year', 'effective_date', 'is_current', 'source_url'];
const DATE_FIELDS = new Set(['effective_date']);

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

function Actions({ document }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const withRecentAuth = useRecentAuth();
  const [confirming, setConfirming] = useState(false);

  const onUpdated = (updated, message) => {
    queryClient.setQueryData(adminKeys.document(document.id), updated);
    queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] });
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
      </div>
    </div>
  );
}
