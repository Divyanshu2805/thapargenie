"""Server-sent events over a plain WSGI streaming response.

The event source (the answer pipeline) runs in a worker thread so the response can
send keep-alive comments while it waits on slow upstream calls. When the client goes
away, WSGI closes our generator; we then close the event source from its own thread,
which raises GeneratorExit at its current `yield` so it can save partial work.
"""

import json
import queue
import threading

from django.conf import settings
from django.db import connections
from django.http import StreamingHttpResponse

HEARTBEAT_SECONDS = 15.0

_DONE = object()


class _Failure:
    def __init__(self, exc):
        self.exc = exc


def format_event(event, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=str)
    return f'event: {event}\ndata: {payload}\n\n'.encode()


def format_comment(text='ping'):
    return f': {text}\n\n'.encode()


def with_heartbeat(events, interval=HEARTBEAT_SECONDS):
    """Yield encoded SSE frames from an iterator of (event, data) pairs."""
    frames = queue.Queue()
    cancelled = threading.Event()

    def pump():
        try:
            for item in events:
                if cancelled.is_set():
                    break
                frames.put(item)
        except Exception as exc:  # re-raised in the response thread
            frames.put(_Failure(exc))
        finally:
            close = getattr(events, 'close', None)
            if close is not None:
                close()
            connections.close_all()
            frames.put(_DONE)

    threading.Thread(target=pump, name='sse-pump', daemon=True).start()
    try:
        while True:
            try:
                item = frames.get(timeout=interval)
            except queue.Empty:
                yield format_comment()
                continue
            if item is _DONE:
                return
            if isinstance(item, _Failure):
                raise item.exc
            yield format_event(*item)
    finally:
        cancelled.set()


def _inline(events):
    try:
        for item in events:
            yield format_event(*item)
    finally:
        close = getattr(events, 'close', None)
        if close is not None:
            close()


def event_stream_response(events, *, status=200, interval=HEARTBEAT_SECONDS):
    # Tests stream inline: a worker thread would use its own DB connection and not see
    # the test transaction. The threaded path is covered in common/tests/test_sse.py.
    frames = _inline(events) if settings.SSE_INLINE else with_heartbeat(events, interval)
    response = StreamingHttpResponse(
        frames,
        status=status,
        content_type='text/event-stream; charset=utf-8',
    )
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response
