import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Mail, MessageSquareHeart, RotateCcw, Star, X } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import { SITE_FEEDBACK_KINDS, kindLabel } from '@/features/feedback/kinds';
import { adminKeys, listSiteFeedback, updateSiteFeedback } from '@/lib/api/admin';
import { formatRelative } from '@/lib/format';

function SiteFeedbackCard({ item, onReview, pending }) {
  const [note, setNote] = useState(item.admin_note);
  return (
    <li className="p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="brand">{kindLabel(item.kind)}</Badge>
        {item.rating ? (
          <span className="inline-flex items-center gap-0.5 font-medium text-foreground" aria-label={`Rated ${item.rating} of 5`}>
            <Star className="size-3.5 fill-gold text-gold" aria-hidden="true" /> {item.rating}/5
          </span>
        ) : null}
        <StatusBadge status={item.review_status} />
        <span>·</span>
        {item.contact_email ? (
          <a className="inline-flex items-center gap-1 font-medium text-foreground underline-offset-4 hover:underline" href={`mailto:${item.contact_email}`}>
            <Mail className="size-3.5" aria-hidden="true" /> {item.contact_email}
          </a>
        ) : (
          <span title="A stable pseudonym; the student’s identity is never shown">Student {item.reporter.slice(0, 6)}</span>
        )}
        <span>·</span>
        <span>{formatRelative(item.created_at)}</span>
        {item.page ? (
          <>
            <span>·</span>
            <span title="Where the student was before opening the feedback page">from {item.page}</span>
          </>
        ) : null}
      </div>

      <p className="mt-3 text-[15px] leading-relaxed break-words whitespace-pre-line">{item.message}</p>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div>
          <label htmlFor={`site-note-${item.id}`} className="text-xs font-medium text-muted-foreground">
            Note for the team
          </label>
          <Textarea
            id={`site-note-${item.id}`}
            className="mt-1 min-h-10"
            rows={1}
            maxLength={1000}
            value={note}
            placeholder="What was done about it"
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {item.review_status === 'open' ? (
            <>
              <Button variant="outline" size="sm" disabled={pending} onClick={() => onReview(item, { review_status: 'dismissed', admin_note: note })}>
                <X /> Dismiss
              </Button>
              <Button size="sm" disabled={pending} onClick={() => onReview(item, { review_status: 'resolved', admin_note: note })}>
                <Check /> Resolve
              </Button>
            </>
          ) : (
            <>
              {note !== item.admin_note ? (
                <Button size="sm" variant="outline" disabled={pending} onClick={() => onReview(item, { admin_note: note })}>
                  Save note
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" disabled={pending} onClick={() => onReview(item, { review_status: 'open' })}>
                <RotateCcw /> Reopen
              </Button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

/** Feedback and suggestions students sent about the site. */
export default function SiteFeedbackSection() {
  const queryClient = useQueryClient();
  const [reviewStatus, setReviewStatus] = useState('open');
  const [kind, setKind] = useState('');
  const filters = { reviewStatus: reviewStatus === 'all' ? '' : reviewStatus, kind };

  const list = useCursorList({
    queryKey: adminKeys.siteFeedback(filters),
    fetchPage: (cursor) => listSiteFeedback({ ...filters, cursor }),
  });

  const review = useMutation({
    mutationFn: ({ id, changes }) => updateSiteFeedback(id, changes),
    onSuccess: (_updated, { changes }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'site-feedback'] });
      toast.success(changes.review_status ? `Marked ${changes.review_status}` : 'Note saved');
    },
    onError: (error) => toast.error('Couldn’t update the feedback', { description: error.message }),
  });

  return (
    <SplitSection
      icon={MessageSquareHeart}
      title="Site feedback"
      description="Ideas and problems students sent from the Feedback page. Anonymous unless they asked to be contacted."
      flush
    >
      <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={reviewStatus} onValueChange={setReviewStatus}>
          <TabsList aria-label="Review status">
            <TabsTrigger value="open">Open</TabsTrigger>
            <TabsTrigger value="resolved">Resolved</TabsTrigger>
            <TabsTrigger value="dismissed">Dismissed</TabsTrigger>
            <TabsTrigger value="all">All</TabsTrigger>
          </TabsList>
        </Tabs>
        <Select
          aria-label="Kind"
          className="w-full sm:w-52"
          value={kind}
          onChange={(event) => setKind(event.target.value)}
          placeholder="Any kind"
          options={SITE_FEEDBACK_KINDS.map(({ value, label }) => ({ value, label }))}
        />
      </div>

      {list.isPending ? (
        <TableSkeleton rows={3} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => list.refetch()} />
      ) : list.rows.length === 0 ? (
        <EmptyState icon={MessageSquareHeart} title={reviewStatus === 'open' ? 'Nothing new' : 'No feedback here'}>
          {reviewStatus === 'open' ? 'New suggestions and problem reports will appear here.' : 'Try another filter.'}
        </EmptyState>
      ) : (
        <>
          <ul className="divide-y">
            {list.rows.map((item) => (
              <SiteFeedbackCard
                key={item.id}
                item={item}
                pending={review.isPending && review.variables?.id === item.id}
                onReview={(target, changes) => review.mutate({ id: target.id, changes })}
              />
            ))}
          </ul>
          <LoadMoreButton query={list} />
        </>
      )}
    </SplitSection>
  );
}
