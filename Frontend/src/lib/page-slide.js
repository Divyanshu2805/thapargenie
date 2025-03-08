// The slide used when signing in and signing up: the current page slides out to the left while
// the next one slides in from the right behind it. Signing out (and going back) runs it the other
// way, left to right. Built on the browser's
// View Transitions; where they aren't supported (or motion is reduced) the page just changes.
// Styles: index.css (html.page-slide).
import { useNavigate } from 'react-router-dom';

// The longest the slide waits for the next page to settle before moving on.
const READY_TIMEOUT_MS = 3000;

let sliding = false;
let held = 0;

/** No full-screen loading state is showing. */
const noLoadingScreen = () => !document.querySelector('.auth-loading');

/** For signing out: the sign-in page itself is on screen. */
export const onSignInPage = () => window.location.pathname.startsWith('/login') && noLoadingScreen();

/**
 * While a sign-in is in flight, the signed-out routes hold their automatic redirect to the
 * app, so the slide can carry the user there instead of the page jumping.
 */
export function holdAuthRedirect() {
  held += 1;
  return () => {
    held = Math.max(0, held - 1);
  };
}

export function authRedirectHeld() {
  return sliding || held > 0;
}

// Timers, not animation frames: the browser pauses rendering while a transition's update runs.
const pause = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

async function waitUntil(ready) {
  const started = Date.now();
  await pause(30);
  while (!ready() && Date.now() - started < READY_TIMEOUT_MS) {
    await pause(60);
  }
  // One more beat so React has painted what it just committed.
  await pause(40);
}

/**
 * Runs `go` (which may return a promise) inside a page slide. By default the slide waits until
 * the address has changed and no loading screen is showing; `ready` can say otherwise.
 * `back: true` runs it the other way round, for going back to where a slide came from.
 */
export function slideTo(go, { ready, back = false } = {}) {
  if (!canSlide()) return go();

  const from = window.location.pathname;
  const settled = ready ?? (() => window.location.pathname !== from && noLoadingScreen());
  const root = document.documentElement;
  sliding = true;
  root.classList.add('page-slide');
  root.classList.toggle('page-slide-back', back);
  const transition = document.startViewTransition(async () => {
    try {
      await go();
    } finally {
      await waitUntil(settled);
    }
  });
  // A skipped or aborted transition still changes the page; nothing to report.
  transition.ready.catch(() => {});
  transition.finished
    .catch(() => {})
    .finally(() => {
      sliding = false;
      root.classList.remove('page-slide', 'page-slide-back');
    });
  return transition.updateCallbackDone.catch(() => {});
}

function canSlide() {
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  return Boolean(document.startViewTransition) && !reduced;
}

const isAuthPath = (path) => /^\/(login|register)\/?$/.test(path);

// Popstate events this module re-sends for the router once a slide has started.
const replayed = new WeakSet();

/**
 * The browser's Back and Forward buttons between the landing page and the sign-in pages slide
 * too: back to the landing page runs the slide in reverse, forward again runs it as before.
 * The popstate is held back from the router (by listening in the capture phase) and sent on
 * from inside the slide, so the router swaps the page while the old one is still pictured.
 */
export function slideOnHistoryMoves() {
  window.addEventListener(
    'popstate',
    (event) => {
      if (replayed.has(event) || sliding || !canSlide()) return;
      const to = window.location.pathname;
      const leavingAuth = Boolean(document.querySelector('.auth-page'));
      const leavingLanding = Boolean(document.querySelector('.landing'));
      let back;
      if (leavingAuth && to === '/') back = true;
      else if (leavingLanding && isAuthPath(to)) back = false;
      else return;

      event.stopImmediatePropagation();
      const arrived = back ? '.landing' : '.auth-page';
      slideTo(
        () => {
          const again = new PopStateEvent('popstate', { state: event.state });
          replayed.add(again);
          window.dispatchEvent(again);
        },
        { back, ready: () => Boolean(document.querySelector(arrived)) && noLoadingScreen() },
      );
    },
    true,
  );
}

/** navigate() inside a page slide. */
export function useSlideNavigate() {
  const navigate = useNavigate();
  return (to, options, slideOptions) => slideTo(() => navigate(to, options), slideOptions);
}

/** An onClick for links: plain clicks slide; modified or middle clicks work as usual. */
export function useSlideClick(slideOptions) {
  const go = useSlideNavigate();
  return (event) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    go(event.currentTarget.getAttribute('href'), undefined, slideOptions);
  };
}
