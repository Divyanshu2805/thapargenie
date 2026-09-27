import { beforeEach, describe, expect, it, vi } from 'vitest';

import { clearUserSpecificState, registerUserStateReset } from './session';

describe('user-specific state clearing', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('clears registered stores and known draft/cache keys without clearing unrelated data', () => {
    const reset = vi.fn();
    const unregister = registerUserStateReset(reset);
    localStorage.setItem('thapargenie:conversation-cache', 'user-a');
    sessionStorage.setItem('thapargenie:draft', 'private draft');
    localStorage.setItem('unrelated', 'keep');

    clearUserSpecificState();

    expect(reset).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('thapargenie:conversation-cache')).toBeNull();
    expect(sessionStorage.getItem('thapargenie:draft')).toBeNull();
    expect(localStorage.getItem('unrelated')).toBe('keep');
    unregister();
  });
});
