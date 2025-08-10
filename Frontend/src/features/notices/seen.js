// What this device has already seen: kept in localStorage, so the user
// model stays untouched and the unread dot simply shows again on a new device.
import { useSyncExternalStore } from 'react';

export const SEEN_KEY = 'thapargpt:notices-seen';
export const DISMISSED_KEY = 'thapargpt:notice-dismissed';
const CHANGED = 'thapargpt:notices-changed';

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode or full storage: the dot just stays until the next visit.
  }
  window.dispatchEvent(new Event(CHANGED));
}

function subscribe(callback) {
  window.addEventListener(CHANGED, callback);
  window.addEventListener('storage', callback);
  return () => {
    window.removeEventListener(CHANGED, callback);
    window.removeEventListener('storage', callback);
  };
}

/** True when something was posted after the last visit to the Notices page. */
export function hasUnread(latestAt, seenAt) {
  if (!latestAt) return false;
  const latest = Date.parse(latestAt);
  const seen = seenAt ? Date.parse(seenAt) : NaN;
  return Number.isNaN(seen) || latest > seen;
}

export function useNoticesSeen() {
  return useSyncExternalStore(subscribe, () => read(SEEN_KEY), () => null);
}

/** Records the visit up to `latestAt` (the newest notice the page showed), or now. */
export function markNoticesSeen(latestAt) {
  const current = read(SEEN_KEY);
  const next = latestAt || new Date().toISOString();
  if (!current || Date.parse(next) > Date.parse(current)) write(SEEN_KEY, next);
}

export function useDismissedNotice() {
  return useSyncExternalStore(subscribe, () => read(DISMISSED_KEY), () => null);
}

export function dismissNotice(id) {
  write(DISMISSED_KEY, id);
}
