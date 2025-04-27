// Transport for the two request kinds `utils/apiClient.js` can't carry: SSE streams
// (no fixed timeout, body read incrementally) and multipart uploads. JSON calls keep
// using `apiRequest`. Tokens are obtained the same way, with one forced refresh on 401.
import { firebaseAuth } from '../config/firebase';
import { ApiError, newRequestId, rememberRequestId, sentRequestId } from '../utils/apiClient';
import { API_BASE_URL } from '../utils/constants';
import { registerUserStateReset } from '../utils/session';
import { readSseEvents } from './sse';

const UPLOAD_TIMEOUT_MS = 120_000;
// The server sends a heartbeat every 15 s, so this much silence means the stream is dead.
const STREAM_IDLE_TIMEOUT_MS = 45_000;
const activeControllers = new Set();

registerUserStateReset(() => {
  for (const controller of activeControllers) controller.abort('Authentication state changed.');
  activeControllers.clear();
});

function buildUrl(path) {
  return new URL(path.replace(/^\//, ''), API_BASE_URL).toString();
}

async function authorizedFetch(path, init) {
  const user = firebaseAuth?.currentUser;
  if (!user) throw new ApiError('Sign in is required.', { code: 'unauthenticated', status: 401 });

  const send = async (forceRefresh) => {
    const token = await user.getIdToken(forceRefresh);
    const requestId = newRequestId();
    const response = await fetch(buildUrl(path), {
      ...init,
      headers: {
        ...init.headers,
        ...(requestId ? { 'X-Request-ID': requestId } : {}),
        Authorization: `Bearer ${token}`,
      },
    });
    return rememberRequestId(response, requestId);
  };

  // A 401 means the request was rejected before any work was done, so a retry is safe.
  let response = await send(false);
  if (response.status === 401 && !init.signal?.aborted) response = await send(true);
  return response;
}

async function errorFromResponse(response) {
  let payload = null;
  if ((response.headers.get('content-type') || '').includes('application/json')) {
    payload = await response.json().catch(() => null);
  }
  const error = payload?.error;
  const apiError = new ApiError(error?.message || 'The request could not be completed.', {
    code: error?.code,
    status: response.status,
    fields: error?.fields,
    requestId: error?.request_id || sentRequestId(response),
  });
  const retryAfter = error?.retry_after_seconds ?? Number(response.headers.get('retry-after'));
  if (Number.isFinite(retryAfter) && retryAfter > 0) apiError.retryAfterSeconds = retryAfter;
  // A duplicate upload names the document that already holds this content.
  if (error?.existing_id) apiError.existingId = error.existing_id;
  return apiError;
}

function linkController(externalSignal) {
  const controller = new AbortController();
  const onAbort = () => controller.abort(externalSignal.reason);
  if (externalSignal?.aborted) controller.abort(externalSignal.reason);
  externalSignal?.addEventListener('abort', onAbort, { once: true });
  activeControllers.add(controller);
  return {
    controller,
    release() {
      externalSignal?.removeEventListener('abort', onAbort);
      activeControllers.delete(controller);
    },
  };
}

function toTransportError(error, controller) {
  if (error instanceof ApiError) return error;
  if (controller.signal.aborted) {
    return new ApiError(
      controller.signal.reason === 'Stream idle.'
        ? 'The connection went quiet. Please try again.'
        : 'The request was cancelled.',
      { code: controller.signal.reason === 'Stream idle.' ? 'network_error' : 'request_cancelled' },
    );
  }
  return new ApiError('The service is currently unreachable.', { code: 'network_error' });
}

/**
 * POST `body` as JSON and yield the server-sent events as `{event, data}`.
 * Abort `signal` to stop; the generator then throws an ApiError `request_cancelled`.
 */
export async function* streamRequest(path, body, { signal } = {}) {
  const { controller, release } = linkController(signal);
  try {
    let response;
    try {
      response = await authorizedFetch(path, {
        method: 'POST',
        // The API's content negotiation only knows JSON (errors come back as JSON); the view
        // itself answers with the event stream. Asking for SSE alone gets a 406.
        headers: { Accept: 'text/event-stream, application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(body ?? {}),
        signal: controller.signal,
      });
    } catch (error) {
      throw toTransportError(error, controller);
    }
    if (!response.ok) throw await errorFromResponse(response);
    if (!response.body) throw new ApiError('Streaming is not supported here.', { code: 'network_error' });

    try {
      yield* readSseEvents(response.body, {
        idleTimeoutMs: STREAM_IDLE_TIMEOUT_MS,
        onIdle: () => controller.abort('Stream idle.'),
      });
    } catch (error) {
      throw toTransportError(error, controller);
    }
  } finally {
    // Leaving the loop early (break/return) closes the connection.
    if (!controller.signal.aborted) controller.abort('Stream closed.');
    release();
  }
}

/** Send multipart `formData` (the browser sets the boundary) and return the JSON reply. */
export async function uploadRequest(path, formData, { method = 'POST', signal, timeoutMs = UPLOAD_TIMEOUT_MS } = {}) {
  const { controller, release } = linkController(signal);
  const timer = window.setTimeout(() => controller.abort('Request timed out.'), timeoutMs);
  try {
    let response;
    try {
      response = await authorizedFetch(path, {
        method,
        headers: { Accept: 'application/json' },
        body: formData,
        signal: controller.signal,
      });
    } catch (error) {
      if (controller.signal.reason === 'Request timed out.') {
        throw new ApiError('The upload took too long.', { code: 'request_cancelled' });
      }
      throw toTransportError(error, controller);
    }
    if (!response.ok) throw await errorFromResponse(response);
    if (response.status === 204) return null;
    return response.json();
  } finally {
    window.clearTimeout(timer);
    release();
  }
}
