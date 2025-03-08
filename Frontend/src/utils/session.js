const resetCallbacks = new Set();

const USER_STORAGE_KEYS = [
  'thapargpt:active-conversation',
  'thapargpt:conversation-cache',
  'thapargpt:draft',
  'thapargpt:message-cache',
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
