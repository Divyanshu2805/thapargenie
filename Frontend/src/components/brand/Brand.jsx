import { useId } from 'react';

import { cn } from '@/lib/utils';

/**
 * The "ti" mark, drawn as strokes so it can animate.
 * motion: 'none' | 'draw' (letters draw in once, the dot drops) | 'loop' (draws, holds, repeats: brand and loading)
 * | 'think' (the dot bounces; an answer is being prepared).
 */
export function LogoGlyph({ className, motion = 'none' }) {
  const gradient = useId();
  return (
    <svg
      viewBox="0 0 54 76"
      aria-hidden="true"
      focusable="false"
      className={cn('logo-glyph', motion !== 'none' && `logo-glyph--${motion}`, className)}
    >
      <defs>
        <linearGradient id={gradient} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="36" y2="76">
          <stop offset="0" stopColor="#e52b36" />
          <stop offset="1" stopColor="#b3141f" />
        </linearGradient>
      </defs>
      <g fill="none" stroke={`url(#${gradient})`} strokeLinecap="round" strokeLinejoin="round">
        <path className="logo-glyph__stroke" pathLength="1" d="M8 8 V50 Q8 67 25 67 H32" strokeWidth="14" />
        <path className="logo-glyph__stroke logo-glyph__bar" pathLength="1" d="M8 33 H32" strokeWidth="14" />
        <path className="logo-glyph__stroke logo-glyph__stem" pathLength="1" d="M45 33 V67" strokeWidth="14" />
      </g>
      <circle className="logo-glyph__dot" cx="45" cy="11" r="8" fill={`url(#${gradient})`} />
    </svg>
  );
}

export function LogoMark({ className, motion = 'none' }) {
  return (
    <span
      className={cn(
        'inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-soft ring-1 ring-black/5',
        className,
      )}
    >
      <LogoGlyph motion={motion} className="h-[62%] w-auto" />
    </span>
  );
}

export function Wordmark({ className }) {
  return (
    <span className={cn('truncate text-lg leading-none font-bold tracking-tight', className)}>
      Thapar<span className="genie-shine genie-sparkles">Genie</span>
    </span>
  );
}

export function Brand({ className, markClassName }) {
  return (
    <span className={cn('group/brand flex min-w-0 items-center gap-2.5', className)}>
      {/* The brand mark always animates: it draws in, holds, and draws again. */}
      <LogoMark motion="loop" className={markClassName} />
      <Wordmark />
    </span>
  );
}
