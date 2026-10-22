import unittest
from unittest.mock import patch
import io
import json
import urllib.error
import socket
import threading
from types import SimpleNamespace
from core import Buffer, extract_code, generate, rectangle, api_error_summary, RequestControl, RequestCancelled, validate_source


def response(text, reason='STOP'):
    return {'status': 'completed' if reason == 'STOP' else 'incomplete',
            'incomplete_details': {'reason': 'max_output_tokens'},
            'output': [{'type': 'message', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': text}]}]}


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
        body = {'error': {'code': 'insufficient_quota', 'message': 'secret-key screenshot text'}}
        error = urllib.error.HTTPError('https://example.test', 429, 'secret-key', {'Retry-After': '12'}, io.BytesIO(json.dumps(body).encode()))
        output = ' '.join(api_error_summary(error))
        self.assertIn('HTTP 429', output)
        self.assertIn('quota/billing', output)
        self.assertIn('12 seconds', output)
        self.assertNotIn('secret-key', output)
        self.assertNotIn('screenshot', output)

    def test_malformed_api_error_preserves_http_status(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'failed', {}, io.BytesIO(b'<html>unavailable</html>'))
        output = ' '.join(api_error_summary(error))
        self.assertIn('HTTP 503', output)
        self.assertIn('Structured error details unavailable', output)

    def test_complete_long_response_is_not_capped(self):
        text = 'x=1\n' * 30000
        self.assertEqual(extract_code(response(text)), text.strip())

    def test_provider_truncation_logs_and_rejects_partial_code(self):
        with self.assertLogs('quiet-capture', level='ERROR') as logs:
            with self.assertRaises(ValueError):
                extract_code(response('partial', 'MAX_TOKENS'))
        self.assertIn('output token limit', ' '.join(logs.output))

    def test_python_syntax_checked_without_execution(self):
        text = 'raise RuntimeError("must not execute")'
        self.assertEqual(validate_source(text, 'Python 3'), text)
        for invalid in ('def f():\n    a=1\n        b=2', 'x = [1,2', 'return 1'):
            with self.assertLogs('quiet-capture', level='ERROR'):
                with self.assertRaises(ValueError):
                    validate_source(invalid, 'Python 3')
        self.assertEqual(validate_source('int main() {}', 'C++'), 'int main() {}')

    def test_refusal_and_incomplete_messages_rejected(self):
        data = response('x=1')
        data['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]
        with self.assertRaises(ValueError):
            extract_code(data)
        data = response('x=1')
        data['output'][0]['status'] = 'incomplete'
        with self.assertRaises(ValueError):
            extract_code(data)

    def test_reverse_drag_and_negative_monitor_coordinates(self):
        self.assertEqual(rectangle((100, 80), (-400, -100)), (-400, -100, 100, 80))
        with self.assertRaises(ValueError):
            rectangle((0, 0), (2, 9))

    def test_fences_indentation_and_thoughts(self):
        data = response('```python\ndef f():\n\treturn 1\n```')
        data['output'].insert(0, {'type': 'reasoning', 'summary': []})
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
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
        payload = json.loads(request.data)
        self.assertFalse(payload['store'])
        self.assertEqual(payload['input'][0]['content'][1]['image_url'], 'data:image/png;base64,cG5n')


if __name__ == '__main__':
    unittest.main()

