import { describe, expect, it } from 'vitest';

import { createSseParser, readSseEvents } from './sse';

function collect(chunks) {
  const events = [];
  const parser = createSseParser((event) => events.push(event));
  for (const chunk of chunks) parser.push(chunk);
  parser.end();
  return events;
}

function streamOf(chunks) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe('SSE parser', () => {
  it('parses named events with JSON data', () => {
    expect(collect(['event: meta\ndata: {"conversation_id":"c1"}\n\n'])).toEqual([
      { event: 'meta', data: { conversation_id: 'c1' } },
    ]);
  });

  it('reassembles events split across arbitrary chunk boundaries', () => {
    const text = 'event: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"text":"lo"}\n\n';
    const chunks = text.split('');
    expect(collect(chunks).map((event) => event.data.text)).toEqual(['Hel', 'lo']);
  });

  it('ignores heartbeat comments and handles CRLF split between chunks', () => {
    const events = collect([': ping\r', '\n\r\nevent: done\r', '\ndata: {"ok":true}\r\n\r', '\n']);
    expect(events).toEqual([{ event: 'done', data: { ok: true } }]);
  });

  it('joins multi-line data and defaults the event name to message', () => {
    expect(collect(['data: line one\ndata: line two\n\n'])).toEqual([
      { event: 'message', data: 'line one\nline two' },
    ]);
  });

  it('discards an event cut off before its terminating blank line', () => {
    expect(collect(['event: done\ndata: {"partial":'])).toEqual([]);
  });

  it('reads events from a byte stream', async () => {
    const events = [];
    const body = streamOf(['event: status\ndata: {"stage":"search', 'ing"}\n\n', ': ping\n\n']);
    for await (const event of readSseEvents(body)) events.push(event);
    expect(events).toEqual([{ event: 'status', data: { stage: 'searching' } }]);
  });
});
