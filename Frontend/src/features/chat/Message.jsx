import {
  AlertTriangle,
  Check,
  Copy,
  RotateCcw,
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

export function UserMessage({ message }) {
  const pending = !message.id;

  return (
    <div className={cn('group flex flex-col items-end gap-1', message.key && 'animate-rise')}>
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5 text-[15px] leading-relaxed break-words whitespace-pre-wrap text-secondary-foreground">
        {message.content}
      </div>
      {!pending ? (
        <div className="flex items-center opacity-100 transition-opacity focus-within:opacity-100 sm:opacity-0 sm:group-hover:opacity-100 print:hidden">
          <CopyAction text={message.content} />
        </div>
      ) : null}
    </div>
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
  onFeedback,
  onRetry,
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
          </div>
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
