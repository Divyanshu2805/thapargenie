import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  auth: { currentUser: null },
  getIdToken: vi.fn(),
  resetCallbacks: [],
}));

vi.mock('../config/firebase', () => ({ firebaseAuth: mocks.auth }));
vi.mock('../utils/session', () => ({
  registerUserStateReset: (callback) => {
    mocks.resetCallbacks.push(callback);
    return () => {};
  },
}));

import { ApiError } from '../utils/apiClient';
import { API_BASE_URL } from '../utils/constants';
import { streamRequest, uploadRequest } from './http';

function sseResponse(text, status = 200) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(text));
        controller.close();
      },
    }),
    { status, headers: { 'content-type': 'text/event-stream' } },
  );
}

function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

async function drain(iterator) {
  const events = [];
  for await (const event of iterator) events.push(event);
  return events;
}

describe('streamRequest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.auth.currentUser = { getIdToken: mocks.getIdToken };
    mocks.getIdToken.mockResolvedValue('token-1');
    globalThis.fetch = vi.fn();
  });

  it('posts JSON with a bearer token and yields parsed events', async () => {
    fetch.mockResolvedValue(sseResponse('event: meta\ndata: {"a":1}\n\nevent: done\ndata: {}\n\n'));

    const events = await drain(streamRequest('conversations/c1/messages/', { content: 'Hi' }));

    expect(events.map((event) => event.event)).toEqual(['meta', 'done']);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(new URL('conversations/c1/messages/', API_BASE_URL).toString());
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"content":"Hi"}');
    expect(init.headers.Authorization).toBe('Bearer token-1');
    expect(init.headers.Accept).toBe('text/event-stream, application/json');
    expect(init.headers['X-Request-ID']).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('uses the sent request id when an error has no envelope', async () => {
    fetch.mockResolvedValue(new Response('Bad gateway', { status: 502, headers: { 'content-type': 'text/html' } }));

    const error = await drain(streamRequest('x/', {})).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.requestId).toBe(fetch.mock.calls[0][1].headers['X-Request-ID']);
  });

  it('retries once with a forced token refresh on 401', async () => {
    mocks.getIdToken.mockResolvedValueOnce('stale').mockResolvedValueOnce('fresh');
    fetch
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'invalid_identity_token' } }))
      .mockResolvedValueOnce(sseResponse('event: done\ndata: {}\n\n'));

    await drain(streamRequest('x/', {}));

    expect(mocks.getIdToken).toHaveBeenNthCalledWith(2, true);
    expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer fresh');
  });

  it('turns an error envelope into an ApiError with retry-after', async () => {
    fetch.mockResolvedValue(
      jsonResponse(429, { error: { code: 'daily_quota_exceeded', message: 'Limit reached.', request_id: 'r1' } }, {
        'retry-after': '120',
      }),
    );

    const error = await drain(streamRequest('x/', {})).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'daily_quota_exceeded', status: 429, requestId: 'r1', retryAfterSeconds: 120 });
  });

  it('reports a cancelled request when the caller aborts', async () => {
    const controller = new AbortController();
    fetch.mockImplementation((_url, init) =>
      new Promise((_resolve, reject) => {
        init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }),
    );

    const pending = drain(streamRequest('x/', {}, { signal: controller.signal }));
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    controller.abort();

    await expect(pending).rejects.toMatchObject({ code: 'request_cancelled' });
  });

  it('aborts open streams when the signed-in user changes', async () => {
    let seenSignal;
    fetch.mockImplementation((_url, init) => {
      seenSignal = init.signal;
      return new Promise(() => {});
    });

    drain(streamRequest('x/', {})).catch(() => {});
    await vi.waitFor(() => expect(seenSignal).toBeDefined());
    for (const callback of mocks.resetCallbacks) callback();

    expect(seenSignal.aborted).toBe(true);
  });

  it('requires a signed-in user', async () => {
    mocks.auth.currentUser = null;
    await expect(drain(streamRequest('x/', {}))).rejects.toMatchObject({ code: 'unauthenticated' });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('uploadRequest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.auth.currentUser = { getIdToken: mocks.getIdToken };
    mocks.getIdToken.mockResolvedValue('token-1');
    globalThis.fetch = vi.fn();
  });

  it('sends FormData untouched so the browser sets the multipart boundary', async () => {
    fetch.mockResolvedValue(jsonResponse(202, { results: [] }));
    const form = new FormData();
    form.append('title', 'Fees');

    const payload = await uploadRequest('admin/documents/', form);

    const [, init] = fetch.mock.calls[0];
    expect(init.body).toBe(form);
    expect(init.headers['Content-Type']).toBeUndefined();
    expect(payload).toEqual({ results: [] });
  });

  it('surfaces validation errors', async () => {
    fetch.mockResolvedValue(jsonResponse(400, { error: { code: 'duplicate_document', message: 'Already uploaded.' } }));
    await expect(uploadRequest('admin/documents/', new FormData())).rejects.toMatchObject({
      code: 'duplicate_document',
      status: 400,
    });
  });
});
