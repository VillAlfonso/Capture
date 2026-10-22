"""Read-only status monitor. Never starts capture, registers hotkeys, or owns the app."""
import time
from runtime_state import StateChannel


def describe(state, now):
    if not state:
        return 'NOT RUNNING / NO STATUS: use start.cmd or sign in to Windows. Monitor keeps waiting.'
    if not state.get('running'):
        return 'STOPPED: monitor keeps waiting for the next launch.'
    if now - state.get('heartbeat', 0) > 3:
        return 'NO LIVE HEARTBEAT: app may have stopped or be unresponsive. Monitor keeps waiting.'
    return ('LIVE: capture/typing=' + ('ON' if state['active'] else 'OFF (paused)')
            + '; status=' + state['status']
            + '; request=' + ('PENDING' if state['busy'] else 'NONE')
            + '; characters=' + str(state.get('sent', '?')) + '/' + str(state.get('total', '?'))
            + '; Ctrl+Alt+F9=toggle; Ctrl+Alt+F12=restart')


def main():
    print('MONITOR ONLY: closing this window leaves the background app running.', flush=True)
    channel = StateChannel()
    previous, last_report = None, 0
    owner, last_event = None, 0
    try:
        while True:
            now = time.monotonic()
            state = channel.read()
            if state:
                if owner != state.get('pid'):
                    owner, last_event = state.get('pid'), 0
                    print('--- Recent app events (up to 50), followed by live events ---', flush=True)
                events = state.get('events', [])
                unseen = [event for event in events if event['id'] > last_event]
                if unseen and last_event and unseen[0]['id'] > last_event + 1:
                    print('Some older events expired from the in-memory history.', flush=True)
                for event in unseen:
                    print(event['text'], flush=True)
                    last_event = event['id']
            summary = describe(state, now)
            if summary != previous or now - last_report >= 10:
                print(time.strftime('%H:%M:%S') + ' ' + summary, flush=True)
                previous, last_report = summary, now
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        channel.close()


if __name__ == '__main__':
    main()
