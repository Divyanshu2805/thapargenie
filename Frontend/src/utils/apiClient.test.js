import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: { currentUser: null },
  getIdToken: vi.fn(),
  resetCallback: null,
}));

vi.mock('../config/firebase', () => ({ firebaseAuth: mocks.auth }));
vi.mock('./session', () => ({
  registerUserStateReset: (callback) => {
    mocks.resetCallback = callback;
    return () => {};
  },
}));

import { ApiError, apiRequest } from './apiClient';
import { API_BASE_URL } from './constants';

function jsonResponse(status, body) {
  return {
    headers: { get: () => 'application/json' },
    json: async () => body,
    ok: status >= 200 && status < 300,
    status,
  };
}

describe('authenticated API client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.auth.currentUser = { getIdToken: mocks.getIdToken };
    mocks.getIdToken.mockResolvedValue('firebase-id-token');
    globalThis.fetch = vi.fn();
  });

  it('sends the current Firebase ID token as bearer authentication', async () => {
    fetch.mockResolvedValue(jsonResponse(200, { onboarding_status: 'ready' }));

    await apiRequest('me/');

    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}me/`,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer firebase-id-token' }),
      }),
    );
  });

  it('sends a fresh X-Request-ID with every request', async () => {
    fetch.mockResolvedValue(jsonResponse(200, {}));

    await apiRequest('me/');
    await apiRequest('me/');

    const [first, second] = fetch.mock.calls.map(([, init]) => init.headers['X-Request-ID']);
    expect(first).toMatch(/^[0-9a-f-]{36}$/);
    expect(second).toMatch(/^[0-9a-f-]{36}$/);
    expect(first).not.toBe(second);
  });

  it('falls back to the sent request id when the error has no envelope', async () => {
    fetch.mockResolvedValue({ headers: { get: () => 'text/html' }, ok: false, status: 502 });

    const error = await apiRequest('me/').catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.requestId).toBe(fetch.mock.calls[0][1].headers['X-Request-ID']);
  });

  it('force-refreshes once after a 401 for a safe request', async () => {
    fetch
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'unauthenticated', message: 'Expired.' } }))
      .mockResolvedValueOnce(jsonResponse(200, { onboarding_status: 'ready' }));

    await expect(apiRequest('me/')).resolves.toEqual({ onboarding_status: 'ready' });
    expect(mocks.getIdToken).toHaveBeenNthCalledWith(1, false);
    expect(mocks.getIdToken).toHaveBeenNthCalledWith(2, true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('never replays an answer-creation POST after a 401', async () => {
    fetch.mockResolvedValue(
      jsonResponse(401, { error: { code: 'unauthenticated', message: 'Expired.' } }),
    );

    await expect(apiRequest('conversations/abc/answers/', {
      method: 'POST',
      body: { question: 'When is registration?' },
    })).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(mocks.getIdToken).toHaveBeenCalledTimes(1);
  });
});
