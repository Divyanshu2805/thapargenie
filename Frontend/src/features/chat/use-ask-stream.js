import { useCallback, useEffect, useReducer, useRef } from 'react';

import { askQuestion, regenerateAnswer } from '@/lib/api/chat';

// One in-flight answer. `anchor` says where it sits in the thread:
//   {kind: 'ask'}                      appended after the current leaf
//   {kind: 'edit', messageId}          replaces that user message and everything after it
//   {kind: 'regenerate', messageId}    replaces that assistant message
export const initialStreamState = {
  phase: 'idle', // idle | streaming | done | stopped | error
  anchor: null,
  question: '',
  stage: null,
  stageDetail: null,
  sources: [],
  text: '',
  meta: null,
  message: null,
  error: null,
};

export function streamReducer(state, action) {
  switch (action.type) {
    case 'start':
      return {
        ...initialStreamState,
        phase: 'streaming',
        anchor: action.anchor,
        question: action.question ?? '',
      };
    case 'meta':
      return { ...state, meta: action.data };
    case 'status':
      return { ...state, stage: action.data.stage, stageDetail: action.data.detail ?? null };
    case 'sources':
      return { ...state, sources: action.data.sources || [] };
    case 'delta':
      return { ...state, stage: 'writing', text: state.text + (action.data.text || '') };
    case 'done':
      return { ...state, phase: 'done', message: action.data.message, text: action.data.message?.content ?? state.text };
    case 'stopped':
      return { ...state, phase: 'stopped' };
    case 'error':
      return { ...state, phase: 'error', error: action.error };
    case 'reset':
      return initialStreamState;
    default:
      return state;
  }
}

function newRequestId() {
  return globalThis.crypto.randomUUID();
}

/**
 * Drives one answer stream at a time.
 * `onEvent(event, data)` sees every server event (for cache updates). `onSettled({accepted})`
 * runs once the stream ends for any reason other than a stop; `accepted` means the server
 * saved the turn (a `meta` event arrived), so the thread should be refetched.
 */
export function useAskStream({ onEvent, onSettled } = {}) {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState);
  const controllerRef = useRef(null);
  const lastRequestRef = useRef(null);
  const callbacksRef = useRef({ onEvent, onSettled });

  useEffect(() => {
    callbacksRef.current = { onEvent, onSettled };
  });

  // Leaving the page closes the stream; the server keeps the partial answer as "stopped".
  // The abort waits a tick so React's development double-mount doesn't cancel a live stream.
  const mountedRef = useRef(false);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      window.setTimeout(() => {
        if (!mountedRef.current) controllerRef.current?.abort('Stream closed.');
      }, 0);
    };
  }, []);

  const run = useCallback(async (request) => {
    controllerRef.current?.abort('Superseded.');
    const controller = new AbortController();
    controllerRef.current = controller;
    lastRequestRef.current = request;
    dispatch({ type: 'start', anchor: request.anchor, question: request.content });

    let gotMeta = false;
    let finished = false;
    try {
      const events =
        request.anchor.kind === 'regenerate'
          ? regenerateAnswer(request.anchor.messageId, { clientRequestId: request.clientRequestId }, { signal: controller.signal })
          : askQuestion(
              request.conversationId,
              {
                content: request.content,
                clientRequestId: request.clientRequestId,
                editOf: request.anchor.kind === 'edit' ? request.anchor.messageId : undefined,
              },
              { signal: controller.signal },
            );

      for await (const { event, data } of events) {
        if (controller !== controllerRef.current) return;
        callbacksRef.current.onEvent?.(event, data);
        if (event === 'meta') {
          gotMeta = true;
          dispatch({ type: 'meta', data });
        } else if (event === 'status' || event === 'sources' || event === 'delta') {
          dispatch({ type: event, data });
        } else if (event === 'done') {
          finished = true;
          dispatch({ type: 'done', data });
        } else if (event === 'error') {
          finished = true;
          dispatch({ type: 'error', error: { code: data.code, message: data.message, retryable: data.retryable !== false } });
        }
      }
      if (!finished && controller === controllerRef.current) {
        dispatch({
          type: 'error',
          error: { code: 'network_error', message: 'The connection closed before the answer finished.', retryable: true },
        });
      }
    } catch (error) {
      if (controller !== controllerRef.current) return;
      if (error?.code === 'request_cancelled') {
        dispatch({ type: 'stopped' });
        return;
      }
      dispatch({
        type: 'error',
        error: {
          code: error?.code || 'network_error',
          message: error?.message || 'Something went wrong.',
          retryable: isRetryable(error),
          status: error?.status,
        },
      });
    } finally {
      if (controller === controllerRef.current) {
        controllerRef.current = null;
        // A retry after the server accepted the turn must be a new turn; before that,
        // reusing the id lets the server de-duplicate.
        if (gotMeta && lastRequestRef.current === request) {
          lastRequestRef.current = { ...request, clientRequestId: newRequestId() };
        }
        if (!controller.signal.aborted) callbacksRef.current.onSettled?.({ accepted: gotMeta });
      }
    }
  }, []);

  const ask = useCallback(
    (conversationId, content, { editOf } = {}) =>
      run({
        conversationId,
        content,
        clientRequestId: newRequestId(),
        anchor: editOf ? { kind: 'edit', messageId: editOf } : { kind: 'ask' },
      }),
    [run],
  );

  const regenerate = useCallback(
    (conversationId, assistantMessageId) =>
      run({ conversationId, clientRequestId: newRequestId(), anchor: { kind: 'regenerate', messageId: assistantMessageId } }),
    [run],
  );

  const retry = useCallback(() => {
    if (lastRequestRef.current) run(lastRequestRef.current);
  }, [run]);

  const stop = useCallback(() => controllerRef.current?.abort('Stopped by user.'), []);
  const reset = useCallback(() => dispatch({ type: 'reset' }), []);

  return { state, ask, regenerate, retry, stop, reset };
}

const NOT_RETRYABLE = new Set([
  'daily_quota_exceeded',
  'maintenance',
  'conversation_full',
  'invalid_parent',
  'validation_error',
  'not_found',
  'email_verification_required',
  'eligibility_required',
]);

function isRetryable(error) {
  if (NOT_RETRYABLE.has(error?.code)) return false;
  return !(error?.status >= 400 && error?.status < 500 && error?.status !== 409 && error?.status !== 429);
}
