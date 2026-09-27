const resetCallbacks = new Set();

const USER_STORAGE_KEYS = [
  'thapargenie:active-conversation',
  'thapargenie:conversation-cache',
  'thapargenie:draft',
  'thapargenie:message-cache',
];

export function registerUserStateReset(callback) {
  resetCallbacks.add(callback);
  return () => resetCallbacks.delete(callback);
}

export function clearUserSpecificState() {
  for (const callback of resetCallbacks) callback();

  if (typeof window === 'undefined') return;
  for (const key of USER_STORAGE_KEYS) {
    window.localStorage.removeItem(key);
    window.sessionStorage.removeItem(key);
  }
}
