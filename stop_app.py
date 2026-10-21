"""Explicitly stop the background app using its published message thread."""
import ctypes as C
from ctypes import wintypes as W
from runtime_state import StateChannel


def stop():
    channel = StateChannel()
    try:
        state = channel.read()
    finally:
        channel.close()
    if not state or not state.get('running'):
        print('No running background app reported.')
        return
    if not state.get('thread_id'):
        raise RuntimeError('Older app version: exit it once before using this launcher.')
    kernel, user = C.WinDLL('kernel32', use_last_error=True), C.WinDLL('user32', use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    user.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]
    handle = kernel.OpenProcess(0x100000, False, state['pid'])
    if not handle:
        raise RuntimeError('Cannot verify background process; no stop message sent.')
    try:
        if kernel.WaitForSingleObject(handle, 0) == 0:
            return
        if not user.PostThreadMessageW(state['thread_id'], 0x12, 0, 0):
            raise C.WinError(C.get_last_error())
        if kernel.WaitForSingleObject(handle, 5000) != 0:
            raise RuntimeError('App has not stopped; restart aborted.')
        print('Background app stopped.')
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    stop()
