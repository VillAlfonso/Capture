"""Small Windows shared-memory status channel; contains no capture or key data."""
import json
import logging
from collections import deque
import mmap
import time


class StateChannel:
    SIZE = 65536

    def __init__(self, name='Local\\QuietCaptureStateV2'):
        self.memory = mmap.mmap(-1, self.SIZE, tagname=name)

    def write(self, state):
        payload = dict(state, heartbeat=time.monotonic())
        if 'events' in payload:
            payload['events'] = list(payload['events'])
        data = json.dumps(payload).encode('utf-8')
        while len(data) >= self.SIZE and payload.get('events'):
            payload['events'].pop(0)
            data = json.dumps(payload).encode('utf-8')
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


class RecentEvents(logging.Handler):
    """Bounded diagnostic history in memory, with monotonic event IDs."""
    def __init__(self):
        super().__init__()
        self.events = deque(maxlen=50)
        self.sequence = 0
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        self.sequence += 1
        self.events.append({'id': self.sequence, 'text': self.format(record)[:900]})

    def snapshot(self):
        self.acquire()
        try:
            return list(self.events)
        finally:
            self.release()
