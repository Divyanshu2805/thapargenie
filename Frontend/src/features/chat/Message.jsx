import {
  AlertTriangle,
  CalendarClock,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  History,
  Lightbulb,
  Pencil,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Square,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { LogoMark } from '@/components/brand/Brand';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import FeedbackDialog from '@/features/chat/FeedbackDialog';
import { describeFreshness } from '@/features/chat/freshness';
import Markdown from '@/features/chat/Markdown';
import { CitationChip, SourceList } from '@/features/chat/sources';
import { ThinkingIndicator } from '@/features/chat/thinking';
import { useSmoothText } from '@/features/chat/use-smooth-text';
import { cn } from '@/lib/utils';

function IconAction({ label, onClick, disabled, active, children }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
          aria-pressed={active === undefined ? undefined : active}
          className={cn(
            'icon-nudge flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors outline-none hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-4',
            active && 'text-primary dark:text-accent-foreground',
          )}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function CopyAction({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Couldn’t copy to the clipboard');
    }
  };
  return (
    <IconAction label={copied ? 'Copied' : 'Copy'} onClick={copy}>
      {copied ? <Check /> : <Copy />}
    </IconAction>
  );
}

export function BranchSwitcher({ siblings, onSwitch, disabled }) {
  if (!siblings || siblings.count < 2) return null;
  const { index, count, ids } = siblings;
  return (
    <div className="flex items-center text-xs text-muted-foreground tabular-nums" aria-label="Versions">
      <IconAction label="Previous version" disabled={disabled || index === 0} onClick={() => onSwitch(ids[index - 1])}>
        <ChevronLeft />
      </IconAction>
      <span aria-live="polite">
        {index + 1} / {count}
      </span>
      <IconAction label="Next version" disabled={disabled || index === count - 1} onClick={() => onSwitch(ids[index + 1])}>
        <ChevronRight />
      </IconAction>
    </div>
  );
}

export function UserMessage({ message, busy, onEdit, onSwitch }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);
  const pending = !message.id;

  if (editing) {
    const submit = () => {
      const content = draft.trim();
      if (!content) return;
      setEditing(false);
      if (content !== message.content) onEdit(message.id, content);
    };
    return (
      <div className="flex justify-end">
        <form
          className="w-full max-w-[85%] rounded-2xl border bg-card p-3 shadow-soft"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label htmlFor={`edit-${message.id}`} className="sr-only">
            Edit your question
          </label>
          <textarea
            id={`edit-${message.id}`}
            autoFocus
            value={draft}
            maxLength={2000}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
              if (event.key === 'Escape') setEditing(false);
            }}
            className="field-sizing-content block max-h-60 min-h-12 w-full resize-none bg-transparent text-[15px] leading-relaxed outline-none"
          />
          <div className="mt-2 flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" type="submit" disabled={!draft.trim()}>
              Send
            </Button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className={cn('group flex flex-col items-end gap-1', message.key && 'animate-rise')}>
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5 text-[15px] leading-relaxed break-words whitespace-pre-wrap text-secondary-foreground">
        {message.content}
      </div>
      {!pending ? (
        <div className="flex items-center opacity-100 transition-opacity focus-within:opacity-100 sm:opacity-0 sm:group-hover:opacity-100 print:hidden">
          <BranchSwitcher siblings={message.siblings} onSwitch={onSwitch} disabled={busy} />
          <CopyAction text={message.content} />
          <IconAction
            label="Edit question"
            disabled={busy}
            onClick={() => {
              setDraft(message.content);
              setEditing(true);
            }}
          >
            <Pencil />
          </IconAction>
        </div>
      ) : null}
    </div>
  );
}

function FreshnessNote({ sources }) {
  const freshness = describeFreshness(sources);
  if (!freshness) return null;
  return (
    <>
      {freshness.summary ? (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
          <CalendarClock className="size-3.5 shrink-0" aria-hidden="true" />
          {freshness.summary}
        </p>
      ) : null}
      {freshness.warning ? (
        <p className="mt-3 flex animate-fade-in items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-relaxed">
          <History className="mt-px size-4 shrink-0 text-warning" aria-hidden="true" />
          {freshness.warning}
        </p>
      ) : null}
    </>
  );
}

const SUGGESTABLE = new Set(['answered', 'cached']);

/** Follow-up questions: a button until asked for, then chips that ask the question. */
function FollowUps({ message, pending, askDisabled, onSuggest, onAsk }) {
  if (message.suggestions?.length) {
    return (
      <div className="mt-4 print:hidden" role="group" aria-label="Suggested follow-ups">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Lightbulb className="size-3.5" aria-hidden="true" /> Suggested follow-ups
        </p>
        <div className="flex flex-wrap gap-2">
          {message.suggestions.map((text) => (
            <button
              key={text}
              type="button"
              disabled={askDisabled}
              onClick={() => onAsk(text)}
              className="rounded-full border bg-card px-3 py-1.5 text-left text-sm leading-snug transition-colors outline-none hover:border-primary/40 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50"
            >
              {text}
            </button>
          ))}
        </div>
      </div>
    );
  }
  if (message.suggestionsEmpty) {
    return <p className="mt-4 text-xs text-muted-foreground">No follow-up suggestions for this answer.</p>;
  }
  return (
    <Button size="sm" variant="outline" className="mt-4 rounded-full" disabled={pending} onClick={() => onSuggest(message.id)}>
      <Lightbulb /> {pending ? 'Thinking of follow-ups…' : 'Suggest follow-ups'}
    </Button>
  );
}

