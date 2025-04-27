import { describe, expect, it } from 'vitest';

import { buildThread, hasStreamingMessage } from './thread';
import { initialStreamState } from './use-ask-stream';

const saved = [
  { id: 'u1', role: 'user', content: 'Q1' },
  { id: 'a1', role: 'assistant', content: 'A1', status: 'complete' },
  { id: 'u2', role: 'user', content: 'Q2' },
  { id: 'a2', role: 'assistant', content: 'A2', status: 'complete' },
];

const streaming = (anchor, extra = {}) => ({
  ...initialStreamState,
  phase: 'streaming',
  anchor,
  question: 'New',
  text: 'Part',
  ...extra,
});

describe('buildThread', () => {
  it('returns the saved thread when idle', () => {
    expect(buildThread(saved, initialStreamState)).toBe(saved);
  });

  it('appends a pending question and live answer for a new ask', () => {
    const thread = buildThread(saved, streaming({ kind: 'ask' }));
    expect(thread.map((message) => message.id ?? message.key)).toEqual(['u1', 'a1', 'u2', 'a2', 'live-question', 'live-answer']);
    expect(thread.at(-1)).toMatchObject({ role: 'assistant', status: 'streaming', content: 'Part' });
  });

  it('replaces an edited question and everything after it', () => {
    const thread = buildThread(saved, streaming({ kind: 'edit', messageId: 'u2' }));
    expect(thread.map((message) => message.id ?? message.key)).toEqual(['u1', 'a1', 'live-question', 'live-answer']);
    expect(thread[2].content).toBe('New');
  });

  it('replaces only the regenerated answer', () => {
    const thread = buildThread(saved, streaming({ kind: 'regenerate', messageId: 'a2' }));
    expect(thread.map((message) => message.id ?? message.key)).toEqual(['u1', 'a1', 'u2', 'live-answer']);
  });

  it('uses the saved message once done and shows errors', () => {
    const done = buildThread(saved, streaming({ kind: 'ask' }, { phase: 'done', message: { id: 'a3', content: 'Full', status: 'complete', sources: [] } }));
    expect(done.at(-1)).toMatchObject({ id: 'a3', content: 'Full', status: 'complete' });

    const failed = buildThread(saved, streaming({ kind: 'ask' }, { phase: 'error', error: { message: 'Busy' } }));
    expect(failed.at(-1)).toMatchObject({ status: 'failed', error: { message: 'Busy' } });
  });

  it('detects unfinished answers', () => {
    expect(hasStreamingMessage(saved)).toBe(false);
    expect(hasStreamingMessage([...saved, { id: 'a9', status: 'streaming' }])).toBe(true);
  });
});
