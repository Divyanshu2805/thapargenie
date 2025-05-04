import { useInfiniteQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, CircleDashed, Clock, Loader2, MinusCircle, XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cursorFrom } from '@/lib/pagination';
import { cn } from '@/lib/utils';

// Status is never colour alone: every badge has an icon and a label.
const TONES = {
  good: 'border-success/30 bg-success/10 text-foreground [&>svg]:text-success',
  warning: 'border-warning/30 bg-warning/10 text-foreground [&>svg]:text-warning',
  critical: 'border-destructive/30 bg-destructive/10 text-foreground [&>svg]:text-destructive',
  info: 'border-border bg-muted text-foreground [&>svg]:text-muted-foreground',
  brand: 'border-transparent bg-accent text-accent-foreground',
};

const STATUS = {
  ready: { tone: 'good', icon: CheckCircle2, label: 'Ready' },
  queued: { tone: 'info', icon: Clock, label: 'Queued' },
  processing: { tone: 'warning', icon: Loader2, label: 'Processing', spin: true },
  failed: { tone: 'critical', icon: XCircle, label: 'Failed' },
  disabled: { tone: 'info', icon: MinusCircle, label: 'Disabled' },
  open: { tone: 'warning', icon: CircleDashed, label: 'Open' },
  resolved: { tone: 'good', icon: CheckCircle2, label: 'Resolved' },
  dismissed: { tone: 'info', icon: MinusCircle, label: 'Dismissed' },
  approved: { tone: 'good', icon: CheckCircle2, label: 'Approved' },
  pending: { tone: 'warning', icon: Clock, label: 'Pending' },
  denied: { tone: 'critical', icon: XCircle, label: 'Denied' },
  suspended: { tone: 'critical', icon: AlertCircle, label: 'Suspended' },
  accepted: { tone: 'good', icon: CheckCircle2, label: 'Accepted' },
  expired: { tone: 'info', icon: Clock, label: 'Expired' },
  inactive: { tone: 'info', icon: MinusCircle, label: 'Revoked' },
  success: { tone: 'good', icon: CheckCircle2, label: 'Success' },
  failure: { tone: 'critical', icon: XCircle, label: 'Failure' },
  denied_outcome: { tone: 'critical', icon: XCircle, label: 'Denied' },
  // A document's "valid until" (constants.validityOf).
  valid_expiring: { tone: 'warning', icon: Clock, label: 'Expiring' },
  valid_expired: { tone: 'info', icon: Clock, label: 'Expired' },
};

/** "Expires 12 Oct 2026" / "Expired 3 Sept 2026" for a validityOf() result. */
export function ValidityTag({ validity, className }) {
  return <StatusBadge status={`valid_${validity.state}`} label={validity.label} className={className} />;
}

export function StatusBadge({ status, label, className }) {
  const spec = STATUS[status] || { tone: 'info', icon: CircleDashed, label: status };
  const Icon = spec.icon;
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&>svg]:size-3.5',
        TONES[spec.tone],
        className,
      )}
    >
      <Icon className={cn(spec.spin && 'animate-spin')} aria-hidden="true" />
      {label || spec.label}
    </span>
  );
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      {Icon ? (
        <span className="flex size-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
          <Icon className="size-5" aria-hidden="true" />
        </span>
      ) : null}
      <h2 className="mt-4 text-heading">{title}</h2>
      {children ? <p className="mt-1 max-w-sm text-sm text-muted-foreground">{children}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <AlertCircle className="size-6 text-destructive" aria-hidden="true" />
      <p className="text-sm">{error?.message || 'Something went wrong.'}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

export function TableSkeleton({ rows = 6 }) {
  return (
    <div className="space-y-3 p-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-9 w-full" />
      ))}
    </div>
  );
}

/** Cursor-paginated admin list. Returns the flattened rows plus TanStack's infinite-query state. */
export function useCursorList({ queryKey, fetchPage, refetchInterval }) {
  const query = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) => fetchPage(pageParam),
    initialPageParam: undefined,
    getNextPageParam: (page) => cursorFrom(page.next),
    refetchInterval,
  });
  const rows = query.data?.pages.flatMap((page) => page.results || []) ?? [];
  return { ...query, rows };
}

export function LoadMoreButton({ query }) {
  if (!query.hasNextPage) return null;
  return (
    <div className="flex justify-center border-t p-3">
      <Button variant="ghost" size="sm" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
        {query.isFetchingNextPage ? 'Loading…' : 'Load more'}
      </Button>
    </div>
  );
}
