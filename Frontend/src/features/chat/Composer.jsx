import { ArrowUp, Mic, Square } from 'lucide-react';
import { toast } from 'sonner';

import { useSpeechInput } from '@/features/chat/use-speech-input';
import { useTypewriter } from '@/hooks/use-typewriter';
import { cn } from '@/lib/utils';

const MAX_QUESTION_CHARS = 2000;
const NO_SUGGESTIONS = [];

// Focus the box on desktop only; on phones it would pop the keyboard over the page.
function prefersAutoFocus() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(pointer: fine)').matches;
}

export default function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  streaming = false,
  disabled = false,
  disabledReason,
  inputRef,
  remaining,
  placeholder = 'Ask about fees, hostels, admissions, the academic calendar…',
  suggestions = NO_SUGGESTIONS,
  autoFocus,
}) {
  // While the box is empty, suggested questions type themselves out as the placeholder;
  // Tab puts the one on screen into the box.
  const speech = useSpeechInput({ value, onText: onChange, onError: (message) => toast.error(message) });
  const suggesting = !value && !disabled && !speech.listening && suggestions.length > 0;
  const typed = useTypewriter(suggestions, { enabled: suggesting, hold: 2200 });
  const canSend = value.trim().length > 0 && !disabled && !streaming;
  const nearLimit = value.length > MAX_QUESTION_CHARS - 200;

  const handleKeyDown = (event) => {
    if (event.key === 'Tab' && !event.shiftKey && suggesting && typed.full) {
      event.preventDefault();
      onChange(typed.full);
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      speech.stop();
      if (canSend) onSubmit();
    }
    if (event.key === 'Escape' && speech.listening) speech.stop();
    if (event.key === 'Escape' && streaming) onStop?.();
  };

  let hint = ' ';
  if (disabled && disabledReason) hint = disabledReason;
  else if (speech.listening) hint = 'Listening… speak your question, then pause.';
  else if (nearLimit) hint = `${value.length} / ${MAX_QUESTION_CHARS} characters`;
  else if (typeof remaining === 'number') hint = `${remaining} question${remaining === 1 ? '' : 's'} left today`;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        speech.stop();
        if (canSend) onSubmit();
      }}
      className="rounded-2xl border bg-card shadow-lift transition-[border-color,box-shadow] focus-within:border-ring/60 focus-within:ring-[3px] focus-within:ring-ring/15"
    >
      <label htmlFor="composer" className="sr-only">
        Ask a question about TIET
      </label>
      <div className="relative">
        <textarea
          id="composer"
          ref={inputRef}
          rows={1}
          value={value}
          maxLength={MAX_QUESTION_CHARS}
          disabled={disabled}
          autoFocus={autoFocus && prefersAutoFocus()}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={cn(
            'field-sizing-content block max-h-52 min-h-[3.25rem] w-full resize-none bg-transparent px-4 pt-3.5 pb-1 text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed',
            suggesting && 'placeholder:text-transparent',
          )}
        />
        {suggesting ? (
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-4 top-3.5 flex items-center gap-2 text-[15px] leading-relaxed text-muted-foreground">
            <span className="min-w-0 truncate">
              {typed.text}
              <span className="ml-px inline-block h-[1.1em] w-[2px] translate-y-[0.2em] animate-[caret-blink_1s_steps(2,start)_infinite] rounded-full bg-primary/70" />
            </span>
            {typed.text === typed.full ? (
              <kbd className="hidden shrink-0 animate-fade-in rounded border px-1.5 font-sans text-[11px] leading-5 [@media(pointer:fine)]:inline">Tab</kbd>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-3 px-3 pb-3">
        <span className={cn('truncate pl-1 text-xs text-muted-foreground', nearLimit && 'text-warning')} aria-live="polite">
          {hint}
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          {speech.supported && !streaming ? (
            <button
              type="button"
              onClick={speech.listening ? speech.stop : speech.start}
              disabled={disabled}
              aria-label={speech.listening ? 'Stop listening' : 'Speak your question'}
              aria-pressed={speech.listening}
              title={speech.listening ? 'Stop listening' : 'Speak your question'}
              className={cn(
                'icon-nudge relative flex size-9 shrink-0 items-center justify-center rounded-xl transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:pointer-events-none disabled:opacity-50',
                speech.listening
                  ? 'bg-destructive/10 text-destructive'
                  : 'text-muted-foreground hover:bg-hover hover:text-foreground',
              )}
            >
              {speech.listening ? (
                <span aria-hidden="true" className="absolute inset-0 animate-ping rounded-xl bg-destructive/15 [animation-duration:1.6s]" />
              ) : null}
              <Mic className="relative size-[18px]" />
            </button>
          ) : null}
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop answering"
              className="icon-nudge flex size-9 shrink-0 items-center justify-center rounded-xl bg-foreground text-background shadow-sm transition-transform outline-none hover:opacity-90 focus-visible:ring-[3px] focus-visible:ring-ring/40 active:scale-95"
            >
              <Square className="size-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send question"
              className={cn(
                'icon-nudge flex size-9 shrink-0 items-center justify-center rounded-xl transition-[background-color,transform,opacity] outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40',
                canSend
                  ? 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 active:scale-95'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              <ArrowUp className="size-[18px]" strokeWidth={2.25} />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
