// One scroll listener and one animation frame for everything that follows the page's scroll
// (the landing page's bar, hero, backdrop and back-to-top ring). Each frame reads the scroll
// position once and hands it to every subscriber, so one subscriber's style change never makes
// the next one's read force a fresh layout.

const subscribers = new Set();
let frame = 0;

function read() {
  const y = window.scrollY;
  const max = document.documentElement.scrollHeight - window.innerHeight;
  return { y, progress: max > 0 ? y / max : 0 };
}

function run() {
  frame = 0;
  const state = read();
  subscribers.forEach((subscriber) => subscriber(state));
}

function onScroll() {
  if (!frame) frame = requestAnimationFrame(run);
}

/** Calls `subscriber({ y, progress })` now and on every frame the page scrolls; returns the cleanup. */
export function onScrollFrame(subscriber) {
  if (!subscribers.size) window.addEventListener('scroll', onScroll, { passive: true });
  subscribers.add(subscriber);
  subscriber(read());
  return () => {
    subscribers.delete(subscriber);
    if (subscribers.size) return;
    window.removeEventListener('scroll', onScroll);
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  };
}
