import { useEffect } from 'react';

function allowed() {
  const media = (query) => window.matchMedia?.(query).matches;
  return media('(hover: hover) and (pointer: fine)') && !media('(prefers-reduced-motion: reduce)');
}

/**
 * Moves the element in `lightRef` so its centre sits under the pointer while it is over the
 * element in `areaRef`. The light's CSS places it at `restX` / `restY` of the area (fractions
 * of its width and height); only a transform changes from there, at most once a frame, so
 * following the pointer repaints nothing. Mouse only, and only with motion.
 */
export function usePointerLight(areaRef, lightRef, restX, restY) {
  useEffect(() => {
    const area = areaRef.current;
    const light = lightRef.current;
    if (!area || !light || !allowed()) return undefined;
    let frame = 0;
    let point = null;

    const update = () => {
      frame = 0;
      const rect = area.getBoundingClientRect();
      const dx = point.x - rect.left - rect.width * restX;
      const dy = point.y - rect.top - rect.height * restY;
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
  }, [areaRef, lightRef, restX, restY]);
}
