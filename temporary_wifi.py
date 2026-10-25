"""Request-scoped use of an existing Windows WLAN profile. No credentials stored."""
import ctypes as C
from ctypes import wintypes as W
import logging
import threading
import time
import urllib.request
import urllib.error

LOG = logging.getLogger('quiet-capture')
LEASE_LOCK = threading.Lock()


class GUID(C.Structure):
    _fields_ = [('data', C.c_ubyte * 16)]


class Interface(C.Structure):
    _fields_ = [('guid', GUID), ('description', W.WCHAR * 256), ('state', W.DWORD)]


class Profile(C.Structure):
    _fields_ = [('name', W.WCHAR * 256), ('flags', W.DWORD)]


class Radio(C.Structure):
    _fields_ = [('index', W.DWORD), ('software', W.DWORD), ('hardware', W.DWORD)]


class Connection(C.Structure):
    _fields_ = [('mode', W.DWORD), ('profile', W.LPCWSTR), ('ssid', C.c_void_p),
                ('bssid', C.c_void_p), ('bss_type', W.DWORD), ('flags', W.DWORD)]


def api_reachable():
    # No API key is sent. An HTTP error still proves HTTPS connectivity.
    try:
        with urllib.request.urlopen('https://api.openai.com/v1/models', timeout=3):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, urllib.error.URLError):
        return False


class NativeWifi:
    def __init__(self):
        self.dll = C.WinDLL('wlanapi')
        self.handle = W.HANDLE()
        signatures = {
            'WlanOpenHandle': [W.DWORD, C.c_void_p, C.POINTER(W.DWORD), C.POINTER(W.HANDLE)],
            'WlanCloseHandle': [W.HANDLE, C.c_void_p],
            'WlanEnumInterfaces': [W.HANDLE, C.c_void_p, C.POINTER(C.c_void_p)],
            'WlanGetProfileList': [W.HANDLE, C.POINTER(GUID), C.c_void_p, C.POINTER(C.c_void_p)],
            'WlanQueryInterface': [W.HANDLE, C.POINTER(GUID), W.DWORD, C.c_void_p, C.POINTER(W.DWORD), C.POINTER(C.c_void_p), C.c_void_p],
            'WlanSetInterface': [W.HANDLE, C.POINTER(GUID), W.DWORD, W.DWORD, C.c_void_p, C.c_void_p],
            'WlanConnect': [W.HANDLE, C.POINTER(GUID), C.POINTER(Connection), C.c_void_p],
            'WlanDisconnect': [W.HANDLE, C.POINTER(GUID), C.c_void_p],
        }
        for name, args in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes, fn.restype = args, W.DWORD
        self.dll.WlanFreeMemory.argtypes = [C.c_void_p]
        self.dll.WlanFreeMemory.restype = None
        version = W.DWORD()
        self.check(self.dll.WlanOpenHandle(2, None, C.byref(version), C.byref(self.handle)))

    @staticmethod
    def check(code):
        if code:
            raise OSError(code, 'Windows WLAN operation failed')

    def list_items(self, function, item_type, *args):
        pointer = C.c_void_p()
        self.check(function(self.handle, *args, None, C.byref(pointer)))
        try:
            count = W.DWORD.from_address(pointer.value).value
            return [item_type.from_buffer_copy(C.string_at(pointer.value + 8 + i * C.sizeof(item_type), C.sizeof(item_type))) for i in range(count)]
        finally:
            self.dll.WlanFreeMemory(pointer)

    def candidates(self, profile):
        return [item for item in self.list_items(self.dll.WlanEnumInterfaces, Interface)
                if item.state == 4 and any(p.name == profile for p in
                    self.list_items(self.dll.WlanGetProfileList, Profile, C.byref(item.guid)))]

    def query(self, item, opcode):
        pointer, size = C.c_void_p(), W.DWORD()
        self.check(self.dll.WlanQueryInterface(self.handle, C.byref(item.guid), opcode, None, C.byref(size), C.byref(pointer), None))
        try:
            return C.string_at(pointer, size.value)
        finally:
            self.dll.WlanFreeMemory(pointer)

    def radios(self, item):
        data = self.query(item, 4)
        count = W.DWORD.from_buffer_copy(data).value
        return [Radio.from_buffer_copy(data, 4 + i * C.sizeof(Radio)) for i in range(count)]

    def set_radio(self, item, radio, state):
        value = Radio(radio.index, state, radio.hardware)
        self.check(self.dll.WlanSetInterface(self.handle, C.byref(item.guid), 4, C.sizeof(value), C.byref(value), None))

    def connect(self, item, profile):
        params = Connection(0, profile, None, None, 3, 0)
        self.check(self.dll.WlanConnect(self.handle, C.byref(item.guid), C.byref(params), None))

    def connected_profile(self, item):
        # Current connection starts with two DWORDs followed by WCHAR[256].
        data = self.query(item, 6)
        if W.DWORD.from_buffer_copy(data).value != 1:
            return None
        return (W.WCHAR * 256).from_buffer_copy(self.query(item, 7), 8).value

    def disconnect(self, item):
        self.check(self.dll.WlanDisconnect(self.handle, C.byref(item.guid), None))

    def close(self):
        self.dll.WlanCloseHandle(self.handle, None)


