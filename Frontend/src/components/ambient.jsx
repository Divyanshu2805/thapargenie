import { useEffect, useRef } from 'react';

import { cn } from '@/lib/utils';

// The quiet backdrop shared by the landing page, the sign-in screens and the chat app:
// slowly drifting glows and topographic contour lines. Styles live in index.css.

// Nine wobbly rings around a centre, computed once.
function ring(radius, seed) {
  const steps = 64;
  const points = Array.from({ length: steps }, (_, index) => {
    const angle = (index / steps) * Math.PI * 2;
    const r = radius * (1 + 0.09 * Math.sin(3 * angle + seed) + 0.05 * Math.sin(5 * angle + seed * 1.7) + 0.03 * Math.cos(7 * angle - seed));
    return [200 + Math.cos(angle) * r, 200 + Math.sin(angle) * r];
  });
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const start = mid(points[steps - 1], points[0]);
  let d = `M${start[0].toFixed(1)} ${start[1].toFixed(1)}`;
  points.forEach((point, index) => {
    const next = mid(point, points[(index + 1) % steps]);
    d += `Q${point[0].toFixed(1)} ${point[1].toFixed(1)} ${next[0].toFixed(1)} ${next[1].toFixed(1)}`;
  });
  return `${d}Z`;
}

const CONTOURS = Array.from({ length: 9 }, (_, index) => ring(28 + index * 20, index * 0.55));

export function Contours({ className }) {
  return (
    <svg viewBox="0 0 400 400" aria-hidden="true" className={cn('contours', className)}>
      {CONTOURS.map((d, index) => (
        <path key={index} d={d} />
      ))}
    </svg>
  );
}

function reducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/**
 * `fixed` covers the viewport and drifts with page scroll (the landing page). Otherwise it
 * fills its nearest positioned, isolated parent and sits behind that parent's content.
 */
export function Ambient({ fixed = false, className }) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!fixed || !node || reducedMotion()) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      node.style.setProperty('--ambient-progress', (max > 0 ? window.scrollY / max : 0).toFixed(4));
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
  }, [fixed]);

  return (
    <div ref={ref} aria-hidden="true" className={cn('ambient', fixed ? 'ambient--fixed' : 'ambient--contained', className)}>
      <span className="ambient__glow ambient__glow--a" />
      <span className="ambient__glow ambient__glow--b" />
      <span className="ambient__glow ambient__glow--c" />
      <Contours className="ambient__contours ambient__contours--a" />
      <Contours className="ambient__contours ambient__contours--b" />
    </div>
  );
}
