import { Fragment } from 'react';
import { Link } from 'react-router-dom';

import { useSlideClick } from '@/lib/page-slide';
import { cn } from '@/lib/utils';

// Building blocks shared by the landing page sections.

/** A small arrow; the chip holds two so one can leave as the other arrives. */
function ChipArrow({ className }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <path d="M2.5 8h10.5M9 4l4 4-4 4" />
    </svg>
  );
}

/** A ripple from the point that was pressed; it removes itself when it has faded. */
function ripple(event) {
  const node = event.currentTarget;
  const rect = node.getBoundingClientRect();
  const dot = document.createElement('span');
  dot.className = 'lp-btn__ripple';
  dot.style.left = `${event.clientX - rect.left}px`;
  dot.style.top = `${event.clientY - rect.top}px`;
  dot.addEventListener('animationend', () => dot.remove());
  node.appendChild(dot);
}

/** Keeps the pointer's position on the button so the hover fill grows from under it. */
function track(event) {
  const node = event.currentTarget;
  const rect = node.getBoundingClientRect();
  node.style.setProperty('--x', `${event.clientX - rect.left}px`);
  node.style.setProperty('--y', `${event.clientY - rect.top}px`);
}

/**
 * The landing page's button. The large one is a warm ivory pill with a thread of gold light
 * running round its edge and a glint that crosses it now and then; the small one is glass on
 * the photo. On hover a fill spreads out from under the pointer, the label rolls over and the
 * arrow in the chip is swapped for a fresh one. Following it slides to the next page the way
 * signing in does. `blend` lets it melt into the scrolled top bar. `size` is 'lg' or 'sm'.
 */
export function Cta({ to, children, className, size = 'lg', blend = false }) {
  const slide = useSlideClick();
  return (
    <Link
      to={to}
      onClick={slide}
      onPointerDown={ripple}
      onPointerEnter={track}
      onPointerMove={track}
      onPointerLeave={track}
      aria-label={children}
      data-size={size}
      data-blend={blend || undefined}
      className={cn('lp-btn', className)}
    >
      <span aria-hidden="true" className="lp-btn__ring" />
      <span aria-hidden="true" className="lp-btn__fill" />
      <span aria-hidden="true" className="lp-btn__glint" />
      <span className="lp-btn__label">
        <span className="lp-btn__text">
          {children}
        </span>
      </span>
      <span aria-hidden="true" className="lp-btn__chip">
        <ChipArrow className="lp-btn__arrow" />
        <ChipArrow className="lp-btn__arrow lp-btn__arrow--next" />
      </span>
    </Link>
  );
}

/** "01 ── The idea": a numbered section label whose rule draws in. */
export function Kicker({ index, children, dark = false, className }) {
  return (
    <p data-reveal className={cn('lp-kicker', dark && 'lp-kicker--dark', className)}>
      <span className="lp-kicker__num">{index}</span>
      <span aria-hidden="true" className="lp-kicker__rule" />
      {children}
    </p>
  );
}

/** A heading whose words rise one after another from behind a mask. `gold` words glow. */
export function SplitHeading({ as: Tag = 'h2', text, gold = '', className, delay = 0 }) {
  const words = text.split(' ');
  const golden = gold ? gold.split(' ') : [];
  return (
    <Tag data-reveal="words" className={cn('lp-split', className)}>
      {[...words, ...golden].map((word, index) => (
        <Fragment key={`${word}-${index}`}>
          <span className="lp-split__mask">
            <span className="lp-split__word" style={{ '--i': index, '--d0': `${delay}ms` }}>
              {index >= words.length ? <span className="landing-gold lp-gold-on-light">{word}</span> : word}
            </span>
          </span>{' '}
        </Fragment>
      ))}
    </Tag>
  );
}

export function SectionHeading({ index, eyebrow, title, gold, children, align = 'center', dark = false, className }) {
  return (
    <div className={cn(align === 'center' ? 'mx-auto max-w-2xl text-center' : 'max-w-xl', className)}>
      <Kicker index={index} dark={dark} className={align === 'center' ? 'justify-center' : undefined}>
        {eyebrow}
      </Kicker>
      <SplitHeading text={title} gold={gold} className={cn('landing-h2 mt-5', dark && 'text-white')} />
      {children ? (
        <p
          data-reveal
          style={{ '--d': '220ms' }}
          className={cn('mt-5 text-base leading-relaxed sm:text-lg', dark ? 'text-white/70' : 'text-muted-foreground')}
        >
          {children}
        </p>
      ) : null}
    </div>
  );
}

/** A cursor that glides to a target and clicks, for the mini UIs. Positioned by its parent's CSS. */
export function FakeCursor({ className }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn('lp-cursor', className)}>
      <path d="M5 3l14 8-6.2 1.6L10 19z" fill="#fff" stroke="#1d1517" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}