class TemporaryWifi:
    def __init__(self, profile, control, backend=NativeWifi, reachable=api_reachable):
        self.profile, self.control = profile, control
        self.backend, self.reachable = backend, reachable
        self.lock = threading.RLock()
        self.wifi = self.item = None
        self.changed_radios = []
        self.owns_connection = self.leased = False
        self.closed = False

    def prepare(self):
        with self.lock:
            self.control.check()
            if self.closed:
                raise RuntimeError('Wi-Fi request already closed')
            if self.reachable():
                LOG.info('NETWORK: API reachable; existing Wi-Fi and Ethernet connections left unchanged.')
                return
            self.control.check()
            if not LEASE_LOCK.acquire(blocking=False):
                raise RuntimeError('Another temporary Wi-Fi request is still cleaning up')
            self.leased = True
            self.wifi = self.backend()
            candidates = self.wifi.candidates(self.profile)
            if len(candidates) != 1:
                raise RuntimeError('Expected exactly one disconnected Wi-Fi interface with the saved profile')
            self.item = candidates[0]
            for radio in self.wifi.radios(self.item):
                if radio.hardware == 2:
                    raise RuntimeError('Wi-Fi hardware radio is switched off')
                if radio.software == 2:
                    self.changed_radios.append(radio)
                    self.wifi.set_radio(self.item, radio, 1)
            self.control.check()
            self.owns_connection = True
            LOG.info('NETWORK: connecting temporarily to saved Wi-Fi profile %s.', self.profile)
            self.wifi.connect(self.item, self.profile)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                self.control.check()
                if self.wifi.connected_profile(self.item) == self.profile and self.reachable():
                    LOG.info('NETWORK: temporary Wi-Fi ready; sending API request.')
                    return
                self.control.cancelled.wait(0.5)
            raise TimeoutError('Saved Wi-Fi connection did not become ready within 30 seconds')

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            try:
                if self.owns_connection:
                    current = self.wifi.connected_profile(self.item)
                    if current not in (None, self.profile):
                        LOG.warning('NETWORK: Wi-Fi was switched to another profile; leaving the user connection unchanged.')
                        return
                    try:
                        self.wifi.disconnect(self.item)
                        LOG.info('NETWORK: temporary Wi-Fi disconnected; Ethernet unchanged.')
                    except OSError as error:
                        LOG.error('NETWORK: Wi-Fi disconnect failed (Windows error %s).', error.errno)
                for radio in self.changed_radios:
                    try:
                        self.wifi.set_radio(self.item, radio, 2)
                    except OSError as error:
                        LOG.error('NETWORK: restoring Wi-Fi radio failed (Windows error %s).', error.errno)
            except OSError as error:
                LOG.error('NETWORK: Wi-Fi cleanup failed (Windows error %s). Check Wi-Fi manually.', error.errno)
            finally:
                if self.wifi:
                    self.wifi.close()
                if self.leased:
                    LEASE_LOCK.release()
