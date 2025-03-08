import { describe, expect, it, vi } from 'vitest';

vi.mock('../utils/session', () => ({ registerUserStateReset: () => () => {} }));

import { shouldRetry } from './query-client';

describe('query retry policy', () => {
  it('retries transient failures at most twice', () => {
    const networkError = { code: 'network_error', status: 0 };
    expect(shouldRetry(0, networkError)).toBe(true);
    expect(shouldRetry(1, { status: 503 })).toBe(true);
    expect(shouldRetry(2, networkError)).toBe(false);
  });

  it('never retries client errors or cancellations', () => {
    for (const status of [400, 401, 403, 404, 429]) expect(shouldRetry(0, { status })).toBe(false);
    expect(shouldRetry(0, { code: 'request_cancelled', status: 0 })).toBe(false);
  });
});
