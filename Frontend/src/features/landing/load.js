// The landing page loads on demand. Pages that can lead back to it (the sign-in screens) fetch
// it ahead with preloadLanding(), and once it has arrived App renders it straight away rather
// than flashing a loading screen through React.lazy.
import { createElement } from 'react';

import campusPhoto from './assets/campus-tinted.webp';

let loaded = null;
let pending = null;

/** Starts fetching the landing page's code and its hero photo; safe to call more than once. */
export function preloadLanding() {
  if (pending) return pending;
  const photo = new Image();
  photo.fetchPriority = 'high';
  photo.src = campusPhoto;
  pending = import('./LandingPage').then((module) => {
    loaded = module.default;
    return module;
  });
  return pending;
}

/** Whether the landing page has already been fetched. */
export const landingLoaded = () => loaded !== null;

/** The fetched landing page; render it only once landingLoaded() is true. */
export function LoadedLanding() {
  return createElement(loaded);
}
