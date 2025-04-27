// Incremental parser for `text/event-stream` bodies (the subset the API emits:
// `event:`, multi-line `data:`, and `:` comments used as heartbeats).
// EventSource can't send an Authorization header, so streams are read with fetch.

export function createSseParser(onEvent) {
  let buffer = '';
  let eventName = '';
  let dataLines = [];

  function dispatch() {
    if (dataLines.length === 0) {
      eventName = '';
      return;
    }
    const raw = dataLines.join('\n');
    let data = raw;
    try {
      data = JSON.parse(raw);
    } catch {
      // Non-JSON payloads are passed through as text.
    }
    onEvent({ event: eventName || 'message', data });
    eventName = '';
    dataLines = [];
  }

  function processLine(line) {
    if (line === '') {
      dispatch();
      return;
    }
    if (line.startsWith(':')) return;
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? '' : line.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') eventName = value;
    else if (field === 'data') dataLines.push(value);
  }

  return {
    push(chunk) {
      buffer += chunk;
      // A trailing `\r` might be the first half of `\r\n`; hold it back until the next chunk.
      const held = buffer.endsWith('\r') ? '\r' : '';
      const lines = (held ? buffer.slice(0, -1) : buffer).split(/\r\n|\r|\n/);
      buffer = lines.pop() + held;
      for (const line of lines) processLine(line);
    },
    // Per the SSE spec, an event cut off before its blank line is discarded.
    end() {
      if (buffer === '\r') dispatch();
      buffer = '';
      eventName = '';
      dataLines = [];
    },
  };
}

export async function* readSseEvents(body, { idleTimeoutMs, onIdle } = {}) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  const queue = [];
  const parser = createSseParser((event) => queue.push(event));
  let idleTimer = null;
  const armIdleTimer = () => {
    if (!idleTimeoutMs) return;
    window.clearTimeout(idleTimer);
    idleTimer = window.setTimeout(() => onIdle?.(), idleTimeoutMs);
  };

  try {
    armIdleTimer();
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        parser.end();
        while (queue.length) yield queue.shift();
        return;
      }
      armIdleTimer();
      parser.push(value);
      while (queue.length) yield queue.shift();
    }
  } finally {
    window.clearTimeout(idleTimer);
    reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
