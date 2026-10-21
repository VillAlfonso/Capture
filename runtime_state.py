"""Small Windows shared-memory status channel; contains no capture or key data."""
import json
import mmap
import time


class StateChannel:
    SIZE = 4096

    def __init__(self, name='Local\\QuietCaptureStateV1'):
        self.memory = mmap.mmap(-1, self.SIZE, tagname=name)

    def write(self, state):
        data = json.dumps(dict(state, heartbeat=time.monotonic())).encode('utf-8')
        if len(data) >= self.SIZE:
            raise ValueError('Status too large')
        self.memory[:] = data + b'\0' * (self.SIZE - len(data))

    def read(self):
        first = self.memory[:]
        if first != self.memory[:]:
            return None
        try:
            state = json.loads(first.split(b'\0', 1)[0])
            return state if isinstance(state, dict) else None
        except (ValueError, UnicodeError):
            return None

    def close(self):
        self.memory.close()
