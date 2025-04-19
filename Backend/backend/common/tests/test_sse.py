import json
import threading
import time

from django.test import SimpleTestCase

from common.sse import event_stream_response, format_event, with_heartbeat


def parse(frame):
    lines = frame.decode().strip().split('\n')
    return lines[0].removeprefix('event: '), json.loads(lines[1].removeprefix('data: '))


class SSETests(SimpleTestCase):
    def test_format_event(self):
        frame = format_event('delta', {'text': 'नमस्ते'})
        self.assertEqual(frame, 'event: delta\ndata: {"text":"नमस्ते"}\n\n'.encode())

    def test_frames_follow_source_order(self):
        events = iter([('meta', {'id': 1}), ('delta', {'text': 'hi'}), ('done', {})])
        frames = list(with_heartbeat(events, interval=5))
        self.assertEqual([parse(f)[0] for f in frames], ['meta', 'delta', 'done'])

    def test_heartbeat_while_source_is_slow(self):
        def slow():
            time.sleep(0.3)
            yield 'done', {}

        frames = list(with_heartbeat(slow(), interval=0.05))
        self.assertTrue(frames[0].startswith(b': ping'))
        self.assertEqual(parse(frames[-1])[0], 'done')

    def test_source_error_is_raised_in_response_thread(self):
        def broken():
            yield 'meta', {}
            raise RuntimeError('upstream failed')

        stream = with_heartbeat(broken(), interval=5)
        next(stream)
        with self.assertRaisesRegex(RuntimeError, 'upstream failed'):
            next(stream)

    def test_client_disconnect_closes_source(self):
        closed = threading.Event()
        release = threading.Event()

        def source():
            try:
                yield 'meta', {}
                release.wait(2)
                yield 'delta', {'text': 'late'}
                yield 'delta', {'text': 'never sent'}
            finally:
                closed.set()

        stream = with_heartbeat(source(), interval=5)
        next(stream)
        stream.close()  # what WSGI does when the client goes away
        release.set()
        self.assertTrue(closed.wait(2))

    def test_response_headers(self):
        response = event_stream_response(iter([]))
        self.assertEqual(response['Content-Type'], 'text/event-stream; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'no-cache, no-transform')
        self.assertEqual(response['X-Accel-Buffering'], 'no')
