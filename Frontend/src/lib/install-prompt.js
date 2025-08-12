// "Install app". Chrome and Edge fire `beforeinstallprompt` once, early, so
// it is captured at start-up and kept until the user asks. iPhone/iPad Safari has no
// prompt: there the menu explains Share → Add to Home Screen instead.
import { useSyncExternalStore } from 'react';

let deferred = null;
let installed = false;
const listeners = new Set();

function notify() {
  for (const listener of listeners) listener();
}

export function listenForInstallPrompt(target = window) {
  target.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferred = event;
    notify();
  });
  target.addEventListener('appinstalled', () => {
    deferred = null;
    installed = true;
    notify();
  });
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function isStandalone(win = window) {
  return Boolean(win.matchMedia?.('(display-mode: standalone)').matches || win.navigator?.standalone);
}

export function isIosSafari(nav = navigator) {
  const ios = /iPad|iPhone|iPod/.test(nav.userAgent) || (nav.platform === 'MacIntel' && nav.maxTouchPoints > 1);
  // Other iOS browsers (CriOS, FxiOS, EdgiOS) can't add to the home screen themselves.
  return ios && !/CriOS|FxiOS|EdgiOS/.test(nav.userAgent);
}

/** `mode`: 'prompt' (the browser's dialog), 'ios' (show how), or null (hide the item). */
export function useInstallApp() {
  const prompt = useSyncExternalStore(subscribe, () => deferred, () => null);
  const done = useSyncExternalStore(subscribe, () => installed, () => false);
  let mode = null;
  if (!done && !isStandalone()) {
    if (prompt) mode = 'prompt';
    else if (isIosSafari()) mode = 'ios';
  }
  const install = async () => {
    if (!deferred) return;
    const event = deferred;
    deferred = null;
    notify();
    await event.prompt();
  };
  return { mode, install };
}
