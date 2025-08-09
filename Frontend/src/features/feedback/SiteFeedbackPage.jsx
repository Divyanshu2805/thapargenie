import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CircleDashed, History, MessageSquareHeart, MinusCircle, Send, Star } from 'lucide-react';
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';

import { PageHeader } from '@/components/layout/PageHeader';
import { SectionFields, SectionToggle, SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { MAX_MESSAGE, MIN_MESSAGE, SITE_FEEDBACK_KINDS, kindLabel } from '@/features/feedback/kinds';
import { chatKeys, listSiteFeedback, sendSiteFeedback } from '@/lib/api/chat';
import { formatRelative } from '@/lib/format';
import { cn } from '@/lib/utils';

// How the team's review reads to the student who sent it.
const STATUS = {
  open: { label: 'Received', icon: CircleDashed, className: 'border-warning/30 bg-warning/10 text-foreground' },
  resolved: { label: 'Resolved', icon: CheckCircle2, className: 'border-success/30 bg-success/10 text-foreground' },
  dismissed: { label: 'Closed', icon: MinusCircle, className: 'border-border bg-muted text-muted-foreground' },
};

const RATING_WORDS = ['', 'Poor', 'Could be better', 'Okay', 'Good', 'Excellent'];

/** Only the section the student came from (`/chat/`), never a conversation id. */
function sectionOf(path) {
  const first = typeof path === 'string' ? path.split('/').filter(Boolean)[0] : '';
  return first && /^[\w-]+$/.test(first) ? `/${first}/` : '';
}

function KindPicker({ value, onChange }) {
  return (
    <div role="radiogroup" aria-label="What is it about?" className="grid gap-2 sm:grid-cols-2">
      {SITE_FEEDBACK_KINDS.map(({ value: kind, label, hint, icon: Icon }) => {
        const selected = value === kind;
        return (
          <button
            key={kind}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(kind)}
            className={cn(
              'flex items-start gap-3 rounded-xl border p-3 text-left transition-colors duration-150 outline-none hover:border-primary/40 hover:bg-hover focus-visible:ring-[3px] focus-visible:ring-ring/30',
              selected && 'border-primary bg-accent hover:bg-accent',
            )}
          >
            <span
              className={cn(
                'flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground transition-colors',
                selected && 'bg-primary text-primary-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className={cn('block text-sm font-medium', selected && 'text-accent-foreground')}>{label}</span>
              <span className="block text-xs text-muted-foreground">{hint}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function RatingPicker({ value, onChange }) {
  const [hovered, setHovered] = useState(0);
  const shown = hovered || value || 0;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div role="radiogroup" aria-label="Rating" className="flex" onMouseLeave={() => setHovered(0)}>
        {[1, 2, 3, 4, 5].map((stars) => (
          <button
            key={stars}
            type="button"
            role="radio"
            aria-checked={value === stars}
            aria-label={`${stars} of 5: ${RATING_WORDS[stars]}`}
            onMouseEnter={() => setHovered(stars)}
            onClick={() => onChange(value === stars ? null : stars)}
            className="rounded-md p-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <Star
              className={cn(
                'size-6 transition-colors duration-150',
                stars <= shown ? 'fill-gold text-gold' : 'text-muted-foreground/60',
              )}
              aria-hidden="true"
            />
          </button>
        ))}
      </div>
      <span className="text-sm text-muted-foreground" aria-live="polite">
        {shown ? RATING_WORDS[shown] : 'Optional'}
      </span>
    </div>
  );
}

function ShareFeedback() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const [kind, setKind] = useState('suggestion');
  const [rating, setRating] = useState(null);
  const [message, setMessage] = useState('');
  const [contactOk, setContactOk] = useState(false);
  const [error, setError] = useState('');
  const trimmed = message.trim();

  const send = useMutation({
    mutationFn: () =>
      sendSiteFeedback({ kind, rating, message: trimmed, page: sectionOf(location.state?.from), contactOk }),
    onSuccess: () => {
      toast.success('Thanks! Your feedback reached the team.');
      setMessage('');
      setRating(null);
      setContactOk(false);
      queryClient.invalidateQueries({ queryKey: chatKeys.siteFeedback });
    },
    onError: (failure) => toast.error('Couldn’t send your feedback', { description: failure.message }),
  });

  const submit = (event) => {
    event.preventDefault();
    if (trimmed.length < MIN_MESSAGE) {
      setError(`Write at least ${MIN_MESSAGE} characters so the team can act on it.`);
      return;
    }
    setError('');
    send.mutate();
  };

  return (
    <SplitSection
      icon={MessageSquareHeart}
      title="Share feedback"
      description="Ideas, problems or answers that missed the mark. The team reads every one."
    >
      <form onSubmit={submit}>
        <SectionFields>
          <div className="grid content-start gap-2">
            <span className="text-sm font-medium">What is it about?</span>
            <KindPicker value={kind} onChange={setKind} />
          </div>
          <div className="grid content-start gap-2">
            <span className="text-sm font-medium">How is ThaparGenie working for you?</span>
            <RatingPicker value={rating} onChange={setRating} />
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="site-feedback-message">Your feedback</Label>
            <Textarea
              id="site-feedback-message"
              className="min-h-32"
              maxLength={MAX_MESSAGE}
              placeholder="Tell us what happened or what you’d like to see. Please don’t include passwords or personal details."
              value={message}
              onChange={(event) => {
                setMessage(event.target.value);
                if (error) setError('');
              }}
              aria-invalid={Boolean(error)}
              aria-describedby="site-feedback-hint"
            />
            <div id="site-feedback-hint" className="flex justify-between gap-3 text-xs">
              <span className={error ? 'text-destructive' : 'text-muted-foreground'}>
                {error || `At least ${MIN_MESSAGE} characters.`}
              </span>
              <span className="text-muted-foreground tabular-nums">
                {message.length} / {MAX_MESSAGE}
              </span>
            </div>
          </div>
        </SectionFields>
        <SectionToggle
          id="site-feedback-contact"
          title="You can contact me about this"
          description="Shares your email with the team for this message only. Otherwise it stays anonymous."
          checked={contactOk}
          onChange={setContactOk}
        />
        <div className="flex justify-end border-t px-5 py-4 sm:px-6">
          <Button type="submit" disabled={send.isPending || !trimmed}>
            <Send /> {send.isPending ? 'Sending…' : 'Send feedback'}
          </Button>
        </div>
      </form>
    </SplitSection>
  );
}

function YourFeedback() {
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: chatKeys.siteFeedback,
    queryFn: ({ signal }) => listSiteFeedback({ signal }),
  });
  const items = data?.results || [];

  return (
    <SplitSection icon={History} title="Your feedback" description="What you sent recently and where it stands.">
      {isPending ? (
        <div className="space-y-3 p-5 sm:p-6" aria-busy="true">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ) : isError ? (
        <div className="flex items-center justify-between gap-3 p-5 text-sm text-muted-foreground sm:p-6">
          Couldn’t load your feedback.
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="p-5 text-sm text-muted-foreground sm:p-6">Nothing yet. What you send will show up here.</p>
      ) : (
        <ul className="divide-y">
          {items.map((item) => {
            const status = STATUS[item.review_status] || STATUS.open;
            const StatusIcon = status.icon;
            return (
              <li key={item.id} className="px-5 py-4 sm:px-6">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{kindLabel(item.kind)}</span>
                  {item.rating ? (
                    <span className="inline-flex items-center gap-0.5" aria-label={`${item.rating} of 5`}>
                      <Star className="size-3 fill-gold text-gold" aria-hidden="true" /> {item.rating}
                    </span>
                  ) : null}
                  <span>·</span>
                  <span>{formatRelative(item.created_at)}</span>
                  <span
                    className={cn(
                      'ml-auto inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium',
                      status.className,
                    )}
                  >
                    <StatusIcon className="size-3.5" aria-hidden="true" /> {status.label}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed break-words whitespace-pre-line">{item.message}</p>
              </li>
            );
          })}
        </ul>
      )}
    </SplitSection>
  );
}

export default function SiteFeedbackPage() {
  return (
    <div className="page-wide space-y-6">
      <PageHeader title="Feedback" description="Help shape ThaparGenie: tell us what works, what doesn’t and what’s missing." />
      <div>
        <ShareFeedback />
        <YourFeedback />
      </div>
    </div>
  );
}
