import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BookPlus,
  Check,
  ChevronDown,
  MessageSquareWarning,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/PageHeader';
import ExportCsvButton from '@/features/admin/ExportCsvButton';
import { SplitSection } from '@/components/split-section';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import AddKnowledgeDialog from '@/features/admin/AddKnowledgeDialog';
import SiteFeedbackSection from '@/features/admin/SiteFeedbackSection';
import { EmptyState, ErrorState, LoadMoreButton, StatusBadge, TableSkeleton, useCursorList } from '@/features/admin/components';
import { ANSWER_TYPES, FEEDBACK_REASONS } from '@/features/admin/constants';
import Markdown from '@/features/chat/Markdown';
import { adminKeys, exportFeedbackCsv, listFeedback, updateFeedback } from '@/lib/api/admin';
import { formatMs, formatRelative } from '@/lib/format';
import { cn } from '@/lib/utils';

/** Prefill for an FAQ that answers a question students asked. */
export function faqDraft(question) {
  const text = (question || '').trim();
  return { tab: 'text', title: text.slice(0, 300), text: `Q: ${text}\nA: `, meta: { category: 'faq' } };
}

function FeedbackCard({ item, onReview, onCreateFaq, pending }) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState(item.admin_note);
  const answer = item.answer;
  const cited = answer.sources.filter((source) => source.cited);

  return (
    <li className="p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {item.rating === -1 ? (
          <span className="inline-flex items-center gap-1 font-medium text-destructive">
            <ThumbsDown className="size-3.5" aria-hidden="true" /> Unhelpful
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 font-medium text-success">
            <ThumbsUp className="size-3.5" aria-hidden="true" /> Helpful
          </span>
        )}
        {item.reason ? <Badge variant="secondary">{FEEDBACK_REASONS[item.reason] || item.reason}</Badge> : null}
        <StatusBadge status={item.review_status} />
        <span>·</span>
        <span title="A stable pseudonym; the student’s identity is never shown">Student {item.reporter.slice(0, 6)}</span>
        <span>·</span>
        <span>{formatRelative(item.created_at)}</span>
      </div>

      <p className="mt-3 text-[15px] font-medium">{item.question || <span className="text-muted-foreground">(question unavailable)</span>}</p>
      {item.comment ? (
        <blockquote className="mt-2 border-l-2 border-primary/40 pl-3 text-sm text-muted-foreground italic">“{item.comment}”</blockquote>
      ) : null}

      <div className="mt-3 rounded-lg border bg-muted/30">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <ChevronDown className={cn('size-3.5 transition-transform', expanded && 'rotate-180')} aria-hidden="true" />
          Answer · {ANSWER_TYPES[answer.answer_type] || answer.answer_type || 'unknown'}
          {answer.grounded === false ? ' · not grounded' : ''} · {cited.length} cited source{cited.length === 1 ? '' : 's'}
          {answer.latency_ms ? ` · ${formatMs(answer.latency_ms)}` : ''}
        </button>
        {expanded ? (
          <div className="border-t px-4 py-3">
            <Markdown content={answer.content || '_Empty answer._'} />
            {answer.sources.length ? (
              <ol className="mt-3 space-y-1 border-t pt-3 text-xs text-muted-foreground">
                {answer.sources.map((source) => (
                  <li key={source.position}>
                    [{source.position}] {source.title}
                    {source.heading_path ? ` · ${source.heading_path}` : ''}
                    {source.score !== null ? ` · score ${source.score.toFixed(3)}` : ''}
                    {source.cited ? ' · cited' : ''}
                  </li>
                ))}
              </ol>
            ) : null}
            {item.trace?.standalone_query ? (
              <p className="mt-2 text-xs text-muted-foreground">Searched as: “{item.trace.standalone_query}”</p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div>
          <label htmlFor={`note-${item.id}`} className="text-xs font-medium text-muted-foreground">
            Note for the team
          </label>
          <Textarea
            id={`note-${item.id}`}
            className="mt-1 min-h-10"
            rows={1}
            maxLength={1000}
            value={note}
            placeholder="What was wrong, what was fixed"
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => onCreateFaq(item)}>
            <BookPlus /> Create FAQ
          </Button>
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

export default function FeedbackPage() {
  const queryClient = useQueryClient();
  const [reviewStatus, setReviewStatus] = useState('open');
  const [rating, setRating] = useState('-1');
  const [reason, setReason] = useState('');
  const [faqFor, setFaqFor] = useState(null);
  const filters = { reviewStatus: reviewStatus === 'all' ? '' : reviewStatus, rating, reason };

  const list = useCursorList({
    queryKey: adminKeys.feedback(filters),
    fetchPage: (cursor) => listFeedback({ ...filters, cursor }),
  });

  const review = useMutation({
    mutationFn: ({ id, changes }) => updateFeedback(id, changes),
    onSuccess: (_updated, { changes }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'feedback'] });
      queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] });
      if (changes.review_status) toast.success(`Marked ${changes.review_status}`);
      else toast.success('Note saved');
    },
    onError: (error) => toast.error('Couldn’t update the feedback', { description: error.message }),
  });

  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Feedback"
        description="Rated answers and site feedback, without student identities."
        actions={<ExportCsvButton request={() => exportFeedbackCsv(filters)} fallbackName="thapargenie-feedback.csv" label="Export rated answers" />}
      />

      <SplitSection
        icon={MessageSquareWarning}
        title="Review queue"
        description="Answers students rated. Fix a gap with an FAQ, then resolve the item."
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
          <div className="flex gap-3">
            <Select
              aria-label="Rating"
              className="w-36"
              value={rating}
              onChange={(event) => setRating(event.target.value)}
              placeholder="Any rating"
              options={[
                { value: '-1', label: 'Unhelpful' },
                { value: '1', label: 'Helpful' },
              ]}
            />
            <Select
              aria-label="Reason"
              className="w-44"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Any reason"
              options={Object.entries(FEEDBACK_REASONS).map(([value, label]) => ({ value, label }))}
            />
          </div>
        </div>

        {list.isPending ? (
          <TableSkeleton rows={4} />
        ) : list.isError ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.rows.length === 0 ? (
          <EmptyState icon={MessageSquareWarning} title={reviewStatus === 'open' ? 'Nothing to review' : 'No feedback here'}>
            {reviewStatus === 'open' ? 'New thumbs-down answers will appear here.' : 'Try another filter.'}
          </EmptyState>
        ) : (
          <>
            <ul className="divide-y">
              {list.rows.map((item) => (
                <FeedbackCard
                  key={item.id}
                  item={item}
                  pending={review.isPending && review.variables?.id === item.id}
                  onReview={(target, changes) => review.mutate({ id: target.id, changes })}
                  onCreateFaq={setFaqFor}
                />
              ))}
            </ul>
            <LoadMoreButton query={list} />
          </>
        )}
      </SplitSection>

      <SiteFeedbackSection />

      {faqFor ? (
        <AddKnowledgeDialog
          open
          initial={faqDraft(faqFor.question)}
          onOpenChange={(open) => !open && setFaqFor(null)}
          onCreated={() => {
            if (faqFor.review_status === 'open') {
              review.mutate({
                id: faqFor.id,
                changes: { review_status: 'resolved', admin_note: faqFor.admin_note || 'Answered with a new FAQ entry.' },
              });
            }
          }}
        />
      ) : null}
    </div>
  );
}
