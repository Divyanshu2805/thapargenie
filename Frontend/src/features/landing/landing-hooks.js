import { useEffect, useRef, useState } from 'react';

export function prefersReducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

function finePointer() {
  return typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches;
}

/**
 * Fades in every `[data-reveal]` element under the returned ref the first time it scrolls
 * into view (adds `.is-visible`). Each element can set `--d` to delay its entrance.
 */
export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const items = ref.current?.querySelectorAll('[data-reveal]') ?? [];
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

/** Counts from 0 up to `target` once `active` turns true, easing out. */
export function useCountUp(target, active, duration = 1400) {
  const [value, setValue] = useState(0);
  const [still] = useState(prefersReducedMotion);
  useEffect(() => {
    if (!active || still) return undefined;
    let frame;
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      setValue(Math.round(target * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active, still, duration]);
  return still && active ? target : value;
}

/** Whether the page has left the very top. */
export function useScrollState(threshold = 24) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      // A little hysteresis so hovering around the threshold doesn't flip the bar back and forth.
      const y = window.scrollY;
      setScrolled((was) => (was ? y > threshold / 3 : y > threshold));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [threshold]);
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
 * Pointer effects for everything under `ref`, with one listener:
 * `[data-spotlight]` gets --mx/--my (a light that follows the pointer), and
 * `[data-tilt]` gets --rx/--ry (a gentle 3D tilt; mouse only, and only with motion).
 */
export function usePointerEffects(ref) {
  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const moving = finePointer() && !prefersReducedMotion();
    let tilt = null;

    const settle = () => {
      if (!tilt) return;
      tilt.style.setProperty('--rx', '0deg');
      tilt.style.setProperty('--ry', '0deg');
    };

    const onMove = (event) => {
      if (!(event.target instanceof Element)) return;
      const spot = event.target.closest('[data-spotlight]');
      if (spot) {
        const rect = spot.getBoundingClientRect();
        spot.style.setProperty('--mx', `${event.clientX - rect.left}px`);
        spot.style.setProperty('--my', `${event.clientY - rect.top}px`);
      }
      if (!moving) return;

      const nextTilt = event.target.closest('[data-tilt]');
      if (nextTilt !== tilt) {
        settle();
        tilt = nextTilt;
      }
      if (tilt) {
        const rect = tilt.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        tilt.style.setProperty('--ry', `${x * 5}deg`);
        tilt.style.setProperty('--rx', `${y * -5}deg`);
      }
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
    };
  }, [ref]);
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
