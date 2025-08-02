import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText, Globe, Library, Plus, Search } from 'lucide-react';
import { useDeferredValue, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ConfirmDialog } from '@/components/confirm-dialog';
import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { useRecentAuth } from '@/components/recent-auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import AddKnowledgeDialog from '@/features/admin/AddKnowledgeDialog';
import { BulkActionBar, BulkEditDialog, MAX_SELECTION, bulkSummary, runInBatches } from '@/features/admin/bulk';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, ValidityTag, useCursorList } from '@/features/admin/components';
import {
  CATEGORIES,
  DOCUMENT_STATUSES,
  SOURCE_TYPES,
  VALIDITY_FILTERS,
  isInFlight,
  labelOf,
  validityOf,
} from '@/features/admin/constants';
import { adminKeys, bulkDocuments, listDocuments, listMatchingDocumentIds } from '@/lib/api/admin';
import { formatNumber, formatRelative } from '@/lib/format';

const NO_IDS = new Set();

export default function DocumentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const q = useDeferredValue(search.trim());
  // Kept in the URL so other pages can link to a filtered list (e.g. "expiring soon").
  const urlFilter = (name, options) => {
    const value = searchParams.get(name) || '';
    return options.some((option) => option.value === value) ? value : '';
  };
  const setUrlFilter = (name) => (value) =>
    setSearchParams(
      (params) => {
        if (value) params.set(name, value);
        else params.delete(name);
        return params;
      },
      { replace: true },
    );
  const validity = urlFilter('validity', VALIDITY_FILTERS);
  const filters = { status, category, validity, q };

  const list = useCursorList({
    queryKey: adminKeys.documents(filters),
    fetchPage: (cursor) => listDocuments({ ...filters, cursor }),
    // Keep statuses live while anything on screen is still being processed.
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) => page.results?.some(isInFlight)) ? 3000 : false,
  });

  const filtered = status || category || validity || q;

  // The selection belongs to one set of filters; changing a filter starts afresh.
  // `all` is set when every document matching the filter is selected.
  const filterKey = JSON.stringify(filters);
  const [selection, setSelection] = useState(() => ({ key: filterKey, ids: new Set(), all: null }));
  const current = selection.key === filterKey;
  const selectedIds = current ? selection.ids : NO_IDS;
  const allMatching = current ? selection.all : null;
  const setSelectedIds = (update) =>
    setSelection((previous) => ({ key: filterKey, ids: update(previous.key === filterKey ? previous.ids : NO_IDS), all: null }));
  const selectAllMatching = useMutation({
    mutationFn: () => listMatchingDocumentIds(filters),
    onSuccess: ({ ids, count, truncated }) => setSelection({ key: filterKey, ids: new Set(ids), all: { count, truncated } }),
    onError: (error) => toast.error('Couldn’t select all matching documents', { description: error.message }),
  });
  const loadedIds = list.rows.map((document) => document.id);
  const allSelected = loadedIds.length > 0 && loadedIds.every((id) => selectedIds.has(id));
  const someSelected = !allSelected && loadedIds.some((id) => selectedIds.has(id));

  const toggleOne = (id, checked) => {
    if (checked && selectedIds.size >= MAX_SELECTION) {
      toast(`You can select up to ${MAX_SELECTION} documents at a time.`);
      return;
    }
    const next = new Set(selectedIds);
    if (checked) next.add(id);
    else next.delete(id);
    setSelectedIds(() => next);
  };
  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(() => NO_IDS);
      return;
    }
    const next = new Set(selectedIds);
    for (const id of loadedIds) {
      if (next.size >= MAX_SELECTION) break;
      next.add(id);
    }
    if (loadedIds.some((id) => !next.has(id))) toast(`Selected the first ${MAX_SELECTION} documents.`);
    setSelectedIds(() => next);
  };
  const documentsLabel = (n) => `${n} document${n === 1 ? '' : 's'}`;

  const [pendingAction, setPendingAction] = useState(null);
  // Runs go in batches of 100 with visible progress; Stop ends them after the current batch.
  const [progress, setProgress] = useState(null);
  const stopRequested = useRef(false);
  const bulk = useMutation({
    mutationFn: ({ action, changes, changesById }) => {
      const ids = changesById ? Object.keys(changesById) : [...selectedIds];
      stopRequested.current = false;
      setProgress({ action, done: 0, total: ids.length, stopping: false });
      const send = (batch) => {
        const run = () =>
          bulkDocuments({
            action,
            ids: batch,
            changes,
            changesById: changesById ? Object.fromEntries(batch.map((id) => [id, changesById[id]])) : undefined,
          });
        return action === 'delete' ? withRecentAuth(run) : run();
      };
      return runInBatches(ids, send, {
        onProgress: (done, total) => setProgress((previous) => previous && { ...previous, done, total }),
        shouldStop: () => stopRequested.current,
      });
    },
    onSuccess: (result, { action }) => {
      const summary = bulkSummary(action, result);
      (summary.ok ? toast.success : toast.error)(summary.title, summary.description ? { description: summary.description } : undefined);
      // Failed (and, after Stop, unprocessed) documents stay selected to look at or retry.
      setSelectedIds(() => new Set([...result.failed.map((item) => item.id), ...result.skipped]));
      setPendingAction(null);
    },
    onError: (error) => {
      if (error.code !== 'request_cancelled') toast.error('The bulk action failed', { description: error.message });
    },
    onSettled: () => {
      setProgress(null);
      queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
  });
  const count = selectedIds.size;
  const startAction = (action) => (action === 'enable' || action === 'disable' ? bulk.mutate({ action }) : setPendingAction(action));

  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Documents"
        description="Everything ThaparGenie answers from."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus /> Add knowledge
          </Button>
        }
      />

      <SplitSection
        icon={Library}
        title="All documents"
        description="Search and filter the library. Tick rows for bulk actions, or open one to edit it and its passages."
        flush
      >
        <div className="grid grid-cols-2 gap-3 border-b p-4 sm:p-5 lg:grid-cols-4">
          <div className="relative col-span-2 lg:col-span-4">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <label htmlFor="document-search" className="sr-only">
              Search titles
            </label>
            <Input
              id="document-search"
              type="search"
              placeholder="Search titles"
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Select
            aria-label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            placeholder="All statuses"
            options={DOCUMENT_STATUSES}
          />
          <Select
            aria-label="Category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="All categories"
            options={CATEGORIES}
          />
          <Select
            aria-label="Valid until"
            value={validity}
            onChange={(event) => setUrlFilter('validity')(event.target.value)}
            placeholder="Any validity"
            options={VALIDITY_FILTERS}
          />
        </div>

        {list.isPending ? (
          <TableSkeleton />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.rows.length === 0 ? (
          <EmptyState
            icon={FileText}
            title={filtered ? 'No documents match' : 'The knowledge base is empty'}
            action={filtered ? null : <Button onClick={() => setAdding(true)}>Add the first document</Button>}
          >
            {filtered ? 'Try a different search or filter.' : 'Upload official PDFs, add web pages or write FAQs.'}
          </EmptyState>
        ) : (
          <>
            {allMatching ? (
              <p className="flex flex-wrap items-center justify-center gap-x-2 border-b bg-accent/40 px-4 py-2 text-sm" role="status">
                All {formatNumber(allMatching.count)} matching documents are selected
                {allMatching.truncated ? ` (the newest ${formatNumber(selectedIds.size)})` : ''}.
                <Button size="sm" variant="link" className="h-auto p-0" onClick={() => setSelectedIds(() => NO_IDS)}>
                  Clear selection
                </Button>
              </p>
            ) : allSelected && list.hasNextPage ? (
              <p className="flex flex-wrap items-center justify-center gap-x-2 border-b bg-muted/50 px-4 py-2 text-sm">
                All {formatNumber(selectedIds.size)} shown are selected.
                <Button
                  size="sm"
                  variant="link"
                  className="h-auto p-0"
                  disabled={selectAllMatching.isPending}
                  onClick={() => selectAllMatching.mutate()}
                >
                  {selectAllMatching.isPending ? 'Selecting…' : 'Select all matching this filter'}
                </Button>
              </p>
            ) : null}
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-10 pr-0">
                    <input
                      type="checkbox"
                      className="size-4 align-middle accent-primary"
                      aria-label="Select all shown documents"
                      checked={allSelected}
                      ref={(element) => {
                        if (element) element.indeterminate = someSelected;
                      }}
                      onChange={toggleAll}
                    />
                  </TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead className="hidden @2xl:table-cell">Category</TableHead>
                  <TableHead className="hidden @4xl:table-cell">Year</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden text-right @xl:table-cell">Passages</TableHead>
                  <TableHead className="hidden text-right @2xl:table-cell">Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.rows.map((document) => {
                  const Icon = document.source_type === 'url' ? Globe : FileText;
                  const documentValidity = validityOf(document);
                  return (
                    <TableRow
                      key={document.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/admin/documents/${document.id}`)}
                      data-state={selectedIds.has(document.id) ? 'selected' : undefined}
                    >
                      <TableCell className="w-10 pr-0" onClick={(event) => event.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="size-4 align-middle accent-primary"
                          aria-label={`Select ${document.title}`}
                          checked={selectedIds.has(document.id)}
                          onChange={(event) => toggleOne(document.id, event.target.checked)}
                        />
                      </TableCell>
                      <TableCell className="max-w-[22rem]">
                        <div className="flex items-start gap-2.5">
                          <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <div className="min-w-0">
                            {/* The link makes each row reachable by keyboard. */}
                            <a
                              href={`/admin/documents/${document.id}`}
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                navigate(`/admin/documents/${document.id}`);
                              }}
                              className="line-clamp-2 font-medium outline-none hover:underline focus-visible:underline"
                            >
                              {document.title}
                            </a>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {SOURCE_TYPES[document.source_type] || document.source_type}
                              {document.is_current ? '' : ' · Superseded'}
                            </p>
                            {documentValidity ? <ValidityTag validity={documentValidity} className="mt-1" /> : null}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground @2xl:table-cell">{labelOf(CATEGORIES, document.category)}</TableCell>
                      <TableCell className="hidden text-muted-foreground tabular-nums @4xl:table-cell">{document.academic_year || '—'}</TableCell>
                      <TableCell>
                        <StatusBadge status={document.status} />
                        {isInFlight(document) && document.status_detail ? (
                          <p className="mt-1 max-w-[12rem] truncate text-xs text-muted-foreground">{document.status_detail}</p>
                        ) : null}
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums @xl:table-cell">{formatNumber(document.chunk_count)}</TableCell>
                      <TableCell className="hidden text-right text-muted-foreground @2xl:table-cell">{formatRelative(document.updated_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <LoadMoreButton query={list} />
          </>
        )}
      </SplitSection>

      {count || progress ? (
        <BulkActionBar
          count={count}
          allMatching={Boolean(allMatching)}
          busy={bulk.isPending}
          progress={progress}
          onAction={startAction}
          onClear={() => setSelectedIds(() => NO_IDS)}
          onStop={() => {
            stopRequested.current = true;
            setProgress((previous) => previous && { ...previous, stopping: true });
          }}
        />
      ) : null}

      {adding ? <AddKnowledgeDialog open onOpenChange={setAdding} /> : null}
      {pendingAction === 'update' ? (
        <BulkEditDialog
          open
          count={count}
          pending={bulk.isPending}
          onOpenChange={(open) => !open && setPendingAction(null)}
          onSubmit={(changes) => bulk.mutate({ action: 'update', changes })}
        />
      ) : null}
      <ConfirmDialog
        open={pendingAction === 'reprocess' || pendingAction === 'delete'}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title={`${pendingAction === 'delete' ? 'Delete' : 'Reprocess'} ${documentsLabel(count)}?`}
        description={
          pendingAction === 'delete'
            ? 'Their passages and stored files are removed and answers stop citing them. This can’t be undone.'
            : 'Each document is extracted and embedded again, which uses AI calls. They stay answerable meanwhile.'
        }
        confirmLabel={pendingAction === 'delete' ? 'Delete' : 'Reprocess'}
        pending={bulk.isPending}
        onConfirm={() => bulk.mutate({ action: pendingAction })}
      />
    </div>
  );
}
