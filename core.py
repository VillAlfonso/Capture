"""Pure request and buffer logic; no global hooks on import."""
import base64
import json
import logging
import time
import re
import urllib.request
import http.client
import socket
import threading

PROMPT = ('this is a leet code question and I want you to answer this with no comments '
          'and a very creative way to solve the problem, but prioritize getting the job '
          'done and have it functioning and running and solving the question, no other '
          'response except for the raw answer, no thank yous no recommendation just plain answer. '
          'MANDATORY RULE: Do not use any external or third-party libraries, packages, '
          'frameworks, or dependencies whatsoever. Use only language built-ins and '
          'the standard library. The solution must run without installing anything. '
          'MANDATORY RULE: Do not include ASCII art, decorative text, banners, '
          'or ornamental separators. Return only executable source code; normal '
          'code characters and required string literals are allowed.')


def rectangle(start, end):
    left, right = sorted((start[0], end[0]))
    top, bottom = sorted((start[1], end[1]))
    if right - left < 4 or bottom - top < 4:
        raise ValueError('Selection is too small')
    return left, top, right, bottom


def extract_code(response):
    candidates = response.get('candidates', [])
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise ValueError('No complete answer returned')
    parts = candidates[0].get('content', {}).get('parts', [])
    text = ''.join(p.get('text', '') for p in parts if not p.get('thought')).strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != '```':
            raise ValueError('Incomplete code fence')
        text = '\n'.join(lines[1:-1])
    if not text or len(text) > 100000:
        raise ValueError('Empty or oversized response')
    text = text.replace('\r\n', '\n').replace('\r', '\n').expandtabs(4)
    if any(ord(c) < 32 and c != '\n' for c in text):
        raise ValueError('Unexpected control characters')
    return text


def api_error_summary(error):
    """Report allowlisted diagnostic fields, never raw provider text or credentials."""
    hints = {
        400: 'Invalid request, API key, or unsupported configuration.',
        401: 'Authentication failed; check the API key.',
        403: 'Access denied; check API permissions, project access, and region.',
        404: 'Model or endpoint not found; check config.json.',
        429: 'Rate limit or quota exhausted. This alone does not distinguish a short-term limit from daily quota.',
        500: 'Provider internal error.',
        502: 'Gateway error.',
        503: 'Provider unavailable or overloaded.',
        504: 'Provider gateway timeout.',
    }
    result = [f'API ERROR: HTTP {error.code}. ' + hints.get(error.code, 'Request rejected by server.')]
    try:
        payload = json.loads(error.read(65536))
        detail = payload.get('error', {}) if isinstance(payload, dict) else {}
        if not isinstance(detail, dict):
            return result
        status = detail.get('status')
        if status in {'INVALID_ARGUMENT', 'UNAUTHENTICATED', 'PERMISSION_DENIED',
                      'NOT_FOUND', 'RESOURCE_EXHAUSTED', 'INTERNAL', 'UNAVAILABLE',
                      'DEADLINE_EXCEEDED', 'FAILED_PRECONDITION'}:
            result.append('Provider status: ' + status)
        details = detail.get('details', [])
        for item in details if isinstance(details, list) else []:
            if not isinstance(item, dict):
                continue
            kind = item.get('@type')
            if kind == 'type.googleapis.com/google.rpc.QuotaFailure':
                result.append('Provider explicitly reported a quota violation.')
            elif kind == 'type.googleapis.com/google.rpc.RetryInfo':
                delay = item.get('retryDelay', '')
                if isinstance(delay, str) and re.fullmatch(r'[0-9]{1,9}(?:\.[0-9]{1,9})?s', delay):
                    result.append('Provider suggested retry delay: ' + delay + ' (no automatic retry).')
            elif kind == 'type.googleapis.com/google.rpc.ErrorInfo':
                reason = item.get('reason')
                if reason in {'API_KEY_INVALID', 'API_KEY_EXPIRED', 'API_KEY_SERVICE_BLOCKED',
                              'SERVICE_DISABLED', 'BILLING_DISABLED', 'RATE_LIMIT_EXCEEDED',
                              'QUOTA_EXCEEDED', 'CONSUMER_INVALID'}:
                    result.append('Provider reason: ' + reason)
    except Exception:
        result.append('Structured error details unavailable; HTTP status above is still valid.')
    finally:
        error.close()
    return result


class RequestCancelled(Exception):
    pass


class RequestControl:
    def __init__(self):
        self.cancelled = threading.Event()
        self.connection = None
        self.socket = None
        self.lock = threading.Lock()

    def check(self):
        if self.cancelled.is_set():
            raise RequestCancelled()

    def attach(self, connection):
        with self.lock:
            self.check()
            self.connection = connection

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            connection = self.connection
            sock = self.socket or (connection.sock if connection else None)
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if connection:
            connection.close()

    def open(self, request):
        control = self

        class Connection(http.client.HTTPSConnection):
            def connect(self):
                control.check()
                super().connect()
                with control.lock:
                    control.socket = self.sock
                if control.cancelled.is_set():
                    self.close()
                    raise RequestCancelled()

        def factory(*args, **kwargs):
            connection = Connection(*args, **kwargs)
            control.attach(connection)
            return connection

        class Handler(urllib.request.HTTPSHandler):
            def https_open(self, request):
                return self.do_open(factory, request, context=self._context)

        self.check()
        return urllib.request.build_opener(Handler()).open(request, timeout=None)


def generate(png, key, model, language, control=None):
    if not re.fullmatch(r'[A-Za-z0-9._-]+', model):
        raise ValueError('Invalid model ID')
    payload = {'contents': [{'parts': [
        {'text': PROMPT + '\nUse ' + language + '. Return raw source code without Markdown fences.'},
        {'inline_data': {'mime_type': 'image/png', 'data': base64.b64encode(png).decode('ascii')}}
    ]}]}
    body = json.dumps(payload).encode('utf-8')
    if len(body) >= 19000000:
        raise ValueError('Capture too large for inline request')
    request = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
        data=body, headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
    log = logging.getLogger('quiet-capture')
    started = time.monotonic()
    log.info('Opening Gemini HTTPS request (%s bytes); awaiting response headers. No app timeout; waiting for server response or connection failure.', len(body))
    opened = control.open(request) if control else urllib.request.urlopen(request, timeout=None)
    with opened as response:
        log.info('Response headers received after %.1fs; reading response body.', time.monotonic() - started)
        data = json.load(response)
        log.info('Response body received after %.1fs; validating answer.', time.monotonic() - started)
        return extract_code(data)


class Buffer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.epoch = getattr(self, 'epoch', 0) + 1
        self.text = ''
        self.index = 0
        return self.epoch

    def accept(self, epoch, text):
        if epoch != self.epoch:
            return False
        self.text, self.index = text, 0
        return True

    def peek(self):
        return self.text[self.index:self.index + 1]

    def advance(self):
        self.index = min(self.index + 1, len(self.text))
