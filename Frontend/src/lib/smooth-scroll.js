// Momentum scrolling for the landing page (Lenis): the wheel glides to a stop instead of
// jumping in steps, and in-page links (#faq, …) glide there too. Only the landing page runs
// it; everywhere else in the app scrolls natively. Skipped under reduced motion.
// Styles: landing.css (html.lenis).
import Lenis from 'lenis';

let lenis = null;

/** Starts smooth scrolling; returns the cleanup. */
export function startSmoothScroll() {
  if (lenis || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return () => {};
  const instance = new Lenis({
    autoRaf: true,
    lerp: 0.09,
    wheelMultiplier: 0.9,
    anchors: true,
    // Inner scrollers (menus, the mobile nav sheet) keep their own native scroll.
    allowNestedScroll: true,
  });
  lenis = instance;
  return () => {
    instance.destroy();
    if (lenis === instance) lenis = null;
  };
}

/** Scrolls to the top, gliding when smooth scrolling is on. */
export function scrollToTop() {
  if (lenis) lenis.scrollTo(0);
  else {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
  }
}
