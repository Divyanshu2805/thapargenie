import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Archive,
  Bot,
  EllipsisVertical,
  Megaphone,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Send,
  Trash2,
} from 'lucide-react';
import { useDeferredValue, useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/PageHeader';
import { useRecentAuth } from '@/components/recent-auth';
import { SectionToggle, SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import { CATEGORIES, labelOf } from '@/features/admin/constants';
import NoticeDialog from '@/features/admin/NoticeDialog';
import { adminKeys, deleteNotice, listAdminNotices, updateNotice } from '@/lib/api/admin';
import { formatDateTime, formatRelative } from '@/lib/format';

const STATES = [
  { value: 'published', label: 'Published', empty: 'Nothing published right now.' },
  { value: 'scheduled', label: 'Scheduled', empty: 'Nothing scheduled.' },
  { value: 'draft', label: 'Drafts', empty: 'No drafts.' },
  { value: 'expired', label: 'Expired', empty: 'No expired notices.' },
];

/** The date line for a row, by state. */
export function noticeWhen(notice) {
  switch (notice.state) {
    case 'scheduled':
      return `Publishes ${formatDateTime(notice.publish_at)}`;
    case 'draft':
      return `Edited ${formatRelative(notice.updated_at)}`;
    case 'expired':
      return `Expired ${formatRelative(notice.expires_at)}`;
    default:
      return notice.expires_at
        ? `Published ${formatRelative(notice.publish_at)} · until ${formatDateTime(notice.expires_at)}`
        : `Published ${formatRelative(notice.publish_at)}`;
  }
}

function AnswerStatus({ notice }) {
  if (!notice.answerable) return null;
  if (!notice.document) {
    return notice.state === 'published' ? <StatusBadge status="queued" label="Adding to answers" /> : null;
  }
  const { status, is_current: current } = notice.document;
  if (status === 'ready') return <StatusBadge status="ready" label={current ? 'In answers' : 'In answers (not current)'} />;
  return <StatusBadge status={status} />;
}

function NoticeRow({ notice, onEdit, onChange, onDelete, pending }) {
  const published = notice.state === 'published' || notice.state === 'scheduled';
  return (
    <li className="flex items-start gap-3 px-5 py-4 sm:px-6">
      <button type="button" onClick={() => onEdit(notice)} className="min-w-0 flex-1 rounded-lg text-left outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
        <span className="flex flex-wrap items-center gap-2">
          {notice.is_pinned ? <Pin className="size-3.5 text-gold" aria-label="Pinned" /> : null}
          <span className="font-medium break-words">{notice.title}</span>
          {notice.importance === 'important' ? (
            <Badge variant="destructive">
              <AlertTriangle aria-hidden="true" /> Important
            </Badge>
          ) : null}
        </span>
        <span className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="brand">{labelOf(CATEGORIES, notice.category)}</Badge>
          <span>{noticeWhen(notice)}</span>
          {notice.updated_by ? <span>· by {notice.updated_by}</span> : null}
          <AnswerStatus notice={notice} />
        </span>
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Actions for ${notice.title}`} disabled={pending}>
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onSelect={() => onEdit(notice)}>
            <Pencil /> Edit
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onChange(notice, { is_pinned: !notice.is_pinned }, notice.is_pinned ? 'Unpinned' : 'Pinned')}>
            {notice.is_pinned ? (
              <>
                <PinOff /> Unpin
              </>
            ) : (
              <>
                <Pin /> Pin
              </>
            )}
          </DropdownMenuItem>
          {published ? (
            <DropdownMenuItem onSelect={() => onChange(notice, { is_draft: true }, 'Moved to drafts')}>
              <Archive /> Unpublish
            </DropdownMenuItem>
          ) : notice.state === 'draft' ? (
            <DropdownMenuItem onSelect={() => onChange(notice, { is_draft: false }, 'Notice published')}>
              <Send /> Publish
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => onDelete(notice)}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}

function DeleteNoticeDialog({ notice, onOpenChange }) {
  const queryClient = useQueryClient();
  const withRecentAuth = useRecentAuth();
  const [withDocument, setWithDocument] = useState(false);
  const remove = useMutation({
    mutationFn: () => withRecentAuth(() => deleteNotice(notice.id, { deleteDocument: withDocument })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'notices'] });
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      queryClient.invalidateQueries({ queryKey: ['app-config'] });
      toast.success('Notice deleted');
      onOpenChange(false);
    },
    onError: (error) => toast.error('Couldn’t delete the notice', { description: error.message }),
  });
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete this notice?</DialogTitle>
          <DialogDescription>“{notice.title}” disappears from the Notices page for everyone. This can’t be undone.</DialogDescription>
        </DialogHeader>
        {notice.document ? (
          <div className="-mx-2 overflow-hidden rounded-xl border">
            <SectionToggle
              id="notice-delete-document"
              title="Also remove it from answers"
              description="Deletes its knowledge-base copy. Otherwise the copy stays, marked not current."
              checked={withDocument}
              onChange={setWithDocument}
            />
          </div>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {remove.isPending ? 'Deleting…' : 'Delete notice'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function NoticesAdminPage() {
  const queryClient = useQueryClient();
  const [state, setState] = useState('published');
  const [search, setSearch] = useState('');
  const q = useDeferredValue(search.trim());
  const [editing, setEditing] = useState(null); // null, 'new' or a notice
  const [deleting, setDeleting] = useState(null);
  const filters = { state, q };

  const list = useCursorList({
    queryKey: adminKeys.notices(filters),
    fetchPage: (cursor) => listAdminNotices({ ...filters, cursor }),
  });

  const change = useMutation({
    mutationFn: ({ notice, changes }) => updateNotice(notice.id, changes),
    onSuccess: (_saved, { message }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'notices'] });
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      queryClient.invalidateQueries({ queryKey: ['app-config'] });
      toast.success(message);
    },
    onError: (error) => toast.error('Couldn’t update the notice', { description: error.message }),
  });

  const emptyText = STATES.find((item) => item.value === state)?.empty;

  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Notices"
        description="Announcements students see on their Notices page. Answerable ones are also added to the knowledge base."
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus /> New notice
          </Button>
        }
      />
      <div>
        <SplitSection
          icon={Megaphone}
          title="All notices"
          description="Scheduled notices publish on their own; expired ones leave the students’ list but stay here."
          flush
        >
          <div className="flex flex-col gap-3 border-b p-4 sm:p-5 lg:flex-row lg:items-center lg:justify-between">
            <Tabs value={state} onValueChange={setState}>
              <TabsList aria-label="Notice state">
                {STATES.map((item) => (
                  <TabsTrigger key={item.value} value={item.value}>
                    {item.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <div className="relative lg:w-72">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <label htmlFor="notice-search" className="sr-only">
                Search notices
              </label>
              <Input id="notice-search" type="search" placeholder="Search notices" className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} />
            </div>
          </div>

          {list.isPending ? (
            <TableSkeleton rows={4} />
          ) : list.isError ? (
            <ErrorState error={list.error} onRetry={() => list.refetch()} />
          ) : list.rows.length === 0 ? (
            <EmptyState
              icon={q ? Search : Bot}
              title={q ? 'No matches' : emptyText}
              action={
                !q && state !== 'expired' ? (
                  <Button variant="outline" size="sm" onClick={() => setEditing('new')}>
                    <Plus /> New notice
                  </Button>
                ) : null
              }
            >
              {q ? 'Try other words, or another tab.' : 'Post deadlines, exam dates and new rules here.'}
            </EmptyState>
          ) : (
            <>
              <ul className="divide-y">
                {list.rows.map((notice) => (
                  <NoticeRow
                    key={notice.id}
                    notice={notice}
                    pending={change.isPending && change.variables?.notice.id === notice.id}
                    onEdit={setEditing}
                    onDelete={setDeleting}
                    onChange={(target, changes, message) => change.mutate({ notice: target, changes, message })}
                  />
                ))}
              </ul>
              <LoadMoreButton query={list} />
            </>
          )}
        </SplitSection>
      </div>

      <NoticeDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        notice={editing && editing !== 'new' ? editing : null}
      />
      {deleting ? <DeleteNoticeDialog notice={deleting} onOpenChange={(open) => !open && setDeleting(null)} /> : null}
    </div>
  );
}
