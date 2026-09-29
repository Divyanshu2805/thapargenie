import { firebaseAuth } from '../config/firebase';
import { API_BASE_URL } from './constants';
import { registerUserStateReset } from './session';

const DEFAULT_TIMEOUT_MS = 10_000;
const SAFE_RETRY_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);
const activeControllers = new Set();
// The X-Request-ID each response was sent with, for errors that arrive without an envelope.
const sentRequestIds = new WeakMap();

registerUserStateReset(() => {
  for (const controller of activeControllers) controller.abort('Authentication state changed.');
  activeControllers.clear();
});

export class ApiError extends Error {
  constructor(message, { code = 'request_failed', status = 0, fields = null, requestId = null, timedOut = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.fields = fields;
    this.requestId = requestId;
    // True when our own timeout fired, as opposed to a cancel from the caller.
    this.timedOut = timedOut;
  }
}

function buildUrl(path) {
  return new URL(path.replace(/^\//, ''), API_BASE_URL).toString();
}

// A random id per HTTP request, echoed by the server in its logs and error bodies.
export function newRequestId() {
  return globalThis.crypto?.randomUUID?.() ?? null;
}

export function rememberRequestId(response, requestId) {
  if (requestId && response) sentRequestIds.set(response, requestId);
  return response;
}

export function sentRequestId(response) {
  return sentRequestIds.get(response) ?? null;
}

function createRequestController(externalSignal, timeoutMs) {
  const controller = new AbortController();
  const abortFromExternalSignal = () => controller.abort(externalSignal.reason);
  externalSignal?.addEventListener('abort', abortFromExternalSignal, { once: true });
  const timeoutId = window.setTimeout(() => controller.abort('Request timed out.'), timeoutMs);

  return {
    controller,
    cleanup() {
      window.clearTimeout(timeoutId);
      externalSignal?.removeEventListener('abort', abortFromExternalSignal);
    },
  };
}

async function responsePayload(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return null;
  return response.json();
}

function toApiError(response, payload) {
  const error = payload?.error;
  return new ApiError(error?.message || 'The request could not be completed.', {
    code: error?.code,
    status: response.status,
    fields: error?.fields,
    requestId: error?.request_id || sentRequestId(response),
  });
}

async function authenticatedFetch(path, options, forceRefresh) {
  const user = firebaseAuth?.currentUser;
  if (!user) {
    throw new ApiError('Sign in is required.', { code: 'unauthenticated', status: 401 });
  }

  const token = await user.getIdToken(forceRefresh);
  const requestId = newRequestId();
  const response = await fetch(buildUrl(path), {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
      ...(requestId ? { 'X-Request-ID': requestId } : {}),
      Authorization: `Bearer ${token}`,
    },
  });
  return rememberRequestId(response, requestId);
}

async function performAuthenticatedRequest(
  path,
  { method = 'GET', body, headers, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {},
) {
  const normalizedMethod = method.toUpperCase();
  const canRetryAuthentication = SAFE_RETRY_METHODS.has(normalizedMethod);
  const { controller, cleanup } = createRequestController(signal, timeoutMs);
  activeControllers.add(controller);

  const options = {
    method: normalizedMethod,
    headers,
    signal: controller.signal,
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };

  try {
    let response = await authenticatedFetch(path, options, false);
    if (response.status === 401 && canRetryAuthentication && !controller.signal.aborted) {
      response = await authenticatedFetch(path, options, true);
    }
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      const timedOut = controller.signal.reason === 'Request timed out.';
      throw new ApiError(
        timedOut ? 'The server took too long to respond.' : 'The request was cancelled.',
        { code: 'request_cancelled', timedOut },
      );
    }
    throw new ApiError('The service is currently unreachable.', { code: 'network_error' });
  } finally {
    activeControllers.delete(controller);
    cleanup();
  }
}

export async function apiRequest(
  path,
  { method = 'GET', body, headers, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {},
) {
  const response = await performAuthenticatedRequest(path, {
    method,
    body,
    headers,
    signal,
    timeoutMs,
  });
  const payload = await responsePayload(response);
  if (!response.ok) throw toApiError(response, payload);
  return payload;
}

export async function apiBlobRequest(path, options = {}) {
  const response = await performAuthenticatedRequest(path, options);
  if (!response.ok) throw toApiError(response, await responsePayload(response));
  return {
    blob: await response.blob(),
    contentDisposition: response.headers.get('content-disposition') || '',
  };
}

export const getCurrentUserProfile = (options) => apiRequest('me/', options);
