import { useEffect, useState } from 'react';

import { cn } from '@/lib/utils';

// The "working on it" line shown before the first words of an answer:
// a rotating verb for the current stage with a shimmer, and the elapsed time. The animated
// logo beside it (Message.jsx) carries the motion.

export const STAGES = [
  {
    key: 'understanding',
    label: 'Understanding your question',
    verbs: ['Understanding', 'Pondering', 'Unpacking the question', 'Thinking it through'],
  },
  {
    key: 'searching',
    label: 'Searching official documents',
    verbs: ['Searching', 'Rummaging through notices', 'Digging through circulars', 'Checking the archives'],
  },
  {
    key: 'reading',
    label: 'Reading the sources',
    verbs: ['Reading', 'Skimming the fine print', 'Cross-checking', 'Connecting the dots'],
  },
  {
    key: 'writing',
    label: 'Writing the answer',
    verbs: ['Composing', 'Drafting', 'Putting it together', 'Polishing'],
  },
];

const VERB_MS = 2400;

function prefersReducedMotion() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function useTicker(intervalMs, enabled = true) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) return undefined;
    const id = window.setInterval(() => setTick((value) => value + 1), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
  return tick;
}

export function ThinkingIndicator({ stage, detail }) {
  const current = STAGES.find((item) => item.key === stage) || STAGES[0];
  const motion = !prefersReducedMotion();
  const secondTick = useTicker(1000);
  const [verbStart, setVerbStart] = useState({ stage: current.key, tick: secondTick });

  // Each stage starts on its first verb, then rotates.
  if (verbStart.stage !== current.key) setVerbStart({ stage: current.key, tick: secondTick });
  const verbIndex = Math.floor(((secondTick - verbStart.tick) * 1000) / VERB_MS) % current.verbs.length;
  const verb = current.verbs[verbIndex];
  const seconds = secondTick;
  const extra = [stage === 'reading' || stage === 'writing' ? detail : null, seconds >= 1 ? `${seconds}s` : null]
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="flex min-h-7 animate-fade-in items-center gap-2 text-sm" role="status">
      <span className="sr-only">{current.label}…</span>
      <span aria-hidden="true" key={`${current.key}-${verb}`} className={cn('animate-rise font-medium', motion && 'shimmer-text')}>
        {verb}…
      </span>
      {extra ? (
        <span aria-hidden="true" className="text-xs text-muted-foreground tabular-nums">
          ({extra}
          <span className="hidden [@media(pointer:fine)]:inline"> · esc to stop</span>)
        </span>
      ) : null}
    </div>
  );
}