function ErrorNotice({ error, onRetry }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-xl border border-destructive/25 bg-destructive/5 p-4 sm:flex-row sm:items-center">
      <AlertTriangle className="size-5 shrink-0 text-destructive" aria-hidden="true" />
      <p className="flex-1 text-sm">{error.message}</p>
      {error.retryable && onRetry ? (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCcw /> Try again
        </Button>
      ) : null}
    </div>
  );
}

/**
 * `message` is a saved assistant message, or a live one built from the stream:
 * {content, sources, status: 'streaming'|..., stage, stageDetail, error}.
 */
export function AssistantMessage({
  message,
  busy,
  isLast,
  onRegenerate,
  onSwitch,
  onFeedback,
  onRetry,
  onSuggest,
  suggesting = false,
  onAsk,
  askDisabled = false,
}) {
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const streaming = message.status === 'streaming';
  const sourcesByPosition = new Map((message.sources || []).map((source) => [source.position, source]));
  const rating = message.feedback?.rating ?? 0;
  const complete = message.status === 'complete';
  const canAct = Boolean(message.id) && !streaming;

  const smooth = useSmoothText(message.content || '', streaming, message.id);
  const renderCitation = (position) => <CitationChip position={position} source={sourcesByPosition.get(position)} />;

  return (
    <div className={cn('group flex gap-3 sm:gap-4', message.key && 'animate-rise')}>
      <LogoMark motion={streaming && !message.content ? 'loop' : 'none'} className="mt-0.5 size-7 rounded-lg" />
      <div className="min-w-0 flex-1">
        {streaming && !message.content ? <ThinkingIndicator stage={message.stage} detail={message.stageDetail} /> : null}

        {message.content ? (
          <div aria-live="polite" aria-busy={streaming}>
            <Markdown content={smooth.text} renderCitation={renderCitation} className={cn((streaming || smooth.revealing) && 'streaming-caret')} />
          </div>
        ) : null}

        {message.status === 'stopped' ? (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Square className="size-3" aria-hidden="true" /> {message.content ? 'Stopped. The answer may be incomplete.' : 'Stopped.'}
          </p>
        ) : null}

        {message.status === 'failed' && !message.error ? (
          <ErrorNotice
            error={{ message: 'This answer couldn’t be completed.', retryable: Boolean(onRegenerate) && isLast }}
            onRetry={() => onRegenerate(message.id)}
          />
        ) : null}

        {message.error ? <ErrorNotice error={message.error} onRetry={onRetry} /> : null}

        {complete && !smooth.revealing && message.grounded === false && message.answer_type === 'answered' ? (
          <p className="mt-3 flex animate-fade-in items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs leading-relaxed">
            <ShieldAlert className="mt-px size-4 shrink-0 text-warning" aria-hidden="true" />
            Parts of this answer couldn’t be matched to the sources. Verify the details with the official source before relying on them.
          </p>
        ) : null}

        {complete && !smooth.revealing ? <FreshnessNote sources={message.sources} /> : null}

        {!streaming && !smooth.revealing ? <SourceList sources={message.sources} /> : null}

        {canAct && message.content && !smooth.revealing ? (
          <div
            className={cn(
              'mt-2 -ml-2 flex items-center transition-opacity print:hidden',
              !isLast && 'sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100',
            )}
          >
            <CopyAction text={message.content} />
            {complete ? (
              <>
                <IconAction
                  label="Good answer"
                  active={rating === 1}
                  disabled={busy}
                  onClick={() => onFeedback(message.id, rating === 1 ? null : { rating: 1 })}
                >
                  <ThumbsUp className={cn(rating === 1 && 'fill-current')} />
                </IconAction>
                <IconAction
                  label="Bad answer"
                  active={rating === -1}
                  disabled={busy}
                  onClick={() => (rating === -1 ? onFeedback(message.id, null) : setFeedbackOpen(true))}
                >
                  <ThumbsDown className={cn(rating === -1 && 'fill-current')} />
                </IconAction>
              </>
            ) : null}
            <IconAction label="Regenerate" disabled={busy} onClick={() => onRegenerate(message.id)}>
              <RefreshCw />
            </IconAction>
            <BranchSwitcher siblings={message.siblings} onSwitch={onSwitch} disabled={busy} />
          </div>
        ) : null}

        {/* Only under the latest answer: a chip asks its question at the end of the chat. */}
        {isLast && canAct && complete && !smooth.revealing && SUGGESTABLE.has(message.answer_type) && onSuggest ? (
          <FollowUps message={message} pending={suggesting} askDisabled={busy || askDisabled} onSuggest={onSuggest} onAsk={onAsk} />
        ) : null}
      </div>

      {feedbackOpen ? (
        <FeedbackDialog
          open
          onOpenChange={setFeedbackOpen}
          initial={message.feedback}
          onSubmit={({ reason, comment }) => {
            setFeedbackOpen(false);
            onFeedback(message.id, { rating: -1, reason, comment });
          }}
        />
      ) : null}
    </div>
  );
}
