import { ChevronRight, ClipboardList, ScrollText } from 'lucide-react';
import { Fragment, useState } from 'react';

import { PageHeader } from '@/components/layout/PageHeader';
import { SplitSection } from '@/components/split-section';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import { adminKeys, listAuditLog } from '@/lib/api/admin';
import { formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';

// Action prefixes the API filters on (a trailing "." matches the whole family).
const ACTION_FILTERS = [
  { value: 'document.', label: 'Documents' },
  { value: 'chunk.', label: 'Passages' },
  { value: 'settings.', label: 'Settings' },
  { value: 'feedback.', label: 'Feedback' },
  { value: 'eligibility.', label: 'Access changes' },
  { value: 'staff.', label: 'Staff access' },
  { value: 'identity.', label: 'Identity & invitations' },
  { value: 'retention.', label: 'Retention purges' },
  { value: 'access.', label: 'Denied access' },
  { value: 'privacy.', label: 'Student exports & deletions' },
  { value: 'playground.', label: 'Playground runs' },
];

export function describeAction(action) {
  return (action || '')
    .split('.')
    .map((part) => part.replace(/_/g, ' '))
    .join(' · ');
}

export function actorLabel(event) {
  if (event.actor_email) return event.actor_email;
  if (event.actor_kind === 'user') return 'Deleted account';
  if (event.actor_kind === 'service') return 'System';
  return event.actor_kind || '—';
}

// api/models.py AuditOutcome.
const OUTCOME_STATUS = { succeeded: 'success', failed: 'failure', denied: 'denied_outcome' };

export default function AuditLogPage() {
  const [action, setAction] = useState('');
  const [open, setOpen] = useState(null);
  const filters = { action };
  const list = useCursorList({ queryKey: adminKeys.auditLog(filters), fetchPage: (cursor) => listAuditLog({ ...filters, cursor }) });

  return (
    <div className="page-wide space-y-6">
      <PageHeader title="Audit log" description="Every admin change and sign-in event, newest first. Kept for one year." />
      <SplitSection
        icon={ScrollText}
        title="Events"
        description="Filter by type. Expand a row to see exactly what changed."
        flush
      >
        <div className="flex border-b p-4">
          <Select
            aria-label="Event type"
            className="w-full sm:w-56"
            value={action}
            onChange={(event) => setAction(event.target.value)}
            placeholder="All events"
            options={ACTION_FILTERS}
          />
        </div>
        {list.isPending ? (
          <TableSkeleton />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.rows.length === 0 ? (
          <EmptyState icon={ClipboardList} title="No events">
            {action ? 'Nothing of this type yet.' : 'Administrative actions will be recorded here.'}
          </EmptyState>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-8">
                    <span className="sr-only">Details</span>
                  </TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead className="hidden @2xl:table-cell">By</TableHead>
                  <TableHead className="hidden @4xl:table-cell">Resource</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.rows.map((event) => {
                  const expanded = open === event.id;
                  const hasMetadata = event.metadata && Object.keys(event.metadata).length > 0;
                  return (
                    <Fragment key={event.id}>
                      <TableRow>
                        <TableCell>
                          {hasMetadata ? (
                            <button
                              type="button"
                              aria-expanded={expanded}
                              aria-label={expanded ? 'Hide details' : 'Show details'}
                              onClick={() => setOpen(expanded ? null : event.id)}
                              className="rounded p-0.5 text-muted-foreground outline-none hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                            >
                              <ChevronRight className={cn('size-4 transition-transform', expanded && 'rotate-90')} />
                            </button>
                          ) : null}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-muted-foreground tabular-nums">{formatDateTime(event.created_at)}</TableCell>
                        <TableCell className="font-medium capitalize">{describeAction(event.action)}</TableCell>
                        <TableCell className="hidden max-w-[14rem] truncate text-muted-foreground @2xl:table-cell">
                          {actorLabel(event)}
                        </TableCell>
                        <TableCell className="hidden max-w-[14rem] truncate text-xs text-muted-foreground @4xl:table-cell">
                          {event.resource_type ? `${event.resource_type} ${String(event.resource_id || '').slice(0, 8)}` : '—'}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={OUTCOME_STATUS[event.outcome] || event.outcome} />
                        </TableCell>
                      </TableRow>
                      {expanded ? (
                        <TableRow className="bg-muted/30 hover:bg-hover">
                          <TableCell />
                          <TableCell colSpan={5}>
                            <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs leading-relaxed">
                              {JSON.stringify(event.metadata, null, 2)}
                            </pre>
                            {event.request_id ? <p className="mt-2 text-xs text-muted-foreground">Request {event.request_id}</p> : null}
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
            <LoadMoreButton query={list} />
          </>
        )}
      </SplitSection>
    </div>
  );
}
