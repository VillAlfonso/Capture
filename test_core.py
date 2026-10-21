import unittest
from unittest.mock import patch
import io
import json
import urllib.error
import socket
import threading
from types import SimpleNamespace
from core import Buffer, extract_code, generate, rectangle, api_error_summary, RequestControl, RequestCancelled


def response(text, reason='STOP'):
    return {'candidates': [{'finishReason': reason, 'content': {'parts': [{'text': text}]}}]}


class CoreTests(unittest.TestCase):
    def test_cancel_interrupts_blocked_socket_read(self):
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        control = RequestControl()
        control.attach(SimpleNamespace(sock=left, close=left.close))
        finished = threading.Event()
        def read():
            try:
                left.recv(1)
            except OSError:
                pass
            finally:
                finished.set()
        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        control.cancel()
        self.assertTrue(finished.wait(2))
        with self.assertRaises(RequestCancelled):
            control.check()
        with self.assertRaises(RequestCancelled):
            control.open(None)

    def test_quota_diagnostics_do_not_expose_raw_messages(self):
        body = {'error': {'status': 'RESOURCE_EXHAUSTED', 'message': 'secret-key screenshot text',
                         'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure'},
                                     {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '12s'}]}}
        error = urllib.error.HTTPError('https://example.test', 429, 'secret-key', {}, io.BytesIO(json.dumps(body).encode()))
        output = ' '.join(api_error_summary(error))
        self.assertIn('HTTP 429', output)
        self.assertIn('quota violation', output)
        self.assertIn('12s', output)
        self.assertNotIn('secret-key', output)
        self.assertNotIn('screenshot', output)

    def test_malformed_api_error_preserves_http_status(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'failed', {}, io.BytesIO(b'<html>unavailable</html>'))
        output = ' '.join(api_error_summary(error))
        self.assertIn('HTTP 503', output)
        self.assertIn('Structured error details unavailable', output)

    def test_reverse_drag_and_negative_monitor_coordinates(self):
        self.assertEqual(rectangle((100, 80), (-400, -100)), (-400, -100, 100, 80))
        with self.assertRaises(ValueError):
            rectangle((0, 0), (2, 9))

    def test_fences_indentation_and_thoughts(self):
        data = response('```python\ndef f():\n\treturn 1\n```')
        data['candidates'][0]['content']['parts'].insert(0, {'thought': True, 'text': 'private reasoning'})
        self.assertEqual(extract_code(data), 'def f():\n    return 1')

    def test_incomplete_or_blocked_response_is_never_typed(self):
        for data in ({}, response('x', 'MAX_TOKENS'), response(''), response('```python\nx'), response('a\x00b')):
            with self.assertRaises(ValueError):
                extract_code(data)

    def test_old_network_response_cannot_replace_new_capture(self):
        buffer = Buffer()
        old = buffer.epoch
        buffer.reset()
        self.assertFalse(buffer.accept(old, 'stale'))
        self.assertEqual(buffer.peek(), '')

    def test_character_consumption_waiting_and_exhaustion(self):
        buffer = Buffer()
        self.assertEqual(buffer.peek(), '')
        buffer.accept(buffer.epoch, 'a\n\U0001f600')
        for expected in ('a', '\n', '\U0001f600'):
            self.assertEqual(buffer.peek(), expected)
            buffer.advance()
        self.assertEqual(buffer.peek(), '')
        buffer.advance()
        self.assertEqual(buffer.index, 3)

    def test_request_contains_image_and_uses_header_for_secret(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response('x=1')).encode())) as call:
            self.assertEqual(generate(b'png', 'test-secret', 'gemini-test', 'Python 3'), 'x=1')
        self.assertIn('timeout', call.call_args.kwargs)
        self.assertIsNone(call.call_args.kwargs['timeout'])
        request = call.call_args.args[0]
        self.assertNotIn('test-secret', request.full_url)
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-secret')
        payload = json.loads(request.data)
        self.assertEqual(payload['contents'][0]['parts'][1]['inline_data']['data'], 'cG5n')


if __name__ == '__main__':
    unittest.main()

