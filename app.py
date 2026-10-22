"""Windowless Windows capture/replay utility. Does not hide its OS process."""
import ctypes as C
from ctypes import wintypes as W
import io
import json
import logging
from logging.handlers import QueueHandler, QueueListener
import os
from pathlib import Path
import queue
import sys
import subprocess
import threading
import time
import urllib.error

from runtime_state import StateChannel, RecentEvents

from core import Buffer, generate, rectangle, api_error_summary, RequestControl, RequestCancelled

LOG = logging.getLogger('quiet-capture')
RECENT_EVENTS = RecentEvents()
LOG.addHandler(RECENT_EVENTS)
LOG.setLevel(logging.INFO)


def debug_error(context, error):
    # Exception messages can include request data; show source locations only.
    import traceback
    frames = traceback.extract_tb(error.__traceback__)
    locations = ' -> '.join(f'{Path(f.filename).name}:{f.lineno} ({f.name})' for f in frames)
    LOG.error('%s: %s at %s', context, type(error).__name__, locations)


if getattr(sys, 'frozen', False):
    executable_dir = Path(sys.executable).resolve().parent
    ROOT = next((folder for folder in (executable_dir, executable_dir.parent, executable_dir.parent.parent)
                 if (folder / 'config.json').is_file()), executable_dir)
else:
    ROOT = Path(__file__).resolve().parent
