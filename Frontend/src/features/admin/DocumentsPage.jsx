import { FileText, Globe, Library, Plus, Search } from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import AddKnowledgeDialog from '@/features/admin/AddKnowledgeDialog';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import {
  CATEGORIES,
  DOCUMENT_STATUSES,
  SOURCE_TYPES,
  isInFlight,
  labelOf,
} from '@/features/admin/constants';
import { adminKeys, listDocuments } from '@/lib/api/admin';
import { formatNumber, formatRelative } from '@/lib/format';

export default function DocumentsPage() {
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const q = useDeferredValue(search.trim());
  const filters = { status, category, q };

  const list = useCursorList({
    queryKey: adminKeys.documents(filters),
    fetchPage: (cursor) => listDocuments({ ...filters, cursor }),
    // Keep statuses live while anything on screen is still being processed.
    refetchInterval: (query) =>
      query.state.data?.pages.some((page) => page.results?.some(isInFlight)) ? 3000 : false,
  });

  const filtered = status || category || q;

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
        description="Search and filter the library, or open a document to edit it."
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
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
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
                  return (
                    <TableRow
                      key={document.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/admin/documents/${document.id}`)}
                    >
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

      {adding ? <AddKnowledgeDialog open onOpenChange={setAdding} /> : null}
    </div>
  );
}
