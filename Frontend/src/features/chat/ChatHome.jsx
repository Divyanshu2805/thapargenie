import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Building2,
  CircleHelp,
  CalendarDays,
  GraduationCap,
  IndianRupee,
  Landmark,
  Sparkles,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '@/auth/AuthContext';
import { LogoMark } from '@/components/brand/Brand';
import { Skeleton } from '@/components/ui/skeleton';
import Composer from '@/features/chat/Composer';
import { MaintenanceCard } from '@/features/chat/Maintenance';
import { dismissNotice, useDismissedNotice } from '@/features/notices/seen';
import { useAppConfig } from '@/hooks/use-app-config';
import { createConversation } from '@/lib/api/chat';

const CATEGORY_ICONS = {
  fees: IndianRupee,
  hostels: Building2,
  admissions: GraduationCap,
  calendar: CalendarDays,
  academics: BookOpen,
  rules: Landmark,
};

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function firstName(user) {
  const name = user?.displayName?.trim();
  return name ? name.split(/\s+/)[0] : null;
}

function StarterQuestions({ onPick }) {
  const { data, isPending } = useAppConfig();

  if (isPending) {
    return (
      <div className="grid gap-3 sm:grid-cols-2" aria-hidden="true">
        {[0, 1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-[4.5rem] rounded-xl" />
        ))}
      </div>
    );
  }

  const questions = (data?.starter_questions || []).slice(0, 4);
  if (questions.length === 0) return null;

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {questions.map((question, index) => {
        const Icon = CATEGORY_ICONS[question.category?.toLowerCase()] || Sparkles;
        return (
          <li key={question.text} className="animate-rise" style={{ animationDelay: `${80 + index * 50}ms` }}>
            <button
              type="button"
              onClick={() => onPick(question.text)}
              className="group flex h-full w-full items-start gap-3 rounded-xl border bg-card p-3.5 text-left shadow-soft transition-[border-color,box-shadow,transform] outline-none hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lift focus-visible:ring-[3px] focus-visible:ring-ring/30"
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0">
                <span className="block text-xs font-medium text-muted-foreground">{question.category}</span>
                <span className="mt-0.5 block text-sm leading-snug">{question.text}</span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** The newest important notice, until the student dismisses it on this device. */
export function ImportantNotice({ notice }) {
  const dismissed = useDismissedNotice();
  if (!notice || dismissed === notice.id) return null;
  return (
    <div className="mb-4 flex items-center gap-3 rounded-xl border border-destructive/25 bg-destructive/[0.05] py-2.5 pr-2 pl-3.5 text-sm animate-rise">
      <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
      <p className="min-w-0 flex-1">
        <span className="font-semibold">Important:</span> <span className="break-words">{notice.title}</span>
      </p>
      <Link
        to={`/notices#notice-${notice.id}`}
        className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 font-medium text-primary outline-none hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        Read <ArrowRight className="size-3.5" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => dismissNotice(notice.id)}
        aria-label="Dismiss this notice"
        className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// Typed into the empty composer after the admin's starter questions.
const MORE_SUGGESTIONS = [
  'When does the odd semester start?',
  'How do I apply for a merit scholarship?',
  'What is the attendance rule for exams?',
  'Where is the admissions office?',
];

/** Why asking is unavailable right now, or null. */
export function composerBlock(config) {
  if (config?.maintenance) return 'Asking is paused during maintenance.';
  if (config?.remaining_today === 0) return 'You’ve reached today’s question limit. It resets at midnight.';
  return null;
}

export default function ChatHome() {
  const { user } = useAuth();
  const { data: config } = useAppConfig();
  const location = useLocation();
  // A question handed over by the "What can I ask?" page starts in the box, not sent.
  const [draft, setDraft] = useState(() => location.state?.draft || '');
  const inputRef = useRef(null);
  const name = firstName(user);

  const pickStarter = (text) => {
    setDraft(text);
    inputRef.current?.focus();
  };

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const blocked = composerBlock(config);
  const suggestions = useMemo(
    () => [...new Set([...(config?.starter_questions || []).map((question) => question.text), ...MORE_SUGGESTIONS])],
    [config?.starter_questions],
  );

  // Drop the handed-over question from history, so a reload doesn't bring it back.
  const handedOver = Boolean(location.state?.draft);
  useEffect(() => {
    if (handedOver) navigate(location.pathname, { replace: true, state: null });
  }, [handedOver, location.pathname, navigate]);

  // The conversation is created first; its page then streams the question (state.ask).
  const start = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (conversation) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      navigate(`/chat/${conversation.id}`, { state: { ask: draft.trim() } });
    },
    onError: (error) => toast.error('Couldn’t start a chat', { description: error.message }),
  });

  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(60%_100%_at_50%_0%,color-mix(in_oklab,var(--color-primary)_9%,transparent),transparent)]"
      />
      <div className="chat-column relative flex flex-1 flex-col justify-center py-8 sm:py-12">
        <div className="animate-rise text-center">
          <LogoMark motion="loop" className="size-16 rounded-2xl shadow-lift" />
          <h1 className="mt-5 text-display">
            {greeting()}
            {name ? `, ${name}` : ''}.
            <span className="block text-muted-foreground">
              {config?.maintenance ? 'Back with answers shortly.' : 'What would you like to know?'}
            </span>
          </h1>
        </div>

        <div className="mt-8 animate-rise [animation-delay:80ms] sm:mt-10">
          {config?.maintenance ? (
            <MaintenanceCard message={config.maintenance_message} />
          ) : (
            <Composer
              value={draft}
              onChange={setDraft}
              onSubmit={() => start.mutate()}
              inputRef={inputRef}
              disabled={Boolean(blocked) || start.isPending}
              disabledReason={blocked}
              remaining={config?.remaining_today}
              suggestions={suggestions}
              autoFocus
            />
          )}
        </div>

        <div className="mt-6">
          {/* Nothing can be asked during maintenance, so no starter questions then. */}
          {config?.maintenance ? null : <ImportantNotice notice={config?.important_notice} />}
          {config?.maintenance ? null : <StarterQuestions onPick={pickStarter} />}
          <p className="mt-4 text-center text-sm">
            <Link
              to="/help"
              className="inline-flex items-center gap-1.5 rounded text-muted-foreground outline-none hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <CircleHelp className="size-4" aria-hidden="true" /> What can I ask?
            </Link>
          </p>
        </div>
      </div>

      <p className="relative px-4 pb-4 text-center text-xs text-muted-foreground">
        ThaparGenie can make mistakes. Check the linked source, and don’t share personal details.
      </p>
    </div>
  );
}
