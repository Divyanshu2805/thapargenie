import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ askQuestion: vi.fn(), regenerateAnswer: vi.fn() }));
vi.mock('@/lib/api/chat', () => api);

import { ApiError } from '@/utils/apiClient';
import { initialStreamState, streamReducer, useAskStream } from './use-ask-stream';

async function* events(list) {
  for (const item of list) yield item;
}

const META = { event: 'meta', data: { assistant_message_id: 'a1', remaining_today: 9 } };
const DONE = { event: 'done', data: { message: { id: 'a1', content: 'Fee is ₹2,00,000 [1].', status: 'complete' } } };

describe('streamReducer', () => {
  it('accumulates deltas and moves to writing', () => {
    let state = streamReducer(initialStreamState, { type: 'start', anchor: { kind: 'ask' }, question: 'Q' });
    state = streamReducer(state, { type: 'status', data: { stage: 'searching' } });
    state = streamReducer(state, { type: 'delta', data: { text: 'Hel' } });
    state = streamReducer(state, { type: 'delta', data: { text: 'lo' } });
    expect(state).toMatchObject({ phase: 'streaming', stage: 'writing', text: 'Hello', question: 'Q' });
  });
});

describe('useAskStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('streams events in order and settles as accepted', async () => {
    api.askQuestion.mockReturnValue(
      events([
        META,
        { event: 'status', data: { stage: 'understanding' } },
        { event: 'sources', data: { sources: [{ position: 1, title: 'Fee structure' }] } },
        { event: 'delta', data: { text: 'Fee is ' } },
        DONE,
      ]),
    );
    const onEvent = vi.fn();
    const onSettled = vi.fn();
    const { result } = renderHook(() => useAskStream({ onEvent, onSettled }));

    await act(() => result.current.ask('c1', 'What is the fee?'));

    expect(api.askQuestion).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ content: 'What is the fee?', editOf: undefined }),
      expect.anything(),
    );
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual(['meta', 'status', 'sources', 'delta', 'done']);
    expect(result.current.state).toMatchObject({
      phase: 'done',
      text: 'Fee is ₹2,00,000 [1].',
      sources: [{ position: 1, title: 'Fee structure' }],
      meta: META.data,
    });
    expect(onSettled).toHaveBeenCalledWith({ accepted: true });
  });

  it('passes edit_of and regenerate targets', async () => {
    api.askQuestion.mockReturnValue(events([META, DONE]));
    api.regenerateAnswer.mockReturnValue(events([META, DONE]));
    const { result } = renderHook(() => useAskStream());

    await act(() => result.current.ask('c1', 'Edited', { editOf: 'u1' }));
    expect(api.askQuestion.mock.calls[0][1]).toMatchObject({ content: 'Edited', editOf: 'u1' });
    expect(result.current.state.anchor).toEqual({ kind: 'edit', messageId: 'u1' });

    await act(() => result.current.regenerate('c1', 'a1'));
    expect(api.regenerateAnswer).toHaveBeenCalledWith('a1', expect.objectContaining({ clientRequestId: expect.any(String) }), expect.anything());
    expect(result.current.state.anchor).toEqual({ kind: 'regenerate', messageId: 'a1' });
  });

  it('maps a server error event to a retryable error', async () => {
    api.askQuestion.mockReturnValue(
      events([META, { event: 'error', data: { code: 'llm_unavailable', message: 'Unavailable.', retryable: true } }]),
    );
    const onSettled = vi.fn();
    const { result } = renderHook(() => useAskStream({ onSettled }));

    await act(() => result.current.ask('c1', 'Q'));

    expect(result.current.state).toMatchObject({
      phase: 'error',
      error: { code: 'llm_unavailable', message: 'Unavailable.', retryable: true },
    });
    expect(onSettled).toHaveBeenCalledWith({ accepted: true });
  });

  it('marks a quota rejection as not retryable and not accepted', async () => {
    api.askQuestion.mockImplementation(async function* reject() {
      yield* [];
      throw new ApiError('Limit reached.', { code: 'daily_quota_exceeded', status: 429 });
    });
    const onSettled = vi.fn();
    const { result } = renderHook(() => useAskStream({ onSettled }));

    await act(() => result.current.ask('c1', 'Q'));

    expect(result.current.state.error).toMatchObject({ code: 'daily_quota_exceeded', retryable: false });
    expect(onSettled).toHaveBeenCalledWith({ accepted: false });
  });

  it('retries with the same request id until the server accepts the turn', async () => {
    api.askQuestion
      .mockImplementationOnce(async function* fail() {
        yield* [];
        throw new ApiError('Offline.', { code: 'network_error' });
      })
      .mockReturnValueOnce(events([META, { event: 'error', data: { code: 'internal_error', message: 'x', retryable: true } }]))
      .mockReturnValueOnce(events([META, DONE]));
    const { result } = renderHook(() => useAskStream());

    await act(() => result.current.ask('c1', 'Q'));
    await act(() => result.current.retry());
    await act(() => result.current.retry());

    const ids = api.askQuestion.mock.calls.map((call) => call[1].clientRequestId);
    // Not received → same id (the server de-duplicates); accepted but failed → a new turn.
    expect(ids[1]).toBe(ids[0]);
    expect(ids[2]).not.toBe(ids[1]);
    expect(result.current.state.phase).toBe('done');
  });

  it('stops without settling', async () => {
    let release;
    api.askQuestion.mockImplementation(async function* slow(_id, _body, { signal }) {
      yield META;
      await new Promise((resolve) => {
        release = resolve;
        signal.addEventListener('abort', resolve);
      });
      if (signal.aborted) throw new ApiError('Cancelled.', { code: 'request_cancelled' });
    });
    const onSettled = vi.fn();
    const { result } = renderHook(() => useAskStream({ onSettled }));

    let pending;
    act(() => {
      pending = result.current.ask('c1', 'Q');
    });
    await waitFor(() => expect(result.current.state.meta).not.toBeNull());
    await act(async () => {
      result.current.stop();
      await pending;
    });

    expect(release).toBeDefined();
    expect(result.current.state.phase).toBe('stopped');
    expect(onSettled).not.toHaveBeenCalled();
  });
});
