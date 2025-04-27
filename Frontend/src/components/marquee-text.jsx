import { useLayoutEffect, useRef } from 'react';

import { cn } from '@/lib/utils';

/**
 * One line of text that slides to reveal the rest while its row is hovered or focused,
 * like long chat titles in a sidebar. The parent needs the `group/marquee` class.
 */
export function MarqueeText({ children, className }) {
  const outer = useRef(null);
  const inner = useRef(null);

  // Measured on mount and again on hover, so resizing never leaves a stale distance.
  const measure = () => {
    const box = outer.current;
    const text = inner.current;
    if (!box || !text) return;
    const overflow = Math.max(0, text.scrollWidth - box.clientWidth);
    // Only a title that doesn't fit fades out at its end.
    box.toggleAttribute('data-overflow', overflow > 0);
    text.style.setProperty('--marquee-shift', `-${overflow}px`);
    text.style.setProperty('--marquee-duration', `${Math.min(6, Math.max(1.2, overflow / 45))}s`);
  };

  useLayoutEffect(measure, [children]);

  return (
    <span
      ref={outer}
      onMouseEnter={measure}
      onFocus={measure}
      className={cn('marquee block min-w-0 overflow-hidden whitespace-nowrap', className)}
    >
      <span ref={inner} className="marquee__text inline-block">
        {children}
      </span>
    </span>
  );
}