U = C.WinDLL('user32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
P = C.WinDLL('crypt32', use_last_error=True)
PTR = C.c_size_t
RESULT = C.c_ssize_t
HOOK = C.WINFUNCTYPE(RESULT, C.c_int, W.WPARAM, W.LPARAM)


class KB(C.Structure):
    _fields_ = [('vk', W.DWORD), ('scan', W.DWORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', PTR)]


class MS(C.Structure):
    _fields_ = [('pt', W.POINT), ('data', W.DWORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', PTR)]


class KI(C.Structure):
    _fields_ = [('vk', W.WORD), ('scan', W.WORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', PTR)]


class MI(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('data', W.DWORD),
                ('flags', W.DWORD), ('time', W.DWORD), ('extra', PTR)]


class IU(C.Union):
    _fields_ = [('ki', KI), ('mi', MI)]


class INPUT(C.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', W.DWORD), ('u', IU)]


class BLOB(C.Structure):
    _fields_ = [('size', W.DWORD), ('data', C.POINTER(C.c_ubyte))]


def bind(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


bind(U, 'SetWindowsHookExW', W.HANDLE, C.c_int, HOOK, W.HINSTANCE, W.DWORD)
bind(U, 'CallNextHookEx', RESULT, W.HANDLE, C.c_int, W.WPARAM, W.LPARAM)
bind(U, 'UnhookWindowsHookEx', W.BOOL, W.HANDLE)
bind(U, 'GetForegroundWindow', W.HWND)
bind(U, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
bind(U, 'GetMessageW', W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
bind(U, 'TranslateMessage', W.BOOL, C.POINTER(W.MSG))
bind(U, 'DispatchMessageW', RESULT, C.POINTER(W.MSG))
bind(U, 'RegisterHotKey', W.BOOL, W.HWND, C.c_int, W.UINT, W.UINT)
bind(U, 'UnregisterHotKey', W.BOOL, W.HWND, C.c_int)
bind(U, 'PostThreadMessageW', W.BOOL, W.DWORD, W.UINT, W.WPARAM, W.LPARAM)
bind(U, 'SendInput', W.UINT, W.UINT, C.POINTER(INPUT), C.c_int)
bind(K, 'GetModuleHandleW', W.HMODULE, W.LPCWSTR)
bind(K, 'CreateMutexW', W.HANDLE, C.c_void_p, W.BOOL, W.LPCWSTR)
bind(K, 'CloseHandle', W.BOOL, W.HANDLE)
bind(K, 'OpenProcess', W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
bind(K, 'QueryFullProcessImageNameW', W.BOOL, W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
bind(K, 'GetCurrentThreadId', W.DWORD)
bind(K, 'LocalFree', C.c_void_p, C.c_void_p)
bind(P, 'CryptUnprotectData', W.BOOL, C.POINTER(BLOB), C.c_void_p,
     C.c_void_p, C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(BLOB))


def read_key():
    if os.environ.get('OPENAI_API_KEY'):
        return os.environ['OPENAI_API_KEY'].strip()
    data = (ROOT / 'openai-key.dpapi').read_bytes()
    raw = (C.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = BLOB(len(data), raw), BLOB()
    if not P.CryptUnprotectData(C.byref(source), None, None, None, None, 1, C.byref(target)):
        raise C.WinError(C.get_last_error())
    try:
        return C.string_at(target.data, target.size).decode('utf-8').strip()
    finally:
        C.memset(target.data, 0, target.size)
        K.LocalFree(target.data)


def foreground_allowed(allowed):
    hwnd = U.GetForegroundWindow()
    pid = W.DWORD()
    U.GetWindowThreadProcessId(hwnd, C.byref(pid))
    handle = K.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return 0
    try:
        name, size = C.create_unicode_buffer(32768), W.DWORD(32768)
        if K.QueryFullProcessImageNameW(handle, 0, name, C.byref(size)):
            if Path(name.value).name.lower() in allowed:
                return hwnd
    finally:
        K.CloseHandle(handle)
    return 0


def send_character(char):
    # Unicode packets avoid depending on the user's keyboard layout.
    events = []
    if char == '\n':
        events = [INPUT(type=1, ki=KI(vk=13)), INPUT(type=1, ki=KI(vk=13, flags=2))]
    else:
        encoded = char.encode('utf-16-le')
        for i in range(0, len(encoded), 2):
            unit = int.from_bytes(encoded[i:i + 2], 'little')
            events += [INPUT(type=1, ki=KI(scan=unit, flags=4)),
                       INPUT(type=1, ki=KI(scan=unit, flags=6))]
    batch = (INPUT * len(events))(*events)
    return U.SendInput(len(events), batch, C.sizeof(INPUT)) == len(events)


def send_backspace():
    events = (INPUT * 2)(INPUT(type=1, ki=KI(vk=8)),
                         INPUT(type=1, ki=KI(vk=8, flags=2)))
    return U.SendInput(2, events, C.sizeof(INPUT)) == 2


class App:
    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self._status = value
        LOG.info('Status: %s', value)

    def __init__(self, config):
        self.config = config
        self.debug_mode = '--debug' in sys.argv
        self.allowed = {s.lower() for s in config['allowed_processes']}
        self.buffer = Buffer()
        self.lock = threading.RLock()
        self.work = queue.Queue()
        self.active = not config.get('start_paused', False)
        self.held = False
        self.hold_generation = 0
        self.target = 0
        self.blocked = set()
        self.mouse_blocked = set()
        self.start = None
        self.png = None
        self.busy = False
        self.request_control = None
        self.status = 'idle' if self.active else 'paused'
        self.thread_id = K.GetCurrentThreadId()
        self.kb_callback, self.ms_callback = HOOK(self.keyboard), HOOK(self.mouse)

    def clear(self):
        with self.lock:
            self.buffer.reset()
            self.png = None
            self.start = None
            self.status = 'idle'
            self.target = 0

    def cancel_pending(self):
        with self.lock:
            control = self.request_control
            self.request_control = None
            self.busy = False
            self.clear()
            while True:
                try:
                    self.work.get_nowait()
                except queue.Empty:
                    break
        if control:
            control.cancel()
            LOG.info('CANCELLED LOCALLY: connection closed; pending actions discarded. Server-side cancellation is not guaranteed.')
        else:
            LOG.info('Pending actions cleared; no active request.')

    def keyboard(self, code, msg, address):
        if code < 0:
            return U.CallNextHookEx(None, code, msg, address)
        event = C.cast(address, C.POINTER(KB)).contents
        if event.flags & 0x10:
            return U.CallNextHookEx(None, code, msg, address)
        vk, down = event.vk, msg in (0x100, 0x104)
        if vk == 0xA5:
            if down and not self.held and self.active:
                self.target = foreground_allowed(self.allowed)
                self.held = bool(self.target)
                if self.held:
                    self.hold_generation += 1
                    LOG.info('REPLAY RESUMED: next character %s of %s.', self.buffer.index + 1, len(self.buffer.text))
            elif not down and self.held:
                self.held = False
                self.hold_generation += 1
                self.target = 0
                LOG.info('REPLAY PAUSED: position %s/%s saved. Hold Right Alt again to continue.', self.buffer.index, len(self.buffer.text))
                return 1
            if self.held:
                return 1
        if vk in self.blocked:
            if not down:
                self.blocked.discard(vk)
            return 1
        if self.held:
            if down and vk not in self.blocked:
                self.blocked.add(vk)
                # Escape cancels this answer; modifiers do not advance it.
                if vk == 27:
                    self.clear()
                elif vk not in (16,17,18,91,92,160,161,162,163,164,165):
                    if self.active and self.target == U.GetForegroundWindow():
                        action = 'backspace' if vk == 8 else 'type'
                        self.work.put((action, self.buffer.epoch, (self.target, self.hold_generation)))
            return 1
        return U.CallNextHookEx(None, code, msg, address)

    def mouse(self, code, msg, address):
        if code < 0 or msg not in (0x20B, 0x20C):
            return U.CallNextHookEx(None, code, msg, address)
        event = C.cast(address, C.POINTER(MS)).contents
        button, down = (event.data >> 16) & 0xFFFF, msg == 0x20B
        LOG.info('Mouse side button: XBUTTON%s / Button %s %s; active=%s; injected=%s',
                 button, button + 3, 'DOWN' if down else 'UP', self.active, bool(event.flags & 1))
        if button not in (1, 2) or event.flags & 1:
            return U.CallNextHookEx(None, code, msg, address)
        if not down and button in self.mouse_blocked:
            self.mouse_blocked.discard(button)
            if button == 1 and self.active and self.start:
                start, self.start = self.start, None
                try:
                    box = rectangle(start, (event.pt.x, event.pt.y))
                    LOG.info('Capture selected: %s x %s pixels', box[2] - box[0], box[3] - box[1])
                    self.work.put(('capture', self.buffer.epoch, box))
                except ValueError:
                    self.status = 'selection-too-small'
                    LOG.warning('Hold Button 4, move diagonally, then release. Both width and height must be at least 4 pixels.')
            return 1
        if not self.active:
            return U.CallNextHookEx(None, code, msg, address)
        if down:
            self.mouse_blocked.add(button)
            if button == 1:
                self.clear()
                self.start = (event.pt.x, event.pt.y)
                LOG.info('Selection started. Keep holding Button 4, drag diagonally, then release to capture.')
            else:
                self.work.put(('send', self.buffer.epoch, None))
        return 1

    def request(self, epoch, png, control):
        started = time.monotonic()
        done = threading.Event()

        def progress():
            while not done.wait(10):
                if control.cancelled.is_set():
                    return
                LOG.info('Request still pending after %.0fs; this does not confirm server-side processing.', time.monotonic() - started)

        if LOG.isEnabledFor(logging.INFO):
            threading.Thread(target=progress, daemon=True).start()
        try:
            LOG.info('Loading API key locally.')
            key = read_key()
            LOG.info('API key loaded; preparing request.')
            control.check()
            result = generate(png, key, self.config['model'], self.config['language'], control)
            control.check()
            with self.lock:
                if self.buffer.accept(epoch, result):
                    self.status = 'ready'
                    LOG.info('Answer ready after %.1fs (%s characters).', time.monotonic() - started, len(result))
                else:
                    LOG.info('Response ignored because the capture was cleared or replaced.')
        except RequestCancelled:
            LOG.info('Cancelled request worker stopped.')
        except urllib.error.HTTPError as error:
            if control.cancelled.is_set():
                error.close()
                return
            for line in api_error_summary(error):
                LOG.error('%s', line)
            with self.lock:
                if epoch == self.buffer.epoch:
                    self.status = 'api-http-' + str(error.code)
        except Exception as error:
            if control.cancelled.is_set():
                LOG.info('Cancelled request connection released.')
                return
            if isinstance(error, TimeoutError) or (isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)):
                LOG.error('NETWORK TIMEOUT: The connection reported a timeout; this app has no fixed request deadline. Quota/authentication status UNKNOWN.')
            elif isinstance(error, urllib.error.URLError):
                LOG.error('CONNECTION ERROR: Could not complete HTTPS connection (%s). Check network, proxy, DNS, or TLS. Quota status UNKNOWN.', type(error.reason).__name__)
            debug_error('OpenAI request failed', error)
            with self.lock:
                if epoch == self.buffer.epoch:
                    self.status = 'request-error-' + type(error).__name__
        finally:
            done.set()
            LOG.info('Request ended after %.1fs.', time.monotonic() - started)
            with self.lock:
                if self.request_control is control:
                    self.request_control = None
                    self.busy = False

    def worker(self):
        try:
            from PIL import ImageGrab
        except Exception as error:
            self.status = 'worker-start-failed'
            debug_error('Capture worker could not start', error)
            return
        while True:
            action, epoch, value = self.work.get()
            try:
                if epoch != self.buffer.epoch or not self.active:
                    continue
                if action == 'capture':
                    picture = ImageGrab.grab(bbox=value, all_screens=True)
                    output = io.BytesIO()
                    picture.save(output, format='PNG')
                    with self.lock:
                        if epoch == self.buffer.epoch:
                            self.png = output.getvalue()
                            self.status = 'captured'
                elif action == 'send':
                    with self.lock:
                        if self.busy:
                            LOG.info('Request already in progress; wait for it to finish.')
                            continue
                        epoch = self.buffer.reset()
                        if self.config.get('rehearsal'):
                            self.buffer.accept(epoch, 'def demo():\n    return "ready"\n\nprint(demo())')
                            self.status = 'ready-rehearsal'
                        elif self.png:
                            self.busy = True
                            self.status = 'waiting'
                            control = RequestControl()
                            self.request_control = control
                            threading.Thread(target=self.request, args=(epoch, self.png, control), daemon=True).start()
                        else:
                            self.status = 'no-capture'
                elif action in ('type', 'backspace'):
                    self.replay_character(epoch, value, backspace=action == 'backspace')
            except Exception as error:
                debug_error('Worker action failed', error)
                self.status = 'local-error-' + type(error).__name__

    def replay_character(self, epoch, value, backspace=False):
        target, hold_generation = value
        with self.lock:
            if (epoch != self.buffer.epoch or not self.held or not self.active
                    or hold_generation != self.hold_generation
                    or target != self.target or target != U.GetForegroundWindow()):
                return
            if backspace:
                if self.buffer.index > 0:
                    if send_backspace():
                        self.buffer.rewind()
                        self.status = 'ready'
                        LOG.info('REPLAY BACKSPACE: position %s/%s; next tap retypes the removed character.', self.buffer.index, len(self.buffer.text))
                    else:
                        self.status = 'input-blocked'
                return
            char = self.buffer.peek()
            if char:
                if send_character(char):
                    self.buffer.advance()
                    if not self.buffer.peek():
                        self.status = 'finished'
                        LOG.info('REPLAY COMPLETE: all %s characters sent to the editor. Editor formatting is not verified.', len(self.buffer.text))
                else:
                    self.status = 'input-blocked'

    def publish_state(self, channel, stopped):
        last_report = time.monotonic()
        while not stopped.is_set():
            with self.lock:
                state = dict(pid=os.getpid(), running=True, active=self.active,
                             status=self.status, busy=self.busy, debug=False, thread_id=self.thread_id,
                             sent=self.buffer.index, total=len(self.buffer.text))
            state['events'] = RECENT_EVENTS.snapshot()
            channel.write(state)
            if self.debug_mode and time.monotonic() - last_report >= 10:
                LOG.info('LIVE: capture/typing=%s; status=%s; request=%s', 'ON' if state['active'] else 'OFF (paused)', state['status'], 'PENDING' if state['busy'] else 'NONE')
                last_report = time.monotonic()
            stopped.wait(0.25)

    def run(self):
        # Physical pixel coordinates, including mixed-DPI monitors.
        try:
            U.SetProcessDpiAwarenessContext(C.c_void_p(-4))
        except AttributeError:
            U.SetProcessDPIAware()
        LOG.info('STARTING: Checking for an existing instance...')
        mutex = K.CreateMutexW(None, False, 'Local\\QuietCaptureDemo')
        if not mutex:
            raise C.WinError(C.get_last_error())
        if C.get_last_error() == 183:
            K.CloseHandle(mutex)
            return
        restart_requested = False
        hooks, hotkeys = [], []
        channel, publisher = None, None
        state_stopped = threading.Event()
        try:
            LOG.info('STARTING: Registering hotkeys and installing mouse/keyboard hooks...')
            for identifier, key in ((1, 0x78), (2, 0x7B), (3, 0x79)):
                if not U.RegisterHotKey(None, identifier, 0x4003, key):
                    raise RuntimeError('Hotkey unavailable')
                hotkeys.append(identifier)
            module = K.GetModuleHandleW(None)
            for kind, callback in ((13, self.kb_callback), (14, self.ms_callback)):
                hook = U.SetWindowsHookExW(kind, callback, module, 0)
                if not hook:
                    raise C.WinError(C.get_last_error())
                hooks.append(hook)
            threading.Thread(target=self.worker, daemon=True).start()
            channel = StateChannel()
            publisher = threading.Thread(target=self.publish_state, args=(channel, state_stopped), daemon=True)
            publisher.start()
            LOG.info('================ BACKGROUND APP RUNNING ================')
            LOG.info('Capture/typing: %s. Ctrl+Alt+F9 toggles ON/OFF.', 'ON' if self.active else 'OFF (paused)')
            LOG.info('The app is listening for Ctrl+Alt+F9 even while capture/typing is OFF.')
            LOG.info('HOLD Button 4 and DRAG, then RELEASE to capture; Button 5: send.')
            LOG.info('No selection rectangle appears. Side-button DOWN/UP events will appear here in debug mode.')
            LOG.info('Right Alt + keys in PyCharm: replay.')
            LOG.info('Ctrl+Alt+F9: enable/pause. Ctrl+Alt+F12: restart and reload, initially paused. Use stop.cmd to exit.')
            message = W.MSG()
            while True:
                result = U.GetMessageW(C.byref(message), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    raise C.WinError(C.get_last_error())
                if message.message == 0x312:
                    if message.wParam == 2:
                        self.cancel_pending()
                        self.active = False
                        self.clear()
                        self.status = 'restarting'
                        LOG.info('RESTART REQUESTED: cancelling locally and reloading code/configuration. New instance starts paused.')
                        restart_requested = True
                        break
                    if message.wParam == 1:
                        self.active = not self.active
                        self.clear()
                        self.status = 'idle' if self.active else 'paused'
                        LOG.info('CTRL+ALT+F9 -> Capture/typing %s. Background app remains running.', 'ON - ready for Button 4' if self.active else 'OFF - paused')
                    if message.wParam == 3:
                        # Explicit diagnostic action only; no screenshots/code/keys.
                        (ROOT / 'status.txt').write_text(
                            f'active={self.active}\nstatus={self.status}\n'
                            f'characters={self.buffer.index}/{len(self.buffer.text)}\n', encoding='utf-8')
                U.TranslateMessage(C.byref(message))
                U.DispatchMessageW(C.byref(message))
        finally:
            state_stopped.set()
            if publisher:
                publisher.join()
            if channel:
                channel.write(dict(pid=os.getpid(), running=False, active=False, status="stopped", busy=False, debug=self.debug_mode))
                channel.close()
            self.active = False
            self.cancel_pending()
            for hook in hooks:
                U.UnhookWindowsHookEx(hook)
            for identifier in hotkeys:
                U.UnregisterHotKey(None, identifier)
            self.clear()
            K.CloseHandle(mutex)
            LOG.info('Stopped; input hooks released.')
        if restart_requested:
            command = ([sys.executable, '--start-paused'] if getattr(sys, 'frozen', False)
                       else [str(ROOT / '.venv' / 'Scripts' / 'pythonw.exe'), '-B', str(ROOT / 'app.py'), '--start-paused'])
            subprocess.Popen(command, cwd=str(ROOT), creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == '__main__':
    if '--stop' in sys.argv:
        from stop_app import stop
        stop()
        sys.exit(0)
    if '--monitor' in sys.argv:
        from monitor import main
        main()
        sys.exit(0)
    listener = None
    if '--debug' in sys.argv:
        events = queue.SimpleQueue()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S'))
        LOG.addHandler(QueueHandler(events))
        LOG.setLevel(logging.INFO)
        listener = QueueListener(events, handler)
        listener.start()
        LOG.info('STARTING: Python loaded; initializing Quiet Capture.')
        LOG.info('Temporary debug console enabled. No key, screenshot, or answer content is logged.')
    try:
        LOG.info('STARTING: Loading config.json...')
        settings = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
        LOG.info('Model: %s; rehearsal: %s', settings['model'], settings.get('rehearsal', False))
        LOG.info('Key available: %s', bool(os.environ.get('OPENAI_API_KEY')) or (ROOT / 'openai-key.dpapi').exists())
        if '--start-paused' in sys.argv:
            settings['start_paused'] = True
        App(settings).run()
    except Exception as error:
        debug_error('Startup/runtime failure (check dependencies and hotkey conflicts)', error)
        # No popup or error body that could contain a secret.
        (ROOT / 'startup-error.txt').write_text(type(error).__name__, encoding='utf-8')
        sys.exit(1)

    finally:
        if listener is not None:
            listener.stop()
