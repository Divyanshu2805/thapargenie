import { useEffect, useRef, useState } from 'react';

import { onScrollFrame } from '@/lib/scroll-frame';

export function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

function finePointer() {
  return typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches;
}

/**
 * Starts the looping visuals: every `[data-play]` element under the returned ref gets
 * `.is-visible` the first time it scrolls into view. Nothing fades or slides in; the page's
 * content is simply there as you scroll.
 */
export function usePlayOnView() {
  const ref = useRef(null);
  useEffect(() => {
    const items = ref.current?.querySelectorAll('[data-play]') ?? [];
    if (typeof IntersectionObserver === 'undefined') {
      items.forEach((item) => item.classList.add('is-visible'));
      return undefined;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.12 },
    );
    items.forEach((item) => observer.observe(item));
    return () => observer.disconnect();
  }, []);
  return ref;
}

/** True while the element is on screen (or always, where IntersectionObserver is missing). */
export function useInView(ref, { once = false, rootMargin = '0px' } = {}) {
  const [inView, setInView] = useState(typeof IntersectionObserver === 'undefined');
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        setInView(entry.isIntersecting);
        if (entry.isIntersecting && once) observer.disconnect();
      },
      { rootMargin, threshold: 0.2 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref, once, rootMargin]);
  return inView;
}

/** Whether the page has left the very top. */
export function useScrollState(threshold = 24) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(
    () =>
      // A little hysteresis so hovering around the threshold doesn't flip the bar back and forth.
      onScrollFrame(({ y }) => setScrolled((was) => (was ? y > threshold / 3 : y > threshold))),
    [threshold],
  );
  return { scrolled };
}

/** The id of the section in the middle of the screen. */
export function useScrollSpy(ids) {
  const [active, setActive] = useState(null);
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) if (entry.isIntersecting) setActive(entry.target.id);
      },
      { rootMargin: '-45% 0px -50% 0px' },
    );
    ids.forEach((id) => {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [ids]);
  return active;
}

/**
 * Pointer effects for the cards under `ref`, with one listener and at most one update a frame:
 * the `.lp-card` under the pointer gets --mx/--my (a soft light that follows it), and a
 * `[data-tilt]` card also gets --rx/--ry (a gentle 3D tilt). Mouse only, and only with motion.
 */
export function usePointerEffects(ref) {
  useEffect(() => {
    const root = ref.current;
    if (!root || !finePointer() || prefersReducedMotion()) return undefined;
    let tilt = null;
    let frame = 0;
    let last = null;

    const settle = () => {
      if (!tilt) return;
      tilt.style.setProperty('--rx', '0deg');
      tilt.style.setProperty('--ry', '0deg');
    };

    const update = () => {
      frame = 0;
      const { target, x, y } = last;
      const card = target.closest('.lp-card');
      const rect = card?.getBoundingClientRect();
      if (card) {
        card.style.setProperty('--mx', `${x - rect.left}px`);
        card.style.setProperty('--my', `${y - rect.top}px`);
      }
      const nextTilt = card?.hasAttribute('data-tilt') ? card : null;
      if (nextTilt !== tilt) {
        settle();
        tilt = nextTilt;
      }
      if (tilt) {
        tilt.style.setProperty('--ry', `${((x - rect.left) / rect.width - 0.5) * 5}deg`);
        tilt.style.setProperty('--rx', `${((y - rect.top) / rect.height - 0.5) * -5}deg`);
      }
    };

    const onMove = (event) => {
      if (!(event.target instanceof Element)) return;
      last = { target: event.target, x: event.clientX, y: event.clientY };
      if (!frame) frame = requestAnimationFrame(update);
    };

    const onLeave = () => {
      settle();
      tilt = null;
    };

    root.addEventListener('pointermove', onMove, { passive: true });
    root.addEventListener('pointerleave', onLeave);
    return () => {
      root.removeEventListener('pointermove', onMove);
      root.removeEventListener('pointerleave', onLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [ref]);
}

/**
 * Moves the element in `lightRef` so its centre sits under the pointer while it is over the
 * element in `areaRef`. Only a transform changes, so nothing is repainted. Mouse only.
 */
export function usePointerLight(areaRef, lightRef) {
  useEffect(() => {
    const area = areaRef.current;
    const light = lightRef.current;
    if (!area || !light || !finePointer() || prefersReducedMotion()) return undefined;
    let frame = 0;
    let point = null;

    const update = () => {
      frame = 0;
      const rect = area.getBoundingClientRect();
      // The light rests at 72% / 30% of the area (landing.css); the transform is the offset from there.
      const dx = point.x - rect.left - rect.width * 0.72;
      const dy = point.y - rect.top - rect.height * 0.3;
      light.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0)`;
    };

    const onMove = (event) => {
      if (event.pointerType !== 'mouse') return;
      point = { x: event.clientX, y: event.clientY };
      if (!frame) frame = requestAnimationFrame(update);
    };

    area.addEventListener('pointermove', onMove, { passive: true });
    return () => {
      area.removeEventListener('pointermove', onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [areaRef, lightRef]);
}

/**
 * Steps that take turns. The active item shows a `.lp-progress` bar; when its `lp-progress`
 * animation ends, the next item takes over. CSS pauses the bar on hover, and nothing runs
 * unless the caller sets `data-running` (on screen, motion allowed).
 */
export function useCycle(count) {
  const [active, setActive] = useState(0);
  const onAnimationEnd = (event) => {
    if (event.animationName === 'lp-progress') setActive((index) => (index + 1) % count);
  };
  return { active, setActive, onAnimationEnd };
}
