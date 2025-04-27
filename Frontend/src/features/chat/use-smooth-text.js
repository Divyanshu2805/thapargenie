import { useEffect, useRef, useState } from 'react';

// Streams arrive in uneven pieces (a whole paragraph at once, or a cached answer in one
// go). While an answer is live, reveal it at a steady typing pace instead, speeding up
// when a lot is waiting so the text never lags far behind.
const BASE_CHARS_PER_SECOND = 90;
const MAX_LAG_SECONDS = 1.2;

// How far each answer has been revealed, by message id, so a remount (the live answer
// being replaced by its saved copy) carries on typing instead of jumping to the end.
const progress = new Map();

function reducedMotion() {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Returns the part of `text` to show now. `live` is true while the answer is streaming;
 * `id` (once known) lets the reveal survive a remount.
 */
export function useSmoothText(text, live, id) {
  // Answers loaded from history were never live: show them whole.
  const [resumeFrom] = useState(() => (id && progress.has(id) ? progress.get(id) : null));
  const [animate, setAnimate] = useState(() => (live || resumeFrom !== null) && !reducedMotion());
  if (live && !animate && !reducedMotion()) setAnimate(true);
  const [shown, setShown] = useState(resumeFrom ?? 0);
  const position = useRef(resumeFrom ?? 0);

  useEffect(() => {
    if (!animate) return undefined;
    let frame = 0;
    let last = performance.now();
    const step = (now) => {
      const elapsed = Math.min(0.1, (now - last) / 1000);
      last = now;
      const backlog = text.length - position.current;
      if (backlog <= 0) {
        if (id && !live) progress.delete(id);
        return;
      }
      const speed = Math.max(BASE_CHARS_PER_SECOND, backlog / MAX_LAG_SECONDS);
      let next = Math.min(text.length, position.current + Math.max(1, speed * elapsed));
      // Never split a surrogate pair (emoji and some scripts).
      const code = text.charCodeAt(Math.floor(next) - 1);
      if (code >= 0xd800 && code <= 0xdbff) next += 1;
      position.current = next;
      if (id) progress.set(id, next);
      setShown(Math.floor(next));
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [text, animate, id, live]);

  if (!animate) return { text, revealing: false };
  const visible = Math.min(shown, text.length);
  return { text: text.slice(0, visible), revealing: visible < text.length };
}
