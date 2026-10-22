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
          'code characters and required string literals are allowed. '
          'MANDATORY COMPLETENESS RULE: Return a complete standalone runnable program, '
          'not just a function definition. Implement the actual general solution and '
          'preserve the function or class signature shown in the screenshot. Include '
          'all required imports, helper functions, and data structure definitions. '
          'For Python, include an if __name__ == "__main__": block that calls the '
          'solution with every fully readable example input from the screenshot, '
          'prints each computed result, and checks it against the corresponding '
          'expected output using assertions. Compare results according to the '
          'problem rules, including order-independent comparisons when applicable. '
          'Expected outputs are test expectations only: never substitute them for '
          'computing the answer or hardcode the solution to the examples. If no '
          'complete examples are readable, include a small valid demonstration '
          'input and print its computed result without inventing an expected output. '
          'The program must produce visible output when run directly in PyCharm '
          'without requiring interactive input. Keep demonstration code inside the '
          'main block and keep the solution reusable. Continue to return raw code '
          'only, without comments, Markdown, prose, or decorative output.')


def rectangle(start, end):
    left, right = sorted((start[0], end[0]))
    top, bottom = sorted((start[1], end[1]))
    if right - left < 4 or bottom - top < 4:
        raise ValueError('Selection is too small')
    return left, top, right, bottom


def extract_code(response):
    log = logging.getLogger('quiet-capture')
    if response.get('status') != 'completed':
        reason = (response.get('incomplete_details') or {}).get('reason')
        if reason == 'max_output_tokens':
            log.error('INCOMPLETE ANSWER: OpenAI reached its output token limit. Partial code rejected.')
        else:
            log.error('INCOMPLETE ANSWER: OpenAI did not complete the response. Nothing will be replayed.')
        raise ValueError('No complete answer returned')
    texts = []
    for item in response.get('output', []):
        if item.get('type') != 'message':
            continue
        if item.get('status') != 'completed':
            raise ValueError('Incomplete output message')
        for part in item.get('content', []):
            if part.get('type') == 'refusal':
                log.error('ANSWER REFUSED: no code will be replayed.')
                raise ValueError('Response refused')
            if part.get('type') == 'output_text':
                texts.append(part.get('text', ''))
    text = ''.join(texts).strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != '```':
            raise ValueError('Incomplete code fence')
        text = '\n'.join(lines[1:-1])
    if not text:
        raise ValueError('Empty response')
    text = text.replace('\r\n', '\n').replace('\r', '\n').expandtabs(4)
    if any(ord(c) < 32 and c != '\n' for c in text):
        raise ValueError('Unexpected control characters')
    return text


def validate_source(text, language):
    if language.strip().lower().startswith('python'):
        try:
            compile(text, '<generated-answer>', 'exec')
        except (SyntaxError, ValueError, OverflowError) as error:
            logging.getLogger('quiet-capture').error(
                'INVALID PYTHON: syntax validation failed (%s, line %s). Answer rejected before replay.',
                type(error).__name__, getattr(error, 'lineno', '?'))
            raise ValueError('Generated Python failed syntax validation') from None
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
        code = detail.get('code')
        hints_by_code = {
            'insufficient_quota': 'OpenAI quota/billing limit reached; check API credits and project limits.',
            'rate_limit_exceeded': 'OpenAI request/token rate limit reached; wait before retrying.',
            'invalid_api_key': 'OpenAI API key is invalid.',
            'model_not_found': 'Model unavailable or your project lacks access.',
            'context_length_exceeded': 'Input exceeds this model context limit.'}
        if code in hints_by_code:
            result.append(hints_by_code[code])
        retry = error.headers.get('Retry-After', '') if error.headers else ''
        if re.fullmatch(r'[0-9]{1,9}(?:\.[0-9]{1,9})?', retry):
            result.append('Suggested retry delay: ' + retry + ' seconds (no automatic retry).')
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
    payload = {'model': model, 'store': False,
               'instructions': PROMPT + '\nUse ' + language + '. Return raw source code without Markdown fences.',
               'input': [{'role': 'user', 'content': [
                   {'type': 'input_text', 'text': 'Solve the problem in this screenshot.'},
                   {'type': 'input_image', 'detail': 'high',
                    'image_url': 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')}
               ]}]}
    body = json.dumps(payload).encode('utf-8')
    if len(body) >= 19000000:
        raise ValueError('Capture too large for inline request')
    request = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=body, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}, method='POST')
    log = logging.getLogger('quiet-capture')
    started = time.monotonic()
    log.info('Opening OpenAI HTTPS request (%s bytes); awaiting response headers. No app timeout; waiting for server response or connection failure.', len(body))
    opened = control.open(request) if control else urllib.request.urlopen(request, timeout=None)
    with opened as response:
        log.info('Response headers received after %.1fs; reading response body.', time.monotonic() - started)
        data = json.load(response)
        log.info('Response body received after %.1fs; validating answer.', time.monotonic() - started)
        return validate_source(extract_code(data), language)


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

    def rewind(self):
        self.index = max(0, self.index - 1)
